"""Ödev taslak koçu — puansız yapısal geri bildirim (Plan #41).

`routers/v2_tools.py`'deki `/courses/{course_id}/essays/grade` (final puanlama) ile
aynı gövdeyi (`essay_service`) paylaşır ama ayrı bir router dosyasında tutulur —
paralel geliştirme sırasında v2_tools.py'ye dokunmadan bağımsız kaydedilebilsin diye.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..quota import enforce_quota
from ..services.essay_service import EssayServiceError, review_draft

router = APIRouter(prefix="/api", tags=["essays"])


class DraftReviewIn(BaseModel):
    instructions: str = Field(min_length=1)
    rubric: str | None = None
    user_text: str


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


@router.post("/courses/{course_id}/essays/draft-review")
async def draft_review_homework(
    course_id: int, payload: DraftReviewIn, tenant_id: str = Depends(enforce_quota)
) -> dict:
    """Ödev taslağını puansız değerlendirir (tez/kanıt/zayıf bölüm geri bildirimi)."""
    db = await get_db()
    try:
        exists = await _course_exists(db, course_id, tenant_id)
    finally:
        await db.close()
    if not exists:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")

    try:
        return await review_draft(
            instructions=payload.instructions,
            user_text=payload.user_text,
            rubric=payload.rubric,
            course_id=course_id,
            tenant_id=tenant_id,
        )
    except EssayServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
