"""Ayarlar router'ı — kaydet/oku + gizli anahtar maskesi testleri."""


async def test_settings_roundtrip(client):
    resp = await client.put("/api/settings", json={"key": "model", "value": "deepseek-chat"})
    assert resp.status_code == 200

    resp2 = await client.get("/api/settings")
    assert resp2.status_code == 200
    assert resp2.json()["model"] == "deepseek-chat"


async def test_settings_update_existing(client):
    await client.put("/api/settings", json={"key": "model", "value": "deepseek-chat"})
    await client.put("/api/settings", json={"key": "model", "value": "deepseek-reasoner"})
    resp = await client.get("/api/settings")
    assert resp.json()["model"] == "deepseek-reasoner"


async def test_secret_key_masked_in_response(client):
    await client.put("/api/settings", json={"key": "deepseek_api_key", "value": "sk-abcdef123456"})
    resp = await client.get("/api/settings")
    body = resp.json()
    masked = body["deepseek_api_key"]
    assert "sk-abcdef123456" not in masked
    assert masked.startswith("sk-a")
    assert "•" in masked
