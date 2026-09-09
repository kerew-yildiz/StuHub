"""Migration runner testleri (Faz V2.0 — Niş Analizi Entegrasyonu).

Kapsam: taze kurulum şeması, eski kurulumdan veri koruyarak yükseltme,
idempotent yeniden çalıştırma.
"""

from __future__ import annotations

import re
import sqlite3

import aiosqlite
import pytest

from src.config import settings
from src.db import MIGRATIONS_DIR, init_db

V2_TABLES = (
    "flashcard_sets",
    "card_reviews",
    "chat_messages",
    "study_guides",
    "essay_submissions",
    "activity_log",
    "schema_migrations",
)


def _migration_file_count() -> int:
    """Diskteki geçerli migration dosya sayısı — yeni migration eklenince test kırılmasın.

    Adlandırma kuralı `src/db.py`'deki runner ile aynı: `NNN_ad.sql` (3+ hane).
    """
    return len([p for p in MIGRATIONS_DIR.glob("*.sql") if re.match(r"^\d{3,}_.+\.sql$", p.name)])


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
        versions = [row["version"] for row in rows]
        # Sabit liste değil: yeni migration eklendiğinde bu test kırılmasın.
        # Sözleşme: sürümler 1'den başlar, artan ve boşluksuz; ilk dördünün adı sabit.
        assert versions == list(range(1, len(rows) + 1))
        assert len(rows) >= 4
        names = [row["name"] for row in rows]
        assert names[:4] == [
            "materials_tipleri",
            "yeni_tablolar",
            "llm_provider_column",
            "tenant_id",
        ]

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

        # Yeni medya türü artık CHECK'ten geçmeli (youtube: v2, syllabus: migration 0012)
        await db.execute(
            "INSERT INTO materials (course_id, type, filepath) "
            "VALUES (1, 'youtube', 'https://youtu.be/abc')"
        )
        await db.execute(
            "INSERT INTO materials (course_id, type, filepath) "
            "VALUES (1, 'syllabus', 'izlence.pdf')"
        )
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) AS c FROM materials")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 3

        # saved_questions (migration 0012): aynı (tenant_id, feed_question_id) iki kez kaydedilemez
        await db.execute(
            "INSERT INTO feed_questions (id, course_id, question, options_json, correct_index) "
            "VALUES (1, 1, 'Soru?', '[]', 0)"
        )
        await db.execute(
            "INSERT INTO saved_questions (tenant_id, feed_question_id) VALUES ('local', 1)"
        )
        await db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO saved_questions (tenant_id, feed_question_id) VALUES ('local', 1)"
            )

        cursor = await db.execute("SELECT COUNT(*) AS c FROM schema_migrations")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == _migration_file_count()


async def test_init_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await init_db()  # ikinci çalıştırma hata vermemeli, kayıtlar tekilleşmeli

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COUNT(*) AS c FROM schema_migrations")
        row = await cursor.fetchone()
        # Tekilleşme kontrolü: iki init_db sonrası kayıt sayısı migration dosya sayısına eşit
        assert row is not None and row["c"] == _migration_file_count()

        cursor = await db.execute("SELECT COUNT(*) AS c FROM materials")
        row = await cursor.fetchone()
        assert row is not None and row["c"] == 0  # 0001'in tekrarı satır üretmemeli
