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
from ..quota import QuotaExceededError, enforce_quota
from . import (
    chunking,
    embed_service,
    media_extractors,
    note_generator,
    pdf_service,
    slides_service,
    vector_store,
)

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 64

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


def _extract_syllabus(path: str) -> tuple[list[dict], str]:
    """Syllabus .pdf ya da .docx olabilir (materials.py ALLOWED_EXTENSIONS) — uzantıya
    göre uygun çıkarıcıya yönlendirir."""
    if Path(path).suffix.lower() == ".docx":
        return media_extractors.extract_for("docx", path), "segments"
    return pdf_service.extract_pdf_pages(path), "pages"


EXTRACTORS: dict[str, ExtractorFn] = {
    "textbook": _extract_textbook,
    "slides": _extract_slides,
    "syllabus": _extract_syllabus,
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

        if not chunks:
            raise RuntimeError(
                "Materyalden metin çıkarılamadı (dosya boş ya da taranmış olabilir)."
            )

        # extracted_text: chunk'lanmış tam metin — LanceDB'ye özgü, DB'de de tutulur ki
        # kazanımlar (syllabus) gibi özellikler chunk aramasına gitmeden düz metin okuyabilsin.
        full_text = "\n\n".join(chunk["text"] for chunk in chunks)
        await db.execute(
            "UPDATE materials SET page_count = ?, extracted_text = ? "
            "WHERE id = ? AND tenant_id = ?",
            (page_count, full_text, material_id, tenant_id),
        )
        await db.commit()

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
        try:
            await maybe_start_auto_notes(course_id, tenant_id)
        except Exception:
            logger.exception("otomatik not tetikleme başarısız: course=%s", course_id)
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


# Aynı chapter için not üretiminin arka planda ikinci kez başlamaması adına in-flight
# anahtar kümesi (tenant_id, chapter_id). `asyncio.create_task`'ın dönüşü ayrıca
# `_note_tasks`'ta tutulur — tutulmazsa görev iş ortasında çöp toplanabilir
# (asyncio'nun bilinen tuzağı, bkz. workers/indexer.py._running).
_note_inflight: set[tuple[str, int]] = set()
_note_tasks: set[asyncio.Task] = set()


async def _consume_auto_note(chapter_id: int, tenant_id: str) -> None:
    """`generate_notes_stream`i sonuna kadar tüketir; hata loglanır, yutulur.

    Bu bir sunucu tarafı arka plan tetiği — akışı okuyan bir SSE istemcisi yok.
    """
    try:
        async for event in note_generator.generate_notes_stream(chapter_id, tenant_id):
            if event.get("type") == "error":
                logger.warning(
                    "otomatik not üretimi hata event'i: chapter=%s tenant=%s msg=%s",
                    chapter_id,
                    tenant_id,
                    event.get("message"),
                )
    except Exception:
        logger.exception("otomatik not üretimi başarısız: chapter=%s", chapter_id)
    finally:
        _note_inflight.discard((tenant_id, chapter_id))


async def maybe_start_auto_notes(course_id: int, tenant_id: str) -> None:
    """Chapter için gerekli her şey hazır olduğunda not üretimini arka planda başlatır.

    Tetik: dersin pending/processing indexing_job'u YOK AND chapter'ın slaytı VAR
    AND chapter'ın notu YOK AND üretim zaten koşmuyor. Kota aşımında sessizce
    atlanır (loglanır) — bu bir arka plan tetiği, 402 döndürecek bir istek yok.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM indexing_jobs WHERE course_id = ? AND tenant_id = ? "
            "AND status IN ('pending', 'processing') LIMIT 1",
            (course_id, tenant_id),
        )
        if await cursor.fetchone() is not None:
            return
        cursor = await db.execute(
            "SELECT c.id FROM chapters c WHERE c.course_id = ? AND c.tenant_id = ? "
            "AND EXISTS (SELECT 1 FROM slides s WHERE s.chapter_id = c.id AND s.tenant_id = ?) "
            "AND NOT EXISTS (SELECT 1 FROM notes n WHERE n.chapter_id = c.id AND n.tenant_id = ?)",
            (course_id, tenant_id, tenant_id, tenant_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    for row in rows:
        chapter_id = dict(row)["id"]
        key = (tenant_id, chapter_id)
        if key in _note_inflight:
            continue
        try:
            await enforce_quota(tenant_id)
        except QuotaExceededError:
            logger.info(
                "otomatik not üretimi atlandı — kota aşıldı: tenant=%s chapter=%s",
                tenant_id,
                chapter_id,
            )
            continue
        _note_inflight.add(key)
        task = asyncio.create_task(_consume_auto_note(chapter_id, tenant_id))
        _note_tasks.add(task)
        task.add_done_callback(_note_tasks.discard)


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
