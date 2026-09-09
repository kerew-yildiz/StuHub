"""Kaydedilen sorular testleri (Plan: kaydırmalı quiz #8) — idempotent kayıt/kaldırma,
listeleme, tenant izolasyonu.
"""

import json

import aiosqlite
import pytest

from src.config import settings
from src.main import app
from src.routers import saved_questions as saved_router
from src.services import feed_service

if not any(getattr(r, "path", "") == "/api/saved-questions" for r in app.routes):
    app.include_router(saved_router.router)


@pytest.fixture(autouse=True)
def _clear_filling():
    feed_service._filling.clear()
    yield
    feed_service._filling.clear()


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _make_chapter(client, course_id: int) -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Konu A"})
    return resp.json()["id"]


async def _seeded_feed_question(client, tenant_id: str = "local") -> tuple[int, int]:
    """(course_id, feed_id) — havuzda bir soru hazırlar."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    questions_json = {
        "topics": [
            {
                "topic": "Konu A",
                "questions": [
                    {
                        "topic": "Konu A",
                        "question": "Bağlı listeler nedir?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 0,
                        "explanation": "Açıklama.",
                    }
                ],
            }
        ]
    }
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await conn.commit()
        quiz_id = cursor.lastrowid
    await feed_service.backfill_from_existing(course_id, tenant_id)
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id FROM feed_questions WHERE tenant_id = ? AND course_id = ?",
            (tenant_id, course_id),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert quiz_id is not None
    return course_id, dict(row)["id"]


async def test_kaydetme_idempotenttir(client):
    _course_id, feed_id = await _seeded_feed_question(client)

    first = await client.post(f"/api/feed/{feed_id}/save")
    assert first.status_code == 201
    assert first.json() == {"saved": True}

    # Aynı soruyu tekrar kaydetmek hata vermez (idempotent)
    second = await client.post(f"/api/feed/{feed_id}/save")
    assert second.status_code == 201
    assert second.json() == {"saved": True}

    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT COUNT(*) AS n FROM saved_questions")
        row = await cursor.fetchone()
    assert row is not None
    assert dict(row)["n"] == 1  # ikinci istek yeni satır açmadı


async def test_kaydetme_olmayan_soruda_404(client):
    resp = await client.post("/api/feed/99999/save")
    assert resp.status_code == 404


async def test_kaldirma_idempotenttir(client):
    _course_id, feed_id = await _seeded_feed_question(client)
    await client.post(f"/api/feed/{feed_id}/save")

    first = await client.delete(f"/api/feed/{feed_id}/save")
    assert first.status_code == 200
    assert first.json() == {"saved": False}

    # Zaten kaldırılmış bir kaydı tekrar silmek hata vermez
    second = await client.delete(f"/api/feed/{feed_id}/save")
    assert second.status_code == 200
    assert second.json() == {"saved": False}

    resp = await client.get("/api/saved-questions")
    assert resp.json() == []


async def test_listeleme_sozlesme_alanlari_ve_siralama(client):
    course_id, feed_id = await _seeded_feed_question(client)
    await client.post(f"/api/feed/{feed_id}/save")

    resp = await client.get("/api/saved-questions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert set(item) == {
        "feed_id",
        "question",
        "options",
        "correct_index",
        "explanation",
        "topic",
        "chapter_id",
        "chapter_title",
        "course_id",
        "course_name",
        "saved_at",
    }
    assert item["feed_id"] == feed_id
    assert item["question"] == "Bağlı listeler nedir?"
    assert item["correct_index"] == 0
    assert item["course_id"] == course_id
    assert item["course_name"] == "Veri Yapıları"
    assert item["chapter_title"] == "Konu A"


async def test_tenant_izolasyonu(client):
    _course_id, feed_id = await _seeded_feed_question(client, tenant_id="local")
    assert await feed_service.save_question(feed_id, "other") is False  # başka kiracının sorusu

    await client.post(f"/api/feed/{feed_id}/save")  # 'local' kiracısı kaydeder
    assert await feed_service.list_saved("other") == []
    assert len(await feed_service.list_saved("local")) == 1
