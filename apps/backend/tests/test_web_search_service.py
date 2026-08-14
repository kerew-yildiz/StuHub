"""Web arama servisi testleri — DDGS ve urlopen mock'lu."""

from __future__ import annotations

from src.services import web_search_service


class _FakeResponse:
    def __init__(self, html: str):
        self._html = html.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._html


class FakeDDGS:
    def __init__(self, results: list[dict] | None = None, raise_error: bool = False):
        self.results = results or []
        self.raise_error = raise_error
        self.queries: list[tuple[str, int | None]] = []

    def text(self, query: str, max_results: int | None = None):
        self.queries.append((query, max_results))
        if self.raise_error:
            raise RuntimeError("bağlantı hatası")
        return list(self.results)


async def test_search_web_parses_and_downloads(monkeypatch):
    monkeypatch.setattr(
        web_search_service,
        "DDGS",
        lambda: FakeDDGS(
            [
                {
                    "title": "Bağlı Listeler",
                    "href": "https://example.com/liste",
                    "body": "snippet metni",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        web_search_service.urllib.request,
        "urlopen",
        lambda url, timeout=None: _FakeResponse(
            "<html><body><p>Zengin içerik paragrafı.</p></body></html>"
        ),
    )

    results = await web_search_service.search_web("Bağlı Listeler", "Veri Yapıları")
    assert len(results) == 1
    r = results[0]
    assert r["title"] == "Bağlı Listeler"
    assert r["url"] == "https://example.com/liste"
    assert "Zengin içerik paragrafı" in r["text"]
    assert r["quote"] == r["text"][:240]


async def test_download_strips_html_and_unescapes(monkeypatch):
    monkeypatch.setattr(
        web_search_service.urllib.request,
        "urlopen",
        lambda url, timeout=None: _FakeResponse("<h1>Başlık</h1><p>A &amp; B &lt;c&gt;</p>"),
    )
    text = web_search_service._download_text("https://example.com/x")
    assert text is not None
    assert "Başlık" in text
    assert "A & B <c>" in text
    # ham HTML etiketleri ayıklanır; entity'ler (e.g. &lt;) çözülür
    assert "<h1>" not in text and "<p>" not in text


async def test_search_web_all_downloads_fail_returns_empty(monkeypatch):
    monkeypatch.setattr(
        web_search_service,
        "DDGS",
        lambda: FakeDDGS(
            [
                {"title": "X", "href": "https://example.com/a", "body": ""},
                {"title": "Y", "href": "https://example.com/b", "body": ""},
            ]
        ),
    )

    def boom(url, timeout=None):
        raise OSError("indirilemedi")

    monkeypatch.setattr(web_search_service.urllib.request, "urlopen", boom)
    assert await web_search_service.search_web("konu", "ders") == []


async def test_search_web_ddgs_raises_returns_empty(monkeypatch):
    monkeypatch.setattr(web_search_service, "DDGS", lambda: FakeDDGS(raise_error=True))
    assert await web_search_service.search_web("konu", "ders") == []


async def test_search_web_import_missing_returns_empty(monkeypatch):
    monkeypatch.setattr(web_search_service, "DDGS", None)
    assert await web_search_service.search_web("konu", "ders") == []


async def test_web_search_enabled_table_priority(client):
    # tablo boş → env varsayılanı (True)
    assert await web_search_service.web_search_enabled() is True

    await client.put("/api/settings", json={"key": "web_search_enabled", "value": "false"})
    assert await web_search_service.web_search_enabled() is False

    await client.put("/api/settings", json={"key": "web_search_enabled", "value": "0"})
    assert await web_search_service.web_search_enabled() is False

    await client.put("/api/settings", json={"key": "web_search_enabled", "value": "1"})
    assert await web_search_service.web_search_enabled() is True


async def test_web_search_enabled_env_fallback(client, monkeypatch):
    monkeypatch.setattr(web_search_service.settings, "web_search_enabled", False)
    assert await web_search_service.web_search_enabled() is False
