"""Bölüm quizi üretimi — konu başına 5 MCQ, atıf zorunlu, feedback üretim anında (Faz 4.1).

SSE olayları yield eder:
  {"type": "status", "percent": int, "message": str}
  {"type": "done", "quiz": {...}}
  {"type": "error", "message": str}
"""

from __future__ import annotations

import json
import logging
import re

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..db import get_db
from ..prompts.common import dil_talimati, kazanimlar_blok
from ..prompts.quiz_prompts import QUIZ_BATCH_PROMPT
from . import llm_service
from .note_generator import load_kazanimlar, topic_matches

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_TOPIC = 5
MAX_CORRECT_PER_INDEX = 2


def _split_topics(content_md: str, topics: list[dict]) -> list[dict]:
    """Notu başlık yapısına göre böler; her bölüme topics_json'dan atıf listesi bağlar.

    Dönüş: [{"topic", "section", "citations"}]; citations: not atıf listesi elemanları.
    """
    citation_map: dict[str, list[dict]] = {}
    for topic in topics:
        citation_map[topic.get("topic", "")] = topic.get("citations", [])

    def _citations_for(heading: str) -> list[dict]:
        for name, citations in citation_map.items():
            if topic_matches(heading, name):
                return citations
        return []

    result: list[dict] = []
    lines = content_md.split("\n")
    current: dict | None = None
    for line in lines:
        match = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if match:
            if current:
                result.append(current)
            heading = match.group(1).strip()
            current = {
                "topic": heading,
                "section": "",
                "citations": _citations_for(heading),
            }
        elif current:
            current["section"] += f"{line}\n"
    if current:
        result.append(current)

    if not result:
        result = [{"topic": "Genel", "section": content_md, "citations": []}]
    return [r for r in result if r["section"].strip()]


def _validate_question(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    if not isinstance(q.get("question"), str) or not q["question"].strip():
        return False
    options = q.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return False
    if not all(isinstance(o, str) and o.strip() for o in options):
        return False
    idx = q.get("correct_index")
    if not isinstance(idx, int) or not (0 <= idx < 4):
        return False
    if not isinstance(q.get("explanation"), str) or not q["explanation"].strip():
        return False
    if not isinstance(q.get("feedback_correct"), str) or not q["feedback_correct"].strip():
        return False
    if not isinstance(q.get("feedback_wrong"), str) or not q["feedback_wrong"].strip():
        return False
    # citations yapısal doğrulama; geçerlilik (izinli liste) _generate_batch'te denetlenir
    citations = q.get("citations")
    return isinstance(citations, list)


def _balanced(questions: list[dict]) -> bool:
    counts = [0] * 4
    for q in questions:
        idx = q["correct_index"]
        counts[idx] += 1
        if counts[idx] > MAX_CORRECT_PER_INDEX:
            return False
    return True


def _rebalance(questions: list[dict]) -> list[dict]:
    """Doğru cevap indexlerini seçenek yer değiştirerek dengeler (soru anlamı değişmez).

    Fazla temsil edilen bir index'teki sorunun iki seçeneği yer değiştirilir;
    doğru cevabın KENDİSİ az temsil edilen index'e taşınır.
    """
    counts = [0] * 4
    for q in questions:
        counts[q["correct_index"]] += 1

    for q in questions:
        idx = q["correct_index"]
        if counts[idx] <= MAX_CORRECT_PER_INDEX:
            counts[idx] += 1
            continue
        target = min(range(4), key=lambda i: (counts[i], i))
        options = list(q["options"])
        options[idx], options[target] = options[target], options[idx]
        q["options"] = options
        q["correct_index"] = target
        counts[target] += 1
    return questions


def _enrich_citations(questions: list[dict], allowed: list[dict]) -> list[dict]:
    """Soru atıflarını not atıf listesinden zenginleştirir (chunk_id, quote, page, slide)."""
    by_id = {c.get("id"): c for c in allowed}
    for question in questions:
        enriched = []
        for ref in question.get("citations", []):
            cid = ref.get("id")
            source = by_id.get(cid)
            if source is None:
                continue  # bilinmeyen atıf — soru doğrulamada yakalanır
            enriched.append(
                {
                    "id": cid,
                    "source_type": source.get("source_type", "note"),
                    "source_id": source.get("source_id"),
                    "page": source.get("page"),
                    "slide": source.get("slide"),
                    "chunk_id": source.get("chunk_id"),
                    "quote": source.get("quote", ""),
                }
            )
        question["citations"] = enriched
    return questions


# ── Sonsuz kaydırma feed'i için parti üretimi (Plan: feed) ──────────────
# Feed, bölüm quiziyle AYNI üretim hattını kullanır: aynı prompt, aynı doğrulama,
# aynı atıf zenginleştirme, aynı denge düzeltmesi. Fark yalnızca (a) tekrar yasağı
# negatif listesi, (b) soru başına `difficulty` alanı ve (c) partinin konulara
# round-robin dağıtılmasıdır — tek konudan yığılma olmaz.

FEED_BATCH_SIZE = 10
FEED_AVOID_LIMIT = 40  # negatif listeye alınan en fazla soru sayısı (prompt şişmesin)
_FEED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})

