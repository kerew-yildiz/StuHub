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
# `mimetypes` bu uzantıları platforma göre yanlış/hiç tahmin ediyor: `.webmanifest`
# tabloda yok, `.js` ise Windows'ta registry'den `text/plain` gelebiliyor — ikisi de
# tarayıcının dosyayı reddetmesine yeter. Bu üçü açıkça sabitlenir, gerisi tahmine kalır.
_STATIC_MEDIA_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".webmanifest": "application/manifest+json",
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

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback: dist kökündeki GERÇEK dosyalar servis edilir, kalanı index.html.

        Önceden yalnızca `sw.js` ve `manifest.webmanifest` için açık rota vardı; dist
        kökündeki diğer dosyalar (`registerSW.js`, `workbox-*.js`, `icon.svg`, ileride
        `robots.txt`/`favicon.*`) buraya düşüp index.html alıyordu. Tarayıcı
        `registerSW.js`'i JS diye çalıştırınca `Unexpected token '<'` veriyor ve PWA
        tamamen kırılıyordu; manifest ikonu da "geçersiz görsel" oluyordu (prod'da
        doğrulandı: iki dosya da 200 + `text/html`, 758 bayt `<!doctype html>`).
        Dosya adı listelemek yerine varlık kontrolü yapılır — yeni bir build çıktısı
        eklendiğinde bug tekrar etmesin.
        """
        if full_path.startswith(("api/", "health")):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)

        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            # Yol geçişi koruması: `../../etc/passwd` gibi istekler dist dışına çıkmamalı.
            if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
                return FileResponse(candidate, media_type=_STATIC_MEDIA_TYPES.get(candidate.suffix))

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
