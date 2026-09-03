"""Dönem arşivi export/import testleri (Yetenek 12 Format 4)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services.archive_service import (
    ARCHIVE_VERSION,
    ArchiveError,
    build_term_archive,
    import_term_archive,
)


async def _seed(tmp_path) -> int:
    """Örnek dönem kurar; dönem kimliğini döner."""
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await db.execute(
            "INSERT INTO courses (id, term_id, name, instructor) "
            "VALUES (1, 1, 'Veri Yapıları', 'Dr. A')"
        )
        await db.execute(
            "INSERT INTO chapters (id, course_id, title) VALUES (1, 1, 'Bağlı Listeler')"
        )
        await db.execute(
            "INSERT INTO notes (id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES (1, 1, '# Not\nİçerik', '{}', '[]')"
        )
        await db.execute(
            "INSERT INTO quizzes (id, chapter_id, questions_json) VALUES (1, 1, '{}')"
        )
        await db.execute(
            "INSERT INTO flashcard_sets (id, course_id, chapter_id, cards_json) "
            "VALUES (1, 1, 1, '[]')"
        )
        await db.execute(
            "INSERT INTO chat_messages (id, course_id, role, content, citations_json) "
            "VALUES (1, 1, 'user', 'soru', '[]')"
        )
        await db.execute(
            "INSERT INTO study_guides (id, course_id, chapter_id, kind, content_json) "
            "VALUES (1, 1, 1, 'summary', '{}')"
        )
        await db.commit()
    return 1


async def _count(db_path: str, table: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
        row = await cursor.fetchone()
        assert row is not None
        return row[0]


async def test_archive_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    term_id = await _seed(tmp_path)

    data = await build_term_archive(term_id, include_files=False)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["app"] == "stuhub"
        assert manifest["version"] == ARCHIVE_VERSION
        assert manifest["term"] == "2026 Bahar"
        assert manifest["courses"] == [1]
        names = set(archive.namelist())
        assert "courses/1/course.json" in names
        assert "courses/1/chapters.json" in names
        assert "chapters/1/note-1.json" in names
        assert "chapters/1/quiz-1.json" in names
        assert "courses/1/flashcards/1.json" in names

    summary = await import_term_archive(data, include_files=False)
    assert summary["term_name"] == "2026 Bahar (içe aktarıldı)"
    assert summary["courses"][0]["new_id"] != 1

    db_path = tmp_path / "stuhub.db"
    assert await _count(db_path, "terms") == 2
    assert await _count(db_path, "courses") == 2
    assert await _count(db_path, "chapters") == 2
    assert await _count(db_path, "notes") == 2
    assert await _count(db_path, "quizzes") == 2
    assert await _count(db_path, "flashcard_sets") == 2
    assert await _count(db_path, "chat_messages") == 2
    assert await _count(db_path, "study_guides") == 2

    # içe aktarılan not yeni chapter'a bağlı
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT n.chapter_id AS cid, c.title FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id WHERE n.id = 2"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[1] == "Bağlı Listeler"


async def test_import_name_conflict_gets_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    term_id = await _seed(tmp_path)

    data = await build_term_archive(term_id, include_files=False)
    summary = await import_term_archive(data, include_files=False)
    assert summary["term_name"].endswith("(içe aktarıldı)")


async def test_import_rejects_unknown_version(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    term_id = await _seed(tmp_path)
    data = await build_term_archive(term_id, include_files=False)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    manifest["version"] = 99

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(ArchiveError, match="sürüm"):
        await import_term_archive(buffer.getvalue(), include_files=False)

    # reddedilen import hiçbir şey yazmamalı
    assert await _count(tmp_path / "stuhub.db", "terms") == 1


async def test_import_rejects_garbage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    with pytest.raises(ArchiveError):
        await import_term_archive(b"zip degil", include_files=False)
    assert await _count(tmp_path / "stuhub.db", "terms") == 0


async def test_archive_with_material_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    term_id = await _seed(tmp_path)

    materials_dir = tmp_path / "materials" / "1"
    materials_dir.mkdir(parents=True)
    pdf = materials_dir / "kitap.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO materials (id, course_id, type, filepath, page_count) "
            "VALUES (1, 1, 'textbook', ?, 2)",
            (str(pdf),),
        )
        await db.commit()

    data = await build_term_archive(term_id, include_files=True)
    summary = await import_term_archive(data, include_files=True)
    assert summary["materials_imported"] == 1

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        cursor = await db.execute(
            "SELECT filepath, page_count FROM materials WHERE id = 2"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0]
        assert row[1] == 2

        # içe aktarılan dosya gerçekten diskte
        assert Path(row[0]).exists()
