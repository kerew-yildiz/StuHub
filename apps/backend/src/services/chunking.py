"""Chunking — sayfa/slide bazlı, ~1200 token hedefi, ~100 token overlap (Yetenek 01).

Token tahmini: Türkçe/İngilizce için ~4 karakter ≈ 1 token (basit, deterministik).
"""

from __future__ import annotations

import re

TOKEN_CHARS = 4
TARGET_TOKENS = 1200
OVERLAP_TOKENS = 100
TARGET_CHARS = TARGET_TOKENS * TOKEN_CHARS
OVERLAP_CHARS = OVERLAP_TOKENS * TOKEN_CHARS

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")


def _split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Uzun metni cümle sınırlarında böler; parçalar arası overlap uygular."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current = text
    while len(current) > max_chars:
        head = current[:max_chars]
        matches = list(_SENTENCE_BOUNDARY.finditer(head))
        cut = matches[-1].end() if matches else max_chars
        parts.append(head[:cut].strip())
        tail = head[max(cut - overlap_chars, 0) : cut] if cut > 0 else ""
        current = (tail + current[cut:]).strip()
    if current:
        parts.append(current)
    return parts


def chunk_pdf_pages(course_id: int, material_id: int, pages: list[dict]) -> list[dict]:
    """Sayfa bazlı chunk üretir; uzun sayfalar bölünür.

    chunk_id: chk_<material_id>_<page>_<seq> (Yetenek 01 formatı).
    """
    chunks: list[dict] = []
    for page_data in pages:
        page_no = page_data["page"]
        text = page_data["text"].strip()
        if not text:
            continue  # boş/taranmış sayfa: temsil edilemez, atla
        parts = _split_long_text(text, TARGET_CHARS, OVERLAP_CHARS)
        for seq, part in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": f"chk_{material_id}_{page_no}_{seq}",
                    "course_id": course_id,
                    "material_id": material_id,
                    "page": page_no,
                    "slide": None,
                    "text": part,
                }
            )
    return chunks


def chunk_slides(course_id: int, material_id: int, slides: list[dict]) -> list[dict]:
    """Slide bazlı chunk üretir (bir slide = en az bir chunk; uzun slide bölünür).

    chunk_id: chk_<material_id>_s<slide>_<seq> (slide'ı sayfadan ayırt eder).
    """
    chunks: list[dict] = []
    for slide_data in slides:
        slide_no = slide_data["slide"]
        text = slide_data["text"].strip()
        if not text:
            continue
        parts = _split_long_text(text, TARGET_CHARS, OVERLAP_CHARS)
        for seq, part in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": f"chk_{material_id}_s{slide_no}_{seq}",
                    "course_id": course_id,
                    "material_id": material_id,
                    "page": None,
                    "slide": slide_no,
                    "text": part,
                }
            )
    return chunks


def _format_timestamp(seconds: float) -> str:
    """Saniyeyi "mm:ss" biçimine çevirir (transkript öneki)."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def chunk_segments(course_id: int, material_id: int, segments: list[dict]) -> list[dict]:
    """Medya/transkript segmentlerini chunk'a çevirir (v2 — Yetenek 11).

    `page`/`slide` boş bırakılır (kaynak etiketi "Kaynak N"); zaman damgalı
    metinler "[mm:ss] " önekiyle saklanır. chunk_id: chk_<mat>_t<segment>_<seq>.
    """
    chunks: list[dict] = []
    for seg in segments:
        index = seg["segment"]
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = seg.get("start")
        prefix = f"[{_format_timestamp(float(start))}] " if start is not None else ""
        parts = _split_long_text(text, TARGET_CHARS, OVERLAP_CHARS)
        for seq, part in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": f"chk_{material_id}_t{index}_{seq}",
                    "course_id": course_id,
                    "material_id": material_id,
                    "page": None,
                    "slide": None,
                    "text": f"{prefix}{part}",
                }
            )
    return chunks
