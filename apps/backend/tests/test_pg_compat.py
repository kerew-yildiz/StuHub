"""`pg_compat` testleri — SQL çevirisi ve işlem (transaction) yaşam döngüsü.

Bu ortamda Postgres/Docker yok; testler asyncpg arayüzünü taklit eden bir sahte
bağlantı kullanır. Amaç, sarmalayıcının asyncpg'yi DOĞRU SIRAYLA çağırdığını
doğrulamak — sunucu davranışını değil. Gerçek Postgres'e karşı doğrulama staging
deploy'unda yapılmalıdır (bkz. yol haritası Aşama 3).

Kapsam özellikle işlem semantiği: `commit()` eskiden hiçbir şey yapmayan bir
saplamaydı, yani SaaS yolunda çok adımlı işlemler atomik değildi.
"""

from typing import Any, cast

import pytest

from src.pg_compat import PgConnection, _translate_placeholders


class FakeTransaction:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.started = False
        self.finished: str | None = None

    async def start(self) -> None:
        self.started = True
        self._log.append("BEGIN")

    async def commit(self) -> None:
        self.finished = "commit"
        self._log.append("COMMIT")

    async def rollback(self) -> None:
        self.finished = "rollback"
        self._log.append("ROLLBACK")


class FakeConnection:
    """asyncpg.Connection'ın kullanılan yüzeyi: execute/fetch/fetchrow/transaction."""

    def __init__(self, fetchrow_result=None, fetch_result=None) -> None:
        self.log: list[str] = []
        self.transactions: list[FakeTransaction] = []
        self._fetchrow_result = fetchrow_result
        self._fetch_result = fetch_result or []

    def transaction(self) -> FakeTransaction:
        tx = FakeTransaction(self.log)
        self.transactions.append(tx)
        return tx

    async def execute(self, sql: str, *params):
        self.log.append(f"EXEC {sql.split()[0].upper()}")
        return "UPDATE 1"

    async def fetch(self, sql: str, *params):
        self.log.append("FETCH")
        return self._fetch_result

    async def fetchrow(self, sql: str, *params):
        self.log.append("FETCHROW")
        return self._fetchrow_result


def _make_conn(**kwargs) -> tuple[PgConnection, FakeConnection, list[bool]]:
    raw = FakeConnection(**kwargs)
    released: list[bool] = []

    async def release() -> None:
        released.append(True)

    # `raw` bilerek gerçek bir asyncpg.Connection değil — bu testlerin amacı
    # sarmalayıcının asyncpg'yi doğru sırayla çağırmasını doğrulamak.
    return PgConnection(cast(Any, raw), release), raw, released


# ── İşlem yaşam döngüsü ────────────────────────────────────────────────────


async def test_select_does_not_open_transaction():
    """Salt-okunur istek işlem açmamalı (gereksiz snapshot/kilit maliyeti)."""
    conn, raw, _ = _make_conn(fetch_result=[])
    await conn.execute("SELECT 1 FROM courses WHERE id = ?", (1,))
    assert raw.transactions == []
    assert "BEGIN" not in raw.log


async def test_write_opens_transaction_and_commit_commits():
    conn, raw, _ = _make_conn(fetchrow_result=None)
    await conn.execute("UPDATE courses SET name = ? WHERE id = ?", ("x", 1))
    assert len(raw.transactions) == 1
    assert raw.transactions[0].started
    await conn.commit()
    assert raw.transactions[0].finished == "commit"
    assert raw.log.count("BEGIN") == 1
    assert raw.log.count("COMMIT") == 1


async def test_multiple_writes_share_one_transaction():
    """Çok adımlı işlem tek bir transaction içinde olmalı — atomiklik budur."""
    conn, raw, _ = _make_conn()
    await conn.execute("DELETE FROM materials WHERE id = ?", (1,))
    await conn.execute("DELETE FROM notes WHERE material_id = ?", (1,))
    await conn.execute("UPDATE courses SET name = ? WHERE id = ?", ("x", 1))
    assert len(raw.transactions) == 1
    assert raw.log.count("BEGIN") == 1


async def test_close_without_commit_rolls_back():
    """Commit edilmemiş yazım kapanışta geri alınmalı — kısmi yazım kalmaz.

    Eski davranışta (autocommit + no-op commit) bu yazım kalıcı oluyordu.
    """
    conn, raw, released = _make_conn()
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))
    await conn.close()
    assert raw.transactions[0].finished == "rollback"
    assert released == [True]


async def test_close_after_commit_does_not_roll_back():
    conn, raw, released = _make_conn()
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))
    await conn.commit()
    await conn.close()
    assert raw.transactions[0].finished == "commit"
    assert raw.log.count("ROLLBACK") == 0
    assert released == [True]


async def test_write_after_commit_starts_new_transaction():
    conn, raw, _ = _make_conn()
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))
    await conn.commit()
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("y",))
    await conn.commit()
    assert len(raw.transactions) == 2
    assert [t.finished for t in raw.transactions] == ["commit", "commit"]


async def test_close_is_released_even_on_readonly_path():
    conn, raw, released = _make_conn(fetch_result=[])
    await conn.execute("SELECT 1")
    await conn.close()
    assert released == [True]
    assert "ROLLBACK" not in raw.log


async def test_explicit_rollback():
    conn, raw, _ = _make_conn()
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))
    await conn.rollback()
    assert raw.transactions[0].finished == "rollback"
    # Geri alma sonrası yeni yazım yeni işlem açar.
    await conn.execute("INSERT INTO courses (name) VALUES (?)", ("y",))
    assert len(raw.transactions) == 2


async def test_partial_failure_leaves_nothing_committed():
    """İkinci yazımda hata fırlayan akış hiçbir satır bırakmamalı.

    Yol haritası Aşama 0-3'ün kabul kriteri: `finally: await db.close()` kalıbı
    ile hata yolunda işlem geri alınır.
    """
    conn, raw, _ = _make_conn()

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        try:
            await conn.execute("DELETE FROM materials WHERE id = ?", (1,))
            raise Boom()
        finally:
            await conn.close()

    assert raw.transactions[0].finished == "rollback"
    assert "COMMIT" not in raw.log


# ── SQL çevirisi (mevcut davranışın regresyon koruması) ────────────────────


def test_placeholder_translation():
    assert _translate_placeholders("SELECT * FROM t WHERE a = ? AND b = ?") == (
        "SELECT * FROM t WHERE a = $1 AND b = $2"
    )


def test_placeholder_translation_ignores_question_mark_in_string_literal():
    sql = "SELECT * FROM t WHERE a = ? AND note = 'neden? bilinmiyor'"
    assert _translate_placeholders(sql) == (
        "SELECT * FROM t WHERE a = $1 AND note = 'neden? bilinmiyor'"
    )


async def test_insert_gets_returning_id_and_exposes_lastrowid():
    conn, raw, _ = _make_conn(fetchrow_result={"id": 42})
    cursor = await conn.execute("INSERT INTO courses (name) VALUES (?)", ("x",))
    assert cursor.lastrowid == 42
    assert "FETCHROW" in raw.log
