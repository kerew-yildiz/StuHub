"""Genel quiz üretimi — 55 soru (20 MCQ + 15 TF + 15 FIB + 5 açık uçlu), seed'li karışık (Faz 5.1)."""
# ruff: noqa: E501 — uzun Türkçe etiket satırları

from __future__ import annotations

import json
import logging
import random

from ..config import settings
from ..db import get_db
from ..prompts.common import dil_talimati
from ..prompts.overall_prompts import OVERALL_BATCH_PROMPT
from . import llm_service
from .quiz_generator import _rebalance as _rebalance_mcq
from .quiz_generator import _validate_question as _validate_mcq

logger = logging.getLogger(__name__)

BATCH_PLAN: list[tuple[str, int]] = [
    ("mcq", 5),
    ("mcq", 5),
    ("mcq", 5),
    ("mcq", 5),
    ("tf", 8),
    ("tf", 7),
    ("fib", 5),
    ("fib", 5),
    ("fib", 5),
    ("open", 5),
]
# Puanlama: mcq 20×1 + tf 15×1 + fib 15×1 + açık uçlu 5×10 = 100
EXPECTED_COUNTS = {"mcq": 20, "tf": 15, "fib": 15, "open": 5}
MIN_TF_TRUE = 7
MAX_TF_TRUE = 8
MAX_BATCH_ATTEMPTS = 3
NOTE_CONTEXT_CHARS = 5000
CITATIONS_CONTEXT_CHARS = 3000


class OverallGenerationError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _validate_overall_question(q: dict, category: str) -> bool:
    if not isinstance(q, dict) or q.get("type") != category:
        return False
    if not isinstance(q.get("topic"), str) or not q["topic"].strip():
        return False
    if category == "open":
        # açık uçlu: atıflar answer_key.citations içinde (Yetenek 04 şeması)
        question = q.get("question")
        if not isinstance(question, str) or not question.strip():
            return False
        key = q.get("answer_key")
        if not isinstance(key, dict) or not isinstance(key.get("points"), list):
            return False
        if not key["points"]:
            return False
        key_citations = key.get("citations")
        return isinstance(key_citations, list) and bool(key_citations)
    citations = q.get("citations")
    if not isinstance(citations, list) or not citations:
        return False
    if category == "mcq":
        return _validate_mcq(q)
    if category == "tf":
        if not isinstance(q.get("statement"), str) or not q["statement"].strip():
            return False
        if not isinstance(q.get("answer"), bool):
            return False
        return all(
            isinstance(q.get(f), str) and q[f].strip()
            for f in ("explanation", "feedback_correct", "feedback_wrong")
        )
    if category == "fib":
        if not isinstance(q.get("text"), str) or "____" not in q["text"]:
            return False
        answers = q.get("accepted_answers")
        if not isinstance(answers, list) or not answers:
            return False
        if not all(isinstance(a, str) and a.strip() for a in answers):
            return False
        return all(
            isinstance(q.get(f), str) and q[f].strip()
            for f in ("explanation", "feedback_correct", "feedback_wrong")
        )
    return False


