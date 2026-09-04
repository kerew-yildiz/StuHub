"""Ortak test fixture'ları — veri dizinini geçici dizine yönlendirir."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.db import init_db
from src.main import app
from src.services.llm_providers import PROVIDER_CHAIN


@pytest.fixture(autouse=True)
def _reset_llm_provider_keys(monkeypatch):
    """`llm_service._apply_table_config` global `settings` nesnesini doğrudan mutasyona uğratır
    (monkeypatch takibi dışında) — testler arası sızıntıyı önlemek için her testte sıfırlanır.

    `database_url` de burada sıfırlanır: `.env`'de gerçek bir SaaS `DATABASE_URL` tanımlıysa
    (geliştirici makinesinde SaaS test ediliyorsa) testler yine de her zaman yerel/SQLite modda
    (`saas_mode=False`) çalışmalı — aksi halde tüm test paketi gerçek Postgres'e bağlanmaya
    çalışır, ağ üzerinden yavaşlar/asılır ve gerçek veritabanına test verisi yazar."""
    monkeypatch.setattr(settings, "database_url", "")
    for provider in PROVIDER_CHAIN:
        setattr(settings, provider.api_key_setting, "")
    yield
    for provider in PROVIDER_CHAIN:
        setattr(settings, provider.api_key_setting, "")


@pytest.fixture
async def client(tmp_path, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    """Şema uygulanmış, geçici veri dizinli test istemcisi."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
