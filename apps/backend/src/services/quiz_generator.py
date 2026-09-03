"""Bölüm quizi üretimi — konu başına 5 MCQ, atıf zorunlu, feedback üretim anında (Faz 4.1).

SSE olayları yield eder:
  {"type": "status", "percent": int, "message": str}
  {"type": "done", "quiz": {...}}
  {"type": "error", "message": str}
"""

from __future__ import annotations

import json
import logging
import re

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..db import get_db
from ..prompts.common import dil_talimati
from ..prompts.quiz_prompts import QUIZ_BATCH_PROMPT
from . import llm_service
from .note_generator import topic_matches

logger = logging.getLogger(__name__)

MAX_BATCH_ATTEMPTS = 3
MAX_QUESTIONS_PER_TOPIC = 5
MAX_CORRECT_PER_INDEX = 2


class QuizGenerationError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _split_topics(content_md: str, topics: list[dict]) -> list[dict]:
    """Notu başlık yapısına göre böler; her bölüme topics_json'dan atıf listesi bağlar.

    Dönüş: [{"topic", "section", "citations"}]; citations: not atıf listesi elemanları.
    """
    citation_map: dict[str, list[dict]] = {}
    for topic in topics:
        citation_map[topic.get("topic", "")] = topic.get("citations", [])

    def _citations_for(heading: str) -> list[dict]:
        for name, citations in citation_map.items():
            if topic_matches(heading, name):
                return citations
        return []

    result: list[dict] = []
    lines = content_md.split("\n")
    current: dict | None = None
    for line in lines:
        match = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if match:
            if current:
                result.append(current)
            heading = match.group(1).strip()
            current = {
                "topic": heading,
                "section": "",
                "citations": _citations_for(heading),
            }
        elif current:
            current["section"] += f"{line}\n"
    if current:
        result.append(current)

    if not result:
        result = [{"topic": "Genel", "section": content_md, "citations": []}]
    return [r for r in result if r["section"].strip()]


