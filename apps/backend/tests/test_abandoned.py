"""Terk edilmiş konular kurtarma listesi testleri (Plan #50) — LLM YOK."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import aiosqlite

from src.config import settings
from src.main import app
from src.routers import abandoned as abandoned_router

# Router kaydı `src/routers/__init__.py`'de yapılır; kayıt henüz eklenmemişse
# (paralel geliştirme) test kendi başına da koşabilsin diye burada bir kez bağlanır.
if not any(getattr(r, "path", "") == "/api/courses/{course_id}/abandoned" for r in app.routes):
    app.include_router(abandoned_router.router)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def _make_chapter(client, course_id: int, title: str) -> int:
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": title})
    return resp.json()["id"]


async def _add_note(
    chapter_id: int, topics: list[str], generated_at: datetime, tenant_id: str = "local"
) -> None:
    topics_blob = json.dumps(
        [{"topic": t, "keywords": [], "slide_refs": []} for t in topics], ensure_ascii=False
    )
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, "
            "topics_json, generated_at) VALUES (?, ?, '# İçerik', '{}', ?, ?)",
            (tenant_id, chapter_id, topics_blob, _iso(generated_at)),
        )
        await conn.commit()


async def _add_quiz_attempt(
    chapter_id: int, topic: str, created_at: datetime, tenant_id: str = "local"
) -> None:
    questions_json = {
        "topics": [
            {
                "topic": topic,
                "questions": [{"question": "S?", "options": ["A", "B", "C", "D"]}],
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
        await conn.execute(
            "INSERT INTO quiz_attempts (tenant_id, quiz_id, user_answers_json, score, "
            "feedback_json, created_at) VALUES (?, ?, '[]', 100, '{}', ?)",
            (tenant_id, quiz_id, _iso(created_at)),
        )
        await conn.commit()


NOW = datetime.now(UTC)
OLD = NOW - timedelta(days=30)
RECENT = NOW - timedelta(days=2)


async def test_uc_haftadir_hicbir_aktivitesi_olmayan_konu_donuyor(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id, "Bölüm 1")
    await _add_note(chapter_id, ["Terk Edilmiş Konu"], generated_at=OLD)

    resp = await client.get(f"/api/courses/{course_id}/abandoned")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["topic"] == "Terk Edilmiş Konu"
    assert body[0]["chapter_id"] == chapter_id
    assert body[0]["last_activity"] is None


async def test_yakin_zamanda_notu_uretilen_konu_terk_edilmis_sayilmaz(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id, "Bölüm 1")
    await _add_note(chapter_id, ["Yeni Konu"], generated_at=RECENT)

    resp = await client.get(f"/api/courses/{course_id}/abandoned")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_yakin_zamanda_quiz_denemesi_olan_konu_terk_edilmis_sayilmaz(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id, "Bölüm 1")
    await _add_note(chapter_id, ["Aktif Konu"], generated_at=OLD)
    await _add_quiz_attempt(chapter_id, "Aktif Konu", created_at=RECENT)

    resp = await client.get(f"/api/courses/{course_id}/abandoned")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_eski_quiz_denemesi_olan_konu_terk_edilmis_sayilir_ve_tarih_doner(client):
    course_id = await _make_course(client)
    chapter_id = await _make_chapter(client, course_id, "Bölüm 1")
    await _add_note(chapter_id, ["Soğumuş Konu"], generated_at=OLD)
    await _add_quiz_attempt(chapter_id, "Soğumuş Konu", created_at=OLD)

    resp = await client.get(f"/api/courses/{course_id}/abandoned")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["topic"] == "Soğumuş Konu"
    assert body[0]["last_activity"] is not None


async def test_tenant_izolasyonu(client):
    """Başka kiracının aynı course_id altındaki notu/aktivitesi yerel kiracıya sızmaz."""
    course_id = await _make_course(client)

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO chapters (tenant_id, course_id, title) VALUES (?, ?, ?)",
            ("other-tenant", course_id, "Gizli Bölüm"),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        other_chapter_id = cursor.lastrowid
    await _add_note(other_chapter_id, ["Gizli Konu"], generated_at=OLD, tenant_id="other-tenant")

    resp = await client.get(f"/api/courses/{course_id}/abandoned")
    assert resp.status_code == 200
    assert resp.json() == []
