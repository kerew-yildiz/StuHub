"""Hata-odaklı kurtarma quizi testleri (Plan #6) — LLM mock'lu.

Gerçek LLM çağrısı YOK: üretim yolu `quiz_generator._generate_feed_topic`'in
çağırdığı `llm_service.chat_json` düzeyinde mock'lanır (mevcut test kalıbı,
bkz. test_quiz_generator.py / test_feed.py).
"""

from __future__ import annotations

import json

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import quiz_review as quiz_review_router
from src.services import llm_service

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(getattr(r, "path", "") == "/api/courses/{course_id}/errors/quiz" for r in app.routes):
    app.include_router(quiz_review_router.router)

TOPIC_A = "Konu A"
TOPIC_B = "Konu B"

CITATION = {
    "id": 1,
    "source_type": "textbook",
    "source_id": 9,
    "page": 1,
    "slide": None,
    "chunk_id": "chk_9_1_1",
    "quote": "Kaynak metni.",
}


def _envelope(topic: str) -> dict:
    return {
        "topic": topic,
        "questions": [
            {
                "topic": topic,
                "question": f"{topic} için yeni soru {i}",
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


def _mock_chat_json(monkeypatch, responses=None):
    calls: dict = {"count": 0, "prompts": []}

    async def fake(messages, **kwargs):
        calls["count"] += 1
        calls["prompts"].append(messages[0]["content"])
        if responses is None:
            # Prompt'taki başlıktan konuyu çıkarıp o konu için zarf üretir.
            content = messages[0]["content"]
            topic = TOPIC_A if TOPIC_A in content else TOPIC_B
            return _envelope(topic)
        if callable(responses):
            return responses(calls["count"])
        return responses[min(calls["count"] - 1, len(responses) - 1)]

    monkeypatch.setattr(llm_service, "chat_json", fake)
    return calls


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _make_chapter_with_note(client, course_id: int, title: str, topics: list[str]) -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": title})
    chapter_id = resp.json()["id"]

    content_md = "\n\n".join(f"### {t}\n\nİçerik metni [1]." for t in topics)
    citations_blob = json.dumps(
        {"topics": [{"topic": t, "citations": [CITATION]} for t in topics]}, ensure_ascii=False
    )
    topics_blob = json.dumps(
        [{"topic": t, "keywords": [], "slide_refs": []} for t in topics], ensure_ascii=False
    )
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (chapter_id, content_md, citations_blob, topics_blob, "gemini-2.5-flash"),
        )
        await conn.commit()
    return chapter_id


def _wrong(qid: str, question: str) -> dict:
    return {
        "qid": qid,
        "question": question,
        "options": ["Birinci", "İkinci", "Üçüncü", "Dördüncü"],
        "selected_index": 1,
        "correct_index": 0,
        "correct": False,
        "feedback": "Doğru cevap açıklaması.",
        "explanation": "Açıklama.",
        "citations": [],
    }


async def _seed_wrong_attempts(chapter_id: int, tenant_id: str = "local") -> None:
    """Konu A'da 2 yanlış (tekrarlı), Konu B'de 1 yanlış cevap kaydeder."""
    questions_json = {
        "topics": [
            {
                "topic": TOPIC_A,
                "questions": [
                    {"question": "Konu A eski soru 1?", "options": ["A", "B", "C", "D"]},
                    {"question": "Konu A eski soru 2?", "options": ["A", "B", "C", "D"]},
                ],
            },
            {
                "topic": TOPIC_B,
                "questions": [{"question": "Konu B eski soru?", "options": ["A", "B", "C", "D"]}],
            },
        ]
    }
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await conn.commit()
        quiz_id = cursor.lastrowid

        feedback = {
            "results": [
                _wrong("0-0", "Konu A eski soru 1?"),
                _wrong("1-0", "Konu B eski soru?"),
            ]
        }
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
            "feedback_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, quiz_id, "[]", 50, json.dumps(feedback, ensure_ascii=False),
             "2026-01-01 10:00:00"),
        )
        feedback2 = {"results": [_wrong("0-1", "Konu A eski soru 2?")]}
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
            "feedback_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, quiz_id, "[]", 50, json.dumps(feedback2, ensure_ascii=False),
             "2026-06-01 10:00:00"),
        )
        await conn.commit()


async def test_konu_belirtilmezse_hata_gunlugunden_cikarilir(client, monkeypatch):
    """`topics` boş → hata günlüğündeki en sık konu (Konu A, 2 tekrar) otomatik seçilir."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter_with_note(client, course_id, "Bölüm 1", [TOPIC_A, TOPIC_B])
    await _seed_wrong_attempts(chapter_id)
    _mock_chat_json(monkeypatch)

    resp = await client.post(f"/api/courses/{course_id}/errors/quiz", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["topics"][0] == TOPIC_A  # en çok tekrar eden konu (2x) önce
    assert len(body["questions"]) > 0
    assert any(q["topic"] == TOPIC_A for q in body["questions"])


async def test_negatif_liste_eski_sorulari_yasaklar(client, monkeypatch):
    """Hata günlüğündeki eski soru metinleri prompt'a negatif liste olarak girer."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter_with_note(client, course_id, "Bölüm 1", [TOPIC_A, TOPIC_B])
    await _seed_wrong_attempts(chapter_id)
    calls = _mock_chat_json(monkeypatch)

    resp = await client.post(
        f"/api/courses/{course_id}/errors/quiz", json={"topics": [TOPIC_A]}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Üretilen sorular eski (hata günlüğündeki) soru metinleriyle AYNI değil.
    generated_texts = {q["question"] for q in body["questions"]}
    assert "Konu A eski soru 1?" not in generated_texts
    assert "Konu A eski soru 2?" not in generated_texts
    # Negatif liste gerçekten prompt'a girmiş.
    assert any("Konu A eski soru 1?" in prompt for prompt in calls["prompts"])


async def test_tenant_izolasyonu(client, monkeypatch):
    """Başka kiracının hata günlüğü/notu yerel kiracının kurtarma quizine sızmaz."""
    course_id = await _make_course(client)
    await _make_chapter_with_note(client, course_id, "Bölüm 1", [TOPIC_A])
    _mock_chat_json(monkeypatch)

    # Başka kiracıya ait, aynı ders altında ayrı bir bölüm + yanlış cevap kaydı.
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES (?, ?, ?)",
            ("other-tenant", course_id, "Gizli Bölüm"),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        other_chapter_id = cursor.lastrowid
    await _seed_wrong_attempts(other_chapter_id, tenant_id="other-tenant")

    resp = await client.post(f"/api/courses/{course_id}/errors/quiz", json={})
    assert resp.status_code == 200
    body = resp.json()
    # Yerel kiracının hata günlüğü boş olduğu için otomatik konu bulunamaz.
    assert body["topics"] == []
    assert body["questions"] == []


async def test_belirtilen_konu_yoksa_bos_doner(client, monkeypatch):
    """Hiçbir bölüm notunda eşleşmeyen konu için sessizce boş liste döner (hata fırlatmaz)."""
    course_id = await _make_course(client)
    await _make_chapter_with_note(client, course_id, "Bölüm 1", [TOPIC_A])
    _mock_chat_json(monkeypatch)

    resp = await client.post(
        f"/api/courses/{course_id}/errors/quiz", json={"topics": ["Var Olmayan Konu"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["topics"] == ["Var Olmayan Konu"]
    assert body["questions"] == []
