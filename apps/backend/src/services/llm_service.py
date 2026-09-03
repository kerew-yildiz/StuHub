"""Ücretsiz LLM sağlayıcı zinciri istemcisi — stream, üstel backoff, kota-tabanlı devir.

Geçici çözüm (Kerem kararı, 2026-09-02): StuHub artık DeepSeek kullanmıyor. Sağlayıcı
sırası ve seçim gerekçesi `services/llm_providers.py`'de. Akış:

- Her çağrı, yetenek sırasına göre yapılandırılmış + cooldown'da olmayan ilk sağlayıcıyı
  dener (bkz. `_available_providers`).
- Kota hatası (401/402/403/429): sağlayıcı bir sonraki UTC gece yarısına kadar cooldown'a
  alınır (`settings` tablosunda `llm_provider_cooldowns` — kalıcı, restart'tan sağ çıkar)
  ve zincirdeki bir sonraki sağlayıcıya geçilir.
- 5xx/ağ hatası: aynı sağlayıcıda kısa üstel backoff ile birkaç deneme, sonra sıradaki
  sağlayıcıya geçilir.
- Her başarılı çağrı `generation_logs`'a (kind, model, provider, token) yazılır.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from openai import AsyncOpenAI

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..db import get_db
from .llm_providers import PROVIDER_CHAIN, LLMProvider

logger = logging.getLogger(__name__)

BASE_DELAY = 1.0
MAX_BACKOFF_DELAY = 4.0
MAX_RETRIES_PER_PROVIDER = 2
MAX_TOKENS_DEFAULT = 2048
TEMPERATURE = 0.1  # halüsinasyon azaltma (yol haritası Bölüm 9)

_COOLDOWN_SETTING_KEY = "llm_provider_cooldowns"


class LLMError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı."""


async def _apply_table_config() -> None:
    """Ayarlar tablosundaki (Ayarlar sayfası) sağlayıcı anahtarlarını runtime'a uygular.

    Öncelik: Ayarlar tablosu → .env/ortam değişkeni. Tablo boşsa mevcut (env) değerler korunur.
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
    finally:
        await db.close()
    values = {r["key"]: r["value"] for r in rows}
    for provider in PROVIDER_CHAIN:
        if values.get(provider.api_key_setting):
            setattr(settings, provider.api_key_setting, values[provider.api_key_setting])


async def _load_cooldowns() -> dict[str, str]:
    """Sağlayıcı adı → cooldown bitiş zamanı (ISO 8601, UTC)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (_COOLDOWN_SETTING_KEY,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        return {}
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return {}


async def _mark_cooldown(provider_name: str) -> None:
    """Sağlayıcıyı bir sonraki UTC gece yarısına kadar devre dışı bırakır (günlük kota varsayımı)."""
    cooldowns = await _load_cooldowns()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cooldowns[provider_name] = tomorrow.isoformat()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_COOLDOWN_SETTING_KEY, json.dumps(cooldowns)),
        )
        await db.commit()
    finally:
        await db.close()
    logger.warning(
        "LLM sağlayıcı kotası tükendi, %s bir sonraki gün yarısına kadar atlanacak (%s)",
        provider_name,
        tomorrow.isoformat(),
    )


def _is_provider_configured(provider: LLMProvider) -> bool:
    return bool(getattr(settings, provider.api_key_setting, ""))


async def _available_providers() -> list[LLMProvider]:
    """Anahtarı ayarlanmış ve cooldown'da olmayan sağlayıcılar, yetenek sırasına göre."""
    cooldowns = await _load_cooldowns()
    now = datetime.now(timezone.utc)
    result = []
    for provider in PROVIDER_CHAIN:
        if not _is_provider_configured(provider):
            continue
        until = cooldowns.get(provider.name)
        if until:
            try:
                if datetime.fromisoformat(until) > now:
                    continue
            except ValueError:
                pass
        result.append(provider)
    return result


def _client_for(provider: LLMProvider) -> AsyncOpenAI:
    key = getattr(settings, provider.api_key_setting)
    return AsyncOpenAI(api_key=key, base_url=provider.base_url, timeout=120.0)


def _friendly_error(exc: Exception | None) -> str:
    if exc is None:
        return (
            "Hiçbir LLM sağlayıcısı yapılandırılmadı veya hepsi kota sınırına ulaştı. "
            "Ayarlar sayfasından bir API anahtarı girin."
        )
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "API anahtarı geçersiz. Ayarlar sayfasından kontrol edin."
    if status in (402, 429):
        return "API kotası aşıldı veya ödeme gerekli. Birazdan tekrar deneyin."
    if status and status >= 500:
        return "API sunucusu geçici olarak kullanılamıyor. Birazdan tekrar deneyin."
    return "LLM isteği başarısız oldu. Lütfen tekrar deneyin."


def _is_fatal_error(exc: Exception) -> bool:
    """401/403: anahtar geçersiz — retry anlamsız, sağlayıcı hemen cooldown'a alınır."""
    return getattr(exc, "status_code", None) in (401, 403)


def _is_rate_or_quota_error(exc: Exception) -> bool:
    """402/429: dakikalık limit (geçici, retry mantıklı) ya da günlük kota (kalıcı) olabilir —
    bu yüzden önce kısa retry denenir, hâlâ başarısızsa sağlayıcı cooldown'a alınır."""
    return getattr(exc, "status_code", None) in (402, 429)


_last_call: dict[str, str] = {"provider": "", "model": ""}


