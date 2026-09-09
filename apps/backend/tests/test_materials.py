"""Materyal yükleme testleri (Faz 1.2 — depolama; çıkarım Faz 2.1)."""

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def test_upload_and_list(client):
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "textbook"
    assert body["filepath"].endswith("kitap.pdf")
    assert body["page_count"] is None  # çıkarım Faz 2.1

    resp = await client.get(f"/api/courses/{course_id}/materials")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_upload_syllabus_type(client):
    """syllabus (müfredat/izlence) türü PDF kabul eder, desteklenmeyen uzantıyı reddeder."""
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("izlence.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "syllabus"},
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "syllabus"

    # desteklenmeyen uzantı (syllabus yalnızca .pdf/.docx kabul eder)
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("izlence.txt", b"merhaba", "text/plain")},
        data={"type": "syllabus"},
    )
    assert resp.status_code == 422


async def test_upload_validation(client):
    course_id = await _make_course(client)
    # yanlış uzantı
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("nota.txt", b"merhaba", "text/plain")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 422

    # yanlış tür
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "video"},
    )
    assert resp.status_code == 422

    # var olmayan ders
    resp = await client.post(
        "/api/courses/9999/materials",
        files={"file": ("kitap.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 404


async def test_upload_empty_file_clear_error(client):
    """0 baytlık dosya net Türkçe mesajla reddedilmeli (bozuk/eksik indirme uyarısı)."""
    course_id = await _make_course(client)
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", b"", "application/pdf")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"].lower()
    assert "boş" in detail or "0 bayt" in detail

    # materyal satırı oluşmamalı
    resp = await client.get(f"/api/courses/{course_id}/materials")
    assert resp.json() == []


async def test_delete_material(client):
    course_id = await _make_course(client)
    created = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "textbook"},
    )
    material_id = created.json()["id"]

    resp = await client.delete(f"/api/materials/{material_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/courses/{course_id}/materials")
    assert resp.json() == []


async def test_upload_rejects_oversized_file(client, monkeypatch):
    """Boyut sınırı aşılırsa 413 döner ve yarım dosya diskte kalmaz.

    Sınır olmadan tek bir istek diski doldurabiliyordu (yol haritası Aşama 0-4).
    """
    from src.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", PDF_BYTES + b"x" * 5000, "application/pdf")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 413

    # Materyal kaydedilmemeli ve dosya artığı bırakılmamalı.
    resp = await client.get(f"/api/courses/{course_id}/materials")
    assert resp.json() == []
    course_dir = settings.materials_dir / str(course_id)
    assert not course_dir.exists() or list(course_dir.iterdir()) == []


async def test_upload_within_limit_still_works(client, monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 10 * 1024)
    course_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", PDF_BYTES, "application/pdf")},
        data={"type": "textbook"},
    )
    assert resp.status_code == 201
