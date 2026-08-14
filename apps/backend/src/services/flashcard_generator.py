"""Bölüm flashcard üretimi — konu başına map-reduce, atıf zorunlu (Yetenek 09).

SSE olayları yield eder:
  {"type": "status", "percent": int, "message": str}
  {"type": "done", "id": int, "chapter_id": int, "cards_json": [...],
   "card_count": int, "warnings": [...]}
  {"type": "error", "message": str}
"""

from __future__ import annotations

import json
import logging

from ..config import settings
from ..db import get_db
from ..prompts.common import dil_talimati
from ..prompts.flashcard_prompts import FLASHCARD_BATCH_PROMPT
from . import llm_service
from .note_generator import topic_matches
from .quiz_generator import _enrich_citations, _split_topics

logger = logging.getLogger(__name__)

MAX_BATCH_ATTEMPTS = 3  # ilk üretim + en fazla 2 yeniden üretim
MAX_CARDS_PER_TOPIC = 15
CARD_TYPES = ("qa", "term")


class FlashcardGenerationError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _validate_card(card: dict) -> bool:
    if not isinstance(card, dict):
        return False
    front = card.get("front")
    back = card.get("back")
    if not isinstance(front, str) or not front.strip():
        return False
    if not isinstance(back, str) or not back.strip():
        return False
    if card.get("type") not in CARD_TYPES:
        return False
    return isinstance(card.get("citations"), list)


def _dedup_cards(cards: list[dict]) -> list[dict]:
    """front normalize edilip (strip + casefold) çift kartlar ayıklanır."""
    seen: set[str] = set()
    result: list[dict] = []
    for card in cards:
        key = str(card.get("front", "")).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(card)
    return result


def _find_by_topic(mapping: dict[str, list], heading: str) -> list:
    for name, value in mapping.items():
        if topic_matches(heading, name):
            return value
    return []


