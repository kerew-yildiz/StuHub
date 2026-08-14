"""Ses kaydı transkripsiyonu — faster-whisper (tembel import, Yetenek 11)."""

from __future__ import annotations

from pathlib import Path

from src.config import settings


def extract(path: str) -> list[dict]:
    """Ses dosyasını yerel STT ile metne çevirir; segmentler start/end taşır."""
    if not Path(path).exists():
        raise ValueError(f"Ses dosyası bulunamadı: {path}")

    import faster_whisper

    try:
        model = faster_whisper.WhisperModel(
            settings.whisper_model, device="cpu", compute_type="int8"
        )
        segments_iter, _info = model.transcribe(path)
        segments = [
            {
                "segment": i,
                "text": seg.text.strip(),
                "start": float(seg.start),
                "end": float(seg.end),
            }
            for i, seg in enumerate(segments_iter)
        ]
    except Exception as exc:
        raise RuntimeError("Ses kaydından metin çıkarılamadı.") from exc

    segments = [seg for seg in segments if seg["text"]]
    if not segments:
        raise RuntimeError("Ses kaydından metin çıkarılamadı.")
    return segments
