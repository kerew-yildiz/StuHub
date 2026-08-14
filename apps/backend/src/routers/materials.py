"""Materyal (PDF/PPTX) yükleme ve yönetimi — Faz 1.2 (metin çıkarımı Faz 2.1)."""

from __future__ import annotations

import uuid
from contextlib import suppress
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api", tags=["materials"])

_COLUMNS = "id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at"

ALLOWED_TYPES = {"textbook", "slides"}
# textbook: PDF; slides: PDF ya da PPTX (Faz 2.1'de çıkarılır)
ALLOWED_EXTENSIONS = {"textbook": {".pdf"}, "slides": {".pdf", ".pptx", ".ppt"}}


class MaterialOut(BaseModel):
    id: int
    course_id: int
    type: str
    filepath: str
    extracted_text: str | None = None
    page_count: int | None = None
    vector_ns: str | None = None
    created_at: str


def _safe_filename(original: str) -> str:
    name = Path(original).name
    # Windows/Unix ayraçlarını ve tehlikeli karakterleri temizle
    for ch in ('/', '\\', '..', ':', '*', '?', '"', '<', '>', '|'):
        name = name.replace(ch, '_')
    return name or "dosya"


async def _course_exists(db, course_id: int) -> bool:
    cursor = await db.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,))
    return await cursor.fetchone() is not None


@router.post("/courses/{course_id}/materials", response_model=MaterialOut, status_code=201)
async def upload_material(
    course_id: int,
    file: UploadFile = File(...),
    type: str = Form(...),
) -> MaterialOut:
    """Ders materyali yükler (textbook PDF ya da slides PDF/PPTX).

    Dosya `data/materials/{course_id}/` altında UUID önekli adla saklanır.
    Metin çıkarımı ve indeksleme Faz 2.1/2.2'de (indexing_jobs) yapılır.
    """
    if type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="Geçersiz materyal türü")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS[type]:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS[type]))
        raise HTTPException(
            status_code=422,
            detail=f"{type} türü için desteklenen uzantılar: {allowed}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Boş dosya yüklenemez")

    db = await get_db()
    try:
        if not await _course_exists(db, course_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        course_dir = settings.materials_dir / str(course_id)
        course_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{_safe_filename(file.filename or 'dosya')}"
        dest = course_dir / stored_name
        dest.write_bytes(content)

        cursor = await db.execute(
            "INSERT INTO materials (course_id, type, filepath) VALUES (?, ?, ?)",
            (course_id, type, str(dest)),
        )
        await db.commit()
        row_id = cursor.lastrowid
        assert row_id is not None
        cursor2 = await db.execute(
            f"SELECT {_COLUMNS} FROM materials WHERE id = ?", (row_id,)
        )
        row = await cursor2.fetchone()
    finally:
        await db.close()
    assert row is not None
    return MaterialOut(**dict(row))


@router.get("/courses/{course_id}/materials", response_model=list[MaterialOut])
async def list_materials(course_id: int) -> list[MaterialOut]:
    """Bir derse ait materyaller."""
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM materials WHERE course_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (course_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [MaterialOut(**dict(r)) for r in rows]


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material(material_id: int) -> None:
    """Materyali siler (dosyayı da kaldırır)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT filepath FROM materials WHERE id = ?", (material_id,))
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Materyal bulunamadı")
        await db.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        await db.commit()
    finally:
        await db.close()
    with suppress(OSError):
        Path(row["filepath"]).unlink(missing_ok=True)
