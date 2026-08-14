"""Dönem CRUD testleri (Faz 1.1)."""


async def test_terms_empty(client):
    resp = await client.get("/api/terms")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_term_crud_roundtrip(client):
    # oluştur
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "2026 Bahar"
    assert body["id"] > 0
    term_id = body["id"]

    # listele
    resp = await client.get("/api/terms")
    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["2026 Bahar"]

    # güncelle
    payload = {
        "name": "2026 Bahar (uzatıldı)",
        "start_date": "2026-02-01",
        "end_date": "2026-06-30",
    }
    resp = await client.put(f"/api/terms/{term_id}", json=payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "2026 Bahar (uzatıldı)"
    assert updated["start_date"] == "2026-02-01"

    # sil
    resp = await client.delete(f"/api/terms/{term_id}")
    assert resp.status_code == 204
    resp = await client.get("/api/terms")
    assert resp.json() == []


async def test_term_validation_and_404(client):
    # boş ad → 422
    resp = await client.post("/api/terms", json={"name": ""})
    assert resp.status_code == 422

    # var olmayan güncelle → 404
    resp = await client.put("/api/terms/9999", json={"name": "Yok"})
    assert resp.status_code == 404

    # var olmayan sil → 404
    resp = await client.delete("/api/terms/9999")
    assert resp.status_code == 404