async def _load_course_notes(course_id: int) -> list[dict]:
    """Dersin tüm chapter notlarını (en güncel) toplar."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, title FROM chapters WHERE course_id = ? ORDER BY id", (course_id,)
        )
        chapters = await cursor.fetchall()
        notes: list[dict] = []
        for chapter in chapters:
            cursor = await db.execute(
                "SELECT content_md, citations_json FROM notes "
                "WHERE chapter_id = ? ORDER BY id DESC LIMIT 1",
                (chapter["id"],),
            )
            row = await cursor.fetchone()
            if row is not None:
                notes.append(
                    {
                        "chapter_id": chapter["id"],
                        "chapter_title": chapter["title"],
                        "content_md": row["content_md"],
                        "citations_json": json.loads(row["citations_json"] or "{}"),
                    }
                )
    finally:
        await db.close()
    return notes


def _build_context(notes: list[dict]) -> tuple[list[dict], str, str]:
    """Global atıf havuzu (1-bazlı _gid), not parçaları ve dağılım planı metni üretir."""
    citation_pool: list[dict] = []
    sections: list[str] = []
    distribution: list[str] = []
    for note in notes:
        topics = note["citations_json"].get("topics", [])
        topic_names = [t.get("topic", "") for t in topics if t.get("topic")]
        distribution.append(
            f"- {note['chapter_title']}: {', '.join(topic_names) or 'konu yok'}"
        )
        sections.append(
            f"### Chapter: {note['chapter_title']}\n\n{note['content_md'][:NOTE_CONTEXT_CHARS]}"
        )
        for topic in topics:
            for citation in topic.get("citations", []):
                if isinstance(citation, dict):
                    citation_pool.append(dict(citation))
    for i, citation in enumerate(citation_pool, start=1):
        citation["_gid"] = i
    return (
        citation_pool,
        "\n\n".join(sections),
        "\n".join(distribution),
    )


def _map_citations(question: dict, citation_pool: list[dict]) -> bool:
    """Soru atıflarını _gid üzerinden gerçek kaynaklara eşler; bilinmeyen atıf → False.

    Açık uçlu sorularda atıflar answer_key.citations içindedir (Yetenek 04 şeması).
    """
    if question["type"] == "open":
        refs = question["answer_key"].get("citations", [])
        mapped: list[dict] = []
        for ref in refs:
            source = next((c for c in citation_pool if c["_gid"] == ref.get("id")), None)
            if source is None:
                return False
            mapped.append(
                {
                    "id": source["_gid"],
                    "source_type": source.get("source_type", "note"),
                    "source_id": source.get("source_id"),
                    "page": source.get("page"),
                    "slide": source.get("slide"),
                    "chunk_id": source.get("chunk_id"),
                    "quote": source.get("quote", ""),
                }
            )
        question["answer_key"]["citations"] = mapped
        return bool(mapped)

    mapped = []
    for ref in question.get("citations", []):
        source = next((c for c in citation_pool if c["_gid"] == ref.get("id")), None)
        if source is None:
            return False
        mapped.append(
            {
                "id": source["_gid"],
                "source_type": source.get("source_type", "note"),
                "source_id": source.get("source_id"),
                "page": source.get("page"),
                "slide": source.get("slide"),
                "chunk_id": source.get("chunk_id"),
                "quote": source.get("quote", ""),
            }
        )
    question["citations"] = mapped
    return bool(mapped)


async def _generate_batch(
    category: str,
    count: int,
    citation_pool: list[dict],
    note_sections: str,
    distribution_plan: str,
    course_id: int,
) -> list[dict] | None:
    allowed_text = json.dumps(
        [
            {"id": c["_gid"], "page": c.get("page"), "slide": c.get("slide")}
            for c in citation_pool
        ],
        ensure_ascii=False,
    )[:CITATIONS_CONTEXT_CHARS]

    prompt = OVERALL_BATCH_PROMPT.format(
        category=category,
        count=count,
        distribution_plan=distribution_plan,
        note_sections=note_sections[:6000],
        citations_json=allowed_text,
        dil_talimati=dil_talimati(settings.not_dili),
    )

    last_data: dict | None = None
    for _ in range(MAX_BATCH_ATTEMPTS):
        try:
            data = await llm_service.chat_json(
                [{"role": "user", "content": prompt}],
                kind=f"overall_{category}",
                course_id=course_id,
                max_tokens=4096,  # 5 açık uçlu + answer_key'ler uzun çıktıdır (Yetenek 04 hata modları)
            )
        except llm_service.LLMError:
            # API/JSON hatası: batch sessizce atlanır — kullanıcıya hata gösterilmez
            return None
        last_data = data
        questions = data.get("questions", [])
        if not isinstance(questions, list) or len(questions) != count:
            continue
        if not all(_validate_overall_question(q, category) for q in questions):
            continue
        if not all(_map_citations(q, citation_pool) for q in questions):
            continue
        if category == "mcq":
            questions = _rebalance_mcq(questions)
        return questions

    # YUMUŞAK GEÇİŞ — asla başarısız olma: şema-geçerli sorular kabul edilir,
    # atıflar havuzun ilk kaynağıyla onarılır; eksik sayıyla da teslim edilir.
    questions = (last_data or {}).get("questions", [])
    if not isinstance(questions, list):
        return None
    questions = [q for q in questions if _validate_overall_question(q, category)]
    if len(questions) < 2:
        return None
    first_citation = next((c for c in citation_pool if c.get("_gid") is not None), None)
    for q in questions:
        if not _map_citations(q, citation_pool) and first_citation is not None:
            if category == "open":
                q["answer_key"]["citations"] = [
                    {
                        "id": first_citation["_gid"],
                        "source_type": first_citation.get("source_type", "note"),
                        "source_id": first_citation.get("source_id"),
                        "page": first_citation.get("page"),
                        "slide": first_citation.get("slide"),
                        "chunk_id": first_citation.get("chunk_id"),
                        "quote": first_citation.get("quote", ""),
                    }
                ]
            else:
                q["citations"] = [
                    {
                        "id": first_citation["_gid"],
                        "source_type": first_citation.get("source_type", "note"),
                        "source_id": first_citation.get("source_id"),
                        "page": first_citation.get("page"),
                        "slide": first_citation.get("slide"),
                        "chunk_id": first_citation.get("chunk_id"),
                        "quote": first_citation.get("quote", ""),
                    }
                ]
    if category == "mcq":
        questions = _rebalance_mcq(questions)
    return questions


def _strip_answer_keys(questions: list[dict]) -> tuple[list[dict], dict]:
    """Açık uçlu cevap anahtarlarını ayırır; frontend'e yalnızca ref gider (Yetenek 04 §6)."""
    answer_keys: dict = {}
    for i, question in enumerate(questions):
        if question["type"] == "open":
            ref = f"oq_{i}"
            answer_keys[ref] = question["answer_key"]
            question["answer_key_ref"] = ref
            del question["answer_key"]
    return questions, answer_keys


