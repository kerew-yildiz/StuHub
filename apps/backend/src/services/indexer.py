"""İndeksleme orkestrasyonu — extract → chunk → embed → LanceDB (Faz 2.2 + v2).

v2 (Niş Analizi Entegrasyonu): medya türleri (youtube/audio/docx/epub/image/text)
`media_extractors` paketi üzerinden çıkarılır (Yetenek 11). `kind='transcribe'`
işleri ses/YouTube için önce transkript üretir, ardından `kind='index'` işini
zincirler; `kind='index'` transkripti dosyadan okur (yeniden çevrim yok).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path

from ..config import settings
from ..db import get_db
from . import chunking, embed_service, media_extractors, pdf_service, slides_service, vector_store

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32

# Extractor imzası: (kaynak) -> (parça listesi, 'pages' | 'slides' | 'segments')
ExtractorFn = Callable[[str], tuple[list[dict], str]]

MEDIA_TYPES = ("youtube", "audio", "docx", "epub", "image", "text")


def transcript_path(material_id: int) -> Path:
    """Transkript JSON yolu: data/transcripts/{material_id}.json (Yetenek 11)."""
    return settings.data_dir / "transcripts" / f"{material_id}.json"


def _extract_textbook(path: str) -> tuple[list[dict], str]:
    return pdf_service.extract_pdf_pages(path), "pages"


def _extract_slides(path: str) -> tuple[list[dict], str]:
    ext = Path(path).suffix.lower()
    if ext in (".pptx", ".ppt"):
        return slides_service.extract_pptx_slides(path), "slides"
    pages = pdf_service.extract_pdf_pages(path)
    return [{"slide": p["page"], "text": p["text"]} for p in pages], "slides"


EXTRACTORS: dict[str, ExtractorFn] = {
    "textbook": _extract_textbook,
    "slides": _extract_slides,
}


def register_extractor(mtype: str, fn: ExtractorFn) -> None:
    """v2 genişletme noktası: yeni materyal türleri çıkarıcılarını kaydeder (Yetenek 11)."""
    EXTRACTORS[mtype] = fn


def _extract_material(material: dict) -> tuple[list[dict], str]:
    """Materyal türüne göre sayfa/slide/segment listesi çıkarır. (bloklayıcı — to_thread ile)

    Medya türleri `media_extractors.extract_for` üzerinden dağıtılır; ses
    materyali için önceki transkripsiyon dosyadan okunur (yeniden çevrim yok).
    Dönüş: (parça listesi, 'pages' | 'slides' | 'segments')
    """
    mtype = material["type"]
    path = material["filepath"]
    if mtype in MEDIA_TYPES:
        if mtype == "audio":
            transcript = transcript_path(material["id"])
            if transcript.exists():
                segments = json.loads(transcript.read_text(encoding="utf-8"))
                return segments, "segments"
            raise RuntimeError(
                "Bu ses kaydının transkripsiyonu henüz hazır değil — "
                "iş kuyruğundaki transkripsiyonun bitmesini bekleyin."
            )
        if mtype == "text":
            content = Path(path).read_text(encoding="utf-8")
            return media_extractors.extract_for("text", content), "segments"
        return media_extractors.extract_for(mtype, path), "segments"
    extractor = EXTRACTORS.get(mtype)
    if extractor is None:
        raise RuntimeError(f"'{mtype}' türü için çıkarıcı bulunamadı")
    return extractor(path)


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Bir batch'i embed eder. (bloklayıcı — to_thread ile çağrılır)"""
    return embed_service.embed_texts(texts)


