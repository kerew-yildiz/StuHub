"""Hibrit retrieval — vektör + keyword (Yetenek 02 §2)."""

from __future__ import annotations

import lancedb

from ..config import settings
from .embed_service import embed_texts

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
TOP_K = 10
MAX_RESULT_CHUNKS = 24  # context taşmasını önler


def _namespace(course_id: int) -> str:
    return f"course_{course_id}_chunks"


def _keyword_score(text: str, keywords: list[str]) -> float:
    lowered = text.lower()
    return sum(lowered.count(kw.lower().strip()) for kw in keywords if kw.strip())


def hybrid_search(
    course_id: int,
    query: str,
    keywords: list[str] | None = None,
    k: int = TOP_K,
) -> list[dict]:
    """Konu için hibrit arama: 0.7·vektör(cosine) + 0.3·keyword; sayfa komşusu ekler.

    Dönüş: skorlanmış chunk'lar — [{"chunk_id", "text", "page", "slide", "score"}, ...].
    İndeks yoksa ya da boşsa boş liste.
    """
    keywords = keywords or []
    db = lancedb.connect(str(settings.data_dir / "lancedb"))
    ns = _namespace(course_id)
    if ns not in (db.list_tables().tables or []):
        return []
    table = db.open_table(ns)
    rows = table.to_arrow().to_pylist()
    if not rows:
        return []

    query_vec = embed_texts([query])[0]  # L2 normalize — dot product = cosine

    scored: list[dict] = []
    for row in rows:
        vec = row["vector"]
        dot = sum(a * b for a, b in zip(query_vec, vec, strict=False))
        kw = _keyword_score(row["text"], keywords)
        combined = VECTOR_WEIGHT * dot + KEYWORD_WEIGHT * kw
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "material_id": row["material_id"],
                "text": row["text"],
                "page": row["page"],
                "slide": row["slide"],
                "score": combined,
            }
        )
    scored.sort(key=lambda r: r["score"], reverse=True)
    top = scored[:k]

    # Sayfa/slide komşuluğu: bağlam bütünlüğü için aynı sayfadaki diğer chunk'ları ekle
    pages = {r["page"] for r in top if r["page"] is not None}
    slides = {r["slide"] for r in top if r["slide"] is not None}
    existing = {r["chunk_id"] for r in top}
    merged = list(top)
    for row in scored:
        if len(merged) >= MAX_RESULT_CHUNKS:
            break
        if row["chunk_id"] in existing:
            continue
        if (row["page"] in pages or row["slide"] in slides) and row["score"] > 0:
            merged.append(row)
            existing.add(row["chunk_id"])

    return merged
