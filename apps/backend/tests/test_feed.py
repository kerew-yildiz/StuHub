"""Sonsuz kaydırma quiz feed'i testleri — havuz servisi, cevap kaydı, izolasyon.

Gerçek LLM çağrısı YOK: üretim yolu `quiz_generator.generate_feed_batch` düzeyinde
mock'lanır (mevcut test kalıbı — bkz. test_quizzes_router.py).
"""

import asyncio
import json

import aiosqlite
import pytest

from src.config import settings
from src.main import app
from src.routers import feed as feed_router
from src.services import feed_service, llm_service, quiz_generator
from src.workers import feed_topup

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(getattr(r, "path", "") == "/api/feed/{feed_id}/answer" for r in app.routes):
    app.include_router(feed_router.router)

# Autouse `_no_llm` fixture bu fonksiyonu boş listeye sabitler (aşağıda) — round-robin
# testi gerçek implementasyonu sınamak için import anındaki orijinali saklar.
_REAL_GENERATE_FEED_BATCH = quiz_generator.generate_feed_batch


@pytest.fixture(autouse=True)
async def _no_llm(monkeypatch):
    """Gerçek LLM çağrısı yok (varsayılan: boş parti); fire-and-forget görevler drene edilir.

    `spawn_topup` arka plan görevi testin event loop'undan sonra yaşarsa aiosqlite
    işçi thread'i kapanmış loop'a yazar (`Event loop is closed`) — bu yüzden her testin
    sonunda bekleyen doldurma görevleri beklenir.
    """
    # `feed_service._filling` süreç düzeyinde bir kilit kümesi — bir test sırasında
    # eklenip `finally`'e ulaşamadan (ör. event loop testin sonunda kapanınca) kalırsa
    # sonraki testte AYNI (tenant_id, course_id) çiftine rastlayınca `ensure_pool`
    # sessizce 0 döner (gerçek bug — 2026-09-05, tam paket koşulunca ortaya çıktı).
    feed_service._filling.clear()

    async def _empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(feed_service.quiz_generator, "generate_feed_batch", _empty)
    yield
    pending = list(feed_service._pending_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    feed_service._filling.clear()


def _questions_json(prefix: str = "S"):
    return {
        "topics": [
            {
                "topic": "Konu A",
                "questions": [
                    {
                        "topic": "Konu A",
                        "question": f"{prefix}1 Bağlı listeler nedir?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 0,
                        "explanation": "Açıklama 1.",
                        "feedback_correct": "Doğru!",
                        "feedback_wrong": "Doğru cevap: A.",
                        "citations": [{"id": 1, "chunk_id": "chk_1", "quote": "kaynak"}],
                    },
                    {
                        "topic": "Konu A",
                        "question": f"{prefix}2 Sıralama yöntemi?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 2,
                        "explanation": "Açıklama 2.",
                        "feedback_correct": "Doğru!",
                        "feedback_wrong": "Doğru cevap: C.",
                        "citations": [{"id": 1, "chunk_id": "chk_1", "quote": "kaynak"}],
                    },
                ],
            }
        ]
    }


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _make_chapter(client, course_id: int) -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Konu A"})
    return resp.json()["id"]


async def _insert_quiz(chapter_id: int, prefix: str = "S", tenant_id: str = "local") -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(_questions_json(prefix), ensure_ascii=False)),
        )
        await conn.commit()
        quiz_id = cursor.lastrowid
        assert quiz_id is not None
        return quiz_id


