"""card_summary uç testleri — ders/chapter kart hover rotation verisi (yönerge §36/§37)."""

from __future__ import annotations

import json

import pytest


async def _seed(client, chapter_title: str = "Ağaç Yapıları") -> dict:
    term = (await client.post("/api/terms", json={"name": "2026 Güz"})).json()
    course = (
        await client.post(f"/api/terms/{term['id']}/courses", json={"name": "Veri Yapıları"})
    ).json()
    chapter = (
        await client.post(f"/api/courses/{course['id']}/chapters", json={"title": chapter_title})
    ).json()
    return {"term": term, "course": course, "chapter": chapter}


@pytest.mark.asyncio
async def test_bos_ders_null_progress_ve_sifir_sure(client):
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]

    resp = await client.get(f"/api/courses/{course_id}/card-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["progress"] is None
    assert body["total_study_sec"] == 0
    assert body["next_exam"] is None
    assert body["last_activity"] is None
    assert body["total_chapters"] == 1
    chapter = body["chapters"][0]
    assert chapter["topics_total"] == 0
    assert chapter["topics_completed"] == 0


@pytest.mark.asyncio
async def test_not_topici_tamamlanma_ve_son_aktivite(client):
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]
    chapter_id = seeded["chapter"]["id"]

    # Not üret (topic'li) — test double: doğrudan DB insert yerine üretim ucunun
    # mock'lanması gerekir; burada notes ucunun var olan seed'ini kullanırız.
    # Not üretim ucu LLM istediği için doğrudan fixture üzerinden ilerlenir:
    from src.db import get_db

    db = await get_db()
    await db.execute(
        "INSERT INTO notes (tenant_id, chapter_id, content_md, topics_json) VALUES (?, ?, ?, ?)",
        (
            "local",
            chapter_id,
            "# Not",
            json.dumps([{"topic": "Binary Trees", "keywords": [], "slide_refs": []}]),
        ),
    )
    await db.commit()
    await db.close()

    resp = await client.get(f"/api/courses/{course_id}/card-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["progress"] == 0.0  # topic var ama tamamlanma sinyali yok
    chapter = body["chapters"][0]
    assert chapter["topics_total"] == 1
    assert chapter["topics_completed"] == 0
    # Son aktivite: not üretimi
    assert body["last_activity"] is not None
    assert body["last_activity"]["kind"] == "note"


@pytest.mark.asyncio
async def test_yaklasan_sinav_donuyor(client):
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": "2099-12-01", "scope_json": []},
    )
    assert resp.status_code == 201, resp.text

    body = (await client.get(f"/api/courses/{course_id}/card-summary")).json()
    assert body["next_exam"] is not None
    assert body["next_exam"]["title"] == "Vize"
    assert body["next_exam"]["days_left"] > 0


@pytest.mark.asyncio
async def test_dogru_quiz_cevabi_topic_tamamlar(client):
    """Doğru chapter-quiz cevabı topic'i tamamlar (yönerge §4 tamamlanma sinyali).

    Quiz üretimi LLM istediği için quiz + deneme satırları, gerçek `POST
    /quizzes/{id}/attempts` router'ının yazdığı şemayla birebir aynı şekilde
    doğrudan eklenir (chapter_quizzes.submit_chapter_quiz INSERT'i ile aynı)."""
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]
    chapter_id = seeded["chapter"]["id"]

    from src.db import get_db

    questions_payload = json.dumps(
        {
            "topics": [
                {
                    "topic": "Binary Trees",
                    "questions": [
                        {
                            "qid": "0-0",
                            "question": "2-3 ağacı nedir?",
                            "options": ["A", "B", "C", "D"],
                            "correct_index": 1,
                            "explanation": "",
                            "citations": [],
                        }
                    ],
                }
            ]
        }
    )
    feedback = json.dumps(
        {
            "results": [
                {
                    "qid": "0-0",
                    "question": "2-3 ağacı nedir?",
                    "selected_index": 1,
                    "correct_index": 1,
                    "correct": True,
                    "topic": "Binary Trees",
                }
            ]
        }
    )
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
        ("local", chapter_id, questions_payload),
    )
    quiz_id = cursor.lastrowid
    await db.execute(
        "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, feedback_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("local", quiz_id, json.dumps([{"qid": "0-0", "selected_index": 1}]), 100.0, feedback),
    )
    await db.commit()
    await db.close()

    body = (await client.get(f"/api/courses/{course_id}/card-summary")).json()
    chapter = body["chapters"][0]
    assert chapter["topics_total"] == 1
    assert chapter["topics_completed"] == 1
    assert body["progress"] == 1.0
    assert body["last_activity"] is not None
    assert body["last_activity"]["kind"] == "quiz"


@pytest.mark.asyncio
async def test_ders_bulunamadi_404(client):
    resp = await client.get("/api/courses/999999/card-summary")
    assert resp.status_code == 404
