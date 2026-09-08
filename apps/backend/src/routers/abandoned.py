"""Terk edilmiş konular kurtarma listesi (Plan #50). **LLM çağrısı YOK.**

Konu evreni `notes.topics_json`'dan çıkarılır — heatmap.py (Plan #18) ile AYNI
yaklaşım. "Son aktivite", quiz denemesi / kart tekrarı / chat sorusu ham zaman
damgalarının (`quiz_attempts.created_at` / `card_reviews.reviewed_at` /
`chat_messages.created_at`) en yenisidir.

`activity_log` KASITLI OLARAK kullanılmaz: yalnızca (kiracı, ders, tür, gün)
granülaritesinde tutar, hangi KONUYA ait olduğunu taşımaz — konu bazlı terk tespiti
için yeterli değildir; ham tablolardaki zaman damgaları daha isabetlidir ve zaten
heatmap.py'de aynı konu evreni için kullanılıyor.

Bir konu hiç aktivite görmediyse eşik notun üretim tarihine (`notes.generated_at`)
göre uygulanır: yeni oluşturulmuş bir konuya henüz "terk edilmiş" denmez.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["abandoned"])

# Bu kadar gündür hiç aktivitesi olmayan konu "terk edilmiş" sayılır.
ABANDONED_AFTER_DAYS = 21
# Konu adı/anahtar kelimenin chat mesajında aranabilmesi için gereken en kısa uzunluk
# (heatmap.py ile aynı eşik — kısa parçalar rastgele eşleşme üretir).
MIN_MATCH_LEN = 4


class AbandonedTopic(BaseModel):
    topic: str
    chapter_id: int
    last_activity: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _placeholders(count: int) -> str:
    return ", ".join(["?"] * count)


def _as_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


class _TopicBucket:
    """Bir konunun kimliği + gözlenen en yeni aktivite zaman damgası."""

    __slots__ = ("label", "chapter_id", "first_seen", "last_activity")

    def __init__(self, label: str, chapter_id: int, first_seen: datetime | None) -> None:
        self.label = label
        self.chapter_id = chapter_id
        self.first_seen = first_seen
        self.last_activity: datetime | None = None

    def touch(self, moment: datetime | None) -> None:
        if moment is not None and (self.last_activity is None or moment > self.last_activity):
            self.last_activity = moment


@router.get("/courses/{course_id}/abandoned", response_model=list[AbandonedTopic])
async def list_abandoned_topics(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> list[AbandonedTopic]:
    """`ABANDONED_AFTER_DAYS` gündür hiç aktivitesi olmayan konuları döner.

    Sıralama: en uzun süredir aktivitesiz konu önce (hiç aktivite görmemiş konular
    notun üretim tarihine göre sıralanır).
    """
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        buckets: dict[str, _TopicBucket] = {}
        match_terms: list[tuple[str, str]] = []

        def bucket_for(
            label: str, chapter_id: int, first_seen: datetime | None
        ) -> _TopicBucket | None:
            key = _normalize(label)
            if not key:
                return None
            bucket = buckets.get(key)
            if bucket is None:
                bucket = buckets[key] = _TopicBucket(label.strip(), chapter_id, first_seen)
                match_terms.append((key, key))
            return bucket

        # ── 1) Konu evreni: her bölümün EN SON notu (topics_json) ──
        cursor = await db.execute(
            "SELECT n.chapter_id, n.topics_json, n.generated_at FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id AND c.tenant_id = n.tenant_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND n.tenant_id = ? "
            "AND n.id = (SELECT MAX(id) FROM notes WHERE chapter_id = n.chapter_id "
            "AND tenant_id = ?)",
            (course_id, tenant_id, tenant_id, tenant_id),
        )
        for row in await cursor.fetchall():
            row = dict(row)
            first_seen = _as_datetime(row["generated_at"])
            for entry in json.loads(row["topics_json"] or "[]"):
                if not isinstance(entry, dict):
                    continue
                bucket = bucket_for(str(entry.get("topic") or ""), row["chapter_id"], first_seen)
                if bucket is None:
                    continue
                key = _normalize(bucket.label)
                for keyword in entry.get("keywords", []):
                    term = _normalize(str(keyword))
                    if len(term) >= MIN_MATCH_LEN:
                        match_terms.append((key, term))

        if not buckets:
            return []

        # ── 2) Quiz denemesi zaman damgaları ──
        # Bir denemenin TÜMÜ, o quizdeki tüm konulara "aktivite" sayılır — deneme
        # yapılmışsa öğrenci o bölümdeki konularla en azından temas etmiştir (kaba
        # ama sağlam bir üst sınır; hangi TEKİL soruya denk geldiği burada önemsiz).
        cursor = await db.execute(
            "SELECT q.id, q.questions_json FROM quizzes q "
            "JOIN chapters c ON c.id = q.chapter_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND q.tenant_id = ?",
            (course_id, tenant_id, tenant_id),
        )
        quiz_topics: dict[int, set[str]] = {}
        for row in await cursor.fetchall():
            row = dict(row)
            data = json.loads(row["questions_json"] or "{}")
            labels = {
                str(topic.get("topic") or "")
                for topic in data.get("topics", [])
                if isinstance(topic, dict)
            }
            quiz_topics[row["id"]] = labels

        if quiz_topics:
            quiz_ids = list(quiz_topics)
            cursor = await db.execute(
                "SELECT quiz_id, created_at FROM quiz_attempts "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND quiz_id IN ({_placeholders(len(quiz_ids))})",
                (tenant_id, *quiz_ids),
            )
            for row in await cursor.fetchall():
                row = dict(row)
                moment = _as_datetime(row["created_at"])
                for label in quiz_topics[row["quiz_id"]]:
                    bucket = buckets.get(_normalize(label))
                    if bucket is not None:
                        bucket.touch(moment)

        # ── 3) Kart tekrarı zaman damgaları ──
        cursor = await db.execute(
            "SELECT id, cards_json FROM flashcard_sets WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        card_topics: dict[tuple[int, int], str] = {}
        for row in await cursor.fetchall():
            row = dict(row)
            for card_index, card in enumerate(json.loads(row["cards_json"] or "[]")):
                if not isinstance(card, dict):
                    continue
                label = str(card.get("topic") or "").strip()
                if _normalize(label) in buckets:
                    card_topics[(row["id"], card_index)] = label

        if card_topics:
            set_ids = sorted({set_id for set_id, _ in card_topics})
            cursor = await db.execute(
                "SELECT set_id, card_index, reviewed_at FROM card_reviews "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND reviewed_at IS NOT NULL "
                f"AND set_id IN ({_placeholders(len(set_ids))})",
                (tenant_id, *set_ids),
            )
            for row in await cursor.fetchall():
                row = dict(row)
                label = card_topics.get((row["set_id"], row["card_index"]))
                if label is None:
                    continue
                bucket = buckets.get(_normalize(label))
                if bucket is not None:
                    bucket.touch(_as_datetime(row["reviewed_at"]))

        # ── 4) Chat soru zaman damgaları ──
        cursor = await db.execute(
            "SELECT content, created_at FROM chat_messages "
            "WHERE course_id = ? AND tenant_id = ? AND role = 'user'",
            (course_id, tenant_id),
        )
        terms = [(key, term) for key, term in match_terms if len(term) >= MIN_MATCH_LEN]
        for row in await cursor.fetchall():
            row = dict(row)
            normalized = _normalize(row["content"] or "")
            if not normalized:
                continue
            moment = _as_datetime(row["created_at"])
            hit_keys = {key for key, term in terms if term in normalized}
            for key in hit_keys:
                buckets[key].touch(moment)
    finally:
        await db.close()

    cutoff = datetime.now(UTC) - timedelta(days=ABANDONED_AFTER_DAYS)
    never = datetime.min.replace(tzinfo=UTC)

    def effective(bucket: _TopicBucket) -> datetime:
        return bucket.last_activity or bucket.first_seen or never

    abandoned = [bucket for bucket in buckets.values() if effective(bucket) < cutoff]
    abandoned.sort(key=lambda bucket: (effective(bucket), bucket.label.lower()))

    return [
        AbandonedTopic(
            topic=bucket.label,
            chapter_id=bucket.chapter_id,
            last_activity=bucket.last_activity.isoformat() if bucket.last_activity else None,
        )
        for bucket in abandoned
    ]
