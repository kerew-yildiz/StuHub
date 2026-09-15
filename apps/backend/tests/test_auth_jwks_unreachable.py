"""JWKS ucuna ulaşılamadığında davranış: tek deneme, kısa zaman aşımı, 503.

2026-09-10 canlı ölçüm (test kampanyası, Alan 33): geçici bir ağ arızasında JWKS
çekimi `WinError 10054` ile 19.3 sn sonra düşüyordu; `_decode_token` bunu genel
`PyJWTError` sanıp `fresh=True` ile İKİNCİ bir ağ turu daha yapıyordu → her kimlik
doğrulamalı istek 38.6 sn asılıyor (3 koşu: 38618/38611/38557 ms) ve sonunda
`401 "Oturum geçersiz veya süresi dolmuş."` dönüyordu. İki ayrı hata: (a) sınırsız
gecikme, (b) altyapı arızasının kullanıcı oturumu hatası gibi raporlanması.
"""

from __future__ import annotations

import jwt
import pytest
from jwt.exceptions import PyJWKClientConnectionError

from src import auth


class _StubClient:
    """`get_signing_key_from_jwt` çağrısında verilen hatayı fırlatan JWKS istemcisi."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get_signing_key_from_jwt(self, _token: str):
        raise self._error


def _stub_clients(monkeypatch: pytest.MonkeyPatch, error: Exception) -> list[bool]:
    """`_get_jwk_client`'ı sabitler; dönen liste `fresh` bayraklarının kaydıdır."""
    calls: list[bool] = []

    def _client(*, fresh: bool = False):
        calls.append(fresh)
        return _StubClient(error)

    monkeypatch.setattr(auth, "_get_jwk_client", _client)
    return calls


async def test_jwks_ulasilamazsa_tek_deneme_ve_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    # HS256 sırrı DOLU olmasına rağmen oraya düşülmemeli: ağ hatası "imza yanlış"
    # demek değildir, ES256 token'ı HS256 ile denemek boşuna gecikmedir.
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "legacy-secret")
    calls = _stub_clients(monkeypatch, PyJWKClientConnectionError("ağa ulaşılamadı"))

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id("Bearer x")

    assert caught.value.status_code == 503
    assert "ulaşılamıyor" in caught.value.detail
    # Tek deneme: `fresh=True` ikinci ağ turu tetiklenmemeli (38.6 sn'nin kaynağı buydu).
    assert calls == [False]


async def test_bozuk_imzada_jwks_turu_atilmaz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bozuk/çöp token JWKS'i tazeletmemeli — ağ turu sonucu değiştirmez."""
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "")
    calls = _stub_clients(monkeypatch, jwt.InvalidSignatureError("imza uyuşmuyor"))

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id("Bearer x")

    assert caught.value.status_code == 401
    assert calls == [False]


async def test_anahtar_rotasyonunda_taze_istemciyle_tekrar_denenir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-09-08 düzeltmesi korunmalı: kid önbellekte yoksa taze istemciyle bir kez daha."""
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "")
    calls = _stub_clients(monkeypatch, jwt.PyJWKClientError("eşleşen imza anahtarı yok"))

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id("Bearer x")

    assert caught.value.status_code == 401
    assert calls == [False, True]


def test_taze_istemci_global_onbellegi_ezmez(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fresh=True` süreç genelindeki ısınmış istemciyi çöpe atmamalı."""
    monkeypatch.setattr(auth.settings, "supabase_url", "https://proje.supabase.co")
    monkeypatch.setattr(auth, "_jwk_client", None)
    monkeypatch.setattr(jwt, "PyJWKClient", lambda uri, **kwargs: object())

    warm = auth._get_jwk_client()
    fresh = auth._get_jwk_client(fresh=True)

    assert fresh is not warm
    # Isınmış istemci yerinde kalmalı: aksi halde auth'suz bir çöp istek, sonraki
    # meşru isteğe yeni bir JWKS ağ turu ödetirdi.
    assert auth._get_jwk_client() is warm


def test_jwks_istemcisi_kisa_zaman_asimiyla_kurulur(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://proje.supabase.co")
    monkeypatch.setattr(auth, "_jwk_client", None)
    captured: dict[str, object] = {}

    class _Recorder:
        def __init__(self, uri: str, **kwargs: object) -> None:
            captured["uri"] = uri
            captured.update(kwargs)

    monkeypatch.setattr(jwt, "PyJWKClient", _Recorder)
    auth._get_jwk_client(fresh=True)

    assert captured["uri"] == "https://proje.supabase.co/auth/v1/.well-known/jwks.json"
    # PyJWT varsayılanı 30 sn — erişilemeyen uçta istek başına kabul edilemez gecikme.
    assert captured["timeout"] == auth._JWKS_TIMEOUT_SECONDS <= 5
