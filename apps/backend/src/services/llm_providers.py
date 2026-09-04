"""Ücretsiz LLM sağlayıcı zinciri — geçici çözüm (Kerem kararı, 2026-09-02).

StuHub artık DeepSeek kullanmıyor. Kerem ileride tek bir model için ücretli API
anahtarı verene kadar, aşağıdaki ücretsiz sağlayıcılar YETENEK sırasına göre
denenir: birinin günlük kotası tükenince (401/402/403/429) otomatik olarak
sıradakine geçilir (bkz. `llm_service._pick_provider`). Kota durumu `settings`
tablosunda `llm_provider_cooldowns` anahtarı altında kalıcı tutulur — uygulama
yeniden başlasa da tükenmiş bir sağlayıcıya tekrar tekrar vurulmaz.

Sıralama gerekçesi (StuHub ihtiyaçları gözetilerek — Türkçe kalite, JSON modu
güvenilirliği, uzun materyal bağlamı, atıflı akıl yürütme):

1. Google Gemini 2.5 Flash — en iyi genel yetenek: 1M token bağlam (RAG için
   kritik), güçlü Türkçe, native JSON modu, günlük 1500 istek (en geniş kota).
2. OpenRouter ücretsiz havuzu (Nvidia Nemotron 3 Ultra 550B) — güçlü akıl yürütme
   (ödev değerlendirme, quiz mantığı), 1M token bağlam; ücretsiz model listesi
   haftalık değişebilir (2026-09-03: DeepSeek R1 free slug kaldırılmış, canlı API
   ile doğrulanıp bu modelle değiştirildi — bkz. Backlog.md).
3. Groq (Llama 3.3 70B) — en hızlı ve en geniş kota (günlük 14.400 istek),
   yetenek olarak ilk ikisinin gerisinde ama sistemi ayakta tutan hacim çapası.
   YETENEKLER/08-ucretsiz-arac-envanteri.md ile uyumlu (zaten onaylı araç).
4. GitHub Models (GPT-4.1 mini) — frontier kalite ama 8K girdi / 4K çıktı
   sınırı (uzun bölüm metni + materyal bağlamını kısıtlar) ve günlük kota en
   dar (50-150) sağlayıcı; son çare.

Bu liste geçicidir. Kerem tek bir ücretli anahtar verdiğinde `PROVIDER_CHAIN`
o tek sağlayıcıya indirgenecek (bkz. Backlog.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMProvider:
    name: str
    """Kalıcı anahtar — cooldown state ve generation_logs.provider'da kullanılır."""
    label: str
    """Ayarlar sayfasında gösterilecek Türkçe ad."""
    base_url: str
    model: str
    api_key_setting: str
    """`config.Settings` üzerindeki anahtar alanının adı."""
    max_context_tokens: int


PROVIDER_CHAIN: list[LLMProvider] = [
    LLMProvider(
        name="gemini",
        label="Google Gemini 2.5 Flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        api_key_setting="google_api_key",
        max_context_tokens=1_000_000,
    ),
    LLMProvider(
        name="openrouter",
        label="OpenRouter — Nemotron 3 Ultra 550B (ücretsiz)",
        base_url="https://openrouter.ai/api/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        api_key_setting="openrouter_api_key",
        max_context_tokens=1_000_000,
    ),
    LLMProvider(
        name="groq",
        label="Groq — Llama 3.3 70B",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        api_key_setting="groq_api_key",
        max_context_tokens=128_000,
    ),
    LLMProvider(
        name="github",
        label="GitHub Models — GPT-4.1 mini",
        base_url="https://models.github.ai/inference",
        model="openai/gpt-4.1-mini",
        api_key_setting="github_token",
        max_context_tokens=8_000,
    ),
]

PROVIDERS_BY_NAME: dict[str, LLMProvider] = {p.name: p for p in PROVIDER_CHAIN}
