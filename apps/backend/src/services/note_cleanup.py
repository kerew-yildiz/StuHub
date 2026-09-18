"""Model çıktısı normalizasyonu — JSON zarfı soyma, kaçış/çit temizliği (2026-09-18).

Model markdown yerine JSON zarfı döndürebiliyor:

    ```json
    {"content": "### Konu\\n\\nMetin [1]\\n"}
    ```

Ham hâliyle kaydedilirse not ekranında JSON görünür: ```` ```json ```` çiti notun
TAMAMINI tek kod bloğuna çevirir, bu yüzden markdown işaretleri (`**kalın**`, `[1]`)
ve `\\n` kaçışları da ham basılır (2026-09-18 kullanıcı vakası: gemini
`note_generation_slide_only` akışı `{"content": ...}` zarfı döndürdü, not 22 ham
JSON olarak kaydedildi ve ekranda ham göründü).

Bu modül gelen metni normalize eder: JSON zarfını soyar, `{"content": ...}` /
`{"markdown": ...}` / `{"sections": [...]}` biçimlerini açar, kaçış dizilerini
çözer, JSON olmayan gerçek kod çitlerini KORUR. Düzgün markdown hızlı yoldan
değişmeden geçer (zarfsız metne dokunulmaz).

Aynı fonksiyonun TS eşi: `apps/frontend/src/lib/noteCleanup.ts` — son savunma
hattı (render öncesi); iki taraf AYNI örneklerle test edilir.
"""

from __future__ import annotations

import json
import re

# Zarf göstergesi: bir içerik anahtarı JSON anahtarı olarak geçiyor mu?
_ENVELOPE_HINT_RE = re.compile(
    r"""["'](?:content|markdown|markdown_content|note|text|body|answer|[iı]çerik)["']\s*:""",
    re.IGNORECASE,
)

# Kod çiti — ```` ```json ```` / ```` ``` ```` (dil etiketi isteğe bağlı, satır sonu isteğe bağlı).
_FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n?(.*?)```", re.DOTALL)

# ```` ```json ```` ile başlayan çit: model çıktısı sayılır (kullanıcı içeriği değil).
_JSON_FENCE_RE = re.compile(r"```[ \t]*json[ \t]*\n", re.IGNORECASE)

# Zarf içindeki markdown'ı taşıyan anahtarlar (model çıktısında görülen adlar).
_CONTENT_KEYS = (
    "content",
    "markdown",
    "markdown_content",
    "note",
    "text",
    "body",
    "answer",
    "icerik",
    "içerik",
    "bolum",
    "bölüm",
)
# İçeriği alt nesnelerde taşıyan zarf biçimleri.
_LIST_KEYS = ("sections", "topics", "parts", "items", "chunks")

_MAX_DEPTH = 4
"""İç içe zarf koruması (özyineleme sınırı)."""

_ESCAPE_RE = re.compile(r"\\(.)")
_ESCAPE_MAP = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'", "\\": "\\", "/": "/"}
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

# Cümle sonuna YAPIŞMIŞ başlık: `... [2].### Oral Dönem` (markdown olarak render edilmez).
_GLUED_HEADING_RE = re.compile(r"""([.!?:;)\]"'”’])[ \t]*(#{2,4})[ \t]+""")


def _split_glued_headings(text: str) -> str:
    """Cümle sonuna yapışmış markdown başlığını ayırır (`.### X` → `.\\n\\n### X`).

    `note_generator._replace_section` yeniden üretim turlarında yeni bloğu bölüm
    ayırıcısı olmadan yerleştiriyordu: paragrafın devamına yapışan `### Konu` başlığı
    markdown olarak render EDİLMEZ, ekranda düz metin (`... [2].### Oral Dönem`)
    olarak görünür (2026-09-18 kullanıcı notlarının 9'unda bu iz var). Yalnızca cümle
    noktalama işaretinden hemen sonra gelen 2-4 `#` ayırılır — metin içi `#`
    (ör. `C#`, URL çapası) etkilenmez.
    """
    return _GLUED_HEADING_RE.sub(lambda m: f"{m.group(1)}\n\n{m.group(2)} ", text)


