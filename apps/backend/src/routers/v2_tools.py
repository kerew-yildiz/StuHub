"""Rehber + ödev değerlendirme + streak router'ları (Faz V2.4/2.5/2.7)."""

from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..db import get_db
from ..services.essay_service import EssayServiceError, grade_homework, list_submissions
from ..services.guide_service import (
    GuideError,
    generate_chapter_guide,
    generate_course_guide,
    get_latest_guide,
)
from ..services.streak_service import (
    compute_streak,
    load_active_dates,
    load_today_counts,
    progress_percent,
)

router = APIRouter(prefix="/api", tags=["guides", "essays", "streaks"])


class GuideKindOut(BaseModel):
    id: int
    course_id: int
    chapter_id: int | None
    kind: str
    content_json: dict
    created_at: str
    model_used: str | None


class EssayGradeIn(BaseModel):
    instructions: str = Field(min_length=1)
    rubric: str | None = None
    user_text: str


# ── Çalışma rehberi ─────────────────────────────────────────────────────


@router.post("/chapters/{chapter_id}/guide")
async def create_chapter_guide(chapter_id: int, kind: str = "summary") -> dict:
    """Chapter özeti ya da kavram haritası üretir ve kaydeder."""
    try:
        return await generate_chapter_guide(chapter_id, kind)
    except GuideError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/courses/{course_id}/guide")
async def create_course_guide(course_id: int, kind: str = "summary") -> dict:
    """Ders seviyesi rehber üretir ve kaydeder."""
    try:
        return await generate_course_guide(course_id, kind)
    except GuideError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/chapters/{chapter_id}/guides")
async def latest_chapter_guide(chapter_id: int, kind: str = "summary") -> dict | None:
    return await get_latest_guide(course_id=None, chapter_id=chapter_id, kind=kind)


@router.get("/courses/{course_id}/guides")
async def latest_course_guide(course_id: int, kind: str = "summary") -> dict | None:
    return await get_latest_guide(course_id=course_id, chapter_id=None, kind=kind)


# ── Ödev değerlendirme ──────────────────────────────────────────────────


@router.post("/courses/{course_id}/essays/grade")
async def grade_essay_homework(course_id: int, payload: EssayGradeIn) -> dict:
    """Ödevi 0-100 değerlendirir, geçmişe kaydeder ve sonucu döner."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM courses WHERE id = ?", (course_id,))
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
    finally:
        await db.close()
    try:
        return await grade_homework(
            instructions=payload.instructions,
            user_text=payload.user_text,
            rubric=payload.rubric,
            course_id=course_id,
        )
    except EssayServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses/{course_id}/essays")
async def list_essay_submissions(course_id: int) -> list[dict]:
    return await list_submissions(course_id)


# ── Streak / günlük hedef ───────────────────────────────────────────────


@router.get("/streaks")
async def streak_summary() -> dict:
    """Dashboard özeti: streak günü, bugünkü etkinlikler, hedef ve yüzde.

    `daily_goal` önce settings tablosundan (Ayarlar sayfası), yoksa env'den okunur.
    """
    counts = await load_today_counts()
    goal = settings.daily_goal
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'daily_goal'")
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is not None:
        with suppress(ValueError):
            goal = max(int(row["value"]), 1)
    return {
        "streak_days": compute_streak(await load_active_dates()),
        "today_counts": counts,
        "daily_goal": goal,
        "progress_percent": progress_percent(counts, goal),
    }
