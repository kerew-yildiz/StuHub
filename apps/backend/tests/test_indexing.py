"""İndeksleme pipeline testleri (Faz 2.2) — embedding mock'lu, LanceDB gerçek.

Mock stratejisi: model indirmesini test etmek yerine embed_texts sabit vektör döndürür;
chunking + LanceDB yazma/okuma + iş durum makinesi gerçekten doğrulanır.
"""

import io

import lancedb
import pymupdf

import src.services.embed_service as embed_service
from src.config import settings


def _make_pdf_bytes() -> bytes:
    font_file = r"C:\Windows\Fonts\arial.ttf"
    doc = pymupdf.open()
    for text in ["Giriş bölümü içeriği.", "Devam eden bölüm içeriği."]:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11, fontname="arial", fontfile=font_file)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


async def _make_course_with_material(client) -> tuple[int, int]:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": ("kitap.pdf", _make_pdf_bytes(), "application/pdf")},
        data={"type": "textbook"},
    )
    return course_id, resp.json()["id"]


async def _wait_for_job(client, job_id: int, timeout: float = 15.0) -> dict:
    import asyncio

    import aiosqlite

    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with aiosqlite.connect(settings.db_path) as conn:
            cursor = await conn.execute(
                "SELECT status, progress, error FROM indexing_jobs WHERE id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise AssertionError("iş bulunamadı")
        job = {"status": row[0], "progress": row[1], "error": row[2]}
        if job["status"] in ("done", "failed"):
            return job
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"iş zaman aşımına uğradı: {job}")
        await asyncio.sleep(0.2)


async def _open_db():
    from src.db import get_db

    return await get_db()


def _count_chunks(course_id: int) -> int:
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    ns = f"course_{course_id}_chunks"
    if ns not in (db.list_tables().tables or []):
        return 0
    return db.open_table(ns).count_rows()


async def test_full_indexing_pipeline(client, monkeypatch):
    # Embedding'i sabit vektörlerle mock'la (model indirmesi test dışı)
    monkeypatch.setattr(
        embed_service,
        "embed_texts",
        lambda texts: [[0.05] * 8 for _ in texts],
    )

    course_id, material_id = await _make_course_with_material(client)

    resp = await client.post(f"/api/materials/{material_id}/index")
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    job = await _wait_for_job(client, job_id)
    assert job["status"] == "done", job["error"]
    assert job["progress"] == 100

    # LanceDB'de chunk'lar var ve metadata doğru
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    table = db.open_table(f"course_{course_id}_chunks")
    arrow = table.to_arrow()
    rows = arrow.to_pylist()
    assert len(rows) == 2  # iki sayfa → iki chunk
    assert {r["page"] for r in rows} == {1, 2}
    assert all(len(r["vector"]) == 8 for r in rows)

    # page_count güncellendi
    resp = await client.get(f"/api/courses/{course_id}/materials")
    material = next(m for m in resp.json() if m["id"] == material_id)
    assert material["page_count"] == 2
    assert material["vector_ns"] == f"course_{course_id}_chunks"


async def test_reindex_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(
        embed_service,
        "embed_texts",
        lambda texts: [[0.05] * 8 for _ in texts],
    )
    course_id, material_id = await _make_course_with_material(client)

    await client.post(f"/api/materials/{material_id}/index")
    # done olana kadar bekle (ilk iş)
    import asyncio

    deadline = asyncio.get_running_loop().time() + 15
    while True:
        db = await _open_db()
        import aiosqlite

        async with aiosqlite.connect(settings.db_path) as conn:
            cursor = await conn.execute(
                "SELECT status FROM indexing_jobs WHERE material_id = ? ORDER BY id DESC LIMIT 1",
                (material_id,),
            )
            row = await cursor.fetchone()
        await db.close()
        if row and row[0] == "done":
            break
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("ilk indeksleme zaman aşımı")
        await asyncio.sleep(0.2)

    before = _count_chunks(course_id)

    # ikinci kez indeksle → kopya oluşmamalı
    resp = await client.post(f"/api/materials/{material_id}/index")
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    job = await _wait_for_job(client, job_id)
    assert job["status"] == "done"
    after = _count_chunks(course_id)
    assert after == before == 2
