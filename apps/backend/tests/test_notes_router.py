"""Not router testleri — SSE akışı, not okuma, kaynak erişimi (Faz 3.2/3.3)."""

import io

import pymupdf

from src.config import settings
from src.routers import notes as notes_router


async def _make_chapter(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bağlı Listeler"})
    return resp.json()["id"]


def test_sse_format():
    line = notes_router._sse({"type": "status", "percent": 5, "message": "Hazırlanıyor…"})
    assert line.startswith("data: {")
    assert line.endswith("\n\n")


async def test_notes_sse_endpoint(client, monkeypatch):
    chapter_id = await _make_chapter(client)

    async def fake_generator(chapter_id):
        yield {"type": "status", "percent": 5, "message": "Başlıyor…"}
        yield {"type": "delta", "text": "## Konu"}
        yield {
            "type": "done",
            "note": {
                "id": 1,
                "content_md": "## Konu",
                "citations_json": {"topics": []},
                "topics_json": [],
            },
        }

    monkeypatch.setattr(notes_router, "generate_notes_stream", fake_generator)

    resp = await client.post(f"/api/chapters/{chapter_id}/notes")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "Başlıyor…" in body
    assert '"type": "delta"' in body or '"type":"delta"' in body
    assert '"type": "done"' in body or '"type":"done"' in body


async def test_export_note_pdf(client):
    """Not PDF export'u Türkçe içerikle çalışmalı (madde 9)."""
    chapter_id = await _make_chapter(client)

    import json

    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                chapter_id,
                "# Başlık\n\nTürkçe içerik şğı çiçek [1].",
                json.dumps({"topics": []}, ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                "deepseek-chat",
            ),
        )
        await conn.commit()
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        note_id = row[0]

    resp = await client.get(f"/api/notes/{note_id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")
    # PDF'ten geri okunduğunda Türkçe içerik korunmuş olmalı
    import io

    import pymupdf

    doc = pymupdf.open(stream=io.BytesIO(resp.content), filetype="pdf")
    text = "".join(str(page.get_text()) for page in doc)
    assert "Türkçe" in text or "çiçek" in text
    doc.close()


async def test_get_latest_note_roundtrip(client):
    chapter_id = await _make_chapter(client)

    import json

    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                chapter_id,
                "# Not",
                json.dumps({"topics": []}, ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                "deepseek-chat",
            ),
        )
        await conn.commit()

    resp = await client.get(f"/api/chapters/{chapter_id}/notes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_md"] == "# Not"
    assert body["citations_json"] == {"topics": []}
    assert body["model_used"] == "deepseek-chat"

    # notu olmayan chapter → null
    other = await _make_chapter(client)
    resp = await client.get(f"/api/chapters/{other}/notes")
    assert resp.status_code == 200
    assert resp.json() is None


async def test_material_file_endpoint(client):
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Ders"})
    course_id = resp.json()["id"]

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF içerik", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    created = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", buf.getvalue(), "application/pdf")},
        data={"type": "textbook"},
    )
    material_id = created.json()["id"]

    resp = await client.get(f"/api/materials/{material_id}/file")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")

    resp = await client.get("/api/materials/9999/file")
    assert resp.status_code == 404


async def test_resolve_citation(client, monkeypatch):
    from src.services import embed_service, vector_store

    monkeypatch.setattr(embed_service, "embed_texts", lambda texts: [[0.1] * 4 for _ in texts])
    vector_store.upsert_chunks(
        1,
        [
            {
                "chunk_id": "chk_5_1_1",
                "course_id": 1,
                "material_id": 5,
                "page": 1,
                "slide": None,
                "text": "Kaynak parça metni.",
                "vector": [0.1, 0.2, 0.3, 0.4],
            }
        ],
    )

    resp = await client.get("/api/citations/chk_5_1_1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunk_id"] == "chk_5_1_1"
    assert body["page"] == 1

    resp = await client.get("/api/citations/chk_yok")
    assert resp.status_code == 404
