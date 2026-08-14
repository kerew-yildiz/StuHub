"""Genel quiz router'ı — üretim (SSE), okuma (answer_key'siz), 4 tipli değerlendirme (Faz 5)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..db import get_db
from ..services.essay_grader import EssayGradeError, grade_essay
from ..services.fib_utils import fib_is_correct
from ..services.overall_generator import generate_overall_quiz_stream

router = APIRouter(prefix="/api", tags=["overall-quiz"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class OverallAnswerIn(BaseModel):
    qid: int
    value: int | str


class OverallAttemptIn(BaseModel):
    answers: list[OverallAnswerIn]


@router.post("/courses/{course_id}/overall-quiz")
async def generate_overall_quiz(course_id: int) -> StreamingResponse:
    """Ders seviyesinde 55 soruluk genel quiz üretir; SSE akışı."""
    async def event_stream():
        async for event in generate_overall_quiz_stream(course_id):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _strip_answers(questions_json: dict) -> dict:
    """answer_keys'i servis etmez; frontend yalnızca answer_key_ref görür (Yetenek 04 §6)."""
    public = dict(questions_json)
    public.pop("answer_keys", None)
    return public


@router.get("/courses/{course_id}/overall-quiz")
async def get_latest_overall_quiz(course_id: int) -> dict | None:
    """Dersin en güncel genel quizini döner (cevap anahtarları SIZMAZ)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, questions_json, created_at FROM overall_quizzes "
            "WHERE course_id = ? ORDER BY id DESC LIMIT 1",
            (course_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        return None
    questions_json = json.loads(row["questions_json"])
    return {
        "id": row["id"],
        "course_id": course_id,
        "questions_json": _strip_answers(questions_json),
        "created_at": row["created_at"],
    }


def _numbered_sources(question: dict) -> str:
    citations = question.get("citations", [])
    return "\n".join(
        f"[{i}] (sayfa {c.get('page') or '-'} / slide {c.get('slide') or '-'}) "
        f"{c.get('quote') or c.get('chunk_id') or 'kaynak'}"
        for i, c in enumerate(citations, start=1)
    )


@router.post("/overall-quizzes/{quiz_id}/attempts")
async def submit_overall_attempt(quiz_id: int, payload: OverallAttemptIn) -> dict:
    """55 soruyu değerlendirir; mcq/tf/fib anında, açık uçlu Essay Grader (LLM) ile."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id, questions_json FROM overall_quizzes WHERE id = ?", (quiz_id,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Genel quiz bulunamadı")

    course_id = row["course_id"]
    questions_json = json.loads(row["questions_json"])
    questions = questions_json.get("questions", [])
    answer_keys = questions_json.get("answer_keys", {})

    by_qid = {i: q for i, q in enumerate(questions)}
    closed_correct = 0
    open_total = 0.0
    results: list[dict] = []

    for answer in payload.answers:
        question = by_qid.get(answer.qid)
        if question is None:
            raise HTTPException(status_code=422, detail=f"Bilinmeyen soru: {answer.qid}")
        qtype = question["type"]

        if qtype in ("mcq", "tf"):
            value = answer.value if isinstance(answer.value, int) else -1
            if qtype == "mcq":
                correct = value == question["correct_index"]
            else:  # tf: 0 = Yanlış, 1 = Doğru
                correct = (value == 1) == question["answer"]
            if correct:
                closed_correct += 1
            results.append(
                {
                    "qid": answer.qid,
                    "type": qtype,
                    "question": question.get("question") or question.get("statement", ""),
                    "correct": correct,
                    "feedback": (
                        question["feedback_correct"] if correct else question["feedback_wrong"]
                    ),
                    "explanation": question.get("explanation", ""),
                    "citations": question.get("citations", []),
                    # Önizleme için tam içerik (madde 7)
                    "options": question.get("options"),
                    "correct_index": question.get("correct_index"),
                    "selected_index": value if qtype == "mcq" else None,
                    "statement": question.get("statement"),
                    "answer": question.get("answer"),
                    "selected_tf": value if qtype == "tf" else None,
                }
            )
        elif qtype == "fib":
            user_text = answer.value if isinstance(answer.value, str) else ""
            correct = fib_is_correct(user_text, question["accepted_answers"])
            if correct:
                closed_correct += 1
            results.append(
                {
                    "qid": answer.qid,
                    "type": qtype,
                    "question": question["text"],
                    "correct": correct,
                    "feedback": (
                        question["feedback_correct"] if correct else question["feedback_wrong"]
                    ),
                    "explanation": question.get("explanation", ""),
                    "citations": question.get("citations", []),
                    "accepted_answers": question["accepted_answers"] if not correct else [],
                    "user_answer": user_text,
                }
            )
        else:  # open
            user_text = answer.value if isinstance(answer.value, str) else ""
            ref = question.get("answer_key_ref", "")
            answer_key = answer_keys.get(ref, {"points": []})
            try:
                grade = await grade_essay(
                    question=question.get("question", ""),
                    answer_key=answer_key,
                    numbered_sources=_numbered_sources(question),
                    user_answer=user_text,
                    course_id=course_id,
                )
            except EssayGradeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            open_total += grade["score"]
            results.append(
                {
                    "qid": answer.qid,
                    "type": qtype,
                    "question": question.get("question", ""),
                    "score": grade["score"],
                    "correct": grade["score"] >= 5,
                    "user_answer": user_text,
                    "grade": {
                        k: grade[k]
                        for k in (
                            "correct",
                            "missing",
                            "incorrect",
                            "unnecessary",
                            "explanation",
                            "ideal_answer",
                        )
                    },
                }
            )

    closed_count = sum(1 for q in questions if q["type"] in ("mcq", "tf", "fib"))
    # Puanlama (madde 1): mcq/tf/fib 1'er puan (toplam 50) + açık uçlu 5×10 (toplam 50) = 100
    score = closed_correct + open_total
    score = max(0, min(100, score))

    score_json = {
        "score": score,
        "closed_correct": closed_correct,
        "closed_total": closed_count,
        "open_total": round(open_total, 1),
        "results": results,
    }

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO overall_attempts (overall_quiz_id, answers_json, score_json) "
            "VALUES (?, ?, ?)",
            (
                quiz_id,
                json.dumps([a.model_dump() for a in payload.answers], ensure_ascii=False),
                json.dumps(score_json, ensure_ascii=False),
            ),
        )
        await db.commit()
        attempt_id = cursor.lastrowid
    finally:
        await db.close()

    return {"attempt_id": attempt_id, **score_json}


