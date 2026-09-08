"""Hata-odaklı kurtarma quizi router'ı (Plan #6).

Bağımlıdır: `routers/errors.py` (Plan #5) — hata günlüğü verisini yeniden hesaplamaz,
`list_course_errors`'ı doğrudan çağırır. Üretim `services/quiz_generator.py`'deki
`generate_from_errors` ile aynı zinciri (bölüm quizi/feed) kullanır: LLM çağrısı VAR,
bu yüzden `enforce_quota` zorunlu.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..quota import enforce_quota
from ..services import quiz_generator
from .errors import list_course_errors

router = APIRouter(prefix="/api", tags=["quiz-review"])

# Konu verilmediğinde hata günlüğünden otomatik seçilecek en sık konu sayısı.
DEFAULT_TOPIC_COUNT = 3
# Negatif listeye alınan en fazla soru metni (prompt şişmesin — feed'teki
# AVOID_LIMIT ile aynı fikir).
AVOID_LIMIT = 40


class ErrorQuizIn(BaseModel):
    """İstek gövdesi — `topics` boşsa hata günlüğündeki en sık konular kullanılır."""

    topics: list[str] | None = None


class ErrorQuizQuestion(BaseModel):
    topic: str
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    feedback_correct: str
    feedback_wrong: str
    citations: list[dict]
    difficulty: str | None = None


class ErrorQuizOut(BaseModel):
    course_id: int
    topics: list[str]
    questions: list[ErrorQuizQuestion]


def _top_error_topics(entries: list, limit: int = DEFAULT_TOPIC_COUNT) -> list[str]:
    """Hata günlüğündeki konuları tekrar sayısına göre (çoktan aza, tekrarsız) sıralar."""
    repeat_count: dict[str, int] = {}
    order: list[str] = []
    for entry in entries:
        if entry.topic not in repeat_count:
            order.append(entry.topic)
        repeat_count[entry.topic] = entry.repeat_count
    order.sort(key=lambda topic: repeat_count[topic], reverse=True)
    return order[:limit]


@router.post("/courses/{course_id}/errors/quiz", response_model=ErrorQuizOut)
async def generate_error_quiz(
    course_id: int, payload: ErrorQuizIn, tenant_id: str = Depends(enforce_quota)
) -> ErrorQuizOut:
    """Hata günlüğündeki konulardan YENİ sorular üretir.

    `payload.topics` boşsa hata günlüğündeki en sık yanlış yapılan `DEFAULT_TOPIC_COUNT`
    konu otomatik seçilir. Üretilen sorular hata günlüğündeki AYNI soruları tekrar
    üretmez: seçilen konulardaki tüm geçmiş yanlış soru metinleri LLM'e negatif liste
    olarak geçirilir (`generate_from_errors` → `_generate_feed_topic`, feed hattıyla
    aynı tekrar-yasağı mekanizması).
    """
    entries = await list_course_errors(
        course_id, topic=None, since=None, only_repeated=False, tenant_id=tenant_id
    )

    wanted_topics = [t.strip() for t in (payload.topics or []) if t.strip()]
    if not wanted_topics:
        wanted_topics = _top_error_topics(entries)
    if not wanted_topics:
        return ErrorQuizOut(course_id=course_id, topics=[], questions=[])

    wanted_set = set(wanted_topics)
    avoid = [entry.question_text for entry in entries if entry.topic in wanted_set][:AVOID_LIMIT]

    questions = await quiz_generator.generate_from_errors(
        course_id, wanted_topics, avoid, tenant_id
    )
    return ErrorQuizOut(
        course_id=course_id,
        topics=wanted_topics,
        questions=[ErrorQuizQuestion(**q) for q in questions],
    )
