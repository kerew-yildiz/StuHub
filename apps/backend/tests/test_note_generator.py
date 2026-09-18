"""Not üretimi pipeline testleri (Faz 3.1) — LLM ve retrieval mock'lu."""

from src.services import llm_service, note_generator, retrieval, web_search_service

TOPIC = "Bağlı Listeler"
CHUNK_TEXT = "Bağlı listeler, her düğümün bir sonraki düğüme işaret ettiği doğrusal veri yapısıdır."
CHUNKS = [        {

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
        # Yönlendirme prompt METNİNE değil, çağrı TİPİNE bağlıdır: prompt metni
        # değiştiğinde (bkz. prompts v3) mock sessizce boş dönüp akışı kırmasın.
        kind = kwargs.get("kind", "")
        if kind == "topic_extraction" or "konu listesini çıkar" in prompt.lower():
            return {"topics": topics}
        if kind == "coverage_check" or "YETERSİZ" in prompt or "EKSİK" in prompt:
            coverage_calls["count"] += 1
            return {"missing": coverage_missing or []}
        if kind == "citation_confirm" or "destekliyor mu" in prompt:
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


ENVELOPE_SECTION = (
    '```json\n{"content": "### ' + TOPIC + '\\n\\nBağlı listeler, her düğümün bir sonraki '
    'düğüme işaret ettiği doğrusal veri yapısıdır [1].\\n\\n- Her düğüm veri ve işaretçi '
    'taşır [1]."}\n```'
)


async def test_json_envelope_section_saved_as_markdown(client, monkeypatch):
    """Model JSON zarfı döndürse bile KAYIT ve AKIŞ temiz markdown olmalı (2026-09-18 vaka).

    Canlı vaka: gemini `note_generation_slide_only` akışında `{"content": "### ..."}` zarfı
    döndürdü; ham hâli `notes.content_md`ye yazıldı ve ekranda ```json bloğu olarak göründü.
    """
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler konusu")

    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_mocks(monkeypatch, section=ENVELOPE_SECTION)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    content = done["note"]["content_md"]

    assert "```" not in content
    assert '"content"' not in content
    assert "\\n" not in content
    # H1 genel başlık (note_title fallback) + AYNI adlı `###` duplike düşmüş olmalı.
    assert content.startswith(f"# {TOPIC}\n\nBağlı listeler,")
    assert f"### {TOPIC}" not in content
    # Canlı akış da ham JSON taşımaz (yarım zarf ekrana düşmez).
    streamed = "".join(e["text"] for e in events if e["type"] == "delta")
    assert '"content"' not in streamed

    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT content_md FROM notes WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
    assert row is not None
    assert "```" not in row[0] and '"content"' not in row[0]


async def test_content_less_envelope_falls_back_to_slide_section(client, monkeypatch):
    """Yalnızca şema dökümü dönen bölüm boş kalmaz: deterministik slayt bölümüne düşer."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler slayt metni")

    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_mocks(monkeypatch, section='{"topic": "Bağlı Listeler", "summary": "Özet"}')

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    content = done["note"]["content_md"]
    assert '"summary"' not in content and '"topic"' not in content
    assert "Bağlı listeler slayt metni" in content


def test_replace_section_keeps_heading_separator():
    """Yeniden üretilen bölüm, sonraki başlığa YAPIŞMAMALI (2026-09-18 vaka).

    Yapışınca `### Konu` markdown başlığı olarak render edilmiyor, ekranda düz metin
    olarak görünüyordu; kullanıcı notlarının 9'unda bu iz vardı.
    """
    import re as _re

    content = "### A\n\neski [1].\n\n### B\n\nyeni [1]."
    pattern = _re.compile(r"^#{1,4}\s+A\s*$", _re.MULTILINE)
    out, replaced = note_generator._replace_section(content, pattern, "### A\n\ndüzeltilmiş [1].")
    assert replaced
    assert out == "### A\n\ndüzeltilmiş [1].\n\n### B\n\nyeni [1]."


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
        kind = kwargs.get("kind", "")
        if kind == "topic_extraction" or "konu listesini çıkar" in prompt.lower():
            return {
                "topics": [
                    {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
                    {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
                ]
            }
        if kind == "coverage_check" or "YETERSİZ" in prompt or "EKSİK" in prompt:
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
    assert "Tamamen alakasız bir cümle burada" in done["note"]["content_md"]
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
    assert "Bağlı listeler doğrusal bir veri yapısıdır." in content
    assert "ders sunumundan üretildi" not in content
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


async def _insert_syllabus(course_id: int, text: str) -> None:
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute(
            "INSERT INTO materials (course_id, type, filepath, extracted_text) "
            "VALUES (?, 'syllabus', 'izlence.pdf', ?)",
            (course_id, text),
        )
        await conn.commit()


async def _course_id_for_chapter(chapter_id: int) -> int:
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute("SELECT course_id FROM chapters WHERE id = ?", (chapter_id,))
        row = await cursor.fetchone()
        assert row is not None
        return row[0]


async def test_load_kazanimlar_returns_latest_syllabus_text(client):
    from src.db import get_db

    chapter_id = await _make_chapter_with_slides(client)
    course_id = await _course_id_for_chapter(chapter_id)
    await _insert_syllabus(course_id, "Kazanım 1: türev alabilme.")

    db = await get_db()
    try:
        text = await note_generator.load_kazanimlar(db, course_id, "local")
    finally:
        await db.close()
    assert text == "Kazanım 1: türev alabilme."


async def test_load_kazanimlar_empty_without_syllabus(client):
    """Syllabus materyali yüklenmemişse boş string döner (not/quiz üretimi kazanımsız çalışır)."""
    from src.db import get_db

    chapter_id = await _make_chapter_with_slides(client)
    course_id = await _course_id_for_chapter(chapter_id)

    db = await get_db()
    try:
        text = await note_generator.load_kazanimlar(db, course_id, "local")
    finally:
        await db.close()
    assert text == ""


async def test_load_kazanimlar_truncates_long_text(client):
    from src.db import get_db

    chapter_id = await _make_chapter_with_slides(client)
    course_id = await _course_id_for_chapter(chapter_id)
    await _insert_syllabus(course_id, "a" * (note_generator.KAZANIMLAR_MAX_CHARS + 500))

    db = await get_db()
    try:
        text = await note_generator.load_kazanimlar(db, course_id, "local")
    finally:
        await db.close()
    assert len(text) == note_generator.KAZANIMLAR_MAX_CHARS


# ── Global atıf numaralandırma + kaynakça (atif-kaynakca) ──────────────
#
# Kullanıcı hatası: her bölüm kendi kaynak listesini 1'den numaralıyordu → birleşen
# notta numaralar çakışıyordu (1 2 3 / 1 2 3). Ayrıca web kaynağı ile materyal kaynağı
# görsel olarak ayrılmıyordu ve notun sonunda kaynakça yoktu.

GD_TEXT = "Bağlı listeler her düğümün bir sonraki düğüme işaret ettiği doğrusal veri yapısıdır."
GD_SORT_TEXT = "Sıralama algoritmaları karşılaştırma tabanlı çalışır ve karmaşıklıkları farklıdır."
GD_SLIDE_TEXT = "Yığınlar son giren ilk çıkar kuralıyla çalışan bir veri yapısıdır."
GD_WEB_URL = "https://example.com/liste"


def _chunk(chunk_id: str, text: str, *, material_id: int, page=None, slide=None) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "material_id": material_id,
        "page": page,
        "slide": slide,
        "score": 0.9,
    }


async def _insert_material(course_id: int, filename: str, mtype: str) -> int:
    """Materyal satırı ekler; kaynakça satırındaki görünen ad bundan türetilir."""
    import aiosqlite

    from src.auth import LOCAL_TENANT_ID
    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO materials (tenant_id, course_id, type, filepath) VALUES (?, ?, ?, ?)",
            (LOCAL_TENANT_ID, course_id, mtype, f"/tmp/mat/{course_id}/{'a' * 32}_{filename}"),
        )
        await conn.commit()
        row_id = cursor.lastrowid
    assert row_id is not None
    return row_id


def _mock_note_llm(monkeypatch, *, topics, sections, chunks_for, web_sources=None):
    """Konu bazlı sahte üretim: bölüm metni konu adına göre seçilir.

    Çıpa `"{konu}" konusunu`dur (üç üretim prompt'unda da var) — chunk/slayt metni
    başka bir konu adı içerse bile eşleşme karışmaz.
    """

    async def fake_chat_json(messages, **kwargs):
        if kwargs.get("kind") == "topic_extraction":
            # dict ise birebir geçirilir (note_title + topics); liste ise sarılır.
            return topics if isinstance(topics, dict) else {"topics": topics}
        return {}

    async def fake_chat_stream(messages, **kwargs):
        prompt = messages[0]["content"]
        for name, text in sections.items():
            if f'"{name}" konusunu' in prompt:
                yield text
                return
        yield ""

    monkeypatch.setattr(llm_service, "chat_json", fake_chat_json)
    monkeypatch.setattr(llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(
        retrieval,
        "hybrid_search",
        lambda course_id, query, keywords=None, **kw: list(chunks_for.get(query, [])),
    )

    async def _web_enabled():
        return web_sources is not None

    async def _search(topic, course_name, max_results=3):
        return list(web_sources or [])

    monkeypatch.setattr(web_search_service, "web_search_enabled", _web_enabled)
    monkeypatch.setattr(web_search_service, "search_web", _search)


async def _note_of(chapter_id: int) -> dict:
    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    errors = [e for e in events if e["type"] == "error"]
    assert not errors, errors
    return next(e for e in events if e["type"] == "done")["note"]


async def test_citation_numbers_continue_across_sections(client, monkeypatch):
    """İkinci bölümün numaraları 1'den BAŞLAMAZ; birinci bölümün bıraktığı yerden sürer."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
    ]
    _mock_note_llm(
        monkeypatch,
        topics=topics,
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} [1]",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_9_1_1", GD_TEXT, material_id=9, page=3)],
            "Sıralama": [_chunk("chk_9_2_1", GD_SORT_TEXT, material_id=9, page=7)],
        },
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert f"{GD_TEXT} [1]" in content
    assert f"{GD_SORT_TEXT} [2]" in content  # 1'den yeniden başlamaz
    assert "[2]" in content and content.count("[1]") >= 1
    ids = [c["id"] for t in note["citations_json"]["topics"] for c in t["citations"]]
    assert ids == [1, 2]
    # kaynakça: materyal adı veritabanında yoksa genel adla yazılır
    assert "- [1] Ders materyali, s. 3" in content
    assert "- [2] Ders materyali, s. 7" in content