@router.get("/courses/{course_id}/overall-quizzes")
async def list_course_overall_quizzes(course_id: int) -> list[dict]:
    """Dersin TÜM genel quizlerini (yeniden eskiye) döner — answer_key'ler SIZMAZ."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, questions_json, created_at FROM overall_quizzes "
            "WHERE course_id = ? ORDER BY id DESC",
            (course_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [
        {
            "id": row["id"],
            "course_id": course_id,
            "questions_json": _strip_answers(json.loads(row["questions_json"])),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.delete("/overall-quizzes/{quiz_id}", status_code=204)
async def delete_overall_quiz(quiz_id: int) -> None:
    """Genel quiz'i siler (denemeleriyle birlikte)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM overall_quizzes WHERE id = ?", (quiz_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Genel quiz bulunamadı")
        await db.commit()
    finally:
        await db.close()


@router.get("/overall-quizzes/{quiz_id}/attempts")
async def list_overall_attempts(quiz_id: int) -> list[dict]:
    """Genel quiz'in kayıtlı denemeleri (yeniden eskiye) — cevaplar kalıcıdır."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, score_json, created_at FROM overall_attempts "
            "WHERE overall_quiz_id = ? ORDER BY id DESC",
            (quiz_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [
        {
            "attempt_id": row["id"],
            "overall_quiz_id": quiz_id,
            "created_at": row["created_at"],
            "score_json": json.loads(row["score_json"] or "{}"),
        }
        for row in rows
    ]


@router.delete("/overall-attempts/{attempt_id}", status_code=204)
async def delete_overall_attempt(attempt_id: int) -> None:
    """Bir genel quiz denemesini (cevapları) siler."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM overall_attempts WHERE id = ?", (attempt_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Deneme bulunamadı")
        await db.commit()
    finally:
        await db.close()
