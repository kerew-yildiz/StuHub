"""Ayarlar router'ı — kaydet/oku + gizli anahtar maskesi + LLM sağlayıcı durumu testleri."""

from src.services.llm_providers import PROVIDER_CHAIN


async def test_settings_roundtrip(client):
    resp = await client.put("/api/settings", json={"key": "daily_goal", "value": "5"})
    assert resp.status_code == 200

    resp2 = await client.get("/api/settings")
    assert resp2.status_code == 200
    assert resp2.json()["daily_goal"] == "5"


async def test_settings_update_existing(client):
    await client.put("/api/settings", json={"key": "daily_goal", "value": "3"})
    await client.put("/api/settings", json={"key": "daily_goal", "value": "7"})
    resp = await client.get("/api/settings")
    assert resp.json()["daily_goal"] == "7"


async def test_secret_key_masked_in_response(client):
    await client.put("/api/settings", json={"key": "google_api_key", "value": "sk-abcdef123456"})
    resp = await client.get("/api/settings")
    body = resp.json()
    masked = body["google_api_key"]
    assert "sk-abcdef123456" not in masked
    assert masked.startswith("sk-a")
    assert "•" in masked


async def test_llm_status_reports_unconfigured_chain(client):
    resp = await client.get("/api/settings/llm-status")
    assert resp.status_code == 200
    body = resp.json()
    # Beklenen liste PROVIDER_CHAIN'den türetilir: zincire sağlayıcı eklenmesi/çıkarılması
    # (ör. 2026-09-16 opencode) bu testi bayatlatmaz. Testin koruduğu asıl sözleşme:
    # uç nokta zinciri eksiksiz, zincir sırasıyla ve hepsi `configured: false` raporlar.
    assert [p["name"] for p in body] == [p.name for p in PROVIDER_CHAIN]
    assert all(p["configured"] is False for p in body)
    assert all(p["active"] is False for p in body)


async def test_llm_status_reports_active_provider(client):
    await client.put("/api/settings", json={"key": "google_api_key", "value": "sk-test"})
    resp = await client.get("/api/settings/llm-status")
    body = {p["name"]: p for p in resp.json()}
    assert body["gemini"]["configured"] is True
    assert body["gemini"]["active"] is True
    assert body["openrouter"]["active"] is False
