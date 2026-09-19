"""Not üretimi pipeline testleri (Faz 3.1) — LLM ve retrieval mock'lu.

ATIF SİSTEMİ KALDIRILDI (2026-09-19): notlar atıfsız üretilir. Testler artık şunları
doğrular: (1) model yasağa rağmen [n] yazarsa gövde temizlenir, (2) kaynakça
YAZILMAZ, (3) citations_json boş atıf listeleriyle yazılır (geriye uyumluluk).
"""

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
    f"doğrusal veri yapısıdır.\n\n- Her düğüm veri ve işaretçi taşır."
)
SIRALAMA_SECTION = "### Sıralama\n\nSıralama algoritmaları karşılaştırma yapar."


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


def _setup_mocks(monkeypatch, *, topics=None, section=None, coverage_missing=None):
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
    # Atıf sistemi kaldırıldı: citations_json boş atıf listeleriyle yazılır (geriye uyumluluk).
    assert note["citations_json"]["topics"][0]["topic"] == TOPIC
    assert note["citations_json"]["topics"][0]["citations"] == []
    # Kaynakça YAZILMAZ.
    assert "Kaynakça" not in note["content_md"]

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
    'düğüme işaret ettiği doğrusal veri yapısıdır.\\n\\n- Her düğüm veri ve işaretçi '
    'taşır."}\n```'
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

    content = "### A\n\neski metin.\n\n### B\n\nyeni metin."
    pattern = _re.compile(r"^#{1,4}\s+A\s*$", _re.MULTILINE)
    out, replaced = note_generator._replace_section(content, pattern, "### A\n\ndüzeltilmiş metin.")
    assert replaced
    assert out == "### A\n\ndüzeltilmiş metin.\n\n### B\n\nyeni metin."


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
        return {}

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


