"""GET /health ve GET / — temel iskelet testleri (Faz 0.3 + üretim SPA modu)."""

from src.main import INDEX_HTML


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "stuhub-backend"


async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    if INDEX_HTML.exists():
        # üretim modu: kök, inşa edilmiş SPA'yi döner
        assert "text/html" in resp.headers["content-type"]
        assert "<html" in resp.text or 'id="root"' in resp.text
    else:
        body = resp.json()
        assert body["app"] == "stuhub-backend"
        assert "version" in body