async def _seeded_course(client, prefix: str = "S") -> int:
    """Bir quiz'i (2 soru) hazır olan ders — feed havuzu bundan dolgu yapar."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _insert_quiz(chapter_id, prefix)
    return course_id


async def _rows(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]


async def test_servis_edilen_soru_dogru_cevap_sizdirmaz(client):
    course_id = await _seeded_course(client)

    resp = await client.get(f"/api/courses/{course_id}/feed?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert set(data["items"][0]) == {
        "feed_id",
        "question",
        "options",
        "topic",
        "chapter_id",
        "difficulty",
    }
    # Doğru cevap/açıklama gövdede hiçbir biçimde yer almaz
    assert "correct_index" not in resp.text
    assert "Açıklama 1." not in resp.text
    assert data["items"][0]["topic"] == "Konu A"


async def test_ayni_soru_iki_kez_servis_edilmez(client):
    course_id = await _seeded_course(client)

    first = (await client.get(f"/api/courses/{course_id}/feed?limit=1")).json()
    second = (await client.get(f"/api/courses/{course_id}/feed?limit=1")).json()
    third = (await client.get(f"/api/courses/{course_id}/feed?limit=5")).json()

    assert len(first["items"]) == 1
    assert len(second["items"]) == 1
    assert first["items"][0]["feed_id"] != second["items"][0]["feed_id"]
    # Havuzda yalnızca 2 soru vardı; üçüncü istek boş döner (tekrar servis yok)
    assert third["items"] == []
    assert third["pool_ready"] == 0


async def test_cevap_quiz_attempts_a_yazilir(client):
    course_id = await _seeded_course(client)
    items = (await client.get(f"/api/courses/{course_id}/feed?limit=10")).json()["items"]
    target = next(i for i in items if i["question"].startswith("S1"))

    resp = await client.post(
        f"/api/feed/{target['feed_id']}/answer",
        json={"selected_index": 1, "elapsed_ms": 4200},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["correct"] is False
    assert body["correct_index"] == 0
    assert body["explanation"] == "Açıklama 1."
    assert body["chapter_id"] == target["chapter_id"]

    attempts = await _rows("SELECT * FROM quiz_attempts")
    assert len(attempts) == 1
    answers = json.loads(attempts[0]["user_answers_json"])
    assert answers == [{"qid": "0-0", "selected_index": 1}]
    result = json.loads(attempts[0]["feedback_json"])["results"][0]
    assert result["correct"] is False
    assert result["correct_index"] == 0
    assert result["elapsed_ms"] == 4200
    assert result["options"] == ["A", "B", "C", "D"]
    assert attempts[0]["score"] == 0

    # Doğru cevap yolu
    other = next(i for i in items if i["question"].startswith("S2"))
    ok = await client.post(
        f"/api/feed/{other['feed_id']}/answer", json={"selected_index": 2, "elapsed_ms": 900}
    )
    assert ok.json()["correct"] is True
    assert ok.json()["correct_index"] == 2
    assert len(await _rows("SELECT id FROM quiz_attempts")) == 2
    # Cevaplanan soru tüketildi: bir daha servis edilmez
    assert (await client.get(f"/api/courses/{course_id}/feed")).json()["items"] == []


async def test_skip_soruyu_tekrar_gostermez(client):
    course_id = await _seeded_course(client)
    items = (await client.get(f"/api/courses/{course_id}/feed?limit=1")).json()["items"]
    feed_id = items[0]["feed_id"]

    resp = await client.post(
        f"/api/courses/{course_id}/feed/skip", json={"feed_id": feed_id}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    later = (await client.get(f"/api/courses/{course_id}/feed?limit=10")).json()["items"]
    assert feed_id not in [i["feed_id"] for i in later]
    # Atlanan soru denemeye yazılmaz
    assert await _rows("SELECT id FROM quiz_attempts") == []

    missing = await client.post(
        f"/api/courses/{course_id}/feed/skip", json={"feed_id": 99999}
    )
    assert missing.status_code == 404


async def test_bos_havuz_hata_vermez_generating_true(client):
    course_id = await _make_course(client)  # quiz yok, not yok → üretilecek soru yok

    resp = await client.get(f"/api/courses/{course_id}/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["pool_ready"] == 0
    assert data["generating"] is True

    assert (await client.get("/api/courses/99999/feed")).status_code == 404


async def test_tenant_izolasyonu(client):
    course_id = await _seeded_course(client)
    # Başka kiracının aynı derse ait bölümü + quizi (bölüm de 'other' kiracısına ait
    # olmalı: backfill sorgusu quiz→chapter join'ini tenant_id üzerinden kurar)
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES ('other', ?, 'Konu A')",
            (course_id,),
        )
        await conn.commit()
        chapter_id = cursor.lastrowid
    assert chapter_id is not None
    await _insert_quiz(chapter_id, "X", tenant_id="other")
    await feed_service.backfill_from_existing(course_id, "other")

    other_rows = await _rows(
        "SELECT id FROM feed_questions WHERE tenant_id = ?", ("other",)
    )
    assert len(other_rows) == 2

    items = (await client.get(f"/api/courses/{course_id}/feed?limit=10")).json()["items"]
    assert [i["question"] for i in items] == [
        "S1 Bağlı listeler nedir?",
        "S2 Sıralama yöntemi?",
    ]

    # Diğer kiracının sorusu cevaplanamaz / atlanamaz
    foreign_id = other_rows[0]["id"]
    resp = await client.post(
        f"/api/feed/{foreign_id}/answer", json={"selected_index": 0, "elapsed_ms": 10}
    )
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/courses/{course_id}/feed/skip", json={"feed_id": foreign_id}
    )
    assert resp.status_code == 404
    assert await feed_service.pool_size(course_id, "other") == 2


async def test_uretilen_parti_havuza_ve_quizzes_a_yazilir(client, monkeypatch):
    """LLM partisi (mock) hem gerçek bir quiz satırı hem feed havuzu satırı üretir."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES ('local', ?, '# Konu A\nmetin', '{}', '[]')",
            (chapter_id,),
        )
        await conn.commit()

    batch = [
        {
            "topic": "Konu A",
            "question": f"Üretilen soru {i}?",
            "options": ["A", "B", "C", "D"],
            "correct_index": i % 4,
            "explanation": "Açıklama.",
            "feedback_correct": "Doğru!",
            "feedback_wrong": "Doğru cevap.",
            "citations": [],
            "difficulty": "medium",
        }
        for i in range(3)
    ]

    async def _fake_batch(*_args, **_kwargs):
        return batch

    monkeypatch.setattr(feed_service.quiz_generator, "generate_feed_batch", _fake_batch)

    added = await feed_service.ensure_pool(course_id, "local")
    assert added == 3

    rows = await _rows("SELECT * FROM feed_questions ORDER BY id")
    assert len(rows) == 3
    assert {r["source"] for r in rows} == {"generated"}
    assert {r["difficulty"] for r in rows} == {"medium"}
    quizzes = await _rows("SELECT id, questions_json FROM quizzes")
    assert len(quizzes) == 1
    assert rows[0]["origin_question_id"] == f"{quizzes[0]['id']}:0-0"
    assert "Üretilen soru 0?" in quizzes[0]["questions_json"]

    items = (await client.get(f"/api/courses/{course_id}/feed?limit=10")).json()["items"]
    assert len(items) == 3
    assert items[0]["difficulty"] == "medium"


