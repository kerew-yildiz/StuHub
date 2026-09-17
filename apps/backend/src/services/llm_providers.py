"""LLM sağlayıcı zinciri — birincil opencode-go, yedekler ücretsiz sağlayıcılar.

Birincil sağlayıcı artık opencode-go (Kerem kararı, 2026-09-16): $10/ay Go
aboneliği, DeepSeek V4.1 Flash. DeepSeek yeniden kullanımda; aşağıdaki ücretsiz
sağlayıcılar YEDEK olarak korunur. Zincir YETENEK sırasına göre denenir: birinin
kotası tükenince (401/402/403/429) otomatik olarak sıradakine geçilir (bkz.
`llm_service._pick_provider`). Kota durumu `settings` tablosunda
`llm_provider_cooldowns` anahtarı altında kalıcı tutulur — uygulama yeniden
başlasa da tükenmiş bir sağlayıcıya tekrar tekrar vurulmaz.

Sıralama gerekçesi (StuHub ihtiyaçları gözetilerek — Türkçe kalite, JSON modu
güvenilirliği, uzun materyal bağlamı, atıflı akıl yürütme):

0. opencode-go (DeepSeek V4.1 Flash) — ücretli birincil sağlayıcı: yüksek akıl
   yürütme (reasoning_effort=high), geniş bağlam, günlük kota yerine abonelik
   kotası (5 saatlik/haftalık/aylık). Devre dışı kalırsa altındaki ücretsiz yedek
   zincir devralır.

1. Google Gemini 3.1 Flash Lite — ücretsiz yedekler içinde en iyi genel yetenek:
   1M token bağlam (RAG için kritik), güçlü Türkçe, native JSON modu, günlük
   1500 istek (en geniş kota).
2. OpenRouter ücretsiz havuzu (Nvidia Nemotron 3 Ultra 550B) — güçlü akıl yürütme
   (ödev değerlendirme, quiz mantığı), 1M token bağlam; ücretsiz model listesi
   haftalık değişebilir (2026-09-03: DeepSeek R1 free slug kaldırılmış, canlı API
   ile doğrulanıp bu modelle değiştirildi — bkz. Backlog.md).
3. Groq (Llama 3.3 70B) — en hızlı ve en geniş kota (günlük 14.400 istek),
   yetenek olarak ilk ikisinin gerisinde ama sistemi ayakta tutan hacim çapası.
   YETENEKLER/08-ucretsiz-arac-envanteri.md ile uyumlu (zaten onaylı araç).
4. Cerebras (Llama 3.3 70B) — GEÇİCİ TEST sağlayıcısı (Kerem kararı, 2026-09-05):
   Gemini+OpenRouter günlük kotası bugünkü yoğun testten tükendi, GitHub Models
   planlı bakımda; Groq'la aynı model ama ayrı ücretsiz kota (günlük 1M token,
   kredi kartsız). Kerem "kaldır" dediğinde bu girdi silinecek (bkz. Backlog.md).
5. GitHub Models (GPT-4.1 mini) — frontier kalite ama 8K girdi / 4K çıktı
   sınırı (uzun bölüm metni + materyal bağlamını kısıtlar) ve günlük kota en
   dar (50-150) sağlayıcı; son çare.

Bu liste geçicidir: opencode-go çalıştığı sürece ücretsiz yedekler yalnızca
kesinti/kota durumunda devreye girer; Kerem "artık gerek yok" dediğinde yedek
girdiler silinecek (bkz. Backlog.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


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
    extra_params: dict[str, Any] = field(default_factory=dict)
    """Sağlayıcıya özel ek istek parametreleri (ör. Gemini 3 `reasoning_effort`,
    opencode-go `extra_headers` — `User-Agent` bu yolla geçilir).

    Değer tipi `Any`: bu sözlük `client.chat.completions.create(**extra_params)`
    ile açılıyor; `str`e daraltılırsa tip denetleyici her olası keyword parametresini
    `str`e karşı deneyip onlarca yanlış pozitif üretir (parametrelerin gerçek tipleri
    sağlayıcıya göre değişir — bool/int/dict de olabilir).
    """
    session_header: str | None = None
    """Oturum kimliğinin gönderileceği HTTP başlığı (varsa) — değeri statik değil,
    `request_params()` istek başına kiracı + iş bağlamından türetir."""
    max_output_tokens: int | None = None
    """Tek yanıtta üretilebilecek azami token. Çağıran `chat_*`'a özel `max_tokens`
    vermezse `llm_service` bunu kullanır; `None` → `MAX_TOKENS_DEFAULT` (2048).

    Reasoning sağlayıcılarında gizli reasoning token'ları DA bu bütçeden harcanır:
    varsayılan 2048 bütçe uzun promptta yalnızca reasoning'e gider ve yanıt
    `finish_reason=length` + BOŞ içerikle döner (bkz. opencode girdisi ve
    llm_service._max_tokens_for)."""
    request_timeout: float = 20.0
    """Tek HTTP isteği için zaman aşımı (sn). Geniş bütçeyle reasoning yapan sağlayıcıda
    yanıt 20 sn'yi aşabildiğinden yükseltilir (bkz. opencode girdisi)."""



