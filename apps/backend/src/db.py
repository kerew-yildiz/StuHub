"""SQLite (aiosqlite) erişim katmanı (Faz 0.2/0.3 + v2 migration runner).

- `schema.sql` yeni kurulumların tek doğruluk kaynağıdır (idempotent).
- Mevcut kurulumlar `sql/migrations/NNN_*.sql` dosyalarını sırayla işler;
  uygulananlar `schema_migrations` tablosuna kaydedilir (politika: sql/migrations/README.md).
- Migration dosyaları idempotent yazılır: taze kurulumda schema.sql hedef duruma
  zaten ulaştığından "duplicate column name" hatası beklenir ve hoş görülür.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import aiosqlite
import asyncpg

from .config import settings
from .pg_compat import PgConnection

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "migrations"

_MIGRATION_NAME_RE = re.compile(r"^(\d{3,})_(.+)\.sql$")

# SaaS modunda (settings.saas_mode) tekil havuz — get_db() her çağrıda oluşturmaz,
# yalnızca alır/serbest bırakır (asyncpg bağlantı açma maliyeti aiosqlite'tan yüksektir).
_pg_pool: asyncpg.Pool | None = None


async def _get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    return _pg_pool


def _split_sql(script: str) -> list[str]:
    """SQL betiğini tek tek çalıştırılabilir ifadelere böler (yorum satırları atlanır).

    `sqlite3.complete_statement` ile bölme — string içindeki ';' karakterleri
    ifadeyi yanlış bölmez.
    """
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer += line + "\n"
        if sqlite3.complete_statement(buffer.strip()):
            statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        statements.append(buffer.strip())
    return statements


async def _apply_migrations(db: aiosqlite.Connection) -> int:
    """Uygulanmamış migration'ları sırayla işler; uygulanan sayısını döner."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    await db.commit()
    cursor = await db.execute("SELECT version FROM schema_migrations")
    applied = {row["version"] for row in await cursor.fetchall()}

    applied_count = 0
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _MIGRATION_NAME_RE.match(path.name)
        if match is None:
            continue
        version = int(match.group(1))
        name = match.group(2)
        if version in applied:
            continue
        for statement in _split_sql(path.read_text(encoding="utf-8")):
            try:
                await db.execute(statement)
            except sqlite3.OperationalError as exc:
                # Taze kurulumda schema.sql hedef durumu zaten içerir;
                # idempotent migration'ın tekrar denemesi bu hatayı verir.
                if "duplicate column name" not in str(exc).lower():
                    raise
        await db.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        await db.commit()
        logger.info("migration uygulandı: %s (%s)", version, name)
        applied_count += 1
    return applied_count


async def init_db() -> None:
    """Yerel modda (SQLite): veri dizinini oluşturur, şemayı + migration'ları uygular.

    SaaS modunda (settings.saas_mode): şema Supabase SQL Editor'da elle uygulanır
    (bkz. sql/schema_postgres.sql) — burada yalnızca havuz bağlantısı doğrulanır.
    """
    if settings.saas_mode:
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        await db.commit()
        await _apply_migrations(db)


async def get_db() -> aiosqlite.Connection | PgConnection:
    """Yeni bir bağlantı döner (SaaS modunda havuzdan alınır); zorunlu pragmaları uygular.

    Not: Bağlantı tam hazır (thread başlamış) döner; kullanan taraf
    `await db.close()` ile kapatır. `async with conn` YENİDEN başlatmayı
    dener ve aiosqlite'te "threads can only be started once" hatası verir.
    """
    if settings.saas_mode:
        pool = await _get_pg_pool()
        raw = await pool.acquire()

        async def _release() -> None:
            await pool.release(raw)

        return PgConnection(raw, _release)
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    return conn

