"""Not dışa aktarma — Markdown'ı Türkçe karakter destekli Montserrat ile PDF'e çevirir.

İki varyant (kullanıcı seçimi, akordeondan):
- ``physical``: baskı dostu off-white zemin, SİYAH logo (beyaz logo beyaz zeminde
  kayboluyordu), 1. sayfada şık StuHub header bandı (logo + belge başlığı +
  "StuHub ile hazırlandı" imzası). Sayfa takibi YALNIZCA footer'da.
- ``digital``: StuHub'ın koyu tasarım dili — siyaha yakın zemin, cam efektli
  header paneli (katmanlı dolgu + üst ışık çizgisi), beyaz tipografi.

Düzen `pymupdf.Story` ile HTML+CSS üzerinden kurulur: satır kaydırma, sayfa akışı,
iç içe listeler ve satır içi kalın/italik metin motorun kendi işi. 1. sayfa daha
yüksek header bölgesi alır (sayfa başına content rect mekanizması doğrulandı).
"""

from __future__ import annotations

import html
import io
import re
from pathlib import Path

import pymupdf
from markdown_it import MarkdownIt

FONT_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Montserrat-Regular.ttf",
)
BOLD_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Montserrat-Bold.ttf",
)
LOGO_DIR = Path(__file__).resolve().parent.parent / "assets"

_MARGIN = 54
_FOOTER_HEIGHT = 24
# 1. sayfa header bandı yüksekliği (logo + başlık + imza); diğer sayfalarda yalnız
# footer payı ayrılır — header'da sayfa takibi YOK (kullanıcı kararı).
_FIRST_PAGE_HEADER = 118
# Story'ye verilen `em`: CSS'teki px değerleri bu ölçekle punto'ya çevrilir.
_EM = 12

_CITATION_RE = re.compile(r"\[(\d+)\]")

# Dijital varyant ekstra stilleri: bölüm başlık çizgileri (h2/h3 border-bottom) +
# atıf stili (üst simge, muted accent rengi). Story'nin CSS motoru border-bottom ve
# vertical-align destekliyor (mechanism-verified).
_DIGITAL_EXTRAS = """
h2 {{ border-bottom: 0.7px solid #3a3a40; padding-bottom: 3px; }}
h3 {{ border-bottom: 0.6px solid #2c2c31; padding-bottom: 2px; }}
sup.citation {{ font-size: 7.5px; color: #a5a5b4; }}
"""

PDF_VARIANTS = ("physical", "digital")

# --- Dijital varyant paleti (StuHub koyu tasarım dili) -----------------------
_DIGITAL_BG = (0.039, 0.039, 0.043)  # #0a0a0b
_DIGITAL_TEXT = (0.93, 0.93, 0.96)  # #ededf4
_DIGITAL_MUTED = (0.62, 0.62, 0.68)
_DIGITAL_FAINT = (0.47, 0.47, 0.52)

_CSS = """
@font-face {{ font-family: stuhub; src: url(regular.ttf); }}
@font-face {{ font-family: stuhub; font-weight: bold; src: url(bold.ttf); }}

body {{ font-family: {family}; font-size: 10.5px; color: {text}; line-height: 1.55; \
background: {bg}; }}
h1 {{ font-size: 19px; font-weight: bold; margin: 0 0 4px 0; }}
h2 {{ font-size: 14px; font-weight: bold; margin: 18px 0 6px 0; }}
h3 {{ font-size: 11.5px; font-weight: bold; margin: 14px 0 4px 0; }}
h4 {{ font-size: 10.5px; font-weight: bold; margin: 12px 0 4px 0; }}
p {{ margin: 0 0 8px 0; }}
ul, ol {{ margin: 0 0 8px 0; }}
li {{ margin: 0 0 5px 0; }}
blockquote {{ margin: 8px 0 10px 12px; color: {muted}; }}
code {{ font-family: monospace; font-size: 9.5px; color: {muted}; }}
hr {{ margin: 14px 0; }}
.citation {{ color: {faint}; }}
.subtitle {{ color: {muted}; font-size: 9.5px; margin: 0 0 16px 0; }}
"""


