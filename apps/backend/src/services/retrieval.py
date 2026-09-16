"""Hibrit retrieval — vektör + keyword (Yetenek 02 §2)."""

from __future__ import annotations

import re

try:
    import lancedb
except (ImportError, OSError):
    # Windows Uygulama Denetimi (Smart App Control) pyarrow DLL'ini engelleyebilir —
    # bu durumda backend vektör arama olmadan (yalnızca keyword retrieval) çalışır.
    lancedb = None  # type: ignore[assignment]
import numpy as np

from ..config import settings
from . import embed_service, vector_store

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
TOP_K = 10
MAX_RESULT_CHUNKS = 24  # context taşmasını önler

# Bağlantı, yolu değişmediği sürece süreç ömrü boyunca tek sefer açılır — `lancedb.connect`
# her çağrıda dizin manifestini yeniden okuyordu; not üretimi tek chapter için 10+ kez
# `hybrid_search` çağırdığından bu, ölçülebilir (LLM'siz) bir gecikmeydi (2026-09-05 perf
# turu). Yol anahtarlanır ki testlerdeki `settings.data_dir` monkeypatch'i her test için
# taze bağlantı alsın (aksi halde önceki testin dizinine bağlı kalır).
_db: lancedb.DBConnection | None = None
_db_path: str | None = None


def _connect() -> lancedb.DBConnection:
    global _db, _db_path
    if lancedb is None:
        raise RuntimeError(
            "lancedb/pyarrow yüklenemedi — vektör arama bu ortamda kullanılamıyor"
        )
    path = str(settings.data_dir / "lancedb")
    if _db is None or _db_path != path:
        _db = lancedb.connect(path)
        _db_path = path
    return _db


def _namespace(course_id: int) -> str:
    return f"course_{course_id}_chunks"


# chunk_id biçimleri (services/chunking.py): chk_<mat>_<sayfa>_<seq>,
# chk_<mat>_s<slide>_<seq>, chk_<mat>_t<segment>_<seq>.
_CHUNK_ID_RE = re.compile(r"^chk_(\d+)_[st]?\d+_\d+$")


def parse_material_id(chunk_id: str) -> int | None:
    """`chunk_id`'den materyal kimliğini çıkarır; biçim tanınmazsa None döner.

    Biçim doğrulaması aynı zamanda `get_chunk`'ın LanceDB filtre ifadesine
    enjeksiyonu engeller: yalnızca `chk_<sayı>_[st]<sayı>_<sayı>` kabul edilir,
    yani tırnak/boşluk gibi ifadeyi kırabilecek karakterler hiç geçemez.
    """
    match = _CHUNK_ID_RE.match(chunk_id)
    return int(match.group(1)) if match else None


def get_chunk(course_id: int, chunk_id: str) -> dict | None:
    """Tek bir chunk'ı kimliğiyle döner (atıf pop-up'ı); bulunamazsa None.

    Yalnızca ilgili dersin namespace'ine bakar ve filtreyi LanceDB'ye devreder —
    eskiden bu arama TÜM kiracıların tüm tablolarını belleğe yükleyip lineer
    tarıyordu (hem kiracılar arası sızıntı hem O(tüm korpus) maliyet).
    Çağırmadan ÖNCE `parse_material_id` ile biçim doğrulanmış olmalıdır.
    """
    db = _connect()
    ns = _namespace(course_id)
    if ns not in (db.list_tables().tables or []):
        return None
    rows = db.open_table(ns).search().where(f"chunk_id = '{chunk_id}'").limit(1).to_list()
    if not rows:
        return None
    row = rows[0]
    return {
        "chunk_id": row["chunk_id"],
        "course_id": row["course_id"],
        "material_id": row["material_id"],
        "text": row["text"],
        "page": row["page"],
        "slide": row["slide"],
    }


def _keyword_score(text: str, keywords: list[str]) -> float:
    lowered = text.lower()
    return sum(lowered.count(kw.lower().strip()) for kw in keywords if kw.strip())


def _lexical_scores(query: str, rows: list[dict]) -> list[float]:
    """Embedding yokken yedek skor: sorgu terimlerinin chunk metninde sıklığı.

    Windows Uygulama Denetimi sentence-transformers'ın `regex` DLL'ini
    engelleyebiliyor; bu ortamda vektör arama üretilemez ama LanceDB'deki
    chunk metinlerine lexikal erişim çalışır. BM25'in kaba bir yedeği:
    terim frekansı toplamı, 3+ harfli terimlerle (dur kelimeleri elenir).
    """
    terms = [t for t in re.split(r"\W+", query.lower(), flags=re.UNICODE) if len(t) > 2]
    scores: list[float] = []
    for row in rows:
        lowered = row["text"].lower()
        scores.append(float(sum(lowered.count(t) for t in terms)))
    return scores


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
    db = _connect()
    ns = _namespace(course_id)
    if ns not in (db.list_tables().tables or []):
        return []
    table = db.open_table(ns)
    rows = table.to_arrow().to_pylist()
    if not rows:
        return []

    try:
        query_embedding = embed_service.embed_texts([query])[0]
    except embed_service.EmbedError:
        # Embedding modeli bu ortamda yüklenemiyor (ör. Windows Uygulama Denetimi
        # `regex` DLL'ini engelliyor). Chat/not üretimi tamamen çökmesin: lexikal
        # yedeğe düş — vektör katkısı olmadan, yalnızca terim frekansıyla sırala.
        query_embedding = None

    scored: list[dict] = []
    if query_embedding is None:
        lex = _lexical_scores(query, rows)
        for row, lex_score in zip(rows, lex, strict=True):
            kw = _keyword_score(row["text"], keywords)
            scored.append(
                {
                    "chunk_id": row["chunk_id"],
                    "material_id": row["material_id"],
                    "text": row["text"],
                    "page": row["page"],
                    "slide": row["slide"],
                    "score": lex_score + kw,
                }
            )
    else:
        indexed_dim = len(rows[0]["vector"])
        if indexed_dim != len(query_embedding):
            # Embedding modeli indeks kurulduktan sonra değişmiş (bkz. vector_store
            # `VectorDimMismatch`). Ham bir numpy boyut hatası yerine anlaşılır mesaj.
            raise vector_store.VectorDimMismatch(
                f"Ders {course_id} indeksi {indexed_dim} boyutlu, şu anki embedding "
                f"modeli {len(query_embedding)} boyut üretiyor — STUHUB_EMBED_MODEL ayarını "
                "indeksin kurulduğu modelle eşleyin ya da materyalleri yeniden indeksleyin."
            )

        query_vec = np.asarray(query_embedding, dtype=np.float32)
        vectors = np.asarray([row["vector"] for row in rows], dtype=np.float32)
        dots = vectors @ query_vec  # cosine (vektörler zaten normalize) — tek BLAS çağrısı

        for row, dot in zip(rows, dots, strict=True):
            kw = _keyword_score(row["text"], keywords)
            combined = VECTOR_WEIGHT * float(dot) + KEYWORD_WEIGHT * kw
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
