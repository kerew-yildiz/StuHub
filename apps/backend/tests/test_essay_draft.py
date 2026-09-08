"""Ödev taslak koçu uç testleri — puan sızmaz, kind='draft' kaydedilir (Plan #41)."""

from __future__ import annotations

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import essay_draft as essay_draft_router
from src.services import essay_service

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(
    getattr(r, "path", "") == "/api/courses/{course_id}/essays/draft-review" for r in app.routes
):
    app.include_router(essay_draft_router.router)

VALID_DRAFT = {
    "has_thesis": True,
    "thesis_feedback": "Tez cümlesi net.",
    "evidence_linked": False,
    "evidence_feedback": "Kanıt eksik.",
    "weak_sections": ["sonuç bölümü"],
    "next_steps": ["Bir örnek ekle.", "Sonucu güçlendir."],
}


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Edebiyat"})
    return resp.json()["id"]


async def _rows(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]


async def test_draft_review_no_score_leak(client, monkeypatch):
    async def fake(messages, **kwargs):
        return dict(VALID_DRAFT)

    monkeypatch.setattr(essay_service.llm_service, "chat_json", fake)

    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/essays/draft-review",
        json={"instructions": "Bir deneme yaz.", "user_text": "Taslak metin."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" not in data
    assert data["has_thesis"] is True
    assert data["next_steps"] == VALID_DRAFT["next_steps"]


async def test_draft_review_persists_kind_draft(client, monkeypatch):
    async def fake(messages, **kwargs):
        return dict(VALID_DRAFT)

    monkeypatch.setattr(essay_service.llm_service, "chat_json", fake)

    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/essays/draft-review",
        json={"instructions": "Bir deneme yaz.", "user_text": "Taslak metin."},
    )
    assert resp.status_code == 200

    rows = await _rows(
        "SELECT kind, grade_json FROM essay_submissions WHERE course_id = ?", (course_id,)
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "draft"
    assert "score" not in rows[0]["grade_json"]


async def test_empty_draft_text_deterministic_no_llm_call(client, monkeypatch):
    calls = []

    async def fake(messages, **kwargs):
        calls.append(1)
        return dict(VALID_DRAFT)

    monkeypatch.setattr(essay_service.llm_service, "chat_json", fake)

    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/essays/draft-review",
        json={"instructions": "Bir deneme yaz.", "user_text": "   "},
    )
    assert resp.status_code == 200
    assert resp.json()["has_thesis"] is False
    assert calls == []  # boş metinde LLM çağrılmaz


async def test_tenant_isolation(client):
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await conn.execute(
            "INSERT INTO courses (id, term_id, name, tenant_id) VALUES (1, 1, 'Gizli', 'other')"
        )
        await conn.commit()

    resp = await client.post(
        "/api/courses/1/essays/draft-review",
        json={"instructions": "Bir deneme yaz.", "user_text": "Taslak metin."},
    )
    assert resp.status_code == 404
