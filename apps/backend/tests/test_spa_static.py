"""Üretim modu statik dosya servisi — `spa_fallback` MIME + path traversal regresyonu (C4).

Bug (2026-09-10, prod'da doğrulandı): `main.py` yalnızca `sw.js` ve
`manifest.webmanifest` için açık rota kaydediyordu; `dist/` kökündeki diğer dosyalar
(`registerSW.js`, `workbox-*.js`, `icon.svg`) catch-all SPA fallback'e düşüp
`index.html` alıyordu — `GET /registerSW.js` → 200 ama `content-type: text/html`.
Tarayıcı bunu JS olarak çalıştırınca `Uncaught SyntaxError: Unexpected token '<'`
veriyor, PWA kaydı kırılıyordu. Düzeltme: fallback, dist altındaki gerçek dosyayı
MIME'ıyla servis eder; `resolve()` sonrası dist dışına çıkma şartı traversal'ı kapatır.

Test yöntemi: gerçek `dist/` içeriğine bağlı kalmadan tüm uzantı matrisi, `tmp_path`
altında kurulan SAHTE statik kökle koşar (`main.FRONTEND_DIST`/`INDEX_HTML` yamalanır).
Yalnızca açık PWA rotaları (`sw.js`, `manifest.webmanifest`) gerçek build çıktısına
bakar; onlar zaten `dist/` yoksa atlanır — nitekim tüm dosya, rotalar import anında
kaydedildiği için `dist/` yokluğunda atlanır (bkz. `test_health.test_root` aynı koşul).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src import main

pytestmark = pytest.mark.skipif(
    not main.INDEX_HTML.exists(),
    reason="apps/frontend/dist inşa edilmemiş — üretim statik servis yolu yok",
)

_FAKE_INDEX = '<!doctype html><html><body><div id="root">SPA</div></body></html>'


@pytest.fixture
def fake_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sahte `dist/` + kök DIŞINDA bir sızıntı dosyası kurar."""
    root = tmp_path / "dist"
    (root / "fonts").mkdir(parents=True)
    (root / "index.html").write_text(_FAKE_INDEX, encoding="utf-8")
    (root / "app.js").write_text("console.log('stuhub');", encoding="utf-8")
    (root / "styles.css").write_text("body { color: #111; }", encoding="utf-8")
    (root / "icon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    (root / "fonts" / "Montserrat-Regular.ttf").write_bytes(b"\x00\x01\x00\x00fake-font")
    (tmp_path / "gizli.txt").write_text("SIZINTI-OLMAMALI", encoding="utf-8")

    monkeypatch.setattr(main, "FRONTEND_DIST", root)
    monkeypatch.setattr(main, "INDEX_HTML", root / "index.html")
    return root


async def test_index_html_text_html_olarak_sunulur(client, fake_dist):
    resp = await client.get("/index.html")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "SPA" in resp.text


async def test_index_kabugu_onbelleklenmez(client, fake_dist):
    """Deploy sonrası eski kabuk önbellekten gelmesin (PWA otomatik güncelleme).

    Ölçüm (2026-09-18, prod): `/` yanıtında Cache-Control HİÇ yoktu — başlıksız
    yanıtta tarayıcı sezgisel önbellekleme uygular ve yeni deploy'u hiç görmez.
    """
    resp = await client.get("/index.html")

    assert resp.headers["cache-control"] == main.CACHE_NO_STORE


async def test_spa_fallback_kabugu_onbelleklenmez(client, fake_dist):
    resp = await client.get("/dersler/4")

    assert resp.headers["cache-control"] == main.CACHE_NO_STORE


async def test_hashli_asset_immutable_onbelleklenir(client):
    """`/assets/*` içerik-hash'li — asla değişmez, 1 yıl immutable (doğru önbellek)."""
    assets_dir = main.FRONTEND_DIST / "assets"
    adaylar = sorted(assets_dir.glob("*")) if assets_dir.exists() else []
    if not adaylar:
        pytest.skip("assets/ bu build çıktısında yok")

    resp = await client.get(f"/assets/{adaylar[0].name}")

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == main.CACHE_IMMUTABLE


async def test_js_dosyasi_javascript_olarak_sunulur(client, fake_dist):
    """Asıl prod bug'ı: kök seviyesindeki .js dosyası index.html olarak dönüyordu."""
    resp = await client.get("/app.js")

    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert resp.text == "console.log('stuhub');"
    assert "<!doctype" not in resp.text.lower()


async def test_css_dosyasi_text_css_olarak_sunulur(client, fake_dist):
    resp = await client.get("/styles.css")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")
    assert "color" in resp.text


async def test_font_dosyasi_font_mime_iyle_sunulur(client, fake_dist):
    """`mimetypes` bu uzantıyı tanımıyor — `STATIC_MEDIA_TYPES` eşlemesi devrede."""
    resp = await client.get("/fonts/Montserrat-Regular.ttf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == main.STATIC_MEDIA_TYPES[".ttf"] == "font/ttf"


async def test_svg_dosyasi_image_olarak_sunulur(client, fake_dist):
    resp = await client.get("/icon.svg")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("traversal", ["/..%2Fgizli.txt", "/..%2F..%2Fgizli.txt"])
async def test_path_traversal_dist_disina_cikamaz(client, fake_dist, traversal):
    """`resolve()` sonrası dist dışında kalan dosya servis EDİLMEMELİ, SPA index'i döner."""
    resp = await client.get(traversal)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "SIZINTI-OLMAMALI" not in resp.text


async def test_dosya_olmayan_rota_index_e_duser(client, fake_dist):
    """İstemci tarafı rotalar (dist'te karşılığı yok) hâlâ SPA'ye düşmeli."""
    resp = await client.get("/dersler/4")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "SPA" in resp.text


async def test_api_yolu_index_e_dusmez(client, fake_dist):
    resp = await client.get("/api/boyle-bir-uc-yok")

    assert resp.status_code == 404
    # API yanıtlarına önbellek middleware'i dokunmaz (başlığı uçlar belirler).
    assert "cache-control" not in resp.headers


async def test_manifest_keeps_its_media_type(client):
    """`mimetypes` `.webmanifest`i tanımıyor — açık rotanın medya tipi korunmalı."""
    if not main.MANIFEST_FILE.exists():
        pytest.skip("manifest.webmanifest bu build çıktısında yok")

    resp = await client.get("/manifest.webmanifest")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")
    assert resp.headers["cache-control"] == main.CACHE_NO_STORE


async def test_service_worker_served_as_javascript(client):
    """PWA kaydı `sw.js`in JS olarak sunulmasına bağlı (açık rota)."""
    if not main.SW_FILE.exists():
        pytest.skip("sw.js bu build çıktısında yok")

    resp = await client.get("/sw.js")

    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    # SW betiği HTTP önbelleğinden gelirse yeni sürüm hiç görülmez.
    assert resp.headers["cache-control"] == main.CACHE_NO_STORE
