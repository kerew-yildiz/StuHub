"""YouTube altyazı/transkript çıkarımı — yt-dlp + faster-whisper fallback (Yetenek 11)."""

from __future__ import annotations

import html
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.config import settings

_CUE_RE = re.compile(
    r"((?:\d{1,2}:)?\d{1,2}:\d{1,2}[.,]\d{1,3})\s*-->\s*"
    r"((?:\d{1,2}:)?\d{1,2}:\d{1,2}[.,]\d{1,3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_AUDIO_EXTS = {".webm", ".m4a", ".mp3", ".opus", ".mp4", ".ogg", ".aac", ".flac", ".wav"}


def _timestamp_to_seconds(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    return float(parts[0])


def _clean_caption_text(text: str) -> str:
    text = _VTT_TAG_RE.sub("", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _parse_captions(raw: str) -> list[dict]:
    """VTT/SRT metnini zaman damgalı segmentlere çevirir."""
    segments: list[dict] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = _CUE_RE.search(line)
        if match:
            start = _timestamp_to_seconds(match.group(1))
            end = _timestamp_to_seconds(match.group(2))
            text_lines: list[str] = []
            i += 1
            while i < len(lines):
                current = lines[i].strip()
                if not current or _CUE_RE.search(current):
                    break
                text_lines.append(current)
                i += 1
            text = _clean_caption_text(" ".join(text_lines))
            if text:
                segments.append(
                    {"segment": len(segments), "text": text, "start": start, "end": end}
                )
        else:
            i += 1
    return segments


def _download_caption(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Geçersiz altyazı adresi")
    with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310 — yalnızca http(s)
        return response.read().decode("utf-8", errors="replace")


def _try_download_caption(url: str) -> str | None:
    try:
        return _download_caption(url)
    except Exception:
        return None


def _extract_info(url: str) -> dict:
    import yt_dlp

    params: Any = {"skip_download": True, "quiet": True, "no_warnings": True}
    try:
        info = yt_dlp.YoutubeDL(params).extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError("Video bilgisi alınamadı; URL'yi kontrol edin.") from exc
    return dict(info) if isinstance(info, dict) else {}


def _try_captions(info: dict) -> list[dict]:
    """tr→en kademeli, önce manuel altyazı sonra otomatik altyazı dener."""
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    for lang in ("tr", "en"):
        for source in (subtitles, automatic):
            for entry in source.get(lang) or []:
                caption_url = entry.get("url") if isinstance(entry, dict) else None
                if not caption_url:
                    continue
                raw = _try_download_caption(caption_url)
                if raw is None:
                    continue
                segments = _parse_captions(raw)
                if segments:
                    return segments
    return []


def _find_audio_file(tmp_dir: str) -> str | None:
    for child in Path(tmp_dir).iterdir():
        if child.is_file() and child.suffix.lower() in _AUDIO_EXTS:
            return str(child)
    return None


def _whisper_transcribe(url: str) -> list[dict]:
    import yt_dlp

    tmp_dir = tempfile.mkdtemp(prefix="stuhub_yt_")
    try:
        try:
            yt_dlp.YoutubeDL(
                {
                    "format": "bestaudio/best",
                    "outtmpl": str(Path(tmp_dir) / "audio.%(ext)s"),
                    "quiet": True,
                }
            ).download([url])
        except Exception as exc:
            raise RuntimeError("Ses indirilemedi; video kaldırılmış olabilir.") from exc

        audio_path = _find_audio_file(tmp_dir)
        if audio_path is None:
            raise RuntimeError("Bu video için altyazı/transkript alınamadı.")

        try:
            import faster_whisper

            model = faster_whisper.WhisperModel(
                settings.whisper_model, device="cpu", compute_type="int8"
            )
            segments_iter, _info = model.transcribe(audio_path)
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
            raise RuntimeError("Bu video için altyazı/transkript alınamadı.") from exc

        segments = [seg for seg in segments if seg["text"]]
        if not segments:
            raise RuntimeError("Bu video için altyazı/transkript alınamadı.")
        return segments
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def extract(url: str) -> list[dict]:
    """Önce tr→en altyazı dener; yoksa sesi indirip yerel transkripsiyon yapar."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("YouTube URL'si http(s) ile başlamalı.")

    info = _extract_info(url)
    caption_segments = _try_captions(info)
    if caption_segments:
        return caption_segments
    return _whisper_transcribe(url)
