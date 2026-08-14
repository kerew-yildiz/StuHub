"""Quiz router'ı — üretim (SSE), okuma, anında feedback'li deneme (Faz 4)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db import get_db
from ..services.quiz_generator import generate_quiz_stream

router = APIRouter(prefix="/api", tags=["quizzes"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class AnswerIn(BaseModel):
    qid: str = Field(min_length=1)
    selected_index: int = Field(ge=0, le=3)


class AttemptIn(BaseModel):
    answers: list[AnswerIn]


def _flatten(questions_json: dict) -> list[tuple[str, dict]]:
    """Soruları (qid, question) düz listesine çevirir: qid = '<topic_idx>-<q_idx>'."""
    flattened: list[tuple[str, dict]] = []
    topics = questions_json.get("topics", [])
    for t_idx, topic in enumerate(topics):
        for q_idx, question in enumerate(topic.get("questions", [])):
            flattened.append((f"{t_idx}-{q_idx}", question))
    return flattened


@router.post("/chapters/{chapter_id}/quiz")
async def generate_chapter_quiz(chapter_id: int) -> StreamingResponse:
    """Bölüm quizi üretir; SSE akışı (status / done / error)."""
    async def event_stream():
        async for event in generate_quiz_stream(chapter_id):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chapters/{chapter_id}/quiz")
async def get_latest_quiz(chapter_id: int) -> dict | None:
    """Chapter'ın en güncel quizini döner (yoksa null)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, questions_json, created_at FROM quizzes "
            "WHERE chapter_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "chapter_id": chapter_id,
        "questions_json": json.loads(row["questions_json"]),
        "created_at": row["created_at"],
    }


@router.post("/quizzes/{quiz_id}/attempts")
async def submit_attempt(quiz_id: int, payload: AttemptIn) -> dict:
    """Cevapları değerlendirir; feedback üretim anında hazırlandığından LLM çağrısı YOK.

    Feedback: doğru → feedback_correct; yanlış → feedback_wrong + explanation + atıflar.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT questions_json FROM quizzes WHERE id = ?", (quiz_id,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Quiz bulunamadı")

    questions_json = json.loads(row["questions_json"])
    flattened = _flatten(questions_json)
    by_qid = {qid: question for qid, question in flattened}

    results = []
    correct_count = 0
    for answer in payload.answers:
        question = by_qid.get(answer.qid)
        if question is None:
            raise HTTPException(
                status_code=422, detail=f"Bilinmeyen soru: {answer.qid}"
            )
        correct = answer.selected_index == question["correct_index"]
        if correct:
            correct_count += 1
        results.append(
            {
                "qid": answer.qid,
                "question": question["question"],
                "selected_index": answer.selected_index,
                "correct_index": question["correct_index"],
                "correct": correct,
                "feedback": (
                    question["feedback_correct"] if correct else question["feedback_wrong"]
                ),
                "explanation": question["explanation"],
                "citations": question.get("citations", []),
                "options": question["options"],
            }
        )

    total = len(flattened)
    score = round(100 * correct_count / total) if total else 0

    feedback_json = {"results": results}
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO quiz_attempts (quiz_id, user_answers_json, score, feedback_json) "
            "VALUES (?, ?, ?, ?)",
            (
                quiz_id,
                json.dumps([a.model_dump() for a in payload.answers], ensure_ascii=False),
                score,
                json.dumps(feedback_json, ensure_ascii=False),
            ),
        )
        await db.commit()
        attempt_id = cursor.lastrowid
    finally:
        await db.close()

    return {
        "attempt_id": attempt_id,
        "score": score,
        "total": total,
        "correct_count": correct_count,
        "results": results,
    }


@router.get("/chapters/{chapter_id}/quizzes")
async def list_chapter_quizzes(chapter_id: int) -> list[dict]:
    """Chapter'ın TÜM quizlerini (yeniden eskiye) döner — geçmiş korunur."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, questions_json, created_at FROM quizzes "
            "WHERE chapter_id = ? ORDER BY id DESC",
            (chapter_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [
        {
            "id": row["id"],
            "chapter_id": chapter_id,
            "questions_json": json.loads(row["questions_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.delete("/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: int) -> None:
    """Quiz'i siler (denemeleriyle birlikte)."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Quiz bulunamadı")
        await db.commit()
    finally:
        await db.close()


@router.get("/quizzes/{quiz_id}/attempts")
async def list_quiz_attempts(quiz_id: int) -> list[dict]:
    """Quiz'in kayıtlı denemeleri (yeniden eskiye) — cevaplar kalıcıdır."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, score, feedback_json, created_at FROM quiz_attempts "
            "WHERE quiz_id = ? ORDER BY id DESC",
            (quiz_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [
        {
            "attempt_id": row["id"],
            "quiz_id": quiz_id,
            "score": row["score"],
            "created_at": row["created_at"],
            "feedback_json": json.loads(row["feedback_json"] or "{}"),
        }
        for row in rows
    ]


@router.delete("/quiz-attempts/{attempt_id}", status_code=204)
async def delete_quiz_attempt(attempt_id: int) -> None:
    """Bir denemeyi (cevapları) siler."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM quiz_attempts WHERE id = ?", (attempt_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Deneme bulunamadı")
        await db.commit()
    finally:
        await db.close()
