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
from typing import cast

import aiosqlite
import asyncpg

from .config import settings
from .pg_compat import PgConnection

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
PG_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema_postgres.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "migrations"

# Şema uygulaması için advisory lock anahtarı (rastgele sabit). Aynı anda açılan iki
# instance DDL'i paralel çalıştırırsa Postgres `CREATE TABLE IF NOT EXISTS`ta bile
# "duplicate key value violates unique constraint pg_type_typname_nsp_index" ile
# patlayabiliyor; kilit, rolling deploy'da bir anda yalnızca birinin girmesini sağlar.
_PG_SCHEMA_LOCK_KEY = 8471203

_MIGRATION_NAME_RE = re.compile(r"^(\d{3,})_(.+)\.sql$")

# SaaS modunda (settings.saas_mode) tekil havuz — get_db() her çağrıda oluşturmaz,
# yalnızca alır/serbest bırakır (asyncpg bağlantı açma maliyeti aiosqlite'tan yüksektir).
#
# min_size=3: tipik bir sayfa yüklemesi 5-6 sorguyu paralel ateşler (ör. CoursePage
# `Promise.all`); havuz `min_size=1` iken bu patlama her seferinde eksik bağlantıları
# TALEP ANINDA açıyordu — Supabase'e her yeni bağlantı TLS handshake'i ~250-900ms
# sürüyor (ölçüldü, 2026-09-05 perf turu), yani ısınmamış havuzla bir sayfa yüklemesi
# ~900ms+ oluyordu. Havuz `init_db()` içinde açılışta (kullanıcı beklemeden) kısmen
# ısıtılınca aynı sayfa yüklemesi ~265ms'e iniyor (yalnızca ağ gecikmesi kalıyor,
# LLM'siz). 3 seçildi (5 değil): Supabase session pooler toplam istemciyi 15 ile
# sınırlıyor (canlı ölçümde görüldü) — `max_size=10` zaten üst sınırı koruyor, `min_size`
# çok yüksek olursa Supabase Studio/diğer istemcilere yer kalmaz.
_pg_pool: asyncpg.Pool | None = None


async def _get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=3,
            max_size=10,
            # Ağ kesintisinde (ör. pooler'a "no route to host") sorgu sonsuza kadar
            # asılı kalmasın — canlı testte görüldü, saatlerce sessizce donan bir
            # indeksleme işi tespit edildi. Bozuk bağlantılar da periyodik geri
            # dönüştürülür (zombie connection birikimini önler).
            command_timeout=60,
            max_inactive_connection_lifetime=300,
        )
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


async def apply_pg_schema(conn: asyncpg.Connection) -> None:
    """Postgres şemasını açılışta uygular (`schema_postgres.sql` idempotenttir).

    Neden ayrı bir migration çatısı yok: PG şema dosyasının TAMAMI zaten idempotent
    (26/26 `CREATE TABLE IF NOT EXISTS`, 22/22 `CREATE INDEX IF NOT EXISTS`, policy'ler
    `DROP`+`CREATE`, seed `ON CONFLICT DO NOTHING`), yani hedef durumu her açılışta
    yeniden ilan etmek güvenli. Bu, şemanın Supabase SQL Editor'a elle yapıştırılması
    zorunluluğunu kaldırır — elle uygulama unutulursa deploy sessizce eksik tabloyla
    çalışıyordu.

    SINIR: yalnızca EKLEMELİ değişiklikleri taşır. Kolon yeniden adlandırma, tip
    daraltma veya veri backfill'i gerektiğinde numaralı bir PG migration listesi
    (SQLite'taki `_apply_migrations` muadili) gerekir; o güne kadar bu yeterli.
    """
    # DDL'i tek instance çalıştırsın: rolling deploy'da eski ve yeni process bir süre
    # birlikte yaşıyor ve paralel DDL, `IF NOT EXISTS` kullanılsa bile Postgres'te
    # katalog yarışına (pg_type_typname_nsp_index) düşebiliyor.
    await conn.execute("SELECT pg_advisory_lock($1)", _PG_SCHEMA_LOCK_KEY)
    try:
        await conn.execute(PG_SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", _PG_SCHEMA_LOCK_KEY)
    logger.info("Postgres şeması uygulandı")


async def init_db() -> None:
    """Yerel modda (SQLite): veri dizinini oluşturur, şemayı + migration'ları uygular.

    SaaS modunda (settings.saas_mode): şema her açılışta `apply_pg_schema` ile
    yeniden ilan edilir (idempotent — bkz. o fonksiyonun docstring'i).
    """
    if settings.saas_mode:
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            await apply_pg_schema(conn)
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

        # `pool.acquire()` bir `PoolConnectionProxy` döner; proxy `Connection` arayüzünü
        # devreder ama tip olarak onun alt sınıfı değildir.
        return PgConnection(cast("asyncpg.Connection", raw), _release)
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    return conn

