"""Sonsuz kaydırma quiz feed'i — sunucu havuzu servisi (Plan: feed).

Mimari (iki katmanlı buffer):
1. **Sunucu havuzu** (`feed_questions`): istek anında LLM ÇAĞRILMAZ. `serve_batch`
   havuzdan hazır soru claim eder; havuz `TARGET_POOL` altına inince `ensure_pool`
   arka planda (router'ın fire-and-forget task'ı + `workers/feed_topup` döngüsü)
   doldurur. Doldurma sırası: önce kullanıcının mevcut quizlerinden kopyalama
   (bedava, anında), yetmezse LLM ile `BATCH_SIZE`'lık parti üretimi.
2. **İstemci kuyruğu**: frontend 10 soru tutar, 5 altına inince yeni parti çeker.

Kalıcılık kararı — her üretilen feed partisi ayrıca gerçek bir `quizzes` satırı olarak
saklanır ve feed satırı `origin_question_id = '<quizzes.id>:<qid>'` ile ona bağlanır.
Böylece cevap kaydı hiçbir uydurma kolona ihtiyaç duymadan `quiz_attempts`'a yazılabilir
ve hata günlüğü (routers/errors.py) + zayıf konu ısı haritası (routers/heatmap.py)
mevcut sorgularıyla feed cevaplarını da görür.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from asyncpg.exceptions import UniqueViolationError

from ..auth import LOCAL_TENANT_ID, AuthError
from ..config import settings
from ..db import get_db
from ..quota import enforce_quota
from . import note_generator, quiz_generator, streak_service

logger = logging.getLogger(__name__)

# Havuz hedefi: bunun altına inince doldurma tetiklenir.
TARGET_POOL = 30
# LLM ile üretilen bir partinin soru sayısı.
BATCH_SIZE = quiz_generator.FEED_BATCH_SIZE
# Feed isteğinin varsayılan/azami parti boyutu.
DEFAULT_LIMIT = 10
MAX_LIMIT = 30
# Tekrar yasağı penceresi: prompt'a geçirilen son soru sayısı.
AVOID_WINDOW = 40

# Aynı ders için eşzamanlı doldurmayı engelleyen süreç-içi kilit. Router her GET'te
# fire-and-forget doldurma tetikler; worker da 30 sn'de bir tarar — kilit olmasa aynı
# ders için paralel LLM partileri üretilirdi (kota israfı + tekrar eden sorular).
_filling: set[tuple[str, int]] = set()

_POOL_WHERE = "tenant_id = ? AND course_id = ? AND served_at IS NULL AND consumed_at IS NULL"


def _cutoff(hours: int) -> datetime | str:
    """Zaman filtresi parametresi — SaaS/Postgres'te native `datetime`, SQLite'ta metin.

    `TIMESTAMPTZ` kolonuyla karşılaştırılan parametre asyncpg'de gerçek `datetime`
    olmalıdır (bkz. quota._month_start); SQLite tarafında `CURRENT_TIMESTAMP`
    'YYYY-MM-DD HH:MM:SS' (UTC) yazdığı için aynı biçimde metin karşılaştırılır.
    """
    moment = datetime.now(UTC) - timedelta(hours=hours)
    if settings.saas_mode:
        return moment
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _loads_list(value: object) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _public(row: dict) -> dict:
    """Feed satırını istemciye açık alanlara indirger — doğru cevap SIZDIRILMAZ."""
    return {
        "feed_id": row["id"],
        "question": row["question"],
        "options": _loads_list(row["options_json"]),
        "topic": row["topic"],
        "chapter_id": row["chapter_id"],
        "difficulty": row["difficulty"],
    }


async def _saved_ids(db, tenant_id: str, feed_ids: list[int]) -> set[int]:
    """Verilen feed_id'lerden kaydedilmiş olanları döner (tek sorgu, N+1 yok)."""
    placeholders = ", ".join(["?"] * len(feed_ids))
    cursor = await db.execute(
        "SELECT feed_question_id FROM saved_questions "  # nosec B608 - yer tutucu sayısı sabit `feed_ids` uzunluğudur, değerler parametreyle geçer
        f"WHERE tenant_id = ? AND feed_question_id IN ({placeholders})",
        (tenant_id, *feed_ids),
    )
    return {int(dict(row)["feed_question_id"]) for row in await cursor.fetchall()}


