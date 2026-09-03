"""Ders CRUD testleri (Faz 1.2)."""


async def _make_term(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_courses_empty_and_create(client):
    term_id = await _make_term(client)

    resp = await client.get(f"/api/terms/{term_id}/courses")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.post(
        f"/api/terms/{term_id}/courses",
        json={
            "name": "Veri Yapıları",
            "instructor": "Dr. A. Yılmaz",
            "metadata_json": {"kredi": 5},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Veri Yapıları"
    assert body["instructor"] == "Dr. A. Yılmaz"
    assert body["metadata_json"] == {"kredi": 5}


async def test_course_crud_roundtrip(client):
    term_id = await _make_term(client)
    created = await client.post(
        f"/api/terms/{term_id}/courses", json={"name": "Algoritmalar"}
    )
    course_id = created.json()["id"]

    # get
    resp = await client.get(f"/api/courses/{course_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Algoritmalar"

    # update
    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"name": "Algoritmalar II", "instructor": "Prof. B. Kaya"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Algoritmalar II"
    assert resp.json()["instructor"] == "Prof. B. Kaya"

    # delete
    resp = await client.delete(f"/api/courses/{course_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/courses/{course_id}")
    assert resp.status_code == 404


async def test_course_errors(client):
    # var olmayan döneme ders → 404
    resp = await client.post("/api/terms/9999/courses", json={"name": "X"})
    assert resp.status_code == 404

    # boş ad → 422
    term_id = await _make_term(client)
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": ""})
    assert resp.status_code == 422

    # var olmayan ders → 404
    resp = await client.get("/api/courses/9999")
    assert resp.status_code == 404
