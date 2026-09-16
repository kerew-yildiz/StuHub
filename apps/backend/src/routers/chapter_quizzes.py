"""Chapter düzeyindeki normal quiz API'si.

Kaydırarak Quiz feed'inden bağımsızdır: burada kalıcı `quizzes` kayıtları listelenir
ve tek bir quiz denemesi `quiz_attempts` tablosuna tek seferde yazılır.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db
from ..services import quiz_generator

router = APIRouter(prefix="/api", tags=["chapter-quizzes"])


class ChapterQuizQuestion(BaseModel):
    qid: str
    topic: str | None = None
    question: str
    options: list[str]
    difficulty: str | None = None


class ChapterQuizOut(BaseModel):
    id: int
    chapter_id: int
    created_at: str
    questions: list[ChapterQuizQuestion]


class ChapterQuizAnswer(BaseModel):
    qid: str
    selected_index: int = Field(ge=0, le=9)


class ChapterQuizAttemptIn(BaseModel):
    answers: list[ChapterQuizAnswer] = Field(min_length=1)


class ChapterQuizResult(BaseModel):
    qid: str
    question: str
    selected_index: int
    correct_index: int
    correct: bool
    explanation: str
    citations: list[Any] = []
    topic: str | None = None


class ChapterQuizAttemptOut(BaseModel):
    quiz_id: int
    score: float
    results: list[ChapterQuizResult]


def _question_rows(quiz_id: int, questions_json: dict) -> list[dict]:
    rows: list[dict] = []
    for topic_index, topic_data in enumerate(questions_json.get("topics", [])):
        topic = str(topic_data.get("topic") or "Genel")
        for question_index, question in enumerate(topic_data.get("questions", [])):
            rows.append({
                "qid": str(question.get("qid") or f"{topic_index}-{question_index}"),
                "topic": topic,
                "question": str(question.get("question") or ""),
                "options": [str(value) for value in question.get("options", [])],
                "difficulty": question.get("difficulty"),
                "correct_index": int(question.get("correct_index", 0)),
                "explanation": str(question.get("explanation") or ""),
                "citations": question.get("citations") or [],
                "quiz_id": quiz_id,
            })
    return rows


async def _quiz_for_tenant(quiz_id: int, tenant_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, questions_json, created_at FROM quizzes "
            "WHERE id = ? AND tenant_id = ?",
            (quiz_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return dict(row) if row else None


@router.get("/chapters/{chapter_id}/quizzes", response_model=list[ChapterQuizOut])
async def list_chapter_quizzes(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[ChapterQuizOut]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, chapter_id, questions_json, created_at FROM quizzes "
            "WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC",
            (chapter_id, tenant_id),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()

    result: list[ChapterQuizOut] = []
    for row in rows:
        data = json.loads(row["questions_json"] or "{}")
        questions = [ChapterQuizQuestion(**item) for item in _question_rows(row["id"], data)]
        result.append(ChapterQuizOut(
            id=int(row["id"]),
            chapter_id=int(row["chapter_id"]),
            created_at=str(row["created_at"]),
            questions=questions,
        ))
    return result


class ChapterQuizGenerateOut(BaseModel):
    id: int
    question_count: int


@router.post("/chapters/{chapter_id}/quizzes/generate", response_model=ChapterQuizGenerateOut)
async def generate_chapter_quiz(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> ChapterQuizGenerateOut:
    """Chapter için yeni bir quiz üretir (§40 '+ Quiz Oluştur').

    Mevcut notun konularından LLM ile parti üretir ve kalıcı bir `quizzes`
    kaydı yazar — feed havuzunu DOLDURMAZ, yalnızca chapter quiz listesine
    ekler. Not yoksa 409 döner (frontend empty-state'i ile uyumlu).
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise HTTPException(status_code=404, detail="Bölüm bulunamadı.")
    finally:
        await db.close()

    questions = await quiz_generator.generate_feed_batch(chapter_id, tenant_id, count=10)
    if not questions:
        raise HTTPException(
            status_code=409,
            detail="Quiz üretilemedi. Bu bölüm için önce not oluşturmalısın.",
        )

    grouped: dict[str, list[dict]] = {}
    for question in questions:
        topic = str(question.get("topic") or "Genel")
        grouped.setdefault(topic, []).append(question)
    questions_json = {
        "topics": [
            {"topic": topic, "questions": items}
            for topic, items in grouped.items()
        ]
    }

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await db.commit()
        quiz_id = cursor.lastrowid
    finally:
        await db.close()
    if quiz_id is None:
        raise HTTPException(status_code=500, detail="Quiz kaydedilemedi.")

    return ChapterQuizGenerateOut(id=int(quiz_id), question_count=len(questions))


@router.post("/quizzes/{quiz_id}/attempts", response_model=ChapterQuizAttemptOut)
async def submit_chapter_quiz(
    quiz_id: int,
    payload: ChapterQuizAttemptIn,
    tenant_id: str = Depends(get_tenant_id),
) -> ChapterQuizAttemptOut:
    row = await _quiz_for_tenant(quiz_id, tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Quiz bulunamadı")

    data = json.loads(row["questions_json"] or "{}")
    questions = {item["qid"]: item for item in _question_rows(quiz_id, data)}
    results: list[ChapterQuizResult] = []
    correct_count = 0
    for answer in payload.answers:
        question = questions.get(answer.qid)
        if question is None:
            continue
        selected = answer.selected_index
        correct_index = question["correct_index"]
        correct = selected == correct_index
        if correct:
            correct_count += 1
        results.append(ChapterQuizResult(
            qid=answer.qid,
            question=question["question"],
            selected_index=selected,
            correct_index=correct_index,
            correct=correct,
            explanation=question["explanation"],
            citations=question["citations"],
            topic=question["topic"],
        ))

    if not results:
        raise HTTPException(status_code=422, detail="Geçerli quiz cevabı bulunamadı")

    score = correct_count / len(results) * 100
    db = await get_db()
    try:
        feedback = {"results": [item.model_dump() for item in results]}
        answers = [
            {"qid": item.qid, "selected_index": item.selected_index}
            for item in results
        ]
        await db.execute(
            "INSERT INTO quiz_attempts "
            "(tenant_id, quiz_id, user_answers_json, score, feedback_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                tenant_id,
                quiz_id,
                json.dumps(answers, ensure_ascii=False),
                score,
                json.dumps(feedback, ensure_ascii=False),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return ChapterQuizAttemptOut(quiz_id=quiz_id, score=score, results=results)