def _flatten_quiz(questions_json: dict) -> list[tuple[str, dict]]:
    """quiz `questions_json` → [(qid, soru)]; qid biçimi routers/quizzes.py `_flatten` ile aynı."""
    flattened: list[tuple[str, dict]] = []
    for t_idx, topic in enumerate(questions_json.get("topics", [])):
        if not isinstance(topic, dict):
            continue
        for q_idx, question in enumerate(topic.get("questions", [])):
            if isinstance(question, dict):
                flattened.append((f"{t_idx}-{q_idx}", question))
    return flattened


async def pool_size(
    course_id: int, tenant_id: str = LOCAL_TENANT_ID, chapter_id: int | None = None
) -> int:
    """Servis edilmeyi bekleyen (henüz gösterilmemiş) soru sayısı; `chapter_id` verilirse
    o bölümle sınırlanır."""
    where = _POOL_WHERE
    params: tuple = (tenant_id, course_id)
    if chapter_id is not None:
        where += " AND chapter_id = ?"
        params = (*params, chapter_id)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT COUNT(*) AS n FROM feed_questions WHERE {where}",  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
            params,
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return int(dict(row)["n"]) if row else 0


async def serve_batch(
    course_id: int,
    tenant_id: str = LOCAL_TENANT_ID,
    limit: int = DEFAULT_LIMIT,
    chapter_id: int | None = None,
) -> list[dict]:
    """Havuzdan `limit` soru claim edip döner (doğru cevap/açıklama YOK). `chapter_id`
    verilirse yalnızca o bölümün soruları servis edilir.

    Yarış koşulu: aday satırlar tek SELECT ile okunur, sonra her aday
    `UPDATE ... SET served_at = CURRENT_TIMESTAMP WHERE id = ? AND served_at IS NULL`
    ile tek tek claim edilir; `rowcount == 1` yalnızca claim'i KAZANAN çağrıda oluşur,
    böylece aynı soru iki istemciye servis edilemez. Bu kalıp `workers/indexer`'ın
    pending→processing geçişiyle aynıdır ve hem SQLite hem Postgres'te çalışır:
    lehçeye özgü `UPDATE ... RETURNING` / `FOR UPDATE SKIP LOCKED` kullanılmaz
    (pg_compat sarmalayıcısı yalnızca INSERT'e RETURNING ekler, UPDATE'in satırlarını
    döndürmez — bkz. src/pg_compat.py).
    """
    limit = max(1, min(limit, MAX_LIMIT))
    where = _POOL_WHERE
    params: tuple = (tenant_id, course_id)
    if chapter_id is not None:
        where += " AND chapter_id = ?"
        params = (*params, chapter_id)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, question, options_json, topic, chapter_id, difficulty "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
            f"FROM feed_questions WHERE {where} ORDER BY id LIMIT ?",
            # Kaybedilen claim'lere karşı fazladan aday okunur (tek ekstra roundtrip yok).
            (*params, limit * 3),
        )
        candidates = [dict(row) for row in await cursor.fetchall()]

        served: list[dict] = []
        for row in candidates:
            if len(served) >= limit:
                break
            update = await db.execute(
                "UPDATE feed_questions SET served_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND tenant_id = ? AND served_at IS NULL",
                (row["id"], tenant_id),
            )
            if update.rowcount == 1:
                served.append(_public(row))
        if served:
            saved_ids = await _saved_ids(db, tenant_id, [item["feed_id"] for item in served])
            for item in served:
                item["saved"] = item["feed_id"] in saved_ids
        await db.commit()
    finally:
        await db.close()
    return served


