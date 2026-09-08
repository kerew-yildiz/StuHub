"""Sınav simülasyonu testleri (Plan #35) — LLM mock'lu.

Kritik iddia: sınav modunda `correct_index`/`answer`/`accepted_answers`/`feedback_*`/
`explanation` sonuca kadar hiçbir yanıtta (SSE `done` olayı dahil) sızmaz.
"""

import json

import aiosqlite

from src.config import settings
from src.services import llm_service, overall_generator

CITATION = {
    "id": 1,
    "source_type": "textbook",
    "source_id": 9,
    "page": 1,
    "slide": None,
    "chunk_id": "chk_9_1_1",
    "quote": "Kaynak metni.",
}


async def _make_course_with_note(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Konu A"})
    chapter_id = resp.json()["id"]

    async with aiosqlite.connect(settings.db_path) as conn:
        citations_blob = json.dumps(
            {"topics": [{"topic": "Konu A", "citations": [CITATION]}]}, ensure_ascii=False
        )
        topics_blob = json.dumps(
            [{"topic": "Konu A", "keywords": [], "slide_refs": []}], ensure_ascii=False
        )
        await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                chapter_id,
                "### Konu A\n\nİçerik [1].",
                citations_blob,
                topics_blob,
                "gemini-2.5-flash",
            ),
        )
        await conn.commit()
    return course_id


def _question(category: str, index: int) -> dict:
    base = {"type": category, "topic": "Konu A", "citations": [{"id": 1}]}
    if category == "mcq":
        return {
            **base,
            "question": f"Soru {index}",
            "options": ["A", "B", "C", "D"],
            "correct_index": index % 4,
            "explanation": "e",
            "feedback_correct": "Doğru!",
            "feedback_wrong": "Yanlış. Doğru cevap A.",
        }
    if category == "tf":
        return {
            **base,
            "statement": f"İfade {index}",
            "answer": index % 2 == 0,
            "explanation": "e",
            "feedback_correct": "Doğru!",
            "feedback_wrong": "Yanlış.",
        }
    if category == "fib":
        return {
            **base,
            "text": f"Metin ____ {index}",
            "accepted_answers": ["cevap"],
            "explanation": "e",
            "feedback_correct": "Doğru!",
            "feedback_wrong": "Yanlış. Doğru cevap: cevap.",
        }
    return {
        "type": category,
        "topic": "Konu A",
        "question": f"Açık soru {index}",
        "answer_key": {"points": ["nokta"], "citations": [{"id": 1}]},
    }


def _mock_chat_json(monkeypatch):
    async def fake(messages, **kwargs):
        prompt = messages[0]["content"]
        if '"mcq" türünde' in prompt:
            category, count = "mcq", 5
        elif '"tf" türünde' in prompt:
            category = "tf"
            count = 8 if "TAM 8" in prompt else 7
        elif '"fib" türünde' in prompt:
            category, count = "fib", 5
        else:
            category, count = "open", 5
        return {"category": category, "questions": [_question(category, i) for i in range(count)]}

    monkeypatch.setattr(llm_service, "chat_json", fake)


async def _collect(agen) -> list[dict]:
    return [e async for e in agen]


async def _create_exam(client, course_id: int) -> int:
    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Final", "exam_date": "2099-01-01"},
    )
    return resp.json()["id"]


REVEAL_FIELDS = {
    "correct_index",
    "answer",
    "accepted_answers",
    "feedback_correct",
    "feedback_wrong",
    "explanation",
}


def test_strip_exam_answers_removes_reveal_fields():
    """Saf fonksiyon: sınav modu süzgeci mcq/tf/fib'in cevabını açığa çıkaran her alanı atar."""
    questions = [_question("mcq", 0), _question("tf", 1), _question("fib", 2)]
    stripped = overall_generator.strip_exam_answers(questions)
    for question in stripped:
        assert not (REVEAL_FIELDS & question.keys())
    # tip/soru metni gibi zararsız alanlar korunur
    assert stripped[0]["question"] == "Soru 0"
    assert stripped[0]["options"] == ["A", "B", "C", "D"]