def _quiz_questions_by_topic(questions_json: str | None) -> dict[str, list[dict]]:
    """Quiz sorularını konuya göre {soru, cevap} çiftlerine çevirir (qa kart kaynağı)."""
    if not questions_json:
        return {}
    try:
        data = json.loads(questions_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    result: dict[str, list[dict]] = {}
    for quiz_topic in data.get("topics", []):
        pairs: list[dict] = []
        for question in quiz_topic.get("questions", []):
            options = question.get("options", [])
            idx = question.get("correct_index")
            answer = ""
            if isinstance(idx, int) and isinstance(options, list) and 0 <= idx < len(options):
                answer = options[idx]
            pairs.append({"question": question.get("question", ""), "answer": answer})
        result[quiz_topic.get("topic", "")] = pairs
    return result


async def _generate_batch(
    topic: dict,
    course_id: int,
    chapter_id: int,
    keywords: list[str],
    quiz_questions: list[dict],
) -> list[dict] | None:
    """Bir konu için kart zarfı üretir; yapı/atıf denetiminden geçen kartları döner.

    Kaynak (atıf) yoksa atıfsız kartlar `citations: []` ile kabul edilir (quiz'in YUMUŞAK
    GEÇİŞ kalıbı). Atıf varsa mevcut zorunluluk aynen korunur.
    """
    allowed = topic.get("citations", [])
    allowed_text = json.dumps(
        [{"id": c.get("id")} for c in allowed if c.get("id") is not None],
        ensure_ascii=False,
    )
    prompt = FLASHCARD_BATCH_PROMPT.format(
        topic=topic["topic"],
        note_section=topic["section"][:4000],
        keywords=json.dumps(keywords or [], ensure_ascii=False),
        questions=json.dumps(quiz_questions or [], ensure_ascii=False),
        citations_json=allowed_text,
        dil_talimati=dil_talimati(settings.not_dili),
    )

    for _ in range(MAX_BATCH_ATTEMPTS):
        try:
            data = await llm_service.chat_json(
                [{"role": "user", "content": prompt}],
                kind="flashcards",
                course_id=course_id,
                chapter_id=chapter_id,
            )
        except llm_service.LLMError:
            # API/JSON hatası: konu sessizce atlanır — kullanıcıya hata gösterilmez
            return None
        cards = data.get("cards", [])
        if not isinstance(cards, list):
            continue
        # atıf elemanlarını yalnızca sözlüklere indirge (zenginleştirme güvenliği)
        cards = [c for c in cards if _validate_card(c)]
        for card in cards:
            card["citations"] = [r for r in card.get("citations", []) if isinstance(r, dict)]
        if not cards:
            continue
        if allowed:
            cards = _enrich_citations(cards, allowed)
            # atıf varsa zorunlu: atıfsız kart reddedilir (Yetenek 09)
            cards = [c for c in cards if c["citations"]]
            if not cards:
                continue
        else:
            # kaynak yok: atıfsız kartlar citations: [] ile kabul edilir (YUMUŞAK GEÇİŞ)
            for card in cards:
                card["citations"] = []
        for card in cards:
            card["topic"] = topic["topic"]
        return cards[:MAX_CARDS_PER_TOPIC]
    return None


async def generate_flashcards_stream(chapter_id: int):
    """Bölüm flashcard üretim hattı — SSE olayları yield eder (Yetenek 09)."""
    try:
        async for event in _generate(chapter_id):
            yield event
    except FlashcardGenerationError as exc:
        yield {"type": "error", "message": str(exc)}
    except llm_service.LLMError as exc:
        yield {"type": "error", "message": str(exc)}
    except Exception:
        logger.exception("flashcard üretimi başarısız: chapter=%s", chapter_id)
        yield {
            "type": "error",
            "message": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
        }


async def _generate(chapter_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id FROM chapters WHERE id = ?", (chapter_id,)
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise FlashcardGenerationError("Chapter bulunamadı")
        course_id = chapter["course_id"]
        cursor = await db.execute(
            "SELECT content_md, citations_json, topics_json FROM notes "
            "WHERE chapter_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id,),
        )
        note_row = await cursor.fetchone()
        cursor = await db.execute(
            "SELECT questions_json FROM quizzes "
            "WHERE chapter_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id,),
        )
        quiz_row = await cursor.fetchone()
    finally:
        await db.close()

    if note_row is None:
        raise FlashcardGenerationError(
            "Önce not oluştur — flashcard'lar notun üzerinden üretilir."
        )

    content_md = note_row["content_md"]
    citations_json = json.loads(note_row["citations_json"] or "{}")
    topics_meta = json.loads(note_row["topics_json"] or "[]")

    sections = _split_topics(content_md, citations_json.get("topics", []))
    if not sections:
        raise FlashcardGenerationError("Not içeriğinden konu bölümü çıkarılamadı.")

    keyword_map = {
        t.get("topic", ""): t.get("keywords", [])
        for t in topics_meta
        if isinstance(t, dict)
    }
    quiz_by_topic = _quiz_questions_by_topic(
        quiz_row["questions_json"] if quiz_row else None
    )

    all_cards: list[dict] = []
    warnings: list[str] = []
    total = len(sections)
    for i, topic in enumerate(sections):
        percent = int(5 + 90 * i / max(total, 1))
        yield {
            "type": "status",
            "percent": percent,
            "message": f"“{topic['topic']}” için kartlar hazırlanıyor…",
        }
        keywords = _find_by_topic(keyword_map, topic["topic"])
        quiz_questions = _find_by_topic(quiz_by_topic, topic["topic"])
        cards = await _generate_batch(
            topic, course_id, chapter_id, keywords, quiz_questions
        )
        if not cards:
            # Asla başarısız olma: sorunlu konu uyarıyla atlanır, set yine teslim edilir.
            warnings.append(f"“{topic['topic']}” için kart üretilemedi (atlandı).")
            continue
        if not topic.get("citations"):
            warnings.append(f"“{topic['topic']}”: atıfsız kartlar (kaynak yok)")
        all_cards.extend(cards)

    all_cards = _dedup_cards(all_cards)

    if not all_cards:
        raise FlashcardGenerationError(
            "Kart üretilemedi — önce not/quiz oluşturup tekrar deneyin."
        )

    yield {"type": "status", "percent": 97, "message": "Kartlar kaydediliyor…"}

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO flashcard_sets (course_id, chapter_id, cards_json, model_used) "
            "VALUES (?, ?, ?, ?)",
            (
                course_id,
                chapter_id,
                json.dumps(all_cards, ensure_ascii=False),
                settings.model,
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("flashcard seti kimliği alınamadı")
    finally:
        await db.close()

    yield {
        "type": "done",
        "id": row_id,
        "chapter_id": chapter_id,
        "cards_json": all_cards,
        "card_count": len(all_cards),
        "warnings": warnings,
    }
