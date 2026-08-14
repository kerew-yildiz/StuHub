"""Not router'ı — üretim (SSE), kayıtlı not, kaynak erişimi (Faz 3.2/3.3)."""

from __future__ import annotations

import json
from pathlib import Path

import lancedb
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..db import get_db
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
async def generate_chapter_notes(chapter_id: int) -> StreamingResponse:
    """Not üretimini başlatır; SSE akışı: status / delta / done / error.

    Frontend `fetch` ile POST eder ve akışı okur (EventSource GET kısıtı yok).
    """
    async def event_stream():
        async for event in generate_notes_stream(chapter_id):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chapters/{chapter_id}/notes", response_model=NoteOut | None)
async def get_latest_note(chapter_id: int) -> NoteOut | None:
    """Chapter'ın en güncel notunu döner (yoksa null)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, content_md, citations_json, topics_json, "
            "generated_at, model_used FROM notes WHERE chapter_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id,),
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
async def resolve_citation(chunk_id: str) -> dict:
    """Chunk kimliğinden kaynak parçayı çözer (atıf pop-up'ı — Yetenek 06 §4)."""
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    for table_name in db.list_tables().tables or []:
        table = db.open_table(table_name)
        rows = table.to_arrow().to_pylist()
        for row in rows:
            if row["chunk_id"] == chunk_id:
                return {
                    "chunk_id": row["chunk_id"],
                    "course_id": row["course_id"],
                    "material_id": row["material_id"],
                    "text": row["text"],
                    "page": row["page"],
                    "slide": row["slide"],
                }
    raise HTTPException(status_code=404, detail="Kaynak parça bulunamadı")


@router.get("/materials/{material_id}/file")
async def material_file(material_id: int) -> FileResponse:
    """Materyal dosyası — Range destekli (pdfjs sayfa render'ı, Yetenek 06 §4)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT filepath FROM materials WHERE id = ?", (material_id,)
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
