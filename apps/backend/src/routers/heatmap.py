"""Zayıf konu ısı haritası router'ı (Plan #18).

Ders bazında konu × performans matrisi üretir: quiz doğruluğu, flashcard tutma oranı
ve chat'te sorulan soru yoğunluğu tek tabloda birleşir. **LLM çağrısı YOK** — tüm
hesap SQL okumaları + deterministik Python birleştirmesidir.

Konu eşlemesi (`topics_json` zinciri):
- Konu evreni `notes.topics_json` (`[{"topic", "keywords", "slide_refs"}]`),
  `quizzes.questions_json` (`{"topics": [{"topic", "questions": [...]}]}`) ve
  `flashcard_sets.cards_json` (`[{"topic", ...}]`) birleşiminden çıkar.
- Konu anahtarı normalize edilmiş addır (küçük harf + noktalama atılmış); görünen ad
  ilk karşılaşılan yazımdır.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["heatmap"])

# ── weakness_score ağırlıkları ──────────────────────────────────────────
# Üç sinyalin göreli ağırlığı; toplamı 1.0. Quiz en doğrudan ölçüm olduğu için
# en ağır, chat yoğunluğu en dolaylı sinyal olduğu için en hafif.
WEIGHT_QUIZ = 0.5
WEIGHT_CARD = 0.3
WEIGHT_CHAT = 0.2

# Chat soru yoğunluğu doyum noktası: bu kadar (veya daha fazla) soru sorulan konu
# chat sinyalinde tam zayıf (1.0) sayılır.
CHAT_SATURATION = 5

# SM-2 puanlarından "tutuldu" sayılanlar (flashcards.VALID_RATINGS alt kümesi).
RETAINED_RATINGS = frozenset({"good", "easy"})

# Konu adı/anahtar kelimenin chat mesajında aranabilmesi için gereken en kısa uzunluk —
# daha kısa parçalar ("ağ", "iş") rastgele eşleşme üretir.
MIN_MATCH_LEN = 4


class TopicHeat(BaseModel):
    """Tek konunun ısı haritası satırı."""

    topic: str
    # Doğru cevap / cevaplanan soru — hiç deneme yoksa null.
    quiz_accuracy: float | None
    # ("good" + "easy") / puanlanmış tekrar sayısı — hiç tekrar yoksa null.
    card_retention: float | None
    # Konuyla eşleşen kullanıcı sohbet mesajı sayısı.
    chat_question_count: int
    # 0..1, 1 = en zayıf. Hiçbir sinyalde veri yoksa null.
    weakness_score: float | None
    # Skorun dayandığı toplam gözlem sayısı (cevap + tekrar + soru).
    sample_size: int


class HeatmapOut(BaseModel):
    course_id: int
    # Sinyal ağırlıkları — arayüz kolon başlıklarında/tooltip'te gösterilebilir.
    weights: dict[str, float]
    topics: list[TopicHeat]


def _normalize(text: str) -> str:
    """Konu adını eşleştirme anahtarına çevirir (küçük harf, noktalama atılır)."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _placeholders(count: int) -> str:
    return ", ".join(["?"] * count)


async def _course_exists(db, course_id: int, tenant_id: str) -> bool:
    cursor = await db.execute(
        "SELECT id FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
    )
    return await cursor.fetchone() is not None


class _TopicBucket:
    """Bir konunun ham sayaçları; oranlar sonda türetilir."""

    __slots__ = (
        "label",
        "quiz_total",
        "quiz_correct",
        "review_total",
        "review_retained",
        "chat_count",
    )

    def __init__(self, label: str) -> None:
        self.label = label
        self.quiz_total = 0
        self.quiz_correct = 0
        self.review_total = 0
        self.review_retained = 0
        self.chat_count = 0


