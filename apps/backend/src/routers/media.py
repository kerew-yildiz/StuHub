"""Medya alım router'ı — YouTube URL + metin yapıştırma (Faz V2.6, Yetenek 11).

Dosya tabanlı türler (audio/docx/epub/image) `routers/materials.py` üzerinden
yüklenir ve otomatik işe alınır; bu router URL ve metin girdilerini kapsar.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..config import settings
from ..db import get_db
from ..services.indexer import create_indexing_job
from ..workers.indexer import process_pending_jobs

router = APIRouter(prefix="/api", tags=["media"])

_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class YoutubeIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class TextIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


async def _course_exists(course_id: int, tenant_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
        return await cursor.fetchone() is not None
    finally:
        await db.close()


async def _create_material(
    course_id: int, mtype: str, filepath: str, job_kind: str, tenant_id: str
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO materials (tenant_id, course_id, type, filepath) VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, mtype, filepath),
        )
        await db.commit()
        material_id = cursor.lastrowid
        if material_id is None:
            raise RuntimeError("materyal kimliği alınamadı")
        cursor = await db.execute(
            "SELECT id, course_id, type, filepath, created_at FROM materials "
            "WHERE id = ? AND tenant_id = ?",
            (material_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise RuntimeError("beklenen materyal satırı bulunamadı")
    job_id = await create_indexing_job(course_id, material_id, tenant_id, kind=job_kind)
    await process_pending_jobs()
    return {**dict(row), "job_id": job_id}


@router.post("/courses/{course_id}/media/youtube", status_code=201)
async def ingest_youtube(
    course_id: int, payload: YoutubeIn, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """YouTube URL'sini materyal olarak ekler; indeksleme arka planda başlar.

    Altyazı yoksa çıkarıcı yerel whisper ile sesi çevirir (iş 'failed' olursa
    hata mesajı iş kaydındadır).
    """
    if not _HTTP_URL_RE.match(payload.url.strip()):
        raise HTTPException(status_code=422, detail="Geçerli bir http(s) video adresi girin.")
    if not await _course_exists(course_id, tenant_id):
        raise HTTPException(status_code=404, detail="Ders bulunamadı")
    return await _create_material(
        course_id, "youtube", payload.url.strip(), "index", tenant_id
    )


@router.post("/courses/{course_id}/media/text", status_code=201)
async def ingest_text(
    course_id: int, payload: TextIn, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Yapıştırılan metni materyal olarak kaydeder; indeksleme arka planda başlar."""
    if not await _course_exists(course_id, tenant_id):
        raise HTTPException(status_code=404, detail="Ders bulunamadı")

    safe_name = Path(payload.title).name.replace("\\", "_").replace("/", "_") or "metin"
    course_dir = settings.materials_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    stored = course_dir / f"{uuid.uuid4().hex}_{safe_name}.txt"
    stored.write_text(payload.content, encoding="utf-8")

    return await _create_material(course_id, "text", str(stored), "index", tenant_id)
