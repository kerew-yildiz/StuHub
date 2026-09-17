"""Not dışa aktarma — Markdown'ı Türkçe karakter destekli Montserrat ile PDF'e çevirir.

İki varyant (kullanıcı seçimi, akordeondan) — AYNI yerleşim/tipografi, yalnız renk
seti farklı (``_PALETTE`` + ``_BASE_CSS`` token'ları):
- ``physical``: beyaz kâğıt + yazıcı dostu (koyu zemin YOK, kutu/şerit dolguları
  açık ton + ince çizgi), SİYAH logo (beyaz logo beyaz zeminde kayboluyordu),
  StuHub kimliği: çizgiyle ayrılmış header bandı (logo + ``ders · chapter`` +
  "StuHub ile hazırlandı"), bağlantılar altı çizili (renksiz baskıda da okunur).
- ``digital``: StuHub'ın koyu tasarım dili — siyaha yakın zemin, cam hisli header
  paneli (üst ışık çizgisi + alt kenar çizgisi), beyaz tipografi.

Düzen `pymupdf.Story` ile HTML+CSS üzerinden kurulur: satır kaydırma, sayfa akışı,
iç içe listeler ve satır içi kalın/italik metin motorunun kendi işi. 1. sayfa daha
yüksek header bölgesi alır (sayfa başına content rect mekanizması doğrulandı).
Tasarım TALEP ANINDA uygulanır: not gövdesi yalnız Markdown olarak saklanır
(``notes.content_md``), stil bilgisi saklanmaz — bu yüzden eski notların PDF'i de
her indirmede güncel tasarımı alır.
"""

from __future__ import annotations

import io
import re
from datetime import date
from functools import lru_cache
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

# Kenar boşlukları: kullanıcı geri bildirimi (v4) — kartların sayfaya göre dış
# boşluğu %80 azaltıldı (54 → ~11pt); metnin karta olan iç payı da aynı oranda
# küçültülür (`_CONTENT_PAD`), sonra kullanıcı isteğiyle bir tık artırıldı
# (11 → 16pt; iç pay 2 → 3pt). Üst/alt boşluk header/footer geometrisiyle sabittir.
_MARGIN = 16.0
_CONTENT_PAD = 3.0
# Alt boşluk: footer sayfa kenarının içinde durur, içerik metni footer'ın hemen
# üstüne kadar akar (önce 24pt footer payı içeriği yukarı itip altta ölü boşluk
# bırakıyordu — 2026-09-17 koordinatör geri bildirimi).
_MARGIN_BOTTOM = 46
_FOOTER_BASELINE = 30.0
# Story'ye verilen `em`: CSS'teki px değerleri bu ölçekle punto'ya çevrilir.
_EM = 12

# PyMuPDF çizim katmanı font adları. `insert_text(fontfile=...)` TEK BAŞINA
# kullanılırsa PyMuPDF base-14 (Helvetica/Latin-1) kodlamasını uygular ve 'ı/ş/ğ'
# glifleri '·'ya düşer ("haz·rland·" — 2026-09-17 ölçümü, probe-font.png). Özel
# fontname verilince gömülü TTF Unicode eşlemesiyle çizilir.
_CHART_FONTS = {"regular": "stuhub-reg", "bold": "stuhub-bold"}

# Atıf temizliği (v4): PDF'te [1] / [Slide 3] tarzı işaretler HİÇ basılmaz. Not
# verisi değişmez; yalnız render kopyası sadeleşir. Kod blokları/iç kod span'ları
# korunur (ör. `arr[1]` bozulmasın) — `_strip_references` parçalara ayırıp uygular.
_REF_PATTERNS = (
    re.compile(r"\s*[\[\(]\s*[Ss]lide[^\]\)\n]*[\]\)]"),  # [Slide 3], [Slide 26, Slide 27]
    re.compile(r"\s*\[\d+(?:\s*[,;]\s*\d+)*\]"),  # [1], [3, 5]
)
_CODE_SPAN_RE = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([.,;:!?])")
_NOTICE_RE = re.compile(r"^.*ders sunumundan üretildi.*$", re.M)
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
_HEADING_RE = re.compile(r"<h([1-4])(>.*?</h\1>)", re.S)
_TAG_RE = re.compile(r"<[^>]+>")

# --- Konu kartları -----------------------------------------------------------
# Kart = notes.topics_json'daki konu başlığı + sonraki konu başlığına kadar olan
# TÜM içeriği saran yuvarlak cam kutu. Eşleşmeyen başlıklar (alt başlıklar) kart
# İÇİNDE normal h3/h4 stiliyle kalır. Kart PyMuPDF katmanında çizilir: Story'nin
# CSS motoru `border-radius` desteklemiyor (ölçüldü) — yuvarlak köşe bu katmanda.
_TOPIC_MIN_SIZE = 12.0  # başlık punto eşiği (h2 14 / h3 12.5 girer, gövde 10.5 girmez)
_TOPIC_PAD_Y = 8.0  # başlık üstü/altı kart payı
_TOPIC_GAP = 24.0  # iki kart arası görsel boşluk = _TOPIC_GAP - _TOPIC_PAD_Y (16pt)
# Köşe yarıçapı PUNTO cinsinden: PyMuPDF `radius` oranı kısa kenara göre alır,
# oran büyük kartlarda ~100pt'ye çıkar ve metin yuvarlatılmış köşenin dışında
# kalırdı (kullanıcı kanıtı 030416) — sabit 7pt'ye çevrildi.
_TOPIC_RADIUS_PT = 7.0

