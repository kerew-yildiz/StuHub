"""Hata günlüğü router'ı — geçmiş denemelerdeki yanlış cevapları ders bazında toplar (plan #5).

Yeni tablo YOK, LLM YOK: veri zaten `quiz_attempts.feedback_json` (chapter quizleri) ve
`overall_attempts.score_json` (genel quizler) içinde kayıtlı. Bu uç yalnızca mevcut satırları
ders kapsamında okur, yanlış olanları süzer ve konu bazlı tekrar sayısını çıkarır.

Cevap anahtarı sızıntısı: `quizzes.questions_json`/`overall_quizzes.questions_json` yalnızca
konu adı için okunur; `answer_keys` bloğu hiç kullanılmaz. Doğru cevap alanı, kullanıcıya
deneme anında zaten gösterilmiş olan METİN (seçenek metni, Doğru/Yanlış, kabul edilen cevap,
ideal cevap) olarak döner.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["errors"])

# Cevaplanmamış/çözümlenemeyen seçim için gösterilecek metin
_BLANK_ANSWER = "(boş)"
_UNKNOWN_TOPIC = "Genel"

_TF_LABEL = {True: "Doğru", False: "Yanlış"}

# Chapter quiz denemeleri: ders kapsamı chapters üzerinden kurulur
_CHAPTER_ATTEMPTS_SQL = (
    "SELECT a.id AS attempt_id, a.quiz_id, a.feedback_json, a.created_at, "
    "q.chapter_id, q.questions_json "
    "FROM quiz_attempts a "
    "JOIN quizzes q ON q.id = a.quiz_id AND q.tenant_id = a.tenant_id "
    "JOIN chapters c ON c.id = q.chapter_id AND c.tenant_id = q.tenant_id "
    "WHERE c.course_id = ? AND a.tenant_id = ? "
    "ORDER BY a.id DESC"
)

# Genel quiz denemeleri: ders kapsamı doğrudan overall_quizzes.course_id
_OVERALL_ATTEMPTS_SQL = (
    "SELECT a.id AS attempt_id, a.overall_quiz_id, a.score_json, a.created_at, "
    "o.questions_json "
    "FROM overall_attempts a "
    "JOIN overall_quizzes o ON o.id = a.overall_quiz_id AND o.tenant_id = a.tenant_id "
    "WHERE o.course_id = ? AND a.tenant_id = ? "
    "ORDER BY a.id DESC"
)


class ErrorLogEntry(BaseModel):
    """Tek bir yanlış cevap kaydı."""

    question_text: str
    given_answer: str
    correct_answer: str
    topic: str
    quiz_id: int
    chapter_id: int | None = None
    created_at: str
    # Aynı konuda (seçilen zaman aralığında) toplam kaç kez yanlış yapıldığı
    repeat_count: int


def _loads(value: Any) -> dict:
    """JSON kolonunu sözlüğe çevirir; boş/bozuk değerde boş sözlük döner."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    """`created_at`'i (SQLite 'YYYY-MM-DD HH:MM:SS' veya Postgres ISO) datetime'a çevirir."""
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _option_text(options: Any, index: Any) -> str:
    """Seçenek listesinden indeksin metnini döner; geçersizse '(boş)'."""
    if isinstance(options, list) and isinstance(index, int) and 0 <= index < len(options):
        return str(options[index])
    return _BLANK_ANSWER


def _first_text(values: Any) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    return _BLANK_ANSWER


def _topic_from_qid(qid: Any, topic_names: list[str]) -> str:
    """Chapter quiz qid'i '<topic_idx>-<q_idx>' biçimindedir; konu adını oradan çözer."""
    prefix = str(qid or "").split("-", 1)[0]
    if prefix.isdigit():
        index = int(prefix)
        if 0 <= index < len(topic_names) and topic_names[index]:
            return topic_names[index]
    return _UNKNOWN_TOPIC


def _chapter_entries(row: dict) -> list[dict]:
    """Bir chapter quiz denemesinin yanlış cevaplarını çıkarır."""
    feedback = _loads(row["feedback_json"])
    questions_json = _loads(row["questions_json"])
    topic_names = [
        str(topic.get("topic", ""))
        for topic in questions_json.get("topics", [])
        if isinstance(topic, dict)
    ]

    entries: list[dict] = []
    for result in feedback.get("results", []):
        if not isinstance(result, dict) or result.get("correct"):
            continue
        options = result.get("options")
        entries.append(
            {
                "question_text": str(result.get("question", "")),
                "given_answer": _option_text(options, result.get("selected_index")),
                "correct_answer": _option_text(options, result.get("correct_index")),
                "topic": _topic_from_qid(result.get("qid"), topic_names),
                "quiz_id": row["quiz_id"],
                "chapter_id": row["chapter_id"],
                "created_at": row["created_at"],
                "_attempt_id": row["attempt_id"],
            }
        )
    return entries


