"""Sınav geri sayım + unutma eğrisi router testleri (plan #9 / #12).

Hesabın kendisi `tests/test_srs_retention.py`'de saf fonksiyon düzeyinde doğrulanır;
burada yalnızca uçların CRUD davranışı, kapsam süzgeci, kiracı izolasyonu ve
cevap alanlarının (`back`) dışarı sızmaması sınanır.
"""

import json
from datetime import UTC, date, datetime, timedelta

import aiosqlite

from src.config import settings


async def _insert(sql: str, params: tuple) -> int:
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(sql, params)
        await conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("satır kimliği alınamadı")
        return row_id


async def _make_course(client) -> tuple[int, int]:
    """(course_id, chapter_id) üretir."""
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bölüm 1"})
    return course_id, resp.json()["id"]


def _cards(prefix: str, count: int, topic: str) -> str:
    return json.dumps(
        [
            {
                "topic": topic,
                "front": f"{prefix} soru {index}",
                "back": f"GIZLI-CEVAP-{prefix}-{index}",
                "type": "qa",
            }
            for index in range(count)
        ],
        ensure_ascii=False,
    )


async def _seed_set(
    course_id: int,
    chapter_id: int | None,
    prefix: str,
    count: int,
    topic: str,
    tenant_id: str = "local",
) -> int:
    return await _insert(
        "INSERT INTO flashcard_sets (tenant_id, course_id, chapter_id, cards_json) "
        "VALUES (?, ?, ?, ?)",
        (tenant_id, course_id, chapter_id, _cards(prefix, count, topic)),
    )


def _in_days(offset: int) -> str:
    return (datetime.now(UTC).date() + timedelta(days=offset)).isoformat()


# ── CRUD ───────────────────────────────────────────────────────────────────


async def test_exam_crud_roundtrip(client):
    """Oluştur → listele → sil → liste boşalır; ikinci silme 404."""
    course_id, chapter_id = await _make_course(client)

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": _in_days(10), "chapter_ids": [chapter_id]},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["title"] == "Vize"
    assert created["exam_date"] == _in_days(10)
    assert created["chapter_ids"] == [chapter_id]
    assert created["days_left"] == 10

    # İkinci sınav daha erken tarihli — listeleme tarihe göre yakından uzağa.
    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Quiz", "exam_date": _in_days(3)},
    )
    assert resp.status_code == 201
    quiz_id = resp.json()["id"]
    assert resp.json()["chapter_ids"] == []

    resp = await client.get(f"/api/courses/{course_id}/exams")
    assert resp.status_code == 200
    titles = [exam["title"] for exam in resp.json()]
    assert titles == ["Quiz", "Vize"]

    resp = await client.delete(f"/api/exams/{quiz_id}")
    assert resp.status_code == 204
    resp = await client.delete(f"/api/exams/{quiz_id}")
    assert resp.status_code == 404

    resp = await client.get(f"/api/courses/{course_id}/exams")
    assert [exam["id"] for exam in resp.json()] == [created["id"]]


async def test_create_exam_validates_course_and_scope(client):
    """Bilinmeyen ders 404, başka derse ait bölüm kapsamı 422."""
    course_id, chapter_id = await _make_course(client)
    other_course_id, other_chapter_id = await _make_course(client)

    resp = await client.post(
        "/api/courses/999999/exams", json={"title": "Yok", "exam_date": _in_days(5)}
    )
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": _in_days(5), "chapter_ids": [other_chapter_id]},
    )
    assert resp.status_code == 422

    # Kendi bölümü sorunsuz geçer (kontrol negatif teste bağımlı kalmasın).
    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": _in_days(5), "chapter_ids": [chapter_id]},
    )
    assert resp.status_code == 201
    assert other_course_id != course_id


# ── plan ───────────────────────────────────────────────────────────────────


async def test_exam_plan_spreads_cards_over_days_without_leaking_answers(client):
    """5 kart / 3 günlük pencere: dengeli dağılır, sınav gününe hiçbir şey konmaz,
    yanıt (`back`) alanı yanıtta yer almaz."""
    course_id, chapter_id = await _make_course(client)
    await _seed_set(course_id, chapter_id, "A", 5, "Ağaçlar")

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": _in_days(3)},
    )
    exam_id = resp.json()["id"]

    resp = await client.get(f"/api/exams/{exam_id}/plan")
    assert resp.status_code == 200, resp.text
    plan = resp.json()

    assert plan["exam"]["id"] == exam_id
    assert plan["total_cards"] == 5
    assert [day["date"] for day in plan["days"]] == [_in_days(0), _in_days(1), _in_days(2)]
    loads = sorted(day["card_count"] for day in plan["days"])
    assert loads == [1, 2, 2]
    assert sum(loads) == 5
    # Sınav gününe iş bırakılmaz.
    assert all(day["date"] < _in_days(3) for day in plan["days"])

    every_card = [card for day in plan["days"] for card in day["cards"]]
    assert len(every_card) == 5
    assert {card["topic"] for card in every_card} == {"Ağaçlar"}
    assert all(card["front"].startswith("A soru") for card in every_card)
    assert "GIZLI-CEVAP" not in resp.text
    assert all("back" not in card for card in every_card)

    resp = await client.get("/api/exams/424242/plan")
    assert resp.status_code == 404


