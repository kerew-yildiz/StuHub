"""StuHub DS — FastAPI giriş noktası (Faz 0.3 + worker + üretim statik servis)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
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
        """SPA fallback: API dışındaki yollar index.html'e düşer."""
        if full_path.startswith(("api/", "health")):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        return FileResponse(INDEX_HTML)
