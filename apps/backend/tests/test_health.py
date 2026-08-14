"""GET /health ve GET / — temel iskelet testleri (Faz 0.3)."""


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "stuhub-backend"


async def test_root_info(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "stuhub-backend"
    assert "version" in body
