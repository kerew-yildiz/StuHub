"""Çalışma rehberi servis testleri (Yetenek 13)."""

from __future__ import annotations

import json

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services import guide_service
from src.services.guide_service import (
    GuideError,
    generate_chapter_guide,
    generate_course_guide,
    get_latest_guide,
    validate_concept_map,
    validate_summary,
)

VALID_SUMMARY = {
    "summary_md": "Özet metni.",
    "key_terms": ["terim1", "terim2"],
    "exam_focus": ["odak 1"],
}

VALID_MAP = {
    "nodes": [
        {"id": "k1", "label": "Kavram A", "importance": 3},
        {"id": "k2", "label": "Kavram B", "importance": 1},
    ],
    "edges": [{"from": "k1", "to": "k2", "label": "içerir"}],
}


async def _seed_note(tmp_path, chapter_id: int = 1, course_id: int = 1) -> None:
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await db.execute(
            "INSERT INTO courses (id, term_id, name) VALUES (?, 1, 'Veri Yapıları')",
            (course_id,),
        )
        await db.execute(
            "INSERT INTO chapters (id, course_id, title) VALUES (?, ?, 'Bağlı Listeler')",
            (chapter_id, course_id),
        )
        await db.execute(
            "INSERT INTO notes (id, chapter_id, content_md) VALUES (1, ?, '# Not\nİçerik')",
            (chapter_id,),
        )
        await db.commit()


async def test_validate_units():
    assert validate_summary(VALID_SUMMARY) == []
    assert validate_summary({"summary_md": "", "key_terms": [], "exam_focus": ["x"]})
    assert validate_concept_map(VALID_MAP) == []
    cyclic = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    assert "çevrim" in validate_concept_map(cyclic)[0]
    dangling = {
        "nodes": [{"id": "a", "label": "A"}],
        "edges": [{"from": "a", "to": "yok"}],
    }
    assert any("uçları" in e for e in validate_concept_map(dangling))


async def test_chapter_summary_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_note(tmp_path)

    calls = {"n": 0}

    async def fake_chat_json(messages, **kwargs):
        calls["n"] += 1
        return VALID_SUMMARY

    monkeypatch.setattr(guide_service.llm_service, "chat_json", fake_chat_json)

    saved = await generate_chapter_guide(1, "summary")
    assert saved["kind"] == "summary"
    assert calls["n"] == 1

    latest = await get_latest_guide(course_id=None, chapter_id=1, kind="summary")
    assert latest is not None
    assert latest["content_json"]["key_terms"] == ["terim1", "terim2"]


async def test_invalid_then_valid_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_note(tmp_path)

    attempts = {"n": 0}

    async def flaky(messages, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"summary_md": "", "key_terms": [], "exam_focus": []}
        return VALID_SUMMARY

    monkeypatch.setattr(guide_service.llm_service, "chat_json", flaky)
    await generate_chapter_guide(1, "summary")
    assert attempts["n"] == 2


async def test_concept_map_rejects_cycle_then_guide_error(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_note(tmp_path)

    cyclic = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }

    async def always_cyclic(messages, **kwargs):
        return cyclic

    monkeypatch.setattr(guide_service.llm_service, "chat_json", always_cyclic)
    with pytest.raises(GuideError):
        await generate_chapter_guide(1, "concept_map")


async def test_guide_requires_note(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, 'T')")
        await db.execute("INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'C')")
        await db.execute("INSERT INTO chapters (id, course_id, title) VALUES (1, 1, 'Ch')")
        await db.commit()
    with pytest.raises(GuideError, match="not"):
        await generate_chapter_guide(1, "summary")


async def test_course_summary_merges_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_note(tmp_path)
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO chapters (id, course_id, title) VALUES (2, 1, 'Kuyruklar')"
        )
        await db.execute(
            "INSERT INTO notes (id, chapter_id, content_md) VALUES (2, 2, '# Not2\nİçerik2')"
        )
        await db.commit()

    async def fake(messages, **kwargs):
        return VALID_SUMMARY

    monkeypatch.setattr(guide_service.llm_service, "chat_json", fake)
    saved = await generate_course_guide(1, "summary")
    assert saved["chapter_id"] is None

    latest = await get_latest_guide(course_id=1, chapter_id=None, kind="summary")
    assert latest is not None


async def test_course_concept_map_merges_chapter_maps(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_note(tmp_path)
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO study_guides (id, course_id, chapter_id, kind, content_json) "
            "VALUES (1, 1, 1, 'concept_map', ?)",
            (json.dumps(VALID_MAP),),
        )
        await db.commit()

    saved = await generate_course_guide(1, "concept_map")
    content = saved
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT content_json FROM study_guides WHERE chapter_id IS NULL"
        )
        row = await cursor.fetchone()
        assert row is not None
        merged = json.loads(row["content_json"])
    assert len(merged["nodes"]) == 2
    assert all(n["id"].startswith("c1_") for n in merged["nodes"])
    assert content["kind"] == "concept_map"
