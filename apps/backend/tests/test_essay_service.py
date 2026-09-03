"""Genel ödev değerlendirme servis testleri (Yetenek 14)."""

from __future__ import annotations

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services import essay_service
from src.services.essay_service import (
    EssayServiceError,
    grade_homework,
    list_submissions,
)

VALID_GRADE = {
    "score": 78,
    "criteria": [
        {"name": "İçerik doğruluğu", "score": 16, "max": 20, "comment": "iyi"},
        {"name": "Dil ve anlatım", "score": 15, "max": 20, "comment": "akıcı"},
    ],
    "strengths": ["güçlü giriş"],
    "weaknesses": ["kaynak eksik"],
    "quotes": [{"text": "örnek cümle", "comment": "yerinde"}],
    "confidence": 0.9,
}


async def _seed_course(tmp_path) -> None:
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await db.execute("INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'Tarih')")
        await db.commit()


async def test_valid_grade_saved_and_listed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course(tmp_path)

    async def fake(messages, **kwargs):
        return VALID_GRADE

    monkeypatch.setattr(essay_service.llm_service, "chat_json", fake)

    result = await grade_homework(
        instructions="Bir deneme yaz.", user_text="Deneme metni.", rubric=None, course_id=1
    )
    assert result["score"] == 78

    history = await list_submissions(1)
    assert len(history) == 1
    assert history[0]["score"] == 78

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        cursor = await db.execute("SELECT COUNT(*) AS c FROM essay_submissions")
        row = await cursor.fetchone()
        assert row is not None and row[0] == 1


async def test_empty_text_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course(tmp_path)

    async def should_not_call(messages, **kwargs):
        raise AssertionError("boş metinde LLM çağrılmamalı")

    monkeypatch.setattr(essay_service.llm_service, "chat_json", should_not_call)
    result = await grade_homework(
        instructions="Deneme", user_text="   ", rubric=None, course_id=1
    )
    assert result["score"] == 0
    assert result["confidence"] == 1.0


async def test_invalid_then_valid_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course(tmp_path)

    attempts = {"n": 0}

    async def flaky(messages, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"score": 500, "criteria": [], "strengths": [], "weaknesses": [],
                    "quotes": [], "confidence": 0.9}
        return VALID_GRADE

    monkeypatch.setattr(essay_service.llm_service, "chat_json", flaky)
    result = await grade_homework(
        instructions="Deneme", user_text="Metin", rubric=None, course_id=1
    )
    assert result["score"] == 78
    assert attempts["n"] == 2


async def test_low_confidence_reevaluates(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course(tmp_path)

    attempts = {"n": 0}

    async def uncertain(messages, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {**VALID_GRADE, "confidence": 0.3}
        return VALID_GRADE

    monkeypatch.setattr(essay_service.llm_service, "chat_json", uncertain)
    result = await grade_homework(
        instructions="Deneme", user_text="Metin", rubric=None, course_id=1
    )
    assert result["confidence"] == 0.9
    assert attempts["n"] == 2


async def test_always_invalid_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course(tmp_path)

    async def bad(messages, **kwargs):
        return {"score": -1, "criteria": [], "strengths": [], "weaknesses": [],
                "quotes": [], "confidence": 0.9}

    monkeypatch.setattr(essay_service.llm_service, "chat_json", bad)
    with pytest.raises(EssayServiceError):
        await grade_homework(
            instructions="Deneme", user_text="Metin", rubric=None, course_id=1
        )