async def generate_overall_quiz_stream(course_id: int):
    """Genel quiz üretim hattı — SSE olayları yield eder (Faz 5.1)."""
    try:
        async for event in _generate(course_id):
            yield event
    except OverallGenerationError as exc:
        yield {"type": "error", "message": str(exc)}
    except llm_service.LLMError as exc:
        yield {"type": "error", "message": str(exc)}
    except Exception:
        logger.exception("genel quiz üretimi başarısız: course=%s", course_id)
        yield {
            "type": "error",
            "message": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
        }


async def _generate(course_id: int):
    notes = await _load_course_notes(course_id)
    if not notes:
        raise OverallGenerationError(
            "Henüz hiç chapter notu yok. Önce chapter'lar için not oluşturun."
        )

    yield {"type": "status", "percent": 3, "message": "Konu havuzu hazırlanıyor…"}
    citation_pool, note_sections, distribution_plan = _build_context(notes)

    questions: list[dict] = []
    warnings: list[str] = []
    total_batches = len(BATCH_PLAN)
    for batch_index, (category, count) in enumerate(BATCH_PLAN):
        percent = 5 + int(85 * batch_index / total_batches)
        labels = {
            "mcq": "Çoktan seçmeli",
            "tf": "Doğru-yanlış",
            "fib": "Boşluk doldurma",
            "open": "Açık uçlu",
        }
        label = labels[category]
        yield {
            "type": "status",
            "percent": percent,
            "message": f"{label} sorular üretiliyor ({count} adet)…",
        }
        batch = await _generate_batch(
            category, count, citation_pool, note_sections, distribution_plan, course_id
        )
        if batch is None:
            # Asla başarısız olma: sorunlu batch uyarıyla atlanır, quiz yine teslim edilir.
            warnings.append(f"{label} batch'i üretilemedi (atlandı).")
            continue
        questions.extend(batch)

    # TF doğru/yanlış dengesi: 7-8 doğru (Yetenek 04 §3) — saparsa bir kez yeniden üret
    tf_questions = [q for q in questions if q["type"] == "tf"]
    true_count = sum(1 for q in tf_questions if q["answer"])
    if not (MIN_TF_TRUE <= true_count <= MAX_TF_TRUE) and tf_questions:
        yield {
            "type": "status",
            "percent": 92,
            "message": "Doğru-yanlış dengesi yeniden üretiliyor…",
        }
        non_tf = [q for q in questions if q["type"] != "tf"]
        tf_batch = await _generate_batch(
            "tf", 15, citation_pool, note_sections, distribution_plan, course_id
        )
        if tf_batch is not None:
            questions = non_tf + tf_batch
        else:
            warnings.append("Doğru-yanlış batch'i yeniden üretilemedi (mevcut haliyle kabul edildi).")

    # dağılım: hedef 15/15/15/5 — sapma olursa yine de teslim edilir (best-effort)
    counts = {
        category: sum(1 for q in questions if q["type"] == category)
        for category in EXPECTED_COUNTS
    }
    if counts != EXPECTED_COUNTS:
        warnings.append(f"Dağılım sapması: {counts} (hedef {EXPECTED_COUNTS}) — quiz eldeki sorularla sunuldu.")


    yield {"type": "status", "percent": 96, "message": "Sorular karıştırılıyor ve kaydediliyor…"}
    seed = random.SystemRandom().randint(1, 10**9)
    rng = random.Random(seed)  # nosec B311 — yalnızca seed'li karıştırma determinizmi (kripto değil)
    rng.shuffle(questions)

    questions, answer_keys = _strip_answer_keys(questions)
    questions_json = {"seed": seed, "questions": questions, "answer_keys": answer_keys}

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO overall_quizzes (course_id, questions_json) VALUES (?, ?)",
            (course_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("genel quiz kimliği alınamadı")
    finally:
        await db.close()

    yield {
        "type": "done",
        "quiz": {
            "id": row_id,
            "course_id": course_id,
            "seed": seed,
            "questions": questions,  # answer_key'siz (frontend)
        },
        "warnings": warnings,
    }