async def _existing_origins(db, course_id: int, tenant_id: str) -> set[str]:
    cursor = await db.execute(
        "SELECT origin_question_id FROM feed_questions "
        "WHERE tenant_id = ? AND course_id = ? AND origin_question_id IS NOT NULL",
        (tenant_id, course_id),
    )
    return {str(dict(row)["origin_question_id"]) for row in await cursor.fetchall()}


async def _insert_from_quiz(
    db,
    *,
    quiz_id: int,
    chapter_id: int | None,
    course_id: int,
    tenant_id: str,
    questions_json: dict,
    source: str,
    taken: set[str],
    remaining: int,
) -> int:
    """Bir quiz satırının sorularını feed havuzuna kopyalar; eklenen sayıyı döner."""
    inserted = 0
    topics = questions_json.get("topics", [])
    for qid, question in _flatten_quiz(questions_json):
        if inserted >= remaining:
            break
        origin = f"{quiz_id}:{qid}"
        if origin in taken:
            continue
        options = question.get("options")
        correct_index = question.get("correct_index")
        if not isinstance(options, list) or not isinstance(correct_index, int):
            continue
        t_idx = int(qid.split("-", 1)[0])
        topic_name = question.get("topic")
        if not topic_name and 0 <= t_idx < len(topics) and isinstance(topics[t_idx], dict):
            topic_name = topics[t_idx].get("topic")
        try:
            await db.execute(
                "INSERT INTO feed_questions "
                "(tenant_id, course_id, chapter_id, topic, question, options_json, "
                "correct_index, explanation, citations_json, difficulty, source, "
                "origin_question_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    course_id,
                    chapter_id,
                    str(topic_name) if topic_name else None,
                    str(question.get("question", "")),
                    json.dumps(options, ensure_ascii=False),
                    correct_index,
                    str(question.get("explanation") or ""),
                    json.dumps(question.get("citations") or [], ensure_ascii=False),
                    quiz_generator.normalize_difficulty(question.get("difficulty")),
                    source,
                    origin,
                ),
            )
        except (sqlite3.IntegrityError, UniqueViolationError):
            # Eşzamanlı bir çağrı (ör. iki eşzamanlı GET /feed isteğinin senkron
            # fallback'i, `ensure_pool` kilidiyle korunmaz) aynı origin'i bizden önce
            # yazdı — zaten alınmış say, hata fırlatma (2026-09-05, tam paket
            # koşusunda gerçek yarış koşulu olarak yakalandı).
            taken.add(origin)
            continue
        taken.add(origin)
        inserted += 1
    return inserted


async def backfill_from_existing(
    course_id: int,
    tenant_id: str = LOCAL_TENANT_ID,
    limit: int | None = None,
    chapter_id: int | None = None,
) -> int:
    """Dersin mevcut quiz sorularından havuza girmemiş olanları kopyalar (LLM'siz).

    `chapter_id` verilirse yalnızca o bölümün quizlerinden kopyalanır.
    `origin_question_id` ('<quiz_id>:<qid>') üzerinden çift kopyalama engellenir;
    en yeni quizler önce taranır. Eklenen soru sayısını döner.
    """
    remaining = TARGET_POOL if limit is None else limit
    if remaining <= 0:
        return 0
    db = await get_db()
    try:
        taken = await _existing_origins(db, course_id, tenant_id)
        where = "c.course_id = ? AND q.tenant_id = ?"
        params: tuple = (course_id, tenant_id)
        if chapter_id is not None:
            where += " AND q.chapter_id = ?"
            params = (*params, chapter_id)
        cursor = await db.execute(
            "SELECT q.id, q.chapter_id, q.questions_json FROM quizzes q "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
            "JOIN chapters c ON c.id = q.chapter_id AND c.tenant_id = q.tenant_id "
            f"WHERE {where} ORDER BY q.id DESC",
            params,
        )
        quizzes = [dict(row) for row in await cursor.fetchall()]

        inserted = 0
        for quiz in quizzes:
            if inserted >= remaining:
                break
            try:
                questions_json = json.loads(quiz["questions_json"] or "{}")
            except (TypeError, ValueError):
                continue
            if not isinstance(questions_json, dict):
                continue
            inserted += await _insert_from_quiz(
                db,
                quiz_id=quiz["id"],
                chapter_id=quiz["chapter_id"],
                course_id=course_id,
                tenant_id=tenant_id,
                questions_json=questions_json,
                source="existing",
                taken=taken,
                remaining=remaining - inserted,
            )
        await db.commit()
    finally:
        await db.close()
    return inserted


