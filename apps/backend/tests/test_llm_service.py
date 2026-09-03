"""LLM servisi testleri — mock istemci ile stream/retry/sağlayıcı devri (geçici ücretsiz zincir)."""

from types import SimpleNamespace

import pytest

from src.services import llm_service


@pytest.fixture(autouse=True)
async def _tmp_db(tmp_path, monkeypatch):
    """generation_logs şeması için geçici veri dizini."""
    monkeypatch.setattr(llm_service.settings, "data_dir", tmp_path)
    from src.db import init_db

    await init_db()


@pytest.fixture(autouse=True)
def reset_delays(monkeypatch):
    monkeypatch.setattr(llm_service, "BASE_DELAY", 0.01)
    monkeypatch.setattr(llm_service, "MAX_BACKOFF_DELAY", 0.02)


def _chunk(text: str, usage=None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))],
        usage=usage,
    )


class _ApiError(Exception):
    """`openai` SDK'sının fırlattığı `APIStatusError` benzeri, `status_code` taşıyan hata."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"api error {status_code}")
        self.status_code = status_code


class _FakeCompletions:
    def __init__(self, responses: list):
        self.responses = list(responses)

    async def create(self, **kwargs):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, responses: list):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def _fake_client(responses: list) -> _FakeClient:
    return _FakeClient(responses)


def _single_provider_client(monkeypatch, client) -> None:
    """Yalnızca Gemini (zincirin ilki) yapılandırılmış, her sağlayıcı isteği aynı fake client'a gider."""
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    monkeypatch.setattr(llm_service, "_client_for", lambda provider: client)


async def _collect_stream(agen) -> str:
    parts = []
    async for part in agen:
        parts.append(part)
    return "".join(parts)


async def test_no_key_raises_turkish_error():
    with pytest.raises(llm_service.LLMError, match="yapılandırılmadı"):
        await _collect_stream(
            llm_service.chat_stream([{"role": "user", "content": "merhaba"}])
        )


async def test_chat_stream_yields_text_and_logs(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=7)
    stream = [  # async iterable
        _chunk("Merhaba ", None),
        _chunk("dünya", None),
        _chunk("", usage),
    ]

    async def _agen():
        for item in stream:
            yield item

    client = _fake_client([_agen()])
    _single_provider_client(monkeypatch, client)

    text = await _collect_stream(
        llm_service.chat_stream(
            [{"role": "user", "content": "selam"}], kind="test", course_id=1, chapter_id=2
        )
    )
    assert text == "Merhaba dünya"
    # generation_logs kaydı
    import aiosqlite

    async with aiosqlite.connect(llm_service.settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT kind, model, provider, prompt_tokens, completion_tokens FROM generation_logs"
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "test"
    assert row[2] == "gemini"
    assert row[3] == 12 and row[4] == 7


async def test_chat_stream_retries_on_429(monkeypatch):
    """Dakikalık limit gibi görünen 429 aynı sağlayıcıda kısa retry ile atlatılır."""
    err = _ApiError(429)
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    stream = [_chunk("ikinci deneme", usage)]

    async def _agen():
        for item in stream:
            yield item

    client = _fake_client([err, _agen()])
    _single_provider_client(monkeypatch, client)

    text = await _collect_stream(
        llm_service.chat_stream([{"role": "user", "content": "x"}], kind="test")
    )
    assert text == "ikinci deneme"
    # tek deneme sonrası kurtuldu → sağlayıcı cooldown'a alınmadı
    assert await llm_service._load_cooldowns() == {}


async def test_chat_stream_gives_up_after_max_retries(monkeypatch):
    err = _ApiError(500)
    client = _fake_client([err] * 10)  # her denemede hata
    _single_provider_client(monkeypatch, client)
    with pytest.raises(llm_service.LLMError, match="kullanılamıyor|başarısız"):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "x"}]))
    # 5xx geçici sayılır → cooldown'a alınmaz (yalnızca sağlayıcı tükendi)
    assert await llm_service._load_cooldowns() == {}


