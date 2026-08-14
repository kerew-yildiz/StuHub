"""Materyale Sor (RAG chat) router testleri — SSE, geçmiş, temizlik, 404 (Faz V2.1)."""

from __future__ import annotations

import json

import aiosqlite

from src.config import settings
from src.routers import chat as chat_router
from src.services.llm_service import LLMError


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(
        f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"}
    )
    return resp.json()["id"]


async def test_chat_sse_endpoint(client, monkeypatch):
    course_id = await _make_course(client)

    async def fake_generator(course_id, message, mode):
        yield {"type": "citations", "citations": []}
        yield {"type": "delta", "text": "Yanıt [1]."}
        yield {
            "type": "done",
            "message": {
                "id": 1,
                "role": "assistant",
                "content": "Yanıt [1].",
                "citations_json": [],
                "mode": mode,
                "created_at": "2026-01-01 00:00:00",
            },
        }

    monkeypatch.setattr(chat_router, "stream_chat_answer", fake_generator)

    resp = await client.post(
        f"/api/courses/{course_id}/chat", json={"message": "soru", "mode": "direct"}
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert '"type": "citations"' in resp.text
    assert '"type": "delta"' in resp.text
    assert '"type": "done"' in resp.text


async def test_chat_error_event(client, monkeypatch):
    course_id = await _make_course(client)

    async def fake_generator(course_id, message, mode):
        yield {"type": "delta", "text": "kısmi"}
        raise LLMError("API anahtarı ayarlanmadı. Ayarlar sayfasından girin.")

    monkeypatch.setattr(chat_router, "stream_chat_answer", fake_generator)

    resp = await client.post(f"/api/courses/{course_id}/chat", json={"message": "soru"})
    assert resp.status_code == 200
    assert '"type": "error"' in resp.text
    assert "API anahtarı" in resp.text


async def test_chat_invalid_mode_422(client):
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/chat", json={"message": "soru", "mode": "yanlış"}
    )
    assert resp.status_code == 422


async def test_chat_course_not_found(client):
    resp = await client.post("/api/courses/9999/chat", json={"message": "soru"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Ders bulunamadı"


async def test_chat_history_and_delete(client):
    course_id = await _make_course(client)

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO chat_messages (course_id, role, content, mode) "
            "VALUES (?, 'user', 'soru', 'direct')",
            (course_id,),
        )
        await conn.execute(
            "INSERT INTO chat_messages (course_id, role, content, citations_json, mode) "
            "VALUES (?, 'assistant', 'yanıt [1]', ?, 'direct')",
            (course_id, json.dumps([{"id": 1}], ensure_ascii=False)),
        )
        await conn.commit()

    resp = await client.get(f"/api/courses/{course_id}/chat")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["citations_json"] == [{"id": 1}]

    resp = await client.delete(f"/api/courses/{course_id}/chat")
    assert resp.status_code == 204

    resp = await client.get(f"/api/courses/{course_id}/chat")
    assert resp.json() == {"messages": []}
