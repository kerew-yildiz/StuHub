"""DeepSeek (OpenAI uyumlu) LLM istemcisi — stream, üstel backoff, circuit breaker (Faz 3.1).

- API anahtarı yalnızca `settings`'ten okunur; asla loglanmaz (yol haritası Bölüm 8).
- Her çağrı `generation_logs`'a yazılır (maliyet gözetimi — Ücretsizlik Ajanı).
- 429/5xx: üstel backoff (1s → 2s → 4s → …); 5 hata sonrası 30 sn circuit breaker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, cast

from openai import AsyncOpenAI

from ..config import settings
from ..db import get_db

logger = logging.getLogger(__name__)

BASE_DELAY = 1.0
MAX_BACKOFF_DELAY = 8.0
MAX_RETRIES = 5
CIRCUIT_ERROR_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 30
MAX_TOKENS_DEFAULT = 2048
TEMPERATURE = 0.1  # halüsinasyon azaltma (yol haritası Bölüm 9)

_breaker: dict = {"failures": 0, "open_until": 0.0}


class LLMError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı."""


def _check_breaker() -> None:
    if (
        _breaker["failures"] >= CIRCUIT_ERROR_THRESHOLD
        and time.monotonic() < _breaker["open_until"]
    ):
        remaining = int(_breaker["open_until"] - time.monotonic())
        raise LLMError(
            f"API'ye çok fazla hatalı istek yapıldı; "
            f"{remaining} saniye sonra tekrar denenebilir."
        )


def _record_success() -> None:
    _breaker["failures"] = 0


def _record_failure() -> None:
    _breaker["failures"] += 1
    if _breaker["failures"] >= CIRCUIT_ERROR_THRESHOLD:
        _breaker["open_until"] = time.monotonic() + CIRCUIT_OPEN_SECONDS
        logger.warning("LLM circuit breaker açıldı (%s sn)", CIRCUIT_OPEN_SECONDS)


def _client() -> AsyncOpenAI:
    """AsyncOpenAI istemcisi — anahtar yoksa net Türkçe hata."""
    key = settings.deepseek_api_key
    if not key:
        raise LLMError("DeepSeek API anahtarı ayarlanmadı. Ayarlar sayfasından girin.")
    return AsyncOpenAI(api_key=key, base_url=settings.deepseek_base_url)


def _friendly_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "API anahtarı geçersiz. Ayarlar sayfasından kontrol edin."
    if status == 402 or status == 429:
        return "API kotası aşıldı veya ödeme gerekli. Birazdan tekrar deneyin."
    if status and status >= 500:
        return "API sunucusu geçici olarak kullanılamıyor. Birazdan tekrar deneyin."
    return "LLM isteği başarısız oldu. Lütfen tekrar deneyin."


async def log_generation(
    *,
    kind: str,
    course_id: int | None = None,
    chapter_id: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Her LLM çağrısını generation_logs'a işler (maliyet bekçiliği)."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO generation_logs "
            "(kind, course_id, chapter_id, model, prompt_tokens, completion_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, course_id, chapter_id, settings.model, prompt_tokens, completion_tokens),
        )
        await db.commit()
    finally:
        await db.close()


def _extract_delta_text(chunk) -> str:
    """Stream chunk'ından metin deltasını çıkarır (SDK sürümlerine dayanıklı)."""
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return ""
    text = getattr(delta, "content", None)
    return text if isinstance(text, str) else ""


def _extract_usage(chunk) -> tuple[int, int] | None:
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return prompt_tokens, completion_tokens


async def chat_stream(
    messages: list[dict],
    *,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    temperature: float = TEMPERATURE,
    kind: str = "note",
    course_id: int | None = None,
    chapter_id: int | None = None,
):
    """Sohbet tamamlama — metin deltalarını akışkan döner (async generator).

    Kullanım: `async for delta in chat_stream(...): ...`
    """
    _check_breaker()
    client = _client()
    delay = BASE_DELAY
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            stream = await client.chat.completions.create(
                model=settings.model,
                messages=cast(Any, messages),
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True},
            )
            prompt_tokens = 0
            completion_tokens = 0
            async for chunk in stream:
                usage = _extract_usage(chunk)
                if usage is not None:
                    prompt_tokens, completion_tokens = usage
                text = _extract_delta_text(chunk)
                if text:
                    yield text
            _record_success()
            await log_generation(
                kind=kind,
                course_id=course_id,
                chapter_id=chapter_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return
        except LLMError:
            raise
        except Exception as exc:  # ağ, 429, 5xx...
            last_error = exc
            _record_failure()
            status = getattr(exc, "status_code", None)
            if attempt == MAX_RETRIES or (status is not None and status < 500 and status != 429):
                raise LLMError(_friendly_error(exc)) from exc
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF_DELAY)

    if last_error is not None:
        raise LLMError(_friendly_error(last_error))
    raise LLMError("LLM isteği başarısız oldu.")


async def chat_json(
    messages: list[dict],
    *,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    temperature: float = TEMPERATURE,
    kind: str = "json",
    course_id: int | None = None,
    chapter_id: int | None = None,
) -> dict:
    """JSON çıktılı sohbet çağrısı — geçersiz JSON'da 1 yeniden deneme."""
    _check_breaker()
    client = _client()
    delay = BASE_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            messages_for_call = list(messages)
            needs_json_note = attempt > 1 and (
                "önceki yanıt geçerli JSON değildi"
                not in str(messages_for_call[-1]).lower()
            )
            if needs_json_note:
                messages_for_call.append(
                    {
                        "role": "user",
                        "content": (
                            "Önceki yanıt geçerli JSON değildi. Yalnızca istenen JSON "
                            "şemasına uygun geçerli JSON döndür."
                        ),
                    }
                )
            response = await client.chat.completions.create(
                model=settings.model,
                messages=cast(Any, messages_for_call),
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = getattr(response.choices[0].message, "content", None) or ""
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                if attempt == 1:
                    await asyncio.sleep(0.5)
                    continue
                raise LLMError("Model geçerli JSON üretemedi. Lütfen tekrar deneyin.") from None
            _record_success()
            await log_generation(
                kind=kind,
                course_id=course_id,
                chapter_id=chapter_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return data
        except LLMError:
            raise
        except Exception as exc:
            _record_failure()
            status = getattr(exc, "status_code", None)
            if attempt == MAX_RETRIES or (status is not None and status < 500 and status != 429):
                raise LLMError(_friendly_error(exc)) from exc
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF_DELAY)

    raise LLMError("LLM isteği başarısız oldu.")
