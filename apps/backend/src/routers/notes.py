"""Not router'ı — üretim (SSE), kayıtlı not, kaynak erişimi (Faz 3.2/3.3)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db
from ..quota import enforce_quota
from ..services import retrieval
from ..services.export_service import note_markdown_to_pdf
from ..services.note_generator import generate_notes_stream

router = APIRouter(prefix="/api", tags=["notes"])


class NoteOut(BaseModel):
    id: int
    chapter_id: int
    content_md: str
    citations_json: dict
    topics_json: list
    generated_at: str
    model_used: str | None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chapters/{chapter_id}/notes")
async def generate_chapter_notes(
    chapter_id: int, tenant_id: str = Depends(enforce_quota)
) -> StreamingResponse:
    """Not üretimini başlatır; SSE akışı: status / delta / done / error.

    Frontend `fetch` ile POST eder ve akışı okur (EventSource GET kısıtı yok).
    """
    async def event_stream():
        async for event in generate_notes_stream(chapter_id, tenant_id):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chapters/{chapter_id}/notes", response_model=NoteOut | None)
async def get_latest_note(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> NoteOut | None:
    """Chapter'ın en güncel notunu döner (yoksa null)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, content_md, citations_json, topics_json, "
            "generated_at, model_used FROM notes WHERE chapter_id = ? AND tenant_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (chapter_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        return None
    data = dict(row)
    data["citations_json"] = json.loads(data["citations_json"] or "{}")
    data["topics_json"] = json.loads(data["topics_json"] or "[]")
    return NoteOut(**data)


@router.get("/citations/{chunk_id}")
async def resolve_citation(chunk_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Chunk kimliğinden kaynak parçayı çözer (atıf pop-up'ı — Yetenek 06 §4).

    `chunk_id` materyal kimliğini taşıdığı için parça döndürülmeden ÖNCE o
    materyalin istek sahibi kiracıya ait olduğu doğrulanır. Bu kontrol olmadan uç,
    kimliği doğrulanmış herhangi bir kullanıcıya başka kiracıların materyal metnini
    açıyordu. Sahibi olmayan/var olmayan kimlikler aynı 404'ü alır — varlık bilgisi
    de sızdırılmaz.
    """
    material_id = retrieval.parse_material_id(chunk_id)
    if material_id is None:
        raise HTTPException(status_code=404, detail="Kaynak parça bulunamadı")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id FROM materials WHERE id = ? AND tenant_id = ?",
            (material_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Kaynak parça bulunamadı")

    # LanceDB erişimi bloklayıcıdır (senkron I/O) — event loop'u tutmasın.
    chunk = await asyncio.to_thread(retrieval.get_chunk, row["course_id"], chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Kaynak parça bulunamadı")
    return chunk


@router.get("/notes/{note_id}/export")
async def export_note(
    note_id: int, format: str = "pdf", tenant_id: str = Depends(get_tenant_id)
) -> Response:
    """Notu PDF (varsayılan) ya da Markdown olarak indirir (Türkçe karakter destekli)."""
    if format not in ("pdf", "md"):
        raise HTTPException(status_code=422, detail="format 'pdf' veya 'md' olmalı")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.content_md, c.title FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id WHERE n.id = ? AND n.tenant_id = ?",
            (note_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Not bulunamadı")

    if format == "md":
        from ..services.export_service import note_markdown_to_md

        content = note_markdown_to_md(row["title"], row["content_md"])
        return Response(
            content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="stuhub-not-{note_id}.md"'
            },
        )

    pdf_bytes = note_markdown_to_pdf(row["content_md"])
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="stuhub-not-{note_id}.pdf"'
        },
    )


@router.get("/materials/{material_id}/file")
async def material_file(
    material_id: int, tenant_id: str = Depends(get_tenant_id)
) -> FileResponse:
    """Materyal dosyası — Range destekli (pdfjs sayfa render'ı, Yetenek 06 §4)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT filepath FROM materials WHERE id = ? AND tenant_id = ?",
            (material_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Materyal bulunamadı")
    path = Path(row["filepath"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Kaynak dosya bulunamadı")
    return FileResponse(path, media_type="application/pdf")
