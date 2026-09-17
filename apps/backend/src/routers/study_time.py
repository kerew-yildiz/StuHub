"""Chapter çalışma süresi uçları — heartbeat kaydı + ders/chapter toplamları.

`POST /courses/{id}/chapters/{chapter_id}/study-time`: chapter görünümü görünür ve
etkileşimliyken frontend'in gönderdiği periyodik süre dilimi (heartbeat). `session_id`
bazında idempotenttir — ağ hatasında tekrar gönderim süreyi çift saymaz.

`GET /courses/{id}/study-time`: ders + chapter toplam çalışma süresi (saniye). Kart
özetleri (`card_summary`) aynı toplamları `study_time.study_totals` üzerinden okur.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db
from ..services.study_time import MAX_HEARTBEAT_SEC, record_study_heartbeat, study_totals

router = APIRouter(prefix="/api", tags=["study-time"])


class StudyHeartbeatIn(BaseModel):
    """Tek aralığın kimliği + o aralıkta geçen saniye (tipik: 45)."""

    session_id: str = Field(min_length=1, max_length=64)
    duration_sec: int = Field(gt=0, le=MAX_HEARTBEAT_SEC)


class StudyHeartbeatOut(BaseModel):
    id: int
    course_id: int
    chapter_id: int
    session_id: str
    duration_sec: int


class ChapterStudyOut(BaseModel):
    chapter_id: int
    total_study_sec: int


class CourseStudyOut(BaseModel):
    course_id: int
    total_study_sec: int
    chapters: list[ChapterStudyOut]


async def _chapter_of_course(db, course_id: int, chapter_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM chapters WHERE id = ? AND course_id = ? AND tenant_id = ?",
        (chapter_id, course_id, tenant_id),
    )
    return await cursor.fetchone() is not None


@router.post(
    "/courses/{course_id}/chapters/{chapter_id}/study-time",
    response_model=StudyHeartbeatOut,
    status_code=201,
)
async def create_chapter_study_time(
    course_id: int,
    chapter_id: int,
    item: StudyHeartbeatIn,
    tenant_id: str = Depends(get_tenant_id),
) -> StudyHeartbeatOut:
    """Chapter'da geçen bir aralığı kaydeder (idempotent: `session_id` tekrarında mevcut satır)."""
    db = await get_db()
    try:
        if not await _chapter_of_course(db, course_id, chapter_id, tenant_id):
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
        row = await record_study_heartbeat(
            db, tenant_id, course_id, chapter_id, item.session_id, item.duration_sec
        )
    finally:
        await db.close()
    return StudyHeartbeatOut(
        id=row["id"],
        course_id=row["course_id"],
        chapter_id=row["chapter_id"],
        session_id=row["session_id"],
        duration_sec=row["duration_sec"],
    )


@router.get("/courses/{course_id}/study-time", response_model=CourseStudyOut)
async def get_course_study_time(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> CourseStudyOut:
    """Dersin toplam çalışma süresi + chapter bazında dökümü (saniye)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        total, chapters = await study_totals(db, tenant_id, course_id)
    finally:
        await db.close()
    return CourseStudyOut(
        course_id=course_id,
        total_study_sec=total,
        chapters=[
            ChapterStudyOut(chapter_id=cid, total_study_sec=sec)
            for cid, sec in sorted(chapters.items())
        ],
    )