async def _pick_chapter(course_id: int, tenant_id: str) -> int | None:
    """Üretim için en az temsil edilen (notu olan) bölümü seçer — bölümler arası round-robin."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT c.id AS chapter_id, "
            "(SELECT COUNT(*) FROM feed_questions f "
            " WHERE f.chapter_id = c.id AND f.tenant_id = ?) AS pool_count "
            "FROM chapters c "
            "WHERE c.course_id = ? AND c.tenant_id = ? "
            "AND EXISTS (SELECT 1 FROM notes n WHERE n.chapter_id = c.id AND n.tenant_id = ?) "
            "ORDER BY pool_count ASC, c.id ASC LIMIT 1",
            (tenant_id, course_id, tenant_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return int(dict(row)["chapter_id"]) if row else None


async def _recent_questions(course_id: int, tenant_id: str) -> list[str]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT question FROM feed_questions WHERE tenant_id = ? AND course_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (tenant_id, course_id, AVOID_WINDOW),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [str(dict(row)["question"]) for row in rows]


async def _chapter_pool_count(chapter_id: int, tenant_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM feed_questions WHERE tenant_id = ? AND chapter_id = ?",
            (tenant_id, chapter_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return int(dict(row)["n"]) if row else 0


async def _persist_generated(
    questions: list[dict], chapter_id: int, course_id: int, tenant_id: str
) -> int:
    """Üretilen partiyi gerçek bir `quizzes` satırı + feed satırları olarak yazar."""
    grouped: list[dict] = []
    index_by_topic: dict[str, int] = {}
    for question in questions:
        topic = str(question.get("topic") or "Genel")
        idx = index_by_topic.get(topic)
        if idx is None:
            idx = index_by_topic[topic] = len(grouped)
            grouped.append({"topic": topic, "questions": []})
        grouped[idx]["questions"].append(question)
    questions_json = {"topics": grouped}

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await db.commit()
        quiz_id = cursor.lastrowid
        if quiz_id is None:
            return 0
        inserted = await _insert_from_quiz(
            db,
            quiz_id=quiz_id,
            chapter_id=chapter_id,
            course_id=course_id,
            tenant_id=tenant_id,
            questions_json=questions_json,
            source="generated",
            taken=set(),
            remaining=len(questions),
        )
        await db.commit()
    finally:
        await db.close()
    return inserted


async def ensure_pool(
    course_id: int, tenant_id: str = LOCAL_TENANT_ID, chapter_id: int | None = None
) -> int:
    """Havuzu `TARGET_POOL`'a yaklaştırır; eklenen soru sayısını döner.

    `chapter_id` verilirse havuz büyüklüğü/dolgu o bölümle sınırlanır ve üretim
    doğrudan o bölüm için yapılır (`_pick_chapter` round-robin'i atlanır).
    Sıra: (1) mevcut quiz sorularından kopyalama — bedava ve anında, (2) hâlâ eksikse
    LLM ile `BATCH_SIZE`'lık parti. Kota aşılmışsa üretim sessizce atlanır (feed
    yine havuzdan servis edilir, kullanıcıya 402 gösterilmez).
    """
    key = (tenant_id, course_id)
    if key in _filling:
        return 0
    _filling.add(key)
    try:
        size = await pool_size(course_id, tenant_id, chapter_id)
        if size >= TARGET_POOL:
            return 0
        added = await backfill_from_existing(
            course_id, tenant_id, TARGET_POOL - size, chapter_id
        )
        if size + added >= TARGET_POOL:
            return added

        try:
            await enforce_quota(tenant_id)
        except AuthError:
            logger.info("feed havuzu: kota dolu, üretim atlandı (course=%s)", course_id)
            return added

        target_chapter_id = chapter_id
        if target_chapter_id is None:
            target_chapter_id = await _pick_chapter(course_id, tenant_id)
        if target_chapter_id is None:
            return added
        questions = await quiz_generator.generate_feed_batch(
            target_chapter_id,
            tenant_id,
            count=BATCH_SIZE,
            avoid=await _recent_questions(course_id, tenant_id),
            topic_offset=await _chapter_pool_count(target_chapter_id, tenant_id),
        )
        if not questions:
            return added
        return added + await _persist_generated(
            questions, target_chapter_id, course_id, tenant_id
        )
    except Exception:
        logger.exception("feed havuzu doldurma başarısız: course=%s", course_id)
        return 0
    finally:
        _filling.discard(key)


_pending_tasks: set[asyncio.Task] = set()


def spawn_topup(course_id: int, tenant_id: str, chapter_id: int | None = None) -> None:
    """Doldurmayı fire-and-forget başlatır — istek BEKLEMEZ (havuz zaten servis edildi)."""
    task = asyncio.create_task(ensure_pool(course_id, tenant_id, chapter_id))
    # Referansı düşürmemek için görev tamamlanınca kendini temizler (GC koruması).
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def _latest_note_id(db, chapter_id: int | None, tenant_id: str) -> int | None:
    if chapter_id is None:
        return None
    cursor = await db.execute(
        "SELECT id FROM notes WHERE chapter_id = ? AND tenant_id = ? ORDER BY id DESC LIMIT 1",
        (chapter_id, tenant_id),
    )
    row = await cursor.fetchone()
    return int(dict(row)["id"]) if row else None


async def _record_attempt(
    db, row: dict, *, selected_index: int, correct: bool, elapsed_ms: int, tenant_id: str
) -> None:
    """Feed cevabını `quiz_attempts`'a yazar (hata günlüğü + ısı haritası bundan beslenir).

    Eşleme: feed satırının `origin_question_id`'si '<quizzes.id>:<qid>' biçimindedir —
    her feed sorusunun (kopyalanmış ya da feed için üretilmiş) arkasında gerçek bir
    `quizzes` satırı vardır. Bu yüzden yeni kolona ihtiyaç yoktur:
    `quiz_id` = o quiz, `user_answers_json` = [{"qid", "selected_index"}] (heatmap.py
    tam bu biçimi okur), `feedback_json.results` = tek elemanlı sonuç listesi
    (errors.py `_chapter_entries` tam bu biçimi okur), `score` = 100/0 (tek soruluk
    deneme). `elapsed_ms` sonucun içine yazılır — quiz_attempts'ta süre kolonu yok.
    """
    origin = row.get("origin_question_id")
    if not origin or ":" not in str(origin):
        return
    quiz_id_text, qid = str(origin).split(":", 1)
    if not quiz_id_text.isdigit():
        return
    options = _loads_list(row["options_json"])
    result = {
        "qid": qid,
        "question": row["question"],
        "options": options,
        "selected_index": selected_index,
        "correct_index": row["correct_index"],
        "correct": correct,
        "explanation": row["explanation"],
        "citations": _loads_list(row["citations_json"]),
        "elapsed_ms": elapsed_ms,
        "source": "feed",
    }
    await db.execute(
        "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, feedback_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            tenant_id,
            int(quiz_id_text),
            json.dumps([{"qid": qid, "selected_index": selected_index}], ensure_ascii=False),
            100.0 if correct else 0.0,
            json.dumps({"results": [result]}, ensure_ascii=False),
        ),
    )


async def record_answer(
    feed_id: int, tenant_id: str, selected_index: int, elapsed_ms: int = 0
) -> dict | None:
    """Cevabı değerlendirir, soruyu tüketilmiş işaretler, denemeyi kaydeder.

    Soru bulunamazsa (ya da başka kiracıya aitse) None döner — router 404 verir.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, chapter_id, topic, question, options_json, correct_index, "
            "explanation, citations_json, origin_question_id, consumed_at "
            "FROM feed_questions WHERE id = ? AND tenant_id = ?",
            (feed_id, tenant_id),
        )
        found = await cursor.fetchone()
        if found is None:
            return None
        row = dict(found)
        correct = selected_index == row["correct_index"]
        already = row["consumed_at"] is not None
        await db.execute(
            "UPDATE feed_questions SET consumed_at = CURRENT_TIMESTAMP, "
            "served_at = COALESCE(served_at, CURRENT_TIMESTAMP) "
            "WHERE id = ? AND tenant_id = ?",
            (feed_id, tenant_id),
        )
        if not already:
            # Aynı soru iki kez cevaplanırsa istatistik şişmesin.
            await _record_attempt(
                db,
                row,
                selected_index=selected_index,
                correct=correct,
                elapsed_ms=elapsed_ms,
                tenant_id=tenant_id,
            )
        note_id = await _latest_note_id(db, row["chapter_id"], tenant_id)
        await db.commit()
    finally:
        await db.close()

    if not already:
        await streak_service.log_activity("quiz", row["course_id"], tenant_id)

    return {
        "correct": correct,
        "correct_index": row["correct_index"],
        "explanation": row["explanation"] or "",
        "citations": _loads_list(row["citations_json"]) or None,
        "note_id": note_id,
        "chapter_id": row["chapter_id"],
    }