# --- Header stilleri (kullanıcı seçimi bekliyor: V1/V2/V3) --------------------
# (üst boşluk, bant yüksekliği, içerik öncesi nefes payı) — 1. sayfa içerik payı
# bu üçünün toplamından `_MARGIN` çıkarılarak hesaplanır.
HEADER_STYLES = ("v1", "v2", "v3")
HEADER_STYLE = "v2"  # kullanıcı seçimi (2026-09-17): app-header eşleniği (ortada logo + wordmark)
_HEADER_BOX = {
    "digital": {"v1": (28.0, 62.0, 22.0), "v2": (0.0, 78.0, 20.0), "v3": (34.0, 48.0, 24.0)},
    "physical": {"v1": (30.0, 56.0, 22.0), "v2": (30.0, 54.0, 20.0), "v3": (30.0, 58.0, 22.0)},
}

# --- Dijital zemin görseli ---------------------------------------------------
# Uygulamanın arka plan asset'i (public/bg) sayfa zeminine taşınır: A4 oranına
# kırpılır, bulanıklaştırılır ve siyah perdeyle karartılır (metin kontrastı).
_BG_CANDIDATES = (
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "bg" / "calisma-masasi.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "bg" / "zirve.jpg",
)
_BG_SIZE = (596, 842)  # A4 punto ölçüsünde kırpma hedefi
_BG_RASTER = (620, 877)  # blur uygulanacak küçük raster (dosya boyutu düşük kalır)
_BG_BLUR = 6.0
_BG_DIM = 0.66
_BG_BRIGHTNESS = 2.2  # kaynak asset zaten koyu (siyah masa); detay bu çarpanla görünür

PDF_VARIANTS = ("physical", "digital")


def _header_box(variant: str, style: str | None = None) -> tuple[float, float, float]:
    return _HEADER_BOX[variant][style or HEADER_STYLE]


def _first_page_offset(variant: str) -> float:
    """1. sayfada içeriğin üst payı (header bandının toplam yer kapladığı yükseklik)."""
    top, height, gap = _header_box(variant)
    return top + height + gap - _MARGIN

# --- Varyant paleti ----------------------------------------------------------
# Tek tasarım dili, iki renk seti. Dijital = StuHub'ın koyu token'ları
# (theme.css: #0a0a0b zemin, #fafafa metin, cam yüzeyler); fiziksel = aynı dilin
# kâğıt çevirisi (beyaz zemin, mürekkep metin, marka kum tonu accent).
# CSS token'ları (Story) ve PyMuPDF çizim renkleri tek yerde toplanır.
_PALETTE = {
    "digital": {
        "page_bg": (0.039, 0.039, 0.043),
        "card_fill": (0.09, 0.09, 0.10),
        "card_border": (0.24, 0.24, 0.27),
        "card_opacity": 0.42,  # v4: cam hafif hissedilsin (yarıya indirildi)
        "footer": (0.62, 0.62, 0.68),
        "css": {
            "text": "#ededf4",
            "muted": "#9e9ead",
            "faint": "#787884",
            "accent": "#d5c9a8",
            "link": "#fafafa",
            "code_text": "#d6d6de",
            "code_bg": "#1b1b1f",
            "quote_text": "#b9b9c4",
            "quote_bg": "#141416",
            "quote_border": "#4a4436",
            "rule": "#2c2c31",
        },
    },
    "physical": {
        "page_bg": (1.0, 1.0, 1.0),
        "card_fill": (0.969, 0.965, 0.949),
        "card_border": (0.855, 0.835, 0.78),
        "card_opacity": 1.0,
        "footer": (0.42, 0.42, 0.44),
        "css": {
            "text": "#18181b",
            "muted": "#52525b",
            "faint": "#71717a",
            "accent": "#8a7a4d",
            "link": "#18181b",
            "code_text": "#3f3f46",
            "code_bg": "#f4f3ee",
            "quote_text": "#3f3f46",
            "quote_bg": "#f7f5ee",
            "quote_border": "#c9bd98",
            "rule": "#d9d7cf",
        },
    },
}

# Header metin/ton renkleri (PyMuPDF katmanı): dijitalde cam panel üstünde beyaz
# tipografi + açık ayraç, fizikselde mürekkep + kum tonlu geçişler.
_HEADER_TEXT = {
    "digital": {
        "title": (0.98, 0.98, 0.98),
        "eyebrow": (0.72, 0.72, 0.78),
        "tagline": (0.63, 0.63, 0.67),
        "rule": (0.24, 0.24, 0.27),
    },
    "physical": {
        "title": (0.08, 0.08, 0.09),
        "eyebrow": (0.45, 0.45, 0.48),
        "tagline": (0.42, 0.42, 0.45),
        "rule": (0.83, 0.81, 0.74),
    },
}

