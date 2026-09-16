"""K5 arşiv sorgularının büyük veri stresi (C2) — süre + sorgu sayısı + zip girdileri.

Kapsam: `build_term_archive` çok bölümlü/çok kayıtlı bir dönemde hata vermeden bitiyor,
zip BEKLENEN girdi sayısını içeriyor ve süre makul bir üst sınırın altında kalıyor.

Üst sınır türetmesi (brief gereği keyfi sabit değil): 2026-09-16 ölçümü bu dosyadaki
veri hacmiyle (10.520 satır / 40 bölüm) 0.100 sn; sınır ölçümün ~2 katı (0.20 sn) seçildi —
gerçek bir N+1/karesel davranış regresyonu bu sınırı katbekat aşar.

Sorgu sayısı iddiası: arşiv, tablo başına TEK toplu sorgu atar (satır sayısıyla
ölçeklenmez) — 40 bölümde de 8 ifade. Sınır 12, yani satır başına sorguya (N+1)
dönüş bu testi kırar.
"""

from __future__ import annotations

import io
import json
import time
import zipfile

import aiosqlite

from src.config import settings
from src.db import init_db
from src.services import archive_service
from src.services.archive_service import build_term_archive

# Veri hacmi: 40 bölüm × (200 satırlık not + 30 soruluk quiz + 25 kart + 60 satırlık
# sohbet + 20 maddelik rehber) = 10.520 satır (ölçülen değer testin print'inde).
_CHAPTERS = 40
_NOTE_LINES = 200
_QUIZ_QUESTIONS = 30
_FLASHCARDS = 25
_CHAT_LINES = 60
_GUIDE_ENTRIES = 20

# Ölçülen sürenin (~2 katı): 2026-09-16 WSL/Windows ölçümü 0.100 sn (10.520 satır,
# 40 bölüm, 203 zip girdisi) — sınır 0.20 sn. Asıl regresyon koruması sorgu sayısıdır
# (aşağıda); süre sınırı karesel/N+1 patlamayı yakalamak için var.
_MEASURED_SECONDS = 0.10
_TIME_LIMIT_SECONDS = 2 * _MEASURED_SECONDS

# Toplam `execute` çağrısı (2 dönem/ders sorgusu + 6 `_fetch_rows` toplu sorgusu).
_MEASURED_QUERIES = 8
_QUERY_LIMIT = 12


class _CountingDb:
    """`get_db()` sonucunu sarar; ifade sayısını sayar (ölçüm amaçlı)."""

    def __init__(self, db, stats: dict[str, int]) -> None:
        self._db = db
        self._stats = stats

    async def execute(self, *args):
        self._stats["queries"] += 1
        return await self._db.execute(*args)

    async def close(self) -> None:
        await self._db.close()


def _long_text(prefix: str, lines: int) -> str:
    return "\n".join(
        f"{prefix} {i}: karmaşıklık O(n log n), örnek değer {i * 7}" for i in range(lines)
    )


def _payloads(chapter_id: int) -> dict[str, str]:
    """Bir bölümün JSON/metin gövdeleri — gerçek şemaya uygun alanlarla."""
    note = _long_text(f"# Bölüm {chapter_id} notu", _NOTE_LINES)
    quiz = json.dumps(
        [
            {
                "question": f"Bölüm {chapter_id} soru {i}",
                "options": [f"seçenek {i}-{j}" for j in range(4)],
                "correct_index": i % 4,
                "explanation": "x" * 60,
            }
            for i in range(_QUIZ_QUESTIONS)
        ],
        ensure_ascii=False,
    )
    cards = json.dumps(
        [
            {"front": f"Bölüm {chapter_id} kart {i}", "back": "y" * 60}
            for i in range(_FLASHCARDS)
        ],
        ensure_ascii=False,
    )
    chat = _long_text(f"Bölüm {chapter_id} sohbet", _CHAT_LINES)
    guide = json.dumps(
        [{"heading": f"Başlık {i}", "body": "z" * 60} for i in range(_GUIDE_ENTRIES)],
        ensure_ascii=False,
    )
    return {"note": note, "quiz": quiz, "cards": cards, "chat": chat, "guide": guide}


