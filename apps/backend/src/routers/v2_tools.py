"""Rehber + ödev değerlendirme + streak router'ları (Faz V2.4/2.5/2.7)."""

from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..config import settings
from ..db import get_db
from ..quota import enforce_quota
from ..services.essay_service import EssayServiceError, grade_homework, list_submissions
from ..services.guide_service import (
    GuideError,
    compare,
    course_glossary,
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

class CompareIn(BaseModel):
    """Karşılaştırma tablosu isteği — kavramlar `study_guides` anahtar terimleridir."""

    concepts: list[str] = Field(min_length=2, max_length=6)


class GlossaryEntryOut(BaseModel):
    """Sözlük kaydı — tanım ve ilk geçiş bilgisi notun markdown metninden gelir."""

    term: str
    definition: str
    chapter_id: int | None
    chapter_title: str | None
    note_id: int | None
    position: int | None
    heading: str | None


async def _chapter_exists(db, chapter_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM chapters WHERE id = ? AND tenant_id = ?", (chapter_id, tenant_id)
    )
    return await cursor.fetchone() is not None


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None



# ── Çalışma rehberi ─────────────────────────────────────────────────────


@router.post("/chapters/{chapter_id}/guide")
async def create_chapter_guide(
    chapter_id: int, kind: str = "summary", tenant_id: str = Depends(enforce_quota)
) -> dict:
    """Chapter özeti ya da kavram haritası üretir ve kaydeder."""
    db = await get_db()
    try:
        if not await _chapter_exists(db, chapter_id, tenant_id):
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
    finally:
        await db.close()
    try:
        return await generate_chapter_guide(chapter_id, kind, tenant_id=tenant_id)
    except GuideError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/courses/{course_id}/guide")
async def create_course_guide(
    course_id: int, kind: str = "summary", tenant_id: str = Depends(enforce_quota)
) -> dict:
    """Ders seviyesi rehber üretir ve kaydeder."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
    finally:
        await db.close()
    try:
        return await generate_course_guide(course_id, kind, tenant_id=tenant_id)
    except GuideError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/chapters/{chapter_id}/guides")
async def latest_chapter_guide(
    chapter_id: int, kind: str = "summary", tenant_id: str = Depends(get_tenant_id)
) -> dict | None:
    return await get_latest_guide(
        course_id=None, chapter_id=chapter_id, kind=kind, tenant_id=tenant_id
    )


@router.get("/courses/{course_id}/guides")
async def latest_course_guide(
    course_id: int, kind: str = "summary", tenant_id: str = Depends(get_tenant_id)
) -> dict | None:
    return await get_latest_guide(
        course_id=course_id, chapter_id=None, kind=kind, tenant_id=tenant_id
    )


# ── Karşılaştırma tablosu + terim sözlüğü (Plan #24 / #29) ──────────────


@router.post("/courses/{course_id}/compare")
async def create_comparison(
    course_id: int, payload: CompareIn, tenant_id: str = Depends(enforce_quota)
) -> dict:
    """Seçilen kavramları ikili karşılaştırır (LLM) ve kind='comparison' kaydeder.

    Kaydedilen tablo `GET /api/courses/{course_id}/guides?kind=comparison` ile okunur.
    """
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
    finally:
        await db.close()
    try:
        return await compare(course_id, payload.concepts, tenant_id=tenant_id)
    except GuideError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses/{course_id}/glossary")
async def course_glossary_entries(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[GlossaryEntryOut]:
    """Ders terim sözlüğü — alfabetik, ilk geçiş bağlantılı (LLM YOK, SQL + regex)."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
    finally:
        await db.close()
    entries = await course_glossary(course_id, tenant_id=tenant_id)
    return [GlossaryEntryOut(**entry) for entry in entries]


# ── Ödev değerlendirme ──────────────────────────────────────────────────


@router.post("/courses/{course_id}/essays/grade")
async def grade_essay_homework(
    course_id: int, payload: EssayGradeIn, tenant_id: str = Depends(enforce_quota)
) -> dict:
    """Ödevi 0-100 değerlendirir, geçmişe kaydeder ve sonucu döner."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
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
            tenant_id=tenant_id,
        )
    except EssayServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses/{course_id}/essays")
async def list_essay_submissions(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[dict]:
    return await list_submissions(course_id, tenant_id=tenant_id)


# ── Streak / günlük hedef ───────────────────────────────────────────────


@router.get("/streaks")
async def streak_summary(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Dashboard özeti: streak günü, bugünkü etkinlikler, hedef ve yüzde.

    `daily_goal` önce settings tablosundan (Ayarlar sayfası), yoksa env'den okunur.
    """
    counts = await load_today_counts(tenant_id=tenant_id)
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
        "streak_days": compute_streak(await load_active_dates(tenant_id=tenant_id)),
        "today_counts": counts,
        "daily_goal": goal,
        "progress_percent": progress_percent(counts, goal),
    }
