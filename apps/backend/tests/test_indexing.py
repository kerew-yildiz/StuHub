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

    # Materyal yüklemesi artık kendiliğinden indeksleme işini kuyruğa alıp işliyor
    # (Kerem kararı, 2026-09-04: manuel "İndeksle" butonu kaldırıldı) — POST /index
    # burada 409 döner (iş zaten var), bunun yerine oluşan işi listeden buluyoruz.
    resp = await client.get(f"/api/courses/{course_id}/indexing-jobs")
    jobs = resp.json()
    job_id = next(j["id"] for j in jobs if j["material_id"] == material_id)

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

    # Yükleme kendiliğinden indeksleme işini kuyruğa alır (2026-09-04 kararı) — ilk işi
    # POST ile değil, oluşan işi listeden bulup bekleyerek doğrula.
    resp = await client.get(f"/api/courses/{course_id}/indexing-jobs")
    first_job_id = next(j["id"] for j in resp.json() if j["material_id"] == material_id)
    await _wait_for_job(client, first_job_id)

    before = _count_chunks(course_id)

    # ikinci kez indeksle → kopya oluşmamalı
    resp = await client.post(f"/api/materials/{material_id}/index")
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    job = await _wait_for_job(client, job_id)
    assert job["status"] == "done"
    after = _count_chunks(course_id)
    assert after == before == 2


async def test_process_pending_jobs_respects_concurrency_limit(client, monkeypatch):
    """Kapasite kadar iş claim edilir; fazlası `pending` kalır (yol haritası Aşama 0-10).

    Sınır olmadan bekleyen TÜM işler tek turda claim edilip paralel başlatılıyordu.
    """
    import asyncio

    import aiosqlite

    from src.config import settings
    from src.services import indexer as indexer_service
    from src.workers import indexer as indexer_worker

    monkeypatch.setattr(settings, "indexer_concurrency", 2)

    release = asyncio.Event()
    started: list[int] = []

    async def fake_job(job_id: int, tenant_id: str = "local") -> None:
        started.append(job_id)
        await release.wait()

    monkeypatch.setattr(indexer_worker, "run_indexing_job", fake_job)

    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]

    async with aiosqlite.connect(settings.db_path) as db:
        for material_id in range(1, 6):
            await db.execute(
                "INSERT INTO materials (id, tenant_id, course_id, type, filepath) "
                "VALUES (?, ?, ?, ?, ?)",
                (material_id, "local", course_id, "textbook", "/tmp/yok.pdf"),
            )
            await db.execute(
                "INSERT INTO indexing_jobs (tenant_id, course_id, material_id, status) "
                "VALUES (?, ?, ?, 'pending')",
                ("local", course_id, material_id),
            )
        await db.commit()

    try:
        assert await indexer_worker.process_pending_jobs() == 2
        await asyncio.sleep(0)
        assert len(started) == 2
        # Kapasite dolu — ikinci tur hiçbir iş başlatmamalı.
        assert await indexer_worker.process_pending_jobs() == 0

        async with aiosqlite.connect(settings.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT status, COUNT(*) AS n FROM indexing_jobs GROUP BY status"
            )
            counts = {r["status"]: r["n"] for r in await cursor.fetchall()}
        assert counts["processing"] == 2
        assert counts["pending"] == 3
    finally:
        # Görevleri serbest bırakıp bitmelerini BEKLE — yarım kalan görev, testten
        # sonra kapanan event loop'a yazmaya çalışıp gürültülü uyarı üretiyor.
        release.set()
        if indexer_worker._running:
            await asyncio.gather(*list(indexer_worker._running), return_exceptions=True)
        assert indexer_service is not None


async def test_recover_stale_jobs_leaves_live_worker_alone(client):
    """Taze heartbeat'li iş kurtarılmamalı; bayat/heartbeat'siz olan kurtarılmalı.

    Yol haritası Aşama 0-11: eski kod açılışta TÜM 'processing' işleri sahibine
    bakmadan pending'e çeviriyordu — rolling deploy'da aktif işler ikinci kez
    işleniyordu.
    """
    from datetime import UTC, datetime, timedelta

    import aiosqlite

    from src.config import settings
    from src.workers import indexer as indexer_worker

    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]

    def _stamp(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    now = datetime.now(UTC)
    rows = [
        # (worker_id, heartbeat_at, kurtarılmalı mı)
        ("baska-worker", _stamp(now), False),  # canlı başka instance
        ("baska-worker", _stamp(now - timedelta(seconds=600)), True),  # çökmüş instance
        (None, None, True),  # eski sürümden kalma / heartbeat'siz
    ]
    async with aiosqlite.connect(settings.db_path) as db:
        for i, (worker_id, heartbeat, _expected) in enumerate(rows, start=1):
            await db.execute(
                "INSERT INTO materials (id, tenant_id, course_id, type, filepath) "
                "VALUES (?, ?, ?, ?, ?)",
                (i, "local", course_id, "textbook", "/tmp/yok.pdf"),
            )
            await db.execute(
                "INSERT INTO indexing_jobs "
                "(id, tenant_id, course_id, material_id, status, worker_id, heartbeat_at) "
                "VALUES (?, ?, ?, ?, 'processing', ?, ?)",
                (i, "local", course_id, i, worker_id, heartbeat),
            )
        await db.commit()

    recovered = await indexer_worker.recover_stale_jobs()
    assert recovered == 2

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, status FROM indexing_jobs ORDER BY id")
        statuses = {r["id"]: r["status"] for r in await cursor.fetchall()}
    # Canlı worker'ın işi dokunulmadan kalmalı.
    assert statuses[1] == "processing"
    assert statuses[2] == "pending"
    assert statuses[3] == "pending"
