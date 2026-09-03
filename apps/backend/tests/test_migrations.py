"""Migration runner testleri (Faz V2.0 — Niş Analizi Entegrasyonu).

Kapsam: taze kurulum şeması, eski kurulumdan veri koruyarak yükseltme,
idempotent yeniden çalıştırma.
"""

from __future__ import annotations

import aiosqlite

from src.config import settings
from src.db import init_db

V2_TABLES = (
    "flashcard_sets",
    "card_reviews",
    "chat_messages",
    "study_guides",
    "essay_submissions",
    "activity_log",
    "schema_migrations",
)


async def test_fresh_install_creates_v2_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row["name"] for row in list(await cursor.fetchall())}

    for table in V2_TABLES:
        assert table in tables, f"{table} tablosu kurulmadı"

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT version, name FROM schema_migrations ORDER BY version")
        rows = list(await cursor.fetchall())
        assert [row["version"] for row in rows] == [1, 2, 3, 4]
        assert rows[0]["name"] == "materials_tipleri"
        assert rows[1]["name"] == "yeni_tablolar"
        assert rows[2]["name"] == "llm_provider_column"
        assert rows[3]["name"] == "tenant_id"

        cursor = await db.execute("PRAGMA table_info(indexing_jobs)")
        columns = [row["name"] for row in list(await cursor.fetchall())]
        assert "kind" in columns


async def test_upgrade_preserves_existing_data(tmp_path, monkeypatch):
    """Eski CHECK'li bir kurulum v2'ye yükseltilirken veri birebir korunmalı."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db_path = tmp_path / "stuhub.db"

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(
            """
            CREATE TABLE terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT, end_date TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
                name TEXT NOT NULL, instructor TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK (type IN ('textbook', 'slides')),
                filepath TEXT NOT NULL, extracted_text TEXT, page_count INTEGER,
                vector_ns TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE slides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                slide_no INTEGER NOT NULL, content_text TEXT
            );
            INSERT INTO terms (id, name) VALUES (1, '2026 Bahar');
            INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'Veri Yapıları');
            INSERT INTO materials (id, course_id, type, filepath)
                VALUES (1, 1, 'textbook', 'kitap.pdf');
            INSERT INTO chapters (id, course_id, title) VALUES (1, 1, 'Bağlı Listeler');
            INSERT INTO slides (id, chapter_id, material_id, slide_no, content_text)
                VALUES (1, 1, 1, 1, 'slayt metni');
            """
        )
        await db.commit()

    await init_db()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, course_id, type, filepath FROM materials")
        materials = list(await cursor.fetchall())
        assert len(materials) == 1
        assert materials[0]["type"] == "textbook"
        assert materials[0]["filepath"] == "kitap.pdf"

        cursor = await db.execute("SELECT id, slide_no, content_text FROM slides")
        slides = list(await cursor.fetchall())
        assert len(slides) == 1 and slides[0]["slide_no"] == 1

        # Yeni medya türü artık CHECK'ten geçmeli
        await db.execute(
            "INSERT INTO materials (course_id, type, filepath) "
            "VALUES (1, 'youtube', 'https://youtu.be/abc')"
        )
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) AS c FROM materials")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 2

        cursor = await db.execute("SELECT COUNT(*) AS c FROM schema_migrations")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 4


async def test_init_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await init_db()  # ikinci çalıştırma hata vermemeli, kayıtlar tekilleşmeli

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COUNT(*) AS c FROM schema_migrations")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 4

        cursor = await db.execute("SELECT COUNT(*) AS c FROM materials")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 0  # 0001'in tekrarı satır üretmemeli
