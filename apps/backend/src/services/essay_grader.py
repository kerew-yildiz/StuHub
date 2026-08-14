"""Açık uçlu puanlama — rubrik + güven kontrolü (Yetenek 05)."""

from __future__ import annotations

import json
import logging

from ..prompts.overall_prompts import ESSAY_GRADE_PROMPT
from . import llm_service

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.6


class EssayGradeError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _validate(grade: dict) -> bool:
    if not isinstance(grade.get("score"), (int, float)):
        return False
    score = grade["score"]
    if not (0 <= score <= 10):
        return False
    for field in ("correct", "missing", "incorrect", "unnecessary"):
        if not isinstance(grade.get(field), list):
            return False
    for field in ("explanation", "ideal_answer"):
        if not isinstance(grade.get(field), str) or not grade[field].strip():
            return False
    confidence = grade.get("confidence")
    return isinstance(confidence, (int, float)) and 0 <= confidence <= 1


def empty_grade(answer_key: dict) -> dict:
    """Boş cevap — deterministik 0 puan + rehberlik (Yetenek 05 hata modları)."""
    points = answer_key.get("points", [])
    return {
        "score": 0,
        "correct": [],
        "missing": points,
        "incorrect": [],
        "unnecessary": ["yok"],
        "explanation": (
            "Cevap boş bırakıldı. Anahtar noktalar: " + "; ".join(points[:5])
        ),
        "ideal_answer": "",
        "confidence": 1.0,
    }


async def grade_essay(
    *,
    question: str,
    answer_key: dict,
    numbered_sources: str,
    user_answer: str,
    course_id: int,
    chapter_id: int | None = None,
) -> dict:
    """Kullanıcı cevabını 0-10 puanlar; düşük güvende bir kez yeniden değerlendirir.

    İkinci sonuç kesindir (Yetenek 05 §4).
    """
    if not user_answer.strip():
        return empty_grade(answer_key)

    prompt = ESSAY_GRADE_PROMPT.format(
        question=question[:800],
        answer_key=json.dumps(answer_key, ensure_ascii=False)[:1500],
        numbered_sources=numbered_sources[:4000],
        user_answer=user_answer[:3000],
    )

    for attempt in range(2):
        data = await llm_service.chat_json(
            [{"role": "user", "content": prompt}],
            kind="essay_grade",
            course_id=course_id,
            chapter_id=chapter_id,
        )
        if not _validate(data):
            if attempt == 1:
                raise EssayGradeError("Puanlama çıktısı geçersiz. Lütfen tekrar deneyin.")
            continue
        confidence = float(data.get("confidence", 0.0))
        if confidence >= CONFIDENCE_THRESHOLD or attempt == 1:
            return data
        # düşük güven → yeniden değerlendirme

    raise EssayGradeError("Puanlama başarısız oldu. Lütfen tekrar deneyin.")