async def skip(feed_id: int, tenant_id: str) -> bool:
    """Soruyu atlanmış işaretler — bir daha servis edilmez. Bulunamazsa False."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE feed_questions SET consumed_at = CURRENT_TIMESTAMP, "
            "served_at = COALESCE(served_at, CURRENT_TIMESTAMP) "
            "WHERE id = ? AND tenant_id = ?",
            (feed_id, tenant_id),
        )
        await db.commit()
    finally:
        await db.close()
    return cursor.rowcount == 1


async def active_course_ids(hours: int = 24) -> list[tuple[str, int]]:
    """Son `hours` saatte feed kullanılan (kiracı, ders) çiftleri — worker bunları doldurur."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT tenant_id, course_id FROM feed_questions "
            "WHERE served_at IS NOT NULL AND served_at >= ?",
            (_cutoff(hours),),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    return [(str(dict(r)["tenant_id"]), int(dict(r)["course_id"])) for r in rows]


# ── Ustalık ilerlemesi (Plan: kaydırmalı quiz #7) ───────────────────────

def _topic_from_qid(qid: object, topic_names: list[str]) -> str:
    """qid '<topic_idx>-<q_idx>' → konu adı (routers/errors.py `_topic_from_qid` ile aynı desen)."""
    prefix = str(qid or "").split("-", 1)[0]
    if prefix.isdigit():
        index = int(prefix)
        if 0 <= index < len(topic_names) and topic_names[index]:
            return topic_names[index]
    return "Genel"


