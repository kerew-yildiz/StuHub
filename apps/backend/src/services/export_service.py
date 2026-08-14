"""Not PDF dışa aktarma — markdown'ı Türkçe karakter destekli, taşmasız PDF'e çevirir.

pymupdf ile satır bazlı düzenleyici: başlıklar (kalın), listeler, alıntılar, paragraflar.
Metin genişliği ölçülerek kelime bazlı satır kaydırma yapılır (sayfa taşması olmaz).
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
BOLD_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
)

_MARGIN = 56
_HEADING_SIZES = {1: 20, 2: 16, 3: 13, 4: 12}

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_RULE_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")


def _find_font() -> tuple[str, str]:
    """(düz font, kalın font) — Türkçe glif destekli; bulunamazsa base-14 yedeği."""
    for regular, bold in zip(FONT_CANDIDATES, BOLD_CANDIDATES, strict=False):
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    for regular in FONT_CANDIDATES:
        if Path(regular).exists():
            return regular, regular
    return "helv", "helv"


def _clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def note_markdown_to_pdf(content_md: str) -> bytes:
    """Markdown notu PDF baytlarına çevirir (görsel hata: taşan satırlar düzeltildi)."""
    regular_font, bold_font = _find_font()
    doc = pymupdf.open()
    page = doc.new_page()
    max_width = page.rect.width - 2 * _MARGIN
    y = _MARGIN
    used_page_height = page.rect.height - _MARGIN
    # Kelime genişliği ölçümü için font nesnesi (özel fontlarla get_text_length çalışmaz)
    measure_font = (
        pymupdf.Font("stuhub", fontfile=regular_font)
        if regular_font != "helv"
        else pymupdf.Font("helv")
    )

    def ensure_space(needed: float) -> None:
        nonlocal page, y
        if y + needed > used_page_height:
            page = doc.new_page()
            y = _MARGIN

    def write_line(text: str, size: float, font: str, indent: float = 0) -> None:
        nonlocal y
        page.insert_text(
            (_MARGIN + indent, y),
            text,
            fontsize=size,
            fontname="stuhub" if font != "helv" else font,
            fontfile=font if font != "helv" else None,
        )
        y += size + 3.5

    def write_wrapped(text: str, size: float, font: str, indent: float = 0) -> None:
        """Kelime bazlı satır kaydırma — uzun paragraflar sayfadan taşmaz."""
        words = text.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            width = measure_font.text_length(candidate, fontsize=int(size))
            if width > max_width - indent and current:
                ensure_space(size + 4)
                write_line(current, size, font, indent)
                current = word
            else:
                current = candidate
        if current:
            ensure_space(size + 4)
            write_line(current, size, font, indent)

    for raw_line in content_md.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            y += 3
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            size = _HEADING_SIZES.get(len(heading.group(1)), 11)
            ensure_space(size + 8)
            write_wrapped(_clean_inline(heading.group(2)), size, bold_font)
            y += 4
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            write_wrapped("› " + _clean_inline(quote.group(1)), 10.5, regular_font, indent=14)
            continue

        if _RULE_RE.match(line):
            ensure_space(10)
            page.draw_line(
                pymupdf.Point(_MARGIN, y),
                pymupdf.Point(page.rect.width - _MARGIN, y),
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
            write_wrapped(prefix + _clean_inline(text), 11, regular_font, indent=18)
            continue

        write_wrapped(_clean_inline(line), 11, regular_font)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
