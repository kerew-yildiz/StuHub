"""Bölüm quizi üretim testleri (Faz 4.1) — LLM mock'lu."""

import json

from src.services import llm_service, quiz_generator

TOPIC = "Konu A"
CITATION = {
    "id": 1,
    "source_type": "textbook",
    "source_id": 9,
    "page": 1,
    "slide": None,
    "chunk_id": "chk_9_1_1",
    "quote": "Kaynak metni.",
}


def _envelope(topic=TOPIC):
    return {
        "topic": topic,
        "questions": [
            {
                "topic": topic,
                "question": f"{topic} sorusu {i}",
                "options": ["Seçenek A", "Seçenek B", "Seçenek C", "Seçenek D"],
                "correct_index": i % 4,
                "explanation": "Açıklama metni.",
                "feedback_correct": "Doğru! Pekiştirme cümlesi.",
                "feedback_wrong": "Doğru cevap: X. Açıklama: ... [kaynak: [1] sayfa 1]",
                "citations": [{"id": 1}],
            }
            for i in range(5)
        ],
    }


async def _make_chapter_with_note(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": TOPIC})
    chapter_id = resp.json()["id"]

    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        citations_blob = json.dumps(
            {"topics": [{"topic": TOPIC, "citations": [CITATION]}]}, ensure_ascii=False
        )
        topics_blob = json.dumps(
            [{"topic": TOPIC, "keywords": [], "slide_refs": []}], ensure_ascii=False
        )
        await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                chapter_id,
                f"### {TOPIC}\n\nİçerik metni [1].",
                citations_blob,
                topics_blob,
                "deepseek-chat",
            ),
        )
        await conn.commit()
    return chapter_id


def _mock_chat_json(monkeypatch, responses):
    calls = {"count": 0}

    async def fake(messages, **kwargs):
        calls["count"] += 1
        if callable(responses):
            return responses(calls["count"])
        return responses[min(calls["count"] - 1, len(responses) - 1)]

    monkeypatch.setattr(llm_service, "chat_json", fake)
    return calls


async def _collect(agen) -> list[dict]:
    return [e async for e in agen]


async def test_quiz_generation_happy_path(client, monkeypatch):
    chapter_id = await _make_chapter_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    _mock_chat_json(monkeypatch, [_envelope()])

    events = await _collect(quiz_generator.generate_quiz_stream(chapter_id))
    assert events[-1]["type"] == "done"
    quiz = events[-1]["quiz"]
    topics = quiz["questions_json"]["topics"]
    assert len(topics) == 1
    assert len(topics[0]["questions"]) == 5
    # atıflar zenginleştirildi (chunk_id, quote)
    first = topics[0]["questions"][0]
    assert first["citations"][0]["chunk_id"] == "chk_9_1_1"
    assert first["citations"][0]["quote"] == "Kaynak metni."
    # correct_index dengesi: hiçbir şık 2'den fazla doğru değil
    counts = [q["correct_index"] for q in topics[0]["questions"]]
    assert max(counts.count(i) for i in range(4)) <= 2

    # quizzes tablosuna kaydedildi
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM quizzes WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
    count = row[0] if row is not None else 0
    assert count == 1


async def test_quiz_requires_note(client, monkeypatch):
    resp = await client.post("/api/terms", json={"name": "T"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Ders"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": TOPIC})
    chapter_id = resp.json()["id"]
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")

    events = await _collect(quiz_generator.generate_quiz_stream(chapter_id))
    assert events[-1]["type"] == "error"
    assert "Önce not oluştur" in events[-1]["message"]


async def test_quiz_invalid_batch_skipped_with_warning(client, monkeypatch):
    """Üretilemeyen konu asla hataya düşmez — uyarıyla atlanır, quiz teslim edilir."""
    chapter_id = await _make_chapter_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    # her seferinde geçersiz (3 sorulu) zarf
    bad = _envelope()
    bad["questions"] = bad["questions"][:3]
    # 3 sorulu zarf yumuşak geçişte kabul edilir (>=3); tamamen boş döndürmek için 2 soru
    bad["questions"] = bad["questions"][:2]
    _mock_chat_json(monkeypatch, [bad] * 5)

    events = await _collect(quiz_generator.generate_quiz_stream(chapter_id))
    assert events[-1]["type"] == "done"  # hata değil, done!
    assert events[-1].get("warnings")  # uyarı listesi dolu
    # quiz kaydedildi (konu atlandı)
    assert events[-1]["quiz"]["questions_json"]["topics"] == []


async def test_quiz_unattributed_question_self_heals(client, monkeypatch):
    """Atıfsız soru: katı denetim geçemezse atıf bölümün ilk kaynağıyla onarılır."""
    chapter_id = await _make_chapter_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    bad = _envelope()
    bad["questions"][0]["citations"] = []
    _mock_chat_json(monkeypatch, [bad])

    events = await _collect(quiz_generator.generate_quiz_stream(chapter_id))
    assert events[-1]["type"] == "done"
    questions = events[-1]["quiz"]["questions_json"]["topics"][0]["questions"]
    # tüm soruların geçerli atfı var (self-heal)
    assert all(q["citations"] for q in questions)
    assert questions[0]["citations"][0]["chunk_id"] == "chk_9_1_1"


async def test_quiz_unbalanced_is_rebalanced(client, monkeypatch):
    chapter_id = await _make_chapter_with_note(client)
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    # 5 soru da 0. şıkta doğru — yeniden dengeleme devreye girmeli
    bad = _envelope()
    for q in bad["questions"]:
        q["correct_index"] = 0
    _mock_chat_json(monkeypatch, [bad])

    events = await _collect(quiz_generator.generate_quiz_stream(chapter_id))
    assert events[-1]["type"] == "done"
    questions = events[-1]["quiz"]["questions_json"]["topics"][0]["questions"]
    counts = [q["correct_index"] for q in questions]
    assert max(counts.count(i) for i in range(4)) <= 2
    # seçenekler yine 4 elemanlı ve anlamlı
    assert all(len(q["options"]) == 4 for q in questions)
