"""'Bugün ne çalışsam' ekranı testleri (Plan #13) — deterministik öncelik, LLM YOK."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import next_action as next_action_router

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(getattr(r, "path", "") == "/api/courses/{course_id}/next-action" for r in app.routes):
    app.include_router(next_action_router.router)


async def _make_course(client, name: str = "Veri Yapıları") -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": name})
    return resp.json()["id"]


async def _make_chapter(client, course_id: int, title: str = "Bölüm 1") -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": title})
    return resp.json()["id"]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def _add_flashcard_set_with_due(
    course_id: int, chapter_id: int, due_at: datetime | None, tenant_id: str = "local"
) -> int:
    cards = json.dumps([{"topic": "T", "front": "S?", "back": "C.", "type": "qa", "citations": []}])
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO flashcard_sets (tenant_id, course_id, chapter_id, cards_json) "
            "VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, chapter_id, cards),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        set_id = cursor.lastrowid
        if due_at is not None:
            await conn.execute(
                "INSERT INTO card_reviews (tenant_id, set_id, card_index, ease_factor, "
                "interval_days, repetitions, due_at, last_rating, reviewed_at) "
                "VALUES (?, ?, 0, 2.5, 1, 1, ?, 'good', ?)",
                (tenant_id, set_id, _iso(due_at), _iso(due_at - timedelta(days=1))),
            )
            await conn.commit()
    return set_id


async def _seed_repeated_error(chapter_id: int, tenant_id: str = "local") -> None:
    """Konu A'yı 2 kez yanlış yapılmış hale getirir (only_repeated eşiği)."""
    questions_json = {
        "topics": [
            {
                "topic": "Konu A",
                "questions": [
                    {"question": "Soru 1?", "options": ["A", "B", "C", "D"]},
                    {"question": "Soru 2?", "options": ["A", "B", "C", "D"]},
                ],
            }
        ]
    }
    wrong = lambda qid, q: {  # noqa: E731
        "qid": qid, "question": q, "options": ["A", "B", "C", "D"],
        "selected_index": 1, "correct_index": 0, "correct": False,
        "feedback": "x", "explanation": "x", "citations": [],
    }
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO quizzes (tenant_id, chapter_id, questions_json) VALUES (?, ?, ?)",
            (tenant_id, chapter_id, json.dumps(questions_json, ensure_ascii=False)),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        quiz_id = cursor.lastrowid
        for feedback in (
            {"results": [wrong("0-0", "Soru 1?")]},
            {"results": [wrong("0-1", "Soru 2?")]},
        ):
            await conn.execute(
                "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
                "feedback_json) VALUES (?, ?, '[]', 50, ?)",
                (tenant_id, quiz_id, json.dumps(feedback, ensure_ascii=False)),
            )
        await conn.commit()


async def _add_note(chapter_id: int, tenant_id: str = "local") -> None:
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
            "VALUES (?, ?, '# Konu\\nİçerik.', '{}', '[]')",
            (tenant_id, chapter_id),
        )
        await conn.commit()


async def test_vadesi_gecmis_kart_varsa_cards_doner(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    set_id = await _add_flashcard_set_with_due(
        course_id, chapter_id, datetime.now(UTC) - timedelta(days=1)
    )

    resp = await client.get(f"/api/courses/{course_id}/next-action")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "cards"
    assert body["target_id"] == set_id


async def test_vadesi_gecmemis_kart_atlanip_tekrarlanan_hataya_gecer(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _add_note(chapter_id)  # bölüm okunmuş sayılsın, 3. dal tetiklenmesin
    await _add_flashcard_set_with_due(
        course_id, chapter_id, datetime.now(UTC) + timedelta(days=5)
    )
    await _seed_repeated_error(chapter_id)

    resp = await client.get(f"/api/courses/{course_id}/next-action")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "error_quiz"
    assert "Konu A" in body["reason"]


async def test_hicbiri_yoksa_okunmamis_bolum_doner(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)

    resp = await client.get(f"/api/courses/{course_id}/next-action")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "read_chapter"
    assert body["target_id"] == chapter_id


async def test_hepsi_tamamsa_none_doner(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _add_note(chapter_id)

    resp = await client.get(f"/api/courses/{course_id}/next-action")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "action": "none",
        "reason": "Şu an için bekleyen bir öncelik yok.",
        "target_id": None,
    }


async def test_tenant_izolasyonu(client):
    """Başka kiracının vadesi geçmiş kartı/hatası/bölümü yerel kiracıyı etkilemez."""
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id)
    await _add_note(chapter_id)

    # Başka kiracıya ait aynı course_id altında vadesi geçmiş kart.
    await _add_flashcard_set_with_due(
        course_id, chapter_id, datetime.now(UTC) - timedelta(days=1), tenant_id="other-tenant"
    )

    resp = await client.get(f"/api/courses/{course_id}/next-action")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "none"


async def test_ders_bulunamazsa_404(client):
    resp = await client.get("/api/courses/999999/next-action")
    assert resp.status_code == 404
