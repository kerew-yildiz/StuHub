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


async def test_health_stays_cheap(client, monkeypatch):
    """`/health` veritabanına DOKUNMAMALI — frontend onu sekme başına 5 sn'de bir yokluyor.

    Bu uca bir DB sorgusu eklemek yükü sekme sayısıyla çarpar (yol haritası, "ölçekten
    bağımsız" madde 3); regresyonu burada yakalanır.
    """
    from src import main as main_module

    async def explode():
        raise AssertionError("/health veritabanına dokunmamalı")

    monkeypatch.setattr(main_module, "get_db", explode)
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_health_deep_reports_dependencies(client):
    resp = await client.get("/health/deep")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    # Test ortamında hiçbir sağlayıcı anahtarı yok (conftest sıfırlıyor).
    assert body["llm_providers_available"] == 0


async def test_health_deep_returns_503_when_db_down(client, monkeypatch):
    from src import main as main_module

    async def explode():
        raise RuntimeError("bağlantı yok")

    monkeypatch.setattr(main_module, "get_db", explode)
    resp = await client.get("/health/deep")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"].startswith("error:")
    # Bağlantı dizesi/kimlik bilgisi sızmamalı — yalnızca hata türü.
    assert "bağlantı yok" not in resp.text
