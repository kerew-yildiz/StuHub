"""Not PDF dışa aktarma — markdown'ı Türkçe karakter destekli PDF'e çevirir.

pymupdf ile satır bazlı basit bir düzenleyici: başlıklar, listeler, alıntılar,
paragraflar; sistem fontu (Arial vb.) Türkçe glifler için kullanılır.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)

_MARGIN = 60
_LINE_HEIGHT = 16
_PARAGRAPH_GAP = 6

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_RULE_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")


def _find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return "helv"  # yedek: Türkçe glif eksik olabilir


def _clean_inline(text: str) -> str:
    """İnline markdown işaretlerini temizler (**bold**, *italic*, `code`, [n] atıf)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def note_markdown_to_pdf(content_md: str) -> bytes:
    """Markdown notu PDF baytlarına çevirir."""
    font = _find_font()
    doc = pymupdf.open()
    page = doc.new_page()
    width = page.rect.width
    y = _MARGIN

    def ensure_space(needed: float) -> None:
        nonlocal page, y
        if y + needed > page.rect.height - _MARGIN:
            page = doc.new_page()
            y = _MARGIN

    def write(text: str, size: float = 11, bold: bool = False, indent: float = 0) -> None:
        nonlocal y
        ensure_space(size + 4)
        page.insert_text(
            (_MARGIN + indent, y),
            text,
            fontsize=size,
            fontname="stuhub" if font != "helv" else "helv",
            fontfile=font if font != "helv" else None,
        )
        y += size + 6

    for raw_line in content_md.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            y += _PARAGRAPH_GAP / 2
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            size = {1: 20, 2: 16, 3: 13, 4: 12}.get(level, 11)
            write(_clean_inline(heading.group(2)), size=size, bold=True)
            y += _PARAGRAPH_GAP
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            write("› " + _clean_inline(quote.group(1)), size=10.5, indent=14)
            continue

        if _RULE_RE.match(line):
            ensure_space(10)
            page.draw_line(
                pymupdf.Point(_MARGIN, y),
                pymupdf.Point(width - _MARGIN, y),
                color=(0.6, 0.6, 0.6),
                width=0.7,
            )
            y += 12
            continue

        list_item = _LIST_RE.match(line)
        if list_item:
            bullet = list_item.group(2)
            text = list_item.group(3)
            prefix = "• " if bullet in ("-", "*") else f"{bullet} "
            write(prefix + _clean_inline(text), size=11, indent=18)
            continue

        write(_clean_inline(line))

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
