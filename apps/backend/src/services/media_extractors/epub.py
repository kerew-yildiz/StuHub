"""EPUB metin çıkarımı — yalnız stdlib (zipfile + XHTML), Yetenek 11.

AGPL-3.0 lisanslı ebooklib bilinçli olarak kullanılmaz (lisans politikası).
"""

from __future__ import annotations

import html
import posixpath
import re
import zipfile
from pathlib import Path

from src.services.media_extractors import split_text_segments

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
_WS_RE = re.compile(r"\s+")
_HTML_EXTS = (".xhtml", ".html", ".htm")


def _find_opf(zf: zipfile.ZipFile) -> str:
    try:
        container = zf.read("META-INF/container.xml").decode("utf-8", errors="replace")
    except KeyError as exc:
        raise RuntimeError("EPUB geçersiz: container.xml bulunamadı.") from exc
    match = re.search(r'full-path\s*=\s*["\']([^"\']+)["\']', container)
    if match:
        return match.group(1)
    for name in zf.namelist():
        if name.lower().endswith(".opf"):
            return name
    raise RuntimeError("EPUB geçersiz: .opf dosyası bulunamadı.")


def _manifest_text_paths(zf: zipfile.ZipFile, opf_path: str) -> list[str]:
    opf = zf.read(opf_path).decode("utf-8", errors="replace")
    base = posixpath.dirname(opf_path)
    paths: list[str] = []
    for item in re.finditer(r"<item\b[^>]*>", opf):
        href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', item.group(0))
        if not href_match:
            continue
        href = html.unescape(href_match.group(1)).split("#")[0]
        if not href.lower().endswith(_HTML_EXTS):
            continue
        paths.append(posixpath.normpath(posixpath.join(base, href)))
    return paths


def _read_entry(zf: zipfile.ZipFile, path: str) -> str | None:
    names = zf.namelist()
    if path in names:
        return zf.read(path).decode("utf-8", errors="replace")
    base = posixpath.basename(path).lower()
    for name in names:
        if posixpath.basename(name).lower() == base:
            return zf.read(name).decode("utf-8", errors="replace")
    return None


def _strip_html(raw: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", raw)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def extract(path: str) -> list[dict]:
    """EPUB içindeki XHTML dosyalarını sırayla okuyup metne çevirir."""
    if not Path(path).exists():
        raise ValueError(f"EPUB dosyası bulunamadı: {path}")
    try:
        with zipfile.ZipFile(path) as zf:
            opf = _find_opf(zf)
            text_blocks: list[str] = []
            for entry_path in _manifest_text_paths(zf, opf):
                raw = _read_entry(zf, entry_path)
                if raw is None:
                    continue
                text = _strip_html(raw)
                if text:
                    text_blocks.append(text)
    except zipfile.BadZipFile as exc:
        raise RuntimeError("EPUB okunamadı, dosya bozuk olabilir.") from exc

    full_text = "\n".join(text_blocks).strip()
    if not full_text:
        raise RuntimeError("EPUB'dan metin çıkarılamadı.")
    parts = split_text_segments(full_text)
    return [
        {"segment": i, "text": part, "start": None, "end": None}
        for i, part in enumerate(parts)
    ]
