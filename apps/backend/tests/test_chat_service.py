"""Materyale Sor (RAG chat) servis testleri — retrieval + LLM mock'lu (Faz V2.1)."""

from __future__ import annotations

import aiosqlite
import pytest

from src.config import settings
from src.services import chat_service
from src.services.llm_service import LLMError


@pytest.fixture(autouse=True)
async def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    from src.db import init_db

    await init_db()
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await conn.execute(
            "INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'Veri Yapıları')"
        )
        await conn.commit()


def _chunks():
    return [
        {
            "chunk_id": "chk_1_1_1",
            "material_id": 1,
            "text": "Bağlı listeler, düğümler ve işaretçiler ile çalışır.",
            "page": 1,
            "slide": None,
            "score": 0.9,
        },
        {
            "chunk_id": "chk_2_s2_1",
            "material_id": 2,
            "text": "Slayt: düğüm ekleme işlemi.",
            "page": None,
            "slide": 2,
            "score": 0.7,
        },
    ]


async def _collect(generator) -> list[dict]:
    events = []
    async for event in generator:
        events.append(event)
    return events


async def _count_messages() -> list[tuple]:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute("SELECT role, mode FROM chat_messages ORDER BY id")
        return [(r[0], r[1]) for r in await cursor.fetchall()]


async def _activity_count() -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT count FROM activity_log WHERE kind = 'chat' AND course_id = 1"
        )
        row = await cursor.fetchone()
        return row[0] if row is not None else 0


async def test_valid_answer_streams_and_saves(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    async def fake_chat_stream(messages, **kwargs):
        yield "Bağlı liste doğrusal bir yapıdır [1]."

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    events = await _collect(
        chat_service.stream_chat_answer(1, "bağlı liste nedir?", "direct")
    )

    assert [e["type"] for e in events] == ["citations", "delta", "done"]
    assert events[0]["citations"][0]["source_label"] == "Kitap s.1"
    assert events[0]["citations"][1]["source_label"] == "Sunum slayt 2"
    assert events[1]["text"] == "Bağlı liste doğrusal bir yapıdır [1]."
    done = events[2]
    assert done["message"]["role"] == "assistant"
    assert done["message"]["citations_json"][0]["id"] == 1
    assert await _count_messages() == [("user", "direct"), ("assistant", "direct")]
    assert await _activity_count() == 1


async def test_activity_log_increments(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    async def fake_chat_stream(messages, **kwargs):
        yield "Yanıt [1]."

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    await _collect(chat_service.stream_chat_answer(1, "soru 1", "direct"))
    await _collect(chat_service.stream_chat_answer(1, "soru 2", "direct"))
    assert await _activity_count() == 2


async def test_invalid_citation_regen_then_error(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    calls = {"count": 0, "messages": []}

    async def fake_chat_stream(messages, **kwargs):
        calls["count"] += 1
        calls["messages"].append(messages)
        yield "Bu bilgi kaynaklarda yok [9]."

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    with pytest.raises(LLMError, match="atıf doğrulamasından"):
        await _collect(chat_service.stream_chat_answer(1, "soru", "direct"))

    assert calls["count"] == 2
    # ikinci çağrıya düzeltici mesaj eklenmeli
    assert any("kaynak numaralarını" in m["content"] for m in calls["messages"][1])
    # assistant kaydedilmez; yalnızca user kalır
    assert await _count_messages() == [("user", "direct")]


async def test_empty_retrieval_no_llm(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: []
    )

    called = {"called": False}

    async def fake_chat_stream(messages, **kwargs):
        called["called"] = True
        yield "olmamalı"

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    events = await _collect(chat_service.stream_chat_answer(1, "soru", "direct"))

    assert not called["called"]
    assert events[0] == {"type": "citations", "citations": []}
    assert "indekslenmiş kaynaklarında" in events[1]["text"]
    assert events[2]["type"] == "done"
    assert events[2]["message"]["citations_json"] == []
    assert await _count_messages() == [("user", "direct"), ("assistant", "direct")]


async def test_quiz_mode_prompt(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    captured = {}

    async def fake_chat_stream(messages, **kwargs):
        captured["system"] = messages[0]["content"]
        yield "Kavrama sorusu: düğüm nedir? [1]"

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    await _collect(chat_service.stream_chat_answer(1, "bana soru sor", "quiz"))

    system = captured["system"]
    assert "KAVRAMA" in system
    assert "DEĞERLENDİR" in system
    assert "puan" in system


async def test_socratic_mode_prompt(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    captured = {}

    async def fake_chat_stream(messages, **kwargs):
        captured["system"] = messages[0]["content"]
        yield "İpucu: düğüm yapısına dikkat et [1]. Sen ne düşünüyorsun?"

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    await _collect(chat_service.stream_chat_answer(1, "cevap ver", "socratic"))

    assert "DOĞRUDAN VERME" in captured["system"]


async def test_history_included_in_prompt(monkeypatch):
    monkeypatch.setattr(
        chat_service.retrieval, "hybrid_search", lambda course_id, query: _chunks()
    )

    captured = {}

    async def fake_chat_stream(messages, **kwargs):
        captured["messages"] = messages
        yield "Yanıt [1]."

    monkeypatch.setattr(chat_service.llm_service, "chat_stream", fake_chat_stream)

    await _collect(chat_service.stream_chat_answer(1, "ilk soru", "direct"))
    await _collect(chat_service.stream_chat_answer(1, "ikinci soru", "direct"))

    roles = [m["role"] for m in captured["messages"]]
    # system + (önceki user/assistant) + mevcut user
    assert roles == ["system", "user", "assistant", "user"]
    assert captured["messages"][1]["content"] == "ilk soru"