def last_model_label() -> str:
    """Son başarılı LLM çağrısında kullanılan `sağlayıcı/model` — `*_used` DB kolonlarına
    yazmak için (tek sabit `settings.model` artık yok, sağlayıcı çağrı başına değişebilir)."""
    if not _last_call["model"]:
        return ""
    return f"{_last_call['provider']}/{_last_call['model']}"


async def log_generation(
    *,
    kind: str,
    provider: str,
    model: str,
    tenant_id: str = LOCAL_TENANT_ID,
    course_id: int | None = None,
    chapter_id: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Her LLM çağrısını generation_logs'a işler (maliyet bekçiliği + kota sayacı)."""
    _last_call["provider"] = provider
    _last_call["model"] = model
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO generation_logs "
            "(tenant_id, kind, course_id, chapter_id, model, provider, prompt_tokens, completion_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                kind,
                course_id,
                chapter_id,
                model,
                provider,
                prompt_tokens,
                completion_tokens,
            ),
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
    tenant_id: str = LOCAL_TENANT_ID,
    course_id: int | None = None,
    chapter_id: int | None = None,
):
    """Sohbet tamamlama — metin deltalarını akışkan döner (async generator).

    Kullanım: `async for delta in chat_stream(...): ...`
    Sağlayıcı zincirini yetenek sırasına göre dener; kota hatasında sıradakine geçer.
    """
    await _apply_table_config()
    providers = await _available_providers()
    if not providers:
        raise LLMError(_friendly_error(None))

    last_error: Exception | None = None
    for provider in providers:
        client = _client_for(provider)
        delay = BASE_DELAY
        for attempt in range(1, MAX_RETRIES_PER_PROVIDER + 1):
            try:
                stream = await client.chat.completions.create(
                    model=provider.model,
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
                await log_generation(
                    kind=kind,
                    provider=provider.name,
                    model=provider.model,
                    tenant_id=tenant_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
                return
            except Exception as exc:  # ağ, 401/402/403/429, 5xx...
                last_error = exc
                if _is_fatal_error(exc):
                    await _mark_cooldown(provider.name)
                    break  # anahtar geçersiz, retry anlamsız — sıradaki sağlayıcıya geç
                if _is_rate_or_quota_error(exc) and attempt == MAX_RETRIES_PER_PROVIDER:
                    await _mark_cooldown(provider.name)
                    break  # dakikalık limit değil, kota tükenmiş — sıradaki sağlayıcıya geç
                if attempt == MAX_RETRIES_PER_PROVIDER:
                    break  # geçici hata (5xx/ağ), bu sağlayıcıda pes et — sıradakine geç
                await asyncio.sleep(delay)
                delay = min(delay * 2, MAX_BACKOFF_DELAY)

    raise LLMError(_friendly_error(last_error))


def _extract_json(content: str) -> dict | None:
    """Model yanıtından JSON sözlüğünü dayanıklı şekilde çıkarır.

    - ```json ... ``` fence'lerini kaldırır
    - ilk '{' ile son '}' arasını dener (modelin etrafa metin yazmasına karşı)
    """
    text = content.strip()
    # markdown fence
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


async def chat_json(
    messages: list[dict],
    *,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    temperature: float = TEMPERATURE,
    kind: str = "json",
    tenant_id: str = LOCAL_TENANT_ID,
    course_id: int | None = None,
    chapter_id: int | None = None,
) -> dict:
    """JSON çıktılı sohbet çağrısı — geçersiz JSON'da ek denemelerle kendini onarır.

    Sağlayıcı zincirini yetenek sırasına göre dener; kota hatasında sıradakine geçer.
    """
    await _apply_table_config()
    providers = await _available_providers()
    if not providers:
        raise LLMError(_friendly_error(None))

    last_error: Exception | None = None
    for provider in providers:
        client = _client_for(provider)
        json_failures = 0
        provider_exhausted = False
        while json_failures < 3:
            messages_for_call = list(messages)
            if json_failures > 0:
                messages_for_call.append(
                    {
                        "role": "user",
                        "content": (
                            "Önceki yanıt geçerli JSON değildi. Yalnızca istenen JSON "
                            "şemasına uygun, ek açıklama olmadan geçerli JSON döndür "
                            "(``` işareti kullanma)."
                        ),
                    }
                )
            response = None
            delay = BASE_DELAY
            for attempt in range(1, MAX_RETRIES_PER_PROVIDER + 1):
                try:
                    response = await client.chat.completions.create(
                        model=provider.model,
                        messages=cast(Any, messages_for_call),
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    if _is_fatal_error(exc):
                        await _mark_cooldown(provider.name)
                        provider_exhausted = True
                        break
                    if _is_rate_or_quota_error(exc) and attempt == MAX_RETRIES_PER_PROVIDER:
                        await _mark_cooldown(provider.name)
                        provider_exhausted = True
                        break
                    if attempt == MAX_RETRIES_PER_PROVIDER:
                        provider_exhausted = True
                        break
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, MAX_BACKOFF_DELAY)
            if provider_exhausted or response is None:
                break  # sıradaki sağlayıcıya geç
            content = getattr(response.choices[0].message, "content", None) or ""
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            data = _extract_json(content)
            if data is None:
                json_failures += 1
                if json_failures >= 3:
                    raise LLMError("Model geçerli JSON üretemedi. Lütfen tekrar deneyin.") from None
                await asyncio.sleep(0.5)
                continue
            await log_generation(
                kind=kind,
                provider=provider.name,
                model=provider.model,
                tenant_id=tenant_id,
                course_id=course_id,
                chapter_id=chapter_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return data

    raise LLMError(_friendly_error(last_error))
