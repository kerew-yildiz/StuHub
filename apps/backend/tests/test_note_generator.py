"""Not üretimi pipeline testleri (Faz 3.1) — LLM ve retrieval mock'lu."""

from src.services import llm_service, note_generator, retrieval, web_search_service

TOPIC = "Bağlı Listeler"
CHUNK_TEXT = "Bağlı listeler, her düğümün bir sonraki düğüme işaret ettiği doğrusal veri yapısıdır."
CHUNKS = [
    {
        "chunk_id": "chk_9_1_1",
        "material_id": 9,
        "text": CHUNK_TEXT,
        "page": 1,
        "slide": None,
        "score": 0.9,
    }
]
SECTION = (
    f"### {TOPIC}\n\nBağlı listeler, her düğümün bir sonraki düğüme işaret ettiği "
    f"doğrusal veri yapısıdır [1].\n\n- Her düğüm veri ve işaretçi taşır [1]."
)
SIRALAMA_SECTION = "### Sıralama\n\nSıralama algoritmaları karşılaştırma yapar [1]."


async def _make_chapter_with_slides(client) -> int:
    resp = await client.post("/api/terms", json={"name": "2026 Bahar"})
    term_id = resp.json()["id"]
    resp = await client.post(f"/api/terms/{term_id}/courses", json={"name": "Veri Yapıları"})
    course_id = resp.json()["id"]
    resp = await client.post(f"/api/courses/{course_id}/chapters", json={"title": TOPIC})
    return resp.json()["id"]


async def _insert_slide(chapter_id: int, slide_no: int, text: str) -> None:
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO slides (chapter_id, material_id, slide_no, content_text) "
            "VALUES (?, NULL, ?, ?)",
            (chapter_id, slide_no, text),
        )
        await conn.commit()


def _setup_mocks(monkeypatch, *, topics=None, section=None, coverage_missing=None, confirm=True):
    topics = topics or [{"topic": TOPIC, "keywords": ["düğüm"], "slide_refs": [1]}]
    section = section or SECTION
    coverage_calls = {"count": 0}

    async def fake_chat_json(messages, **kwargs):
        await llm_service.log_generation(
            kind=kwargs.get("kind", "json"),
            provider="gemini",
            model="gemini-2.5-flash",
            course_id=kwargs.get("course_id"),
            chapter_id=kwargs.get("chapter_id"),
        )
        prompt = messages[0]["content"]
        if "konu listesini çıkar" in prompt:
            return {"topics": topics}
        if "YETERSİZ" in prompt or "EKSİK" in prompt:
            coverage_calls["count"] += 1
            return {"missing": coverage_missing or []}
        if "destekliyor mu" in prompt:
            return {"supported": confirm}
        return {}

    async def fake_chat_stream(messages, **kwargs):
        await llm_service.log_generation(
            kind=kwargs.get("kind", "stream"),
            provider="gemini",
            model="gemini-2.5-flash",
            course_id=kwargs.get("course_id"),
            chapter_id=kwargs.get("chapter_id"),
        )
        # konu adına göre deterministik içerik (yeniden üretim turları da aynı üretir)
        prompt = messages[0]["content"]
        text = SIRALAMA_SECTION if "Sıralama" in prompt else section
        for delta in [text[i : i + 20] for i in range(0, len(text), 20)]:
            yield delta

    monkeypatch.setattr(llm_service, "chat_json", fake_chat_json)
    monkeypatch.setattr(llm_service, "chat_stream", fake_chat_stream)

    def _fake_search(course_id, query, keywords=None, **kw):
        return list(CHUNKS)

    monkeypatch.setattr(retrieval, "hybrid_search", _fake_search)
    return coverage_calls


async def _collect_events(agen) -> list[dict]:
    return [event async for event in agen]