async def test_model_markers_are_stripped_from_body(client, monkeypatch):
    """Model yasağa rağmen metne [n] yazarsa kullanıcıya GÖSTERİLMEZ (atıf sistemi kaldırıldı)."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    cited_section = (
        f"### {TOPIC}\n\n{CHUNK_TEXT} [1]\n\n- Her düğüm veri taşır [2]. Kayıt [12]."
    )
    _setup_mocks(monkeypatch, section=cited_section)

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert "[1]" not in content
    assert "[2]" not in content
    assert "[12]" not in content
    # İçerik korunur, yalnız işaretler gider.
    assert CHUNK_TEXT in content
    assert "Her düğüm veri taşır." in content


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


async def test_web_fallback_strips_markers(client, monkeypatch):
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "Bağlı listeler konusu")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    _setup_fallback_mocks(monkeypatch, web_enabled=True, section=WEB_SECTION)

    events = await _collect_events(note_generator.generate_notes_stream(chapter_id))
    done = next(e for e in events if e["type"] == "done")
    content = done["note"]["content_md"]
    assert TOPIC in content
    assert "[1]" not in content and "⟨" not in content
    assert "uyarılı not" not in content


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
    """Kapsama düzeltme turunda sağlayıcı zinciri tükenirse (LLMError) not YİNE DE teslim edilir.

    Regresyon (2026-09-05): `_regen_topic`'in gerçek-içerik yolu (chunks mevcut) LLMError'ı
    yakalamıyordu — zaten üretilmiş 8 bölümlük bir not, düzeltme turunda sağlayıcı
    kotası tükendiği an tamamen çöpe atılıyordu (bkz. Backlog.md). Artık `_regen_topic`
    başarısızlığı "bu turda değişiklik yok" sayılır, mevcut bölüm korunur.
    """
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    monkeypatch.setattr(llm_service.settings, "google_api_key", "sk-test")
    good_section = f"### {TOPIC}\n\n{CHUNK_TEXT}"
    _setup_mocks(monkeypatch, section=good_section)

    async def fake_chat_stream_exhausted(messages, **kwargs):
        kind = kwargs.get("kind", "")
        if kind == "note_regeneration":
            # Tüm sağlayıcılar tükendi (2026-09-05'te gerçekleşen gerçek senaryo).
            raise llm_service.LLMError("API kotası aşıldı. Birazdan tekrar deneyin.")
        for delta in [good_section[i : i + 20] for i in range(0, len(good_section), 20)]:
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
    # Sağlayıcı tükense bile önceki bölüm korunur, not boşalmaz.
    assert CHUNK_TEXT in done["note"]["content_md"]


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


# ── Atıfsız üretim: çok konulu akış + başlık kuralları ────────────────

GD_TEXT = "Bağlı listeler her düğümün bir sonraki düğüme işaret ettiği doğrusal veri yapısıdır."
GD_SORT_TEXT = "Sıralama algoritmaları karşılaştırma tabanlı çalışır ve karmaşıklıkları farklıdır."


def _chunk(chunk_id: str, text: str, *, material_id: int, page=None, slide=None) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "material_id": material_id,
        "page": page,
        "slide": slide,
        "score": 0.9,
    }


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


async def test_two_topic_note_has_no_markers_and_no_bibliography(client, monkeypatch):
    """Çok konulu notta işaret yok, kaynakça yok; her bölümün içeriği korunur."""
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
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT} ⟨2⟩",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_9_1_1", GD_TEXT, material_id=9, page=3)],
            "Sıralama": [_chunk("chk_9_2_1", GD_SORT_TEXT, material_id=9, page=7)],
        },
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert GD_TEXT in content and GD_SORT_TEXT in content
    assert "[1]" not in content and "[2]" not in content and "⟨" not in content
    assert "## Kaynakça" not in content
    assert "Kaynakça" not in content


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
            "Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT}",
            "Sıralama": f"### Sıralama\n\n{GD_SORT_TEXT}",
        },
        chunks_for={
            "Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=9, page=3)],
            "Sıralama": [_chunk("chk_2", GD_SORT_TEXT, material_id=9, page=7)],
        },
    )

    note = await _note_of(chapter_id)
    content = note["content_md"]
    assert content.startswith("# Bağlı Liste ve Sıralama Yöntemleri\n\n### Bağlı Listeler")
    assert "## Kaynakça" not in content


async def test_note_title_falls_back_to_chapter_title(client, monkeypatch):
    """Model note_title döndürmezse chapter başlığı genel başlığa düşer."""
    chapter_id = await _make_chapter_with_slides(client)
    await _insert_slide(chapter_id, 1, "İçerik")
    _mock_note_llm(
        monkeypatch,
        topics=[{"topic": "Bağlı Listeler", "keywords": ["düğüm"], "slide_refs": [1]}],
        sections={"Bağlı Listeler": f"### Bağlı Listeler\n\n{GD_TEXT}"},
        chunks_for={"Bağlı Listeler": [_chunk("chk_1", GD_TEXT, material_id=9, page=3)]},
    )

    note = await _note_of(chapter_id)
    assert note["content_md"].startswith("# Bağlı Listeler\n")


def test_strip_note_markers_cleans_spacing():
    """İşaret silinince bıraktığı boşluk/nokta öncesi boşluk düzeltilir."""
    out = note_generator._strip_note_markers(
        "Cümle bir [1] devam.\n\nCümle iki [2]. Çift  boşluk  [12] düzelir."
    )
    assert "[1]" not in out and "[2]" not in out and "[12]" not in out
    assert "Cümle bir devam." in out
    assert "Cümle iki." in out
    assert "Çift boşluk düzelir." in out


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
        "- **Terim** — tanım\n"
        "### Konu B\n"
        "devam"
    )
    out = note_generator._strip_memory_subsection_headings(src)
    assert "### Konu A" in out and "### Konu B" in out
    assert "Hatırlatıcı" not in out and "Ne işe yarar" not in out and "Kavramlar" not in out
    assert "- ipucu" in out and "kullanım cümlesi" in out and "- **Terim**" in out


def test_merge_repeated_memory_headings_merges_duplicates():
    src = "### Konu\n\n### Hatırlatıcı\n- a\n\n### Hatırlatıcı\n- b\n\n### Diğer"
    out = note_generator._merge_repeated_memory_headings(src)
    assert out.count("### Hatırlatıcı") == 1
    assert "- a" in out and "- b" in out
