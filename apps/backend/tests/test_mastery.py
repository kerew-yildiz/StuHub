"""Ustalık ilerlemesi testleri (Plan: kaydırmalı quiz #7) — 5-doğru tavanı, dedupe,
konu etiketi normalizasyonu, not yokken sıfıra bölme.

Gerçek LLM çağrısı YOK — mastery hesaplaması `quiz_attempts` + `notes.topics_json`
üzerinde saf SQL/Python'dur, üretim yolunu hiç kullanmaz.
"""

import json

import aiosqlite
import pytest

from src.config import settings
from src.main import app
from src.routers import feed as feed_router
from src.services import feed_service

if not any(getattr(r, "path", "") == "/api/chapters/{chapter_id}/mastery" for r in app.routes):
    app.include_router(feed_router.router)


@pytest.fixture(autouse=True)
def _clear_filling():
    feed_service._filling.clear()
    yield
    feed_service._filling.clear()


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _make_chapter(client, course_id: int, title: str = "Konu A") -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": title})
    return resp.json()["id"]


async def _insert_note(chapter_id: int, topics: list[str], tenant_id: str = "local") -> None:
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES (?, ?, '# not', '{}', ?)",
            (
                tenant_id,
                chapter_id,
                json.dumps([{"topic": t} for t in topics], ensure_ascii=False),
            ),
        )
        await conn.commit()


async def _insert_quiz(
    chapter_id: int, topic: str, question_count: int, tenant_id: str = "local"
) -> int:
    questions_json = {
        "topics": [
            {
                "topic": topic,
                "questions": [
                    {
                        "topic": topic,
                        "question": f"{topic} soru {i}",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 0,
                    }
                    for i in range(question_count)
                ],
            }
        ]
    }
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await conn.commit()
        quiz_id = cursor.lastrowid
        assert quiz_id is not None
        return quiz_id


async def _insert_attempt(
    quiz_id: int, results: list[dict], tenant_id: str = "local"
) -> None:
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
            "feedback_json) VALUES (?, ?, '[]', 0, ?)",
            (tenant_id, quiz_id, json.dumps({"results": results}, ensure_ascii=False)),
        )
        await conn.commit()


def _result(qid: str, correct: bool) -> dict:
    return {"qid": qid, "correct": correct}


async def test_not_yokken_yuzde_sifir_ve_bolme_hatasi_yok(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)

    resp = await client.get(f"/api/chapters/{chapter_id}/mastery")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"percent": 0.0, "correct": 0, "total": 0, "topics": []}


async def test_konu_basina_5_dogru_tavani(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _insert_note(chapter_id, ["Bağlı Listeler"])
    quiz_id = await _insert_quiz(chapter_id, "Bağlı Listeler", 8)

    # 8 farklı soru doğru cevaplanmış — 5'te tavanlanmalı
    results = [_result(f"0-{i}", True) for i in range(8)]
    await _insert_attempt(quiz_id, results)

    resp = await client.get(f"/api/chapters/{chapter_id}/mastery")
    data = resp.json()
    assert data["total"] == 5
    assert data["correct"] == 5
    assert data["percent"] == 100.0
    assert data["topics"] == [{"topic": "Bağlı Listeler", "correct": 5, "target": 5}]


async def test_ayni_soru_iki_kez_cevaplanirsa_dedupe_son_deneme_kazanir(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _insert_note(chapter_id, ["Bağlı Listeler"])
    quiz_id = await _insert_quiz(chapter_id, "Bağlı Listeler", 2)

    # İlk denemede yanlış, ikinci denemede (yeniden çözüldü) doğru — sadece 1 defa sayılmalı
    await _insert_attempt(quiz_id, [_result("0-0", False)])
    await _insert_attempt(quiz_id, [_result("0-0", True)])

    resp = await client.get(f"/api/chapters/{chapter_id}/mastery")
    data = resp.json()
    assert data["correct"] == 1  # 2 kez sayılmadı
    assert data["topics"][0]["correct"] == 1


async def test_konu_etiketi_fuzzy_eslesir(client):
    """Quiz'in ürettiği konu etiketi notun konu adından ufak sapmışsa (LLM varyasyonu)
    yine de ham `==` değil `topic_matches` ile eşleşmeli."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _insert_note(chapter_id, ["Bağlı Listeler"])
    quiz_id = await _insert_quiz(chapter_id, "bağlı listeler!", 1)  # noktalama + case farklı
    await _insert_attempt(quiz_id, [_result("0-0", True)])

    resp = await client.get(f"/api/chapters/{chapter_id}/mastery")
    data = resp.json()
    assert data["topics"][0]["correct"] == 1


async def test_course_mastery_tum_bolumlerin_toplami(client):
    course_id = await _make_course(client)
    chapter_a = await _make_chapter(client, course_id, "Konu A")
    chapter_b = await _make_chapter(client, course_id, "Konu B")
    await _insert_note(chapter_a, ["Konu A1"])
    await _insert_note(chapter_b, ["Konu B1", "Konu B2"])
    quiz_a = await _insert_quiz(chapter_a, "Konu A1", 5)
    quiz_b = await _insert_quiz(chapter_b, "Konu B1", 3)
    await _insert_attempt(quiz_a, [_result(f"0-{i}", True) for i in range(5)])
    await _insert_attempt(quiz_b, [_result(f"0-{i}", True) for i in range(3)])

    resp = await client.get(f"/api/courses/{course_id}/mastery")
    data = resp.json()
    # Konu A1: 5/5, Konu B1: 3/5, Konu B2: 0/5 → toplam 8/15
    assert data["total"] == 15
    assert data["correct"] == 8
    assert round(data["percent"], 2) == round(100 * 8 / 15, 2)
    assert len(data["topics"]) == 3


async def test_chapter_mastery_bulunamayan_bolum_404(client):
    resp = await client.get("/api/chapters/99999/mastery")
    assert resp.status_code == 404


async def test_course_mastery_bulunamayan_ders_404(client):
    resp = await client.get("/api/courses/99999/mastery")
    assert resp.status_code == 404
