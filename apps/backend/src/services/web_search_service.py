"""Web arama servisi — DuckDuckGo ile kaynak arama + sayfa indirme (not yedeği).

Kitapta kaynak yokken not üretimi için `{ders adı} {konu}` sorgusuyla web'de kaynak arar.
Arama/indirme başarısız olursa boş liste döner (hata FIRLATMAZ — üst katman slayt yedeğine
düşer). `ddgs` isteğe bağlı bir bağımlılıktır; kurulu değilse web araması kapalı kalır.
"""

from __future__ import annotations

import html
import logging
import re
import urllib.request
from urllib.parse import urlparse

from ..config import settings
from ..db import get_db

logger = logging.getLogger(__name__)

# ddgs isteğe bağlı bir bağımlılıktır; kurulu değilse web araması kapalı kalır.
try:
    from ddgs import DDGS
except ImportError:  # modül kurulu olmayabilir — web araması devre dışı kalır
    DDGS = None  # type: ignore[assignment]

MAX_TEXT_CHARS = 3000
QUOTE_CHARS = 240
DOWNLOAD_TIMEOUT = 8
_TAG_RE = re.compile(r"<[^>]+>")


def _safe_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _download_text(url: str) -> str | None:
    """URL'yi indirip HTML etiketlerinden arındırır; başarısızsa None döner."""
    if not _safe_url(url):
        return None
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:  # nosec B310 — yalnızca http(s)
            raw = response.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    return _strip_html(raw)[:MAX_TEXT_CHARS]


async def search_web(topic: str, course_name: str, max_results: int = 3) -> list[dict]:
    """Web'de `{ders adı} {konu}` sorgusuyla kaynak arar; sonuçları metne çevirir.

    Dönüş: [{"title", "url", "text", "quote"}]. Sonuç yoksa ya da tümü başarısızsa boş
    liste döner (hata FIRLATMAZ — üst katman slayt yedeğine düşer).
    """
    if DDGS is None:
        logger.warning("duckduckgo-search kurulu değil; web araması devre dışı")
        return []

    query = f"{course_name} {topic}"
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception:
        logger.exception("web araması başarısız: %s", query)
        return []

    out: list[dict] = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        href = result.get("href") or ""
        body = result.get("body") or ""
        title = result.get("title") or ""
        text = (_download_text(href) or body).strip()
        if not text:
            continue
        text = text[:MAX_TEXT_CHARS]
        out.append(
            {
                "title": title,
                "url": href,
                "text": text,
                "quote": text[:QUOTE_CHARS],
            }
        )
    return out


async def web_search_enabled() -> bool:
    """Web aramasının açık olup olmadığını döner.

    Öncelik: settings tablosundaki `web_search_enabled` anahtarı (yoksa env değerine
    düşer). Tablo değeri "false"/"0" → False; diğer değerler → True.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", ("web_search_enabled",)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is not None:
        raw = str(row["value"]).strip().lower()
        return raw not in ("false", "0")
    return settings.web_search_enabled
