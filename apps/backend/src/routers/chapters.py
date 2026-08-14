"""Chapter CRUD (minimal) — Faz 1.3 temeli; guide slides/çıkarım Faz 2.1'de."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db

router = APIRouter(prefix="/api", tags=["chapters"])

_COLUMNS = "id, course_id, title, created_at"


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChapterOut(ChapterIn):
    id: int
    course_id: int
    created_at: str


async def _fetch(db, chapter_id: int) -> dict | None:
    cursor = await db.execute(f"SELECT {_COLUMNS} FROM chapters WHERE id = ?", (chapter_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def _course_exists(db, course_id: int) -> bool:
    cursor = await db.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,))
    return await cursor.fetchone() is not None


@router.get("/courses/{course_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(course_id: int) -> list[ChapterOut]:
    """Bir derse ait chapter'lar (oluşturma sırasıyla)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM chapters WHERE course_id = ? "
            "ORDER BY created_at ASC, id ASC",
            (course_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [ChapterOut(**dict(r)) for r in rows]


@router.post("/courses/{course_id}/chapters", response_model=ChapterOut, status_code=201)
async def create_chapter(course_id: int, item: ChapterIn) -> ChapterOut:
    """Yeni chapter oluşturur."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        cursor = await db.execute(
            "INSERT INTO chapters (course_id, title) VALUES (?, ?)",
            (course_id, item.title),
        )
        await db.commit()
        row_id = cursor.lastrowid
        assert row_id is not None
        row = await _fetch(db, row_id)
    finally:
        await db.close()
    assert row is not None
    return ChapterOut(**row)


@router.delete("/chapters/{chapter_id}", status_code=204)
async def delete_chapter(chapter_id: int) -> None:
    """Chapter'ı siler."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
        await db.commit()
    finally:
        await db.close()
