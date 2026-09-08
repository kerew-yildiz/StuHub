"""Sınav geri sayım planlayıcısı (Plan #9) + unutma eğrisi (Plan #12) + sınav simülasyonu
(Plan #35) + sınav sonrası muhasebe (Plan #44) uçları.

Geri sayım/unutma eğrisi tamamen deterministik: hesap `services/srs.py`'deki saf
fonksiyonlarda, bu katman yalnızca kiracı filtreli SQL + JSON şekillendirme yapar, LLM
çağrısı yok. Sınav simülasyonu mevcut 55 soruluk genel quiz motorunu (`overall_generator`)
`mode='exam'` ile çağırır; sınav sonrası muhasebe özeti için tek bir LLM çağrısı
(`postmortem_service.summarize_postmortem`) yapılır — ikisi de `enforce_quota` kullanır.

`exams.postmortem_json`: `{"items": [...], "summary": str, "created_at": iso}` — Plan #44.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db
from ..quota import enforce_quota
from ..services import srs
from ..services.overall_generator import generate_overall_quiz_stream
from ..services.postmortem_service import PostmortemSummaryError, summarize_postmortem

router = APIRouter(prefix="/api", tags=["exams"])

DEFAULT_TOPIC = "Genel"
DEFAULT_HORIZON_DAYS = 30
MAX_HORIZON_DAYS = 180
RETENTION_SAMPLES = 9


class ExamIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    exam_date: date
    chapter_ids: list[int] = Field(default_factory=list)


class ExamOut(BaseModel):
    id: int
    course_id: int
    title: str
    exam_date: str
    chapter_ids: list[int]
    days_left: int
    created_at: str


class PlanCard(BaseModel):
    set_id: int
    card_index: int
    topic: str
    front: str


class PlanDay(BaseModel):
    date: str
    card_count: int
    cards: list[PlanCard]


class ExamPlanOut(BaseModel):
    exam: ExamOut
    total_cards: int
    days: list[PlanDay]


class RetentionPoint(BaseModel):
    day: int
    retention: float


class TopicRetention(BaseModel):
    topic: str
    card_count: int
    reviewed_count: int
    current: float
    points: list[RetentionPoint]


class RetentionOut(BaseModel):
    course_id: int
    horizon_days: int
    generated_at: str
    topics: list[TopicRetention]


def _placeholders(count: int) -> str:
    """`?` yer tutucu listesi — değerler her zaman parametre olarak geçer."""
    return ", ".join("?" * count)


def _iso_date(value: object) -> str:
    """Tarih kolonunu 'YYYY-MM-DD'ye indirger (SQLite metin / Postgres ISO)."""
    return str(value)[:10]


def _exam_out(row, today: date) -> ExamOut:
    exam_date = _iso_date(row["exam_date"])
    return ExamOut(
        id=row["id"],
        course_id=row["course_id"],
        title=row["title"],
        exam_date=exam_date,
        chapter_ids=json.loads(row["scope_json"] or "[]"),
        days_left=(date.fromisoformat(exam_date) - today).days,
        created_at=str(row["created_at"]),
    )


async def _require_course(db, course_id: int, tenant_id: str) -> None:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")


async def _load_cards(
    db, course_id: int, tenant_id: str, chapter_ids: list[int]
) -> list[dict]:
    """Dersin (istenirse yalnız kapsam chapter'larının) kartları + SM-2 durumları.

    Dönen her öğe: card_id, set_id, card_index, topic, front, due_at, ease_factor,
    interval_days, reviewed_at. Hiç tekrar edilmemiş kartta tekrar alanları None/0.
    `answer_key`/`back` gibi cevap alanları BİLİNÇLİ olarak dışarı verilmez.
    """
    sql = (
        "SELECT id, cards_json FROM flashcard_sets "
        "WHERE course_id = ? AND tenant_id = ?"
    )
    params: list[object] = [course_id, tenant_id]
    if chapter_ids:
        sql += f" AND chapter_id IN ({_placeholders(len(chapter_ids))})"
        params.extend(chapter_ids)
    sql += " ORDER BY id ASC"

    cursor = await db.execute(sql, tuple(params))
    set_rows = await cursor.fetchall()
    set_ids = [row["id"] for row in set_rows]

    reviews: dict[tuple[int, int], dict] = {}
    if set_ids:
        cursor = await db.execute(
            "SELECT set_id, card_index, ease_factor, interval_days, due_at, reviewed_at "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
            f"FROM card_reviews WHERE tenant_id = ? AND set_id IN ({_placeholders(len(set_ids))})",
            (tenant_id, *set_ids),
        )
        for row in await cursor.fetchall():
            reviews[(row["set_id"], row["card_index"])] = dict(row)

    cards: list[dict] = []
    for row in set_rows:
        set_id = row["id"]
        for card_index, card in enumerate(json.loads(row["cards_json"] or "[]")):
            review = reviews.get((set_id, card_index)) or {}
            cards.append(
                {
                    "card_id": f"{set_id}:{card_index}",
                    "set_id": set_id,
                    "card_index": card_index,
                    "topic": (
                        (card.get("topic") or DEFAULT_TOPIC)
                        if isinstance(card, dict)
                        else DEFAULT_TOPIC
                    ),
                    "front": (card.get("front") or "") if isinstance(card, dict) else "",
                    "due_at": review.get("due_at"),
                    "ease_factor": review.get("ease_factor") or srs.MAX_EASE,
                    "interval_days": review.get("interval_days") or 0.0,
                    "reviewed_at": review.get("reviewed_at"),
                }
            )
    return cards


@router.post("/courses/{course_id}/exams", response_model=ExamOut, status_code=201)
async def create_exam(
    course_id: int, item: ExamIn, tenant_id: str = Depends(get_tenant_id)
) -> ExamOut:
    """Ders için sınav kaydı açar; kapsam chapter'ları aynı derse ait olmalıdır."""
    db = await get_db()
    try:
        await _require_course(db, course_id, tenant_id)

        chapter_ids = sorted(set(item.chapter_ids))
        if chapter_ids:
            cursor = await db.execute(
                "SELECT id FROM chapters WHERE course_id = ? AND tenant_id = ? "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"AND id IN ({_placeholders(len(chapter_ids))})",
                (course_id, tenant_id, *chapter_ids),
            )
            found = {row["id"] for row in await cursor.fetchall()}
            if found != set(chapter_ids):
                raise HTTPException(
                    status_code=422,
                    detail="Sınav kapsamındaki bölümler bu derse ait değil.",
                )

        cursor = await db.execute(
            "INSERT INTO exams (tenant_id, course_id, title, exam_date, scope_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                tenant_id,
                course_id,
                item.title,
                item.exam_date.isoformat(),
                json.dumps(chapter_ids),
            ),
        )
        await db.commit()
        exam_id = cursor.lastrowid
        if exam_id is None:
            raise RuntimeError("sınav kimliği alınamadı")

        cursor = await db.execute(
            "SELECT id, course_id, title, exam_date, scope_json, created_at "
            "FROM exams WHERE id = ? AND tenant_id = ?",
            (exam_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise RuntimeError("oluşturulan sınav satırı okunamadı")
    return _exam_out(row, datetime.now(UTC).date())


@router.get("/courses/{course_id}/exams", response_model=list[ExamOut])
async def list_exams(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[ExamOut]:
    """Dersin sınavları — tarihe göre yakından uzağa."""
    db = await get_db()
    try:
        await _require_course(db, course_id, tenant_id)
        cursor = await db.execute(
            "SELECT id, course_id, title, exam_date, scope_json, created_at FROM exams "
            "WHERE course_id = ? AND tenant_id = ? ORDER BY exam_date ASC, id ASC",
            (course_id, tenant_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    today = datetime.now(UTC).date()
    return [_exam_out(row, today) for row in rows]


@router.delete("/exams/{exam_id}", status_code=204)
async def delete_exam(exam_id: int, tenant_id: str = Depends(get_tenant_id)) -> None:
    """Sınav kaydını siler."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM exams WHERE id = ? AND tenant_id = ?", (exam_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sınav bulunamadı")
        await db.commit()
    finally:
        await db.close()


@router.get("/exams/{exam_id}/plan", response_model=ExamPlanOut)
async def exam_plan(exam_id: int, tenant_id: str = Depends(get_tenant_id)) -> ExamPlanOut:
    """Sınava kadarki günlük çalışma planı — `srs.compress_to_deadline` sonucu."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, title, exam_date, scope_json, created_at "
            "FROM exams WHERE id = ? AND tenant_id = ?",
            (exam_id, tenant_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Sınav bulunamadı")
        exam = _exam_out(row, datetime.now(UTC).date())
        cards = await _load_cards(db, exam.course_id, tenant_id, exam.chapter_ids)
    finally:
        await db.close()

    today = datetime.now(UTC).date()
    distribution = srs.compress_to_deadline(cards, date.fromisoformat(exam.exam_date), today)
    by_id = {card["card_id"]: card for card in cards}

    days = [
        PlanDay(
            date=day,
            card_count=len(card_ids),
            cards=[
                PlanCard(
                    set_id=by_id[card_id]["set_id"],
                    card_index=by_id[card_id]["card_index"],
                    topic=by_id[card_id]["topic"],
                    front=by_id[card_id]["front"],
                )
                for card_id in card_ids
            ],
        )
        for day, card_ids in sorted(distribution.items())
    ]
    return ExamPlanOut(
        exam=exam,
        total_cards=sum(day.card_count for day in days),
        days=days,
    )


@router.get("/courses/{course_id}/retention", response_model=RetentionOut)
async def course_retention(
    course_id: int,
    days: int = Query(default=DEFAULT_HORIZON_DAYS, ge=1, le=MAX_HORIZON_DAYS),
    tenant_id: str = Depends(get_tenant_id),
) -> RetentionOut:
    """Konu bazlı unutma eğrisi — `srs.retention_estimate` serisi (bugün → +days)."""
    db = await get_db()
    try:
        await _require_course(db, course_id, tenant_id)
        cards = await _load_cards(db, course_id, tenant_id, [])
    finally:
        await db.close()

    now = datetime.now(UTC)
    offsets = sorted(
        {round(index * days / (RETENTION_SAMPLES - 1)) for index in range(RETENTION_SAMPLES)}
    )

    by_topic: dict[str, list[dict]] = {}
    for card in cards:
        by_topic.setdefault(card["topic"], []).append(card)

    topics: list[TopicRetention] = []
    for topic, topic_cards in by_topic.items():
        points: list[RetentionPoint] = []
        for offset in offsets:
            moment = now + timedelta(days=offset)
            total = sum(
                srs.retention_estimate(
                    card["ease_factor"], card["interval_days"], card["reviewed_at"], moment
                )
                for card in topic_cards
            )
            points.append(
                RetentionPoint(day=offset, retention=round(total / len(topic_cards), 4))
            )
        topics.append(
            TopicRetention(
                topic=topic,
                card_count=len(topic_cards),
                reviewed_count=sum(1 for card in topic_cards if card["reviewed_at"]),
                current=points[0].retention,
                points=points,
            )
        )

    # En zayıf konu başta — arayüz ilk sırada "soğumuş" konuyu göstersin.
    topics.sort(key=lambda item: (item.current, item.topic))
    return RetentionOut(
        course_id=course_id,
        horizon_days=days,
        generated_at=now.isoformat(),
        topics=topics,
    )


# ── sınav simülasyonu (Plan #35) ─────────────────────────────────────────────


@router.post("/courses/{course_id}/exams/{exam_id}/simulate")
async def simulate_exam(
    course_id: int, exam_id: int, tenant_id: str = Depends(enforce_quota)
) -> StreamingResponse:
    """Sınav simülasyonu — mevcut 55 soruluk genel quiz motorunu `mode='exam'` ile çalıştırır.

    Aynı SSE akışı (`generate_overall_quiz_stream`); tek fark üretilen `overall_quizzes`
    kaydının bu sınava bağlanması ve `done` olayındaki sorulardan cevabı açığa çıkaran
    alanların (`correct_index`/`answer`/`accepted_answers`/`feedback_*`/`explanation`)
    süzülmesi — sonuç yalnızca `POST /overall-quizzes/{id}/attempts` sonrasında görünür.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM exams WHERE id = ? AND course_id = ? AND tenant_id = ?",
            (exam_id, course_id, tenant_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Sınav bulunamadı")
    finally:
        await db.close()

    async def event_stream():
        async for event in generate_overall_quiz_stream(
            course_id, tenant_id, mode="exam", exam_id=exam_id
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── sınav sonrası muhasebe (Plan #44) ────────────────────────────────────────

PostmortemReason = Literal["bilmiyordum", "karıştırdım", "süre_yetmedi", "dikkatsizlik"]


class PostmortemItem(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    reason: PostmortemReason


class PostmortemIn(BaseModel):
    items: list[PostmortemItem] = Field(min_length=1)


class PostmortemOut(BaseModel):
    exam_id: int
    items: list[PostmortemItem]
    summary: str
    created_at: str


async def _require_exam(db, exam_id: int, tenant_id: str) -> dict:
    cursor = await db.execute(
        "SELECT id, course_id, title FROM exams WHERE id = ? AND tenant_id = ?",
        (exam_id, tenant_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sınav bulunamadı")
    return dict(row)


@router.post("/exams/{exam_id}/postmortem", response_model=PostmortemOut)
async def create_postmortem(
    exam_id: int, item: PostmortemIn, tenant_id: str = Depends(enforce_quota)
) -> PostmortemOut:
    """Kaçırılan soru + sebep listesini kaydeder; LLM tek cümlelik çalışma tavsiyesi üretir."""
    db = await get_db()
    try:
        exam = await _require_exam(db, exam_id, tenant_id)
    finally:
        await db.close()

    try:
        summary = await summarize_postmortem(
            exam_title=exam["title"],
            items=[i.model_dump() for i in item.items],
            course_id=exam["course_id"],
            tenant_id=tenant_id,
        )
    except PostmortemSummaryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    created_at = datetime.now(UTC).isoformat()
    payload = {
        "items": [i.model_dump() for i in item.items],
        "summary": summary,
        "created_at": created_at,
    }

    db = await get_db()
    try:
        await db.execute(
            "UPDATE exams SET postmortem_json = ? WHERE id = ? AND tenant_id = ?",
            (json.dumps(payload, ensure_ascii=False), exam_id, tenant_id),
        )
        await db.commit()
    finally:
        await db.close()

    return PostmortemOut(exam_id=exam_id, items=item.items, summary=summary, created_at=created_at)


@router.get("/exams/{exam_id}/postmortem", response_model=PostmortemOut)
async def get_postmortem(exam_id: int, tenant_id: str = Depends(get_tenant_id)) -> PostmortemOut:
    """Kayıtlı sınav sonrası muhasebeyi döner."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT postmortem_json FROM exams WHERE id = ? AND tenant_id = ?",
            (exam_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None or row["postmortem_json"] is None:
        raise HTTPException(status_code=404, detail="Muhasebe kaydı bulunamadı")
    data = json.loads(row["postmortem_json"])
    return PostmortemOut(exam_id=exam_id, **data)
