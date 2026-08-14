"""Flashcard üretim hattı testleri (Yetenek 09) — LLM mock'lu."""

from __future__ import annotations

import json

import aiosqlite

from src.config import settings
from src.db import init_db
from src.services import flashcard_generator

NOTE_MD = "# Not\n\n### Hücre Zarı\n\nFosfolipit çift katman içeriği.\n"
CITATIONS = {
    "topics": [
        {
            "topic": "Hücre Zarı",
            "citations": [
                {
                    "id": 1,
                    "source_type": "textbook",
                    "source_id": 9,
                    "page": 41,
                    "chunk_id": "chk_9_41_1",
                    "quote": "fosfolipit",
                }
            ],
        }
    ]
}

VALID_CARDS = {
    "cards": [
        {"front": "Çift katmanın işlevi?", "back": "Seçici bariyer.", "type": "qa",
         "citations": [{"id": 1}]},
        {"front": "Fosfolipit nedir?", "back": "Zar lipidi.", "type": "term",
         "citations": [{"id": 1}]},
    ]
}


async def _seed(tmp_path, *, with_note: bool = True) -> None:
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, '2026 Bahar')")
        await db.execute("INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'Biyoloji')")
        await db.execute("INSERT INTO chapters (id, course_id, title) VALUES (1, 1, 'Zar')")
        if with_note:
            await db.execute(
                "INSERT INTO notes (id, chapter_id, content_md, citations_json, topics_json) "
                "VALUES (1, 1, ?, ?, ?)",
                (NOTE_MD, json.dumps(CITATIONS), json.dumps([])),
            )
        await db.commit()


async def _collect_events(chapter_id: int) -> list[dict]:
    return [event async for event in flashcard_generator.generate_flashcards_stream(chapter_id)]


async def test_generation_saves_cited_cards(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)

    async def fake_chat_json(messages, **kwargs):
        return VALID_CARDS

    monkeypatch.setattr(flashcard_generator.llm_service, "chat_json", fake_chat_json)

    events = await _collect_events(1)
    done = next(e for e in events if e["type"] == "done")
    assert done["card_count"] == 2
    assert all(card["topic"] == "Hücre Zarı" for card in done["cards_json"])
    assert all(card["citations"] for card in done["cards_json"])
    assert done["warnings"] == []

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        cursor = await db.execute("SELECT cards_json FROM flashcard_sets")
        row = await cursor.fetchone()
        assert row is not None
        assert len(json.loads(row[0])) == 2


async def test_citationless_cards_rejected_and_warned(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)

    async def no_citations(messages, **kwargs):
        return {"cards": [{"front": "X?", "back": "Y.", "type": "qa", "citations": []}]}

    monkeypatch.setattr(flashcard_generator.llm_service, "chat_json", no_citations)

    events = await _collect_events(1)
    assert any(e["type"] == "error" for e in events)  # tüm konular boş → hata
    error = next(e for e in events if e["type"] == "error")
    assert "Kart üretilemedi" in error["message"]


async def test_no_note_yields_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path, with_note=False)

    events = await _collect_events(1)
    error = next(e for e in events if e["type"] == "error")
    assert "not" in error["message"].lower()


async def test_dedup_by_front(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)

    async def duplicates(messages, **kwargs):
        return {
            "cards": [
                {"front": "Aynı soru?", "back": "C1.", "type": "qa",
                 "citations": [{"id": 1}]},
                {"front": "  Aynı soru? ", "back": "C2.", "type": "qa",
                 "citations": [{"id": 1}]},
                {"front": "Farklı?", "back": "C3.", "type": "qa",
                 "citations": [{"id": 1}]},
            ]
        }

    monkeypatch.setattr(flashcard_generator.llm_service, "chat_json", duplicates)
    events = await _collect_events(1)
    done = next(e for e in events if e["type"] == "done")
    assert done["card_count"] == 2


async def test_llm_error_skips_topic(tmp_path, monkeypatch):
    """LLM hatası konuyu uyarıyla atlar; hiç kart yoksa genel hata döner."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)

    async def boom(messages, **kwargs):
        raise flashcard_generator.llm_service.LLMError("API kotası aşıldı")

    monkeypatch.setattr(flashcard_generator.llm_service, "chat_json", boom)
    events = await _collect_events(1)
    assert any(e["type"] == "error" for e in events)
