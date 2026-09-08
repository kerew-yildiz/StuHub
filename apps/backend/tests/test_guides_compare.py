"""Karşılaştırma tablosu testleri (Plan #24 — LLM mock'lu).

LLM `llm_service.chat_json` seviyesinde taklit edilir (test_note_generator.py ile aynı
kalıp): sahte fonksiyon `log_generation` çağırarak gerçek `generation_logs` kaydını atar,
böylece kota sayacının beslendiği de doğrulanabilir.
"""

from __future__ import annotations

import json

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services import guide_service, llm_service
from src.services.guide_service import (
    COMPARISON_KIND,
    GuideError,
    compare,
    get_latest_guide,
    validate_comparison,
)

VALID_COMPARISON = {
    "concepts": ["Yığın", "Kuyruk"],
    "pairs": [
        {
            "a": "Yığın",
            "b": "Kuyruk",
            "similarities": ["İkisi de doğrusal veri yapısıdır."],
            "differences": [
                {"aspect": "erişim düzeni", "a": "LIFO", "b": "FIFO"},
                {"aspect": "tipik kullanım", "a": "geri alma", "b": "iş sırası"},
            ],
            "confusion": "Ekleme ve çıkarma uçlarının hangi yapıda aynı olduğu karıştırılır.",
        }
    ],
}

SUMMARY_CONTENT = {
    "summary_md": "Yığın LIFO, kuyruk FIFO çalışır.",
    "key_terms": ["Yığın", "Kuyruk"],
    "exam_focus": ["LIFO/FIFO ayrımı"],
}


async def _seed_course_with_summary(tmp_path, *, tenant_id: str = "local") -> None:
    """Ders + chapter + not + chapter özeti (karşılaştırmanın girdisi)."""
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO terms (id, tenant_id, name) VALUES (1, ?, '2026 Bahar')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO courses (id, tenant_id, term_id, name) VALUES (1, ?, 1, 'Veri Yapıları')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO chapters (id, tenant_id, course_id, title) "
            "VALUES (1, ?, 1, 'Yığın ve Kuyruk')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO notes (id, tenant_id, chapter_id, content_md) VALUES (1, ?, 1, '# Not')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (1, ?, 1, 1, 'summary', ?)",
            (tenant_id, json.dumps(SUMMARY_CONTENT, ensure_ascii=False)),
        )
        await db.commit()


def _mock_llm(monkeypatch, payload, *, calls: dict | None = None):
    """`chat_json`'ı taklit eder; generation_logs kaydı gerçekten atılır."""

    async def fake_chat_json(messages, **kwargs):
        if calls is not None:
            calls["n"] = calls.get("n", 0) + 1
            calls["kind"] = kwargs.get("kind")
            calls["prompt"] = messages[0]["content"]
        await llm_service.log_generation(
            kind=kwargs.get("kind", "json"),
            provider="gemini",
            model="gemini-2.5-flash",
            tenant_id=kwargs.get("tenant_id", "local"),
            course_id=kwargs.get("course_id"),
            chapter_id=kwargs.get("chapter_id"),
        )
        return payload(messages) if callable(payload) else payload

    monkeypatch.setattr(guide_service.llm_service, "chat_json", fake_chat_json)


async def test_validate_comparison_units():
    assert validate_comparison(VALID_COMPARISON) == []

    tek_fark = json.loads(json.dumps(VALID_COMPARISON))
    tek_fark["pairs"][0]["differences"] = [{"aspect": "düzen", "a": "LIFO", "b": "FIFO"}]
    assert any("en az 2 fark" in e for e in validate_comparison(tek_fark))

    bos_karisim = json.loads(json.dumps(VALID_COMPARISON))
    bos_karisim["pairs"][0]["confusion"] = "  "
    assert any("karıştırılan nokta" in e for e in validate_comparison(bos_karisim))

    assert any("pairs" in e for e in validate_comparison({"concepts": ["a", "b"]}))

    # Eksik ikili: 3 kavram istendi, LLM tek ikili döndü.
    expected = {
        frozenset({"yığın", "kuyruk"}),
        frozenset({"yığın", "dizi"}),
        frozenset({"kuyruk", "dizi"}),
    }
    errors = validate_comparison(VALID_COMPARISON, expected)
    assert any("örtüşmüyor" in e for e in errors)


