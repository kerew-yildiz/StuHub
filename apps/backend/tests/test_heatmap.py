"""Zayıf konu ısı haritası testleri (Plan #18).

Router `src/routers/__init__.py`'ye ana entegrasyonda bağlanır; testler kendi minimal
ASGI uygulamasını kurar ki kayıt sırasından bağımsız çalışsın.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI

from src.config import settings
from src.db import init_db
from src.routers import heatmap as heatmap_router


@pytest.fixture
async def heatmap_client(tmp_path, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    app = FastAPI()
    app.include_router(heatmap_router.router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _questions_json(topic: str, count: int) -> str:
    """`count` adet soruyu tek konu altında toplar; doğru şık her zaman 0."""
    return json.dumps(
        {
            "topics": [
                {
                    "topic": topic,
                    "questions": [
                        {
                            "question": f"{topic} sorusu {i}",
                            "options": ["a", "b", "c", "d"],
                            "correct_index": 0,
                            "explanation": "",
                            "feedback_correct": "",
                            "feedback_wrong": "",
                        }
                        for i in range(count)
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )


async def _seed(tenant_id: str = "local") -> int:
    """Bir ders + iki konuya ait quiz/kart/chat verisi kurar; course_id döner."""
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO terms (tenant_id, name) VALUES (?, ?)", (tenant_id, "2026 Bahar")
        )
        assert cursor.lastrowid is not None
        term_id = cursor.lastrowid
        cursor = await conn.execute(
            "INSERT INTO courses (tenant_id, term_id, name) VALUES (?, ?, ?)",
            (tenant_id, term_id, "Veri Yapıları"),
        )
        assert cursor.lastrowid is not None
        course_id = cursor.lastrowid
        cursor = await conn.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES (?, ?, ?)",
            (tenant_id, course_id, "Bölüm 1"),
        )
        assert cursor.lastrowid is not None
        chapter_id = cursor.lastrowid

        # Konu evreni + chat eşleşmesi için anahtar kelimeler
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                tenant_id,
                chapter_id,
                "# Not",
                "{}",
                json.dumps(
                    [
                        {"topic": "Bağlı Liste", "keywords": ["pointer"]},
                        {"topic": "Yığın", "keywords": []},
                        {"topic": "Kuyruk", "keywords": []},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )

        # Quiz: "Bağlı Liste" 4 soru — denemede 1 doğru / 4 → accuracy 0.25
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, _questions_json("Bağlı Liste", 4)),
        )
        assert cursor.lastrowid is not None
        quiz_id = cursor.lastrowid
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score) "
            "VALUES (?, ?, ?, ?)",
            (
                tenant_id,
                quiz_id,
                json.dumps(
                    [
                        {"qid": "0-0", "selected_index": 0},
                        {"qid": "0-1", "selected_index": 1},
                        {"qid": "0-2", "selected_index": 2},
                        {"qid": "0-3", "selected_index": 3},
                    ]
                ),
                25,
            ),
        )

        # Quiz: "Kuyruk" 2 soru — 1 doğru / 2 → accuracy 0.5 (tek sinyalli konu)
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, _questions_json("Kuyruk", 2)),
        )
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score) "
            "VALUES (?, ?, ?, ?)",
            (
                tenant_id,
                cursor.lastrowid,
                json.dumps(
                    [
                        {"qid": "0-0", "selected_index": 0},
                        {"qid": "0-1", "selected_index": 3},
                    ]
                ),
                50,
            ),
        )

        # Kartlar: "Bağlı Liste" 2 kart — 1 "good" + 1 "again" → retention 0.5
        cursor = await conn.execute(
            "INSERT INTO flashcard_sets (tenant_id, course_id, chapter_id, cards_json) "
            "VALUES (?, ?, ?, ?)",
            (
                tenant_id,
                course_id,
                chapter_id,
                json.dumps(
                    [
                        {"topic": "Bağlı Liste", "front": "a", "back": "b"},
                        {"topic": "Bağlı Liste", "front": "c", "back": "d"},
                        {"topic": "Kuyruk", "front": "e", "back": "f"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
        assert cursor.lastrowid is not None
        set_id = cursor.lastrowid
        for card_index, rating in ((0, "good"), (1, "again")):
            await conn.execute(
                "INSERT INTO card_reviews (tenant_id, set_id, card_index, last_rating) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, set_id, card_index, rating),
            )

        # Chat: 5 kullanıcı sorusu "Bağlı Liste"/pointer ile eşleşir → baskı 1.0
        for content in (
            "Bağlı liste nasıl çalışır?",
            "bağlı liste ile dizi farkı ne?",
            "pointer nedir",
            "Bağlı Liste'de silme adımları?",
            "pointer aritmetiği örneği verir misin",
        ):
            await conn.execute(
                "INSERT INTO chat_messages (tenant_id, course_id, role, content) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, course_id, "user", content),
            )
        # Asistan mesajı sayılmamalı
        await conn.execute(
            "INSERT INTO chat_messages (tenant_id, course_id, role, content) VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, "assistant", "Bağlı liste bir düğüm zinciridir."),
        )
        await conn.commit()
    return course_id


async def test_weakness_score_uc_sinyalden_uretilir(heatmap_client):
    course_id = await _seed()
    resp = await heatmap_client.get(f"/api/courses/{course_id}/heatmap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["weights"] == {"quiz": 0.5, "card": 0.3, "chat": 0.2}

    by_topic = {t["topic"]: t for t in body["topics"]}
    weak = by_topic["Bağlı Liste"]
    assert weak["quiz_accuracy"] == 0.25
    assert weak["card_retention"] == 0.5
    assert weak["chat_question_count"] == 5
    # 0.5*(1-0.25) + 0.3*(1-0.5) + 0.2*1.0 = 0.375 + 0.15 + 0.2 = 0.725 (ağırlık toplamı 1.0)
    assert weak["weakness_score"] == 0.725
    assert weak["sample_size"] == 4 + 2 + 5
    # En zayıf konu listenin başında
    assert body["topics"][0]["topic"] == "Bağlı Liste"


async def test_verisi_olmayan_konu_null_doner(heatmap_client):
    course_id = await _seed()
    resp = await heatmap_client.get(f"/api/courses/{course_id}/heatmap")
    by_topic = {t["topic"]: t for t in resp.json()["topics"]}

    # "Yığın": hiçbir sinyalde veri yok → tüm oranlar ve skor null
    assert by_topic["Yığın"] == {
        "topic": "Yığın",
        "quiz_accuracy": None,
        "card_retention": None,
        "chat_question_count": 0,
        "weakness_score": None,
        "sample_size": 0,
    }

    # "Kuyruk": yalnızca quiz sinyali var (kartı var ama hiç tekrar edilmemiş, chat'te
    # sorulmamış) → eksik sinyaller paydadan düşer, skor tek sinyale normalize edilir:
    # 0.5*(1-0.5) / 0.5 = 0.5 — ağırlık düşmeseydi 0.25 çıkardı.
    queue = by_topic["Kuyruk"]
    assert queue["quiz_accuracy"] == 0.5
    assert queue["card_retention"] is None
    assert queue["chat_question_count"] == 0
    assert queue["weakness_score"] == 0.5
    assert queue["sample_size"] == 2

    # Skoru olmayan konular listenin sonunda
    assert resp.json()["topics"][-1]["topic"] == "Yığın"


async def test_tenant_izolasyonu(heatmap_client):
    """Başka kiracının aynı isimli dersi/verisi yerel kiracıya sızmaz."""
    course_id = await _seed()
    other_course_id = await _seed(tenant_id="other-tenant")

    resp = await heatmap_client.get(f"/api/courses/{other_course_id}/heatmap")
    assert resp.status_code == 404

    # Yerel dersin sayıları başka kiracının verisiyle şişmemiş olmalı
    resp = await heatmap_client.get(f"/api/courses/{course_id}/heatmap")
    by_topic = {t["topic"]: t for t in resp.json()["topics"]}
    assert by_topic["Bağlı Liste"]["sample_size"] == 11

    # Yerel dersin satırlarını başka kiracıya çevir → sinyaller boşalır
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "UPDATE chat_messages SET tenant_id = 'other-tenant' WHERE course_id = ?",
            (course_id,),
        )
        await conn.execute("UPDATE quiz_attempts SET tenant_id = 'other-tenant'")
        await conn.execute("UPDATE card_reviews SET tenant_id = 'other-tenant'")
        await conn.commit()

    resp = await heatmap_client.get(f"/api/courses/{course_id}/heatmap")
    by_topic = {t["topic"]: t for t in resp.json()["topics"]}
    weak = by_topic["Bağlı Liste"]
    assert weak["quiz_accuracy"] is None
    assert weak["card_retention"] is None
    assert weak["chat_question_count"] == 0
    assert weak["weakness_score"] is None
    assert weak["sample_size"] == 0
