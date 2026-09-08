"""Çalışma oturumu (pomodoro) zamanlayıcı uç testleri (Plan #14)."""

from __future__ import annotations

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import study_sessions as study_sessions_router

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(
    getattr(r, "path", "") == "/api/courses/{course_id}/study-sessions" for r in app.routes
):
    app.include_router(study_sessions_router.router)


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Fizik"})
    return resp.json()["id"]


async def _rows(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]


async def test_create_session_persists(client):
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/study-sessions",
        json={"session_id": "sess-1", "duration_sec": 1800},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["course_id"] == course_id
    assert data["session_id"] == "sess-1"
    assert data["duration_sec"] == 1800
    assert data["created_at"]

    rows = await _rows("SELECT * FROM study_sessions WHERE session_id = 'sess-1'")
    assert len(rows) == 1


async def test_duplicate_session_id_is_idempotent(client):
    course_id = await _make_course(client)
    payload = {"session_id": "dup-1", "duration_sec": 900}
    first = await client.post(f"/api/courses/{course_id}/study-sessions", json=payload)
    second = await client.post(f"/api/courses/{course_id}/study-sessions", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    rows = await _rows("SELECT id FROM study_sessions WHERE session_id = 'dup-1'")
    assert len(rows) == 1


async def test_unknown_course_returns_404(client):
    resp = await client.post(
        "/api/courses/99999/study-sessions",
        json={"session_id": "sess-x", "duration_sec": 60},
    )
    assert resp.status_code == 404


async def test_tenant_isolation(client):
    course_id = await _make_course(client)
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO study_sessions (tenant_id, course_id, session_id, duration_sec) "
            "VALUES ('other', ?, 'shared-id', 500)",
            (course_id,),
        )
        await conn.commit()

    # 'local' kiracısı aynı session_id'yi kullanabilir — 'other'ın satırı görülmez
    resp = await client.post(
        f"/api/courses/{course_id}/study-sessions",
        json={"session_id": "shared-id", "duration_sec": 700},
    )
    assert resp.status_code == 201
    assert resp.json()["duration_sec"] == 700

    rows = await _rows("SELECT tenant_id FROM study_sessions WHERE session_id = 'shared-id'")
    assert {r["tenant_id"] for r in rows} == {"local", "other"}