_FEED_EXTRA_PROMPT = """
8. TEKRAR YASAĞI: aşağıdaki sorular kullanıcıya yakın zamanda soruldu. Aynı bilgiyi ölçen
   veya benzer ifadeli soru ÜRETME; bölümün henüz sorulmamış ayrıntılarına yönel.
9. Her soruya ayrıca "difficulty" alanı ekle: "easy" | "medium" | "hard".

SORULMUŞ SORULAR (tekrar etme):
{avoid_list}
"""


def normalize_difficulty(value: object) -> str | None:
    """Modelin verdiği zorluk etiketini normalize eder; tanınmayan değer None olur."""
    if isinstance(value, str) and value.strip().lower() in _FEED_DIFFICULTIES:
        return value.strip().lower()
    return None


async def _generate_feed_topic(
    topic: dict,
    course_id: int,
    chapter_id: int,
    tenant_id: str,
    avoid: list[str],
    kazanimlar: str,
) -> list[dict]:
    """Bir konu için feed sorusu partisi üretir (bölüm quiziyle aynı doğrulama zinciri)."""
    allowed = topic.get("citations", [])
    allowed_text = json.dumps(
        [{"id": c.get("id")} for c in allowed if c.get("id") is not None],
        ensure_ascii=False,
    )
    avoid_list = "\n".join(f"- {q[:160]}" for q in avoid[-FEED_AVOID_LIMIT:]) or "- (yok)"
    prompt = QUIZ_BATCH_PROMPT.format(
        topic=topic["topic"],
        note_section=topic["section"][:4000],
        citations_json=allowed_text,
        dil_talimati=dil_talimati(settings.not_dili),
        kazanimlar=kazanimlar_blok(kazanimlar),
    ) + _FEED_EXTRA_PROMPT.format(avoid_list=avoid_list)

    try:
        data = await llm_service.chat_json(
            [{"role": "user", "content": prompt}],
            kind="feed_batch",
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        )
    except llm_service.LLMError:
        # Feed asla hata göstermez: başarısız parti sessizce atlanır, havuz mevcut
        # sorularla servis edilmeye devam eder.
        return []

    questions = [
        q for q in (data.get("questions") or []) if isinstance(q, dict) and _validate_question(q)
    ][:MAX_QUESTIONS_PER_TOPIC]
    if not questions:
        return []
    if allowed:
        questions = _enrich_citations(questions, allowed)
        first_citation = next((c for c in allowed if c.get("id") is not None), None)
        for q in questions:
            if not q["citations"] and first_citation is not None:
                q["citations"] = [dict(first_citation)]
    else:
        for q in questions:
            q["citations"] = []
    questions = _rebalance(questions)
    for q in questions:
        q["topic"] = topic["topic"]
        q["difficulty"] = normalize_difficulty(q.get("difficulty"))
    return questions


