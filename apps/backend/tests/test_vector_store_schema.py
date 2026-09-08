"""LanceDB açık şema regresyon testleri — kitap/sunum chunk'ları aynı tabloda yaşar.

Korunan bug: şema tip çıkarımına bırakıldığında tabloyu ilk yazan materyal türü
diğerinin kolonunu `null` tipinde oluşturuyordu (kitap `page=<int>, slide=None`,
sunum `page=None, slide=<int>`), ikinci yazma
`ValueError: Invalid input, cannot cast field 'page' from Int64 to Null` ile patlıyordu.
Embedding modeli çağrılmaz; vektörler elle verilir.
"""

import lancedb
import pyarrow as pa

from src.config import settings
from src.services import vector_store

DIM = 4


def _slide_chunks(course_id: int, material_id: int, count: int = 2) -> list[dict]:
    """Sunum chunk'ları: `page` boş, `slide` dolu."""
    return [
        {
            "chunk_id": f"chk_{material_id}_s{i}",
            "course_id": course_id,
            "material_id": material_id,
            "page": None,
            "slide": i,
            "text": f"Sunum slaytı {i} içeriği.",
            "vector": [0.1 * i] * DIM,
        }
        for i in range(1, count + 1)
    ]


def _page_chunks(course_id: int, material_id: int, count: int = 3) -> list[dict]:
    """Kitap chunk'ları: `slide` boş, `page` dolu."""
    return [
        {
            "chunk_id": f"chk_{material_id}_p{i}",
            "course_id": course_id,
            "material_id": material_id,
            "page": 4 + i,
            "slide": None,
            "text": f"Kitap sayfası {4 + i} içeriği.",
            "vector": [0.2 * i] * DIM,
        }
        for i in range(1, count + 1)
    ]


def _table(course_id: int):
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    return db.open_table(vector_store.namespace(course_id))


def test_slides_then_pages_same_course(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    course_id = 1

    assert vector_store.upsert_chunks(course_id, _slide_chunks(course_id, 10)) == 2
    # ikinci yazma eskiden burada ValueError ile patlıyordu
    assert vector_store.upsert_chunks(course_id, _page_chunks(course_id, 11)) == 3

    rows = _table(course_id).to_arrow().to_pylist()
    assert len(rows) == 5
    slides = sorted(r["slide"] for r in rows if r["material_id"] == 10)
    pages = sorted(r["page"] for r in rows if r["material_id"] == 11)
    assert slides == [1, 2]
    assert pages == [5, 6, 7]
    assert all(r["page"] is None for r in rows if r["material_id"] == 10)
    assert all(r["slide"] is None for r in rows if r["material_id"] == 11)


def test_pages_then_slides_same_course(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    course_id = 2

    assert vector_store.upsert_chunks(course_id, _page_chunks(course_id, 20)) == 3
    assert vector_store.upsert_chunks(course_id, _slide_chunks(course_id, 21)) == 2

    rows = _table(course_id).to_arrow().to_pylist()
    assert len(rows) == 5
    assert sorted(r["page"] for r in rows if r["material_id"] == 20) == [5, 6, 7]
    assert sorted(r["slide"] for r in rows if r["material_id"] == 21) == [1, 2]


def test_schema_types_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    course_id = 3

    vector_store.upsert_chunks(course_id, _slide_chunks(course_id, 30))
    schema = _table(course_id).schema

    assert schema.field("page").type == pa.int64()
    assert schema.field("slide").type == pa.int64()
    vector_type = schema.field("vector").type
    assert pa.types.is_fixed_size_list(vector_type)
    assert vector_type.list_size == DIM
    assert vector_type.value_type == pa.float32()


def test_dim_mismatch_raises_clear_error(tmp_path, monkeypatch):
    """Embedding modeli değişip boyut uyuşmazsa sessizce bozulmak yerine net hata.

    Üretimde `STUHUB_EMBED_MODEL` ayarlanmazsa kod varsayılanı (bge-m3, 1024 boyut)
    devreye girer ve MiniLM (384 boyut) ile kurulmuş indeksle çakışır.
    """
    import pytest

    from src.config import settings
    from src.services import vector_store

    monkeypatch.setattr(settings, "data_dir", tmp_path)

    def _chunks(dim: int) -> list[dict]:
        return [
            {
                "chunk_id": "chk_1_1_1",
                "course_id": 1,
                "material_id": 1,
                "page": 1,
                "slide": None,
                "text": "metin",
                "vector": [0.1] * dim,
            }
        ]

    vector_store.upsert_chunks(1, _chunks(384))
    assert vector_store.existing_vector_dim(1) == 384

    with pytest.raises(vector_store.VectorDimMismatch, match="STUHUB_EMBED_MODEL"):
        vector_store.upsert_chunks(1, _chunks(1024))