async def run_indexing_job(job_id: int, tenant_id: str) -> None:
    """Tek indeksleme/transkripsiyon işini çalıştırır.

    kind='transcribe' → transkript üret (ses/youtube) + otomatik 'index' işi zincirle.
    kind='index' → extract → chunk → embed → LanceDB (v2: 'segments' chunk'lanır).
    Hata durumunda kullanıcıya Türkçe mesaj `indexing_jobs.error`'a yazılır.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, material_id, status, kind FROM indexing_jobs "
            "WHERE id = ? AND tenant_id = ?",
            (job_id, tenant_id),
        )
        job = await cursor.fetchone()
        if job is None or job["status"] not in ("pending", "processing"):
            return

        await db.execute(
            "UPDATE indexing_jobs SET status='processing', progress=5, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND tenant_id=?",
            (job_id, tenant_id),
        )
        await db.commit()

        material_id = job["material_id"]
        if material_id is None:
            raise RuntimeError("materyal kimliği eksik")
        cursor = await db.execute(
            "SELECT id, course_id, type, filepath FROM materials WHERE id = ? AND tenant_id = ?",
            (material_id, tenant_id),
        )
        material = await cursor.fetchone()
        if material is None:
            raise RuntimeError("materyal bulunamadı")
        material_dict = dict(material)
        course_id = material_dict["course_id"]

        if job["kind"] == "transcribe":
            await _run_transcribe_job(job_id, material_dict, tenant_id)
            return

        extracted, kind = await asyncio.to_thread(_extract_material, material_dict)

        if kind == "pages":
            chunks = chunking.chunk_pdf_pages(course_id, material_id, extracted)
            page_count = len(extracted)
        elif kind == "segments":
            chunks = chunking.chunk_segments(course_id, material_id, extracted)
            page_count = len(extracted)
        else:
            chunks = chunking.chunk_slides(course_id, material_id, extracted)
            page_count = len(extracted)

        await db.execute(
            "UPDATE materials SET page_count = ? WHERE id = ? AND tenant_id = ?",
            (page_count, material_id, tenant_id),
        )
        await db.commit()

        if not chunks:
            raise RuntimeError(
                "Materyalden metin çıkarılamadı (dosya boş ya da taranmış olabilir)."
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
                "UPDATE indexing_jobs SET progress=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND tenant_id=?",
                (progress, job_id, tenant_id),
            )
            await db.commit()

        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk["vector"] = vector

        ns = vector_store.namespace(course_id)
        count = vector_store.upsert_chunks(course_id, chunks)
        await db.execute(
            "UPDATE materials SET vector_ns = ? WHERE id = ? AND tenant_id = ?",
            (ns, material_id, tenant_id),
        )
        await db.execute(
            "UPDATE indexing_jobs SET status='done', progress=100, error=NULL, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND tenant_id=?",
            (job_id, tenant_id),
        )
        await db.commit()
        logger.info("indexing done: job=%s chunks=%s", job_id, count)
    except Exception as exc:
        logger.exception("indexing failed: job=%s", job_id)
        await db.execute(
            "UPDATE indexing_jobs SET status='failed', error=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND tenant_id=?",
            (str(exc), job_id, tenant_id),
        )
        await db.commit()
    finally:
        await db.close()


async def create_indexing_job(
    course_id: int, material_id: int, tenant_id: str, *, kind: str = "index"
) -> int:
    """Yeni indeksleme/transkripsiyon işi oluşturur (worker tarafından işlenir)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO indexing_jobs (tenant_id, course_id, material_id, status, progress, kind) "
            "VALUES (?, ?, ?, 'pending', 0, ?)",
            (tenant_id, course_id, material_id, kind),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("iş kimliği alınamadı")
    finally:
        await db.close()
    return row_id


async def _run_transcribe_job(job_id: int, material: dict, tenant_id: str) -> None:
    """kind='transcribe': çıkarım + transkript JSON kaydı + otomatik 'index' zinciri.

    Çıktı: `data/transcripts/{material_id}.json` + `materials.extracted_text`;
    ardından aynı materyal için kind='index' işi oluşturulur (Yetenek 11).
    """
    material_id = material["id"]
    segments = await asyncio.to_thread(
        media_extractors.extract_for, material["type"], material["filepath"]
    )
    if not segments:
        raise RuntimeError("Transkripsiyon boş çıktı — kayıtta konuşma bulunamadı.")

    text = media_extractors.transcript_to_text(segments)
    transcript = transcript_path(material_id)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")

    db = await get_db()
    try:
        await db.execute(
            "UPDATE materials SET extracted_text = ? WHERE id = ? AND tenant_id = ?",
            (text, material_id, tenant_id),
        )
        await db.execute(
            "UPDATE indexing_jobs SET status='done', progress=100, error=NULL, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND tenant_id=?",
            (job_id, tenant_id),
        )
        await db.commit()
    finally:
        await db.close()
    await create_indexing_job(material["course_id"], material_id, tenant_id, kind="index")
    # Zincirli işi hemen işle (mevcut /index endpoint'i kalıbı; geç import döngüyü önler)
    from ..workers.indexer import process_pending_jobs

    await process_pending_jobs()
    logger.info("transcription done: job=%s material=%s", job_id, material_id)
