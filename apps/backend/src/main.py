"""StuHub DS — FastAPI giriş noktası (Faz 0.3 + worker + üretim statik servis)."""

from __future__ import annotations

import asyncio
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import get_db, init_db
from .routers import api_router
from .services import llm_service
from .workers.feed_topup import worker_loop as feed_topup_loop
from .workers.indexer import recover_stale_jobs, worker_loop

APP_VERSION = "2.0.0"

# Üretim: inşa edilmiş frontend (apps/frontend/dist) — varsa servis edilir (yol haritası 2.2.2)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"
# v2 PWA dosyaları (Faz V2.8) — build çıktısında varsa servis edilir
SW_FILE = FRONTEND_DIST / "sw.js"
MANIFEST_FILE = FRONTEND_DIST / "manifest.webmanifest"

# `mimetypes` bu uzantıları tanımıyor (ölçüldü: Windows Python 3.12'de registry de boş
# dönüyor) — açık eşleme olmadan dist/fonts yazı tipleri `text/html` olarak sunulurdu.
STATIC_MEDIA_TYPES = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Açılışta veri dizini + şema hazırlar; arka plan işçilerini başlatır.

    İki işçi: indeksleyici (bekleyen indeksleme işleri) ve feed havuzu doldurucu
    (son 24 saatte kullanılan derslerin quiz feed havuzunu hedefte tutar).
    """
    await init_db()
    if not settings.run_workers:
        # Ayrı bir worker servisi (STUHUB_ROLE=worker) çalışıyor — API kuyruğu taramaz.
        yield
        return

    await recover_stale_jobs()
    stop_event = asyncio.Event()
    worker = asyncio.create_task(worker_loop(stop_event))
    feed_worker = asyncio.create_task(feed_topup_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        worker.cancel()
        feed_worker.cancel()


app = FastAPI(
    title="StuHub DS API",
    description="Yerel ders notu ve quiz uygulaması API'si",
    version=APP_VERSION,
    lifespan=lifespan,
)

# SPA ayrı bir origin'den (CDN/farklı domain) servis edilecekse CORS gerekir; aynı
# origin'den servis edilirken (bugünkü varsayılan) middleware hiç eklenmez.
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── Önbellek başlıkları (2026-09-18 — PWA otomatik güncelleme) ─────────
# Ölçüm (prod, curl): `/`, `/sw.js`, `/registerSW.js`, `/manifest.webmanifest`
# yanıtlarında `Cache-Control` HİÇ yoktu (yalnızca ETag/Last-Modified). Başlık
# yokken tarayıcı *sezgisel* önbellekleme uygular — deploy sonrası eski HTML
# kabuğu önbellekten servis edilir; service worker betiği de önbellekten
# okunabildiği için güncelleme hiç görülmez (kullanıcı Ctrl+Shift+R'a mahkûm).
# Tek kural, tüm statik yanıtlar için:
#   - `/assets/*` içerik-hash'li, asla değişmez → 1 yıl immutable
#   - diğer her şey (HTML kabuğu, sw.js, manifest, ikon/font) → her istekte doğrula
# API yanıtlarına dokunulmaz; kendi başlıklarını uçlar belirler.
ASSETS_PATH_PREFIX = "/assets/"
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_NO_STORE = "no-cache, no-store, must-revalidate"


@app.middleware("http")
async def static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    yol = request.url.path
    if yol.startswith(ASSETS_PATH_PREFIX):
        response.headers["Cache-Control"] = CACHE_IMMUTABLE
    elif not yol.startswith("/api/"):
        # Bir uç kendi başlığını koyduysa ona dokunma (setdefault).
        response.headers.setdefault("Cache-Control", CACHE_NO_STORE)
    return response


app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Ucuz sağlık kontrolü — frontend 5 saniyede bir yoklar (yol haritası 2.2.4).

    Bu uç KASITLI olarak veritabanına dokunmaz: frontend onu açık her sekmede 5 sn'de
    bir çağırıyor, yani buraya bir DB sorgusu eklemek sekme sayısıyla çarpılan bir yük
    yaratır (10.000 eşzamanlı sekme ≈ 2.000 sorgu/sn) ve 10 bağlantılık havuzu tek
    başına tüketir. Bağımlılık kontrolü için `/health/deep` kullanılır.

    `saas_mode`: frontend'in giriş ekranı gösterip göstermeyeceğine karar vermesi için
    (DATABASE_URL doluysa True — bkz. KARAR-SAAS-GECISI.md, src/config.py `Settings.saas_mode`).
    """
    return {
        "status": "ok",
        "app": "stuhub-backend",
        "version": APP_VERSION,
        "saas_mode": settings.saas_mode,
    }