async def test_same_chunk_in_two_sections_reuses_one_number(client, monkeypatch):
    """Aynı chunk iki bölümde geçerse TEK global numara alır (yeni numara üretilmez)."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Düğüm Yapısı", "keywords": ["işaretçi"], "slide_refs": [1]},
    ]
    shared = _chunk("chk_9_1_1", GD_TEXT, material_id=9, page=3)
    _mock_note_llm(
        monkeypatch,
        topics=topics,
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Düğüm Yapısı": f"### Düğüm Yapısı\n\n{GD_TEXT} [1]",
        },
        chunks_for={"Bağlı Listeler": [shared], "Düğüm Yapısı": [shared]},
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert content.count(GD_TEXT) == 2
    assert content.count(f"{GD_TEXT} [1]") == 2  # ikisi de [1]
    assert "[2]" not in content
    entries = [c for t in note["citations_json"]["topics"] for c in t["citations"]]
    assert [c["id"] for c in entries] == [1, 1]
    assert all(c["chunk_id"] == "chk_9_1_1" for c in entries)
    # kaynakçada tek satır (aynı chunk iki kez listelenmez)
    assert content.count("- [1] Ders materyali, s. 3") == 1


async def test_web_citation_uses_angle_brackets(client, monkeypatch):
    """Web kaynağı ⟨n⟩, kitap/slayt [n] — görsel tip ayrımı backend'de yapılır."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
    ]
    _mock_note_llm(
        monkeypatch,
        topics=topics,
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} [1]",
        },
        chunks_for={"Bağlı Listeler": [_chunk("chk_9_1_1", GD_TEXT, material_id=9, page=3)]},
        web_sources=[
            {
                "title": "Örnek Web Kaynağı",
                "url": GD_WEB_URL,
                "text": GD_SORT_TEXT,
                "quote": GD_SORT_TEXT,
            }
        ],
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert f"{GD_TEXT} [1]" in content
    assert f"{GD_SORT_TEXT} ⟨2⟩" in content
    by_type = {t["topic"]: t["citations"][0] for t in note["citations_json"]["topics"]}
    assert by_type["Bağlı Listeler"]["source_type"] == "textbook"
    assert by_type["Bağlı Listeler"]["id"] == 1
    assert by_type["Sıralama"]["source_type"] == "web"
    assert by_type["Sıralama"]["id"] == 2
    assert by_type["Sıralama"]["url"] == GD_WEB_URL