async def test_compare_saves_comparison_kind_and_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course_with_summary(tmp_path)

    calls: dict = {}
    _mock_llm(monkeypatch, VALID_COMPARISON, calls=calls)

    saved = await compare(1, ["Yığın", "Kuyruk"])
    assert saved["kind"] == COMPARISON_KIND
    assert saved["chapter_id"] is None
    assert calls["n"] == 1
    # Prompt ders bağlamını (özet + anahtar terimler) taşımalı.
    assert "LIFO" in calls["prompt"]
    assert "Yığın ↔ Kuyruk" in calls["prompt"]

    latest = await get_latest_guide(course_id=1, chapter_id=None, kind=COMPARISON_KIND)
    assert latest is not None
    assert latest["content_json"]["pairs"][0]["a"] == "Yığın"

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM study_guides WHERE kind = ?", (COMPARISON_KIND,)
        )
        row = await cursor.fetchone()
        assert row is not None and row["n"] == 1
        cursor = await db.execute("SELECT kind, tenant_id, course_id FROM generation_logs")
        logs = [dict(r) for r in await cursor.fetchall()]
    assert logs == [{"kind": COMPARISON_KIND, "tenant_id": "local", "course_id": 1}]


async def test_compare_tenant_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course_with_summary(tmp_path, tenant_id="tenant-a")
    _mock_llm(monkeypatch, VALID_COMPARISON)

    # Başka kiracı aynı dersin özetlerini göremez → bağlam yok, üretim reddedilir.
    with pytest.raises(GuideError, match="Önce özet üret"):
        await compare(1, ["Yığın", "Kuyruk"], tenant_id="tenant-b")

    saved = await compare(1, ["Yığın", "Kuyruk"], tenant_id="tenant-a")
    assert saved["kind"] == COMPARISON_KIND
    assert await get_latest_guide(1, None, COMPARISON_KIND, tenant_id="tenant-b") is None


async def test_compare_rejects_bad_concept_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course_with_summary(tmp_path)
    _mock_llm(monkeypatch, VALID_COMPARISON)

    with pytest.raises(GuideError, match="en az 2"):
        await compare(1, ["Yığın", " yığın ", ""])
    with pytest.raises(GuideError, match="En fazla"):
        await compare(1, [f"kavram{i}" for i in range(7)])


async def test_compare_requires_summary_guide(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, 'T')")
        await db.execute("INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'C')")
        await db.commit()
    _mock_llm(monkeypatch, VALID_COMPARISON)

    with pytest.raises(GuideError, match="Önce özet üret"):
        await compare(1, ["Yığın", "Kuyruk"])


async def test_compare_invalid_output_retries_then_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed_course_with_summary(tmp_path)

    calls: dict = {}
    _mock_llm(monkeypatch, {"concepts": ["Yığın", "Kuyruk"], "pairs": []}, calls=calls)

    with pytest.raises(GuideError, match="geçersiz"):
        await compare(1, ["Yığın", "Kuyruk"])
    assert calls["n"] == 2


async def test_compare_endpoint(client, tmp_path, monkeypatch):
    await _seed_course_with_summary(tmp_path)
    _mock_llm(monkeypatch, VALID_COMPARISON)

    missing = await client.post("/api/courses/999/compare", json={"concepts": ["a", "b"]})
    assert missing.status_code == 404

    too_few = await client.post("/api/courses/1/compare", json={"concepts": ["Yığın"]})
    assert too_few.status_code == 422

    created = await client.post(
        "/api/courses/1/compare", json={"concepts": ["Yığın", "Kuyruk"]}
    )
    assert created.status_code == 200
    assert created.json()["kind"] == COMPARISON_KIND

    fetched = await client.get(f"/api/courses/1/guides?kind={COMPARISON_KIND}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["content_json"]["pairs"][0]["confusion"]
    assert "answer_key" not in fetched.text
