"""LLM servisi testleri — mock istemci ile stream/retry/circuit-breaker (Faz 3.1)."""

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
def reset_breaker(monkeypatch):
    monkeypatch.setattr(llm_service, "_breaker", {"failures": 0, "open_until": 0.0})
    monkeypatch.setattr(llm_service, "BASE_DELAY", 0.01)
    monkeypatch.setattr(llm_service, "MAX_BACKOFF_DELAY", 0.02)


def _chunk(text: str, usage=None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))],
        usage=usage,
    )


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


async def _collect_stream(agen) -> str:
    parts = []
    async for part in agen:
        parts.append(part)
    return "".join(parts)


async def test_no_key_raises_turkish_error(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "")
    with pytest.raises(llm_service.LLMError, match="API anahtarı ayarlanmadı"):
        await _collect_stream(
            llm_service.chat_stream([{"role": "user", "content": "merhaba"}])
        )


async def test_chat_stream_yields_text_and_logs(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
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
    monkeypatch.setattr(llm_service, "_client", lambda: client)

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
            "SELECT kind, model, prompt_tokens, completion_tokens FROM generation_logs"
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "test"
    assert row[2] == 12 and row[3] == 7


async def test_chat_stream_retries_on_429(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    err = SimpleNamespace(status_code=429)
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    stream = [_chunk("ikinci deneme", usage)]

    async def _agen():
        for item in stream:
            yield item

    client = _fake_client([err, _agen()])
    monkeypatch.setattr(llm_service, "_client", lambda: client)

    text = await _collect_stream(
        llm_service.chat_stream([{"role": "user", "content": "x"}], kind="test")
    )
    assert text == "ikinci deneme"


async def test_chat_stream_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    err = SimpleNamespace(status_code=500)
    client = _fake_client([err] * 10)  # her denemede hata
    monkeypatch.setattr(llm_service, "_client", lambda: client)
    with pytest.raises(llm_service.LLMError, match="kullanılamıyor|başarısız"):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "x"}]))


async def test_circuit_breaker_opens(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    err = SimpleNamespace(status_code=500)
    client = _fake_client([err] * 10)
    monkeypatch.setattr(llm_service, "_client", lambda: client)
    with pytest.raises(llm_service.LLMError):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "x"}]))
    # breaker açık → hemen hata
    monkeypatch.setattr(llm_service, "_client", lambda: _fake_client([_chunk("yeni")]))
    with pytest.raises(llm_service.LLMError, match="çok fazla hatalı istek"):
        await _collect_stream(llm_service.chat_stream([{"role": "user", "content": "y"}]))


async def test_chat_json_returns_dict(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
    )

    class _FakeCompletionsJson:
        async def create(self, **kwargs):
            return resp

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    monkeypatch.setattr(llm_service, "_client", lambda: client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": True}


async def test_chat_json_invalid_then_valid(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "deepseek_api_key", "sk-test")

    class _FakeCompletionsJson:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            content = 'geçersiz' if self.calls == 1 else '{"ok": 1}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletionsJson()))
    monkeypatch.setattr(llm_service, "_client", lambda: client)
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
    monkeypatch.setattr(llm_service, "_client", lambda: client)
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
    monkeypatch.setattr(llm_service, "_client", lambda: client)
    data = await llm_service.chat_json([{"role": "user", "content": "json üret"}])
    assert data == {"ok": True}
    assert calls["count"] == 2
