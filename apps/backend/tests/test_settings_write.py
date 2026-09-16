"""K1 regresyonu: `settings` yazma yolu ve pg_compat'ın savepoint'li `RETURNING id` denemesi.

Kök neden (KOK-NEDEN-K1): `settings` ve `plans` tablolarında `id` kolonu YOK. pg_compat
RETURNING'siz her INSERT'e `RETURNING id` ekliyor; Postgres hata veren ifadeden sonra
işlemi abort durumuna geçirdiği için, savepoint'siz `except` dalındaki düz INSERT
`InFailedSQLTransactionError` ile düşüyordu → `PUT /api/settings` 500 dönüyordu.

Bu ortamda Postgres/Docker yok (`test_pg_compat.py` ile aynı kısıt); testler asyncpg
arayüzünü taklit eden sahte bir bağlantı kullanır — ama sahte, Postgres'in "abort
sonrası yalnızca ROLLBACK kabul edilir" kuralını da uygular. Yani savepoint'siz eski kod
bu testleri DÜŞÜRÜR (except dalındaki ikinci execute REJECTED olur).
"""

import re
from typing import Any, cast

import asyncpg

from src.pg_compat import PgConnection

_INSERT_TARGET_RE = re.compile(r"INSERT\s+INTO\s+(\w+)", re.IGNORECASE)

# Router ve llm_service'in `settings` tablosuna yazdığı RETURNING'siz biçim —
# pg_compat'ın `RETURNING id` denemesini tetikleyen tam sorgu bu.
_SETTINGS_UPSERT_SQL = (
    "INSERT INTO settings (key, value) VALUES (?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
)


class FakeTransaction:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.finished: str | None = None

    async def start(self) -> None:
        self._log.append("BEGIN")

    async def commit(self) -> None:
        self.finished = "commit"
        self._log.append("COMMIT")

    async def rollback(self) -> None:
        self.finished = "rollback"
        self._log.append("ROLLBACK")


class AbortAwareConnection:
    """asyncpg.Connection'ın kullanılan yüzeyi + Postgres'in hata sonrası abort kuralı.

    `id` kolonu olmayan tabloya `RETURNING id` sorulursa UndefinedColumnError fırlar ve
    işlem abort durumuna geçer; savepoint'e dönülmeden sonraki hiçbir komut kabul edilmez.
    """

    def __init__(self, id_columns: frozenset[str] = frozenset()) -> None:
        self.log: list[str] = []
        self.aborted = False
        self._id_columns = id_columns

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self.log)

    async def execute(self, sql: str, *params: Any) -> str:
        self._reject_if_aborted(sql)
        words = sql.split()
        upper = sql.upper()
        if upper.startswith("SAVEPOINT"):
            self.log.append(f"EXEC SAVEPOINT {words[1]}")
            return "SAVEPOINT"
        if upper.startswith("ROLLBACK TO SAVEPOINT"):
            self.aborted = False
            self.log.append("EXEC ROLLBACK TO SAVEPOINT")
            return "ROLLBACK"
        if upper.startswith("RELEASE SAVEPOINT"):
            self.log.append("EXEC RELEASE SAVEPOINT")
            return "RELEASE"
        self.log.append(f"EXEC {words[0].upper()}")
        return "INSERT 0 1"

    async def fetchrow(self, sql: str, *params: Any):
        self._reject_if_aborted(sql)
        match = _INSERT_TARGET_RE.search(sql)
        table = match.group(1) if match else ""
        self.log.append("FETCHROW")
        if "RETURNING ID" in sql.upper() and table not in self._id_columns:
            self.aborted = True
            raise asyncpg.exceptions.UndefinedColumnError(
                f'column "id" does not exist on table "{table}"'
            )
        return {"id": 42}

    async def fetch(self, sql: str, *params: Any) -> list:
        self._reject_if_aborted(sql)
        self.log.append("FETCH")
        return []

    def _reject_if_aborted(self, sql: str) -> None:
        if self.aborted and not sql.upper().startswith(("ROLLBACK", "COMMIT")):
            self.log.append(f"REJECTED {sql.split()[0].upper()}")
            raise asyncpg.exceptions.InFailedSQLTransactionError(
                "current transaction is aborted, commands ignored until end of transaction block"
            )


def _make_conn(**kwargs: Any) -> tuple[PgConnection, AbortAwareConnection]:
    raw = AbortAwareConnection(**kwargs)

    async def release() -> None:
        return None

    # `raw` bilerek gerçek bir asyncpg.Connection değil (bkz. test_pg_compat.py).
    return PgConnection(cast(Any, raw), release), raw


async def test_id_less_insert_falls_back_without_aborting_transaction():
    """`settings` (id yok) + RETURNING'siz INSERT: savepoint'li fallback, işlem ayakta.

    İşlem içinde ÖNCE başka bir yazım var (gerçek akış: aynı transaction birden çok
    tabloya yazar) — fallback bu yazımı da bozmamalı.
    """
    conn, raw = _make_conn(id_columns=frozenset({"courses"}))

    await conn.execute("UPDATE courses SET name = ? WHERE id = ?", ("x", 1))
    cursor = await conn.execute(_SETTINGS_UPSERT_SQL, ("daily_goal", "3"))

    assert cursor.lastrowid is None
    assert raw.log.index("EXEC SAVEPOINT pgc_ret") < raw.log.index("FETCHROW")
    assert raw.log.index("FETCHROW") < raw.log.index("EXEC ROLLBACK TO SAVEPOINT")
    assert raw.log.index("EXEC ROLLBACK TO SAVEPOINT") < raw.log.index("EXEC INSERT")
    assert "REJECTED" not in raw.log

    # İşlem abort değil: sonraki yazım ve commit aynı transaction içinde çalışır.
    await conn.execute("DELETE FROM materials WHERE course_id = ?", (1,))
    await conn.commit()
    assert raw.log.count("BEGIN") == 1
    assert raw.log.count("COMMIT") == 1
    assert raw.aborted is False


async def test_returning_id_success_releases_savepoint():
    """`id` kolonu olan tabloda deneme başarılı: savepoint bırakılır, lastrowid dolar."""
    conn, raw = _make_conn(id_columns=frozenset({"courses"}))

    cursor = await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))

    assert cursor.lastrowid == 42
    assert raw.log == ["BEGIN", "EXEC SAVEPOINT pgc_ret", "FETCHROW", "EXEC RELEASE SAVEPOINT"]
    assert raw.aborted is False
    await conn.commit()
    assert raw.log.count("COMMIT") == 1


async def test_explicit_returning_skips_id_attempt_on_pg_path():
    """A düzeltmesinin sözleşmesi (router `RETURNING key` ile yazar): sorgu kendi
    RETURNING'ini taşıyorsa pg_compat `RETURNING id` denemesi yapmaz — savepoint'e hiç
    girilmez ve dönen cursor tüketilebilir olur (router commit'ten önce `fetchall()` çağırır)."""
    conn, raw = _make_conn(id_columns=frozenset({"courses"}))

    cursor = await conn.execute(_SETTINGS_UPSERT_SQL + " RETURNING key", ("daily_goal", "3"))

    assert await cursor.fetchall() == []
    await conn.commit()
    assert "FETCHROW" not in raw.log
    assert "EXEC SAVEPOINT pgc_ret" not in raw.log
    assert raw.log.count("COMMIT") == 1
