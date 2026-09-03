"""Medya çıkarım paketi — youtube/audio/docx/epub/image/text (Yetenek 11).

Ağır araçlar (yt-dlp, faster-whisper, rapidocr, python-docx) yalnızca ilgili
extractor çalıştığında, fonksiyon içinde içe aktarılır; böylece bir aracın
kurulu olmaması diğer özellikleri engellemez (tembel import).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

# Doküman/text segmentleri için hedef karakter sayısı (~1500).
SEGMENT_CHARS = 1500


def _last_whitespace(text: str) -> int:
    """Metnin son boşluk karakterinin indeksini döner; yoksa -1."""
    for i in range(len(text) - 1, -1, -1):
        if text[i].isspace():
            return i
    return -1


def split_text_segments(text: str, max_chars: int = SEGMENT_CHARS) -> list[str]:
    """Metni kelime sınırında yaklaşık max_chars karakterlik parçalara böler."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    current = text
    while len(current) > max_chars:
        head = current[:max_chars]
        cut = _last_whitespace(head)
        if cut <= 0:
            # Sınır yok (uzun kesintisiz belirteç): sert böl.
            parts.append(head.strip())
            current = current[max_chars:].lstrip()
        else:
            parts.append(head[:cut].strip())
            current = current[cut:].lstrip()
    if current:
        parts.append(current.strip())
    return parts


def _format_timestamp(seconds: float) -> str:
    """Saniyeyi "mm:ss" biçimine çevirir."""
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def transcript_to_text(segments: list[dict]) -> str:
    """Segmentleri düz metne birleştirir; zaman damgalıysa "[mm:ss] metin"."""
    lines: list[str] = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = seg.get("start")
        if start is not None:
            lines.append(f"[{_format_timestamp(float(start))}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _lazy(module_name: str) -> Callable[[str], list[dict]]:
    """İlk çağrıda modülü içe aktarır; extract fonksiyonunu önbelleğe alır."""
    cached: list[Callable[[str], list[dict]]] = []

    def _call(source: str) -> list[dict]:
        if not cached:
            module = importlib.import_module(module_name)
            cached.append(module.extract)  # type: ignore[attr-defined]
        return cached[0](source)

    return _call


EXTRACTORS: dict[str, Callable[[str], list[dict]]] = {
    "youtube": _lazy("src.services.media_extractors.youtube"),
    "audio": _lazy("src.services.media_extractors.audio"),
    "docx": _lazy("src.services.media_extractors.docx"),
    "epub": _lazy("src.services.media_extractors.epub"),
    "image": _lazy("src.services.media_extractors.ocr"),
    "text": _lazy("src.services.media_extractors.text"),
}


def extract_for(mtype: str, source: str) -> list[dict]:
    """Türe göre doğru extractor'ı seçip çalıştırır; bilinmeyen tür → ValueError."""
    extract = EXTRACTORS.get(mtype)
    if extract is None:
        raise ValueError(f"Bilinmeyen materyal türü: {mtype}")
    return extract(source)
