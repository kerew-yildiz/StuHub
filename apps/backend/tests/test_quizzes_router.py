"""Quiz router testleri — SSE üretim, okuma, anında feedback'li deneme (Faz 4.2)."""

import json

from src.routers import quizzes as quizzes_router


async def _make_chapter(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Konu A"})
    return resp.json()["id"]


def _questions_json():
    return {
        "topics": [
            {
                "topic": "Konu A",
                "questions": [
                    {
                        "topic": "Konu A",
                        "question": "Bağlı listeler nedir?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 0,
                        "explanation": "Açıklama.",
                        "feedback_correct": "Doğru! Pekiştirme.",
                        "feedback_wrong": "Doğru cevap: A. Açıklama...",
                        "citations": [{"id": 1, "chunk_id": "chk_9_1_1", "quote": "kaynak"}],
                    },
                    {
                        "topic": "Konu A",
                        "question": "Sıralama yöntemi?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 2,
                        "explanation": "Açıklama 2.",
                        "feedback_correct": "Doğru!",
                        "feedback_wrong": "Doğru cevap: C.",
                        "citations": [{"id": 1, "chunk_id": "chk_9_1_1", "quote": "kaynak"}],
                    },
                ],
            }
        ]
    }


async def _insert_quiz(client, chapter_id: int) -> int:
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (chapter_id, questions_json) VALUES (?, ?)",
            (chapter_id, json.dumps(_questions_json(), ensure_ascii=False)),
        )
        await conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("quiz kimliği alınamadı")
        return row_id


async def test_quiz_sse_endpoint(client, monkeypatch):
    chapter_id = await _make_chapter(client)

    async def fake_generator(chapter_id, tenant_id):
        yield {"type": "status", "percent": 10, "message": "Soru üretiliyor…"}
        yield {
            "type": "done",
            "quiz": {"id": 1, "chapter_id": chapter_id, "questions_json": _questions_json()},
        }

    monkeypatch.setattr(quizzes_router, "generate_quiz_stream", fake_generator)
    resp = await client.post(f"/api/chapters/{chapter_id}/quiz")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "Soru üretiliyor" in resp.text
    assert '"type": "done"' in resp.text


async def test_get_latest_quiz(client):
    chapter_id = await _make_chapter(client)
    quiz_id = await _insert_quiz(client, chapter_id)
    resp = await client.get(f"/api/chapters/{chapter_id}/quiz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == quiz_id
    assert len(body["questions_json"]["topics"][0]["questions"]) == 2

    other = await _make_chapter(client)
    resp = await client.get(f"/api/chapters/{other}/quiz")
    assert resp.json() is None


async def test_submit_attempt_feedback(client):
    chapter_id = await _make_chapter(client)
    quiz_id = await _insert_quiz(client, chapter_id)

    resp = await client.post(
        f"/api/quizzes/{quiz_id}/attempts",
        json={
            "answers": [
                {"qid": "0-0", "selected_index": 0},
                {"qid": "0-1", "selected_index": 3},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 50
    assert body["correct_count"] == 1
    assert body["total"] == 2

    first = body["results"][0]
    assert first["correct"] is True
    assert first["feedback"] == "Doğru! Pekiştirme."
    second = body["results"][1]
    assert second["correct"] is False
    assert second["feedback"] == "Doğru cevap: C."
    assert second["citations"][0]["chunk_id"] == "chk_9_1_1"

    # deneme kaydedildi
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT score, feedback_json FROM quiz_attempts WHERE quiz_id = ?", (quiz_id,)
        )
        row = await cursor.fetchone()
    assert row is not None and row[0] == 50
    assert "results" in json.loads(row[1])


async def test_submit_attempt_unknown_question(client):
    chapter_id = await _make_chapter(client)
    quiz_id = await _insert_quiz(client, chapter_id)
    resp = await client.post(
        f"/api/quizzes/{quiz_id}/attempts",
        json={"answers": [{"qid": "9-9", "selected_index": 0}]},
    )
    assert resp.status_code == 422
