"""Chapter CRUD (minimal) — guide slides slides.py'de, otomatik not tetiği indexer.py'de."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["chapters"])

# Sabit SQL şablonları — kullanıcı girdisi asla SQL'e gömülmez (parametreli sorgular)
_SELECT_BY_ID = (
    "SELECT id, course_id, title, created_at FROM chapters WHERE id = ? AND tenant_id = ?"
)
_LIST_BY_COURSE = (
    "SELECT id, course_id, title, created_at FROM chapters "
    "WHERE course_id = ? AND tenant_id = ? ORDER BY created_at ASC, id ASC"
)


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChapterOut(ChapterIn):
    id: int
    course_id: int
    created_at: str


async def _fetch(db, chapter_id: int, tenant_id: str) -> dict | None:
    cursor = await db.execute(_SELECT_BY_ID, (chapter_id, tenant_id))
    row = await cursor.fetchone()
    return dict(row) if row else None


def _require(row: dict | None) -> dict:
    if row is None:
        raise RuntimeError("beklenen chapter satırı bulunamadı")
    return row


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.get("/courses/{course_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[ChapterOut]:
    """Bir derse ait chapter'lar (oluşturma sırasıyla)."""
    db = await get_db()
    try:
        cursor = await db.execute(_LIST_BY_COURSE, (course_id, tenant_id))
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [ChapterOut(**dict(r)) for r in rows]


@router.post("/courses/{course_id}/chapters", response_model=ChapterOut, status_code=201)
async def create_chapter(
    course_id: int, item: ChapterIn, tenant_id: str = Depends(get_tenant_id)
) -> ChapterOut:
    """Yeni chapter oluşturur."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        cursor = await db.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES (?, ?, ?)",
            (tenant_id, course_id, item.title),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("chapter kimliği alınamadı")
        row = await _fetch(db, row_id, tenant_id)
    finally:
        await db.close()
    return ChapterOut(**dict(_require(row)))


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
async def get_chapter(chapter_id: int, tenant_id: str = Depends(get_tenant_id)) -> ChapterOut:
    """Tek chapter detayı."""
    db = await get_db()
    try:
        row = await _fetch(db, chapter_id, tenant_id)
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Chapter bulunamadı")
    return ChapterOut(**dict(_require(row)))


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
async def update_chapter(
    chapter_id: int, item: ChapterIn, tenant_id: str = Depends(get_tenant_id)
) -> ChapterOut:
    """Chapter başlığını günceller."""
    db = await get_db()
    try:
        row = await _fetch(db, chapter_id, tenant_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
        await db.execute(
            "UPDATE chapters SET title = ? WHERE id = ? AND tenant_id = ?",
            (item.title, chapter_id, tenant_id),
        )
        await db.commit()
        row = await _fetch(db, chapter_id, tenant_id)
    finally:
        await db.close()
    return ChapterOut(**dict(_require(row)))


@router.delete("/chapters/{chapter_id}", status_code=204)
async def delete_chapter(chapter_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Chapter'ı siler."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM chapters WHERE id = ? AND tenant_id = ?", (chapter_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
        await db.commit()
    finally:
        await db.close()