async def test_get_feed_dolduruyu_fire_and_forget_tetikler(client, monkeypatch):
    course_id = await _seeded_course(client)
    calls: list[tuple[int, str]] = []
    monkeypatch.setattr(
        feed_router.feed_service,
        "spawn_topup",
        lambda cid, tid: calls.append((cid, tid)),
    )

    resp = await client.get(f"/api/courses/{course_id}/feed?limit=1")
    assert resp.status_code == 200
    assert calls == [(course_id, "local")]


async def test_generate_feed_batch_konulari_round_robin_gezer(client, monkeypatch):
    """Parti iki konuya dağıtılır ve prompt'a tekrar yasağı negatif listesi girer."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES ('local', ?, ?, '{}', '[]')",
            (chapter_id, "## Konu A\nA metni\n\n## Konu B\nB metni\n"),
        )
        await conn.commit()

    prompts: list[str] = []

    async def fake_chat_json(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return {
            "questions": [
                {
                    "question": f"Soru {len(prompts)}-{i}",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": i % 4,
                    "explanation": "Açıklama.",
                    "feedback_correct": "Doğru!",
                    "feedback_wrong": "Doğru cevap.",
                    "citations": [],
                    "difficulty": "HARD" if i == 0 else "bilinmeyen",
                }
                for i in range(5)
            ]
        }

    # autouse `_no_llm` fixture, `feed_service.quiz_generator.generate_feed_batch`'i
    # (aynı modül nesnesi) boş listeye sabitliyor — bu test gerçek round-robin/tekrar
    # yasağı mantığını sınadığı için, yalnızca bu testte gerçek fonksiyonu geri yükle.
    monkeypatch.setattr(quiz_generator, "generate_feed_batch", _REAL_GENERATE_FEED_BATCH)
    monkeypatch.setattr(llm_service, "chat_json", fake_chat_json)

    questions = await quiz_generator.generate_feed_batch(
        chapter_id, "local", count=10, avoid=["Daha önce sorulan soru"], topic_offset=0
    )

    assert len(questions) == 10
    assert {q["topic"] for q in questions} == {"Konu A", "Konu B"}
    assert questions[0]["difficulty"] == "hard"  # normalize edildi
    assert questions[1]["difficulty"] is None  # tanınmayan etiket düşürüldü
    assert "TEKRAR YASAĞI" in prompts[0]
    assert "Daha önce sorulan soru" in prompts[0]
    # İkinci çağrı ilk partinin sorularını da negatif listeye alır
    assert "Soru 1-0" in prompts[1]


async def test_worker_aktif_dersin_havuzunu_doldurur(client):
    course_id = await _seeded_course(client)
    chapter_id = (await _rows("SELECT id FROM chapters"))[0]["id"]

    # Feed kullanımı doğrudan servis katmanından simüle edilir: router'ın GET'i
    # fire-and-forget `ensure_pool` görevi başlatır ve o görev bu testin ölçtüğü
    # doldurmayı kendisi yapabilir (ya da süreç-içi kilidi tutar) — worker'ın kendi
    # katkısını ölçmek için istek yolu bilinçli olarak devre dışı bırakıldı.
    assert await feed_service.backfill_from_existing(course_id, "local") == 2
    assert len(await feed_service.serve_batch(course_id, "local", 1)) == 1
    assert await feed_service.active_course_ids(24) == [("local", course_id)]

    await _insert_quiz(chapter_id, "T")  # havuza girmemiş 2 yeni soru
    added = await feed_topup.topup_active_courses()

    assert added == 2
    assert await feed_service.pool_size(course_id, "local") == 3
    assert await feed_topup.topup_active_courses() == 0  # kopyalanacak soru kalmadı
