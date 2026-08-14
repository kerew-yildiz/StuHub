"""Dönem (term) router'ı — Faz 1'de tam CRUD eklenecek (iskelet)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/terms", tags=["terms"])


@router.get("")
async def list_terms() -> list[dict]:
    """Dönem listesi (Faz 1.1 iskeleti — şimdilik boş)."""
    return []
