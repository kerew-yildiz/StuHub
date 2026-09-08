"""`/api/citations/{chunk_id}` testleri — kiracı izolasyonu ve biçim doğrulaması.

Bu uç eskiden TÜM kiracıların tüm LanceDB tablolarını tarayıp eşleşen ilk chunk'ı
döndürüyordu; yani kimliği doğrulanmış herhangi bir kullanıcı, chunk_id bilerek
başka bir kiracının materyal metnini okuyabiliyordu. Testler hem sızıntının
kapandığını hem de meşru akışın çalışmaya devam ettiğini doğrular.
"""

import aiosqlite
import pytest

from src.config import settings
from src.services import retrieval, vector_store

DIM = 4


def _chunk(course_id: int, material_id: int) -> list[dict]:
    return [
        {
            "chunk_id": f"chk_{material_id}_1_1",
            "course_id": course_id,
            "material_id": material_id,
            "page": 1,
            "slide": None,
            "text": "Gizli kalması gereken ders materyali metni.",
            "vector": [0.5] * DIM,
        }
    ]


async def _insert_material(course_id: int, tenant_id: str) -> int:
    """Materyal satırını doğrudan ekler (yükleme ucunu atlar) ve kimliğini döner."""
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO materials (tenant_id, course_id, type, filepath) VALUES (?, ?, ?, ?)",
            (tenant_id, course_id, "textbook", "/tmp/yok.pdf"),
        )
        await db.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid


async def _make_course(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    return resp.json()["id"]


async def test_citation_resolves_for_owning_tenant(client):
    """Kendi materyaline ait chunk normal şekilde çözülür."""
    course_id = await _make_course(client)
    material_id = await _insert_material(course_id, "local")
    vector_store.upsert_chunks(course_id, _chunk(course_id, material_id))

    resp = await client.get(f"/api/citations/chk_{material_id}_1_1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunk_id"] == f"chk_{material_id}_1_1"
    assert body["material_id"] == material_id
    assert body["page"] == 1
    assert "Gizli kalması gereken" in body["text"]


async def test_citation_of_other_tenant_is_not_readable(client):
    """Başka kiracıya ait materyalin chunk'ı — LanceDB'de var olsa bile 404.

    Sızıntının regresyon testi: chunk fiziksel olarak yazılmıştır ve eski kod onu
    tabloları tarayarak bulup döndürürdü.
    """
    course_id = await _make_course(client)
    material_id = await _insert_material(course_id, "baska-kiraci")
    vector_store.upsert_chunks(course_id, _chunk(course_id, material_id))

    resp = await client.get(f"/api/citations/chk_{material_id}_1_1")
    assert resp.status_code == 404
    # Varlık bilgisi de sızmamalı — sahibi olmayan ve hiç olmayan kimlik aynı yanıtı alır.
    assert "Gizli kalması gereken" not in resp.text


async def test_unknown_material_returns_404(client):
    await _make_course(client)
    resp = await client.get("/api/citations/chk_99999_1_1")
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "chunk_id",
    [
        "bozuk",
        "chk_abc_1_1",
        "chk_1_1_1' OR '1'='1",  # filtre ifadesine enjeksiyon denemesi
        "chk_1_1",
    ],
)
async def test_malformed_chunk_id_rejected(client, chunk_id):
    """Biçim doğrulaması, LanceDB filtre ifadesine enjeksiyonu da kapatır."""
    await _make_course(client)
    resp = await client.get(f"/api/citations/{chunk_id}")
    assert resp.status_code == 404


def test_parse_material_id_accepts_all_chunk_formats():
    """chunking.py'nin ürettiği üç biçim de tanınmalı (sayfa / slide / segment)."""
    assert retrieval.parse_material_id("chk_7_12_1") == 7
    assert retrieval.parse_material_id("chk_7_s3_2") == 7
    assert retrieval.parse_material_id("chk_7_t5_1") == 7
    assert retrieval.parse_material_id("chk_x_1_1") is None
    assert retrieval.parse_material_id("chk_7_1_1; DROP TABLE") is None
