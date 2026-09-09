"""Not dışa aktarma — markdown'ı Türkçe karakter destekli, tipografisi düzgün PDF'e çevirir.

Düzen `pymupdf.Story` ile HTML+CSS üzerinden kurulur: satır kaydırma, sayfa akışı,
iç içe listeler ve satır içi kalın/italik metin motorun kendi işi. Fiziksel çıktı için
zemin beyaz, metin siyah kalır; tasarım dili yalnızca tipografi + boşluk hiyerarşisiyle
taşınır (uygulamadaki monokrom kimlikle aynı mantık).
"""

from __future__ import annotations

import html
import io
import re
from pathlib import Path

import pymupdf
from markdown_it import MarkdownIt

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

_MARGIN = 54
# Story'ye verilen `em`: CSS'teki px değerleri bu ölçekle punto'ya çevrilir.
_EM = 12

_CITATION_RE = re.compile(r"\[(\d+)\]")

_CSS = """
@font-face {{ font-family: stuhub; src: url(regular.ttf); }}
@font-face {{ font-family: stuhub; font-weight: bold; src: url(bold.ttf); }}

body {{ font-family: {family}; font-size: 10.5px; color: #18181b; line-height: 1.55; }}
h1 {{ font-size: 19px; font-weight: bold; margin: 0 0 4px 0; }}
h2 {{ font-size: 14px; font-weight: bold; margin: 18px 0 6px 0; }}
h3 {{ font-size: 11.5px; font-weight: bold; margin: 14px 0 4px 0; }}
h4 {{ font-size: 10.5px; font-weight: bold; margin: 12px 0 4px 0; }}
p {{ margin: 0 0 8px 0; }}
ul, ol {{ margin: 0 0 8px 0; }}
li {{ margin: 0 0 5px 0; }}
blockquote {{ margin: 8px 0 10px 12px; color: #52525b; }}
code {{ font-family: monospace; font-size: 9.5px; color: #3f3f46; }}
hr {{ margin: 14px 0; }}
.citation {{ color: #71717a; }}
.subtitle {{ color: #71717a; font-size: 9.5px; margin: 0 0 16px 0; }}
"""


def _find_font() -> tuple[str, str]:
    """(düz font, kalın font) — Türkçe glif destekli; bulunamazsa base-14 yedeği."""
    for regular, bold in zip(FONT_CANDIDATES, BOLD_CANDIDATES, strict=False):
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    for regular in FONT_CANDIDATES:
        if Path(regular).exists():
            return regular, regular
    return "helv", "helv"


def _story_assets() -> tuple[pymupdf.Archive | None, str]:
    """(font arşivi, CSS font ailesi) — sistemde TTF yoksa base-14'e düşer."""
    regular, bold = _find_font()
    if regular == "helv":
        # Base-14 Helvetica WinAnsi kodlamasıdır: ğ/ş/ı gliflerini taşımaz, ama
        # font bulunamayan bir ortamda PDF üretmemekten iyidir.
        return None, "sans-serif"
    archive = pymupdf.Archive()
    archive.add(Path(regular).read_bytes(), "regular.ttf")
    archive.add(Path(bold).read_bytes(), "bold.ttf")
    return archive, "stuhub"


_MD = MarkdownIt("commonmark")


def _markdown_to_html(title: str, content_md: str) -> str:
    # CommonMark: uygulamadaki react-markdown ile aynı ayrıştırma — iki boşlukla girintili
    # iç içe listeler PDF'te de iç içe kalır (Python-Markdown bunları düzleştiriyordu).
    body = _MD.render(content_md)
    # Atıf numaraları gövde metninden görsel olarak ayrılsın (tıklanabilir değiller).
    body = _CITATION_RE.sub(r'<span class="citation">[\1]</span>', body)
    # Notun ilk başlığı zaten bölüm adıysa belge başlığını tekrar basma.
    first_line = content_md.lstrip().split("\n", 1)[0].lstrip("#").strip()
    duplicate = title.casefold() == first_line.casefold()
    heading = "" if not title or duplicate else f"<h1>{html.escape(title)}</h1>"
    return f"<html><body>{heading}{body}</body></html>"


def note_markdown_to_pdf(content_md: str, title: str = "") -> bytes:
    """Markdown notu PDF baytlarına çevirir (A4, beyaz zemin, siyah metin)."""
    archive, family = _story_assets()
    story = pymupdf.Story(
        html=_markdown_to_html(title, content_md),
        user_css=_CSS.format(family=family),
        em=_EM,
        archive=archive,
    )

    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page_rect = pymupdf.paper_rect("a4")
    content_rect = page_rect + (_MARGIN, _MARGIN, -_MARGIN, -_MARGIN)

    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()


def note_markdown_to_md(title: str, content_md: str) -> str:
    """Notu Markdown olarak döner: başlık + content_md birebir (Yetenek 12 Format 1)."""
    return f"# {title}\n\n{content_md}\n"


def flashcards_to_md(cards: list[dict]) -> str:
    """Kartları basit MD listelemesine çevirir (Yetenek 12 Format 1)."""
    lines: list[str] = []
    current_topic: str | None = None
    for card in cards:
        topic = str(card.get("topic", "") or "Genel")
        if topic != current_topic:
            lines.append(f"\n## {topic}\n")
            current_topic = topic
        lines.append(f"- **Soru:** {card.get('front', '')}")
        lines.append(f"- **Cevap:** {card.get('back', '')}")
    return "\n".join(lines).strip() + "\n"