def normalize_note_markdown(text: str, _depth: int = 0) -> str:
    """Model yanıtını temiz markdown'a çevirir.

    - JSON zarfı (kod çitli ya da çıplak) → içindeki markdown
    - art arda gelen birden çok zarf → sırayla birleştirilir
    - zarf içinde olmayan kaçışlı metin (`\\n`) → gerçek satır sonları
    - JSON olmayan kod çitleri ve düz markdown → DEĞİŞMEZ

    Zarf açıldıktan sonra içerik anahtarı taşımayan JSON nesneleri (ör. modelin
    konuya eklediği `{"topic": ..., "summary": ...}` dökümü) düşürülür — bkz.
    `_scan`. Hiçbir şey çıkarılamazsa boş string döner (çağıran taraf yedeğe düşer);
    bu, ham JSON basmaktan her zaman daha iyidir.
    """
    if not text or not text.strip():
        return text or ""
    if _depth > _MAX_DEPTH:
        return text.strip()

    stripped = text.strip()
    if not _looks_like_envelope(stripped):
        # Hızlı yol: düzgün markdown. Yalnızca satır sonu kaçışı varsa çözülür.
        return _split_glued_headings(_decode_escaped_text(stripped))

    pieces = _scan(stripped)
    joined = "\n\n".join(piece for piece in pieces if piece.strip())
    cleaned = re.sub(r"\n{3,}", "\n\n", _dedupe_headings(joined)).strip()
    return _split_glued_headings(cleaned)


def _dedupe_headings(text: str) -> str:
    """Yinelenen ardışık başlıkları tekleştirir.

    Zarf soyma ile `_ensure_topic_heading`/`_replace_section` çakışınca bölüm başlığı
    iki kez görünür (`### Konu` + zarf içindeki `### Konu`).
    """
    lines: list[str] = []
    last_heading: str | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and stripped == last_heading:
            continue
        if stripped:
            last_heading = stripped if stripped.startswith("#") else None
        lines.append(line)
    return "\n".join(lines).strip()


def _looks_like_envelope(text: str) -> bool:
    """Metin JSON zarfı içeriyor/olabilir mi? (hızlı yol kapısı)"""
    if _ENVELOPE_HINT_RE.search(text):
        return True
    if text.startswith("```"):
        # Bölüm doğrudan kod çitiyle başlıyor: JSON zarfı olabilir (JSON olmayan
        # çitler `_scan` içinde aynen korunur).
        return True
    if text[0] in "{[":
        return _json_prefix(text) is not None
    if _JSON_FENCE_RE.search(text):
        # ```` ```json ```` çitli bir blok: model çıktısı sayılır (gerçek kod örnekleri
        # dilsiz/başka etiketli çitlerde korunur).
        return True
    return len(text) >= 2 and text[0] == '"' and text[-1] == '"'


def _scan(text: str) -> list[str]:
    """Metni kod çitlerine göre parçalar; zarf çitlerini markdown'a çevirir.

    ```` ```json ```` çitinin gövdesi JSON ama içerik anahtarı yoksa (modelin konuya
    eklediği `{"topic": ..., "summary": ...}` dökümü) blok DÜŞÜRÜLÜR — ham JSON ekrana
    çıkmaz. Etiketsiz/başka dilli çitler gerçek kod bloğu sayılır ve aynen korunur.
    """
    pieces: list[str] = []
    position = 0
    for match in _FENCE_RE.finditer(text):
        pieces.extend(_plain_pieces(text[position : match.start()]))
        inner = _markdown_from_json_text(match.group(2))
        if inner is None:
            pieces.append(match.group(0))  # JSON değil: gerçek kod bloğu
        elif inner.strip():
            pieces.append(inner)
        elif match.group(1).strip().lower() != "json":
            pieces.append(match.group(0))  # içerik anahtarı yok ama JSON çiti değil
        position = match.end()
    pieces.extend(_plain_pieces(text[position:]))
    return pieces


def _plain_pieces(segment: str) -> list[str]:
    """Çit DIŞINDAKİ parça: başında JSON varsa soyar, kalanı markdown kabul eder."""
    text = segment.strip()
    if text.startswith("```"):
        # Kapanmamış çit (kesik yanıt) — açılış satırını at, gövdeyi normal işle.
        head, _, tail = text.partition("\n")
        text = tail.strip() if head.strip().startswith("```") else text
        if not text:
            return []
    if not text:
        return []
    if text[0] in "{[":
        decoded = _json_prefix(text)
        if decoded is not None:
            value, rest = decoded
            inner = value if isinstance(value, str) else _markdown_from_json(value)
            pieces = [inner] if inner.strip() else []
            return pieces + _plain_pieces(rest)
        truncated = _truncated_envelope_markdown(text)
        if truncated is not None:
            return [truncated]
    return [_decode_escaped_text(text)]


