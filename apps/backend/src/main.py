"""StuHub DS — FastAPI giriş noktası (Faz 0.3 + Faz 2.2 worker)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .routers import api_router
from .workers.indexer import recover_stale_jobs, worker_loop

APP_VERSION = "0.2.0"


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


@app.get("/")
async def root() -> dict[str, str]:
    return {"app": "stuhub-backend", "version": APP_VERSION, "docs": "/docs"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Sağlık kontrolü — frontend 5 saniyede bir yoklar (yol haritası 2.2.4)."""
    return {"status": "ok", "app": "stuhub-backend", "version": APP_VERSION}
