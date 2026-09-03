"""Materyal (PDF/PPTX) yükleme ve yönetimi — Faz 1.2 (metin çıkarımı Faz 2.1)."""

from __future__ import annotations

import re
import uuid
from contextlib import suppress
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..config import settings
from ..db import get_db
from ..services import vector_store
from ..services.indexer import MEDIA_TYPES, create_indexing_job
from ..workers.indexer import process_pending_jobs

router = APIRouter(prefix="/api", tags=["materials"])

# Sabit SQL şablonları — kullanıcı girdisi asla SQL'e gömülmez (parametreli sorgular)
_SELECT_BY_ID = (
    "SELECT id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at "
    "FROM materials WHERE id = ? AND tenant_id = ?"
)
_LIST_BY_COURSE = (
    "SELECT id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at "
    "FROM materials WHERE course_id = ? AND tenant_id = ? ORDER BY created_at DESC, id DESC"
)

_UUID_PREFIX_RE = re.compile(r"^[0-9a-f]{32}_")


def _display_name(filepath: str) -> str:
    """Kullanıcının yüklediği özgün dosya adını döndürür (UUID öneki gizlenir)."""
    name = Path(filepath).name
    if _UUID_PREFIX_RE.match(name):
        return name[33:]
    return name

ALLOWED_TYPES = {"textbook", "slides", "audio", "docx", "epub", "image"}
# textbook: PDF; slides: PDF/PPTX; v2 medya türleri kendi uzantı kümeleriyle (Yetenek 11)
ALLOWED_EXTENSIONS = {
    "textbook": {".pdf"},
    "slides": {".pdf", ".pptx", ".ppt"},
    "audio": {".mp3", ".m4a", ".wav", ".ogg", ".webm", ".mp4"},
    "docx": {".docx"},
    "epub": {".epub"},
    "image": {".png", ".jpg", ".jpeg", ".webp", ".bmp"},
}


class MaterialOut(BaseModel):
    id: int
    course_id: int
    type: str
    filepath: str
    display_name: str
    extracted_text: str | None = None
    page_count: int | None = None
    vector_ns: str | None = None
    created_at: str


def _to_out(row: dict) -> MaterialOut:
    return MaterialOut(
        **{k: v for k, v in row.items() if k != "display_name"},
        display_name=_display_name(row["filepath"]),
    )


def _safe_filename(original: str) -> str:
    name = Path(original).name
    # Windows/Unix ayraçlarını ve tehlikeli karakterleri temizle
    for ch in ('/', '\\', '..', ':', '*', '?', '"', '<', '>', '|'):
        name = name.replace(ch, '_')
    return name or "dosya"


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.post("/courses/{course_id}/materials", response_model=MaterialOut, status_code=201)
async def upload_material(
    course_id: int,
    file: UploadFile = File(...),
    type: str = Form(...),
    tenant_id: str = Depends(get_tenant_id),
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

    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        course_dir = settings.materials_dir / str(course_id)
        course_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{_safe_filename(file.filename or 'dosya')}"
        dest = course_dir / stored_name

        # Büyük kitaplar için akışkan yükleme (parça parça diske yaz)
        total = 0
        with dest.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                handle.write(chunk)
                total += len(chunk)
        if total == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail="Dosya boş (0 bayt). Dosyanın bozuk ya da eksik indirilmiş olmadığından "
                "emin olup tekrar yükleyin.",
            )

        cursor = await db.execute(
            "INSERT INTO materials (tenant_id, course_id, type, filepath) VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, type, str(dest)),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("materyal kimliği alınamadı")
        cursor2 = await db.execute(_SELECT_BY_ID, (row_id, tenant_id))
        row = await cursor2.fetchone()
    finally:
        await db.close()
    if row is None:
        raise RuntimeError("beklenen materyal satırı bulunamadı")

    # v2: medya türleri yükleme anında otomatik işe alınır (Yetenek 11)
    # ses → önce transkripsiyon; docx/epub/görsel → doğrudan indeksleme
    if type in MEDIA_TYPES:
        kind = "transcribe" if type == "audio" else "index"
        await create_indexing_job(course_id, row_id, tenant_id, kind=kind)
        await process_pending_jobs()

    return _to_out(dict(row))


@router.get("/materials/{material_id}", response_model=MaterialOut)
async def get_material(material_id: int, tenant_id: str = Depends(get_tenant_id)) -> MaterialOut:
    """Tek materyal (önizleme/title için)."""
    db = await get_db()
    try:
        cursor = await db.execute(_SELECT_BY_ID, (material_id, tenant_id))
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Materyal bulunamadı")
    return _to_out(dict(row))


@router.get("/courses/{course_id}/materials", response_model=list[MaterialOut])
async def list_materials(course_id: int, tenant_id: str = Depends(get_tenant_id)) -> list[MaterialOut]:
    """Bir derse ait materyaller."""
    db = await get_db()
    try:
        cursor = await db.execute(_LIST_BY_COURSE, (course_id, tenant_id))
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [_to_out(dict(r)) for r in rows]


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material(material_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Materyali siler (dosyayı ve vektör chunk'larını da kaldırır)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id, filepath, vector_ns FROM materials WHERE id = ? AND tenant_id = ?",
            (material_id, tenant_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Materyal bulunamadı")
        await db.execute("DELETE FROM materials WHERE id = ? AND tenant_id = ?", (material_id, tenant_id))
        await db.commit()
    finally:
        await db.close()

    if row["vector_ns"]:
        # indekslenmişse LanceDB'den chunk'ları temizle (kabul kriteri: dup yok)
        with suppress(Exception):
            vector_store.delete_material_chunks(row["course_id"], material_id)
    with suppress(OSError):
        Path(row["filepath"]).unlink(missing_ok=True)