_TRUNCATED_ENVELOPE_RE = re.compile(r'^\{\s*"([A-Za-z_]+)"\s*:\s*"')


def _truncated_envelope_markdown(text: str) -> str | None:
    """Token bütçesi kesilen zarf: `{"content": "### Konu\\n...` → `### Konu\\n...`.

    Kapanış parantezi/tırnağı olmadığı için `json.loads` başarısız olur; bu, not
    üretiminde kayıtlı bir kesilme biçimidir (`finish_reason=length`) ve ham JSON
    olarak kaydedilirse aynı ekran hatasını üretir.
    """
    match = _TRUNCATED_ENVELOPE_RE.match(text)
    if not match or match.group(1).lower() not in _CONTENT_KEYS:
        return None
    body = text[match.end() :]
    body = re.sub(r'"\s*\}?\s*$', "", body)
    return _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP.get(m.group(1), m.group(1)), body).strip()


def _json_prefix(text: str) -> tuple[object, str] | None:
    """Metnin BAŞINDAKİ JSON değerini ve kalanını döner (yoksa None).

    Art arda gelen nesneler (`{...}{...}`) bu sayede sırayla çözülür.
    """
    try:
        value, end = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return None
    return value, text[end:]


def _markdown_from_json_text(text: str) -> str | None:
    """Kod çiti gövdesi JSON mu? JSON ise markdown'ı, değilse None döner."""
    body = text.strip()
    if not body or body[0] not in '{["':
        return None
    try:
        value = json.loads(body)
    except ValueError:
        return None
    if isinstance(value, str):
        return _decode_escaped_text(value)
    return _markdown_from_json(value)


def _markdown_from_json(value: object, depth: int = 0) -> str:
    """JSON değerinden markdown çıkarır; içerik anahtarı yoksa boş string."""
    if depth > _MAX_DEPTH:
        return ""
    if isinstance(value, str):
        if _looks_like_envelope(value.strip()):
            return normalize_note_markdown(value, depth + 1)
        return value
    if isinstance(value, list):
        parts = [_markdown_from_json(item, depth + 1) for item in value]
        return "\n\n".join(part for part in parts if part.strip())
    if isinstance(value, dict):
        for key in _CONTENT_KEYS:
            if key in value:
                inner = _markdown_from_json(value[key], depth + 1)
                if inner.strip():
                    return inner
        for key in _LIST_KEYS:
            if isinstance(value.get(key), list):
                inner = _markdown_from_json(value[key], depth + 1)
                if inner.strip():
                    return inner
        return ""
    return ""


def _decode_escaped_text(text: str) -> str:
    """Kaçışlı metni çözer — ama YALNIZCA metinde gerçek satır sonu yoksa.

    json.loads zarf içindeki kaçışları zaten çözer; bu fonksiyon zarf DIŞINDA kalan
    (ör. `"### Konu\\n\\nMetin"` gibi tırnaklı ya da düz) metin içindir. Gerçek satır
    sonu taşıyan markdown'a dokunulmaz — aksi hâlde markdown içindeki `\\` kullanımları
    bozulurdu.
    """
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        try:
            value = json.loads(stripped)
        except ValueError:
            value = None
        if isinstance(value, str):
            return value
    if "\n" in stripped or "\\n" not in stripped:
        return stripped
    decoded = _UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), stripped)
    return _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP.get(m.group(1), m.group(1)), decoded)


class SectionStream:
    """Bölüm akışı tamponu — yarım JSON'un canlı önizlemeye sızmasını engeller.

    Model düz markdown yazıyorsa (yaygın yol) deltalar geldiği gibi geçer: kullanıcı
    akışı eskisi gibi harf harf görür. Metin `{` / `[` / ```` ``` ```` ile başlıyorsa
    (JSON zarfı şüphesi) tampon TUTULUR; bölüm bitince normalize edilmiş hâli tek parça
    yayınlanır — ekrana `{"content": "### ...` gibi ham parçalar düşmez.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._passthrough = False

    def feed(self, delta: str) -> str:
        """Deltayı tampona ekler; ŞİMDİ yayınlanacak metni döner (çoğu zaman delta)."""
        self._buffer += delta
        if self._passthrough:
            return delta
        head = self._buffer.lstrip()
        if not head:
            return ""
        if head.startswith(("{", "[", "```")):
            return ""  # karar bölüm sonunda verilir
        self._passthrough = True
        return self._buffer

    def cleaned(self) -> str:
        """Tamponun normalize edilmiş (yayına hazır) hâli."""
        return normalize_note_markdown(self._buffer).strip()
