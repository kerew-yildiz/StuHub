"""`db.py` testleri — Postgres şema uygulaması (`apply_pg_schema`).

Bu ortamda Postgres yok; asyncpg'nin kullanılan yüzeyini taklit eden sahte bir
bağlantı ile SIRA doğrulanır (advisory lock → şema → unlock), sunucu davranışı değil.
`test_pg_compat.py`'deki FakeConnection deseniyle tutarlı. `asyncio_mode = "auto"`
(pyproject.toml) sayesinde `async def test_*` otomatik toplanır, işaretleyici gerekmez.
"""

from __future__ import annotations

import pytest

from src import db


class FakeConn:
    def __init__(self) -> None:
        self.log: list[tuple[str, tuple]] = []

    async def execute(self, sql: str, *params):
        self.log.append((sql, params))
        return "OK"


class FailingFakeConn(FakeConn):
    async def execute(self, sql: str, *params):
        await super().execute(sql, *params)
        if sql.startswith("CREATE EXTENSION"):
            raise RuntimeError("şema hatası")
        return "OK"


class _StubPath:
    """`Path.read_text` yüzeyini taklit eden minimal sahte — gerçek dosyaya dokunmaz."""

    def __init__(self, content: str) -> None:
        self._content = content

    def read_text(self, encoding: str) -> str:  # noqa: ARG002
        return self._content


async def test_apply_pg_schema_kilit_sema_kilit_acma_sirasinda(monkeypatch):
    """Advisory lock şemadan ÖNCE alınır, unlock en sonda çalışır — tam olarak 3 çağrı."""
    conn = FakeConn()
    monkeypatch.setattr(db, "PG_SCHEMA_PATH", _StubPath("CREATE TABLE IF NOT EXISTS x (id int);"))

    await db.apply_pg_schema(conn)

    calls = [c[0] for c in conn.log]
    assert calls == [
        "SELECT pg_advisory_lock($1)",
        "CREATE TABLE IF NOT EXISTS x (id int);",
        "SELECT pg_advisory_unlock($1)",
    ]
    assert conn.log[0][1] == (db._PG_SCHEMA_LOCK_KEY,)
    assert conn.log[-1][1] == (db._PG_SCHEMA_LOCK_KEY,)


async def test_apply_pg_schema_hata_olsa_bile_kilidi_birakir(monkeypatch):
    """Şema uygulaması patlarsa advisory lock yine de serbest bırakılmalı.

    Aksi halde bir sonraki deploy denemesi kilitte sonsuza kadar bekler — tek bir
    bozuk şema değişikliği tüm gelecekteki açılışları kilitleyebilir.
    """
    conn = FailingFakeConn()
    monkeypatch.setattr(db, "PG_SCHEMA_PATH", _StubPath("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

    with pytest.raises(RuntimeError, match="şema hatası"):
        await db.apply_pg_schema(conn)

    calls = [c[0] for c in conn.log]
    assert calls[0] == "SELECT pg_advisory_lock($1)"
    assert calls[-1] == "SELECT pg_advisory_unlock($1)"
