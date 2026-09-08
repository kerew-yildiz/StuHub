"""LanceDB (embedded) vektör deposu — namespace course_{id}_chunks (Yetenek 01)."""

from __future__ import annotations

import lancedb
import pyarrow as pa

from ..config import settings


def _db_path() -> str:
    return str(settings.data_dir / "lancedb")


def namespace(course_id: int) -> str:
    return f"course_{course_id}_chunks"


def _schema(vector_dim: int) -> pa.Schema:
    """Açık şema — tip çıkarımı yapılmaz.

    Kritik: `page` yalnızca kitap chunk'larında, `slide` yalnızca sunum chunk'larında
    doludur. Tip çıkarımına bırakılırsa tabloyu ilk yazan materyal türü diğerinin
    kolonunu `null` tipinde oluşturur ve sonraki yazma
    "cannot cast field 'page' from Int64 to Null" ile patlar.
    """
    return pa.schema(
        [
            ("chunk_id", pa.string()),
            ("course_id", pa.int64()),
            ("material_id", pa.int64()),
            ("page", pa.int64()),
            ("slide", pa.int64()),
            ("text", pa.string()),
            ("vector", pa.list_(pa.float32(), vector_dim)),
        ]
    )


class VectorDimMismatch(RuntimeError):
    """İndeksin boyutu ile üretilen vektörün boyutu uyuşmuyor.

    Pratikte tek sebebi vardır: embedding modeli, indeks kurulduktan SONRA değişti
    (ör. üretimde `STUHUB_EMBED_MODEL` ayarlanmadı ve kod varsayılanı `BAAI/bge-m3`
    (1024 boyut) devreye girdi, oysa indeks MiniLM-L12-v2 (384 boyut) ile kurulmuştu).
    Sessizce devam etmek retrieval'ı bozar; bu yüzden net bir hatayla durulur.
    """


def existing_vector_dim(course_id: int) -> int | None:
    """Mevcut indeksin vektör boyutu; indeks yoksa None."""
    db = lancedb.connect(_db_path())
    ns = namespace(course_id)
    if ns not in (db.list_tables().tables or []):
        return None
    field = db.open_table(ns).schema.field("vector")
    return getattr(field.type, "list_size", None)


def _assert_dim_matches(course_id: int, vector_dim: int) -> None:
    existing = existing_vector_dim(course_id)
    if existing is not None and existing != vector_dim:
        raise VectorDimMismatch(
            f"Ders {course_id} indeksi {existing} boyutlu vektörlerle kurulmuş, "
            f"şu anki embedding modeli {vector_dim} boyut üretiyor. "
            "STUHUB_EMBED_MODEL ayarı indeksin kurulduğu modelle aynı olmalı; "
            "model bilerek değiştirildiyse bu dersin materyalleri yeniden indekslenmeli."
        )


def upsert_chunks(course_id: int, chunks: list[dict]) -> int:
    """Chunk'ları namespace'e yazar; aynı materyalin eski chunk'larını önce siler.

    Idempotent: aynı materyal yeniden indekslendiğinde kopya oluşmaz (Yetenek 01 kabul).
    """
    if not chunks:
        return 0
    _assert_dim_matches(course_id, len(chunks[0]["vector"]))
    db = lancedb.connect(_db_path())
    ns = namespace(course_id)
    data = pa.table(
        {
            "chunk_id": [c["chunk_id"] for c in chunks],
            "course_id": [c["course_id"] for c in chunks],
            "material_id": [c["material_id"] for c in chunks],
            "page": [c["page"] for c in chunks],
            "slide": [c["slide"] for c in chunks],
            "text": [c["text"] for c in chunks],
            "vector": [c["vector"] for c in chunks],
        },
        schema=_schema(len(chunks[0]["vector"])),
    )
    if ns in (db.list_tables().tables or []):
        table = db.open_table(ns)
        material_ids = {c["material_id"] for c in chunks}
        for material_id in material_ids:
            table.delete(f"material_id = {material_id}")
        table.add(data)
    else:
        db.create_table(ns, data=data)
    return len(chunks)


def delete_material_chunks(course_id: int, material_id: int) -> None:
    """Bir materyalin tüm chunk'larını siler (materyal silindiğinde çağrılır)."""
    db = lancedb.connect(_db_path())
    ns = namespace(course_id)
    if ns in (db.list_tables().tables or []):
        db.open_table(ns).delete(f"material_id = {material_id}")
