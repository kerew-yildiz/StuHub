"""Flashcard router'ı — üretim (SSE), set listesi, due kuyruğu, SM-2 review (Yetenek 09)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db
from ..quota import enforce_quota
from ..services import srs, streak_service
from ..services.flashcard_generator import generate_flashcards_stream

router = APIRouter(prefix="/api", tags=["flashcards"])

VALID_RATINGS = ("again", "hard", "good", "easy")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class ReviewIn(BaseModel):
    card_index: int
    rating: str


@router.post("/chapters/{chapter_id}/flashcards")
async def generate_chapter_flashcards(
    chapter_id: int, tenant_id: str = Depends(enforce_quota)
) -> StreamingResponse:
    """Bölüm flashcard'larını üretir; SSE akışı (status / done / error)."""

    async def event_stream():
        async for event in generate_flashcards_stream(chapter_id, tenant_id):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chapters/{chapter_id}/flashcard-sets")
async def list_chapter_flashcard_sets(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[dict]:
    """Chapter'ın TÜM flashcard setlerini (yeniden eskiye) döner — geçmiş korunur."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, cards_json, created_at, model_used "
            "FROM flashcard_sets WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC",
            (chapter_id, tenant_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [
        {
            "id": row["id"],
            "chapter_id": chapter_id,
            "cards_json": json.loads(row["cards_json"] or "[]"),
            "card_count": len(json.loads(row["cards_json"] or "[]")),
            "created_at": row["created_at"],
            "model_used": row["model_used"],
        }
        for row in rows
    ]


@router.get("/flashcard-sets/{set_id}")
async def get_flashcard_set(set_id: int, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Tek bir flashcard setini döner (yoksa 404)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, chapter_id, cards_json, created_at, model_used "
            "FROM flashcard_sets WHERE id = ? AND tenant_id = ?",
            (set_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Flashcard seti bulunamadı")
    return {
        "id": row["id"],
        "course_id": row["course_id"],
        "chapter_id": row["chapter_id"],
        "cards_json": json.loads(row["cards_json"] or "[]"),
        "card_count": len(json.loads(row["cards_json"] or "[]")),
        "created_at": row["created_at"],
        "model_used": row["model_used"],
    }


@router.delete("/flashcard-sets/{set_id}", status_code=204)
async def delete_flashcard_set(set_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Flashcard setini siler (review'ları cascade)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM flashcard_sets WHERE id = ? AND tenant_id = ?", (set_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Flashcard seti bulunamadı")
        await db.commit()
    finally:
        await db.close()


@router.get("/courses/{course_id}/flashcards/due")
async def due_flashcards(
    course_id: int, limit: int = 20, tenant_id: str = Depends(get_tenant_id)
) -> list[dict]:
    """Dersin due kuyruğu: vadesi geçenler önce, sonra yeni kartlar (Yetenek 09 §5)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, cards_json FROM flashcard_sets "
            "WHERE course_id = ? AND tenant_id = ? ORDER BY id ASC",
            (course_id, tenant_id),
        )
        set_rows = await cursor.fetchall()
        set_ids = [row["id"] for row in set_rows]
        reviews: dict[tuple[int, int], dict] = {}
        if set_ids:
            cursor = await db.execute(
                "SELECT set_id, card_index, ease_factor, interval_days, repetitions, "
                "due_at, last_rating FROM card_reviews "
                "WHERE set_id IN (SELECT value FROM json_each(?)) AND tenant_id = ?",
                (json.dumps(set_ids), tenant_id),
            )
            for row in await cursor.fetchall():
                reviews[(row["set_id"], row["card_index"])] = dict(row)
    finally:
        await db.close()

    now = datetime.now(UTC)
    overdue: list[dict] = []
    fresh: list[dict] = []

    for row in set_rows:
        set_id = row["id"]
        cards = json.loads(row["cards_json"] or "[]")
        for card_index, card in enumerate(cards):
            review = reviews.get((set_id, card_index))
            if review is None:
                fresh.append(
                    {"set_id": set_id, "card_index": card_index, "card": card,
                     "review": None, "due": True}
                )
                continue
            due_at = review.get("due_at")
            due = False
            if due_at:
                try:
                    due = datetime.fromisoformat(due_at) <= now
                except ValueError:
                    due = False
            if due:
                overdue.append(
                    {
                        "set_id": set_id,
                        "card_index": card_index,
                        "card": card,
                        "review": {
                            "ease_factor": review["ease_factor"],
                            "interval_days": review["interval_days"],
                            "repetitions": review["repetitions"],
                            "due_at": due_at,
                            "last_rating": review["last_rating"],
                        },
                        "due": True,
                    }
                )

    overdue.sort(key=lambda item: item["review"]["due_at"] or "")
    fresh.sort(key=lambda item: (item["set_id"], item["card_index"]))
    return (overdue + fresh)[:limit]


@router.post("/flashcard-sets/{set_id}/reviews")
async def submit_review(
    set_id: int, payload: ReviewIn, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """SM-2 durumunu günceller; due_at'i hesaplar; activity_log'a 'flashcard' yazar."""
    if payload.rating not in VALID_RATINGS:
        raise HTTPException(
            status_code=422,
            detail="Geçersiz tekrar puanı — 'again', 'hard', 'good' veya 'easy' olmalı.",
        )

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id, cards_json FROM flashcard_sets WHERE id = ? AND tenant_id = ?",
            (set_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Flashcard seti bulunamadı")

    cards = json.loads(row["cards_json"] or "[]")
    if payload.card_index < 0 or payload.card_index >= len(cards):
        raise HTTPException(status_code=404, detail="Kart bulunamadı")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT ease_factor, interval_days, repetitions FROM card_reviews "
            "WHERE set_id = ? AND card_index = ? AND tenant_id = ?",
            (set_id, payload.card_index, tenant_id),
        )
        review = await cursor.fetchone()

        if review is None:
            ease_factor = srs.INITIAL_STATE["ease_factor"]
            interval_days = srs.INITIAL_STATE["interval_days"]
            repetitions = srs.INITIAL_STATE["repetitions"]
        else:
            ease_factor = review["ease_factor"]
            interval_days = review["interval_days"]
            repetitions = review["repetitions"]

        new_ease, new_interval, new_reps = srs.next_review_state(
            ease_factor, interval_days, repetitions, payload.rating
        )
        due_at = datetime.now(UTC) + timedelta(days=new_interval)
        due_at_iso = due_at.isoformat()

        await db.execute(
            "INSERT INTO card_reviews "
            "(tenant_id, set_id, card_index, ease_factor, interval_days, repetitions, due_at, "
            "last_rating, reviewed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(set_id, card_index) DO UPDATE SET "
            "ease_factor = excluded.ease_factor, "
            "interval_days = excluded.interval_days, "
            "repetitions = excluded.repetitions, "
            "due_at = excluded.due_at, "
            "last_rating = excluded.last_rating, "
            "reviewed_at = CURRENT_TIMESTAMP",
            (tenant_id, set_id, payload.card_index, new_ease, new_interval, new_reps,
             due_at_iso, payload.rating),
        )
        await db.commit()
    finally:
        await db.close()

    await streak_service.log_activity("flashcard", row["course_id"], tenant_id=tenant_id)

    return {
        "set_id": set_id,
        "card_index": payload.card_index,
        "ease_factor": new_ease,
        "interval_days": new_interval,
        "repetitions": new_reps,
        "due_at": due_at_iso,
        "last_rating": payload.rating,
    }
