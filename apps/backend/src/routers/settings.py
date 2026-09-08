"""Uygulama ayarları router'ı — ücretsiz LLM sağlayıcı anahtarları + durumu (Faz 1.4 temeli)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import require_admin
from ..db import get_db
from ..services import llm_service
from ..services.llm_providers import PROVIDER_CHAIN

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Değerleri API yanıtında maskelenecek anahtarlar
SENSITIVE_KEYS = {p.api_key_setting for p in PROVIDER_CHAIN}


class SettingIn(BaseModel):
    key: str
    value: str


def _mask(key: str, value: str) -> str:
    if key in SENSITIVE_KEYS and value:
        return f"{value[:4]}••••"
    return value


@router.get("")
async def get_settings(_: str = Depends(require_admin)) -> dict[str, str]:
    """Tüm ayarları döner; gizli anahtarlar maskeli."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return {key: _mask(key, value) for key, value in rows}


@router.put("")
async def upsert_setting(item: SettingIn, _: str = Depends(require_admin)) -> dict[str, bool]:
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
    # LLM anahtarı/ayarı değişmiş olabilir — TTL'li önbellek beklenmeden tazelensin
    # (Ayarlar sayfasından anahtar giren kullanıcı etkiyi hemen görmeli).
    llm_service.reset_config_cache()
    return {"ok": True}


@router.get("/llm-status")
async def get_llm_status(_: str = Depends(require_admin)) -> list[dict[str, object]]:
    """Ücretsiz sağlayıcı zincirinin durumu — yapılandırılmış mı, cooldown'da mı, aktif mi.

    Anahtar değerleri döndürmez; yalnızca Ayarlar sayfasındaki durum göstergesi için.
    """
    keys, cooldowns = await llm_service._load_config()
    active_found = False
    result: list[dict[str, object]] = []
    for provider in PROVIDER_CHAIN:
        configured = llm_service._is_provider_configured(provider, keys)
        cooldown_until = cooldowns.get(provider.name)
        in_cooldown = False
        if cooldown_until:
            try:
                in_cooldown = datetime.fromisoformat(cooldown_until) > datetime.now(UTC)
            except ValueError:
                in_cooldown = False
        is_active = configured and not in_cooldown and not active_found
        if is_active:
            active_found = True
        result.append(
            {
                "name": provider.name,
                "label": provider.label,
                "configured": configured,
                "cooldown_until": cooldown_until if in_cooldown else None,
                "active": is_active,
            }
        )
    return result
