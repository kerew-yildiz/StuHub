"""Görsel OCR — rapidocr-onnxruntime (tembel import, Yetenek 11)."""

from __future__ import annotations

from pathlib import Path

from src.config import settings
from src.services.media_extractors import split_text_segments

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def extract(path: str) -> list[dict]:
    """Görüntüyü OCR'lar; satırları birleştirip ~1500 karakterlik segmentlere böler."""
    if not settings.ocr_enabled:
        raise RuntimeError("OCR kapalı — ayarlardan açın.")
    if not Path(path).exists():
        raise ValueError(f"Görsel bulunamadı: {path}")
    ext = Path(path).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise ValueError(f"Desteklenmeyen görsel türü: {ext or 'yok'}")

    from rapidocr_onnxruntime import RapidOCR

    try:
        engine = RapidOCR()
        result, _elapse = engine(path)
    except Exception as exc:
        raise RuntimeError("Görüntüden metin çıkarılamadı.") from exc

    lines: list[str] = []
    for item in result or []:
        text = item[1] if len(item) > 1 else ""
        if text and str(text).strip():
            lines.append(str(text).strip())

    full_text = "\n".join(lines).strip()
    if not full_text:
        raise RuntimeError("Görüntüden metin çıkarılamadı.")
    parts = split_text_segments(full_text)
    return [
        {"segment": i, "text": part, "start": None, "end": None}
        for i, part in enumerate(parts)
    ]
