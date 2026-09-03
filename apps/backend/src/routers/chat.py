"""Materyale Sor (RAG chat) router'ı — SSE yanıt, geçmiş, temizlik (Faz V2.1)."""

from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db
from ..quota import enforce_quota
from ..services import llm_service
from ..services.chat_service import stream_chat_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    mode: Literal["direct", "socratic", "quiz"] = "direct"


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.post("/courses/{course_id}/chat")
async def send_chat_message(
    course_id: int, payload: ChatIn, tenant_id: str = Depends(enforce_quota)
) -> StreamingResponse:
    """Kullanıcı sorusunu atıflı yanıtlar; SSE: citations / delta / done / error."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
    finally:
        await db.close()

    async def event_stream():
        try:
            async for event in stream_chat_answer(
                course_id, payload.message, payload.mode, tenant_id
            ):
                yield _sse(event)
        except llm_service.LLMError as exc:
            yield _sse({"type": "error", "message": str(exc)})
        except Exception:
            logger.exception("chat yanıtı başarısız: course=%s", course_id)
            yield _sse(
                {
                    "type": "error",
                    "message": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
                }
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/courses/{course_id}/chat")
async def get_chat_history(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Dersin son 100 sohbet mesajını kronolojik sırayla döner."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        cursor = await db.execute(
            "SELECT id, role, content, citations_json, mode, created_at "
            "FROM (SELECT * FROM chat_messages WHERE course_id = ? AND tenant_id = ? "
            "ORDER BY id DESC LIMIT 100) ORDER BY id ASC",
            (course_id, tenant_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    messages = []
    for row in rows:
        data = dict(row)
        data["citations_json"] = json.loads(data["citations_json"] or "[]")
        messages.append(data)
    return {"messages": messages}


@router.delete("/courses/{course_id}/chat", status_code=204)
async def clear_chat_history(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> None:
    """Dersin sohbet geçmişini temizler."""
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")
        await db.execute(
            "DELETE FROM chat_messages WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        await db.commit()
    finally:
        await db.close()
