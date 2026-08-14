"""SQLite (aiosqlite) erişim katmanı (Faz 0.2/0.3)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from .config import settings

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


async def init_db() -> None:
    """Veri dizinini oluşturur ve şemayı uygular (idempotent)."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Yeni bir bağlantı açar; zorunlu pragmaları uygular.

    Not: Bağlantı tam hazır (thread başlamış) döner; kullanan taraf
    `await db.close()` ile kapatır. `async with conn` YENİDEN başlatmayı
    dener ve aiosqlite'te "threads can only be started once" hatası verir.
    """
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    return conn