# Uygulama tipografi ritmi (NoteViewer.tsx: gövde 15.5px/1.75, h1 26 · h2 21 ·
# h3 19 · h4 16 semibold, p mb-4, li space-y-2, kod 13.5px) A4 punto ölçeğine
# (~0.68) indirildi; iki varyant da bu tek şablonu kullanır — yalnız token'lar
# değişir. blur/gradient YOK (Story desteklemez); başlık hiyerarşisi yalnız
# punto + ağırlık + boşlukla kurulur (09-08 kararı: çizgili/renkli başlık vurgusu
# "AI-üretimi arayüz" izi sayılıp kaldırılmıştı).
# Bağlantı rengi `body a` ile verilir: Story'nin UA stil sayfası çıplak `a`
# seçicisini (mavi) geçersiz kılıyor — ölçüldü, kapsam + `:link` özgüllüğü gerekiyor.
_BASE_CSS = """
@font-face {{ font-family: stuhub; src: url(regular.ttf); }}
@font-face {{ font-family: stuhub; font-weight: bold; src: url(bold.ttf); }}

/* Gövde zemini YOK: sayfa zemini + arka plan görseli PyMuPDF katmanında çizilir,
   metin katmanı şeffaf kalır (aksi halde opak gövde zemini görseli kapatırdı). */
body {{ font-family: {family}; font-size: 10.5px; color: {text}; line-height: 1.62; }}
h1 {{ font-size: 17.5px; font-weight: bold; margin: 0 0 7px 0; }}
h2 {{ font-size: 14px; font-weight: bold; margin: 19px 0 7px 0; }}
h3 {{ font-size: 12.5px; font-weight: bold; margin: 15px 0 5px 0; }}
h4 {{ font-size: 11px; font-weight: bold; margin: 13px 0 4px 0; }}
/* Konu başlıkları: kart PyMuPDF katmanında çizilir; burada yalnız kartlar arası
   nefes payı verilir. Yatay hizalama padding ile DEĞİL, metin dikdörtgeni kartın
   iç payı kadar daraltılarak kurulur (taşma önlemi — v4). */
h1.topic, h2.topic, h3.topic, h4.topic {{ margin: 26px 0 16px 0; }}
p {{ margin: 0 0 9px 0; }}
ul, ol {{ margin: 0 0 9px 0; }}
li {{ margin: 0 0 5px 0; }}
strong {{ font-weight: bold; }}
body a, body a:link, body a:visited {{ color: {link}; text-decoration: underline; }}
blockquote {{ margin: 10px 0 12px 0; padding: 5px 10px; color: {quote_text}; \
background: {quote_bg}; border-left: 2px solid {quote_border}; }}
code {{ font-family: monospace; font-size: 9.5px; color: {code_text}; \
background: {code_bg}; }}
pre {{ margin: 0 0 11px 0; padding: 6px 8px; background: {code_bg}; \
border-left: 2px solid {quote_border}; }}
pre code {{ font-size: 9px; background: {code_bg}; }}
hr {{ margin: 15px 0; border: none; border-top: 0.7px solid {rule}; }}
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

# Türkçe harf katlama: başlık ile topics_json adı arasında büyük/küçük harf ve
# aksan farkı eşleşmeyi bozmasın ('İ' casefold'da 'i̇' olur, 'ı' ise 'ı' kalır).
_TR_FOLD = str.maketrans("ıİşŞğĞçÇöÖüÜ", "iissggccoouu")


def _normalize_topic(text: str) -> str:
    """Başlık/konu adını karşılaştırma için sadeleştirir (etiketler, aksan, boşluk)."""
    plain = _TAG_RE.sub("", text).translate(_TR_FOLD).casefold()
    return " ".join(plain.split()).strip(" .:;,-–—·")


def _strip_refs_in_line(line: str) -> str:
    """Tek satırda atıf işaretlerini siler; satır içi kodu ve satır girintisini korur."""
    indent = line[: len(line) - len(line.lstrip(" \t"))]
    parts = line[len(indent) :].split("`")
    for index in range(0, len(parts), 2):  # çift indeksler kod DIŞI parçalar
        for pattern in _REF_PATTERNS:
            parts[index] = pattern.sub("", parts[index])
        parts[index] = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", parts[index])
        parts[index] = _MULTISPACE_RE.sub(" ", parts[index])
    return indent + "`".join(parts)


_LIST_START_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|>)")


def _strip_references(markdown: str) -> str:
    """Atıf işaretlerini (``[1]``, ``[Slide 3]``) ve bilgi kutusunu render kopyasından çıkarır.

    Not verisine DOKUNULMAZ. Kod içerikleri korunur: ``` çitleri, satır içi ``kod``
    ve 4 boşlukla kaydırılmış kod satırları. Girinti kodu ile liste alt satırı
    ayrımı için bir önceki İÇERİK satırına bakılır (liste/blockquote ise girinti
    liste devamıdır, kod değildir) — aksi halde ör. ``arr[1]`` bozulabilirdi.
    """
    lines = _NOTICE_RE.sub("", markdown).split("\n")
    out: list[str] = []
    in_fence = False
    in_code = False
    last_content = ""
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            in_code = False
            out.append(line)
            last_content = line.strip()
            continue
        indented = line[:4] == "    " or line[:1] == "\t"
        if in_fence:
            out.append(line)
        elif indented and (in_code or (not last_content or not _LIST_START_RE.match(last_content))):
            in_code = True  # boş satır ya da kod bloğu devamı → kod
            out.append(line)
        elif not line.strip():
            out.append(line)
        else:
            in_code = False
            out.append(_strip_refs_in_line(line))
        if line.strip():
            last_content = line
    return "\n".join(out)


def _body_markdown(content_md: str, title: str) -> str:
    """Belge başlığı bandda basılır: notun ilk satırı da onu tekrarlıyorsa düşürülür.

    Üretici notları bölüm adıyla başlayabiliyor (``# <chapter>``); router başlığı
    "ders · chapter" biçiminde geldiği için karşılaştırma parça bazında yapılır.
    """
    content_md = _strip_references(content_md)
    lines = content_md.lstrip().split("\n")
    if lines[0].lstrip().startswith("#"):
        heading = lines[0].lstrip("#").strip().casefold()
        if heading and heading in {part.strip().casefold() for part in title.split("·")}:
            return "\n".join(lines[1:])
    return content_md


def _mark_topic_headings(body: str, topics: set[str]) -> str:
    """topics_json ile eşleşen başlıklara `topic` sınıfı ekler (kart içi pay/marj).

    Kartın kendisi PyMuPDF katmanında çizilir; sınıf yalnız yerleşim (yatay pay +
    nefes payı) verir. Eşleşmeyen başlıklar alt başlık olarak normal stilde kalır.
    """
    if not topics:
        return body

    def repl(match: re.Match[str]) -> str:
        level, rest = match.group(1), match.group(2)
        text = _normalize_topic(rest)
        return f'<h{level} class="topic"{rest}' if text in topics else match.group(0)

    return _HEADING_RE.sub(repl, body)


def _markdown_to_html(content_md: str, topics: set[str]) -> str:
    # CommonMark: uygulamadaki react-markdown ile aynı ayrıştırma — iki boşlukla girintili
    # iç içe listeler PDF'te de iç içe kalır (Python-Markdown bunları düzleştiriyordu).
    body = _MD.render(content_md)
    # Belge başlığı gövdeye AYRICA basılmaz: tek yeri header bandı (önce hem bantta
    # hem h1 olarak iki kez görünüyordu). Notun kendi başlıkları içerik olarak kalır.
    return f"<html><body>{_mark_topic_headings(body, topics)}</body></html>"


def _style_for(variant: str) -> str:
    """Varyantın CSS'i — ortak `_BASE_CSS` şablonu + varyantın renk token'ları."""
    tokens = dict(_PALETTE[variant]["css"], family="stuhub")
    return _BASE_CSS.format(**tokens)


def note_markdown_to_pdf(
    content_md: str,
    title: str = "",
    variant: str = "physical",
    topics: list[str] | None = None,
) -> bytes:
    """Markdown notu PDF baytlarına çevirir (A4; ``physical`` | ``digital``).

    ``topics``: ``notes.topics_json`` içindeki konu adları — eşleşen başlıklar ve
    altındaki içerik yuvarlak konu kartı içinde basılır. Boş/None ise kart çizilmez.
    """
    if variant not in PDF_VARIANTS:
        raise ValueError(f"unknown pdf variant: {variant!r}")
    palette = _PALETTE[variant]
    topic_set = {_normalize_topic(t) for t in (topics or []) if t and t.strip()}

    archive, family = _story_assets()
    story = pymupdf.Story(
        html=_markdown_to_html(_body_markdown(content_md, title), topic_set),
        user_css=_style_for(variant),
        em=_EM,
        archive=archive,
    )

    # 1) Metin katmanı: yalnızca tipografi (şeffaf zemin) — Story sayfa akışını kurar.
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page_rect = pymupdf.paper_rect("a4")
    first_offset = _first_page_offset(variant)
    # Metin genişliği kart iç genişliğine KİLİTLİ: içerik dikdörtgeni kartın iç
    # payı kadar daraltılır (padding'e güvenilmez — taşma bu yüzden oluyordu).
    text_left = _MARGIN + _CONTENT_PAD
    text_right = -(_MARGIN + _CONTENT_PAD)
    first_content = page_rect + (text_left, _MARGIN + first_offset, text_right, -_MARGIN_BOTTOM)
    rest_content = page_rect + (text_left, _MARGIN, text_right, -_MARGIN_BOTTOM)

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
    text_doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")

    # 2) Baskı katmanı: zemin → arka plan görseli → konu kartları → metin katmanı →
    #    header/footer. Sıra tek yerde ve deterministiktir (overlay varsayılanı:
    #    her çizim mevcut içeriğin ÜSTÜNE eklenir).
    logo_name = "stuhub-logo-soft.png" if variant == "digital" else "stuhub-logo-black.png"
    logo_path = LOGO_DIR / logo_name
    if not logo_path.exists():
        logo_path = LOGO_DIR / "stuhub-logo.png"
    regular_path, bold_path = _find_font()
    background = _digital_background() if variant == "digital" else None

    doc = pymupdf.open()
    # Konu başlıkları belge genelinde ÖNCEDEN taranır: kart kapanışı sayfa
    # doluluğuna değil "sonraki başlık var mı" bilgisine bağlıdır.
    page_count = text_doc.page_count
    headings = {
        index: _topic_span_boxes(text_doc[index], topic_set) for index in range(page_count)
    } if topic_set else {}
    open_topic = False
    for number, text_page in enumerate(text_doc, start=1):
        page = doc.new_page(width=page_rect.width, height=page_rect.height)
        page.draw_rect(page.rect, color=None, fill=palette["page_bg"])
        if background:
            page.insert_image(page.rect, stream=background)
        if topic_set:
            content_top = _MARGIN + (first_offset if number == 1 else 0.0)
            open_topic = _draw_topic_cards(
                page,
                text_page,
                palette,
                content_top,
                open_topic,
                headings[number - 1],
                number == page_count,
            )
        page.show_pdf_page(page.rect, text_doc, number - 1)
        if number == 1:
            _draw_brand_header(page, page_rect, title, variant, logo_path, regular_path, bold_path)
        # Footer — sayfa takibi ve alt bilgi yalnızca burada (header'da yok).
        _draw_footer(page, page_rect, number, variant, regular_path)

    out = doc.tobytes(deflate=True, garbage=4)
    doc.close()
    text_doc.close()
    return out


def _text(
    page: pymupdf.Page,
    x: float,
    y: float,
    value: str,
    font_path: str,
    size: float,
    color: tuple[float, ...],
    weight: str = "regular",
) -> None:
    """Gömülü Montserrat ile metin — `fontname` şart (bkz. `_CHART_FONTS` notu)."""
    page.insert_text(
        (x, y),
        value,
        fontname=_CHART_FONTS[weight],
        fontfile=str(font_path),
        fontsize=size,
        color=color,
    )


def _text_width(value: str, font_path: str, size: float) -> float:
    return pymupdf.Font(fontfile=str(font_path)).text_length(value, fontsize=size)


@lru_cache(maxsize=2)
def _digital_background() -> bytes | None:
    """Dijital varyant zemin görseli: A4'e kırpılmış, bulanık + karartılmış JPEG.

    Kaynak: uygulamanın çalışma masası arka planı (``public/bg/calisma-masasi.png``;
    yoksa ``zirve.jpg``). Blur + siyah perde (%66) metin kontrastını korur: en parlak
    zemin ~%34 parlaklığa iner, gövde metni (#ededf4) ≥ 6:1 kontrast verir. Görsel
    bir kez işlenip önbelleklenir (her sayfa/PDF için yeniden blur maliyeti olmasın).
    """
    source = next((p for p in _BG_CANDIDATES if p.exists()), None)
    if source is None:
        return None  # görsel yoksa düz zemin kalır (mevcut davranış)
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:  # Pillow yoksa düz zemin
        return None
    image = Image.open(source).convert("RGB")
    # A4 oranına "cover" kırpma: kısa kenarı hedef orana büyüt, ortadan kırp.
    scale = max(_BG_SIZE[0] / image.width, _BG_SIZE[1] / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
    )
    left = (resized.width - _BG_SIZE[0]) // 2
    top = (resized.height - _BG_SIZE[1]) // 2
    crop = resized.crop((left, top, left + _BG_SIZE[0], top + _BG_SIZE[1]))
    # Küçük raster + blur: dosya boyutu ve render maliyeti düşük kalır.
    small = crop.resize(_BG_RASTER, Image.LANCZOS).filter(ImageFilter.GaussianBlur(_BG_BLUR))
    small = ImageEnhance.Brightness(small).enhance(_BG_BRIGHTNESS)
    dimmed = Image.blend(small, Image.new("RGB", small.size, (0, 0, 0)), _BG_DIM)
    out = io.BytesIO()
    dimmed.save(out, format="JPEG", quality=72, optimize=True)
    return out.getvalue()


def _topic_span_boxes(page: pymupdf.Page, topics: set[str]) -> list[pymupdf.Rect]:
    """Sayfadaki konu başlıklarının yerleşim kutuları (üstten alta sıralı)."""
    boxes: list[pymupdf.Rect] = []
    for block in page.get_text("dict")["blocks"]:
        spans = [s for line in block.get("lines", []) for s in line["spans"]]
        if not spans:
            continue
        if max(s["size"] for s in spans) < _TOPIC_MIN_SIZE:
            continue
        if not all("Bold" in s["font"] for s in spans):
            continue  # konu başlıkları kalın; gövde/içerik span'ları girmesin
        if _normalize_topic(" ".join(s["text"] for s in spans)) in topics:
            boxes.append(pymupdf.Rect(block["bbox"]))
    return sorted(boxes, key=lambda r: r.y0)


def _card_shape(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    palette: dict,
    round_top: bool,
    round_bottom: bool,
) -> None:
    """Yuvarlak konu kartı — köşeler AYRI AYRI yuvarlanır.

    Kullanıcı kuralı (v4): kart bir sonraki başlığa kadar kapanmaz; sayfa biterse
    kapanış YOK (düz kenarla sayfa sonuna kadar gider), devamı yeni sayfada düz
    kenarla başlar, yuvarlak kapanış yalnız sonraki başlıkta/belge sonunda olur.
    PyMuPDF'in `draw_rect(radius=...)` çağrısı dört köşeyi birden yuvarladığı ve
    oranı kısa kenara göre aldığı için (büyük kartta ~100pt → metin köşe dışında
    kalıyordu) kart yolu elde kurulur.
    """
    radius = min(_TOPIC_RADIUS_PT, rect.width / 2 - 0.5, rect.height / 2 - 0.5)
    control = 0.5523 * radius  # çeyrek daire yaklaşımı (cubic bezier)
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    shape = page.new_shape()
    right_start = y0 + radius
    right_end = y1 - radius if round_bottom else y1
    left_end = y0 + radius if round_top else y0
    left_end_b = y1 - radius
    arc = shape.draw_bezier  # kısa ad: çeyrek daire yayları
    if round_top:
        arc(
            (x0, left_end),
            (x0, left_end - control),
            (x0 + radius - control, y0),
            (x0 + radius, y0),
        )
        shape.draw_line((x0 + radius, y0), (x1 - radius, y0))
        arc(
            (x1 - radius, y0),
            (x1 - radius + control, y0),
            (x1, right_start - control),
            (x1, right_start),
        )
    else:
        shape.draw_line((x0, y0), (x1, y0))
    shape.draw_line((x1, left_end), (x1, right_end))
    if round_bottom:
        arc(
            (x1, right_end),
            (x1, right_end + control),
            (x1 - radius + control, y1),
            (x1 - radius, y1),
        )
        shape.draw_line((x1 - radius, y1), (x0 + radius, y1))
        arc(
            (x0 + radius, y1),
            (x0 + radius - control, y1),
            (x0, y1 - radius + control),
            (x0, left_end_b),
        )
    else:
        shape.draw_line((x1, y1), (x0, y1))
    left_top = (x0, y0 + radius) if round_top else (x0, y0)
    left_bottom = (x0, y1 - radius) if round_bottom else (x0, y1)
    shape.draw_line(left_top, left_bottom)
    shape.finish(
        color=palette["card_border"],
        fill=palette["card_fill"],
        width=0.7,
        fill_opacity=palette["card_opacity"],
        closePath=True,
    )
    shape.commit()


def _draw_topic_cards(
    page: pymupdf.Page,
    text_page: pymupdf.Page,
    palette: dict,
    content_top: float,
    open_topic: bool,
    boxes: list[pymupdf.Rect],
    is_last_page: bool,
) -> bool:
    """Konu kartlarını çizer; kart sayfa sonunda AÇIK kalıyorsa True döner.

    Kapanış kuralı (kullanıcı, v4): kart bir sonraki konu başlığına kadar kapanmaz.
    Sayfa sınırında kesilen kenar DÜZ çizilir, devamı yeni sayfada DÜZ başlar; kart
    yalnız sonraki başlıkta ya da belgenin son sayfasında yuvarlak kapanır. Karar
    sayfa doluluğuna değil BELGE YAPISINA bağlıdır (doluluk sezgisi dijital varyantta
    devam kartını düşürüyordu — 2026-09-17 ölçümü).
    """
    blocks = [
        b
        for b in text_page.get_text("dict")["blocks"]
        if b.get("lines") and b["bbox"][3] > content_top
    ]
    if not blocks:
        return open_topic and not is_last_page
    cut_bottom = page.rect.height - _MARGIN_BOTTOM  # kesilen kart sayfa sonuna kadar gider
    text_bottom = min(max(b["bbox"][3] for b in blocks) + _TOPIC_PAD_Y, cut_bottom)
    segments: list[tuple[float, float, bool, bool]] = []
    if open_topic:
        if boxes:
            segments.append((content_top, boxes[0].y0 - _TOPIC_GAP, False, True))
        else:
            flat_bottom = text_bottom if is_last_page else cut_bottom
            segments.append((content_top, flat_bottom, False, is_last_page))
    for index, box in enumerate(boxes):
        last = index == len(boxes) - 1
        if last:
            close = is_last_page  # sonraki başlık yoksa kart belge sonunda kapanır
            bottom = text_bottom if close else cut_bottom
            segments.append((box.y0 - _TOPIC_PAD_Y, bottom, True, close))
        else:
            segments.append((box.y0 - _TOPIC_PAD_Y, boxes[index + 1].y0 - _TOPIC_GAP, True, True))
    right = page.rect.width - _MARGIN
    for top, bottom, round_top, round_bottom in segments:
        if bottom - top < 2:
            continue
        _card_shape(
            page,
            pymupdf.Rect(_MARGIN, max(top, content_top), right, bottom),
            palette,
            round_top,
            round_bottom,
        )
    return (bool(boxes) or open_topic) and not is_last_page


def _split_title(title: str) -> tuple[str, str]:
    """Belge başlığını (ders, chapter) olarak ayırır — router "ders · chapter" verir."""
    parts = [part.strip() for part in (title or "Not").split("·")]
    if len(parts) >= 2:
        return parts[0], " · ".join(parts[1:])
    return "", parts[0]


def _clip(value: str, limit: int = 64) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _upper_tr(text: str) -> str:
    """Türkçe büyük harf: 'i' → 'İ', 'ı' → 'I' (Python'un str.upper()'ı 'i'yi 'I' yapar)."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def _line(page, x0, y0, x1, y1, color, width=0.7) -> None:
    page.draw_line(pymupdf.Point(x0, y0), pymupdf.Point(x1, y1), color=color, width=width)


def _text_right(page, right, y, value, font_path, size, color, weight="regular") -> None:
    """Sağa hizalı metin — genişlik font metrikleriyle ölçülür."""
    x = right - _text_width(value, font_path, size)
    _text(page, x, y, value, font_path, size, color, weight)


def _draw_brand_header(
    page: pymupdf.Page,
    page_rect: pymupdf.Rect,
    title: str,
    variant: str,
    logo_path: Path,
    regular_path: str,
    bold_path: str,
    style: str | None = None,
) -> None:
    """1. sayfa marka header'ı — kullanıcının seçeceği üç stil (V1/V2/V3).

    Referans: uygulamanın kendi header dili (AppHeader.tsx + theme.css `.app-header`:
    cam yüzey, ince kenar ışığı, logo + wordmark). PDF'te blur/backdrop-filter yok;
    cam hissi katmanlı çizimle (dolgu + üst ışık çizgisi + kenar) kurulur.
    """
    style = style or HEADER_STYLE
    top, height, _ = _header_box(variant, style)
    eyebrow, main = _split_title(title)
    eyebrow, main = _clip(eyebrow), _clip(main)
    drawer = _HEADER_DRAWERS[(variant, style)]
    drawer(page, page_rect, top, height, eyebrow, main, logo_path, regular_path, bold_path)


def _logo(page: pymupdf.Page, x: float, y: float, height: float, logo_path: Path) -> float:
    """Logoyu verilen sol-üst köşeye basar; kapladığı genişliği döner (2:1 en-boy)."""
    width = height * 2
    if logo_path.exists():
        page.insert_image(
            pymupdf.Rect(x, y, x + width, y + height),
            filename=str(logo_path),
            keep_proportion=True,
        )
    return width


# --- Dijital header stilleri -------------------------------------------------
def _header_digital_v1(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V1 — cam panel: yuvarlak glass kart, logo + eyebrow (ders) + chapter + imza."""
    colors = _HEADER_TEXT["digital"]
    left, right = _MARGIN, page_rect.width - _MARGIN
    page.draw_rect(
        pymupdf.Rect(left, top, right, top + height),
        color=colors["rule"],
        fill=(0.071, 0.071, 0.082),
        width=0.7,
        radius=0.2,
    )
    # Üst kenar ışığı (app `--glass-inner-light`): yuvarlak köşelerden uzak, kısa çizgi.
    _line(page, left + 26, top + 0.8, right - 26, top + 0.8, (0.30, 0.30, 0.34), 0.8)
    logo_h = 24.0
    logo_w = _logo(page, left + 16, top + (height - logo_h) / 2, logo_h, logo_path)
    text_x = left + 16 + logo_w + 16
    if eyebrow:
        _text(page, text_x, top + 22, _upper_tr(eyebrow), regular, 7.5, colors["eyebrow"])
    _text(page, text_x, top + 36, main, bold, 13, colors["title"], "bold")
    _text(page, text_x, top + 50, "StuHub ile hazırlandı", regular, 8, colors["tagline"])


def _header_digital_v2(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V2 — app header eşleniği: tam genişlik koyu şerit, ortada logo + wordmark."""
    colors = _HEADER_TEXT["digital"]
    width = page_rect.width
    page.draw_rect(
        pymupdf.Rect(0, top, width, top + height), color=None, fill=(0.02, 0.02, 0.024)
    )
    _line(page, 0, top + height, width, top + height, colors["rule"], 0.8)
    logo_h = 22.0
    mark_w = logo_h * 2
    wordmark = "StuHub"
    group_w = mark_w + 8 + _text_width(wordmark, bold, 13)
    x = (width - group_w) / 2
    _logo(page, x, top + 16, logo_h, logo_path)
    _text(page, x + mark_w + 8, top + 32, wordmark, bold, 13, colors["title"], "bold")
    line = f"{eyebrow} · {main}" if eyebrow else main
    line_w = _text_width(line, regular, 9)
    _text(page, (width - line_w) / 2, top + 56, line, regular, 9, colors["tagline"])


def _header_digital_v3(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V3 — panel yok: eyebrow (ders) + büyük chapter solda, imza sağda, accent hairline."""
    colors = _HEADER_TEXT["digital"]
    left, right = _MARGIN, page_rect.width - _MARGIN
    logo_w = _logo(page, left, top, 26.0, logo_path)
    text_x = left + logo_w + 18
    if eyebrow:
        _text(page, text_x, top + 11, _upper_tr(eyebrow), regular, 8, colors["eyebrow"])
    _text(page, text_x, top + 30, main, bold, 16, colors["title"], "bold")
    _text_right(page, right, top + 30, "StuHub ile hazırlandı", regular, 8, colors["tagline"])
    _line(page, left, top + height, right, top + height, colors["rule"], 0.7)
    # Accent vurgu: başlığın altında kısa kum çizgisi (marka tonu, baskı dostu).
    _line(page, left, top + height, left + 64, top + height, (0.84, 0.79, 0.66), 1.6)


# --- Fiziksel header stilleri ------------------------------------------------
def _header_physical_v1(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V1 — asimetrik: logo solda geniş alan, meta sağa hizalı, çizgi yerine ton geçişi."""
    colors = _HEADER_TEXT["physical"]
    left, right = _MARGIN, page_rect.width - _MARGIN
    strips = 6  # kâğıtta yumuşak ton geçişi (mürekkep dostu, çok açık)
    for index in range(strips):
        tone = 1 - (index + 1) / strips * 0.08
        y0 = top + index * height / strips
        y1 = top + (index + 1) * height / strips
        page.draw_rect(
            pymupdf.Rect(left, y0, right, y1), color=None, fill=(tone, tone - 0.004, tone - 0.022)
        )
    logo_h = 26.0
    logo_w = _logo(page, left + 12, top + (height - logo_h) / 2, logo_h, logo_path)
    if eyebrow:
        _text_right(page, right - 12, top + 20, _upper_tr(eyebrow), regular, 7.5, colors["eyebrow"])
    _text_right(page, right - 12, top + 38, main, bold, 14, colors["title"], "bold")
    _text(
        page,
        left + 12 + logo_w + 12,
        top + height - 10,
        "StuHub ile hazırlandı",
        regular,
        8,
        colors["tagline"],
    )


def _header_physical_v2(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V2 — eyebrow sol: ders adı küçük üst satır, chapter büyük; logo sağda."""
    colors = _HEADER_TEXT["physical"]
    left, right = _MARGIN, page_rect.width - _MARGIN
    logo_w = 24.0 * 2
    _logo(page, right - logo_w, top + (height - 24.0) / 2, 24.0, logo_path)
    if eyebrow:
        _text(page, left, top + 14, _upper_tr(eyebrow), regular, 8, colors["eyebrow"])
    _text(page, left, top + 34, main, bold, 15, colors["title"], "bold")
    _text(page, left, top + 48, "StuHub ile hazırlandı", regular, 8, colors["tagline"])
    _line(page, left, top + height, right, top + height, colors["rule"], 0.8)
    _line(page, left, top + height, left + 56, top + height, (0.84, 0.79, 0.66), 1.6)


def _header_physical_v3(page, page_rect, top, height, eyebrow, main, logo_path, regular, bold):
    """V3 — split kolon: solda logo + wordmark (dikey ayraç), sağda eyebrow + başlık."""
    colors = _HEADER_TEXT["physical"]
    left = _MARGIN
    _logo(page, left, top + 4, 26.0, logo_path)
    _text(page, left, top + 44, "StuHub", bold, 9, colors["title"], "bold")
    divider = left + 116
    _line(page, divider, top + 2, divider, top + height - 6, colors["rule"], 0.7)
    text_x = divider + 18
    if eyebrow:
        _text(page, text_x, top + 16, _upper_tr(eyebrow), regular, 7.5, colors["eyebrow"])
    _text(page, text_x, top + 36, main, bold, 14, colors["title"], "bold")
    _text(page, text_x, top + 52, "StuHub ile hazırlandı", regular, 8, colors["tagline"])


_HEADER_DRAWERS = {
    ("digital", "v1"): _header_digital_v1,
    ("digital", "v2"): _header_digital_v2,
    ("digital", "v3"): _header_digital_v3,
    ("physical", "v1"): _header_physical_v1,
    ("physical", "v2"): _header_physical_v2,
    ("physical", "v3"): _header_physical_v3,
}


def _draw_footer(
    page: pymupdf.Page,
    page_rect: pymupdf.Rect,
    number: int,
    variant: str,
    regular_path: str,
) -> None:
    """Footer: sol "StuHub · tarih" alt bilgisi, sağ sayfa numarası — takibin tek yeri."""
    color = _PALETTE[variant]["footer"]
    y = page_rect.height - _FOOTER_BASELINE
    _text(page, _MARGIN, y, f"StuHub · {date.today().strftime('%d.%m.%Y')}", regular_path, 8, color)
    # Sağa hizalı sayfa numarası: metin genişliği fontla ölçülür (sabit ofset yok).
    number_text = str(number)
    number_w = pymupdf.Font(fontfile=str(regular_path)).text_length(number_text, fontsize=8)
    page.insert_text(
        pymupdf.Point(page_rect.width - _MARGIN - number_w, y),
        number_text,
        fontname=_CHART_FONTS["regular"],
        fontfile=str(regular_path),
        fontsize=8,
        color=color,
        overlay=True,
    )


def note_markdown_to_md(title: str, content_md: str) -> str:
    """Notu Markdown olarak döner: başlık + content_md birebir (Yetenek 12 Format 1)."""
    return f"# {title}\n\n{content_md}\n"

