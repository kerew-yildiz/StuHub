"""Kaynak kapsama göstergesi testleri (Plan #31) — kısmi kapsama, not yokluğu, kiracı izolasyonu."""

import json

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import coverage as coverage_router

_COVERAGE_PATH = "/api/chapters/{chapter_id}/coverage"

# Router kaydı ana uygulamada yapılır; test bağımsız çalışabilsin diye eksikse burada
# eklenir (kayıt sonrası bu blok no-op olur, yol bir kez kaydedilir).
if not any(getattr(route, "path", "") == _COVERAGE_PATH for route in app.routes):
    app.include_router(coverage_router.router)


async def _make_chapter(client) -> tuple[int, int]:
    """(course_id, chapter_id) döner."""
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bağlı Listeler"})
    return course_id, resp.json()["id"]


async def _add_textbook(course_id: int, page_count: int | None, tenant_id: str = "local") -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO materials (tenant_id, course_id, type, filepath, page_count) "
            "VALUES (?, ?, 'textbook', ?, ?)",
            (tenant_id, course_id, "/kitaplar/algoritmalar.pdf", page_count),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid


async def _add_note(chapter_id: int, cited: dict[int, list[int]], tenant_id: str = "local") -> int:
    """`{material_id: [sayfa, ...]}` eşlemesinden not_generator biçiminde atıf JSON'u yazar."""
    citations = [
        {
            "id": i,
            "source_type": "textbook",
            "source_id": material_id,
            "page": page,
            "slide": None,
            "chunk_id": f"chk_{material_id}_{page}_1",
            "quote": "",
        }
        for i, (material_id, page) in enumerate(
            ((m, p) for m, pages in cited.items() for p in pages), start=1
        )
    ]
    payload = {"topics": [{"topic": "Konu", "citations": citations}]}
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES (?, ?, ?, ?, '[]')",
            (tenant_id, chapter_id, "# Not", json.dumps(payload, ensure_ascii=False)),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def test_uncovered_ranges_merges_gaps():
    covered = set(range(1, 12)) | set(range(19, 40))
    assert coverage_router._uncovered_ranges(covered, 41) == [[12, 18], [40, 41]]
    assert coverage_router._uncovered_ranges(set(), 3) == [[1, 3]]
    assert coverage_router._uncovered_ranges({1, 2, 3}, 3) == []
    assert coverage_router._uncovered_ranges(set(), 0) == []


async def test_partial_coverage_returns_correct_ranges(client):
    """Atıf gören sayfalar dolu, geri kalanı bitişik aralık olarak dönmeli."""
    course_id, chapter_id = await _make_chapter(client)
    material_id = await _add_textbook(course_id, page_count=41)
    cited_pages = list(range(1, 12)) + list(range(19, 40))
    note_id = await _add_note(chapter_id, {material_id: cited_pages})

    resp = await client.get(f"/api/chapters/{chapter_id}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["note_id"] == note_id
    assert body["total_pages"] == 41
    assert body["covered_pages"] == cited_pages
    assert body["uncovered_ranges"] == [[12, 18], [40, 41]]
    assert body["coverage_ratio"] == round(32 / 41, 4)

    assert len(body["materials"]) == 1
    material = body["materials"][0]
    assert material["material_id"] == material_id
    assert material["filename"] == "algoritmalar.pdf"
    assert material["total_pages"] == 41
    assert material["uncovered_ranges"] == [[12, 18], [40, 41]]
    assert material["coverage_ratio"] == round(32 / 41, 4)


async def test_no_note_yields_zero_coverage(client):
    """Not üretilmemişse 200 + sıfır kapsama dönmeli (hata değil)."""
    course_id, chapter_id = await _make_chapter(client)
    await _add_textbook(course_id, page_count=20)

    resp = await client.get(f"/api/chapters/{chapter_id}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["note_id"] is None
    assert body["covered_pages"] == []
    assert body["uncovered_ranges"] == [[1, 20]]
    assert body["coverage_ratio"] == 0.0
    assert body["materials"][0]["uncovered_ranges"] == [[1, 20]]


async def test_no_paged_material_is_not_an_error(client):
    """Hiç ders kitabı yüklenmemişse toplam 0, aralık yok, hata yok."""
    _course_id, chapter_id = await _make_chapter(client)

    resp = await client.get(f"/api/chapters/{chapter_id}/coverage")
    assert resp.status_code == 200
    assert resp.json() == {
        "chapter_id": chapter_id,
        "note_id": None,
        "total_pages": 0,
        "covered_pages": [],
        "uncovered_ranges": [],
        "coverage_ratio": 0.0,
        "materials": [],
        "orphaned_source_ids": [],
    }


async def test_tenant_isolation(client):
    """Başka kiracının notu/materyali kapsamaya karışmamalı; başka kiracının chapter'ı 404."""
    course_id, chapter_id = await _make_chapter(client)
    material_id = await _add_textbook(course_id, page_count=10)
    await _add_note(chapter_id, {material_id: [1, 2, 3]}, tenant_id="tenant-b")
    other_material = await _add_textbook(course_id, page_count=10, tenant_id="tenant-b")

    resp = await client.get(f"/api/chapters/{chapter_id}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    # tenant-b'nin notu görülmez → kapsama sıfır; tenant-b'nin materyali listede yok
    assert body["note_id"] is None
    assert body["coverage_ratio"] == 0.0
    assert [m["material_id"] for m in body["materials"]] == [material_id]
    assert other_material not in [m["material_id"] for m in body["materials"]]

    # tenant-b'ye ait chapter yerel kiracıya 404
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES ('tenant-b', ?, 'Gizli')",
            (course_id,),
        )
        await conn.commit()
        foreign_chapter = cursor.lastrowid

    resp = await client.get(f"/api/chapters/{foreign_chapter}/coverage")
    assert resp.status_code == 404
