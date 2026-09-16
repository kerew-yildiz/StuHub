"""İhracat router testleri — not (PDF/MD), flashcard (apkg/csv/md), arşiv (V2.3)."""

from __future__ import annotations

import io
import json
import zipfile

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
            (chapter_id, "# Giriş\n\nİçerik metni.", "{}", "[]", "gemini-2.5-flash"),
        )
        note_id = cursor.lastrowid
        cursor = await conn.execute(
            "INSERT INTO flashcard_sets (course_id, chapter_id, cards_json, model_used) "
            "VALUES (?, ?, ?, ?)",
            (course_id, chapter_id, json.dumps(CARDS, ensure_ascii=False), "gemini-2.5-flash"),
        )
        set_id = cursor.lastrowid
        materials_dir = settings.materials_dir / str(course_id)
        materials_dir.mkdir(parents=True, exist_ok=True)
        pdf = materials_dir / "kitap.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")
        cursor = await conn.execute(
            "INSERT INTO materials (course_id, type, filepath, page_count) "
            "VALUES (?, 'textbook', ?, 2)",
            (course_id, str(pdf)),
        )
        material_id = cursor.lastrowid
        await conn.commit()

    return {
        "term_id": term_id,
        "course_id": course_id,
        "chapter_id": chapter_id,
        "note_id": note_id,
        "set_id": set_id,
        "material_id": material_id,
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
    """Dersi olan dönem: 200 + application/zip + GERÇEK içerik (K5).

    Regresyon: 401 (başlıksız indirme) ve 500 (`bigint = json`) düzeltilmeden önce
    bu istek 401/500 dönüyordu. Yalnızca `manifest.json` içeren 239-295 baytlık
    "boş" arşiv dönüşü başarı SAYILMAZ — ders/chapter girdileri zorunlu.
    """
    seed = await _seed(client)
    resp = await client.get(f"/api/terms/{seed['term_id']}/archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    assert resp.content.startswith(b"PK")

    course_prefix = f"courses/{seed['course_id']}"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert f"{course_prefix}/course.json" in names
        assert f"{course_prefix}/chapters.json" in names

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["term"] == "2026 Bahar"
        assert manifest["courses"] == [seed["course_id"]]

        course = json.loads(archive.read(f"{course_prefix}/course.json"))
        assert course["name"] == "Veri Yapıları"
        chapters = json.loads(archive.read(f"{course_prefix}/chapters.json"))
        assert [c["title"] for c in chapters] == ["Bağlı Listeler"]


async def test_archive_export_term_without_courses_is_manifest_only(client):
    """Dersi olmayan dönem: 200 + yalnızca manifest, `courses: []` (K5 regresyonu).

    Boş dönem `_fetch_rows`'un erken `[]` dönüşüne düşer — 500'lerin nedeni olan
    id-listeli sorgular bu yolda hiç çalışmaz; yine de 200 + tutarlı manifest şart.
    """
    resp = await client.post("/api/terms", json={"name": "Boş Dönem"})
    term_id = resp.json()["id"]

    resp = await client.get(
        f"/api/terms/{term_id}/archive", params={"include_files": "false"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        assert archive.namelist() == ["manifest.json"]
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["term"] == "Boş Dönem"
        assert manifest["courses"] == []


async def test_archive_export_include_files_packs_materials(client):
    """`include_files=true`: materyal kaydı hem JSON hem dosya olarak arşive girer (K5).

    Bu yol `materials` şablonunu (`course_id` id-listesi) VE `row['filepath']`
    okumasını tetikler — Katman 2/3 düzeltmelerinin asıl sınavı.
    """
    seed = await _seed(client)
    resp = await client.get(
        f"/api/terms/{seed['term_id']}/archive", params={"include_files": "true"}
    )
    assert resp.status_code == 200

    material_prefix = f"courses/{seed['course_id']}/materials/{seed['material_id']}"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        names = set(archive.namelist())
        assert f"{material_prefix}.json" in names
        assert f"{material_prefix}.bin" in names

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["materials_included"] is True

        row = json.loads(archive.read(f"{material_prefix}.json"))
        assert row["type"] == "textbook"
        assert row["page_count"] == 2
        assert archive.read(f"{material_prefix}.bin") == b"%PDF-1.4 test"


async def test_archive_import_roundtrip(client):
    """Dışa aktarılan zip geri yüklenir: yeni dönem + " (içe aktarıldı)" eki (K5/D)."""
    seed = await _seed(client)
    archive = await client.get(f"/api/terms/{seed['term_id']}/archive")
    resp = await client.post(
        "/api/archive/import",
        files={"file": ("archive.zip", archive.content, "application/zip")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["term_name"] == "2026 Bahar (içe aktarıldı)"
    assert body["term_id"] != seed["term_id"]
    new_course_id = body["courses"][0]["new_id"]
    assert new_course_id != seed["course_id"]

    # İçe aktarılan dönem gerçekten içerik taşıyor (yalnız dönem satırı değil):
    # yeniden dışa aktarınca yeni ders kimliğiyle course/chapters girdileri gelir.
    reexport = await client.get(f"/api/terms/{body['term_id']}/archive")
    assert reexport.status_code == 200
    with zipfile.ZipFile(io.BytesIO(reexport.content)) as archive_zip:
        names = set(archive_zip.namelist())
        assert f"courses/{new_course_id}/course.json" in names
        assert f"courses/{new_course_id}/chapters.json" in names
        chapters = json.loads(archive_zip.read(f"courses/{new_course_id}/chapters.json"))
    assert [c["title"] for c in chapters] == ["Bağlı Listeler"]


async def test_archive_import_empty_file(client):
    resp = await client.post(
        "/api/archive/import",
        files={"file": ("empty.zip", b"", "application/zip")},
    )
    assert resp.status_code == 422