async def _chapter_topic_names(db, chapter_id: int, tenant_id: str) -> list[str]:
    """Bölümün en son notundaki konu adları (ustalık çubuğunun paydası)."""
    cursor = await db.execute(
        "SELECT topics_json FROM notes WHERE chapter_id = ? AND tenant_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (chapter_id, tenant_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return []
    topics = _loads_list(dict(row)["topics_json"])
    return [str(t["topic"]) for t in topics if isinstance(t, dict) and t.get("topic")]


async def _topic_correct_counts(
    db, tenant_id: str, *, chapter_id: int | None, course_id: int | None
) -> dict[int, dict[str, int]]:
    """chapter_id → {konu etiketi: doğru sayılan FARKLI soru sayısı}.

    Aynı soru (quiz_id, qid) birden çok kez cevaplanmışsa (chapter quiz yeniden
    çözüldüğünde) yalnızca EN SON denemesi sayılır — `a.id ASC` sırayla iterasyonda
    sonraki satır öncekinin üzerine yazar.
    """
    if chapter_id is not None:
        cursor = await db.execute(
            "SELECT a.id, a.quiz_id, a.feedback_json, q.chapter_id, q.questions_json "
            "FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
            "WHERE q.chapter_id = ? AND a.tenant_id = ? ORDER BY a.id ASC",
            (chapter_id, tenant_id),
        )
    else:
        cursor = await db.execute(
            "SELECT a.id, a.quiz_id, a.feedback_json, q.chapter_id, q.questions_json "
            "FROM quiz_attempts a "
            "JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
            "JOIN chapters c ON c.id = q.chapter_id AND c.tenant_id = q.tenant_id "
            "WHERE c.course_id = ? AND a.tenant_id = ? ORDER BY a.id ASC",
            (course_id, tenant_id),
        )
    rows = [dict(r) for r in await cursor.fetchall()]

    latest: dict[tuple[int, int, str], tuple[str, bool]] = {}
    for row in rows:
        try:
            questions_json = json.loads(row["questions_json"] or "{}")
        except (TypeError, ValueError):
            questions_json = {}
        topic_names = [
            str(t.get("topic", ""))
            for t in questions_json.get("topics", [])
            if isinstance(t, dict)
        ]
        try:
            feedback = json.loads(row["feedback_json"] or "{}")
        except (TypeError, ValueError):
            feedback = {}
        results = feedback.get("results", []) if isinstance(feedback, dict) else []
        for result in results:
            if not isinstance(result, dict) or result.get("qid") is None:
                continue
            qid = str(result["qid"])
            label = _topic_from_qid(qid, topic_names)
            latest[(row["chapter_id"], row["quiz_id"], qid)] = (
                label,
                bool(result.get("correct")),
            )

    per_chapter: dict[int, dict[str, int]] = {}
    for (chap_id, _quiz_id, _qid), (label, correct) in latest.items():
        if not correct:
            continue
        bucket = per_chapter.setdefault(chap_id, {})
        bucket[label] = bucket.get(label, 0) + 1
    return per_chapter


def _mastery_payload(topic_names: list[str], topic_correct: dict[str, int]) -> dict:
    """Konu listesi + {etiket: doğru sayısı} → ustalık yüzdesi.

    Yüzde = sum(min(dogru_t, 5)) / (konu_sayısı * 5); konu 0 ise 0. Etiket eşlemesi
    ham `==` değil `note_generator.topic_matches` (fuzzy, LLM başlık sapmalarına
    tolerans) ile yapılır.
    """
    topics = []
    total_correct = 0
    for name in topic_names:
        correct = sum(
            count
            for label, count in topic_correct.items()
            if note_generator.topic_matches(label, name)
        )
        capped = min(correct, 5)
        total_correct += capped
        topics.append({"topic": name, "correct": capped, "target": 5})
    total = len(topic_names) * 5
    percent = min(100.0, round(100 * total_correct / total, 2)) if total else 0.0
    return {"percent": percent, "correct": total_correct, "total": total, "topics": topics}


async def chapter_mastery(chapter_id: int, tenant_id: str = LOCAL_TENANT_ID) -> dict:
    """Bir bölümün ustalık ilerlemesi (GET /api/chapters/{chapter_id}/mastery)."""
    db = await get_db()
    try:
        topic_names = await _chapter_topic_names(db, chapter_id, tenant_id)
        topic_correct = (
            await _topic_correct_counts(db, tenant_id, chapter_id=chapter_id, course_id=None)
        ).get(chapter_id, {})
    finally:
        await db.close()
    return _mastery_payload(topic_names, topic_correct)


async def course_mastery(course_id: int, tenant_id: str = LOCAL_TENANT_ID) -> dict:
    """Bir dersin ustalık ilerlemesi — tüm bölümlerin toplamı.

    GET /api/courses/{course_id}/mastery tarafından çağrılır.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM chapters WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        chapter_ids = [int(dict(row)["id"]) for row in await cursor.fetchall()]
        per_chapter_correct = await _topic_correct_counts(
            db, tenant_id, chapter_id=None, course_id=course_id
        )
        topics: list[dict] = []
        total_correct = 0
        total = 0
        for cid in chapter_ids:
            names = await _chapter_topic_names(db, cid, tenant_id)
            chapter_payload = _mastery_payload(names, per_chapter_correct.get(cid, {}))
            topics.extend(chapter_payload["topics"])
            total_correct += chapter_payload["correct"]
            total += chapter_payload["total"]
    finally:
        await db.close()
    percent = min(100.0, round(100 * total_correct / total, 2)) if total else 0.0
    return {"percent": percent, "correct": total_correct, "total": total, "topics": topics}


# ── Kaydedilen sorular (Plan: kaydırmalı quiz #8) ───────────────────────

async def save_question(feed_id: int, tenant_id: str) -> bool:
    """Feed sorusunu kaydeder (idempotent — zaten kayıtlıysa hata vermez).

    Soru bulunamaz/başka kiracıya aitse False döner (router 404 verir).
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM feed_questions WHERE id = ? AND tenant_id = ?", (feed_id, tenant_id)
        )
        if await cursor.fetchone() is None:
            return False
        with contextlib.suppress(sqlite3.IntegrityError, UniqueViolationError):
            await db.execute(
                "INSERT INTO saved_questions (tenant_id, feed_question_id) VALUES (?, ?)",
                (tenant_id, feed_id),
            )
        await db.commit()
    finally:
        await db.close()
    return True