def _find_font() -> tuple[str, str]:
    """(düz font, kalın font) — Türkçe glif destekli; bulunamazsa hata."""
    regular = FONT_CANDIDATES[0]
    bold = BOLD_CANDIDATES[0]
    if regular.exists() and bold.exists():
        return str(regular), str(bold)
    raise RuntimeError(
        "StuHub PDF font assets are missing: Montserrat-Regular.ttf / Montserrat-Bold.ttf"
    )


def _story_assets() -> tuple[pymupdf.Archive, str]:
    """(font arşivi, CSS font ailesi)."""
    regular, bold = _find_font()
    archive = pymupdf.Archive()
    archive.add(Path(regular).read_bytes(), "regular.ttf")
    archive.add(Path(bold).read_bytes(), "bold.ttf")
    return archive, "stuhub"


_MD = MarkdownIt("commonmark")


def _markdown_to_html(title: str, content_md: str, digital: bool = False) -> str:
    # CommonMark: uygulamadaki react-markdown ile aynı ayrıştırma — iki boşlukla girintili
    # iç içe listeler PDF'te de iç içe kalır (Python-Markdown bunları düzleştiriyordu).
    body = _MD.render(content_md)
    # Atıf numaraları: fiziksel baskıda gövde içinde soluk span; dijital kopyada
    # üst simge (sup) — ekran okumada gövde akışını bozmaz, ayırt edici bir stil.
    if digital:
        body = _CITATION_RE.sub(r'<sup class="citation">[\1]</sup>', body)
    else:
        body = _CITATION_RE.sub(r'<span class="citation">[\1]</span>', body)
    # Notun ilk başlığı zaten bölüm adıysa belge başlığını tekrar basma.
    first_line = content_md.lstrip().split("\n", 1)[0].lstrip("#").strip()
    duplicate = title.casefold() == first_line.casefold()
    heading = "" if not title or duplicate else f"<h1>{html.escape(title)}</h1>"
    return f"<html><body>{heading}{body}</body></html>"


def _style_for(variant: str) -> str:
    if variant == "digital":
        base = _CSS.format(
            family="stuhub",
            bg="#0a0a0b",
            text="#ededf4",
            muted="#9e9ead",
            faint="#787884",
        )
        return base + _DIGITAL_EXTRAS.format()
    return _CSS.format(
        family="stuhub", bg="#fbfaf7", text="#18181b", muted="#52525b", faint="#71717a"
    )


def note_markdown_to_pdf(content_md: str, title: str = "", variant: str = "physical") -> bytes:
    """Markdown notu PDF baytlarına çevirir (A4; ``physical`` | ``digital``)."""
    if variant not in PDF_VARIANTS:
        raise ValueError(f"unknown pdf variant: {variant!r}")
    digital = variant == "digital"

    archive, family = _story_assets()
    story = pymupdf.Story(
        html=_markdown_to_html(title, content_md, digital=digital),
        user_css=_style_for(variant),
        em=_EM,
        archive=archive,
    )

    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page_rect = pymupdf.paper_rect("a4")
    # 1. sayfada header bandı için daha yüksek üst pay; sonraki sayfalarda yalnız margin.
    first_content = page_rect + (
        _MARGIN,
        _MARGIN + _FIRST_PAGE_HEADER,
        -_MARGIN,
        -(_MARGIN + _FOOTER_HEIGHT),
    )
    rest_content = page_rect + (_MARGIN, _MARGIN, -_MARGIN, -(_MARGIN + _FOOTER_HEIGHT))

    more = True
    page_number = 1
    while more:
        device = writer.begin_page(page_rect)
        content_rect = first_content if page_number == 1 else rest_content
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
        page_number += 1
    writer.close()

    # Print katmanı: her sayfada zemin rengi + footer; 1. sayfada üstelik marka header'ı.
    doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    logo_name = "stuhub-logo-soft.png" if digital else "stuhub-logo-black.png"
    logo_path = LOGO_DIR / logo_name
    if not logo_path.exists():
        logo_path = LOGO_DIR / "stuhub-logo.png"
    regular_path, bold_path = _find_font()

    for number, page in enumerate(doc, start=1):
        # Zemin: baskıda off-white, dijitalde siyah (body zaten aynı rengi taşır;
        # bu katman Story alanının dışındaki kenarları da kapatır).
        page.draw_rect(
            page.rect,
            color=None,
            fill=_DIGITAL_BG if digital else (0.984, 0.98, 0.965),
            overlay=False,
        )

        if number == 1:
            _draw_brand_header(page, page_rect, title, digital, logo_path, regular_path, bold_path)

        # Footer — sayfa takibi yalnızca burada (header'da yok).
        _draw_footer(page, page_rect, number, digital, regular_path, bold_path)

    out = doc.tobytes(deflate=True, garbage=4)
    doc.close()
    return out


