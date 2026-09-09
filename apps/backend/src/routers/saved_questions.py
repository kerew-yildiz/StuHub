"""Kaydedilen sorular router'ı (Plan: kaydırmalı quiz #8).

Sözleşme:
- `POST   /api/feed/{feed_id}/save` → 201 {"saved": true}
- `DELETE /api/feed/{feed_id}/save` → 200 {"saved": false}
- `GET    /api/saved-questions`     → [{feed_id, question, options, correct_index,
  explanation, topic, chapter_id, chapter_title, course_id, course_name, saved_at}]

Kayıt idempotenttir: zaten kaydedilmiş bir soruyu tekrar kaydetmek/olmayan bir kaydı
silmek hata vermez. Doğru cevap burada SIZDIRILIR (feed'in aksine) — kullanıcı zaten
kendi kaydettiği soruyu tekrar gözden geçiriyor.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..services import feed_service

router = APIRouter(prefix="/api", tags=["saved-questions"])


class SavedToggleOut(BaseModel):
    saved: bool


class SavedQuestionOut(BaseModel):
    feed_id: int
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    topic: str | None = None
    chapter_id: int | None = None
    chapter_title: str
    course_id: int
    course_name: str
    saved_at: str


@router.post("/feed/{feed_id}/save", response_model=SavedToggleOut, status_code=201)
async def save_feed_question(
    feed_id: int, tenant_id: str = Depends(get_tenant_id)
) -> SavedToggleOut:
    """Soruyu kaydeder (idempotent). Soru bulunamaz/başka kiracıya aitse 404."""
    if not await feed_service.save_question(feed_id, tenant_id):
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    return SavedToggleOut(saved=True)


@router.delete("/feed/{feed_id}/save", response_model=SavedToggleOut)
async def unsave_feed_question(
    feed_id: int, tenant_id: str = Depends(get_tenant_id)
) -> SavedToggleOut:
    """Kaydı kaldırır (idempotent) — kayıtlı değilse de 200 döner."""
    await feed_service.unsave_question(feed_id, tenant_id)
    return SavedToggleOut(saved=False)


@router.get("/saved-questions", response_model=list[SavedQuestionOut])
async def list_saved_questions(
    tenant_id: str = Depends(get_tenant_id),
) -> list[SavedQuestionOut]:
    """Kaydedilen sorular — en yeni önce."""
    rows = await feed_service.list_saved(tenant_id)
    return [SavedQuestionOut(**row) for row in rows]
