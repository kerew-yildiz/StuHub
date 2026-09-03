"""SaaS kimlik doğrulama — Supabase JWT doğrulama + kiracı kimliği çözümü.

Yerel/test modunda (`settings.saas_mode` False, yani `DATABASE_URL` boş) auth yok:
sabit `LOCAL_TENANT_ID` kullanılır, bugünkü tek-kullanıcı davranışı birebir korunur
(KARAR-SAAS-GECISI.md soru 1/7 — yerel sürüm auth'suz kalır).

SaaS modunda her istek `Authorization: Bearer <supabase-access-token>` taşımak
zorundadır. İmza `SUPABASE_JWT_SECRET` (Supabase proje ayarları → JWT Settings →
Legacy JWT Secret, HS256) ile doğrulanır; `sub` claim'i `tenant_id` (Supabase
`auth.users.id`, uuid) olarak kullanılır. İlk geçerli istekte `profiles` tablosuna
otomatik bir satır açılır (auto-provision) — Supabase Auth kullanıcı kaydını
kendi yönetir, uygulama yalnızca profil/plan satırını senkron tutar.

`require_admin`: `/api/settings` gibi kiracıya özel OLMAYAN, operatör-seviyeli
uçlar için (bkz. schema_postgres.sql `settings` tablosu yorumu). Yerel modda
her istek admin sayılır; SaaS modunda yalnızca `profiles.is_admin = true`.
"""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException

from .config import settings
from .db import get_db

LOCAL_TENANT_ID = "local"

# Supabase access token'ları bu audience ile imzalanır (GoTrue varsayılanı).
_JWT_AUDIENCE = "authenticated"


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = 401) -> None:
        super().__init__(status_code=status_code, detail=detail)


def _decode_token(token: str) -> dict:
    if not settings.supabase_jwt_secret:
        raise AuthError("Sunucu SaaS auth için yapılandırılmamış (SUPABASE_JWT_SECRET eksik).")
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=_JWT_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Oturum geçersiz veya süresi dolmuş.") from exc


async def _ensure_profile(tenant_id: str, email: str) -> None:
    """Profil satırı yoksa açar (varsayılan plan: free). Var olanı değiştirmez."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO profiles (id, email) VALUES (?, ?) "
            "ON CONFLICT (id) DO NOTHING",
            (tenant_id, email),
        )
        await db.commit()
    finally:
        await db.close()


async def _fetch_profile(tenant_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, plan, is_admin FROM profiles WHERE id = ?", (tenant_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_tenant_id(authorization: str | None = Header(default=None)) -> str:
    """İstek sahibinin kiracı kimliğini döner; SaaS modunda JWT doğrular ve
    profili otomatik açar. Yerel modda her zaman `LOCAL_TENANT_ID` döner."""
    if not settings.saas_mode:
        return LOCAL_TENANT_ID
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("Oturum açmanız gerekiyor.")
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_token(token)
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise AuthError("Oturum geçersiz.")
    await _ensure_profile(tenant_id, payload.get("email", ""))
    return tenant_id


async def require_admin(authorization: str | None = Header(default=None)) -> str:
    """`/api/settings` gibi operatör uçları için: yerel modda serbest, SaaS
    modunda yalnızca `profiles.is_admin = true` olan kiracı."""
    tenant_id = await get_tenant_id(authorization)
    if not settings.saas_mode:
        return tenant_id
    profile = await _fetch_profile(tenant_id)
    if profile is None or not profile.get("is_admin"):
        raise AuthError("Bu uç yalnızca yönetici erişimine açık.", status_code=403)
    return tenant_id
