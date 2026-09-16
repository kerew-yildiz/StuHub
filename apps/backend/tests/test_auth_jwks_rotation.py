"""JWKS anahtar rotasyonu (C3) — eski + yeni `kid` birlikte geçerli, bilinmeyen `kid` 401.

Supabase asimetrik imza anahtarlarını döndürürken JWKS dokümanı bir süre İKİ anahtar
birden içerir (eski + yeni); bu pencerede gelen token'lar iki farklı `kid` taşır ve
doğrulama her ikisini de kabul etmelidir. Testler PyJWT'nin GERÇEK anahtar seçimini
(`PyJWKClient.get_signing_key` → `kid` eşleştirme) ve GERÇEK ES256 imza doğrulamasını
kullanır; yalnızca JWKS'in ağ çekimi (`fetch_data`) taklit edilir — ağa hiç çıkılmaz
(brief: worker sunucu çalıştırmaz, localhost'a istek atmaz).

Beklenen davranış `src/auth.py`'den okundu (kod DEĞİŞTİRİLMEDİ):
- Bilinmeyen `kid` → `PyJWKClientError` (`PyJWTError` alt sınıfı) → önbellek atlanıp
  TAZE istemciyle bir kez daha denenir → yine başarısız → `supabase_jwt_secret` boşsa
  `401 "Oturum geçersiz veya süresi dolmuş."` (2026-09-08 rotasyon düzeltmesi).
- Ağ hatası (`PyJWKClientConnectionError`) → TEK deneme, `503` (2026-09-10 düzeltmesi;
  ayrıntılı regresyon `tests/test_auth_jwks_unreachable.py`'de).
"""

from __future__ import annotations

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.exceptions import PyJWKClientConnectionError

from src import auth

_SUPABASE_URL = "https://proje.supabase.co"
_JWKS_URI = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"


def _keypair(kid: str) -> tuple[object, dict]:
    """Gerçek ES256 anahtar çifti + JWKS'e girecek public JWK (Supabase varsayılanı)."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    return key, {**jwk, "kid": kid, "use": "sig", "alg": "ES256"}


@pytest.fixture
def rotation(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Eski + yeni `kid`'li JWKS dokümanı, ağsız sahte JWKS ucu ve istemci sayacı."""
    old_key, old_jwk = _keypair("eski-kid")
    new_key, new_jwk = _keypair("yeni-kid")
    document = {"keys": [old_jwk, new_jwk]}
    builds: list[jwt.PyJWKClient] = []

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: document)
    monkeypatch.setattr(auth, "_jwk_client", None)

    real_new_client = auth._new_jwk_client

    def _recorded_new_client() -> jwt.PyJWKClient:
        client = real_new_client()
        builds.append(client)
        return client

    # Kurulan istemci sayısı = "taze deneme yapıldı mı" göstergesi (`fresh=True`
    # doğrudan `_new_jwk_client()` çağırır, ısınmış singleton'ı ezmeden).
    monkeypatch.setattr(auth, "_new_jwk_client", _recorded_new_client)

    monkeypatch.setattr(auth.settings, "supabase_url", _SUPABASE_URL)
    # Legacy HS256 sırrı BİLEREK boş: rotasyon senaryosunda düşülecek bir yol kalmamalı,
    # hata gerçekten JWKS yolundan gelmeli.
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://x")
    # Profil auto-provision DB'ye gitmesin (konu: token doğrulama).
    monkeypatch.setattr(auth, "_provisioned", {"t1"})

    return {"old": old_key, "new": new_key, "builds": builds}


def _token(private_key: object, kid: str, sub: str = "t1") -> str:
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "email": "ogrenci@example.com",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


def test_jwks_dokumani_iki_anahtarli_uctan_kurulur(rotation) -> None:
    """Ön koşul: istemci Supabase JWKS ucuna bakar ve dokümanda iki `kid` vardır."""
    client = auth._get_jwk_client()

    assert client is not None
    assert client.uri == _JWKS_URI
    assert len(client.get_signing_keys()) == 2


async def test_eski_ve_yeni_kid_ile_imzali_tokenlar_dogrulanir(rotation) -> None:
    """Rotasyon penceresi: iki anahtar da geçerli — hiçbiri 'geçersiz oturum' almamalı."""
    old_token = _token(rotation["old"], "eski-kid")
    new_token = _token(rotation["new"], "yeni-kid")

    # Ön koşul: token'lar gerçekten FARKLI iki anahtarı işaret ediyor.
    assert jwt.get_unverified_header(old_token)["kid"] == "eski-kid"
    assert jwt.get_unverified_header(new_token)["kid"] == "yeni-kid"

    assert await auth.get_tenant_id(f"Bearer {old_token}") == "t1"
    assert await auth.get_tenant_id(f"Bearer {new_token}") == "t1"


async def test_imzasi_uyusmayan_token_reddedilir(rotation) -> None:
    """`kid` tanınıyor ama imza başka anahtardan → imza doğrulaması atlanmıyor."""
    foreign_key, _ = _keypair("eski-kid")

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id(f"Bearer {_token(foreign_key, 'eski-kid')}")

    assert caught.value.status_code == 401
    # Bozuk imza JWKS'i tazeletmez (ağ turu sonucu değiştirmez): tek istemci.
    assert len(rotation["builds"]) == 1


async def test_bilinmeyen_kid_401_ve_taze_istemciyle_tek_deneme(rotation) -> None:
    """`kid` ne eski ne yeni ise: 401 + önbellek atlanıp taze istemciyle bir kez daha."""
    stranger_key, _ = _keypair("rotasyona-girmemis-kid")

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id(
            f"Bearer {_token(stranger_key, 'rotasyona-girmemis-kid')}"
        )

    assert caught.value.status_code == 401
    assert "Oturum geçersiz" in caught.value.detail
    # İki istemci: ilki bilinmeyen kid'de düşer, ikincisi 2026-09-08 düzeltmesinin
    # "soğuk önbellek/rotasyon" yeniden denemesidir. Üçüncü bir deneme OLMAMALI.
    assert len(rotation["builds"]) == 2


async def test_jwks_ag_hatasinda_tek_deneme_ve_503(rotation, monkeypatch) -> None:
    """Ağ hatası imza hatası değildir: taze deneme YOK, 401 değil 503."""
    calls: list[str] = []

    def _unreachable(self: jwt.PyJWKClient) -> dict:
        calls.append(self.uri)
        raise PyJWKClientConnectionError('Fail to fetch data from the url, err: "ag yok"')

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _unreachable)

    with pytest.raises(auth.AuthError) as caught:
        await auth.get_tenant_id(f"Bearer {_token(rotation['old'], 'eski-kid')}")

    assert caught.value.status_code == 503
    assert "ulaşılamıyor" in caught.value.detail
    # Tek çekim + tek istemci: ikinci (taze) ağ turu 38.6 sn'lik asılmanın kaynağıydı.
    assert calls == [_JWKS_URI]
    assert len(rotation["builds"]) == 1
