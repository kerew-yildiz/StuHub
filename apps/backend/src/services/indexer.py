"""İndeksleme orkestrasyonu — extract → chunk → embed → LanceDB (Faz 2.2)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..db import get_db
from . import chunking, embed_service, pdf_service, slides_service, vector_store

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32


def _extract_material(material: dict) -> tuple[list[dict], str]:
    """Materyal türüne göre sayfa/slide listesi çıkarır. (bloklayıcı — to_thread ile çağrılır)

    Dönüş: (sayfa/slide listesi, 'pages' | 'slides')
    """
    path = material["filepath"]
    mtype = material["type"]
    if mtype == "textbook":
        return pdf_service.extract_pdf_pages(path), "pages"
    ext = Path(path).suffix.lower()
    if ext == ".pptx":
        return slides_service.extract_pptx_slides(path), "slides"
    pages = pdf_service.extract_pdf_pages(path)
    return [{"slide": p["page"], "text": p["text"]} for p in pages], "slides"


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Bir batch'i embed eder. (bloklayıcı — to_thread ile çağrılır)"""
    return embed_service.embed_texts(texts)


async def run_indexing_job(job_id: int) -> None:
    """Tek indeksleme işini çalıştırır; durum: pending → processing → done|failed.

    Hata durumunda kullanıcıya Türkçe mesaj `indexing_jobs.error`'a yazılır.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, material_id, status FROM indexing_jobs WHERE id = ?",
            (job_id,),
        )
        job = await cursor.fetchone()
        if job is None or job["status"] not in ("pending", "processing"):
            return

        await db.execute(
            "UPDATE indexing_jobs SET status='processing', progress=5, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        await db.commit()

        material_id = job["material_id"]
        if material_id is None:
            raise RuntimeError("materyal kimliği eksik")
        cursor = await db.execute(
            "SELECT id, course_id, type, filepath FROM materials WHERE id = ?",
            (material_id,),
        )
        material = await cursor.fetchone()
        if material is None:
            raise RuntimeError("materyal bulunamadı")
        material_dict = dict(material)
        course_id = material_dict["course_id"]

        extracted, kind = await asyncio.to_thread(_extract_material, material_dict)

        if kind == "pages":
            chunks = chunking.chunk_pdf_pages(course_id, material_id, extracted)
            page_count = len(extracted)
        else:
            chunks = chunking.chunk_slides(course_id, material_id, extracted)
            page_count = len(extracted)

        await db.execute(
            "UPDATE materials SET page_count = ? WHERE id = ?",
            (page_count, material_id),
        )
        await db.commit()

        if not chunks:
            raise RuntimeError(
                "Materyalden metin çıkarılamadı (dosya boş ya da tüm sayfalar "
                "taranmış olabilir). OCR desteği Faz 2.2 sonrasında geliyor."
            )

        # embed — batch'ler arası ilerleme raporlanır
        total = len(chunks)
        vectors: list[list[float]] = []
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch_texts = [c["text"] for c in chunks[i : i + EMBED_BATCH_SIZE]]
            batch_vectors = await asyncio.to_thread(_embed_batch, batch_texts)
            vectors.extend(batch_vectors)
            progress = 5 + int(90 * min(i + EMBED_BATCH_SIZE, total) / total)
            await db.execute(
                "UPDATE indexing_jobs SET progress=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (progress, job_id),
            )
            await db.commit()

        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk["vector"] = vector

        ns = vector_store.namespace(course_id)
        count = vector_store.upsert_chunks(course_id, chunks)
        await db.execute(
            "UPDATE materials SET vector_ns = ? WHERE id = ?", (ns, material_id)
        )
        await db.execute(
            "UPDATE indexing_jobs SET status='done', progress=100, error=NULL, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        await db.commit()
        logger.info("indexing done: job=%s chunks=%s", job_id, count)
    except Exception as exc:
        logger.exception("indexing failed: job=%s", job_id)
        await db.execute(
            "UPDATE indexing_jobs SET status='failed', error=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (str(exc), job_id),
        )
        await db.commit()
    finally:
        await db.close()
