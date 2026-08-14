"""Dönem (term) CRUD — Faz 1.1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db

router = APIRouter(prefix="/api/terms", tags=["terms"])

# Sabit SQL şablonları — kullanıcı girdisi asla SQL'e gömülmez (parametreli sorgular)
_SELECT_BY_ID = (
    "SELECT id, name, start_date, end_date, created_at FROM terms WHERE id = ?"
)
_LIST_SQL = (
    "SELECT id, name, start_date, end_date, created_at "
    "FROM terms ORDER BY created_at DESC, id DESC"
)


class TermIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: str | None = None
    end_date: str | None = None


class TermOut(TermIn):
    id: int
    created_at: str


async def _fetch(db, term_id: int) -> dict | None:
    cursor = await db.execute(_SELECT_BY_ID, (term_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


def _require(row: dict | None) -> dict:
    if row is None:
        raise RuntimeError("beklenen dönem satırı bulunamadı")
    return row


@router.get("", response_model=list[TermOut])
async def list_terms() -> list[TermOut]:
    """Dönem listesi (yeniden eskiye)."""
    db = await get_db()
    try:
        cursor = await db.execute(_LIST_SQL)
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [TermOut(**dict(r)) for r in rows]


@router.post("", response_model=TermOut, status_code=201)
async def create_term(item: TermIn) -> TermOut:
    """Yeni dönem oluşturur."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO terms (name, start_date, end_date) VALUES (?, ?, ?)",
            (item.name, item.start_date, item.end_date),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("dönem kimliği alınamadı")
        term = await _fetch(db, row_id)
    finally:
        await db.close()
    return TermOut(**dict(_require(term)))


@router.get("/{term_id}", response_model=TermOut)
async def get_term(term_id: int) -> TermOut:
    """Tek dönem detayı."""
    db = await get_db()
    try:
        row = await _fetch(db, term_id)
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Dönem bulunamadı")
    return TermOut(**row)


@router.put("/{term_id}", response_model=TermOut)
async def update_term(term_id: int, item: TermIn) -> TermOut:
    """Dönemi günceller."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE terms SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
            (item.name, item.start_date, item.end_date, term_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Dönem bulunamadı")
        await db.commit()
        term = await _fetch(db, term_id)
    finally:
        await db.close()
    return TermOut(**dict(_require(term)))


@router.delete("/{term_id}", status_code=204)
async def delete_term(term_id: int) -> None:
    """Dönemi siler (dersler cascade ile silinir)."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM terms WHERE id = ?", (term_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Dönem bulunamadı")
        await db.commit()
    finally:
        await db.close()