@app.get("/health/deep")
async def health_deep() -> JSONResponse:
    """Bağımlılık kontrollü sağlık — yalnızca uptime monitörü/operatör içindir.

    Frontend bunu YOKLAMAZ (bkz. `/health`). Veritabanına gerçek bir sorgu atar ve
    LLM sağlayıcı zincirinin kaçının kullanılabilir olduğunu bildirir. DB erişilemezse
    503 döner ki uptime monitörü gerçekten "ayakta ama kullanılamaz" durumu görsün.
    """
    checks: dict[str, object] = {"app": "stuhub-backend", "version": APP_VERSION}
    healthy = True

    try:
        db = await get_db()
        try:
            await db.execute("SELECT 1")
        finally:
            await db.close()
        checks["database"] = "ok"
    except Exception as exc:
        healthy = False
        # Bağlantı dizesi/kimlik bilgisi sızmasın diye yalnızca hata TÜRÜ raporlanır.
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        providers = await llm_service._available_providers()
        checks["llm_providers_available"] = len(providers)
        if not providers:
            # Üretim çalışmaz ama uygulama ayakta — 503 değil, uyarı olarak bildirilir.
            checks["llm"] = "no provider configured or all in cooldown"
    except Exception as exc:
        checks["llm"] = f"error: {type(exc).__name__}"

    checks["status"] = "ok" if healthy else "degraded"
    return JSONResponse(checks, status_code=200 if healthy else 503)


# ── Üretim modu: inşa edilmiş SPA'yi servis et ─────────────────────────
# dist yoksa (geliştirme) yalnızca API çalışır; frontend Vite dev sunucusundan gelir.

if INDEX_HTML.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def root_spa():
        return FileResponse(INDEX_HTML)

    # v2 PWA: service worker + manifest — catch-all SPA fallback'ten ÖNCE kaydedilir
    if SW_FILE.exists():

        @app.get("/sw.js", include_in_schema=False)
        async def sw_js():
            return FileResponse(SW_FILE, media_type="application/javascript")

    if MANIFEST_FILE.exists():

        @app.get("/manifest.webmanifest", include_in_schema=False)
        async def web_manifest():
            return FileResponse(MANIFEST_FILE, media_type="application/manifest+json")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback: dist'te gerçek dosya varsa onu, yoksa index.html döner."""
        if full_path.startswith(("api/", "health")):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        # dist kökündeki/altındaki gerçek dosyalar (registerSW.js, workbox-*.js, icon.svg,
        # fonts/*.ttf) burada koşulsuz index.html'e dönüyordu: tarayıcı JS yerine HTML alıp
        # service worker'ı kaydetmiyordu (2026-09-10'da prod'da doğrulandı). `sw.js` ve
        # `manifest.webmanifest` açık rotaları yalnızca o iki dosyayı kurtarıyordu.
        # Dosya varsa MIME `mimetypes` ile (bilinmeyenler için STATIC_MEDIA_TYPES ile) verilir;
        # resolve() sonrası dist altında kalma şartı path traversal'ı kapatır.
        candidate = (FRONTEND_DIST / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
            media_type = STATIC_MEDIA_TYPES.get(
                candidate.suffix.lower()
            ) or mimetypes.guess_type(candidate.name)[0]
            return FileResponse(candidate, media_type=media_type)
        return FileResponse(INDEX_HTML)

else:
    # dist yok (API-only: yerel dev'de frontend hiç build edilmemiş, ya da gelecekte
    # Aşama 2'nin API/worker imaj ayrımı) — SPA servis edilemez, ama kök yine de bir
    # yanıt vermeli. Bu dal önceden yoktu ve GET / bu modda sessizce 404 dönüyordu;
    # yalnızca yerel geliştirmede `dist/` her zaman build edilmiş olduğu için hiç
    # görünmemişti — backend'in kendi CI job'u (frontend build etmiyor) yakaladı.
    @app.get("/", include_in_schema=False)
    async def root_api_only() -> JSONResponse:
        return JSONResponse({"app": "stuhub-backend", "version": APP_VERSION})
