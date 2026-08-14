"""Genel quiz router testleri — üretim, answer_key gizliliği, 4 tipli değerlendirme (Faz 5)."""

import json

from src.config import settings
from src.routers import overall as overall_router


def _questions_json():
    return {
        "seed": 42,
        "questions": [
            {
                "type": "mcq",
                "topic": "Konu A",
                "question": "MCQ sorusu?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
                "explanation": "e",
                "feedback_correct": "Doğru!",
                "feedback_wrong": "Yanlış.",
                "citations": [{"id": 1, "chunk_id": "chk_9_1_1", "quote": "kaynak"}],
            },
            {
                "type": "tf",
                "topic": "Konu A",
                "statement": "TF ifadesi.",
                "answer": True,
                "explanation": "e",
                "feedback_correct": "Doğru!",
                "feedback_wrong": "Yanlış.",
                "citations": [{"id": 1, "chunk_id": "chk_9_1_1", "quote": "kaynak"}],
            },
            {
                "type": "fib",
                "topic": "Konu A",
                "text": "Bağlı liste ____ yapıdır.",
                "accepted_answers": ["doğrusal", "lineer"],
                "explanation": "e",
                "feedback_correct": "Doğru!",
                "feedback_wrong": "Doğru cevap: doğrusal.",
                "citations": [{"id": 1, "chunk_id": "chk_9_1_1", "quote": "kaynak"}],
            },
            {
                "type": "open",
                "topic": "Konu A",
                "question": "Açık uçlu soru?",
                "answer_key_ref": "oq_3",
            },
        ],
        "answer_keys": {"oq_3": {"points": ["nokta a", "nokta b"], "citations": [{"id": 1}]}},
    }


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _insert_quiz(client, course_id: int) -> int:
    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO overall_quizzes (course_id, questions_json) VALUES (?, ?)",
            (course_id, json.dumps(_questions_json(), ensure_ascii=False)),
        )
        await conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("quiz kimliği alınamadı")
        return row_id


async def test_overall_sse_endpoint(client, monkeypatch):
    course_id = await _make_course(client)

    async def fake_generator(course_id):
        yield {"type": "status", "percent": 10, "message": "Üretiliyor…"}
        yield {
            "type": "done",
            "quiz": {"id": 1, "course_id": course_id, "seed": 1, "questions": []},
        }

    monkeypatch.setattr(overall_router, "generate_overall_quiz_stream", fake_generator)
    resp = await client.post(f"/api/courses/{course_id}/overall-quiz")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert '"type": "done"' in resp.text


async def test_get_overall_quiz_hides_answer_keys(client):
    course_id = await _make_course(client)
    quiz_id = await _insert_quiz(client, course_id)

    resp = await client.get(f"/api/courses/{course_id}/overall-quiz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == quiz_id
    assert "answer_keys" not in body["questions_json"]
    # hiçbir soruda "answer_key" alanı olmamalı (yalnızca answer_key_ref)
    assert all("answer_key" not in q for q in body["questions_json"]["questions"])
    open_q = next(q for q in body["questions_json"]["questions"] if q["type"] == "open")
    assert open_q["answer_key_ref"] == "oq_3"


async def test_submit_overall_attempt(client, monkeypatch):
    course_id = await _make_course(client)
    quiz_id = await _insert_quiz(client, course_id)

    async def fake_grade(**kwargs):
        return {
            "score": 8,
            "correct": ["nokta a"],
            "missing": ["nokta b"],
            "incorrect": ["yok"],
            "unnecessary": ["yok"],
            "explanation": "Gerekçe.",
            "ideal_answer": "İdeal [1].",
            "confidence": 0.9,
        }

    monkeypatch.setattr(overall_router, "grade_essay", fake_grade)

    resp = await client.post(
        f"/api/overall-quizzes/{quiz_id}/attempts",
        json={
            "answers": [
                {"qid": 0, "value": 0},  # mcq doğru
                {"qid": 1, "value": 1},  # tf doğru (1 = Doğru)
                {"qid": 2, "value": "doğrusal"},  # fib doğru
                {"qid": 3, "value": "cevap metni"},  # açık uçlu → 8
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # kapalı: 3/3 doğru → 3 puan; açık: 8 puan; toplam 11 (mcq/tf/fib 1'er, açık 10)
    assert body["score"] == 11
    assert body["closed_correct"] == 3
    assert body["open_total"] == 8
    assert body["results"][2]["correct"] is True
    open_result = body["results"][3]
    assert open_result["score"] == 8
    assert open_result["grade"]["ideal_answer"] == "İdeal [1]."
    assert "answer_key" not in json.dumps(body["results"])


async def test_submit_overall_attempt_wrong_fib(client, monkeypatch):
    course_id = await _make_course(client)
    quiz_id = await _insert_quiz(client, course_id)

    async def fake_grade(**kwargs):
        return {
            "score": 0,
            "correct": [],
            "missing": ["nokta a", "nokta b"],
            "incorrect": [],
            "unnecessary": ["yok"],
            "explanation": "Boş.",
            "ideal_answer": "İdeal.",
            "confidence": 1.0,
        }

    monkeypatch.setattr(overall_router, "grade_essay", fake_grade)

    resp = await client.post(
        f"/api/overall-quizzes/{quiz_id}/attempts",
        json={
            "answers": [
                {"qid": 0, "value": 1},  # mcq yanlış
                {"qid": 1, "value": 0},  # tf yanlış
                {"qid": 2, "value": "yanlış cevap"},  # fib yanlış
                {"qid": 3, "value": ""},  # açık boş → 0
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["closed_correct"] == 0
    assert body["score"] == 0
    assert body["results"][2]["correct"] is False
    assert body["results"][2]["accepted_answers"] == ["doğrusal", "lineer"]