async def test_quota_exhausted_marks_provider_cooldown(monkeypatch):
    """401/403/402/429 tüm retry'lardan sonra da sürerse sağlayıcı ertesi güne kadar cooldown'a alınır."""
    err = _ApiError(429)
    client = _fake_client([err] * 10)
    _single_provider_client(monkeypatch, client)
    with pytest.raises(llm_service.LLMError):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "x"}]))
    cooldowns = await llm_service._load_cooldowns()
    assert "gemini" in cooldowns
    # aynı çağrı hemen tekrar denense de (tek sağlayıcı, cooldown'da) hâlâ hata verir
    with pytest.raises(llm_service.LLMError):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "y"}]))


async def test_falls_back_to_next_provider_on_quota_exhaustion(monkeypatch):
    """Gemini kotası tükenince zincirdeki bir sonraki sağlayıcıya (OpenRouter) otomatik geçilir."""
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-gemini")
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "sk-openrouter")

    err = _ApiError(429)
    gemini_client = _fake_client([err] * 10)

    usage = SimpleNamespace(prompt_tokens=3, completion_tokens=4)

    async def _agen():
        yield _chunk("openrouter yanıtı", usage)

    openrouter_client = _fake_client([_agen()])

    clients = {"gemini": gemini_client, "openrouter": openrouter_client}
    monkeypatch.setattr(llm_service, "_client_for", lambda provider: clients[provider.name])

    text = await _collect_stream(
        llm_service.chat_stream([{"role": "user", "content": "x"}], kind="test")
    )
    assert text == "openrouter yanıtı"

    cooldowns = await llm_service._load_cooldowns()
    assert "gemini" in cooldowns
    assert "openrouter" not in cooldowns

    import aiosqlite

    async with aiosqlite.connect(llm_service.settings.db_path) as conn:
        cursor = await conn.execute("SELECT provider FROM generation_logs")
        row = await cursor.fetchone()
    assert row[0] == "openrouter"


async def test_chat_json_returns_dict(monkeypatch):
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
    )

    class _FakeCompletionsJson:
        async def create(self, **kwargs):
            return resp

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    _single_provider_client(monkeypatch, client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": True}


async def test_chat_json_invalid_then_valid(monkeypatch):
    class _FakeCompletionsJson:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            content = "geçersiz" if self.calls == 1 else '{"ok": 1}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    _single_provider_client(monkeypatch, client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": 1}


async def test_chat_json_extracts_fenced_json(monkeypatch):
    """Model ```json fence içinde döndürse de dayanıklı ayrıştırma çalışmalı."""
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='Açıklama:\n```json\n{"ok": 1}\n```\nBitti.')
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )

    class _FakeCompletionsJson:
        async def create(self, **kwargs):
            return resp

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    _single_provider_client(monkeypatch, client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": 1}


async def test_chat_json_recovers_from_garbage_then_valid(monkeypatch):
    """Ardışık geçersiz yanıtlardan sonra geçerli JSON ile kendini onarır."""
    calls = {"count": 0}

    class _FakeCompletionsJson:
        async def create(self, **kwargs):
            calls["count"] += 1
            content = "bunlar json değil" if calls["count"] == 1 else '{"ok": true}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    _single_provider_client(monkeypatch, client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": True}
    assert calls["count"] == 2


async def test_chat_json_falls_back_to_next_provider_on_auth_error(monkeypatch):
    """401 (geçersiz anahtar) retry beklemeden hemen sıradaki sağlayıcıya düşer."""
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-gemini")
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "sk-openrouter")

    err = _ApiError(401)
    gemini_client = _fake_client([err])

    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=2),
    )

    class _FakeCompletionsJson:
        async def create(self, **kwargs):
            return resp

    openrouter_client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))

    clients = {"gemini": gemini_client, "openrouter": openrouter_client}
    monkeypatch.setattr(llm_service, "_client_for", lambda provider: clients[provider.name])

    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": True}
    cooldowns = await llm_service._load_cooldowns()
    assert "gemini" in cooldowns