async def unsave_question(feed_id: int, tenant_id: str) -> None:
    """Kaydı kaldırır — kayıtlı değilse sessizce no-op (idempotent)."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM saved_questions WHERE tenant_id = ? AND feed_question_id = ?",
            (tenant_id, feed_id),
        )
        await db.commit()
    finally:
        await db.close()


async def list_saved(tenant_id: str, limit: int = 200) -> list[dict]:
    """Kaydedilen sorular — en yeni önce (GET /api/saved-questions)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT s.feed_question_id AS feed_id, s.created_at AS saved_at, "
            "f.question, f.options_json, f.correct_index, f.explanation, f.topic, "
            "f.chapter_id, c.title AS chapter_title, c.course_id, co.name AS course_name "
            "FROM saved_questions s "
            "JOIN feed_questions f ON f.id = s.feed_question_id AND f.tenant_id = s.tenant_id "
            "JOIN chapters c ON c.id = f.chapter_id AND c.tenant_id = f.tenant_id "
            "JOIN courses co ON co.id = c.course_id AND co.tenant_id = f.tenant_id "
            "WHERE s.tenant_id = ? ORDER BY s.created_at DESC LIMIT ?",
            (tenant_id, limit),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
    return [
        {
            "feed_id": row["feed_id"],
            "question": row["question"],
            "options": _loads_list(row["options_json"]),
            "correct_index": row["correct_index"],
            "explanation": row["explanation"],
            "topic": row["topic"],
            "chapter_id": row["chapter_id"],
            "chapter_title": row["chapter_title"],
            "course_id": row["course_id"],
            "course_name": row["course_name"],
            "saved_at": row["saved_at"],
        }
        for row in rows
    ]
