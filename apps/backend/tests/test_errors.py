"""Hata günlüğü router testleri — yanlış cevap toplama, tekrar süzgeci,
kiracı izolasyonu (plan #5)."""

import json

import aiosqlite

from src.config import settings


async def _insert(sql: str, params: tuple) -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(sql, params)
        await conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("satır kimliği alınamadı")
        return row_id


async def _make_course(client) -> tuple[int, int]:
    """(course_id, chapter_id) üretir."""
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bölüm 1"})
    return course_id, resp.json()["id"]


def _questions_json() -> dict:
    return {
        "topics": [
            {
                "topic": "Konu A",
                "questions": [
                    {"question": "Bağlı liste nedir?", "options": ["A", "B", "C", "D"]},
                    {"question": "Yığın nedir?", "options": ["A", "B", "C", "D"]},
                ],
            },
            {
                "topic": "Konu B",
                "questions": [{"question": "Kuyruk nedir?", "options": ["A", "B", "C", "D"]}],
            },
        ]
    }


def _wrong(qid: str, question: str, selected: int, correct: int) -> dict:
    return {
        "qid": qid,
        "question": question,
        "options": ["Birinci", "İkinci", "Üçüncü", "Dördüncü"],
        "selected_index": selected,
        "correct_index": correct,
        "correct": False,
        "feedback": "Doğru cevap açıklaması.",
        "explanation": "Açıklama.",
        "citations": [],
    }


def _right(qid: str, question: str, index: int) -> dict:
    return {
        "qid": qid,
        "question": question,
        "options": ["Birinci", "İkinci", "Üçüncü", "Dördüncü"],
        "selected_index": index,
        "correct_index": index,
        "correct": True,
        "feedback": "Doğru!",
        "explanation": "Açıklama.",
        "citations": [],
    }


async def _seed_chapter_attempts(chapter_id: int, tenant_id: str = "local") -> int:
    """İki deneme kaydeder: Konu A 2 kez, Konu B 1 kez yanlış; bir de doğru cevap."""
    quiz_id = await _insert(
        "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
        (tenant_id, chapter_id, json.dumps(_questions_json(), ensure_ascii=False)),
    )
    first = {
        "results": [
            _wrong("0-0", "Bağlı liste nedir?", selected=1, correct=0),
            _wrong("1-0", "Kuyruk nedir?", selected=3, correct=2),
        ]
    }
    second = {
        "results": [
            _wrong("0-1", "Yığın nedir?", selected=0, correct=3),
            _right("1-0", "Kuyruk nedir?", index=2),
        ]
    }
    for feedback, created_at in ((first, "2026-01-01 10:00:00"), (second, "2026-06-01 10:00:00")):
        await _insert(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
            "feedback_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, quiz_id, "[]", 50, json.dumps(feedback, ensure_ascii=False), created_at),
        )
    return quiz_id


async def test_lists_wrong_answers(client):
    course_id, chapter_id = await _make_course(client)
    quiz_id = await _seed_chapter_attempts(chapter_id)

    resp = await client.get(f"/api/courses/{course_id}/errors")
    assert resp.status_code == 200
    entries = resp.json()
    # 3 yanlış (doğru cevaplanan soru listelenmez)
    assert len(entries) == 3
    assert {e["topic"] for e in entries} == {"Konu A", "Konu B"}
    assert all(e["quiz_id"] == quiz_id and e["chapter_id"] == chapter_id for e in entries)

    # yeniden eskiye: son deneme başta
    assert entries[0]["question_text"] == "Yığın nedir?"
    assert entries[0]["given_answer"] == "Birinci"
    assert entries[0]["correct_answer"] == "Dördüncü"

    # konu bazlı tekrar sayısı
    by_topic = {e["topic"]: e["repeat_count"] for e in entries}
    assert by_topic == {"Konu A": 2, "Konu B": 1}

    # cevap anahtarı ham hâli sızmaz
    assert all("answer_key" not in e and "answer_keys" not in e for e in entries)
    assert "answer_key" not in resp.text


