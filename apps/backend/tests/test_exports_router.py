"""İhracat router testleri — not (PDF/MD), flashcard (apkg/csv/md), arşiv (V2.3)."""

from __future__ import annotations

import json

CARDS = [
    {
        "topic": "Konu A",
        "front": "Fosfolipid çift katmanın temel işlevi nedir?",
        "back": "Seçici geçirgen bariyer oluşturur.",
        "type": "qa",
        "citations": [{"id": 1, "page": 5}],
    },
    {
        "topic": "Konu A",
        "front": "Hücre zarı",
        "back": "Hücreyi dış ortamdan ayıran yapı.",
        "type": "term",
        "citations": [{"id": 1, "page": 5}],
    },
    {
        "topic": "Konu B",
        "front": "Osmoz nedir?",
        "back": "Suyun yarı geçirgen zardan geçişi.",
        "type": "qa",
        "citations": [{"id": 2, "slide": 3}],
    },
]


async def _seed(client) -> dict:
    """term → course → chapter → note + flashcard set (3 kart) + materyal kurar."""
    import aiosqlite

    from src.config import settings

    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(
        f"/api/courses/{course_id}/chapters", json={"title": "Bağlı Listeler"}
    )
    chapter_id = resp.json()["id"]

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, "
            "model_used) VALUES (?, ?, ?, ?, ?)",
            (chapter_id, "# Giriş\n\nİçerik metni.", "{}", "[]", "deepseek-chat"),
        )
        note_id = cursor.lastrowid
        cursor = await conn.execute(
            "INSERT INTO flashcard_sets (course_id, chapter_id, cards_json, model_used) "
            "VALUES (?, ?, ?, ?)",
            (course_id, chapter_id, json.dumps(CARDS, ensure_ascii=False), "deepseek-chat"),
        )
        set_id = cursor.lastrowid
        materials_dir = settings.materials_dir / str(course_id)
        materials_dir.mkdir(parents=True, exist_ok=True)
        pdf = materials_dir / "kitap.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")
        await conn.execute(
            "INSERT INTO materials (course_id, type, filepath, page_count) "
            "VALUES (?, 'textbook', ?, 2)",
            (course_id, str(pdf)),
        )
        await conn.commit()

    return {
        "term_id": term_id,
        "course_id": course_id,
        "chapter_id": chapter_id,
        "note_id": note_id,
        "set_id": set_id,
    }


async def test_export_note_markdown(client):
    seed = await _seed(client)
    resp = await client.get(f"/api/notes/{seed['note_id']}/export", params={"format": "md"})
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "# Bağlı Listeler" in resp.text


async def test_export_note_pdf_default(client):
    seed = await _seed(client)
    resp = await client.get(f"/api/notes/{seed['note_id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


async def test_export_flashcard_apkg(client):
    seed = await _seed(client)
    resp = await client.get(
        f"/api/flashcard-sets/{seed['set_id']}/export", params={"format": "apkg"}
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"PK")  # zip imzası


async def test_export_flashcard_csv(client):
    seed = await _seed(client)
    resp = await client.get(
        f"/api/flashcard-sets/{seed['set_id']}/export", params={"format": "csv"}
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM


async def test_export_flashcard_md(client):
    seed = await _seed(client)
    resp = await client.get(
        f"/api/flashcard-sets/{seed['set_id']}/export", params={"format": "md"}
    )
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "Fosfolipid çift katmanın temel işlevi nedir?" in resp.text


async def test_export_flashcard_invalid_format(client):
    seed = await _seed(client)
    resp = await client.get(
        f"/api/flashcard-sets/{seed['set_id']}/export", params={"format": "docx"}
    )
    assert resp.status_code == 422


async def test_export_flashcard_missing_set(client):
    resp = await client.get("/api/flashcard-sets/9999/export")
    assert resp.status_code == 404


async def test_export_note_invalid_format(client):
    seed = await _seed(client)
    resp = await client.get(f"/api/notes/{seed['note_id']}/export", params={"format": "docx"})
    assert resp.status_code == 422


async def test_archive_export_zip(client):
    seed = await _seed(client)
    resp = await client.get(f"/api/terms/{seed['term_id']}/archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    assert resp.content.startswith(b"PK")


async def test_archive_import_roundtrip(client):
    seed = await _seed(client)
    archive = await client.get(f"/api/terms/{seed['term_id']}/archive")
    resp = await client.post(
        "/api/archive/import",
        files={"file": ("archive.zip", archive.content, "application/zip")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["term_name"].endswith("(içe aktarıldı)")
    assert body["term_id"] != seed["term_id"]


async def test_archive_import_empty_file(client):
    resp = await client.post(
        "/api/archive/import",
        files={"file": ("empty.zip", b"", "application/zip")},
    )
    assert resp.status_code == 422
