"""Anki (.apkg) + CSV dışa aktarma testleri (Yetenek 12)."""

from __future__ import annotations

import csv
import io
import sqlite3
import zipfile

import pytest

from src.services.anki_export import build_apkg, flashcards_to_csv, validate_apkg

CARDS = [
    {"front": "Fosfolipid çift katman nedir?", "back": "Seçici geçirgen bariyer."},
    {"front": "SM-2 nedir?", "back": "Uzamsal tekrar algoritması."},
    {"front": "LanceDB ne işe yarar?", "back": "Yerel vektör depolama."},
]


def _open_collection(data: bytes) -> sqlite3.Connection:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert "collection.anki2" in archive.namelist()
        assert "media" in archive.namelist()
        raw = archive.read("collection.anki2")
    conn = sqlite3.connect(":memory:")
    conn.executescript(raw.decode("utf-8"))
    return conn


def test_build_and_validate_apkg():
    data = build_apkg("StuHub::Veri Yapıları", CARDS)
    validate_apkg(data, len(CARDS))  # hata fırlatmamalı

    conn = _open_collection(data)
    try:
        count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert count == len(CARDS)
        card_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        assert card_count == len(CARDS)
        first = conn.execute("SELECT flds FROM notes ORDER BY id LIMIT 1").fetchone()[0]
        assert "Fosfolipid" in first and "Seçici" in first
        deck = conn.execute("SELECT decks FROM col WHERE id = 1").fetchone()[0]
        assert "StuHub::Veri Yapıları" in deck
    finally:
        conn.close()


def test_empty_deck_raises():
    with pytest.raises(ValueError):
        build_apkg("StuHub::X", [])


def test_validate_rejects_wrong_count():
    data = build_apkg("StuHub::X", CARDS)
    with pytest.raises(ValueError):
        validate_apkg(data, 99)


def test_validate_rejects_garbage():
    with pytest.raises(ValueError):
        validate_apkg(b"bu bir apkg degil", 1)


def test_csv_has_bom_and_columns():
    raw = flashcards_to_csv(
        [
            {
                "front": "Soru;1",
                "back": "Cevap 1",
                "topic": "Konu",
                "citations": [{"page": 41}],
            }
        ]
    )
    text = raw.decode("utf-8-sig")
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    lines = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert lines[0] == ["front", "back", "topic", "citation"]
    assert lines[1][0] == "Soru;1"  # noktalı virgül alıntılanmış
    assert lines[1][3] == "41"
