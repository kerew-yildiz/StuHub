"""Ders/chapter kart özeti router'ı — dashboard kartlarının hover rotation verisi.

Yönerge §36/§37: ders kartı normalde `progress + yaklaşan sınav`, hover'da
`son aktivite + toplam çalışma` ve 2 sn sonra `tamamlanan chapter + yaklaşan ödev`
gösterir; chapter kartı hover'da `tamamlanan topic / toplam topic + son aktivite`
gösterir. Bu uç, kart başına N+1 istek yerine tek istekte tüm özeti verir.

LLM YOK — tüm hesap saf SQL + JSON ayrıştırmasıdır.

Topic tamamlanma sinyali (yönerge §4):
- topic, o topic'te en az bir *doğru* chapter-quiz cevabı VEYA en az bir
  "tutuldu" (good/easy) SM-2 tekrarı aldıysa tamamlanmış sayılır.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db
from ..services.study_time import study_totals

router = APIRouter(prefix="/api", tags=["card-summary"])

# "Tutuldu" sayılan SM-2 puanları (heatmap.RETAINED_RATINGS ile aynı küme).
RETAINED_RATINGS = frozenset({"good", "easy"})

_KIND_LABELS = {"quiz": "Quiz", "flashcard": "Flashcard", "note": "Not"}


class NextExamOut(BaseModel):
    title: str
    exam_date: str
    days_left: int


class LastActivityOut(BaseModel):
    at: str
    kind: str  # quiz | flashcard | note
    label: str | None = None


class ChapterSummaryOut(BaseModel):
    chapter_id: int
    topics_total: int
    topics_completed: int
    # Chapter'da geçen aktif süre (heartbeat kayıtları; migration 0015) — saniye.
    total_study_sec: int = 0
    last_activity: str | None = None


class CardSummaryOut(BaseModel):
    course_id: int
    # Ders ilerlemesi: tamamlanan topic / toplam topic. Kart yoksa null.
    progress: float | None
    next_exam: NextExamOut | None
    total_study_sec: int
    last_activity: LastActivityOut | None
    completed_chapters: int
    total_chapters: int
    chapters: list[ChapterSummaryOut]


class TopicProgressOut(BaseModel):
    topic: str
    # 0-100; null = bu topic için hiç sinyal yok (halka boş çizilir).
    percent: float | None
    cards_total: int
    cards_retained: int
    quiz_total: int
    quiz_correct: int


class TopicProgressReportOut(BaseModel):
    chapter_id: int
    topics: list[TopicProgressOut]
    completed_topics: int
    total_topics: int


def _loads(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    """Timestamp kolonunu ISO'ya çevirir; bozuk değer None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _require_course(db, course_id: int, tenant_id: str) -> None:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Ders bulunamadı")


def _placeholders(count: int) -> str:
    return ", ".join(["?"] * count)


