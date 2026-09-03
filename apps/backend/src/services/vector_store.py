"""LanceDB (embedded) vektör deposu — namespace course_{id}_chunks (Yetenek 01)."""

from __future__ import annotations

import lancedb
import pyarrow as pa

from ..config import settings


def _db_path() -> str:
    return str(settings.data_dir / "lancedb")


def namespace(course_id: int) -> str:
    return f"course_{course_id}_chunks"


def upsert_chunks(course_id: int, chunks: list[dict]) -> int:
    """Chunk'ları namespace'e yazar; aynı materyalin eski chunk'larını önce siler.

    Idempotent: aynı materyal yeniden indekslendiğinde kopya oluşmaz (Yetenek 01 kabul).
    """
    if not chunks:
        return 0
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
        }
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
