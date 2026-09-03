"""Medya alım pipeline testleri (Faz V2.6) — extractor + embed mock'lu, worker gerçek."""

from __future__ import annotations

import asyncio
import json

import aiosqlite
import lancedb

import src.services.embed_service as embed_service
import src.services.media_extractors as media_extractors
from src.config import settings
from src.services.indexer import transcript_path

FAKE_AUDIO_BYTES = b"RIFF0000WAVEfake-audio-bytes"
FAKE_DOCX_BYTES = b"PK\x03\x04fake-docx-bytes"


def _fake_extract_for(mtype: str, source: str) -> list[dict]:
    if mtype == "audio":
        return [
            {"segment": 0, "text": "Ses transkript bir.", "start": 0.0, "end": 2.0},
            {"segment": 1, "text": "Ses transkript iki.", "start": 2.0, "end": 4.0},
        ]
    if mtype == "youtube":
        return [{"segment": 0, "text": "Video altyazı metni.", "start": 1.0}]
    if mtype == "docx":
        return [{"segment": 0, "text": "Belge paragrafı."}]
    if mtype == "text":
        return [
            {"segment": i, "text": part}
            for i, part in enumerate(source.split("\n"))
            if part.strip()
        ]
    raise AssertionError(f"beklenmeyen tür: {mtype}")


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Medya Dersi"})
    return resp.json()["id"]


async def _wait_indexed(material_id: int, timeout: float = 30.0) -> None:
    """Materyalin işleri bitene kadar bekler; hata varsa AssertionError."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with aiosqlite.connect(settings.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT vector_ns FROM materials WHERE id = ?", (material_id,)
            )
            material = await cursor.fetchone()
            cursor = await db.execute(
                "SELECT status, error FROM indexing_jobs "
                "WHERE material_id = ? ORDER BY id DESC",
                (material_id,),
            )
            jobs = list(await cursor.fetchall())
        if material is not None and material["vector_ns"]:
            return
        if jobs and jobs[0]["status"] == "failed":
            raise AssertionError(f"iş başarısız: {jobs[0]['error']}")
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("indeksleme zaman aşımı")
        await asyncio.sleep(0.2)


def _chunk_texts(course_id: int) -> list[str]:
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    ns = f"course_{course_id}_chunks"
    if ns not in (db.list_tables().tables or []):
        return []
    return [row["text"] for row in db.open_table(ns).to_arrow().to_pylist()]


async def test_text_paste_pipeline(client, monkeypatch):
    monkeypatch.setattr(
        embed_service, "embed_texts", lambda texts: [[0.05] * 8 for _ in texts]
    )
    monkeypatch.setattr(media_extractors, "extract_for", _fake_extract_for)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/media/text",
        json={"title": "Ders Notları", "content": "Satır bir.\nSatır iki."},
    )
    assert resp.status_code == 201
    material_id = resp.json()["id"]
    assert resp.json()["type"] == "text"

    await _wait_indexed(material_id)
    texts = _chunk_texts(course_id)
    assert any("Satır bir" in t for t in texts)


async def test_youtube_ingest_and_validation(client, monkeypatch):
    monkeypatch.setattr(
        embed_service, "embed_texts", lambda texts: [[0.05] * 8 for _ in texts]
    )
    monkeypatch.setattr(media_extractors, "extract_for", _fake_extract_for)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/media/youtube", json={"url": "geçersiz-adres"}
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/courses/{course_id}/media/youtube",
        json={"url": "https://youtu.be/abc123"},
    )
    assert resp.status_code == 201
    material_id = resp.json()["id"]

    await _wait_indexed(material_id)
    texts = _chunk_texts(course_id)
    assert any("[00:01]" in t and "Video altyazı" in t for t in texts)


async def test_audio_transcribe_chain(client, monkeypatch):
    monkeypatch.setattr(
        embed_service, "embed_texts", lambda texts: [[0.05] * 8 for _ in texts]
    )
    monkeypatch.setattr(media_extractors, "extract_for", _fake_extract_for)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("ders.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")},
        data={"type": "audio"},
    )
    assert resp.status_code == 201
    material_id = resp.json()["id"]

    await _wait_indexed(material_id)  # transkripsiyon + zincirli indeks bitmeli

    # transkript JSON + extracted_text kaydedildi
    transcript = json.loads(transcript_path(material_id).read_text(encoding="utf-8"))
    assert len(transcript) == 2
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute(
            "SELECT extracted_text FROM materials WHERE id = ?", (material_id,)
        )
        row = await cursor.fetchone()
        assert row is not None and "[00:00]" in row[0]

    texts = _chunk_texts(course_id)
    assert any("Ses transkript bir" in t for t in texts)


async def test_docx_upload_auto_index(client, monkeypatch):
    monkeypatch.setattr(
        embed_service, "embed_texts", lambda texts: [[0.05] * 8 for _ in texts]
    )
    monkeypatch.setattr(media_extractors, "extract_for", _fake_extract_for)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={
            "file": (
                "odev.docx",
                FAKE_DOCX_BYTES,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"type": "docx"},
    )
    assert resp.status_code == 201
    material_id = resp.json()["id"]
    await _wait_indexed(material_id)
    assert any("Belge paragrafı" in t for t in _chunk_texts(course_id))


async def test_media_extension_validation(client):
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("virus.exe", b"zararli", "application/octet-stream")},
        data={"type": "audio"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", b"%PDF", "application/pdf")},
        data={"type": "video"},
    )
    assert resp.status_code == 422