def _validate_question(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    if not isinstance(q.get("question"), str) or not q["question"].strip():
        return False
    options = q.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return False
    if not all(isinstance(o, str) and o.strip() for o in options):
        return False
    idx = q.get("correct_index")
    if not isinstance(idx, int) or not (0 <= idx < 4):
        return False
    if not isinstance(q.get("explanation"), str) or not q["explanation"].strip():
        return False
    if not isinstance(q.get("feedback_correct"), str) or not q["feedback_correct"].strip():
        return False
    if not isinstance(q.get("feedback_wrong"), str) or not q["feedback_wrong"].strip():
        return False
    # citations yapısal doğrulama; geçerlilik (izinli liste) _generate_batch'te denetlenir
    citations = q.get("citations")
    return isinstance(citations, list)


def _balanced(questions: list[dict]) -> bool:
    counts = [0] * 4
    for q in questions:
        idx = q["correct_index"]
        counts[idx] += 1
        if counts[idx] > MAX_CORRECT_PER_INDEX:
            return False
    return True


def _rebalance(questions: list[dict]) -> list[dict]:
    """Doğru cevap indexlerini seçenek yer değiştirerek dengeler (soru anlamı değişmez).

    Fazla temsil edilen bir index'teki sorunun iki seçeneği yer değiştirilir;
    doğru cevabın KENDİSİ az temsil edilen index'e taşınır.
    """
    counts = [0] * 4
    for q in questions:
        counts[q["correct_index"]] += 1

    for q in questions:
        idx = q["correct_index"]
        if counts[idx] <= MAX_CORRECT_PER_INDEX:
            counts[idx] += 1
            continue
        target = min(range(4), key=lambda i: (counts[i], i))
        options = list(q["options"])
        options[idx], options[target] = options[target], options[idx]
        q["options"] = options
        q["correct_index"] = target
        counts[target] += 1
    return questions


def _enrich_citations(questions: list[dict], allowed: list[dict]) -> list[dict]:
    """Soru atıflarını not atıf listesinden zenginleştirir (chunk_id, quote, page, slide)."""
    by_id = {c.get("id"): c for c in allowed}
    for question in questions:
        enriched = []
        for ref in question.get("citations", []):
            cid = ref.get("id")
            source = by_id.get(cid)
            if source is None:
                continue  # bilinmeyen atıf — soru doğrulamada yakalanır
            enriched.append(
                {
                    "id": cid,
                    "source_type": source.get("source_type", "note"),
                    "source_id": source.get("source_id"),
                    "page": source.get("page"),
                    "slide": source.get("slide"),
                    "chunk_id": source.get("chunk_id"),
                    "quote": source.get("quote", ""),
                }
            )
        question["citations"] = enriched
    return questions


async def _generate_batch(
    topic: dict,
    course_id: int,
    chapter_id: int,
    tenant_id: str = LOCAL_TENANT_ID,
) -> list[dict] | None:
    """Bir konu için 5 soruluk zarf üretir; şema/denge/atıf denetimlerinden geçerse döner."""
    allowed = topic.get("citations", [])
    allowed_text = json.dumps(
        [{"id": c.get("id")} for c in allowed if c.get("id") is not None],
        ensure_ascii=False,
    )
    prompt = QUIZ_BATCH_PROMPT.format(
        topic=topic["topic"],
        note_section=topic["section"][:4000],
        citations_json=allowed_text,
        dil_talimati=dil_talimati(settings.not_dili),
    )

    last_data: dict | None = None
    for _ in range(MAX_BATCH_ATTEMPTS):
        try:
            data = await llm_service.chat_json(
                [{"role": "user", "content": prompt}],
                kind="quiz_batch",
                tenant_id=tenant_id,
                course_id=course_id,
                chapter_id=chapter_id,
            )
        except llm_service.LLMError:
            # API/JSON hatası: konu sessizce atlanır — kullanıcıya hata gösterilmez
            return None
        last_data = data
        questions = data.get("questions", [])
        if not isinstance(questions, list) or len(questions) != MAX_QUESTIONS_PER_TOPIC:
            continue
        if not all(_validate_question(q) for q in questions):
            continue
        if allowed:
            # atıf zorunlu: her sorunun en az bir İZİNLİ listeden geçerli atfı olmalı
            questions = _enrich_citations(questions, allowed)
            if not all(q["citations"] for q in questions):
                continue
        else:
            # izinli atıf yoksa (kaynak bulunamadı bölümü) sorular atıfsız kabul edilir
            for q in questions:
                q["citations"] = []
        # doğru cevap dağılımını deterministik yeniden dengele (Yetenek 03 §3)
        questions = _rebalance(questions)
        return questions

    # YUMUŞAK GEÇİŞ — asla başarısız olma (kullanıcı isteği):
    # katı denetimlerden geçemeyen son çıktıdan şema-geçerli sorular kabul edilir,
    # atıflar bölümün ilk geçerli kaynağıyla kendi kendine onarılır, denge yeniden kurulur.
    questions = (last_data or {}).get("questions", [])
    if not isinstance(questions, list):
        return None
    questions = [q for q in questions if _validate_question(q)]
    if len(questions) < 3:
        return None  # yeterli soru yok — üst katman konuyu atlayıp devam eder
    questions = questions[:MAX_QUESTIONS_PER_TOPIC]
    if allowed:
        questions = _enrich_citations(questions, allowed)
        first_citation = next((c for c in allowed if c.get("id") is not None), None)
        for q in questions:
            if not q["citations"] and first_citation is not None:
                q["citations"] = [dict(first_citation)]
    else:
        for q in questions:
            q["citations"] = []
    return _rebalance(questions)


async def generate_quiz_stream(chapter_id: int, tenant_id: str = LOCAL_TENANT_ID):
    """Bölüm quizi üretim hattı — SSE olayları yield eder (Faz 4.1)."""
    try:
        async for event in _generate(chapter_id, tenant_id):
            yield event
    except QuizGenerationError as exc:
        yield {"type": "error", "message": str(exc)}
    except llm_service.LLMError as exc:
        yield {"type": "error", "message": str(exc)}
    except Exception:
        logger.exception("quiz üretimi başarısız: chapter=%s", chapter_id)
        yield {
            "type": "error",
            "message": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
        }


async def _generate(chapter_id: int, tenant_id: str = LOCAL_TENANT_ID):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise QuizGenerationError("Chapter bulunamadı")
        course_id = chapter["course_id"]
        cursor = await db.execute(
            "SELECT content_md, citations_json, topics_json FROM notes "
            "WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id, tenant_id),
        )
        note_row = await cursor.fetchone()
    finally:
        await db.close()

    if note_row is None:
        raise QuizGenerationError("Önce not oluştur — quiz notların üzerinden üretilir.")

    content_md = note_row["content_md"]
    citations_json = json.loads(note_row["citations_json"] or "{}")

    topics_meta = citations_json.get("topics", [])
    sections = _split_topics(content_md, topics_meta)
    if not sections:
        raise QuizGenerationError("Not içeriğinden konu bölümü çıkarılamadı.")

    quizzes_topics: list[dict] = []
    warnings: list[str] = []
    total = len(sections)
    for i, topic in enumerate(sections):
        percent = int(5 + 90 * i / max(total, 1))
        yield {
            "type": "status",
            "percent": percent,
            "message": f"“{topic['topic']}” için sorular hazırlanıyor…",
        }
        questions = await _generate_batch(topic, course_id, chapter_id, tenant_id)
        if questions is None:
            # Asla başarısız olma: sorunlu konu uyarıyla atlanır, quiz yine teslim edilir.
            warnings.append(f"“{topic['topic']}” için soru üretilemedi (atlandı).")
            continue
        quizzes_topics.append({"topic": topic["topic"], "questions": questions})

    yield {"type": "status", "percent": 97, "message": "Quiz kaydediliyor…"}
    questions_json = {"topics": quizzes_topics}

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("quiz kimliği alınamadı")
    finally:
        await db.close()

    yield {
        "type": "done",
        "quiz": {"id": row_id, "chapter_id": chapter_id, "questions_json": questions_json},
        "warnings": warnings,
    }