PROVIDER_CHAIN: list[LLMProvider] = [
    LLMProvider(
        name="opencode",
        label="opencode-go — DeepSeek V4.1 Flash",
        # 2026-09-16: base_url + slug canlı doğrulandı (GET /models → 200, 37 model;
        # POST /chat/completions → 200, yanıt "TAMAM"). Zen'in ücretli ucu (/zen/v1)
        # DEĞİL: anahtar Go aboneliğine bağlı, bakiye yok ("Insufficient balance").
        # Go ucu `x-opencode-session` olmadan 400 "MissingSessionID" döner; dokümana
        # göre istemci konuşma başına bir oturum kimliği göndermeli (yönlendirme +
        # prompt cache). Kimlik SABİT DEĞİL: `session_header` işaretlenir, değeri
        # `request_params()` her istekte kiracı + iş bağlamından türetir.
        base_url="https://opencode.ai/zen/go/v1",
        model="deepseek-v4.1-flash",
        api_key_setting="opencode_api_key",
        max_context_tokens=1_000_000,
        session_header="x-opencode-session",
        extra_params={
            "reasoning_effort": "high",
            "extra_headers": {"User-Agent": "StuHub/1.0"},
        },
        # 2026-09-17 (json-hata P0): `reasoning_effort=high` ile gizli reasoning
        # token'ları DA completion bütçesinden harcanıyor. 2048'lik varsayılan bütçe
        # büyük chapter promptunda (8K kr slayt) yalnızca reasoning'e gidiyor ve yanıt
        # `finish_reason=length` + BOŞ `content` ile dönüyordu; chat_json 3 kez
        # ayrıştıramayınca "Model geçerli JSON üretemedi" hatası çıkıyordu (canlı
        # ölçüm: 2048'de boş/length, 8192'de ~29 sn'de tam JSON; reasoning ~17,7K kr
        # + içerik ~2,1K kr = ~6,5K token). Zaman aşımı da 20 sn'de bu yanıtı kesiyordu.
        max_output_tokens=8192,
        request_timeout=90.0,
    ),
    LLMProvider(
        name="gemini",
        label="Google Gemini 3.1 Flash Lite",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-3.1-flash-lite",
        api_key_setting="google_api_key",
        max_context_tokens=1_000_000,
        # 2026-09-05: gemini-2.5-flash "yeni kullanıcılara" kapatıldı (404). gemini-3.6-flash'a
        # geçildi ama günlük kotası son derece dar çıktı — birkaç istekte tekrar tükendi
        # (canlı doğrulandı: aynı gün içinde iki kez 429). gemini-3.1-flash-lite ayrı bir kota
        # havuzunda ve hâlâ müsait (canlı doğrulandı). Gemini 3 serisi varsayılan olarak
        # görünmez "reasoning" token'ı tüketiyor — `minimal` bu overhead'i sıfırlar.
        extra_params={"reasoning_effort": "minimal"},
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
        name="cerebras",
        label="Cerebras — Llama 3.3 70B (geçici test)",
        base_url="https://api.cerebras.ai/v1",
        model="llama-3.3-70b",
        api_key_setting="cerebras_api_key",
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

# Oturum kimliği: eskiden TÜM uygulama için tek bir sabitti; farklı dersler/kiracılar
# aynı oturumu paylaşıyordu (prompt cache kirlenmesi + kiracı ayrımı yok). Artık
# (kiracı, iş bağlamı) çiftinden deterministik UUID5 türetilir — gerekçe ve öneri:
# master_worker_system/uiux/raporlar/INCELEME-opencode-saglayici.md ("Önerilen düzeltme").
_SESSION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "stuhub/llm-session")


def session_id_for(tenant_id: str, context_key: str | None = None) -> str:
    """(kiracı, iş bağlamı) → deterministik oturum kimliği.

    `context_key` işin doğal kimliğidir (ör. "note_generation:5:12"); verilmezse
    yalnızca kiracı ayrımı kalır. Aynı girdi her zaman aynı kimliği üretir: aynı iş
    bağlamının tekrar istekleri sağlayıcı tarafında aynı oturumu (prompt cache) paylaşır.
    """
    return str(uuid.uuid5(_SESSION_NAMESPACE, f"{tenant_id}:{context_key or ''}"))


def request_params(
    provider: LLMProvider, *, tenant_id: str, context_key: str | None = None
) -> dict[str, Any]:
    """`create(**params)` için istek başına parametre sözlüğü (`extra_params` kopyası).

    `extra_params` frozen dataclass üzerinde paylaşılan bir nesnedir; oturum başlığı
    istek başına değiştiğinden kopya döndürülür — orijinal sözlük mutasyona uğramaz.
    """
    params = dict(provider.extra_params)
    if provider.session_header:
        headers = dict(params.get("extra_headers") or {})
        headers[provider.session_header] = session_id_for(tenant_id, context_key)
        params["extra_headers"] = headers
    return params
