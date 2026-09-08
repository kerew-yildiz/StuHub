"""Öğrenme ilerlemesi göstergesi router'ı — haftalık kalıcı hatırlama rozeti (Plan #48).

LLM YOK — `streak_service.topics_mastered_this_week` saf SQL + JSON ayrıştırmasına
dayanır (card_reviews aralık eşiği, bkz. o modülün docstring'i).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db
from ..services.streak_service import topics_mastered_this_week

router = APIRouter(prefix="/api", tags=["streaks"])


class RetentionProgressOut(BaseModel):
    topics_mastered_this_week: int
    topics: list[str]


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.get("/courses/{course_id}/retention-progress", response_model=RetentionProgressOut)
async def course_retention_progress(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> RetentionProgressOut:
    """Bu hafta kalıcı hatırlama eşiğine (`interval_days >= 21`) ulaşan konu sayısı."""
    db = await get_db()
    try:
        exists = await _course_exists(db, course_id, tenant_id)
    finally:
        await db.close()
    if not exists:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")

    topics = await topics_mastered_this_week(course_id, tenant_id)
    return RetentionProgressOut(topics_mastered_this_week=len(topics), topics=topics)
