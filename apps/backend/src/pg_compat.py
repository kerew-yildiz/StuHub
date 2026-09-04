"""aiosqlite-uyumlu ince Postgres (asyncpg) sarmalayıcı.

Amaç: 16 router + servis katmanı `db.execute(sql, params)` → `cursor.fetchone()` /
`fetchall()` / `.rowcount` / `.lastrowid` kalıbını aiosqlite ile birebir kullanıyor
(bkz. routers/courses.py, routers/terms.py). Bu sarmalayıcı aynı arayüzü asyncpg
üzerinde taklit eder ki iş mantığı satırları DEĞİL, yalnızca tenant_id filtreleri
eklensin — sürücü değişimi router kodunu kırmasın.

Çeviriler:
- `?` pozisyonel parametreler → asyncpg'nin `$1, $2, ...` biçimine dönüştürülür
  (tırnaklı string literaller korunur, içindeki `?` karakterine dokunulmaz).
- `INSERT INTO ...` ifadelerine (zaten `RETURNING` yoksa) `RETURNING id` eklenir;
  dönen id `cursor.lastrowid` olarak sunulur (Postgres'te `lastrowid` yoktur).
- `UPDATE` / `DELETE` sonucu asyncpg `"UPDATE 3"` / `"DELETE 1"` durum etiketi döner;
  sondaki sayı `cursor.rowcount` olarak ayrıştırılır.
- Satırlar `asyncpg.Record` — `dict(record)` mapping protokolüyle çalışır, aiosqlite.Row
  ile aynı `dict(row)` kullanım şeklini korur.

Sınır: gerçek bir Postgres sunucusuna karşı bu modül CI'da doğrulanamadı (bu ortamda
Postgres/Docker yok). SQLite yolu (aiosqlite, db.py) testlerle doğrulanır; bu modülün
asyncpg API kullanımı asyncpg'nin belgelenmiş, kararlı arayüzüne dayanır. Canlı doğrulama
Supabase projesi kurulduktan sonra yapılmalı (bkz. KULLANIM-SAAS.md).
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import date, datetime

import asyncpg

_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)
_STATUS_TAG_RE = re.compile(r"^(\w+)\s*(\d+)?", re.IGNORECASE)


class _Row:
    """asyncpg.Record'a benzer, ama `datetime`/`date` değerleri ISO string'e çevrilmiş satır.

    SQLite'ta (aiosqlite) `TIMESTAMP` kolonları zaten TEXT olarak saklanır/dönülür —
    Pydantic modelleri (`TermOut.created_at: str` gibi) bunu varsayar. Postgres/asyncpg
    ise gerçek `datetime`/`date` nesnesi döner; dönüştürülmezse `pydantic.ValidationError`
    fırlar (bkz. routers/terms.py `TermOut`).

    Router/servis kodu hem `dict(row)` / `row["kolon"]` (mapping) hem de `for a, b in row`
    (sıralı sequence — `aiosqlite.Row` ve `asyncpg.Record`'un ortak, tuple'a benzer
    davranışı, bkz. routers/settings.py `for key, value in rows`) kalıplarını kullanıyor.
    Düz `dict`'e çevirmek ikincisini kırar (dict iterasyonu anahtar döner, değer değil) —
    bu sınıf ikisini de doğru destekler.
    """

    __slots__ = ("_keys", "_values")

    def __init__(self, record: asyncpg.Record) -> None:
        self._keys = list(record.keys())
        self._values = tuple(
            v.isoformat() if isinstance(v, datetime | date) else v for v in record.values()
        )

    def keys(self) -> list[str]:
        return self._keys

    def __getitem__(self, key: str | int):
        if isinstance(key, str):
            return self._values[self._keys.index(key)]
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _translate_placeholders(sql: str) -> str:
    """`?` pozisyonel parametreleri `$1, $2, ...` biçimine çevirir (tırnak-farkında)."""
    out: list[str] = []
    n = 0
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "?" and not in_single and not in_double:
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


class PgCursor:
    """`aiosqlite` cursor arayüzünü taklit eder."""

    def __init__(self, rows: list[asyncpg.Record], rowcount: int, lastrowid: int | None):
        self._rows = rows
        self._pos = 0
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    async def fetchone(self) -> _Row | None:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return _Row(row)

    async def fetchall(self) -> list[_Row]:
        rows = self._rows[self._pos :]
        self._pos = len(self._rows)
        return [_Row(r) for r in rows]


class PgConnection:
    """`aiosqlite.Connection` arayüzünü taklit eden asyncpg tekil-bağlantı sarmalayıcısı.

    Not: aiosqlite gibi her istekte yeni bağlantı açılır (bkz. db.py `get_db()`).
    Üretimde havuzlama `asyncpg.create_pool()` ile `db.py` seviyesinde yapılır;
    bu sınıf tek bir alınmış havuz bağlantısını sarmalar.
    """

    def __init__(self, raw: asyncpg.Connection, release: Callable[[], Awaitable[None]]):
        self._raw = raw
        self._release = release

    async def execute(self, sql: str, params: tuple = ()) -> PgCursor:
        translated = _translate_placeholders(sql)
        is_insert = _INSERT_RE.match(translated) is not None
        has_returning = _RETURNING_RE.search(translated) is not None

        if is_insert and not has_returning:
            attempt = translated.rstrip().rstrip(";") + " RETURNING id"
            try:
                row = await self._raw.fetchrow(attempt, *params)
            except asyncpg.exceptions.UndefinedColumnError:
                # Hedef tablonun `id` kolonu yok (ör. `settings`: PK `key`) — lastrowid
                # zaten kullanılmayacak, düz INSERT/UPSERT olarak çalıştır.
                status = await self._raw.execute(translated, *params)
                match = _STATUS_TAG_RE.match(status or "")
                rowcount = int(match.group(2)) if match and match.group(2) else 0
                return PgCursor(rows=[], rowcount=rowcount, lastrowid=None)
            lastrowid = row["id"] if row else None
            return PgCursor(rows=[row] if row else [], rowcount=1 if row else 0, lastrowid=lastrowid)

        if translated.lstrip()[:6].upper() == "SELECT":
            rows = await self._raw.fetch(translated, *params)
            return PgCursor(rows=list(rows), rowcount=len(rows), lastrowid=None)

        status = await self._raw.execute(translated, *params)
        match = _STATUS_TAG_RE.match(status or "")
        rowcount = int(match.group(2)) if match and match.group(2) else 0
        return PgCursor(rows=[], rowcount=rowcount, lastrowid=None)

    async def executescript(self, script: str) -> None:
        await self._raw.execute(script)

    async def commit(self) -> None:
        """asyncpg autocommit modundadır (açık işlem kullanılmıyor) — no-op, aiosqlite API uyumu için."""

    async def close(self) -> None:
        await self._release()