async def test_bibliography_lists_all_source_types(client, monkeypatch):
    """Kaynakça üç tipi de kendi biçimiyle listeler: sayfa / slayt / URL."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    course_id = await _course_id_for_chapter(chapter_id)
    textbook_id = await _insert_material(course_id, "Veri Yapıları.pdf", "textbook")
    slides_id = await _insert_material(course_id, "Hafta-1 Sunum.pptx", "slides")

    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Yığınlar", "keywords": ["yığın"], "slide_refs": [1]},
        {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
    ]
    _mock_note_llm(
        monkeypatch,
        topics=topics,
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Yığınlar": f"### Yığınlar\n\n{GD_SLIDE_TEXT} [1]",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} [1]",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=textbook_id, page=3)],
            "Yığınlar": [_chunk("chk_2", GD_SLIDE_TEXT, material_id=slides_id, slide=5)],
        },
        web_sources=[
            {
                "title": "Örnek Web Kaynağı",
                "url": GD_WEB_URL,
                "text": GD_SORT_TEXT,
                "quote": GD_SORT_TEXT,
            }
        ],
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert content.rstrip().endswith(
        "\n".join(
            [
                "- [1] Veri Yapıları.pdf, s. 3",
                "- [2] Hafta-1 Sunum.pptx, slayt 5",
                f"- ⟨3⟩ Örnek Web Kaynağı — <{GD_WEB_URL}>",
            ]
        )
    )
    assert "## Kaynakça" in content
    # kaynakça not içeriğinin parçası olarak kaydedilir
    import aiosqlite

    from src.config import settings

    async with aiosqlite.connect(settings.db_path) as conn:
        cursor = await conn.execute(
            "SELECT content_md FROM notes WHERE chapter_id = ?", (chapter_id,)
        )
        row = await cursor.fetchone()
    assert row is not None
    assert "## Kaynakça" in row[0]


async def test_bibliography_covers_every_body_chip(client, monkeypatch):
    """Kaynakça, gövdede duran HER atıf çipini kapsar (kullanıcı isteği 1).

    Not 25 koşusunun hatası: yedek zincir `content_md += new_block` ile bölümü ekliyor,
    atıf kaydını GÜNCELLEMİYOR → kaynakça atıfı listelemiyor ama gövdede çip kalıyordu.
    Artık kayıt aşamasından önce gövde gerçeğiyle eşitleniyor.
    """
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    course_id = await _course_id_for_chapter(chapter_id)
    textbook_id = await _insert_material(course_id, "Veri Yapıları.pdf", "textbook")

    # İkinci konunun bölümünü yalnız topic kaydına ekle (yedek zincir senaryosu:
    # gövdeye çip yazıldı ama topic_citations kaydı güncel değil).
    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
    ]
    _mock_note_llm(
        monkeypatch,
        topics=topics,
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} [1]",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=textbook_id, page=3)],
            "Sıralama": [_chunk("chk_2", GD_SORT_TEXT, material_id=textbook_id, page=7)],
        },
    )

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    errors = [e for e in events if e["type"] == "error"]
    assert not errors, errors
    note = next(e for e in events if e["type"] == "done")["note"]
    content = note["content_md"]
    govde = content.split("## Kaynakça")[0]
    # Gövdede her iki çip de duruyor
    assert f"{GD_TEXT} [1]" in govde
    assert f"{GD_SORT_TEXT} [2]" in govde
    # Kaynakça İKİ ATIFI da listeliyor — gövdede çipi olmayan kaynak yok
    kaynakca_satirlari = content.split("## Kaynakça")[1]
    assert "- [1] Veri Yapıları.pdf, s. 3" in kaynakca_satirlari
    assert "- [2] Veri Yapıları.pdf, s. 7" in kaynakca_satirlari
    # topic kayıtları da gövdeyle eşit
    ids = [c["id"] for t in note["citations_json"]["topics"] for c in t["citations"]]
    assert ids == [1, 2]


async def test_note_title_h1_always_present(client, monkeypatch):
    """Notun genel ana başlığı MUTLAKA var (kullanıcı isteği 3):
    - model note_title döndürürse o kullanılır,
    - döndürmezse chapter başlığına düşer,
    - H1, düzgün üretilmiş "### Konu" başlangıçlı notun da üstüne EKLENİR.
    """
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    topics = [
        {"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]},
        {"topic": "Sıralama", "keywords": ["sıralama"], "slide_refs": [1]},
    ]
    _mock_note_llm(
        monkeypatch,
        topics={"note_title": "Bağlı Liste ve Sıralama Yöntemleri", "topics": topics},
        sections={
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} [1]",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=9, page=3)],
            "Sıralama": [_chunk("chk_2", GD_SORT_TEXT, material_id=9, page=7)],
        },
    )



    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert content.startswith("# Bağlı Liste ve Sıralama Yöntemleri\n\n### Bağlı Listeler")
    assert "\n## Kaynakça" in content


async def test_note_title_falls_back_to_chapter_title(client, monkeypatch):
    """Model note_title döndürmezse chapter başlığı genel başlığa düşer."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    _mock_note_llm(
        monkeypatch,
        topics=[{"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]}],
        sections={"Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT} [1]"},
        chunks_for={"Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=9, page=3)]},
    )

    note = await _note_of(chapter_id)
    assert note["content_md"].startswith("# Bağlı Listeler\n")


def test_sync_bibliography_reconstructs_from_body_and_repairs_headings():
    """Birim: yapışık başlık bölünür, duplicate birleşir, kayıt gövde çiplerine eşitlenir."""
    reg = note_generator._CitationRegistry()
    c1 = reg.resolve(_chunk("chk_1", "A metni", material_id=9, page=3))
    reg.resolve(_chunk("chk_2", "B metni", material_id=9, page=7))

    content = (
        "### İlk Konu\n"
        "gövde [1]\n"
        "birleştirir.### İkinci Konu\n"  # yapışık başlık
        "gövde [2]\n"
        "\n"
        "### İkinci Konu\n"  # komşu duplicate
        "gövde [2]"
    )
    # Kayıt "İkinci Konu"nun atıfını BİLMİYOR (yedek zincir senaryosu): boş liste
    topic_citations = {"İlk Konu": [dict(c1)], "İkinci Konu": []}

    out_content, out_cites = note_generator._sync_bibliography(
        content, reg, topic_citations, {9: "Veri Yapıları.pdf"}
    )

    assert "birleştirir.###" not in out_content
    # komşu duplicate birleşir; kayıt gövdede duran [2] ile eşitlenir
    assert [c["id"] for c in out_cites["İkinci Konu"]] == [2]
    kayn = out_content.split("## Kaynakça")[1]
    assert "- [1] Veri Yapıları.pdf, s. 3" in kayn
    assert "- [2] Veri Yapıları.pdf, s. 7" in kayn
    assert [c["id"] for c in out_cites["İkinci Konu"]] == [2]


def test_strip_memory_subsection_headings_keeps_topic_headings():
    src = (
        "### Konu A\n"
        "giriş cümlesi\n"
        "\n"
        "### Hatırlatıcı\n"
        "- ipucu\n"
        "### Ne işe yarar?\n"
        "kullanım cümlesi\n"
        "### Kavramlar\n"
        "- **Terim** — tanım [1]\n"
        "### Konu B\n"
        "devam [1]"
    )
    out = note_generator._strip_memory_subsection_headings(src)
    assert "### Konu A" in out and "### Konu B" in out
    assert "Hatırlatıcı" not in out and "Ne işe yarar" not in out and "Kavramlar" not in out
    assert "- ipucu" in out and "kullanım cümlesi" in out and "- **Terim**" in out


def test_strip_memory_subsection_headings_protects_kaynakca():
    src = "### Konu\ngövde\n## Kaynakça\n- [1] Kaynak"
    out = note_generator._strip_memory_subsection_headings(src)
    assert "## Kaynakça" in out and "- [1] Kaynak" in out


def test_merge_repeated_memory_headings_merges_duplicates():
    src = "### Konu\n\n### Hatırlatıcı\n- a\n\n### Hatırlatıcı\n- b\n\n### Diğer"
    out = note_generator._merge_repeated_memory_headings(src)
    assert out.count("### Hatırlatıcı") == 1
    assert "- a" in out and "- b" in out
