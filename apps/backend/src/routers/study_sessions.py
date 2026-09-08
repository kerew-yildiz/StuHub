"""Çalışma oturumu (pomodoro) zamanlayıcı kayıtları (Plan #14).

Zamanlayıcının kendisi (25dk çalışma / 5dk mola döngüsü) frontend'de çalışır; bu uç
yalnızca tamamlanmış bir oturumu kalıcı hale getirir. Oturum bitince gösterilen mini
test mevcut soru havuzundan servis edilir (`GET /courses/{id}/feed`, feed_service) —
burada yeni soru üretimi YOK.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["study-sessions"])

MAX_DURATION_SEC = 24 * 3600


class StudySessionIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    duration_sec: int = Field(gt=0, le=MAX_DURATION_SEC)


class StudySessionOut(BaseModel):
    id: int
    course_id: int
    session_id: str
    duration_sec: int
    created_at: str


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


_SELECT_BY_SESSION = (
    "SELECT id, course_id, session_id, duration_sec, created_at "
    "FROM study_sessions WHERE tenant_id = ? AND session_id = ?"
)
_SELECT_BY_ID = (
    "SELECT id, course_id, session_id, duration_sec, created_at "
    "FROM study_sessions WHERE id = ?"
)


@router.post(
    "/courses/{course_id}/study-sessions",
    response_model=StudySessionOut,
    status_code=201,
)
async def create_study_session(
    course_id: int, item: StudySessionIn, tenant_id: str = Depends(get_tenant_id)
) -> StudySessionOut:
    """Tamamlanmış bir pomodoro oturumunu kaydeder.

    `session_id` bazında idempotent: istemci ağ hatasında yeniden gönderirse (aynı
    `session_id`) mevcut satır olduğu gibi döner, ikinci kayıt açılmaz.
    """
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        cursor = await db.execute(_SELECT_BY_SESSION, (tenant_id, item.session_id))
        existing = await cursor.fetchone()
        if existing is not None:
            return StudySessionOut(**dict(existing))

        cursor = await db.execute(
            "INSERT INTO study_sessions (tenant_id, course_id, session_id, duration_sec) "
            "VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, item.session_id, item.duration_sec),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("oturum kimliği alınamadı")
        cursor = await db.execute(_SELECT_BY_ID, (row_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise RuntimeError("beklenen oturum satırı bulunamadı")
    return StudySessionOut(**dict(row))
