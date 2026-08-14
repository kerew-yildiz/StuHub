"""Flashcard router testleri (Yetenek 09) — SM-2 review + due kuyruğu."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import aiosqlite

from src.config import settings

CARDS = [
    {"topic": "T", "front": "Soru 1?", "back": "Cevap 1.", "type": "qa",
     "citations": [{"id": 1, "chunk_id": "chk"}]},
    {"topic": "T", "front": "Soru 2?", "back": "Cevap 2.", "type": "qa",
     "citations": [{"id": 1, "chunk_id": "chk"}]},
]


async def _seed(client) -> tuple[int, int]:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Biyoloji"})
    course_id = resp.json()["id"]
    resp = await client.post(
        f"/api/courses/{course_id}/chapters", json={"title": "Zar"}
    )
    chapter_id = resp.json()["id"]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO flashcard_sets (id, course_id, chapter_id, cards_json) "
            "VALUES (1, ?, ?, ?)",
            (course_id, chapter_id, json.dumps(CARDS)),
        )
        await db.commit()
    return course_id, chapter_id


async def test_review_sm2_flow(client):
    course_id, _ = await _seed(client)

    resp = await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "good"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ease_factor"] == 2.5
    assert body["interval_days"] == 1
    assert body["repetitions"] == 1
    assert body["due_at"]

    # tekrar: interval 1 → 6 gün
    resp = await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "good"}
    )
    assert resp.json()["interval_days"] == 6

    # again → sıfırlanır
    resp = await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "again"}
    )
    assert resp.json()["interval_days"] == 1
    assert resp.json()["repetitions"] == 0

    # activity_log 'flashcard' birikti
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT count FROM activity_log WHERE kind = 'flashcard' AND course_id = ?",
            (course_id,),
        )
        row = await cursor.fetchone()
        assert row is not None and row["count"] == 3


async def test_review_validation(client):
    await _seed(client)
    resp = await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "meh"}
    )
    assert resp.status_code == 422
    resp = await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 99, "rating": "good"}
    )
    assert resp.status_code == 404
    resp = await client.post(
        "/api/flashcard-sets/999/reviews", json={"card_index": 0, "rating": "good"}
    )
    assert resp.status_code == 404


async def test_due_queue_orders_overdue_before_new(client):
    course_id, _ = await _seed(client)

    # kart 0 review'lansın ve vadesi GEÇMİŞTE olsun (test için geriye çek)
    await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "good"}
    )
    past = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE card_reviews SET due_at = ? WHERE card_index = 0", (past,)
        )
        await db.commit()

    resp = await client.get(f"/api/courses/{course_id}/flashcards/due")
    assert resp.status_code == 200
    due = resp.json()
    assert len(due) == 2  # vadesi geçmiş kart + yeni kart
    assert due[0]["card_index"] == 0  # vadesi geçen önce
    assert due[0]["review"] is not None
    assert due[1]["review"] is None


async def test_due_queue_filters_future_due(client):
    course_id, _ = await _seed(client)

    # kart 0 "easy" → 4 gün sonra due; bugün due olmamalı
    await client.post(
        "/api/flashcard-sets/1/reviews", json={"card_index": 0, "rating": "easy"}
    )
    resp = await client.get(f"/api/courses/{course_id}/flashcards/due")
    due = resp.json()
    assert all(item["card_index"] == 1 for item in due)  # yalnız yeni kart


async def test_list_and_delete_set(client):
    _, chapter_id = await _seed(client)
    resp = await client.get(f"/api/chapters/{chapter_id}/flashcard-sets")
    assert resp.status_code == 200
    sets = resp.json()
    assert len(sets) == 1 and sets[0]["card_count"] == 2

    resp = await client.delete("/api/flashcard-sets/1")
    assert resp.status_code == 204

    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) AS c FROM card_reviews")
        row = await cursor.fetchone()
        assert row is not None and row[0] == 0  # cascade temizlik
