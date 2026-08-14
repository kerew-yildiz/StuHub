"""Chapter guide slides — yükleme + çıkarım + listeleme (Faz 2.1)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import settings
from ..db import get_db
from ..services import pdf_service, slides_service

router = APIRouter(prefix="/api", tags=["slides"])

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


class SlideOut(BaseModel):
    id: int
    chapter_id: int
    material_id: int | None
    slide_no: int
    content_text: str | None


@router.post("/chapters/{chapter_id}/slides", response_model=list[SlideOut], status_code=201)
async def upload_guide_slides(
    chapter_id: int,
    file: UploadFile = File(...),
) -> list[SlideOut]:
    """Chapter için guide slides yükler; slide içeriklerini çıkarıp `slides`'a yazar.

    - Dosya `materials`'a type='slides' olarak kaydedilir (course_id chapter'dan alınır).
    - PDF → pymupdf sayfa bazlı; PPTX → python-pptx slide bazlı çıkarım.
    - LibreOffice varsa PPTX→PDF render kopyası üretilir (pop-up için); yoksa metin
      alıntısı fallback'i kullanılır (yol haritası 2.1 + Yetenek 01).
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Desteklenen uzantılar: PDF, PPTX")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Boş dosya yüklenemez")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id FROM chapters WHERE id = ?", (chapter_id,)
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")
        course_id = chapter["course_id"]

        safe_name = Path(file.filename or "dosya").name.replace("/", "_").replace("\\", "_")
        course_dir = settings.materials_dir / str(course_id)
        course_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        dest = course_dir / stored_name
        dest.write_bytes(content)

        cursor = await db.execute(
            "INSERT INTO materials (course_id, type, filepath) VALUES (?, 'slides', ?)",
            (course_id, str(dest)),
        )
        await db.commit()
        material_id = cursor.lastrowid
        if material_id is None:
            raise RuntimeError("materyal kimliği alınamadı")

        # PPTX → PDF render kopyası (pop-up görüntüleme; LibreOffice yoksa None)
        if ext in (".pptx", ".ppt"):
            render_dir = settings.materials_dir / str(course_id) / "renders"
            slides_service.render_pptx_to_pdf(str(dest), str(render_dir))

        if ext in (".pptx", ".ppt"):
            extracted = slides_service.extract_pptx_slides(str(dest))
        else:
            pages = pdf_service.extract_pdf_pages(str(dest))
            extracted = [{"slide": p["page"], "text": p["text"]} for p in pages]

        out: list[SlideOut] = []
        for slide_data in extracted:
            cursor = await db.execute(
                "INSERT INTO slides (chapter_id, material_id, slide_no, content_text) "
                "VALUES (?, ?, ?, ?)",
                (chapter_id, material_id, slide_data["slide"], slide_data["text"]),
            )
            await db.commit()
            slide_id = cursor.lastrowid
            if slide_id is None:
                raise RuntimeError("slide kimliği alınamadı")
            out.append(
                SlideOut(
                    id=slide_id,
                    chapter_id=chapter_id,
                    material_id=material_id,
                    slide_no=slide_data["slide"],
                    content_text=slide_data["text"],
                )
            )
        return out
    finally:
        await db.close()


@router.get("/chapters/{chapter_id}/slides", response_model=list[SlideOut])
async def list_slides(chapter_id: int) -> list[SlideOut]:
    """Bir chapter'ın guide slide'larını sıralı döner."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, material_id, slide_no, content_text FROM slides "
            "WHERE chapter_id = ? ORDER BY slide_no ASC",
            (chapter_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [SlideOut(**dict(r)) for r in rows]


@router.delete("/slides/{slide_id}", status_code=204)
async def delete_slide(slide_id: int) -> None:
    """Tek slide'ı siler."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM slides WHERE id = ?", (slide_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Slide bulunamadı")
        await db.commit()
    finally:
        await db.close()
