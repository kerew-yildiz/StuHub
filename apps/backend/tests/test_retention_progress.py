"""Öğrenme ilerlemesi göstergesi uç testleri — haftalık kalıcı hatırlama (Plan #48)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import retention_progress as retention_router

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(
    getattr(r, "path", "") == "/api/courses/{course_id}/retention-progress" for r in app.routes
):
    app.include_router(retention_router.router)

NOW = datetime.now(UTC)
THIS_WEEK = (NOW - timedelta(days=NOW.weekday())).strftime("%Y-%m-%d 09:00:00")
LAST_WEEK = (NOW - timedelta(days=NOW.weekday() + 7)).strftime("%Y-%m-%d 09:00:00")


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Biyoloji"})
    return resp.json()["id"]


async def _make_set(course_id: int, cards: list[dict], tenant_id: str = "local") -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO flashcard_sets (tenant_id, course_id, cards_json) VALUES (?, ?, ?)",
            (tenant_id, course_id, json.dumps(cards, ensure_ascii=False)),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid


async def _add_review(
    set_id: int,
    card_index: int,
    interval_days: float,
    reviewed_at: str,
    tenant_id: str = "local",
) -> None:
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO card_reviews (tenant_id, set_id, card_index, interval_days, reviewed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant_id, set_id, card_index, interval_days, reviewed_at),
        )
        await conn.commit()


async def test_counts_topics_meeting_threshold(client):
    course_id = await _make_course(client)
    set_id = await _make_set(
        course_id,
        [
            {"front": "f0", "back": "b0", "topic": "Hücre"},
            {"front": "f1", "back": "b1", "topic": "Fotosentez"},
        ],
    )
    await _add_review(set_id, 0, 21.0, THIS_WEEK)  # eşiği geçti, bu hafta tekrar edildi
    await _add_review(set_id, 1, 5.0, THIS_WEEK)  # eşik altı

    resp = await client.get(f"/api/courses/{course_id}/retention-progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["topics_mastered_this_week"] == 1
    assert data["topics"] == ["Hücre"]


async def test_excludes_review_from_last_week(client):
    course_id = await _make_course(client)
    set_id = await _make_set(course_id, [{"front": "f0", "back": "b0", "topic": "Genetik"}])
    await _add_review(set_id, 0, 30.0, LAST_WEEK)  # eşiği geçti ama bu hafta tekrar edilmedi

    resp = await client.get(f"/api/courses/{course_id}/retention-progress")
    assert resp.json() == {"topics_mastered_this_week": 0, "topics": []}


async def test_dedupes_same_topic_across_cards(client):
    course_id = await _make_course(client)
    set_id = await _make_set(
        course_id,
        [
            {"front": "f0", "back": "b0", "topic": "Evrim"},
            {"front": "f1", "back": "b1", "topic": "Evrim"},
        ],
    )
    await _add_review(set_id, 0, 25.0, THIS_WEEK)
    await _add_review(set_id, 1, 25.0, THIS_WEEK)

    resp = await client.get(f"/api/courses/{course_id}/retention-progress")
    data = resp.json()
    assert data["topics_mastered_this_week"] == 1
    assert data["topics"] == ["Evrim"]


async def test_unknown_course_returns_404(client):
    resp = await client.get("/api/courses/99999/retention-progress")
    assert resp.status_code == 404


async def test_tenant_isolation(client):
    course_id = await _make_course(client)
    set_id = await _make_set(
        course_id, [{"front": "f0", "back": "b0", "topic": "Gizli Konu"}], tenant_id="other"
    )
    await _add_review(set_id, 0, 25.0, THIS_WEEK, tenant_id="other")

    resp = await client.get(f"/api/courses/{course_id}/retention-progress")
    assert resp.json() == {"topics_mastered_this_week": 0, "topics": []}
