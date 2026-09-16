"""opencode oturum kimliği testleri — sabit kimlik yerine (kiracı, iş bağlamı) UUID5.

Kaynak: master_worker_system/uiux/raporlar/INCELEME-opencode-saglayici.md
("Önerilen düzeltme"): sabit oturum kimliği prompt önbelleğini kirletiyor ve kiracı
ayrımı bırakmıyordu. Artık `llm_providers.session_id_for` deterministik türetir ve
`llm_providers.request_params` istek başına `x-opencode-session` başlığına yazar.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from src.services import llm_service
from src.services.llm_providers import PROVIDERS_BY_NAME, request_params, session_id_for


def test_ayni_kiraci_ve_baglam_ayni_kimlik_verir():
    first = session_id_for("tenant-a", "note_generation:5:12")
    second = session_id_for("tenant-a", "note_generation:5:12")
    assert first == second
    assert uuid.UUID(first).version == 5  # deterministik UUID5


def test_farkli_kiraci_farkli_kimlik_verir():
    assert session_id_for("tenant-a", "note_generation:5:12") != session_id_for(
        "tenant-b", "note_generation:5:12"
    )


def test_farkli_baglam_farkli_kimlik_verir():
    assert session_id_for("tenant-a", "note_generation:5:12") != session_id_for(
        "tenant-a", "quiz:5:12"
    )


def test_baglam_istege_bagli():
    """`context_key` verilmezse yalnızca kiracı ayrımı kalır; kimlik yine geçerlidir."""
    without_context = session_id_for("tenant-a")
    assert uuid.UUID(without_context).version == 5
    assert without_context != session_id_for("tenant-b")


def test_request_params_basligi_turetir_payi_mutasyona_ugratmaz():
    provider = PROVIDERS_BY_NAME["opencode"]
    headers_before = dict(provider.extra_params["extra_headers"])

    params = request_params(provider, tenant_id="tenant-a", context_key="note:5:12")

    assert params["extra_headers"]["x-opencode-session"] == session_id_for(
        "tenant-a", "note:5:12"
    )
    assert params["extra_headers"]["User-Agent"] == "StuHub/1.0"
    assert params["reasoning_effort"] == "high"
    # Paylaşılan (frozen dataclass) sözlük değişmemeli — istek başına kopya döner.
    assert provider.extra_params["extra_headers"] == headers_before
    assert "x-opencode-session" not in provider.extra_params["extra_headers"]


def test_oturum_basligi_olmayan_saglayicida_ek_baslik_yok():
    provider = PROVIDERS_BY_NAME["gemini"]
    params = request_params(provider, tenant_id="tenant-a", context_key="note:5:12")
    assert params == provider.extra_params
    assert "extra_headers" not in params


async def test_chat_json_istegi_turetilen_basligi_tasir(client, monkeypatch):
    """Uçtan uca: istek `x-opencode-session` başlığıyla gider; değer iş bağlamından türer."""
    calls: list[dict] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=5),
            )

    fake = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    monkeypatch.setattr(llm_service, "_client_for", lambda provider, keys=None: fake)
    monkeypatch.setattr(llm_service.settings, "opencode_api_key", "sk-test")
    llm_service.reset_config_cache()

    data = await llm_service.chat_json(
        [{"role": "user", "content": "soru"}],
        kind="quiz",
        tenant_id="tenant-a",
        course_id=3,
        chapter_id=7,
    )
    assert data == {"ok": True}
    assert calls[0]["extra_headers"]["x-opencode-session"] == session_id_for("tenant-a", "quiz:3:7")

    await llm_service.chat_json(
        [{"role": "user", "content": "soru"}],
        kind="quiz",
        tenant_id="tenant-b",
        course_id=3,
        chapter_id=7,
    )
    assert calls[1]["extra_headers"]["x-opencode-session"] == session_id_for("tenant-b", "quiz:3:7")
