"""Takvim etkinlikleri — kullanıcı eklediği sınav/ödev notları (sıkıntı #4).

Takvim sayfasındaki aylık görünümde:
- Sınavlar `exams` tablosundan otomatik gelir (salt okunur, ayrı `source` ile).
- Kullanıcı güne ödev/kişisel not ekleyebilir (calendar_events; kind: 'assignment'|'custom').
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["calendar-events"])


class CalendarEventOut(BaseModel):
    id: int
    course_id: int | None
    event_date: str
    kind: str
    title: str
    source: str  # 'exam' (exams tablosu) | 'user' (calendar_events)
    tags: list[str] = []


class CalendarEventCreateIn(BaseModel):
    event_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Sıkıntı: "sınav veya proje ekleme gibi bir seçenek yok" — 'exam' | 'project'
    # kullanıcı etkinliği olarak da eklenebilir (source hâlâ 'user').
    kind: str = Field(default="custom", pattern=r"^(assignment|custom|exam|project)$")
    title: str = Field(min_length=1, max_length=200)
    course_id: int | None = None
    # Kullanıcı tanımlı etiketler — serbest metin, en fazla 6 etiket × 24 karakter.
    tags: list[str] = Field(default_factory=list, max_length=6)


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


def _parse_tags(raw: str | None) -> list[str]:
    """tags sütunu JSON listesi; bozuk/None değer güvenle boş listeye iner."""
    if not raw:
        return []
    try:
        import json

        parsed = json.loads(raw)
        return [str(t)[:24] for t in parsed][:6] if isinstance(parsed, list) else []
    except Exception:
        return []


@router.get("/calendar-events", response_model=list[CalendarEventOut])
async def list_calendar_events(
    start: str, end: str, tenant_id: str = Depends(get_tenant_id)
) -> list[CalendarEventOut]:
    """[start, end] aralığındaki etkinlikler: exams (otomatik) + calendar_events (kullanıcı)."""
    db = await get_db()
    try:
        out: list[CalendarEventOut] = []

        cursor = await db.execute(
            "SELECT e.id, e.course_id, e.exam_date, e.title, c.name AS course_name "
            "FROM exams e LEFT JOIN courses c ON c.id = e.course_id "
            "WHERE e.tenant_id = ? AND e.exam_date >= ? AND e.exam_date <= ? "
            "ORDER BY e.exam_date ASC",
            (tenant_id, start, end),
        )
        for row in await cursor.fetchall():
            title = row["title"]
            if row["course_name"]:
                title = f"{row['course_name']} · {title}"
            out.append(
                CalendarEventOut(
                    id=row["id"],
                    course_id=row["course_id"],
                    event_date=row["exam_date"],
                    kind="exam",
                    title=title,
                    source="exam",
                )
            )

        cursor = await db.execute(
            "SELECT id, course_id, event_date, kind, title, tags FROM calendar_events "
            "WHERE tenant_id = ? AND event_date >= ? AND event_date <= ? "
            "ORDER BY event_date ASC, id ASC",
            (tenant_id, start, end),
        )
        for row in await cursor.fetchall():
            out.append(
                CalendarEventOut(
                    id=row["id"],
                    course_id=row["course_id"],
                    event_date=row["event_date"],
                    kind=row["kind"],
                    title=row["title"],
                    source="user",
                    tags=_parse_tags(row["tags"]),
                )
            )
    finally:
        await db.close()
    return out


@router.post("/calendar-events", response_model=CalendarEventOut, status_code=201)
async def create_calendar_event(
    item: CalendarEventCreateIn, tenant_id: str = Depends(get_tenant_id)
) -> CalendarEventOut:
    db = await get_db()
    try:
        if item.course_id is not None and not await _course_exists(db, item.course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        import json

        clean_tags = [t.strip()[:24] for t in item.tags if t.strip()][:6]
        cursor = await db.execute(
            "INSERT INTO calendar_events (tenant_id, course_id, event_date, kind, title, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                item.course_id,
                item.event_date,
                item.kind,
                item.title,
                json.dumps(clean_tags, ensure_ascii=False) if clean_tags else None,
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("etkinlik kimliği alınamadı")
        cursor = await db.execute(
            "SELECT id, course_id, event_date, kind, title, tags FROM calendar_events WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise RuntimeError("beklenen etkinlik satırı bulunamadı")
    return CalendarEventOut(
        id=row["id"],
        course_id=row["course_id"],
        event_date=row["event_date"],
        kind=row["kind"],
        title=row["title"],
        source="user",
        tags=_parse_tags(row["tags"]),
    )


@router.delete("/calendar-events/{event_id}", status_code=204)
async def delete_calendar_event(
    event_id: int, tenant_id: str = Depends(get_tenant_id)
) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM calendar_events WHERE id = ? AND tenant_id = ?", (event_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Etkinlik bulunamadı")
        await db.commit()
    finally:
        await db.close()