def _weakness_score(
    quiz_accuracy: float | None,
    card_retention: float | None,
    chat_pressure: float | None,
) -> float | None:
    """Üç sinyali ağırlıklı ortalamayla 0..1 zayıflık skoruna indirger (1 = en zayıf).

    Sinyaller ve ağırlıkları:
    - Quiz zayıflığı  = 1 - quiz_accuracy            → ağırlık 0.5
    - Kart zayıflığı  = 1 - card_retention           → ağırlık 0.3
    - Chat baskısı    = min(soru_sayısı / 5, 1.0)    → ağırlık 0.2

    Formül: Σ(ağırlık × zayıflık) / Σ(mevcut sinyallerin ağırlıkları).
    Veri olmayan sinyal paydadan da düşer (uydurma varsayılan kullanılmaz); hiçbir
    sinyalde veri yoksa sonuç None'dır. Chat tek yönlü bir sinyaldir: soru sorulmuş
    olması zayıflık kanıtıdır, sorulmamış olması güç kanıtı DEĞİLDİR — bu yüzden
    `chat_pressure` yalnızca soru sayısı > 0 iken sinyal sayılır (bkz. çağrı yeri).
    """
    weighted = 0.0
    total_weight = 0.0
    if quiz_accuracy is not None:
        weighted += WEIGHT_QUIZ * (1.0 - quiz_accuracy)
        total_weight += WEIGHT_QUIZ
    if card_retention is not None:
        weighted += WEIGHT_CARD * (1.0 - card_retention)
        total_weight += WEIGHT_CARD
    if chat_pressure is not None:
        weighted += WEIGHT_CHAT * chat_pressure
        total_weight += WEIGHT_CHAT
    if total_weight == 0.0:
        return None
    return round(weighted / total_weight, 4)


def _quiz_answer_key(questions_json: dict) -> dict[str, tuple[str, int]]:
    """qid → (konu adı, doğru şık indeksi). qid biçimi quizzes.py `_flatten` ile aynı."""
    key: dict[str, tuple[str, int]] = {}
    for t_idx, topic in enumerate(questions_json.get("topics", [])):
        if not isinstance(topic, dict):
            continue
        label = str(topic.get("topic") or "").strip()
        for q_idx, question in enumerate(topic.get("questions", [])):
            if not isinstance(question, dict) or "correct_index" not in question:
                continue
            key[f"{t_idx}-{q_idx}"] = (label, question["correct_index"])
    return key


