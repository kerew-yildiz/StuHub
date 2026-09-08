"""Uygulama yapılandırması — pydantic-settings tabanlı (Faz 0.3)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo kökü: apps/backend/src/config.py → üç üst dizin
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Yerel uygulama ayarları.

    - data_dir: uygulama veri dizini (SQLite + materyal deposu).
      Varsayılan <repo>/data; testler STUHUB_DATA_DIR env'iyle geçici dizine yönlendirir.
    - google_api_key / openrouter_api_key / groq_api_key / github_token: ücretsiz LLM
      sağlayıcı zinciri anahtarları (bkz. `services/llm_providers.py`) — geçici çözüm,
      Kerem ileride tek bir ücretli anahtar verecek. Asla loglanmaz, hata mesajında
      veya API yanıtında görünmez (yol haritası Bölüm 8).
    """

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    data_dir: Path = Field(default=REPO_ROOT / "data", alias="STUHUB_DATA_DIR")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    cerebras_api_key: str = Field(default="", alias="CEREBRAS_API_KEY")
    """Geçici test sağlayıcısı (Kerem kararı, 2026-09-05): Gemini/OpenRouter günlük kotası
    tükenince ve GitHub Models bakımdayken devreye giren ücretsiz yedek. Kaldırılana kadar
    `PROVIDER_CHAIN`'de kalır (bkz. Backlog.md)."""
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    embed_model: str = Field(default="", alias="STUHUB_EMBED_MODEL")

    # ── v2 (Niş Analizi Entegrasyonu) ──────────────────────────────────────
    # Yerel STT modeli (faster-whisper) — ses/YouTube transkripsiyonu (Yetenek 11)
    whisper_model: str = Field(default="small", alias="STUHUB_WHISPER_MODEL")
    # Taranmış PDF sayfaları + görsel materyaller için OCR (rapidocr, yerel)
    ocr_enabled: bool = Field(default=True, alias="STUHUB_OCR_ENABLED")
    # Not/quiz/flashcard üretim dili: tr | en | auto (Yetenek 13/15)
    not_dili: str = Field(default="tr", alias="STUHUB_NOT_DILI")
    # Streak halkası için günlük etkinlik hedefi (Yetenek 15)
    daily_goal: int = Field(default=3, alias="STUHUB_DAILY_GOAL")
    # Kitapta kaynak yokken web'den not üretimi (Yetenek 02 §web yedeği)
    web_search_enabled: bool = Field(default=True, alias="STUHUB_WEB_SEARCH_ENABLED")
    # Tek materyal yükleme üst sınırı (bayt; varsayılan 200 MB). Sınır olmadan tek bir
    # istek diski doldurabilir — SaaS'ta bu hem maliyet hem kullanılabilirlik riski.
    max_upload_bytes: int = Field(default=200 * 1024 * 1024, alias="STUHUB_MAX_UPLOAD_BYTES")
    # Aynı anda çalışacak indeksleme işi sayısı. Her iş bge-m3 batch'i işler (CPU + RAM
    # yoğun); sınırsız bırakılırsa N eşzamanlı yükleme N paralel iş başlatır ve process
    # hem thread havuzunu hem belleği tüketir. 2: küçük bir instance'ta güvenli varsayılan.
    indexer_concurrency: int = Field(default=2, alias="STUHUB_INDEXER_CONCURRENCY")
    # Feed havuzu doldurucusunun bir turda işleyeceği azami ders sayısı. Döngü tüm aktif
    # (kiracı, ders) çiftlerini SIRAYLA geziyor; sınırsızken tek bir yavaş LLM partisi
    # tüm sırayı bloklar ve birkaç yüz aktif derste tur hiç tamamlanmaz.
    feed_topup_batch: int = Field(default=20, alias="STUHUB_FEED_TOPUP_BATCH")
    # API process'i arka plan işçilerini de çalıştırsın mı. Ayrı bir worker servisi
    # (STUHUB_ROLE=worker) varsa API'de `false` yapılmalı — çifte tarama güvenlidir
    # (claim atomik + worker_id/heartbeat korumalı) ama gereksiz DB yükü yaratır.
    run_workers: bool = Field(default=True, alias="STUHUB_RUN_WORKERS")
    # SPA farklı bir origin'den (CDN/ayrı domain) servis edilirse virgülle ayrılmış
    # origin listesi. Boşsa CORS middleware hiç eklenmez — SPA backend'le aynı
    # origin'den servis edildiği sürece gerekli değildir.
    cors_origins: str = Field(default="", alias="STUHUB_CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── SaaS (KARAR-SAAS-GECISI.md) ─────────────────────────────────────────
    # Boşsa yerel/test modu: aiosqlite + auth yok (mevcut davranış korunur).
    # Doluysa (postgresql://...) SaaS modu: asyncpg + Supabase Auth zorunlu.
    database_url: str = Field(default="", alias="DATABASE_URL")
    # Supabase proje URL'i — JWKS uç noktası (`{url}/auth/v1/.well-known/jwks.json`)
    # buradan türetilir (yeni asimetrik imzalama, ES256). Frontend'le aynı env adını
    # paylaşır (VITE_SUPABASE_URL) — tek değer, tek kaynak.
    supabase_url: str = Field(default="", alias="VITE_SUPABASE_URL")
    # Eski (Legacy) HS256 paylaşılan sır — yalnızca JWKS'i olmayan eski projeler için
    # geriye dönük uyumluluk yedeği (bkz. src/auth.py).
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    # Lemon Squeezy (sandbox modunda test_mode=true) — ücretli plan checkout + webhook.
    lemonsqueezy_api_key: str = Field(default="", alias="LEMONSQUEEZY_API_KEY")
    lemonsqueezy_store_id: str = Field(default="", alias="LEMONSQUEEZY_STORE_ID")
    lemonsqueezy_webhook_secret: str = Field(default="", alias="LEMONSQUEEZY_WEBHOOK_SECRET")
    lemonsqueezy_pro_variant_id: str = Field(default="", alias="LEMONSQUEEZY_PRO_VARIANT_ID")

    @property
    def saas_mode(self) -> bool:
        return bool(self.database_url)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stuhub.db"

    @property
    def materials_dir(self) -> Path:
        return self.data_dir / "materials"


settings = Settings()