async def test_only_repeated_filters_single_mistakes(client):
    course_id, chapter_id = await _make_course(client)
    await _seed_chapter_attempts(chapter_id)

    resp = await client.get(f"/api/courses/{course_id}/errors", params={"only_repeated": "true"})
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 2
    assert {e["topic"] for e in entries} == {"Konu A"}


async def test_topic_and_since_filters(client):
    course_id, chapter_id = await _make_course(client)
    await _seed_chapter_attempts(chapter_id)

    resp = await client.get(f"/api/courses/{course_id}/errors", params={"topic": "Konu B"})
    assert [e["question_text"] for e in resp.json()] == ["Kuyruk nedir?"]

    resp = await client.get(f"/api/courses/{course_id}/errors", params={"since": "2026-03-01"})
    entries = resp.json()
    assert [e["question_text"] for e in entries] == ["Yığın nedir?"]
    # pencere daraldığı için Konu A artık tek seferlik
    assert entries[0]["repeat_count"] == 1

    resp = await client.get(f"/api/courses/{course_id}/errors", params={"since": "dün"})
    assert resp.status_code == 422


async def test_other_tenant_data_is_hidden(client):
    course_id, chapter_id = await _make_course(client)
    await _seed_chapter_attempts(chapter_id)

    # Başka kiracının aynı ders altındaki chapter'ı + denemeleri
    other_chapter_id = await _insert(
        "INSERT INTO chapters (tenant_id, course_id, title) VALUES (?, ?, ?)",
        ("other-tenant", course_id, "Gizli Bölüm"),
    )
    await _seed_chapter_attempts(other_chapter_id, tenant_id="other-tenant")

    resp = await client.get(f"/api/courses/{course_id}/errors")
    entries = resp.json()
    assert len(entries) == 3
    assert all(e["chapter_id"] == chapter_id for e in entries)


async def test_overall_attempt_errors_included(client):
    course_id, _ = await _make_course(client)
    questions_json = {
        "questions": [
            {
                "type": "mcq",
                "topic": "Sıralama",
                "question": "Hangisi kararlıdır?",
                "options": ["Quick", "Merge", "Heap", "Selection"],
                "correct_index": 1,
            },
            {"type": "tf", "topic": "Grafikler", "statement": "BFS kuyruk kullanır."},
        ],
        # cevap anahtarı bloğu okunmaz, yalnızca konu adı için questions_json açılır
        "answer_keys": {"ak_1": {"points": ["sızmamalı"]}},
    }
    quiz_id = await _insert(
        "INSERT INTO overall_quizzes (tenant_id, course_id, questions_json) VALUES (?, ?, ?)",
        ("local", course_id, json.dumps(questions_json, ensure_ascii=False)),
    )
    score_json = {
        "score": 0,
        "results": [
            {
                "qid": 0,
                "type": "mcq",
                "question": "Hangisi kararlıdır?",
                "correct": False,
                "options": ["Quick", "Merge", "Heap", "Selection"],
                "correct_index": 1,
                "selected_index": 0,
            },
            {
                "qid": 1,
                "type": "tf",
                "question": "BFS kuyruk kullanır.",
                "correct": False,
                "answer": True,
                "selected_tf": 0,
            },
        ],
    }
    await _insert(
        "INSERT INTO overall_attempts (tenant_id, overall_quiz_id, answers_json, score_json, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        ("local", quiz_id, "[]", json.dumps(score_json, ensure_ascii=False), "2026-05-01 09:00:00"),
    )

    resp = await client.get(f"/api/courses/{course_id}/errors")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 2
    assert all(e["chapter_id"] is None and e["quiz_id"] == quiz_id for e in entries)
    mcq = next(e for e in entries if e["topic"] == "Sıralama")
    assert (mcq["given_answer"], mcq["correct_answer"]) == ("Quick", "Merge")
    tf = next(e for e in entries if e["topic"] == "Grafikler")
    assert (tf["given_answer"], tf["correct_answer"]) == ("Yanlış", "Doğru")
    assert "sızmamalı" not in resp.text
