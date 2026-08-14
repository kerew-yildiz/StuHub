"""Uygulama ayarları router'ı — API anahtarı + model seçimi (Faz 1.4 temeli)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Değerleri API yanıtında maskelenecek anahtarlar
SENSITIVE_KEYS = {"deepseek_api_key"}


class SettingIn(BaseModel):
    key: str
    value: str


def _mask(key: str, value: str) -> str:
    if key in SENSITIVE_KEYS and value:
        return f"{value[:4]}••••"
    return value


@router.get("")
async def get_settings() -> dict[str, str]:
    """Tüm ayarları döner; gizli anahtarlar maskeli."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return {key: _mask(key, value) for key, value in rows}


@router.put("")
async def upsert_setting(item: SettingIn) -> dict[str, bool]:
    """Bir ayarı kaydeder (yoksa ekler, varsa günceller)."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (item.key, item.value),
        )
        await db.commit()
    finally:
        await db.close()
    return {"ok": True}
