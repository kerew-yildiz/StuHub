"""Chapter'ı olmayan ders için card-summary — K4 regresyonu (500 → 200).

Kök neden: `card_summary.py`'de `chapter_ids` boşken `len(chapter_ids) or 1` hilesi
SQL'de 2 placeholder üretiyor, parametre demeti 1 kalıyordu (sürücü `InterfaceError`
→ 500). Bu dosya boş chapter listesinin guard'landığını doğrular.
"""

from __future__ import annotations

import pytest


async def _chapter_siz_ders(client) -> int:
    term = (await client.post("/api/terms", json={"name": "2026 Güz"})).json()
    course = (
        await client.post(f"/api/terms/{term['id']}/courses", json={"name": "Veri Yapıları"})
    ).json()
    return course["id"]


@pytest.mark.asyncio
async def test_chapter_siz_ders_200_ve_bos_chapter_listesi(client):
    course_id = await _chapter_siz_ders(client)

    resp = await client.get(f"/api/courses/{course_id}/card-summary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["chapters"] == []
    assert body["total_chapters"] == 0
    assert body["completed_chapters"] == 0
    assert body["progress"] is None
    assert body["last_activity"] is None


@pytest.mark.asyncio
async def test_chapter_siz_derste_sinav_ve_sure_calisir(client):
    """Chapter'dan bağımsız sorgular (sınav, çalışma süresi) boş listede de çalışmalı."""
    course_id = await _chapter_siz_ders(client)

    exam = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": "2099-12-01", "scope_json": []},
    )
    assert exam.status_code == 201, exam.text
    session = await client.post(
        f"/api/courses/{course_id}/study-sessions",
        json={"session_id": "k4-sess-1", "duration_sec": 1800},
    )
    assert session.status_code == 201, session.text

    resp = await client.get(f"/api/courses/{course_id}/card-summary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_exam"]["title"] == "Vize"
    assert body["next_exam"]["days_left"] > 0
    assert body["total_study_sec"] == 1800
    assert body["chapters"] == []