@router.get("/chapters/{chapter_id}/topic-progress", response_model=TopicProgressReportOut)
async def chapter_topic_progress(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> TopicProgressReportOut:
    """Chapter'ın topic bazlı tamamlanması — konu listesindeki ilerleme çemberleri.

    Topic evreni: not topics_json + flashcard kart topic'leri + quiz question topic'leri
    (card-summary ile aynı birleşim). Tamamlanma sinyali iki kaynakta oranlanır:
    - kart: topic'teki kartların kaçına "tutuldu" (good/easy) SM-2 puanı verilmiş,
    - quiz: topic'te yanıtlanan sonuçların kaçı doğru.
    İki sinyal de yoksa percent null döner — sahte yüzde üretilmez.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM chapters WHERE id = ? AND tenant_id = ?", (chapter_id, tenant_id)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")

        # ── Topic evreni (key: lowercase, display: ilk görülen ad) ──────
        universe: dict[str, str] = {}

        cursor = await db.execute(
            "SELECT topics_json FROM notes WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC",
            (chapter_id, tenant_id),
        )
        for row in await cursor.fetchall():
            for topic in _loads(row["topics_json"]) or []:
                name = (
                    str(topic.get("topic", "")).strip() if isinstance(topic, dict) else str(topic)
                )
                if name:
                    universe.setdefault(name.lower(), name)

        cursor = await db.execute(
            "SELECT id, cards_json FROM flashcard_sets WHERE chapter_id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        set_rows = await cursor.fetchall()
        topic_cards: dict[str, list[tuple[int, int]]] = {}  # key → [(set_id, card_index)]
        for row in set_rows:
            for card_index, card in enumerate(_loads(row["cards_json"]) or []):
                name = str(card.get("topic", "")).strip() if isinstance(card, dict) else ""
                if not name:
                    continue
                key = name.lower()
                universe.setdefault(key, name)
                topic_cards.setdefault(key, []).append((row["id"], card_index))

        cursor = await db.execute(
            "SELECT id, questions_json FROM quizzes WHERE chapter_id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        quiz_topics: dict[int, list[str]] = {}
        for row in await cursor.fetchall():
            questions = _loads(row["questions_json"]) or {}
            names = [
                str(t.get("topic", "")).strip()
                for t in (questions.get("topics") or [])
                if isinstance(t, dict)
            ]
            names = [name for name in names if name]
            quiz_topics[row["id"]] = names
            for name in names:
                universe.setdefault(name.lower(), name)

        if not universe:
            return TopicProgressReportOut(
                chapter_id=chapter_id, topics=[], completed_topics=0, total_topics=0
            )

        # ── Sinyal (a): kart tekrarları ──────────────────────────────────
        set_ids = [row["id"] for row in set_rows]
        ratings: dict[tuple[int, int], str] = {}
        if set_ids:
            cursor = await db.execute(
                "SELECT set_id, card_index, last_rating FROM card_reviews "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND set_id IN ({_placeholders(len(set_ids))})",
                (tenant_id, *set_ids),
            )
            for row in await cursor.fetchall():
                ratings[(row["set_id"], row["card_index"])] = row["last_rating"]

        cards_stats: dict[str, list[int]] = {key: [0, 0] for key in universe}  # [total, retained]
        for key, pairs in topic_cards.items():
            for set_id, card_index in pairs:
                cards_stats[key][0] += 1
                if ratings.get((set_id, card_index)) in RETAINED_RATINGS:
                    cards_stats[key][1] += 1

        # ── Sinyal (b): quiz sonuçları ───────────────────────────────────
        quiz_stats: dict[str, list[int]] = {key: [0, 0] for key in universe}  # [total, correct]
        cursor = await db.execute(
            "SELECT a.quiz_id, a.feedback_json FROM quiz_attempts a "
            "JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
            "WHERE q.chapter_id = ? AND q.tenant_id = ?",
            (chapter_id, tenant_id),
        )
        for row in await cursor.fetchall():
            names = quiz_topics.get(row["quiz_id"], [])
            feedback = _loads(row["feedback_json"]) or {}
            for result in feedback.get("results") or []:
                result_topic = str(result.get("topic") or "").strip()
                key = result_topic.lower() if result_topic else None
                if not key:
                    prefix = str(result.get("qid", "")).split("-", 1)[0]
                    if prefix.isdigit() and int(prefix) < len(names) and names[int(prefix)]:
                        key = names[int(prefix)].lower()
                if key is None:
                    continue
                stats = quiz_stats.setdefault(key, [0, 0])
                stats[0] += 1
                if result.get("correct"):
                    stats[1] += 1

        # ── Oranlar ──────────────────────────────────────────────────────
        topics: list[TopicProgressOut] = []
        completed_count = 0
        for key, display in universe.items():
            signals: list[float] = []
            cards_total, cards_retained = cards_stats[key]
            quiz_total, quiz_correct = quiz_stats[key]
            if cards_total:
                signals.append(cards_retained / cards_total)
            if quiz_total:
                signals.append(quiz_correct / quiz_total)
            percent = round(100 * (sum(signals) / len(signals))) if signals else None
            if percent == 100:
                completed_count += 1
            topics.append(
                TopicProgressOut(
                    topic=display,
                    percent=percent,
                    cards_total=cards_total,
                    cards_retained=cards_retained,
                    quiz_total=quiz_total,
                    quiz_correct=quiz_correct,
                )
            )

        return TopicProgressReportOut(
            chapter_id=chapter_id,
            topics=topics,
            completed_topics=completed_count,
            total_topics=len(topics),
        )
    finally:
        await db.close()


@router.get("/courses/{course_id}/card-summary", response_model=CardSummaryOut)
async def course_card_summary(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> CardSummaryOut:
    db = await get_db()
    try:
        await _require_course(db, course_id, tenant_id)

        # ── Chapter'lar ve topic evreni ─────────────────────────────────
        cursor = await db.execute(
            "SELECT id FROM chapters WHERE course_id = ? AND tenant_id = ? ORDER BY id ASC",
            (course_id, tenant_id),
        )
        chapter_ids = [row["id"] for row in await cursor.fetchall()]

        # Topic evreni: not topics_json + kart topics + quiz topic adları (birleşim,
        # chapter bazında). Quiz topic'leri evrene dahildir — yalnızca quiz çözen bir
        # chapter'ın topics_total'ı 0 olmamalı.
        chapter_topics: dict[int, set[str]] = {cid: set() for cid in chapter_ids}
        topic_display: dict[str, str] = {}
        topic_chapter: dict[str, int] = {}

        note_rows = []
        if chapter_ids:
            cursor = await db.execute(
                "SELECT id, chapter_id, topics_json, generated_at FROM notes "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND chapter_id IN ({_placeholders(len(chapter_ids))})",
                (tenant_id, *chapter_ids),
            )
            note_rows = await cursor.fetchall()
        for row in note_rows:
            for topic in _loads(row["topics_json"]) or []:
                name = (
                    str(topic.get("topic", "")).strip() if isinstance(topic, dict) else str(topic)
                )
                if not name:
                    continue
                key = name.lower()
                chapter_topics[row["chapter_id"]].add(key)
                topic_display.setdefault(key, name)
                topic_chapter.setdefault(key, row["chapter_id"])

        cursor = await db.execute(
            "SELECT id, chapter_id, cards_json FROM flashcard_sets "
            "WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        set_rows = await cursor.fetchall()
        set_ids = [row["id"] for row in set_rows]
        for row in set_rows:
            for card in _loads(row["cards_json"]) or []:
                name = str(card.get("topic", "")).strip() if isinstance(card, dict) else ""
                if not name or row["chapter_id"] is None:
                    continue
                key = name.lower()
                chapter_topics[row["chapter_id"]].add(key)
                topic_display.setdefault(key, name)
                topic_chapter.setdefault(key, row["chapter_id"])

        # ── Tamamlanma sinyalleri ───────────────────────────────────────
        completed: set[str] = set()

        # (a) Tutuldu kartlar: set → card_index → topic → completed.
        retained_topics: dict[int, set[str]] = {}  # set_id → topics
        if set_ids:
            cursor = await db.execute(
                "SELECT set_id, card_index, last_rating FROM card_reviews "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND set_id IN ({_placeholders(len(set_ids))}) "
                f"AND last_rating IN ({_placeholders(len(RETAINED_RATINGS))})",
                (tenant_id, *set_ids, *RETAINED_RATINGS),
            )
            retained: dict[int, dict[int, str]] = {}
            for row in await cursor.fetchall():
                retained.setdefault(row["set_id"], {})[row["card_index"]] = row["last_rating"]
            for row in set_rows:
                cards = _loads(row["cards_json"]) or []
                reviews = retained.get(row["id"], {})
                for card_index, card in enumerate(cards):
                    topic = str(card.get("topic", "")).strip() if isinstance(card, dict) else ""
                    if topic and card_index in reviews:
                        retained_topics.setdefault(row["chapter_id"], set()).add(topic.lower())

        for topics in retained_topics.values():
            completed.update(topics)

        # (b) Doğru quiz cevapları: quiz_attempts.feedback_json.results[].correct
        #     + qid topic indeksi → quizzes.questions_json.topics adları.
        quiz_meta: dict[int, tuple[int, list[str]]] = {}
        if chapter_ids:
            cursor = await db.execute(
                "SELECT q.id AS quiz_id, q.chapter_id, q.questions_json, a.feedback_json "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                "FROM quiz_attempts a "
                "JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
                f"WHERE q.tenant_id = ? AND q.chapter_id IN ({_placeholders(len(chapter_ids))})",
                (tenant_id, *chapter_ids),
            )
            for row in await cursor.fetchall():
                questions = _loads(row["questions_json"]) or {}
                names = [
                    str(t.get("topic", "")).strip()
                    for t in (questions.get("topics") or [])
                    if isinstance(t, dict)
                ]
                names = [name for name in names if name]
                quiz_meta[row["quiz_id"]] = (row["chapter_id"], names)
                for name in names:
                    key = name.lower()
                    chapter_topics[row["chapter_id"]].add(key)
                    topic_display.setdefault(key, name)
                    topic_chapter.setdefault(key, row["chapter_id"])
                feedback = _loads(row["feedback_json"]) or {}
                for result in feedback.get("results") or []:
                    if not result.get("correct"):
                        continue
                    result_topic = str(result.get("topic") or "").strip()
                    if result_topic:
                        completed.add(result_topic.lower())
                        continue
                    prefix = str(result.get("qid", "")).split("-", 1)[0]
                    if prefix.isdigit() and int(prefix) < len(names) and names[int(prefix)]:
                        completed.add(names[int(prefix)].lower())

        # ── Son aktivite (tüm kaynakların en yenisi) ────────────────────
        candidates: list[tuple[datetime, str, str | None, int | None]] = []

        if chapter_ids:
            cursor = await db.execute(
                "SELECT a.created_at, a.quiz_id FROM quiz_attempts a "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                "JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
                f"WHERE q.tenant_id = ? AND q.chapter_id IN ({_placeholders(len(chapter_ids))}) "
                "ORDER BY a.created_at DESC LIMIT 1",
                (tenant_id, *chapter_ids),
            )
            if (row := await cursor.fetchone()) is not None:
                moment = _parse_dt(row["created_at"])
                if moment:
                    meta = quiz_meta.get(row["quiz_id"])
                    label = None
                    if meta and meta[1]:
                        label = meta[1][0]
                    candidates.append((moment, "quiz", label, row["quiz_id"] and meta and meta[0]))

        if set_ids:
            cursor = await db.execute(
                "SELECT cr.reviewed_at, fs.chapter_id, fs.cards_json, cr.card_index "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                "FROM card_reviews cr JOIN flashcard_sets fs ON fs.id = cr.set_id "
                "WHERE cr.tenant_id = ? AND cr.reviewed_at IS NOT NULL "
                f"AND fs.id IN ({_placeholders(len(set_ids))}) "
                "ORDER BY cr.reviewed_at DESC LIMIT 1",
                (tenant_id, *set_ids),
            )
            if (row := await cursor.fetchone()) is not None:
                moment = _parse_dt(row["reviewed_at"])
                if moment:
                    cards = _loads(row["cards_json"]) or []
                    card = cards[row["card_index"]] if row["card_index"] < len(cards) else {}
                    topic = str(card.get("topic", "")).strip() if isinstance(card, dict) else ""
                    candidates.append((moment, "flashcard", topic or None, row["chapter_id"]))

        if note_rows:
            moments = [
                (_parse_dt(row["generated_at"]), row) for row in note_rows
            ]
            moments = [(m, r) for m, r in moments if m]
            if moments:
                moment, row = max(moments, key=lambda pair: pair[0])
                topics = _loads(row["topics_json"]) or []
                label = None
                if topics and isinstance(topics[0], dict):
                    label = str(topics[0].get("topic", "")) or None
                candidates.append((moment, "note", label, row["chapter_id"]))

        last_activity = None
        chapter_last: dict[int, datetime] = {}
        if candidates:
            moment, kind, label, chapter_id = max(candidates, key=lambda c: c[0])
            last_activity = LastActivityOut(
                at=moment.isoformat(), kind=kind, label=label or _KIND_LABELS.get(kind)
            )
            if chapter_id is not None:
                chapter_last[chapter_id] = moment
        for moment, _kind, _label, chapter_id in candidates:
            if chapter_id is not None:
                chapter_last[chapter_id] = max(chapter_last.get(chapter_id, moment), moment)

        # ── Yaklaşan sınav ──────────────────────────────────────────────
        cursor = await db.execute(
            "SELECT title, exam_date FROM exams WHERE course_id = ? AND tenant_id = ? "
            "AND exam_date >= ? ORDER BY exam_date ASC LIMIT 1",
            (course_id, tenant_id, datetime.now(UTC).date().isoformat()),
        )
        exam_row = await cursor.fetchone()
        next_exam = None
        if exam_row is not None:
            exam_date = str(exam_row["exam_date"])[:10]
            days_left = (
                datetime.fromisoformat(exam_date).date()
                - datetime.now(UTC).date()
            ).days
            next_exam = NextExamOut(
                title=exam_row["title"], exam_date=exam_date, days_left=days_left
            )

        # ── Toplam çalışma süresi (ders + chapter; heartbeat kayıtları) ──
        total_study, chapter_study = await study_totals(db, tenant_id, course_id)

        # ── Chapter özetleri ────────────────────────────────────────────
        chapters: list[ChapterSummaryOut] = []
        completed_chapter_count = 0
        for cid in chapter_ids:
            topics = chapter_topics[cid]
            done = topics & completed
            if topics and done == topics:
                completed_chapter_count += 1
            last = chapter_last.get(cid)
            chapters.append(
                ChapterSummaryOut(
                    chapter_id=cid,
                    topics_total=len(topics),
                    topics_completed=len(done),
                    total_study_sec=chapter_study.get(cid, 0),
                    last_activity=_iso(last),
                )
            )

        total_topics = sum(len(t) for t in chapter_topics.values())
        progress = (
            round(len(completed) / total_topics, 4) if total_topics else None
        )

        return CardSummaryOut(
            course_id=course_id,
            progress=progress,
            next_exam=next_exam,
            total_study_sec=total_study,
            last_activity=last_activity,
            completed_chapters=completed_chapter_count,
            total_chapters=len(chapter_ids),
            chapters=chapters,
        )
    finally:
        await db.close()
