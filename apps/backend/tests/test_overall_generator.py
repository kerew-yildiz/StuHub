"""Genel quiz üretim testleri (Faz 5.1) — LLM mock'lu."""

import json

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

    import aiosqlite

    from src.config import settings

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
                "deepseek-chat",
            ),
        )
        await conn.commit()
    return course_id


def _question(category: str, index: int) -> dict:
    base = {
        "type": category,
        "topic": "Konu A",
        "citations": [{"id": 1}],
    }
    if category == "mcq":
        return {
            **base,
            "question": f"Soru {index}",
            "options": ["A", "B", "C", "D"],
            "correct_index": index % 4,
            "explanation": "e",
            "feedback_correct": "Doğru!",
            "feedback_wrong": "Yanlış.",
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
            "feedback_wrong": "Yanlış.",
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
            category, count = "tf", 15 if "TAM 15" in prompt else 8
            # zarf boyutu: plan 8+7; mock TAM count kadar üretir
            count = 8 if "TAM 8" in prompt else 7
        elif '"fib" türünde' in prompt:
            category, count = "fib", 5
        else:
            category, count = "open", 5
        return {"category": category, "questions": [_question(category, i) for i in range(count)]}

    monkeypatch.setattr(llm_service, "chat_json", fake)


async def _collect(agen) -> list[dict]:
    return [e async for e in agen]


async def test_overall_generation_full_flow(client, monkeypatch):
    course_id = await _make_course_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    _mock_chat_json(monkeypatch)

    events = await _collect(overall_generator.generate_overall_quiz_stream(course_id))
    assert events[-1]["type"] == "done"
    quiz = events[-1]["quiz"]
    questions = quiz["questions"]
    assert len(questions) == 55
    counts = {
        cat: sum(1 for q in questions if q["type"] == cat) for cat in ("mcq", "tf", "fib", "open")
    }
    assert counts == {"mcq": 20, "tf": 15, "fib": 15, "open": 5}
    # atıflar çözümlenmiş
    mcq = next(q for q in questions if q["type"] == "mcq")
    assert mcq["citations"][0]["chunk_id"] == "chk_9_1_1"
    # açık uçlu: answer_key yalnızca ref olarak
    open_q = next(q for q in questions if q["type"] == "open")
    assert "answer_key" not in open_q
    assert "answer_key_ref" in open_q
    # seed var
    assert quiz["seed"] > 0
    # TF dengesi 7-8 doğru
    tf_true = sum(1 for q in questions if q["type"] == "tf" and q["answer"])
    assert 7 <= tf_true <= 8

    # overall_quizzes kaydı (answer_keys dahili saklı)
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT questions_json FROM overall_quizzes WHERE course_id = ?", (course_id,)
        )
        row = await cursor.fetchone()
    assert row is not None
    stored = json.loads(row[0])
    assert "answer_keys" in stored
    assert len(stored["answer_keys"]) == 5


async def test_overall_generation_requires_notes(client, monkeypatch):
    resp = await client.post("/api/terms", json={"name": "T"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Ders"})
    course_id = resp.json()["id"]
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")

    events = await _collect(overall_generator.generate_overall_quiz_stream(course_id))
    assert events[-1]["type"] == "error"
    assert "not" in events[-1]["message"].lower()


async def test_overall_generation_tf_rebalance(client, monkeypatch):
    course_id = await _make_course_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")

    async def fake(messages, **kwargs):
        prompt = messages[0]["content"]
        if '"mcq" türünde' in prompt:
            return {"category": "mcq", "questions": [_question("mcq", i) for i in range(5)]}
        if '"tf" türünde' in prompt:
            if "TAM 15" in prompt:
                # yeniden üretim: dengeli (8 doğru)
                return {"category": "tf", "questions": [_question("tf", i) for i in range(15)]}
            # ilk tur: iki batch de tümü 'doğru' → toplam 15 doğru → dengesiz
            count = 8 if "TAM 8" in prompt else 7
            questions = [_question("tf", i) for i in range(count)]
            for q in questions:
                q["answer"] = True
            return {"category": "tf", "questions": questions}
        if '"fib" türünde' in prompt:
            return {"category": "fib", "questions": [_question("fib", i) for i in range(5)]}
        return {"category": "open", "questions": [_question("open", i) for i in range(5)]}

    monkeypatch.setattr(llm_service, "chat_json", fake)
    events = await _collect(overall_generator.generate_overall_quiz_stream(course_id))
    assert events[-1]["type"] == "done"
    tf = [q for q in events[-1]["quiz"]["questions"] if q["type"] == "tf"]
    assert 7 <= sum(1 for q in tf if q["answer"]) <= 8
