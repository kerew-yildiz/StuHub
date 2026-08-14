"""İndeksleme iş yönetimi (Faz 2.2)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..workers.indexer import process_pending_jobs

router = APIRouter(prefix="/api", tags=["indexing"])

# Sabit SQL şablonları — kullanıcı girdisi asla SQL'e gömülmez (parametreli sorgular)
_SELECT_BY_ID = (
    "SELECT id, course_id, material_id, status, progress, error, created_at, updated_at "
    "FROM indexing_jobs WHERE id = ?"
)
_LIST_BY_COURSE = (
    "SELECT id, course_id, material_id, status, progress, error, created_at, updated_at "
    "FROM indexing_jobs WHERE course_id = ? ORDER BY id DESC"
)


class IndexingJobOut(BaseModel):
    id: int
    course_id: int
    material_id: int | None
    status: str
    progress: float
    error: str | None
    created_at: str
    updated_at: str


async def _fetch_job(db, job_id: int) -> dict | None:
    cursor = await db.execute(_SELECT_BY_ID, (job_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


@router.post("/materials/{material_id}/index", response_model=IndexingJobOut, status_code=201)
async def enqueue_index(material_id: int) -> IndexingJobOut:
    """Materyal için indeksleme işi kuyruğa alır (çift iş çalışmaz — idempotent)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id FROM materials WHERE id = ?", (material_id,)
        )
        material = await cursor.fetchone()
        if material is None:
            raise HTTPException(status_code=404, detail="Materyal bulunamadı")

        cursor = await db.execute(
            "SELECT id FROM indexing_jobs WHERE material_id = ? "
            "AND status IN ('pending', 'processing')",
            (material_id,),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Bu materyal için zaten bir indeksleme işi var",
            )

        cursor = await db.execute(
            "INSERT INTO indexing_jobs (course_id, material_id, status, progress) "
            "VALUES (?, ?, 'pending', 0)",
            (material["course_id"], material_id),
        )
        await db.commit()
        job_id = cursor.lastrowid
        if job_id is None:
            raise RuntimeError("iş kimliği alınamadı")
    finally:
        await db.close()

    # Arka plan işleyiciye haber ver (worker loop da bekleyenleri tarar)
    await process_pending_jobs()

    db = await get_db()
    try:
        job = await _fetch_job(db, job_id)
    finally:
        await db.close()
    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı")
    return IndexingJobOut(**job)


@router.get("/courses/{course_id}/indexing-jobs", response_model=list[IndexingJobOut])
async def list_indexing_jobs(course_id: int) -> list[IndexingJobOut]:
    """Bir derse ait indeksleme işlerini (yeniden eskiye) döner."""
    db = await get_db()
    try:
        cursor = await db.execute(_LIST_BY_COURSE, (course_id,))
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [IndexingJobOut(**dict(r)) for r in rows]
