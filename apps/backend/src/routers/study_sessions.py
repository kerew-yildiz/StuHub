"""Çalışma oturumu (pomodoro) zamanlayıcı kayıtları (Plan #14).

Zamanlayıcının kendisi (25dk çalışma / 5dk mola döngüsü) frontend'de çalışır; bu uç
yalnızca tamamlanmış bir oturumu kalıcı hale getirir. Oturum bitince gösterilen mini
test mevcut soru havuzundan servis edilir (`GET /courses/{id}/feed`, feed_service) —
burada yeni soru üretimi YOK.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["study-sessions"])

MAX_DURATION_SEC = 24 * 3600


class StudySessionIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    duration_sec: int = Field(gt=0, le=MAX_DURATION_SEC)
    # Ders context'i dışındaki kullanım süresi de kaydedilir (sıkıntı #2):
    # course_id yoksa NULL — haftalık toplam tüm oturumları kapsar.
    course_id: int | None = None


class StudySessionOut(BaseModel):
    id: int
    # Global (ders dışı) oturumlarda NULL — migration 0013 sonrası.
    course_id: int | None
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
    "/study-sessions",
    response_model=StudySessionOut,
    status_code=201,
)
async def create_global_study_session(
    item: StudySessionIn, tenant_id: str = Depends(get_tenant_id)
) -> StudySessionOut:
    """Ders bağlamı OLMAYAN kullanım oturumunu kaydeder (course_id = NULL).

    `session_id` bazında idempotent — create_study_session ile aynı semantik.
    """
    db = await get_db()
    try:
        cursor = await db.execute(_SELECT_BY_SESSION, (tenant_id, item.session_id))
        existing = await cursor.fetchone()
        if existing is not None:
            return StudySessionOut(**dict(existing))

        cursor = await db.execute(
            "INSERT INTO study_sessions (tenant_id, course_id, session_id, duration_sec) "
            "VALUES (?, NULL, ?, ?)",
            (tenant_id, item.session_id, item.duration_sec),
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


class WeeklyStudyDay(BaseModel):
    date: str
    duration_sec: int


class WeeklyStudyOut(BaseModel):
    days: list[WeeklyStudyDay]


@router.get("/study-sessions/weekly", response_model=WeeklyStudyOut)
async def get_weekly_study(tenant_id: str = Depends(get_tenant_id)) -> WeeklyStudyOut:
    """Son 7 takvim günündeki tamamlanmış çalışma oturumlarını toplar.

    Postgres uyumluluğu: asyncpg sürüm parametresi native `datetime` ister
    (ISO string DataError verir); SQLite yolu ISO string alır. PgConnection
    `?` yer tutucularını `$n`'e çevirdiği için tek sorgu iki sürücüde de çalışır.
    """
    today = datetime.now(UTC).date()
    start = today - timedelta(days=6)
    start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)
    db = await get_db()
    try:
        is_pg = hasattr(db, "_raw")  # PgConnection sarmalayıcısı (asyncpg)
        cursor = await db.execute(
            "SELECT created_at, duration_sec FROM study_sessions "
            "WHERE tenant_id = ? AND created_at >= ? ORDER BY created_at ASC",
            (tenant_id, start_dt if is_pg else start.isoformat()),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    totals = {start + timedelta(days=i): 0 for i in range(7)}
    for row in rows:
        raw = row["created_at"]
        # asyncpg datetime döner; SQLite str/timestamp karışımı verebilir.
        if isinstance(raw, datetime):
            event_date = raw.date() if raw.tzinfo else raw.replace(tzinfo=UTC).date()
        else:
            text = str(raw)
            try:
                event_date = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            except ValueError:
                event_date = datetime.strptime(text[:10], "%Y-%m-%d").date()
        if event_date in totals:
            totals[event_date] += int(row["duration_sec"] or 0)

    return WeeklyStudyOut(
        days=[WeeklyStudyDay(date=day.isoformat(), duration_sec=totals[day]) for day in totals]
    )
