"""Anki (.apkg) dışa aktarma — yalnızca stdlib (Yetenek 12).

Paket içeriği: `collection.anki2` (SQLite — col/notes/cards/revlog/graves)
+ `media` (JSON). Deck adı `StuHub::{Ders}`, kart tipi Basic (front/back).
Üretim sonrası açma doğrulaması yapılır; geçersiz paket üretilmez.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import time
import zipfile
import zlib

SCHEMA_VERSION = 11

_FIELDS_SEP = "\x1f"

_BASIC_CSS = (
    ".card { font-family: arial; font-size: 20px; text-align: center; "
    "color: black; background-color: white; }"
)


def _schema_statements() -> list[str]:
    return [
        "CREATE TABLE col ("
        " id integer primary key, crt integer not null, mod integer not null,"
        " scm integer not null, ver integer not null, dty integer not null,"
        " usn integer not null, ls integer not null, conf text not null,"
        " models text not null, decks text not null, dconf text not null,"
        " tags text not null)",
        "CREATE TABLE notes ("
        " id integer primary key, guid text not null, mid integer not null,"
        " mod integer not null, usn integer not null, tags text not null,"
        " flds text not null, sfld integer not null, csum integer not null,"
        " flags integer not null, data text not null)",
        "CREATE TABLE cards ("
        " id integer primary key, nid integer not null, did integer not null,"
        " ord integer not null, mod integer not null, usn integer not null,"
        " type integer not null, queue integer not null, due integer not null,"
        " ivl integer not null, factor integer not null, reps integer not null,"
        " lapses integer not null, left integer not null, odue integer not null,"
        " odid integer not null, flags integer not null, data text not null)",
        "CREATE TABLE revlog ("
        " id integer primary key, cid integer not null, usn integer not null,"
        " ease integer not null, ivl integer not null, lastIvl integer not null,"
        " factor integer not null, time integer not null, type integer not null)",
        "CREATE TABLE graves ("
        " usn integer not null, oid integer not null, type integer not null)",
    ]


def _checksum(text: str) -> int:
    """Anki uyumlu not checksum'u (genanki yaklaşımı — ilk alanın SHA1 kırpılmışı).

    Güvenlik amaçlı değil, Anki'nin dosya biçimi gereğidir (usedforsecurity=False).
    """
    return int(hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()[:8], 16)


def _basic_model(mid: int, now: int) -> dict:
    return {
        "id": mid,
        "name": "Basic",
        "type": 0,
        "mod": now,
        "usn": -1,
        "sortf": 0,
        "did": 1,
        "tmpls": [
            {
                "name": "Card 1",
                "ord": 0,
                "qfmt": "{{Front}}",
                "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
                "bqfmt": "",
                "bafmt": "",
                "did": None,
                "bfont": "",
                "bsize": 0,
            }
        ],
        "flds": [
            {
                "name": "Front",
                "ord": 0,
                "sticky": False,
                "rtl": False,
                "font": "Arial",
                "size": 20,
                "media": [],
            },
            {
                "name": "Back",
                "ord": 1,
                "sticky": False,
                "rtl": False,
                "font": "Arial",
                "size": 20,
                "media": [],
            },
        ],
        "css": _BASIC_CSS,
        "latexPre": "",
        "latexPost": "",
        "req": [[0, "any", [0]]],
    }


def _decks_json(deck_name: str, now: int) -> dict:
    return {
        "1": {
            "id": 1,
            "name": deck_name,
            "mod": now,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "collapsed": False,
            "browserCollapsed": False,
            "desc": "",
            "dyn": 0,
            "conf": 1,
            "extendNew": 10,
            "extendRev": 50,
        }
    }


def _dconf_json() -> dict:
    return {
        "1": {
            "id": 1,
            "name": "Default",
            "mod": 0,
            "usn": -1,
            "maxTaken": 60,
            "autoplay": True,
            "timer": 0,
            "replayq": True,
            "new": {
                "bury": False,
                "delays": [1, 10],
                "initialFactor": 2500,
                "ints": [1, 4, 7],
                "order": 1,
                "perDay": 20,
            },
            "rev": {
                "bury": False,
                "ease4": 1.3,
                "fuzz": 0.05,
                "ivlFct": 1,
                "maxIvl": 36500,
                "minSpace": 1,
                "perDay": 200,
            },
            "lapse": {
                "delays": [10],
                "leechAction": 0,
                "leechFails": 8,
                "minInt": 1,
                "mult": 0,
            },
            "dyn": False,
        }
    }


def _col_conf_json(mid: int) -> dict:
    return {
        "activeDecks": [1],
        "curDeck": 1,
        "newSpread": 0,
        "collapseTime": 1200,
        "timeLim": 0,
        "estTimes": True,
        "dueCounts": True,
        "curModel": str(mid),
        "nextPos": 1,
        "sortType": "noteFld",
        "sortBackwards": False,
        "addToCur": True,
        "dayLearnFirst": False,
    }


def build_apkg(deck_name: str, cards: list[dict]) -> bytes:
    """Kart listesini Anki `.apkg` baytlarına çevirir.

    cards: [{"front": str, "back": str}] — boş liste ValueError fırlatır (Yetenek 12).
    """
    if not cards:
        raise ValueError("Boş deste dışa aktarılamaz — önce flashcard oluşturun.")

    now = int(time.time())
    mid = 1_600_000_000 + (zlib.crc32(deck_name.encode("utf-8")) % 100_000_000)

    conn = sqlite3.connect(":memory:")
    try:
        for statement in _schema_statements():
            conn.execute(statement)

        conn.execute(
            "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models,"
            " decks, dconf, tags) VALUES (1, ?, ?, 0, ?, 0, -1, 0, ?, ?, ?, ?, '{}')",
            (
                now,
                now,
                SCHEMA_VERSION,
                json.dumps(_col_conf_json(mid), ensure_ascii=False),
                json.dumps({str(mid): _basic_model(mid, now)}, ensure_ascii=False),
                json.dumps(_decks_json(deck_name, now), ensure_ascii=False),
                json.dumps(_dconf_json(), ensure_ascii=False),
            ),
        )

        for index, card in enumerate(cards):
            note_id = now * 1000 + index
            card_id = now * 1000 + index + 1_000_000_000
            front = str(card["front"]).strip()
            back = str(card["back"]).strip()
            flds = f"{front}{_FIELDS_SEP}{back}"
            conn.execute(
                "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld,"
                " csum, flags, data) VALUES (?, ?, ?, ?, -1, '', ?, ?, ?, 0, '')",
                (note_id, f"StuHub{now}{index}", mid, now, flds, front, _checksum(front)),
            )
            conn.execute(
                "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due,"
                " ivl, factor, reps, lapses, left, odue, odid, flags, data)"
                " VALUES (?, ?, 1, 0, ?, -1, 0, 0, ?, 0, 0, 0, 0, 0, 0, 0, 0, '')",
                (card_id, note_id, now, index + 1),
            )
        conn.commit()
        collection_bytes = _serialize(conn)
    finally:
        conn.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("collection.anki2", collection_bytes)
        archive.writestr("media", "{}")
    return buffer.getvalue()


def _serialize(conn: sqlite3.Connection) -> bytes:
    """Bağlantıyı baytlara serileştirir (WAL/journal kalıntısı olmadan)."""
    buffer = io.BytesIO()
    for line in conn.iterdump():
        buffer.write(line.encode("utf-8"))
        buffer.write(b"\n")
    return buffer.getvalue()


def validate_apkg(data: bytes, expected_count: int) -> None:
    """Üretilen paketi yeniden açar ve şema/entegrasyonu doğrular (Yetenek 12).

    Başarısızlıkta ValueError fırlatır — geçersiz paket asla teslim edilmez.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "collection.anki2" not in names or "media" not in names:
                raise ValueError("apkg içeriği eksik")
            collection_bytes = archive.read("collection.anki2")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("apkg okunamadı") from exc

    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(collection_bytes.decode("utf-8"))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for required in ("col", "notes", "cards", "revlog", "graves"):
            if required not in tables:
                raise ValueError(f"apkg şeması eksik: {required}")
        count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        if count != expected_count or note_count != expected_count:
            raise ValueError("apkg kart sayısı uyuşmuyor")
    except sqlite3.Error as exc:
        raise ValueError("apkg veritabanı geçersiz") from exc
    finally:
        conn.close()


def flashcards_to_csv(cards: list[dict]) -> bytes:
    """Kartları Excel uyumlu CSV'ye çevirir: front;back;topic;citation (UTF-8 BOM)."""
    lines = ["front;back;topic;citation"]
    for card in cards:
        citation = "; ".join(
            str(c.get("page") or c.get("slide") or "") for c in card.get("citations", [])
        )
        row = [card.get("front", ""), card.get("back", ""), card.get("topic", ""), citation]
        lines.append(
            ";".join(f'"{cell.replace(chr(34), chr(34) + chr(34))}"' for cell in row)
        )
    return ("\ufeff" + "\r\n".join(lines)).encode("utf-8")
