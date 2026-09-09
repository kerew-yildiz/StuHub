"""Otomatik not üretimi tetiği testleri (`services.indexer.maybe_start_auto_notes`).

Tetik koşulu: dersin pending/processing indexing_job'u YOK AND chapter'ın slaytı VAR
AND chapter'ın notu YOK AND üretim zaten koşmuyor. `note_generator.generate_notes_stream`
gerçek LLM çağrısı yapmasın diye monkeypatch'lenir; asıl doğrulanan şey tetikleme mantığı.
"""

import asyncio

from src.auth import LOCAL_TENANT_ID
from src.db import get_db
from src.services import indexer


async def _make_course_with_chapter(client) -> tuple[int, int]:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Ders"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bölüm 1"})
    chapter_id = resp.json()["id"]
    return course_id, chapter_id


async def _add_slide(chapter_id: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO slides (tenant_id, chapter_id, slide_no, content_text) "
            "VALUES (?, ?, 1, 'içerik')",
            (LOCAL_TENANT_ID, chapter_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _add_indexing_job(course_id: int, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO indexing_jobs (tenant_id, course_id, status, progress) "
            "VALUES (?, ?, ?, 0)",
            (LOCAL_TENANT_ID, course_id, status),
        )
        await db.commit()
    finally:
        await db.close()


async def test_active_job_blocks_trigger(client, monkeypatch):
    """Dersin pending/processing bir indexing_job'u varken not üretimi tetiklenmemeli."""
    course_id, chapter_id = await _make_course_with_chapter(client)
    await _add_slide(chapter_id)
    await _add_indexing_job(course_id, "processing")

    started: list[int] = []

    async def _fake_stream(cid: int, tenant_id: str):
        started.append(cid)
        yield {"type": "done", "note_id": 1}

    monkeypatch.setattr(indexer.note_generator, "generate_notes_stream", _fake_stream)

    tasks_before = set(indexer._note_tasks)
    await indexer.maybe_start_auto_notes(course_id, LOCAL_TENANT_ID)
    assert indexer._note_tasks == tasks_before
    assert started == []


async def test_ready_chapter_triggers_note_generation(client, monkeypatch):
    """Slayt var + not yok + aktif iş yok → not üretimi arka planda başlamalı."""
    course_id, chapter_id = await _make_course_with_chapter(client)
    await _add_slide(chapter_id)

    started: list[int] = []

    async def _fake_stream(cid: int, tenant_id: str):
        started.append(cid)
        yield {"type": "done", "note_id": 1}

    monkeypatch.setattr(indexer.note_generator, "generate_notes_stream", _fake_stream)

    await indexer.maybe_start_auto_notes(course_id, LOCAL_TENANT_ID)
    for task in list(indexer._note_tasks):
        await task

    assert started == [chapter_id]
    assert (LOCAL_TENANT_ID, chapter_id) not in indexer._note_inflight


async def test_same_chapter_not_started_twice(client, monkeypatch):
    """Bir chapter için üretim koşarken ikinci tetikleme yeni bir görev başlatmamalı."""
    course_id, chapter_id = await _make_course_with_chapter(client)
    await _add_slide(chapter_id)

    started: list[int] = []
    release = asyncio.Event()

    async def _slow_stream(cid: int, tenant_id: str):
        started.append(cid)
        await release.wait()
        yield {"type": "done", "note_id": 1}

    monkeypatch.setattr(indexer.note_generator, "generate_notes_stream", _slow_stream)

    await indexer.maybe_start_auto_notes(course_id, LOCAL_TENANT_ID)  # görev başlar
    await indexer.maybe_start_auto_notes(course_id, LOCAL_TENANT_ID)  # in-flight — atlanmalı

    assert started == [chapter_id]
    assert len(indexer._note_tasks) == 1

    release.set()
    for task in list(indexer._note_tasks):
        await task
    assert (LOCAL_TENANT_ID, chapter_id) not in indexer._note_inflight
