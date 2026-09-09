"""Sonsuz kaydırma quiz feed'i router'ı (Plan: feed; chapter-scope + ustalık #6/#7).

Sözleşme:
- `GET  /api/courses/{course_id}/feed?limit=10&chapter_id=`  → {items, pool_ready, generating}
- `POST /api/feed/{feed_id}/answer`                          → {correct, correct_index, ...}
- `POST /api/courses/{course_id}/feed/skip`                  → {ok: true}
- `GET  /api/courses/{course_id}/mastery` / `/api/chapters/{chapter_id}/mastery`
  → {percent, correct, total, topics: [{topic, correct, target}]}

GET **hiçbir zaman LLM beklemez**: havuzdan servis eder, ardından doldurmayı
fire-and-forget task olarak tetikler. Havuz boşsa senkron olarak mevcut quiz
sorularından dolgu denenir; o da boşsa `items: []` + `generating: true` döner
(hata değil — üretim arka planda sürüyor). `chapter_id` verilirse feed/havuz/dolgu
zincirinin tamamı o bölümle sınırlanır.

`answer` ucu doğru cevabı YALNIZCA cevap gönderildikten sonra döner; servis edilen
soru gövdesinde `correct_index`/`explanation` bulunmaz (bkz. feed_service._public).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import get_tenant_id
from ..db import get_db
from ..services import feed_service

router = APIRouter(prefix="/api", tags=["feed"])


class FeedQuestion(BaseModel):
    """Servis edilen soru — doğru cevap alanı YOK."""

    feed_id: int
    question: str
    options: list[str]
    topic: str | None = None
    chapter_id: int | None = None
    difficulty: str | None = None
    saved: bool = False


class FeedOut(BaseModel):
    items: list[FeedQuestion]
    pool_ready: int
    generating: bool


class AnswerIn(BaseModel):
    selected_index: int = Field(ge=0, le=9)
    elapsed_ms: int = Field(default=0, ge=0)


class AnswerOut(BaseModel):
    correct: bool
    correct_index: int
    explanation: str
    citations: list | None = None
    note_id: int | None = None
    chapter_id: int | None = None


class SkipIn(BaseModel):
    feed_id: int


class MasteryTopic(BaseModel):
    topic: str
    correct: int
    target: int = 5


class MasteryOut(BaseModel):
    percent: float
    correct: int
    total: int
    topics: list[MasteryTopic]


async def _ensure_course(course_id: int, tenant_id: str) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")


async def _ensure_chapter(chapter_id: int, tenant_id: str) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM chapters WHERE id = ? AND tenant_id = ?", (chapter_id, tenant_id)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Bölüm bulunamadı")


async def _ensure_chapter_in_course(chapter_id: int, course_id: int, tenant_id: str) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM chapters WHERE id = ? AND course_id = ? AND tenant_id = ?",
            (chapter_id, course_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Bölüm bulunamadı")


@router.get("/courses/{course_id}/feed", response_model=FeedOut)
async def get_feed(
    course_id: int,
    limit: int = Query(default=feed_service.DEFAULT_LIMIT, ge=1, le=feed_service.MAX_LIMIT),
    chapter_id: int | None = Query(default=None),
    tenant_id: str = Depends(get_tenant_id),
) -> FeedOut:
    """Havuzdan bir soru partisi döner; doldurmayı arka planda tetikler.

    `chapter_id` verilirse feed yalnızca o bölümün sorularıyla sınırlanır."""
    await _ensure_course(course_id, tenant_id)
    if chapter_id is not None:
        await _ensure_chapter_in_course(chapter_id, course_id, tenant_id)

    items = await feed_service.serve_batch(course_id, tenant_id, limit, chapter_id)
    if not items:
        # Havuz boş: LLM beklemeden, mevcut quiz sorularından anında dolgu denenir.
        # `backfill_from_existing`'in DÖNÜŞ DEĞERİNE göre değil (kaç satır BU çağrı
        # ekledi), her zaman yeniden dene: eşzamanlı bir arka plan doldurma görevi
        # (spawn_topup, satır 142) AYNI kaynak sorulardan aynı anda kopyalıyor olabilir.
        # Origin başına UNIQUE kısıt sayesinde kaybeden tarafın INSERT'i sessizce
        # es geçilir (_insert_from_quiz) ve `inserted` 0 döner — ama satır artık
        # HAVUZDA VAR, yalnızca biz eklemedik. Dönüş değerine göre atlarsak (`and`
        # ile), kazanan görevin eklediği satır hiç servis edilmeden kaybolurdu
        # (tests/test_feed.py::test_ayni_soru_iki_kez_servis_edilmez, ~%15 flaky —
        # 2026-09-09, tam paket CI koşusunda kök nedeniyle yakalandı).
        await feed_service.backfill_from_existing(course_id, tenant_id, limit, chapter_id)
        items = await feed_service.serve_batch(course_id, tenant_id, limit, chapter_id)

    feed_service.spawn_topup(course_id, tenant_id, chapter_id)
    ready = await feed_service.pool_size(course_id, tenant_id, chapter_id)
    return FeedOut(
        items=[FeedQuestion(**item) for item in items],
        pool_ready=ready,
        generating=ready < feed_service.TARGET_POOL,
    )


@router.get("/courses/{course_id}/mastery", response_model=MasteryOut)
async def get_course_mastery(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> MasteryOut:
    """Dersin ustalık ilerlemesi — tüm bölümlerin toplamı."""
    await _ensure_course(course_id, tenant_id)
    return MasteryOut(**await feed_service.course_mastery(course_id, tenant_id))


@router.get("/chapters/{chapter_id}/mastery", response_model=MasteryOut)
async def get_chapter_mastery(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> MasteryOut:
    """Bölümün ustalık ilerlemesi."""
    await _ensure_chapter(chapter_id, tenant_id)
    return MasteryOut(**await feed_service.chapter_mastery(chapter_id, tenant_id))


@router.post("/feed/{feed_id}/answer", response_model=AnswerOut)
async def answer_feed_question(
    feed_id: int, payload: AnswerIn, tenant_id: str = Depends(get_tenant_id)
) -> AnswerOut:
    """Cevabı değerlendirir; doğru cevap + açıklama + atıflar ilk kez burada döner."""
    result = await feed_service.record_answer(
        feed_id, tenant_id, payload.selected_index, payload.elapsed_ms
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    return AnswerOut(**result)


@router.post("/courses/{course_id}/feed/skip")
async def skip_feed_question(
    course_id: int, payload: SkipIn, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Soruyu atlar — tekrar servis edilmez."""
    await _ensure_course(course_id, tenant_id)
    if not await feed_service.skip(payload.feed_id, tenant_id):
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    return {"ok": True}
