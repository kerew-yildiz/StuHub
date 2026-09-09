"""JWT doğrulamanın event loop'u bloklamaması + süresi dolmuş token'da JWKS çekmemesi.

2026-09-08 canlı ölçüm: `get_tenant_id` senkron JWKS çekimini event loop üzerinde
yapıyordu — 6 eşzamanlı istekte `/health` 2ms yerine 1243ms dönüyordu (tüm backend
duruyordu). Bu iki test o davranışın geri gelmesini engeller.
"""

from __future__ import annotations

import asyncio
import time

import jwt
import pytest

from src import auth


async def test_decode_event_loop_u_bloklamaz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    monkeypatch.setattr(auth, "_decode_token", lambda _token: (time.sleep(0.2), {"sub": "t1"})[1])
    monkeypatch.setattr(auth, "_provisioned", {"t1"})

    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    try:
        assert await auth.get_tenant_id("Bearer x") == "t1"
    finally:
        beat.cancel()

    # Senkron çalışsaydı loop 200ms boyunca hiç dönmez, tick sayısı 0-1'de kalırdı.
    assert ticks > 5


async def test_suresi_dolmus_token_jwks_tazelemez(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "legacy-secret")
    calls: list[bool] = []

    class _StubClient:
        def get_signing_key_from_jwt(self, _token: str):
            raise jwt.ExpiredSignatureError("expired")

    def _client(*, fresh: bool = False):
        calls.append(fresh)
        return _StubClient()

    monkeypatch.setattr(auth, "_get_jwk_client", _client)

    with pytest.raises(auth.AuthError):
        await auth.get_tenant_id("Bearer x")

    # Tek istemci, tek deneme: `fresh=True` yeniden denemesi (ağ turu) tetiklenmemeli.
    assert calls == [False]
