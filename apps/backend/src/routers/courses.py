"""Ders (course) CRUD — Faz 1.2."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["courses"])

# Sabit SQL şablonları — kullanıcı girdisi asla SQL'e gömülmez (parametreli sorgular)
_SELECT_BY_ID = (
    "SELECT id, term_id, name, instructor, metadata_json, created_at "
    "FROM courses WHERE id = ? AND tenant_id = ?"
)
_LIST_BY_TERM = (
    "SELECT id, term_id, name, instructor, metadata_json, created_at "
    "FROM courses WHERE term_id = ? AND tenant_id = ? ORDER BY created_at DESC, id DESC"
)


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    instructor: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class CourseOut(CourseIn):
    id: int
    term_id: int
    created_at: str


def _row_to_out(row: dict) -> CourseOut:
    data = dict(row)
    data["metadata_json"] = json.loads(data["metadata_json"] or "{}")
    return CourseOut(**data)


async def _fetch(db, course_id: int, tenant_id: str) -> dict | None:
    cursor = await db.execute(_SELECT_BY_ID, (course_id, tenant_id))
    row = await cursor.fetchone()
    return dict(row) if row else None


def _require(row: dict | None) -> dict:
    if row is None:
        raise RuntimeError("beklenen ders satırı bulunamadı")
    return row


async def _term_exists(db, term_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM terms WHERE id = ? AND tenant_id = ?", (term_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.get("/terms/{term_id}/courses", response_model=list[CourseOut])
async def list_courses(
    term_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[CourseOut]:
    """Bir döneme ait dersler (yeniden eskiye)."""
    db = await get_db()
    try:
        cursor = await db.execute(_LIST_BY_TERM, (term_id, tenant_id))
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [_row_to_out(dict(r)) for r in rows]


@router.post("/terms/{term_id}/courses", response_model=CourseOut, status_code=201)
async def create_course(
    term_id: int, item: CourseIn, tenant_id: str = Depends(get_tenant_id)
) -> CourseOut:
    """Bir dönem altında yeni ders oluşturur."""
    db = await get_db()
    try:
        if not await _term_exists(db, term_id, tenant_id):
            raise HTTPException(status_code=404, detail="Dönem bulunamadı")
        cursor = await db.execute(
            "INSERT INTO courses (tenant_id, term_id, name, instructor, metadata_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                tenant_id,
                term_id,
                item.name,
                item.instructor,
                json.dumps(item.metadata_json, ensure_ascii=False),
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("ders kimliği alınamadı")
        row = await _fetch(db, row_id, tenant_id)
    finally:
        await db.close()
    return _row_to_out(_require(row))


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course(course_id: int, tenant_id: str = Depends(get_tenant_id)) -> CourseOut:
    """Tek ders detayı."""
    db = await get_db()
    try:
        row = await _fetch(db, course_id, tenant_id)
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")
    return _row_to_out(row)


@router.put("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: int, item: CourseIn, tenant_id: str = Depends(get_tenant_id)
) -> CourseOut:
    """Dersi günceller."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE courses SET name = ?, instructor = ?, metadata_json = ? "
            "WHERE id = ? AND tenant_id = ?",
            (
                item.name,
                item.instructor,
                json.dumps(item.metadata_json, ensure_ascii=False),
                course_id,
                tenant_id,
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        await db.commit()
        row = await _fetch(db, course_id, tenant_id)
    finally:
        await db.close()
    return _row_to_out(_require(row))


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(course_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Dersi siler (chapter/materyal cascade ile silinir)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        await db.commit()
    finally:
        await db.close()