async def _seed_big_term(db_path) -> dict[str, int]:
    """Büyük dönemi kurar; satır sayısı + beklenen zip girdisi sayısını döner."""
    texts: list[str] = []
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("INSERT INTO terms (id, name) VALUES (1, 'Stres Dönemi')")
        await db.execute(
            "INSERT INTO courses (id, term_id, name, instructor) "
            "VALUES (1, 1, 'Veri Yapıları', 'Dr. Stres')"
        )
        await db.executemany(
            "INSERT INTO chapters (id, course_id, title) VALUES (?, 1, ?)",
            [(i, f"Bölüm {i}") for i in range(1, _CHAPTERS + 1)],
        )

        notes: list[tuple[int, str]] = []
        quizzes: list[tuple[int, str]] = []
        cards: list[tuple[int, str]] = []
        chats: list[tuple[str]] = []
        guides: list[tuple[int, str]] = []
        for chapter_id in range(1, _CHAPTERS + 1):
            body = _payloads(chapter_id)
            texts.extend(body.values())
            notes.append((chapter_id, body["note"]))
            quizzes.append((chapter_id, body["quiz"]))
            cards.append((chapter_id, body["cards"]))
            chats.append((body["chat"],))
            guides.append((chapter_id, body["guide"]))

        await db.executemany(
            "INSERT INTO notes (chapter_id, content_md) VALUES (?, ?)", notes
        )
        await db.executemany(
            "INSERT INTO quizzes (chapter_id, questions_json) VALUES (?, ?)", quizzes
        )
        await db.executemany(
            "INSERT INTO flashcard_sets (course_id, chapter_id, cards_json) VALUES (1, ?, ?)",
            cards,
        )
        await db.executemany(
            "INSERT INTO chat_messages (course_id, role, content) VALUES (1, 'user', ?)",
            chats,
        )
        await db.executemany(
            "INSERT INTO study_guides (course_id, chapter_id, kind, content_json) "
            "VALUES (1, ?, 'summary', ?)",
            guides,
        )
        await db.commit()

    lines = sum(text.count("\n") + 1 for text in texts)
    # manifest + courses/1/{course,chapters}.json + bölüm başına 1 not/quiz/sohbet/rehber
    # + ders başına flashcard destesi.
    expected_entries = 1 + 2 + _CHAPTERS * 5
    return {"lines": lines, "expected_entries": expected_entries}


async def test_buyuk_donem_arsivi_hata_vermeden_tamamlanir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    seeded = await _seed_big_term(tmp_path / "stuhub.db")
    assert seeded["lines"] >= 2000, f"veri hacmi yetersiz: {seeded['lines']} satır"

    stats = {"queries": 0}
    real_get_db = archive_service.get_db

    async def _counting_get_db():
        return _CountingDb(await real_get_db(), stats)

    monkeypatch.setattr(archive_service, "get_db", _counting_get_db)

    started = time.perf_counter()
    data = await build_term_archive(1, include_files=False)
    elapsed = time.perf_counter() - started

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()

    print(
        f"\n[stres] satirlar={seeded['lines']} bolum={_CHAPTERS} girdi={len(names)} "
        f"sorgu={stats['queries']} sure={elapsed:.3f}sn zip={len(data) / 1024:.0f}KB"
    )

    assert len(names) == seeded["expected_entries"]
    assert "chapters/1/note-1.json" in names
    assert f"chapters/{_CHAPTERS}/quiz-{_CHAPTERS}.json" in names
    # Süre: 2026-09-16 ölçümü 0.082-0.100 sn; sınır ölçümün 2 katı.
    assert elapsed < _TIME_LIMIT_SECONDS, (
        f"arşiv {elapsed:.3f} sn sürdü (sınır {_TIME_LIMIT_SECONDS})"
    )
    # Satır sayısıyla ölçeklenen sorgu (N+1) regresyonu bu iddiaya takılır.
    assert stats["queries"] <= _QUERY_LIMIT, f"{stats['queries']} ifade çalıştı"


async def test_buyuk_donem_arsivi_veriyi_kayipsiz_tasir(tmp_path, monkeypatch):
    """Zip içeriği gerçekten dolu olmalı — boş/kesik JSON paketlenmesin."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_big_term(tmp_path / "stuhub.db")

    data = await build_term_archive(1, include_files=True)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        chapters = json.loads(archive.read("courses/1/chapters.json"))
        last_note = json.loads(
            archive.read(f"chapters/{_CHAPTERS}/note-{_CHAPTERS}.json")
        )

    assert manifest["term"] == "Stres Dönemi"
    assert manifest["materials_included"] is True
    assert len(chapters) == _CHAPTERS
    assert last_note["content_md"].count("\n") + 1 == _NOTE_LINES
