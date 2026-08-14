"""StuHub DS — FastAPI giriş noktası (Faz 0.3)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .routers import api_router

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Uygulama açılışında veri dizini + şemayı hazırlar."""
    await init_db()
    yield


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
