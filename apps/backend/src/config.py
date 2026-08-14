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

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stuhub.db"

    @property
    def materials_dir(self) -> Path:
        return self.data_dir / "materials"


settings = Settings()
