"""Note edit/delete uç testleri — yönerge §39 (kullanıcı emeği içeriğin yönetimi)."""

from __future__ import annotations

import pytest


async def _seed_note(client) -> dict:
    term = (await client.post("/api/terms", json={"name": "2026 Güz"})).json()
    course = (
        await client.post(f"/api/terms/{term['id']}/courses", json={"name": "Veri Yapıları"})
    ).json()
    chapter = (
        await client.post(f"/api/courses/{course['id']}/chapters", json={"title": "Ağaçlar"})
    ).json()

    from src.db import get_db
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO notes (tenant_id, chapter_id, content_md, citations_json, topics_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("local", chapter["id"], "# Başlık\n\nİçerik", "{\"topics\": []}", "[]"),
    )
    note_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return {"note_id": note_id, "chapter_id": chapter["id"]}


@pytest.mark.asyncio
async def test_not_duzenlenir(client):
    seeded = await _seed_note(client)
    resp = await client.patch(
        f"/api/notes/{seeded['note_id']}", json={"content_md": "# Düzenlendi"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_md"] == "# Düzenlendi"

    # GET ile de kalıcı olduğunu doğrula
    latest = (await client.get(f"/api/chapters/{seeded['chapter_id']}/notes")).json()
    assert latest["content_md"] == "# Düzenlendi"


@pytest.mark.asyncio
async def test_not_silinir(client):
    seeded = await _seed_note(client)
    resp = await client.delete(f"/api/notes/{seeded['note_id']}")
    assert resp.status_code == 204

    latest = (await client.get(f"/api/chapters/{seeded['chapter_id']}/notes")).json()
    assert latest is None


@pytest.mark.asyncio
async def test_yabanci_note_404(client):
    resp = await client.patch("/api/notes/999999", json={"content_md": "x"})
    assert resp.status_code == 404
    resp = await client.delete("/api/notes/999999")
    assert resp.status_code == 404