def _overall_answer_pair(result: dict) -> tuple[str, str]:
    """Genel quiz sonucundan (verilen cevap, doğru cevap) metinlerini üretir."""
    qtype = result.get("type")
    if qtype == "mcq":
        options = result.get("options")
        return (
            _option_text(options, result.get("selected_index")),
            _option_text(options, result.get("correct_index")),
        )
    if qtype == "tf":
        selected = result.get("selected_tf")
        given = _TF_LABEL[selected == 1] if isinstance(selected, int) else _BLANK_ANSWER
        answer = result.get("answer")
        correct = _TF_LABEL[bool(answer)] if isinstance(answer, bool) else _BLANK_ANSWER
        return given, correct
    if qtype == "fib":
        given = str(result.get("user_answer") or "") or _BLANK_ANSWER
        return given, _first_text(result.get("accepted_answers"))
    # open: puanlama anında üretilen ideal cevap metni (ham answer_key değil)
    given = str(result.get("user_answer") or "") or _BLANK_ANSWER
    raw_grade = result.get("grade")
    grade: dict = raw_grade if isinstance(raw_grade, dict) else {}
    return given, str(grade.get("ideal_answer") or "") or _BLANK_ANSWER


def _overall_entries(row: dict) -> list[dict]:
    """Bir genel quiz denemesinin yanlış cevaplarını çıkarır (chapter_id yok)."""
    score_json = _loads(row["score_json"])
    questions = _loads(row["questions_json"]).get("questions", [])

    entries: list[dict] = []
    for result in score_json.get("results", []):
        if not isinstance(result, dict) or result.get("correct"):
            continue
        qid = result.get("qid")
        in_range = isinstance(qid, int) and 0 <= qid < len(questions)
        question = questions[qid] if in_range and isinstance(questions[qid], dict) else {}
        given_answer, correct_answer = _overall_answer_pair(result)
        entries.append(
            {
                "question_text": str(
                    result.get("question") or result.get("statement") or result.get("text") or ""
                ),
                "given_answer": given_answer,
                "correct_answer": correct_answer,
                "topic": str(question.get("topic") or "") or _UNKNOWN_TOPIC,
                "quiz_id": row["overall_quiz_id"],
                "chapter_id": None,
                "created_at": row["created_at"],
                "_attempt_id": row["attempt_id"],
            }
        )
    return entries


@router.get("/courses/{course_id}/errors", response_model=list[ErrorLogEntry])
async def list_course_errors(
    course_id: int,
    topic: str | None = Query(default=None, description="Yalnızca bu konudaki hatalar"),
    since: str | None = Query(default=None, description="ISO tarih; bu andan sonraki hatalar"),
    only_repeated: bool = Query(
        default=False, description="Yalnızca 2+ kez yanlış yapılan konular"
    ),
    tenant_id: str = Depends(get_tenant_id),
) -> list[ErrorLogEntry]:
    """Dersteki tüm yanlış cevapları (yeniden eskiye) döner.

    `repeat_count`, `since` ile daraltılan pencere içinde konunun kaç kez yanlış yapıldığıdır;
    `topic`/`only_repeated` süzgeçleri bu sayım yapıldıktan SONRA uygulanır, böylece filtreleme
    tekrar sayısını değiştirmez.
    """
    since_dt: datetime | None = None
    if since:
        since_dt = _parse_ts(since)
        if since_dt is None:
            raise HTTPException(status_code=422, detail="Geçersiz tarih biçimi (ISO bekleniyor).")

    db = await get_db()
    try:
        cursor = await db.execute(_CHAPTER_ATTEMPTS_SQL, (course_id, tenant_id))
        chapter_rows = [dict(row) for row in await cursor.fetchall()]
        cursor = await db.execute(_OVERALL_ATTEMPTS_SQL, (course_id, tenant_id))
        overall_rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()

    entries: list[dict] = []
    for row in chapter_rows:
        entries.extend(_chapter_entries(row))
    for row in overall_rows:
        entries.extend(_overall_entries(row))

    if since_dt is not None:
        entries = [
            entry
            for entry in entries
            if (parsed := _parse_ts(entry["created_at"])) is not None and parsed >= since_dt
        ]

    # Konu bazlı tekrar sayısı — pencere içindeki tüm hatalar üzerinden
    repeats: dict[str, int] = {}
    for entry in entries:
        repeats[entry["topic"]] = repeats.get(entry["topic"], 0) + 1

    epoch = datetime.min.replace(tzinfo=UTC)

    def _sort_key(entry: dict) -> tuple[datetime, int]:
        return (_parse_ts(entry["created_at"]) or epoch, entry["_attempt_id"])

    entries.sort(key=_sort_key, reverse=True)

    wanted_topic = topic.strip() if topic else ""
    return [
        ErrorLogEntry(
            question_text=entry["question_text"],
            given_answer=entry["given_answer"],
            correct_answer=entry["correct_answer"],
            topic=entry["topic"],
            quiz_id=entry["quiz_id"],
            chapter_id=entry["chapter_id"],
            created_at=str(entry["created_at"]),
            repeat_count=repeats[entry["topic"]],
        )
        for entry in entries
        if (not wanted_topic or entry["topic"] == wanted_topic)
        and (not only_repeated or repeats[entry["topic"]] >= 2)
    ]
