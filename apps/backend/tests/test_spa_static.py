"""Üretim modu statik dosya servisi — `spa_fallback` regresyon koruması.

Bug: `main.py` yalnızca `sw.js` ve `manifest.webmanifest` için açık rota kaydediyordu;
`dist/` kökündeki diğer dosyalar (`registerSW.js`, `workbox-*.js`, `icon.svg`) catch-all
SPA fallback'e düşüp `index.html` alıyordu. Prod'da doğrulandı (2026-09-10):
`GET /registerSW.js` → 200 ama `content-type: text/html`, 758 bayt `<!doctype html>`.
Tarayıcı bunu JS olarak çalıştırınca `Uncaught SyntaxError: Unexpected token '<'` veriyor
ve PWA tamamen kırılıyordu; manifest ikonu da "geçersiz görsel" oluyordu.

Testler `dist/` inşa edilmişse koşar. Backend'in kendi CI job'u frontend build etmiyor,
o yüzden yokluğunda atlanır (bkz. `test_health.test_root` aynı koşulu kullanıyor).
"""

import pytest

from src.main import FRONTEND_DIST, INDEX_HTML

pytestmark = pytest.mark.skipif(
    not INDEX_HTML.exists(),
    reason="apps/frontend/dist inşa edilmemiş — üretim statik servis yolu yok",
)


async def test_register_sw_served_as_javascript(client):
    """`registerSW.js` HTML değil JS dönmeli — PWA kaydı buna bağlı."""
    if not (FRONTEND_DIST / "registerSW.js").exists():
        pytest.skip("registerSW.js bu build çıktısında yok")

    resp = await client.get("/registerSW.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert "<!doctype" not in resp.text.lower()


async def test_icon_svg_served_as_image(client):
    """Manifest ikonu gerçek SVG dönmeli, `index.html` değil."""
    if not (FRONTEND_DIST / "icon.svg").exists():
        pytest.skip("icon.svg bu build çıktısında yok")

    resp = await client.get("/icon.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in resp.text


async def test_manifest_keeps_its_media_type(client):
    """`mimetypes` `.webmanifest`i tanımıyor — açık eşleme korunmalı."""
    if not (FRONTEND_DIST / "manifest.webmanifest").exists():
        pytest.skip("manifest.webmanifest bu build çıktısında yok")

    resp = await client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")


async def test_service_worker_served_as_javascript(client):
    if not (FRONTEND_DIST / "sw.js").exists():
        pytest.skip("sw.js bu build çıktısında yok")

    resp = await client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


async def test_unknown_spa_route_still_returns_index(client):
    """İstemci tarafı rotalar (dosya değil) hâlâ SPA'ye düşmeli."""
    resp = await client.get("/dersler/4")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_unknown_api_path_is_404_not_index(client):
    resp = await client.get("/api/boyle-bir-uc-yok")
    assert resp.status_code == 404


async def test_path_traversal_cannot_escape_dist(client):
    """`dist/` dışındaki gerçek bir dosya (../package.json) servis EDİLMEMELİ.

    Güvenlik gereği: dosya varlığına bakan fallback, `resolve()` sonrası yolun
    `FRONTEND_DIST` altında kaldığını doğrulamazsa dosya sistemi okunabilir hale gelir.
    """
    outside = FRONTEND_DIST.parent / "package.json"
    assert outside.exists(), "test öncülü: apps/frontend/package.json bulunmalı"

    resp = await client.get("/..%2Fpackage.json")
    assert resp.status_code == 200
    # Sızıntı yok: SPA index'i döner, paket manifesti dönmez.
    assert "text/html" in resp.headers["content-type"]
    assert '"devDependencies"' not in resp.text