@router.get("/courses/{course_id}/heatmap", response_model=HeatmapOut)
async def get_course_heatmap(
    course_id: int, tenant_id: str = Depends(get_tenant_id)
) -> HeatmapOut:
    """Dersin konu × performans ısı haritasını döner (zayıftan güçlüye sıralı).

    Üç sinyalin kaynağı: `quiz_attempts` (soru bazlı doğruluk), `card_reviews`
    (SM-2 `last_rating` tutma oranı), `chat_messages` (kullanıcı sorularının konu
    adı/anahtar kelime eşleşmesi). Skor formülü `_weakness_score` docstring'inde.
    """
    db = await get_db()
    try:
        if not await _course_exists(db, course_id, tenant_id):
            raise HTTPException(status_code=404, detail="Ders bulunamadı")

        buckets: dict[str, _TopicBucket] = {}
        # Konu adı/anahtar kelime → konu anahtarı (chat eşleşmesi için)
        match_terms: list[tuple[str, str]] = []

        def bucket_for(label: str) -> _TopicBucket | None:
            key = _normalize(label)
            if not key:
                return None
            bucket = buckets.get(key)
            if bucket is None:
                bucket = buckets[key] = _TopicBucket(label.strip())
                match_terms.append((key, key))
            return bucket

        # ── 1) Konu evreni: notes.topics_json (anahtar kelimeler dahil) ──
        cursor = await db.execute(
            "SELECT n.topics_json FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND n.tenant_id = ?",
            (course_id, tenant_id, tenant_id),
        )
        for row in await cursor.fetchall():
            for entry in json.loads(row["topics_json"] or "[]"):
                if not isinstance(entry, dict):
                    continue
                bucket = bucket_for(str(entry.get("topic") or ""))
                if bucket is None:
                    continue
                key = _normalize(bucket.label)
                for keyword in entry.get("keywords", []):
                    term = _normalize(str(keyword))
                    if len(term) >= MIN_MATCH_LEN:
                        match_terms.append((key, term))

        # ── 2) Quiz doğruluğu ──
        cursor = await db.execute(
            "SELECT q.id, q.questions_json FROM quizzes q "
            "JOIN chapters c ON c.id = q.chapter_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND q.tenant_id = ?",
            (course_id, tenant_id, tenant_id),
        )
        answer_keys: dict[int, dict[str, tuple[str, int]]] = {}
        for row in await cursor.fetchall():
            key_map = _quiz_answer_key(json.loads(row["questions_json"] or "{}"))
            answer_keys[row["id"]] = key_map
            for label, _correct in key_map.values():
                bucket_for(label)

        if answer_keys:
            quiz_ids = list(answer_keys)
            cursor = await db.execute(
                "SELECT quiz_id, user_answers_json FROM quiz_attempts "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND quiz_id IN ({_placeholders(len(quiz_ids))})",
                (tenant_id, *quiz_ids),
            )
            for row in await cursor.fetchall():
                key_map = answer_keys[row["quiz_id"]]
                for answer in json.loads(row["user_answers_json"] or "[]"):
                    if not isinstance(answer, dict):
                        continue
                    entry = key_map.get(str(answer.get("qid")))
                    if entry is None:
                        continue
                    label, correct_index = entry
                    bucket = bucket_for(label)
                    if bucket is None:
                        continue
                    bucket.quiz_total += 1
                    if answer.get("selected_index") == correct_index:
                        bucket.quiz_correct += 1

        # ── 3) Kart tutma oranı ──
        cursor = await db.execute(
            "SELECT id, cards_json FROM flashcard_sets WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        card_topics: dict[tuple[int, int], str] = {}
        for row in await cursor.fetchall():
            for card_index, card in enumerate(json.loads(row["cards_json"] or "[]")):
                if not isinstance(card, dict):
                    continue
                label = str(card.get("topic") or "").strip()
                if bucket_for(label) is None:
                    continue
                card_topics[(row["id"], card_index)] = label

        if card_topics:
            set_ids = sorted({set_id for set_id, _ in card_topics})
            cursor = await db.execute(
                "SELECT set_id, card_index, last_rating FROM card_reviews "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
                f"WHERE tenant_id = ? AND last_rating IS NOT NULL "
                f"AND set_id IN ({_placeholders(len(set_ids))})",
                (tenant_id, *set_ids),
            )
            for row in await cursor.fetchall():
                label = card_topics.get((row["set_id"], row["card_index"]))
                if label is None:
                    continue
                bucket = bucket_for(label)
                if bucket is None:
                    continue
                bucket.review_total += 1
                if row["last_rating"] in RETAINED_RATINGS:
                    bucket.review_retained += 1

        # ── 4) Chat soru yoğunluğu ──
        cursor = await db.execute(
            "SELECT content FROM chat_messages "
            "WHERE course_id = ? AND tenant_id = ? AND role = 'user'",
            (course_id, tenant_id),
        )
        terms = [(key, term) for key, term in match_terms if len(term) >= MIN_MATCH_LEN]
        for row in await cursor.fetchall():
            normalized = _normalize(row["content"] or "")
            if not normalized:
                continue
            hit_keys = {key for key, term in terms if term in normalized}
            for key in hit_keys:
                buckets[key].chat_count += 1
    finally:
        await db.close()

    # Chat sinyali TEK YÖNLÜ: soru sorulmamış olması güç kanıtı değil, veri yokluğudur —
    # sinyal yalnızca en az bir eşleşen soru varsa ağırlığa katılır.
    topics: list[TopicHeat] = []
    for bucket in buckets.values():
        quiz_accuracy = (
            round(bucket.quiz_correct / bucket.quiz_total, 4) if bucket.quiz_total else None
        )
        card_retention = (
            round(bucket.review_retained / bucket.review_total, 4)
            if bucket.review_total
            else None
        )
        chat_pressure = (
            round(min(bucket.chat_count / CHAT_SATURATION, 1.0), 4)
            if bucket.chat_count
            else None
        )
        topics.append(
            TopicHeat(
                topic=bucket.label,
                quiz_accuracy=quiz_accuracy,
                card_retention=card_retention,
                chat_question_count=bucket.chat_count,
                weakness_score=_weakness_score(quiz_accuracy, card_retention, chat_pressure),
                sample_size=bucket.quiz_total + bucket.review_total + bucket.chat_count,
            )
        )

    # Zayıftan güçlüye; skoru olmayan konular (veri yok) en sona.
    topics.sort(
        key=lambda t: (
            t.weakness_score is None,
            -(t.weakness_score or 0.0),
            t.topic.lower(),
        )
    )
    return HeatmapOut(
        course_id=course_id,
        weights={"quiz": WEIGHT_QUIZ, "card": WEIGHT_CARD, "chat": WEIGHT_CHAT},
        topics=topics,
    )
