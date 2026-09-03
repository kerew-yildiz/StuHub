"""Düz metin (yapıştırma) çıkarımı — araç gerektirmez (Yetenek 11)."""

from __future__ import annotations

from src.services.media_extractors import split_text_segments


def extract(text: str) -> list[dict]:
    """Yapıştırılan ham metni ~1500 karakterlik segmentlere böler."""
    if not text or not text.strip():
        raise RuntimeError("Yapıştırılan metin boş.")
    parts = split_text_segments(text)
    return [
        {"segment": i, "text": part, "start": None, "end": None}
        for i, part in enumerate(parts)
    ]
