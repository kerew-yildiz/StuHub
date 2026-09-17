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
from ..services.export_service import PDF_VARIANTS, note_markdown_to_pdf
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


class NoteUpdateIn(BaseModel):
    content_md: str


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
    # Eski satırlarda citations_json boş liste olabilir ([]); NoteOut dict bekler —
    # dict olmayan değer boş dict'e indirgenir (gerçek üretim her zaman dict yazar).
    parsed_citations = json.loads(data["citations_json"] or "{}")
    data["citations_json"] = parsed_citations if isinstance(parsed_citations, dict) else {}
    data["topics_json"] = json.loads(data["topics_json"] or "[]")
    return NoteOut(**data)


@router.get("/chapters/{chapter_id}/notes/archive", response_model=list[NoteOut])
async def list_chapter_notes(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[NoteOut]:
    """Chapter'ın tüm kayıtlı notlarını yeniden eskiye döner (not arşivi).

    Yeni not üretimi eskilerin üzerine YAZMAZ — hepsi arşivde kalır;
    kullanıcı önceki sürümlere bu uç üzerinden erişir.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, content_md, citations_json, topics_json, "
            "generated_at, model_used FROM notes WHERE chapter_id = ? AND tenant_id = ? "
            "ORDER BY id DESC",
            (chapter_id, tenant_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    out: list[NoteOut] = []
    for row in rows:
        data = dict(row)
        parsed_citations = json.loads(data["citations_json"] or "{}")
        data["citations_json"] = parsed_citations if isinstance(parsed_citations, dict) else {}
        data["topics_json"] = json.loads(data["topics_json"] or "[]")
        out.append(NoteOut(**data))
    return out


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: int, payload: NoteUpdateIn, tenant_id: str = Depends(get_tenant_id)
) -> NoteOut:
    """Not içeriğini düzenler (yönerge §39 — kullanıcı emeği olan içerik düzenlenebilir)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE notes SET content_md = ? WHERE id = ? AND tenant_id = ?",
            (payload.content_md, note_id, tenant_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not bulunamadı")
        await db.commit()
        cursor = await db.execute(
            "SELECT id, chapter_id, content_md, citations_json, topics_json, "
            "generated_at, model_used FROM notes WHERE id = ? AND tenant_id = ?",
            (note_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Not bulunamadı")
    data = dict(row)
    parsed_citations = json.loads(data["citations_json"] or "{}")
    data["citations_json"] = parsed_citations if isinstance(parsed_citations, dict) else {}
    data["topics_json"] = json.loads(data["topics_json"] or "[]")
    return NoteOut(**data)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Notu siler (yönerge §39 — delete confirmation modal'ı frontend'de zorunlu)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM notes WHERE id = ? AND tenant_id = ?", (note_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not bulunamadı")
        await db.commit()
    finally:
        await db.close()


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
    note_id: int,
    format: str = "pdf",
    variant: str = "physical",
    tenant_id: str = Depends(get_tenant_id),
) -> Response:
    """Notu PDF ya da Markdown olarak indirir (Türkçe karakter destekli).

    PDF'te ``variant``: ``physical`` (baskı dostu, siyah logo, marka header'ı)
    ya da ``digital`` (StuHub koyu tasarım dili, cam efektli header).
    """
    if format not in ("pdf", "md"):
        raise HTTPException(status_code=422, detail="format 'pdf' veya 'md' olmalı")
    if format == "pdf" and variant not in PDF_VARIANTS:
        raise HTTPException(status_code=422, detail="variant 'physical' veya 'digital' olmalı")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.content_md, n.topics_json, c.title, co.name AS course_name FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "JOIN courses co ON co.id = c.course_id "
            "WHERE n.id = ? AND n.tenant_id = ?",
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

    document_title = f"{row['course_name']} · {row['title']}"
    # topics_json: konu başlıkları PDF'te yuvarlak konu kartı içinde basılır
    # (eşleşme export_service içinde yapılır; bozuk kayıt sessizce yok sayılır).
    try:
        topics = [str(item["topic"]) for item in json.loads(row["topics_json"] or "[]")]
    except (TypeError, ValueError, KeyError):
        topics = []
    pdf_bytes = note_markdown_to_pdf(
        row["content_md"], document_title, variant=variant, topics=topics
    )
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="stuhub-not-{note_id}-{variant}.pdf"'
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
