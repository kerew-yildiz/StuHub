"""Konuşarak tekrar uç testleri — whisper mock'lu, LLM YOK (Plan #47)."""

from __future__ import annotations

import json

import aiosqlite
import faster_whisper

from src.config import settings
from src.main import app
from src.routers import recall as recall_router

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(getattr(r, "path", "") == "/api/chapters/{chapter_id}/recall" for r in app.routes):
    app.include_router(recall_router.router)


class _FakeSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, path):
        segments = [
            _FakeSegment(0.0, 2.0, "kuvvet ve ivme newton yasasını anlatır"),
            _FakeSegment(2.0, 4.0, "ama enerjiden hiç bahsetmedim"),
        ]
        return iter(segments), None


TOPICS_META = [
    {"topic": "Newton Yasaları", "keywords": ["kuvvet", "ivme"]},
    {"topic": "Enerji Korunumu", "keywords": ["kinetik", "potansiyel"]},
]


async def _make_chapter_with_note(client, topics_meta: list[dict]) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Fizik"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Mekanik"})
    chapter_id = resp.json()["id"]

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES ('local', ?, '# Mekanik\\nmetin', '{}', ?)",
            (chapter_id, json.dumps(topics_meta, ensure_ascii=False)),
        )
        await conn.commit()
    return chapter_id


async def test_recall_returns_transcript_and_covered_missed(client, monkeypatch):
    monkeypatch.setattr(faster_whisper, "WhisperModel", _FakeWhisperModel)
    chapter_id = await _make_chapter_with_note(client, TOPICS_META)

    resp = await client.post(
        f"/api/chapters/{chapter_id}/recall",
        files={"file": ("kayit.mp3", b"dummy audio bytes", "audio/mpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "kuvvet" in data["transcript"]
    assert data["covered_topics"] == ["Newton Yasaları"]
    assert data["missed_topics"] == ["Enerji Korunumu"]


async def test_recall_no_note_returns_404(client, monkeypatch):
    monkeypatch.setattr(faster_whisper, "WhisperModel", _FakeWhisperModel)
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Kimya"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Asitler"})
    chapter_id = resp.json()["id"]

    resp = await client.post(
        f"/api/chapters/{chapter_id}/recall",
        files={"file": ("kayit.mp3", b"dummy audio bytes", "audio/mpeg")},
    )
    assert resp.status_code == 404


async def test_recall_bad_extension_rejected(client):
    chapter_id = await _make_chapter_with_note(client, TOPICS_META)
    resp = await client.post(
        f"/api/chapters/{chapter_id}/recall",
        files={"file": ("kayit.txt", b"dummy", "text/plain")},
    )
    assert resp.status_code == 422


async def test_recall_empty_topics_json_returns_empty_lists(client, monkeypatch):
    monkeypatch.setattr(faster_whisper, "WhisperModel", _FakeWhisperModel)
    chapter_id = await _make_chapter_with_note(client, [])

    resp = await client.post(
        f"/api/chapters/{chapter_id}/recall",
        files={"file": ("kayit.mp3", b"dummy audio bytes", "audio/mpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["covered_topics"] == []
    assert data["missed_topics"] == []
    assert data["transcript"]
