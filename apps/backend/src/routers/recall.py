"""Konuşarak tekrar — ses kaydını mevcut notun konularıyla karşılaştırır (Plan #47).

Yeni model indirmesi YOK: mevcut faster-whisper zinciri (`media_extractors.audio`,
Yetenek 11) kullanılır. LLM YOK — karşılaştırma `recall_service.compare_transcript`
ile saf kelime örtüşmesidir. Yüklenen ses dosyası geçici dizine yazılır, transkripsiyon
bitince silinir (materials.py'nin aksine kalıcı materyal olarak saklanmaz).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth import get_tenant_id
from ..config import settings
from ..db import get_db
from ..services import media_extractors
from ..services.media_extractors import transcript_to_text
from ..services.recall_service import compare_transcript

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["recall"])

# audio.py'nin desteklediği kayıt biçimleri (tarayıcı MediaRecorder çıktısı dahil)
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".ogg"}


async def _latest_note(db, chapter_id: int, tenant_id: str) -> dict | None:
    cursor = await db.execute(
        "SELECT n.topics_json FROM notes n "
        "JOIN chapters c ON c.id = n.chapter_id "
        "WHERE n.chapter_id = ? AND c.tenant_id = ? ORDER BY n.id DESC LIMIT 1",
        (chapter_id, tenant_id),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


@router.post("/chapters/{chapter_id}/recall")
async def spoken_recall(
    chapter_id: int, file: UploadFile = File(...), tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Ses kaydını çevirir, notun konularıyla örtüşmesini döner (LLM YOK)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=422, detail=f"Desteklenen ses uzantıları: {allowed}")

    db = await get_db()
    try:
        note = await _latest_note(db, chapter_id, tenant_id)
    finally:
        await db.close()
    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Bu bölüm için henüz not üretilmemiş — önce not oluşturup tekrar deneyin.",
        )

    tmp_dir = settings.data_dir / "recall_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"{uuid.uuid4().hex}{ext}"
    total = 0
    with dest.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            handle.write(chunk)
            total += len(chunk)
    if total == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Ses kaydı boş (0 bayt).")

    try:
        segments = await asyncio.to_thread(media_extractors.extract_for, "audio", str(dest))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        dest.unlink(missing_ok=True)

    transcript = transcript_to_text(segments)
    topics_meta = json.loads(note["topics_json"] or "[]")
    covered, missed = compare_transcript(transcript, topics_meta)

    return {"transcript": transcript, "covered_topics": covered, "missed_topics": missed}
