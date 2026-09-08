"""Sınav sonrası muhasebe testleri (Plan #44) — LLM özet mock'lu."""

from src.routers import exams as exams_router


async def _make_course_and_exam(client) -> tuple[int, int]:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(
        f"/api/courses/{course_id}/exams",
        json={"title": "Vize", "exam_date": "2099-01-01"},
    )
    return course_id, resp.json()["id"]


def _fake_summarize(
    monkeypatch, summary: str = "Bilgi eksikliği ağırlıklı; ilgili konuları tekrar et."
):
    calls = []

    async def fake(**kwargs):
        calls.append(kwargs)
        return summary

    monkeypatch.setattr(exams_router, "summarize_postmortem", fake)
    return calls


async def test_postmortem_create_and_get_roundtrip(client, monkeypatch):
    _, exam_id = await _make_course_and_exam(client)
    calls = _fake_summarize(monkeypatch)

    resp = await client.post(
        f"/api/exams/{exam_id}/postmortem",
        json={
            "items": [
                {"question": "Yığın nedir?", "reason": "bilmiyordum"},
                {"question": "Kuyruk mu yığın mı?", "reason": "karıştırdım"},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exam_id"] == exam_id
    assert len(body["items"]) == 2
    assert body["summary"] == "Bilgi eksikliği ağırlıklı; ilgili konuları tekrar et."
    assert "created_at" in body
    assert calls[0]["exam_title"] == "Vize"

    get_resp = await client.get(f"/api/exams/{exam_id}/postmortem")
    assert get_resp.status_code == 200
    saved = get_resp.json()
    assert saved["summary"] == body["summary"]
    assert [item["reason"] for item in saved["items"]] == ["bilmiyordum", "karıştırdım"]


async def test_postmortem_requires_existing_exam(client, monkeypatch):
    _fake_summarize(monkeypatch)
    resp = await client.post(
        "/api/exams/999999/postmortem",
        json={"items": [{"question": "Soru?", "reason": "dikkatsizlik"}]},
    )
    assert resp.status_code == 404


async def test_postmortem_get_404_before_submission(client):
    _, exam_id = await _make_course_and_exam(client)
    resp = await client.get(f"/api/exams/{exam_id}/postmortem")
    assert resp.status_code == 404


async def test_postmortem_rejects_unknown_reason(client, monkeypatch):
    _, exam_id = await _make_course_and_exam(client)
    _fake_summarize(monkeypatch)
    resp = await client.post(
        f"/api/exams/{exam_id}/postmortem",
        json={"items": [{"question": "Soru?", "reason": "tembellik"}]},
    )
    assert resp.status_code == 422


async def test_other_tenant_cannot_access_postmortem(client, monkeypatch):
    """Başka kiracının sınavına muhasebe yazılamaz/okunamaz (course_id gerçek/yerel bir derse ait
    olabilir — izolasyon `exams.tenant_id` üzerinden yapılır, bkz. test_exams.py aynı kalıp)."""
    import aiosqlite

    from src.config import settings

    course_id, _ = await _make_course_and_exam(client)

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO exams (tenant_id, course_id, title, exam_date, scope_json) "
            "VALUES ('other-tenant', ?, 'Gizli Sınav', '2099-01-01', '[]')",
            (course_id,),
        )
        await conn.commit()
        foreign_exam_id = cursor.lastrowid

    _fake_summarize(monkeypatch)
    resp = await client.post(
        f"/api/exams/{foreign_exam_id}/postmortem",
        json={"items": [{"question": "Soru?", "reason": "süre_yetmedi"}]},
    )
    assert resp.status_code == 404
    assert (await client.get(f"/api/exams/{foreign_exam_id}/postmortem")).status_code == 404