async def test_exam_plan_honours_scope_chapters(client):
    """Kapsam bölümü verilen sınav yalnız o bölümün kartlarını planlar."""
    course_id, chapter_id = await _make_course(client)
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": "Bölüm 2"})
    second_chapter_id = resp.json()["id"]

    await _seed_set(course_id, chapter_id, "B1", 2, "Konu 1")
    await _seed_set(course_id, second_chapter_id, "B2", 4, "Konu 2")

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Kapsamlı", "exam_date": _in_days(4), "chapter_ids": [chapter_id]},
    )
    scoped_id = resp.json()["id"]
    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Final", "exam_date": _in_days(4)},
    )
    full_id = resp.json()["id"]

    scoped = (await client.get(f"/api/exams/{scoped_id}/plan")).json()
    assert scoped["total_cards"] == 2
    assert {card["topic"] for day in scoped["days"] for card in day["cards"]} == {"Konu 1"}

    full = (await client.get(f"/api/exams/{full_id}/plan")).json()
    assert full["total_cards"] == 6


async def test_exam_plan_for_past_exam_is_empty(client):
    """Tarihi geçmiş sınavda çalışma penceresi yoktur — plan boş, days_left negatif."""
    course_id, chapter_id = await _make_course(client)
    await _seed_set(course_id, chapter_id, "C", 3, "Konu")

    exam_id = await _insert(
        "INSERT INTO exams (tenant_id, course_id, title, exam_date, scope_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("local", course_id, "Geçmiş", _in_days(-2), "[]"),
    )

    plan = (await client.get(f"/api/exams/{exam_id}/plan")).json()
    assert plan["days"] == []
    assert plan["total_cards"] == 0
    assert plan["exam"]["days_left"] == -2


# ── retention ──────────────────────────────────────────────────────────────


async def test_course_retention_groups_topics_and_decays(client):
    """Konu bazlı eğri: hiç çalışılmamış konu 0.0 ve başta, çalışılmış konu düşerek gider."""
    course_id, chapter_id = await _make_course(client)
    reviewed_set = await _seed_set(course_id, chapter_id, "R", 2, "Taze Konu")
    await _seed_set(course_id, chapter_id, "S", 3, "Soğuk Konu")

    now = datetime.now(UTC)
    for card_index in range(2):
        await _insert(
            "INSERT INTO card_reviews (tenant_id, set_id, card_index, ease_factor, "
            "interval_days, repetitions, due_at, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "local",
                reviewed_set,
                card_index,
                2.5,
                6.0,
                2,
                (now + timedelta(days=6)).isoformat(sep=" ", timespec="seconds"),
                now.isoformat(sep=" ", timespec="seconds"),
            ),
        )

    resp = await client.get(f"/api/courses/{course_id}/retention?days=12")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_id"] == course_id
    assert body["horizon_days"] == 12

    topics = {topic["topic"]: topic for topic in body["topics"]}
    assert set(topics) == {"Taze Konu", "Soğuk Konu"}

    cold = topics["Soğuk Konu"]
    assert cold["card_count"] == 3
    assert cold["reviewed_count"] == 0
    assert cold["current"] == 0.0
    assert body["topics"][0]["topic"] == "Soğuk Konu"  # en zayıf konu başta

    fresh = topics["Taze Konu"]
    assert fresh["card_count"] == 2
    assert fresh["reviewed_count"] == 2
    assert fresh["current"] > 0.99
    series = [point["retention"] for point in fresh["points"]]
    assert [point["day"] for point in fresh["points"]][0] == 0
    assert [point["day"] for point in fresh["points"]][-1] == 12
    assert series == sorted(series, reverse=True)
    assert series[-1] < series[0]
    assert abs(series[4] - 0.9) < 0.01  # 6. günde ≈ SM-2 hedefi %90

    resp = await client.get("/api/courses/999999/retention")
    assert resp.status_code == 404


# ── kiracı izolasyonu ──────────────────────────────────────────────────────


async def test_other_tenant_exams_are_hidden(client):
    """Başka kiracının sınavı listelenmez, silinemez, planı okunamaz."""
    course_id, chapter_id = await _make_course(client)
    await _seed_set(course_id, chapter_id, "M", 2, "Konu")

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Benim Sınavım", "exam_date": _in_days(6)},
    )
    mine_id = resp.json()["id"]

    foreign_id = await _insert(
        "INSERT INTO exams (tenant_id, course_id, title, exam_date, scope_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("other-tenant", course_id, "Gizli Sınav", _in_days(1), "[]"),
    )

    resp = await client.get(f"/api/courses/{course_id}/exams")
    assert [exam["id"] for exam in resp.json()] == [mine_id]
    assert "Gizli Sınav" not in resp.text

    assert (await client.delete(f"/api/exams/{foreign_id}")).status_code == 404
    assert (await client.get(f"/api/exams/{foreign_id}/plan")).status_code == 404

    # Yabancı satır gerçekten duruyor — 404 sessiz silmeden değil, süzgeçten geliyor.
    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM exams WHERE id = ?", (foreign_id,))
        count_row = await cursor.fetchone()
    assert count_row is not None
    assert count_row[0] == 1


async def test_other_tenant_cards_excluded_from_plan_and_retention(client):
    """Yabancı kiracının kart destesi ne plana ne unutma eğrisine girer."""
    course_id, chapter_id = await _make_course(client)
    await _seed_set(course_id, chapter_id, "OK", 2, "Benim Konum")
    await _seed_set(course_id, chapter_id, "NO", 5, "Yabancı Konu", tenant_id="other-tenant")

    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": _in_days(2)},
    )
    exam_id = resp.json()["id"]

    plan = (await client.get(f"/api/exams/{exam_id}/plan")).json()
    assert plan["total_cards"] == 2

    retention = (await client.get(f"/api/courses/{course_id}/retention")).json()
    assert [topic["topic"] for topic in retention["topics"]] == ["Benim Konum"]
    assert date.fromisoformat(retention["generated_at"][:10]) == datetime.now(UTC).date()
