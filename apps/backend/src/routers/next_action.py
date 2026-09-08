"""'Bugün ne çalışsam' ekranı (Plan #13) — deterministik öncelik kuralı, LLM YOK.

Sırayla kontrol edilir, İLK eşleşen dallanma döner:
  1. Vadesi geçmiş flashcard var mı (`card_reviews.due_at`) → `cards`
  2. Hata günlüğünde 2+ kez tekrar eden konu var mı (`routers/errors.py` Plan #5,
     `only_repeated=True`) → `error_quiz`
  3. Hiç notu üretilmemiş (okunmamış) bölüm var mı → `read_chapter`
Hiçbiri yoksa → `none`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db
from .errors import list_course_errors

router = APIRouter(prefix="/api", tags=["next-action"])


class NextActionOut(BaseModel):
    action: str  # 'cards' | 'error_quiz' | 'read_chapter' | 'none'
    reason: str
    target_id: int | None = None


def _as_datetime(value: object) -> datetime | None:
    """`due_at`'i (SQLite metin ya da Postgres native `datetime`) UTC farkındalı yapar."""
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


async def _overdue_card_set(db, course_id: int, tenant_id: str) -> int | None:
    """Vadesi geçmiş en az bir kart taşıyan setin id'sini döner (en eskisi önce)."""
    cursor = await db.execute(
        "SELECT fs.id AS set_id, cr.due_at FROM flashcard_sets fs "
        "JOIN card_reviews cr ON cr.set_id = fs.id AND cr.tenant_id = fs.tenant_id "
        "WHERE fs.course_id = ? AND fs.tenant_id = ? AND cr.due_at IS NOT NULL",
        (course_id, tenant_id),
    )
    now = datetime.now(UTC)
    overdue: list[tuple[datetime, int]] = []
    for row in await cursor.fetchall():
        row = dict(row)
        due_at = _as_datetime(row["due_at"])
        if due_at is not None and due_at <= now:
            overdue.append((due_at, row["set_id"]))
    if not overdue:
        return None
    overdue.sort(key=lambda item: item[0])
    return overdue[0][1]


async def _repeated_error_topic(course_id: int, tenant_id: str) -> str | None:
    """Hata günlüğünde 2+ kez tekrar eden ilk (en yeni) konu adını döner."""
    entries = await list_course_errors(
        course_id, topic=None, since=None, only_repeated=True, tenant_id=tenant_id
    )
    return entries[0].topic if entries else None


async def _unread_chapter(db, course_id: int, tenant_id: str) -> int | None:
    """Hiç notu üretilmemiş ilk bölümün id'sini döner (bölüm sırasına göre)."""
    cursor = await db.execute(
        "SELECT c.id FROM chapters c WHERE c.course_id = ? AND c.tenant_id = ? "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM notes n WHERE n.chapter_id = c.id AND n.tenant_id = c.tenant_id"
        ") ORDER BY c.id ASC LIMIT 1",
        (course_id, tenant_id),
    )
    row = await cursor.fetchone()
    return int(dict(row)["id"]) if row else None


@router.get("/courses/{course_id}/next-action", response_model=NextActionOut)
async def get_next_action(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> NextActionOut:
    """Deterministik tek-adım önerisi — LLM çağrısı YOK, sadece SQL okumaları."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        set_id = await _overdue_card_set(db, course_id, tenant_id)
    finally:
        await db.close()

    if set_id is not None:
        return NextActionOut(
            action="cards", reason="Vadesi geçmiş tekrar kartların var.", target_id=set_id
        )

    topic = await _repeated_error_topic(course_id, tenant_id)
    if topic is not None:
        return NextActionOut(
            action="error_quiz",
            reason=f"'{topic}' konusunda tekrarlayan hataların var.",
            target_id=None,
        )

    db = await get_db()
    try:
        chapter_id = await _unread_chapter(db, course_id, tenant_id)
    finally:
        await db.close()

    if chapter_id is not None:
        return NextActionOut(
            action="read_chapter",
            reason="Henüz hiç çalışmadığın bir bölüm var.",
            target_id=chapter_id,
        )

    return NextActionOut(action="none", reason="Şu an için bekleyen bir öncelik yok.")