async def test_simulate_exam_full_flow_hides_answers(client, monkeypatch):
    """Uçtan uca: SSE `done` olayındaki hiçbir soru cevabı açığa çıkarmaz; kayıt mode='exam'."""
    course_id = await _make_course_with_note(client)
    exam_id = await _create_exam(client, course_id)
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _mock_chat_json(monkeypatch)

    resp = await client.post(f"/api/courses/{course_id}/exams/{exam_id}/simulate")
    assert resp.status_code == 200
    events = [
        json.loads(line[6:])
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]
    done = next(e for e in events if e["type"] == "done")
    quiz = done["quiz"]
    assert quiz["mode"] == "exam"
    assert quiz["exam_id"] == exam_id
    questions = quiz["questions"]
    assert len(questions) == 55
    for question in questions:
        assert not (REVEAL_FIELDS & question.keys()), question
    # open sorularda answer_key_ref kalır ama gerçek anahtar asla frontend'e gitmez
    open_q = next(q for q in questions if q["type"] == "open")
    assert "answer_key" not in open_q
    assert "answer_key_ref" in open_q

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT mode, exam_id, questions_json FROM overall_quizzes WHERE course_id = ?",
            (course_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "exam"
    assert row[1] == exam_id
    # DB'deki tam kayıt (puanlama için) hâlâ correct_index/answer/accepted_answers içerir
    stored_questions = json.loads(row[2])["questions"]
    stored_mcq = next(q for q in stored_questions if q["type"] == "mcq")
    assert "correct_index" in stored_mcq

    # GET /courses/{id}/overall-quiz da aynı şekilde süzülür (sayfa yenilense bile sızmaz)
    get_resp = await client.get(f"/api/courses/{course_id}/overall-quiz")
    fetched_questions = get_resp.json()["questions_json"]["questions"]
    for question in fetched_questions:
        assert not (REVEAL_FIELDS & question.keys())


async def test_practice_mode_still_exposes_closed_answers(client, monkeypatch):
    """Regresyon: pratik mod (mode='exam' değilken) davranışı değişmedi — anında feedback için
    correct_index/answer/accepted_answers hâlâ istemciye gider."""
    course_id = await _make_course_with_note(client)
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _mock_chat_json(monkeypatch)

    events = await _collect(overall_generator.generate_overall_quiz_stream(course_id, "local"))
    quiz = events[-1]["quiz"]
    assert quiz["mode"] == "practice"
    mcq = next(q for q in quiz["questions"] if q["type"] == "mcq")
    assert "correct_index" in mcq


async def test_simulate_exam_requires_matching_course(client, monkeypatch):
    """Sınav başka bir derse aitse simulate 404 döner."""
    course_id = await _make_course_with_note(client)
    other_id = await _create_exam(client, course_id)

    resp = await client.post("/api/terms", json={"name": "T2"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Başka Ders"})
    other_course_id = resp.json()["id"]

    resp = await client.post(f"/api/courses/{other_course_id}/exams/{other_id}/simulate")
    assert resp.status_code == 404


async def test_other_tenant_cannot_simulate_exam(client):
    """Yabancı kiracının sınavı bu tenant'ın course_id'siyle simüle edilemez."""
    course_id = await _make_course_with_note(client)

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO exams (tenant_id, course_id, title, exam_date, scope_json) "
            "VALUES (?, ?, ?, ?, ?)",
            ("other-tenant", course_id, "Gizli Sınav", "2099-01-01", "[]"),
        )
        await conn.commit()
        foreign_exam_id = cursor.lastrowid

    resp = await client.post(f"/api/courses/{course_id}/exams/{foreign_exam_id}/simulate")
    assert resp.status_code == 404