async def test_generate_notes_full_flow(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler konusu")

    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_mocks(monkeypatch)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    types = [e["type"] for e in events]
    assert "status" in types and "delta" in types and "done" in types
    done = next(e for e in events if e["type"] == "done")
    note = done["note"]
    assert TOPIC in note["content_md"]
    assert note["citations_json"]["topics"][0]["topic"] == TOPIC
    citations = note["citations_json"]["topics"][0]["citations"]
    assert len(citations) >= 1
    assert citations[0]["chunk_id"] == "chk_9_1_1"
    assert "chunk_text" not in citations[0]  # dahili alan kaydedilmez

    # notes tablosuna kaydedildi
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT content_md FROM notes WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
    assert row is not None and TOPIC in row[0]


async def test_generate_notes_no_slides(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_mocks(monkeypatch)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    assert events[-1]["type"] == "error"
    assert "guide slides" in events[-1]["message"].lower()


async def test_generate_notes_no_api_key(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "")

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    assert events[-1]["type"] == "error"
    assert "API anahtarı" in events[-1]["message"]


async def test_generate_notes_missing_topic_regenerated(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İki konu: Bağlı Listeler ve Sıralama")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")

    # önce eksik döndür, yeniden üretimden sonra tamam
    coverage = {"calls": 0}

    async def fake_chat_json(messages, **kwargs):
        prompt = messages[0]["content"]
        if "konu listesini çıkar" in prompt:
            return {
                "topics": [
                    {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
                    {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
                ]
            }
        if "YETERSİZ" in prompt or "EKSİK" in prompt:
            coverage["calls"] += 1
            return {"missing": ["Sıralama"] if coverage["calls"] == 1 else []}
        return {"supported": True}

    async def fake_chat_stream(messages, **kwargs):
        prompt = messages[0]["content"]
        if "Sıralama" in prompt:
            yield SIRALAMA_SECTION
        else:
            yield SECTION

    monkeypatch.setattr(llm_service, "chat_json", fake_chat_json)
    monkeypatch.setattr(llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(
        retrieval, "hybrid_search", lambda course_id, query, keywords=None, **kw: list(CHUNKS)
    )

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    assert "Sıralama" in done["note"]["content_md"]
    assert coverage["calls"] >= 2


async def test_generate_notes_unresolvable_citation_never_fails(client, monkeypatch):
    """Çözümsüz atıflar notu HATAYA DÜŞÜRMEZ — slayt yedeğiyle bölüm teslim edilir."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    # alıntı chunk'la eşleşmeyecek ve LLM onayı da 'hayır' → yedek zincir devreye girer
    bad_section = f"### {TOPIC}\n\nTamamen alakasız bir cümle burada [1]."
    _setup_mocks(monkeypatch, section=bad_section, confirm=False)

    async def _disabled():
        return False

    monkeypatch.setattr(web_search_service, "web_search_enabled", _disabled)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    assert not any(e["type"] == "error" for e in events)
    done = next(e for e in events if e["type"] == "done")
    assert TOPIC in done["note"]["content_md"]
    assert note_generator.SLIDE_ONLY_NOTICE in done["note"]["content_md"]
    # sorunlu konunun atıfları temizlenmiş olmalı (doğrulama geçti)
    topic_citations = done["note"]["citations_json"]["topics"][0]["citations"]
    assert topic_citations == []


WEB_TEXT = "Bağlı listeler, her düğümün bir sonraki düğüme işaret ettiği doğrusal veri yapısıdır."
WEB_SECTION = f"### {TOPIC}\n\n{WEB_TEXT} [1]"
SLIDE_ONLY_SECTION = f"### {TOPIC}\n\nBağlı listeler doğrusal bir veri yapısıdır."


def _setup_fallback_mocks(monkeypatch, *, web_enabled, section):
    """Retrieval boş + web arama mock'lu fallback zinciri kurar."""
    _setup_mocks(monkeypatch, section=section)
    monkeypatch.setattr(retrieval, "hybrid_search", lambda *a, **kw: [])

    async def _enabled():
        return web_enabled

    async def _search(topic, course_name, max_results=3):
        return [
            {
                "title": "Web Kaynağı",
                "url": "https://example.com/liste",
                "text": WEB_TEXT,
                "quote": WEB_TEXT[:240],
            }
        ]

    monkeypatch.setattr(web_search_service, "web_search_enabled", _enabled)
    monkeypatch.setattr(web_search_service, "search_web", _search)


async def test_web_fallback_produces_cited_section(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler konusu")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_fallback_mocks(monkeypatch, web_enabled=True, section=WEB_SECTION)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    citations = done["note"]["citations_json"]["topics"][0]["citations"]
    assert len(citations) >= 1
    assert citations[0]["source_type"] == "web"
    assert citations[0]["url"] == "https://example.com/liste"
    assert TOPIC in done["note"]["content_md"]
    assert "uyarılı not" not in done["note"]["content_md"]


async def test_slide_fallback_produces_full_section(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler: düğüm ve işaretçi yapısı")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_fallback_mocks(monkeypatch, web_enabled=False, section=SLIDE_ONLY_SECTION)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    content = done["note"]["content_md"]
    assert TOPIC in content
    assert "ders sunumundan üretildi" in content
    assert done["note"]["citations_json"]["topics"][0]["citations"] == []


async def test_web_fallback_never_emits_missing_source_warning(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler konusu")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_fallback_mocks(monkeypatch, web_enabled=True, section=WEB_SECTION)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    messages = [e.get("message", "") for e in events if e["type"] == "status"]
    assert all("uyarılı not" not in m for m in messages)
    done = next(e for e in events if e["type"] == "done")
    assert "uyarılı not" not in done["note"]["content_md"]
    assert "eksik not edildi" not in done["note"]["content_md"]


async def test_generation_logs_written(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_mocks(monkeypatch)
    await _collect_events(note_generator.generate_notes_stream(chapter_id))

    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM generation_logs WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
    count = row[0] if row is not None else 0
    assert count >= 2  # topic_extraction + en az bir üretim


async def test_regen_provider_exhaustion_never_aborts_note(client, monkeypatch):
    """Atıf düzeltme turunda sağlayıcı zinciri tükenirse (LLMError) not YİNE DE teslim edilir.

    Regresyon (2026-09-05): `_regen_topic`'in gerçek-içerik yolu (chunks mevcut) LLMError'ı
    yakalamıyordu — zaten üretilmiş 8 bölümlük bir not, atıf düzeltme turunda sağlayıcı
    kotası tükendiği an tamamen çöpe atılıyordu (bkz. Backlog.md). Artık `_regen_topic`
    başarısızlığı "bu turda değişiklik yok" sayılır, yedek zincir (SON GÜVENCE) devreye girer.
    """
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    # alıntı chunk'la eşleşmeyecek → atıf doğrulama başarısız, düzeltme turu tetiklenir
    bad_section = f"### {TOPIC}\n\nTamamen alakasız bir cümle burada [1]."
    _setup_mocks(monkeypatch, section=bad_section)

    async def fake_chat_stream_exhausted(messages, **kwargs):
        kind = kwargs.get("kind", "")
        if kind in ("note_regeneration", "note_generation_slide_only"):
            # Tüm sağlayıcılar tükendi (2026-09-05'te gerçekleşen gerçek senaryo).
            raise llm_service.LLMError("API kotası aşıldı. Birazdan tekrar deneyin.")
        for delta in [bad_section[i : i + 20] for i in range(0, len(bad_section), 20)]:
            yield delta

    monkeypatch.setattr(llm_service, "chat_stream", fake_chat_stream_exhausted)

    async def _disabled():
        return False

    monkeypatch.setattr(web_search_service, "web_search_enabled", _disabled)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    assert not any(e["type"] == "error" for e in events), [
        e for e in events if e["type"] == "error"
    ]
    done = next(e for e in events if e["type"] == "done")
    assert TOPIC in done["note"]["content_md"]
    # sağlayıcı zinciri tükendiği için hiçbir yedek not üretemedi → SON ÇARE devreye girdi,
    # çözümsüz atıf düşürüldü ama not (ve önceki içerik) korundu.
    assert done["note"]["citations_json"]["topics"][0]["citations"] == []
