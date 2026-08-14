"""StuHub DS — FastAPI giriş noktası (Faz 0.3 + worker + üretim statik servis)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import api_router
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
    """Açılışta veri dizini + şema hazırlar; arka plan indeksleyiciyi başlatır."""
    await init_db()
    await recover_stale_jobs()
    stop_event = asyncio.Event()
    worker = asyncio.create_task(worker_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        worker.cancel()


app = FastAPI(
    title="StuHub DS API",
    description="Yerel ders notu ve quiz uygulaması API'si",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Sağlık kontrolü — frontend 5 saniyede bir yoklar (yol haritası 2.2.4)."""
    return {"status": "ok", "app": "stuhub-backend", "version": APP_VERSION}


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
