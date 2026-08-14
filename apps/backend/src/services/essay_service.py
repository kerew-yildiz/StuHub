"""Genel ödev (essay) değerlendirme servisi (Yetenek 14).

Yetenek 05'in makinesini geneller: rubrik (verilmezse 5 varsayılan ölçüt),
0–100 skor, ölçüt bazlı kırılım, güçlü/zayıf yönler, alıntılı yorumlar,
güven eşiği altında tek yeniden değerlendirme. Boş metin deterministik 0.
"""

from __future__ import annotations

import json
import logging

from ..db import get_db
from ..prompts.essay_prompts import (
    DEFAULT_CRITERIA_TEXT,
    EMPTY_SUBMISSION_MESSAGE,
    HOMEWORK_GRADE_PROMPT,
)
from . import llm_service

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.6
MAX_USER_TEXT = 8000
MAX_INSTRUCTIONS = 2000


class EssayServiceError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _validate(grade: dict) -> list[str]:
    """Şema doğrulaması — ihlal listesi döner (boş = geçerli)."""
    errors: list[str] = []
    score = grade.get("score")
    if not isinstance(score, (int, float)) or not (0 <= score <= 100):
        errors.append("score 0-100 aralığında sayı olmalı")
    criteria = grade.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria boş")
    else:
        for criterion in criteria:
            if not isinstance(criterion, dict):
                errors.append("ölçüt geçersiz")
                continue
            if not str(criterion.get("name", "")).strip():
                errors.append("ölçüt adı boş")
            for field in ("score", "max"):
                value = criterion.get(field)
                if not isinstance(value, (int, float)) or value < 0:
                    errors.append(f"ölçüt {field} geçersiz")
            if not str(criterion.get("comment", "")).strip():
                errors.append("ölçüt yorumu boş")
    for field in ("strengths", "weaknesses"):
        value = grade.get(field)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"{field} liste olmalı")
    quotes = grade.get("quotes")
    if not isinstance(quotes, list):
        errors.append("quotes liste olmalı")
    confidence = grade.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
        errors.append("confidence 0-1 aralığında olmalı")
    return errors


def _empty_grade() -> dict:
    return {
        "score": 0,
        "criteria": [],
        "strengths": [],
        "weaknesses": [EMPTY_SUBMISSION_MESSAGE],
        "quotes": [],
        "confidence": 1.0,
    }


async def grade_homework(
    *,
    instructions: str,
    user_text: str,
    rubric: str | None,
    course_id: int | None = None,
    chapter_id: int | None = None,
) -> dict:
    """Ödevi 0–100 değerlendirir, `essay_submissions`'a kaydeder ve sonucu döner."""
    if not user_text.strip():
        grade = _empty_grade()
        await _save_submission(instructions, user_text, grade, course_id, chapter_id)
        return grade

    criteria_text = rubric.strip() if rubric and rubric.strip() else DEFAULT_CRITERIA_TEXT
    prompt = HOMEWORK_GRADE_PROMPT.format(
        instructions=instructions[:MAX_INSTRUCTIONS],
        criteria_text=criteria_text[:2000],
        user_text=user_text[:MAX_USER_TEXT],
    )

    for attempt in range(2):
        data = await llm_service.chat_json(
            [{"role": "user", "content": prompt}],
            kind="essay_grade",
            course_id=course_id,
            chapter_id=chapter_id,
        )
        errors = _validate(data)
        if errors:
            logger.warning("essay doğrulama hatası (deneme %s): %s", attempt + 1, errors)
            if attempt == 1:
                raise EssayServiceError(
                    "Değerlendirme çıktısı geçersiz. Lütfen tekrar deneyin."
                )
            continue
        confidence = float(data.get("confidence", 0.0))
        if confidence >= CONFIDENCE_THRESHOLD or attempt == 1:
            await _save_submission(instructions, user_text, data, course_id, chapter_id)
            return data
        # düşük güven → tek yeniden değerlendirme (Yetenek 05 §4)

    raise EssayServiceError("Değerlendirme başarısız oldu. Lütfen tekrar deneyin.")


async def _save_submission(
    instructions: str,
    user_text: str,
    grade: dict,
    course_id: int | None,
    chapter_id: int | None,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO essay_submissions (course_id, chapter_id, prompt, user_text, grade_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                course_id,
                chapter_id,
                instructions,
                user_text[:MAX_USER_TEXT],
                json.dumps(grade, ensure_ascii=False),
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def list_submissions(course_id: int) -> list[dict]:
    """Dersin ödev geçmişi (yeni→eski) — metinler kısaltılmadan saklanır, listede özetlenir."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, chapter_id, prompt, grade_json, created_at "
            "FROM essay_submissions WHERE course_id = ? ORDER BY id DESC LIMIT 50",
            (course_id,),
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()
    return [
        {
            "id": row["id"],
            "course_id": row["course_id"],
            "chapter_id": row["chapter_id"],
            "prompt": row["prompt"][:200],
            "score": (json.loads(row["grade_json"] or "{}") or {}).get("score"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
