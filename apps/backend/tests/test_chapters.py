"""Chapter minimal CRUD testleri (Faz 1.3 temeli)."""


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def test_chapter_create_list_delete(client):
    course_id = await _make_course(client)

    resp = await client.get(f"/api/courses/{course_id}/chapters")
    assert resp.status_code == 200
    assert resp.json() == []

    created = await client.post(
        f"/api/courses/{course_id}/chapters", json={"title": "Giriş"}
    )
    assert created.status_code == 201
    chapter_id = created.json()["id"]
    assert created.json()["title"] == "Giriş"

    resp = await client.get(f"/api/courses/{course_id}/chapters")
    assert [c["title"] for c in resp.json()] == ["Giriş"]

    resp = await client.delete(f"/api/chapters/{chapter_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/courses/{course_id}/chapters")
    assert resp.json() == []


async def test_chapter_errors(client):
    # var olmayan derse chapter → 404
    resp = await client.post("/api/courses/9999/chapters", json={"title": "X"})
    assert resp.status_code == 404

    # boş başlık → 422
    course_id = await _make_course(client)
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": ""})
    assert resp.status_code == 422