def _draw_brand_header(
    page: pymupdf.Page,
    page_rect: pymupdf.Rect,
    title: str,
    digital: bool,
    logo_path: Path,
    regular_path: str,
    bold_path: str,
) -> None:
    """1. sayfa marka header'ı — logo, belge başlığı ve StuHub imzası."""
    page_w = page_rect.width
    left = _MARGIN
    right = page_w - _MARGIN
    top = 30.0
    band_bottom = top + _FIRST_PAGE_HEADER - 24  # content üst boşluğuyla çakışmasın

    if digital:
        # Cam efekt: katmanlı koyu dolgu + üst ışık çizgisi + ince çerçeve.
        bands = [(0.165, 0.165, 0.18), (0.125, 0.125, 0.14), (0.086, 0.086, 0.098)]
        band_h = (band_bottom - top) / len(bands)
        for i, fill in enumerate(bands):
            page.draw_rect(
                pymupdf.Rect(left, top + i * band_h, right, top + (i + 1) * band_h),
                color=None,
                fill=fill,
                overlay=True,
            )
        page.draw_line(
            pymupdf.Point(left, top), pymupdf.Point(right, top), color=(1, 1, 1), width=0.9
        )
        page.draw_line(
            pymupdf.Point(left, band_bottom),
            pymupdf.Point(right, band_bottom),
            color=(0.35, 0.35, 0.4),
            width=0.5,
        )
        tagline_color = _DIGITAL_MUTED
        title_color = _DIGITAL_TEXT
    else:
        # Fiziksel: çerçevesiz, temiz; ince ayraç çizgisi.
        page.draw_line(
            pymupdf.Point(left, band_bottom),
            pymupdf.Point(right, band_bottom),
            color=(0.78, 0.77, 0.74),
            width=0.7,
        )
        tagline_color = (0.42, 0.42, 0.45)
        title_color = (0.09, 0.09, 0.11)

    # Logo: 2:1'e yakın en-boy; yüksekliği 26 punto ile sınırla.
    logo_h = 26.0
    logo_w = logo_h * 2
    if logo_path.exists():
        page.insert_image(
            pymupdf.Rect(left, top + 4, left + logo_w, top + 4 + logo_h),
            filename=str(logo_path),
            keep_proportion=True,
            overlay=True,
        )

    # Belge başlığı (course · chapter) — logonun sağından sağ kenara.
    title_y = top + 4 + logo_h - 4
    display_title = (title or "Not").strip()
    max_chars = 64
    if len(display_title) > max_chars:
        display_title = display_title[: max_chars - 1].rstrip() + "…"
    page.insert_text(
        pymupdf.Point(left + logo_w + 14, title_y),
        display_title,
        fontfile=str(bold_path),
        fontsize=11.5,
        color=title_color,
        overlay=True,
    )

    # İmza satırı: "StuHub ile hazırlandı" + tarih.
    tagline = "StuHub ile hazırlandı"
    page.insert_text(
        pymupdf.Point(left + logo_w + 14, title_y + 14),
        tagline,
        fontfile=str(regular_path),
        fontsize=8,
        color=tagline_color,
        overlay=True,
    )


def _draw_footer(
    page: pymupdf.Page,
    page_rect: pymupdf.Rect,
    number: int,
    digital: bool,
    regular_path: str,
    bold_path: str,
) -> None:
    """Footer: sol StuHub wordmark, sağ sayfa numarası — takibin tek yeri."""
    color = _DIGITAL_MUTED if digital else (0.42, 0.42, 0.44)
    y = page_rect.height - 20
    page.insert_text(
        pymupdf.Point(_MARGIN, y),
        "StuHub",
        fontfile=str(bold_path),
        fontsize=8,
        color=color,
        overlay=True,
    )
    page.insert_text(
        pymupdf.Point(page_rect.width - _MARGIN - 24, y),
        str(number),
        fontfile=str(regular_path),
        fontsize=8,
        color=color,
        overlay=True,
    )


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
