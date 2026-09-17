"""Chapter çalışma süresi (heartbeat) + ders/chapter toplam uçları."""

from __future__ import annotations

import aiosqlite

from src.config import settings


async def _seed(client, ikinci_ders: bool = False) -> dict:
    term = (await client.post("/api/terms", json={"name": "2026 Güz"})).json()
    course = (
        await client.post(f"/api/terms/{term['id']}/courses", json={"name": "Veri Yapıları"})
    ).json()
    chapter = (
        await client.post(f"/api/courses/{course['id']}/chapters", json={"title": "Ağaçlar"})
    ).json()
    seeded = {"term": term, "course": course, "chapter": chapter}
    if ikinci_ders:
        other = (
            await client.post(f"/api/terms/{term['id']}/courses", json={"name": "Fizik"})
        ).json()
        seeded["other_course"] = other
    return seeded


async def _rows(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]


async def test_heartbeat_kaydeder_ve_toplamlari_besler(client):
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]
    chapter_id = seeded["chapter"]["id"]

    for session_id in ("hb-1", "hb-2"):
        resp = await client.post(
            f"/api/courses/{course_id}/chapters/{chapter_id}/study-time",
            json={"session_id": session_id, "duration_sec": 45},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["chapter_id"] == chapter_id

    rows = await _rows("SELECT chapter_id, duration_sec FROM study_sessions ORDER BY id")
    assert [(r["chapter_id"], r["duration_sec"]) for r in rows] == [
        (chapter_id, 45),
        (chapter_id, 45),
    ]

    aggregate = (await client.get(f"/api/courses/{course_id}/study-time")).json()
    assert aggregate["total_study_sec"] == 90
    assert aggregate["chapters"] == [{"chapter_id": chapter_id, "total_study_sec": 90}]

    summary = (await client.get(f"/api/courses/{course_id}/card-summary")).json()
    assert summary["total_study_sec"] == 90
    assert summary["chapters"][0]["total_study_sec"] == 90


async def test_ayni_heartbeat_iki_kez_sayilmaz(client):
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]
    chapter_id = seeded["chapter"]["id"]
    payload = {"session_id": "hb-tekrar", "duration_sec": 45}

    first = await client.post(
        f"/api/courses/{course_id}/chapters/{chapter_id}/study-time", json=payload
    )
    second = await client.post(
        f"/api/courses/{course_id}/chapters/{chapter_id}/study-time", json=payload
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(await _rows("SELECT id FROM study_sessions WHERE session_id = 'hb-tekrar'")) == 1
    aggregate = (await client.get(f"/api/courses/{course_id}/study-time")).json()
    assert aggregate["total_study_sec"] == 45


async def test_baska_dersin_chapteri_404(client):
    seeded = await _seed(client, ikinci_ders=True)
    resp = await client.post(
        f"/api/courses/{seeded['other_course']['id']}"
        f"/chapters/{seeded['chapter']['id']}/study-time",
        json={"session_id": "hb-yabanci", "duration_sec": 45},
    )
    assert resp.status_code == 404
    assert await _rows("SELECT id FROM study_sessions") == []


async def test_sure_sinirlari_dogrulanir(client):
    seeded = await _seed(client)
    url = f"/api/courses/{seeded['course']['id']}/chapters/{seeded['chapter']['id']}/study-time"

    for duration in (0, 301):
        resp = await client.post(
            url, json={"session_id": f"hb-{duration}", "duration_sec": duration}
        )
        assert resp.status_code == 422, resp.text
    assert await _rows("SELECT id FROM study_sessions") == []


async def test_toplamlar_kiraci_ve_chapter_ayrimi(client):
    """Toplam yalnızca kendi kiracının kayıtlarını sayar; chapter'sız süre ders toplamına girer."""
    seeded = await _seed(client)
    course_id = seeded["course"]["id"]
    chapter_id = seeded["chapter"]["id"]

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.executemany(
            "INSERT INTO study_sessions "
            "(tenant_id, course_id, chapter_id, session_id, duration_sec)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                # Başka kiracının aynı session_id'li kaydı: toplamlara girmemeli.
                ("other", course_id, chapter_id, "hb-ortak", 600),
                # Chapter'sız (ders bazlı) süre: ders toplamına girer, chapter dökümüne girmez.
                ("local", course_id, None, "ders-bazli", 30),
            ],
        )
        await conn.commit()

    resp = await client.post(
        f"/api/courses/{course_id}/chapters/{chapter_id}/study-time",
        json={"session_id": "hb-ortak", "duration_sec": 45},
    )
    assert resp.status_code == 201

    aggregate = (await client.get(f"/api/courses/{course_id}/study-time")).json()
    assert aggregate["total_study_sec"] == 75
    assert aggregate["chapters"] == [{"chapter_id": chapter_id, "total_study_sec": 45}]

    summary = (await client.get(f"/api/courses/{course_id}/card-summary")).json()
    assert summary["total_study_sec"] == 75
    assert summary["chapters"][0]["total_study_sec"] == 45


async def test_bilinmeyen_ders_404(client):
    assert (await client.get("/api/courses/99999/study-time")).status_code == 404
