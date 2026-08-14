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
    - deepseek_api_key: kullanıcının kendi anahtarı. Asla loglanmaz, hata mesajında
      veya API yanıtında görünmez (yol haritası Bölüm 8).
    """

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    data_dir: Path = Field(default=REPO_ROOT / "data", alias="STUHUB_DATA_DIR")
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model: str = Field(default="deepseek-chat", alias="STUHUB_MODEL")
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

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stuhub.db"

    @property
    def materials_dir(self) -> Path:
        return self.data_dir / "materials"


settings = Settings()