async def generate_feed_batch(
    chapter_id: int,
    tenant_id: str = LOCAL_TENANT_ID,
    *,
    count: int = FEED_BATCH_SIZE,
    avoid: list[str] | None = None,
    topic_offset: int = 0,
) -> list[dict]:
    """Bölüm notundan feed havuzu için `count` soruluk parti üretir.

    `topic_offset`: round-robin başlangıç konusu — çağıran taraf havuzdaki soru
    sayısını geçirerek ardışık partilerin farklı konulardan başlamasını sağlar.
    `avoid`: son sorulan soru metinleri (tekrar yasağı negatif listesi).

    Not bulunamazsa ya da hiçbir parti doğrulamayı geçemezse boş liste döner —
    feed hattı hata fırlatmaz (üst katman havuzu mevcut sorularla doldurur).
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            return []
        course_id = chapter["course_id"]
        cursor = await db.execute(
            "SELECT content_md, citations_json FROM notes "
            "WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC LIMIT 1",
            (chapter_id, tenant_id),
        )
        note_row = await cursor.fetchone()
        kazanimlar = await load_kazanimlar(db, course_id, tenant_id)
    finally:
        await db.close()

    if note_row is None:
        return []

    citations_json = json.loads(note_row["citations_json"] or "{}")
    sections = _split_topics(note_row["content_md"], citations_json.get("topics", []))
    if not sections:
        return []

    avoid_texts = list(avoid or [])
    collected: list[dict] = []
    max_calls = max(1, -(-count // MAX_QUESTIONS_PER_TOPIC)) + 1
    index = topic_offset
    for _ in range(max_calls):
        if len(collected) >= count:
            break
        topic = sections[index % len(sections)]
        index += 1
        batch = await _generate_feed_topic(
            topic,
            course_id,
            chapter_id,
            tenant_id,
            avoid_texts + [q["question"] for q in collected],
            kazanimlar,
        )
        collected.extend(batch)
    return collected[:count]

# ── Hata günlüğünden kurtarma quizi (Plan #6) ──────────────────────────────
# Aynı üretim/doğrulama zincirini (`_generate_feed_topic`) kullanır. Fark: konu
# kaynağı TEK bir bölüm değil ders geneli (her bölümün EN SON notu taranır, konu
# adı `topic_matches` ile eşlenir); `avoid` hata günlüğündeki (routers/errors.py
# Plan #5) soru metinleridir — LLM aynı soruları tekrar üretmesin diye negatif
# liste olarak prompt'a girer.


async def generate_from_errors(
    course_id: int,
    topics: list[str],
    avoid: list[str],
    tenant_id: str = LOCAL_TENANT_ID,
) -> list[dict]:
    """Verilen konular için dersin bölüm notlarından YENİ sorular üretir (Plan #6).

    Bir konu hiçbir bölüm notunda bulunamazsa sessizce atlanır (feed hattıyla aynı
    hata toleransı — LLM/kapsam hatası kullanıcıya asla gösterilmez, yalnızca o
    konudan soru üretilmez).
    """
    if not topics:
        return []

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.chapter_id, n.content_md, n.citations_json FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id AND c.tenant_id = n.tenant_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND n.tenant_id = ? "
            "AND n.id = (SELECT MAX(id) FROM notes WHERE chapter_id = n.chapter_id "
            "AND tenant_id = ?)",
            (course_id, tenant_id, tenant_id, tenant_id),
        )
        note_rows = [dict(row) for row in await cursor.fetchall()]
        kazanimlar = await load_kazanimlar(db, course_id, tenant_id)
    finally:
        await db.close()

    collected: list[dict] = []
    for note_row in note_rows:
        citations_json = json.loads(note_row["citations_json"] or "{}")
        sections = _split_topics(note_row["content_md"], citations_json.get("topics", []))
        for section in sections:
            if not any(topic_matches(section["topic"], wanted) for wanted in topics):
                continue
            batch = await _generate_feed_topic(
                section,
                course_id,
                note_row["chapter_id"],
                tenant_id,
                avoid + [q["question"] for q in collected],
                kazanimlar,
            )
            collected.extend(batch)
    return collected
