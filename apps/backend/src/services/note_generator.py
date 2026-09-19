"""Map-reduce not üretimi — konu çıkarımı, hibrit retrieval, kapsama denetimi (Faz 3.1).

ATIF SİSTEMİ KALDIRILDI (2026-09-19): notlar hâlâ YALNIZ sağlanan kaynaklardan (kitap/slayt/web)
yazılır ama model metne [n] işareti yazmaz ve kullanıcıya kaynakça/atıf GÖSTERİLMEZ.
`citations_json` kaydı geriye uyumluluk için boş şemayle ({"topics": [...]}) yazılmaya devam eder
(quiz/flashcard üretimi ve `coverage` router'ı bu alanı okur); artık boş atıf listeleri taşır.
`_validate_citations` / `CITATION_CONFIRM_PROMPT` / `_sync_bibliography` zinciri kaldırıldı.

`generate_notes_stream(chapter_id)` bir async generator'dır; SSE olayları yield eder:
  {"type": "status", "percent": int, "message": str}
  {"type": "delta", "text": str}
  {"type": "done", "note": {...}}
  {"type": "error", "message": str}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..db import get_db
from ..prompts.common import dil_talimati, kazanimlar_blok
from ..prompts.note_prompts import (
    COVERAGE_CHECK_PROMPT,
    NOTE_GENERATION_PROMPT,
    NOTE_GENERATION_WEB_PROMPT,
    NOTE_SLIDE_ONLY_PROMPT,
    TOPIC_EXTRACTION_PROMPT,
)
from . import llm_service, note_cleanup, retrieval, web_search_service

logger = logging.getLogger(__name__)

MAX_COVERAGE_ITERATIONS = 3
# Ders için yüklenmiş syllabus/müfredat materyalinin prompt'a eklenecek azami karakter
# sayısı — dev bir PDF metni tüm topic/section promptlarını şişirmesin diye kırpılır.
KAZANIMLAR_MAX_CHARS = 4000
SLIDES_CONTEXT_CHARS = 8000
NOTE_CONTEXT_CHARS = 6000
# Bölüm yazımı çağrılarının çıktı bütçesi. Reasoning sağlayıcısında (opencode/deepseek)
# gizli reasoning token'ları DA bu bütçeden harcanır; sağlayıcı varsayılanı (8192) uzun
# bölüm promptunda tamamen reasoning'e gidip yanıtı BOŞ döndürebiliyordu (2026-09-17 canlı
# ölçüm: aynı prompt 8192'de boş/`finish_reason=length`, 16384'te tam içerik; bir canlı
# üretimde 2/2 bölüm bu yüzden ham slayt dökümüne düşmüştü). 16384 sağlayıcı tarafından
# kabul ediliyor (canlı doğrulandı: 9042 completion token'lı yanıt).
SECTION_MAX_TOKENS = 16384

# Not akışının TAMAMI düşük reasoning ile çalışır (koordinatör kararı, 2026-09-17).
# opencode/deepseek sağlayıcısında gizli reasoning token'ları yanıt bütçesinden
# harcanıyor; yüksek effort uzun bölüm promptlarında yanıtı boş bırakıp bölüm başına
# süreyi ~45-55sn'ye çıkarıyordu. Geçersiz kılma ÇAĞRI BAZINDA geçirilir — diğer
# akışlar (quiz/overall/essay/chat) sağlayıcının kendi ayarıyla (high) çalışmaya
# devam eder; `llm_service` bu değeri yalnızca sağlayıcının mevcut ayarını
# düşürecekse uygular (bkz. `llm_service._apply_reasoning_effort`).
NOTE_REASONING_EFFORT = "low"


class NoteGenerationError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


# ── Metin yardımcıları ─────────────────────────────────────────────────

# Not üretimi artık atıfsız: model metne [n] yazmaz (ATIF_YASAGI), ancak her ihtimale
# karşı kayıt öncesi gövdede kalmış olabilecek numara işaretleri ([3], ⟨3⟩) temizlenir.
_MARKER_RE = re.compile(r"\[(\d+)\]|⟨(\d+)⟩")


def _strip_note_markers(text: str) -> str:
    """Metindeki [n] / ⟨n⟩ numara işaretlerini siler (atıf sistemi kaldırıldı).

    Model prompt yasağına rağmen ara sıra işaret üretebilir; kullanıcıya ASLA
    numara işareti gösterilmez. İşaret silinince bıraktığı boşluk düzeltilir.
    """
    cleaned = _MARKER_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+([,.!?;:])", r"\1", cleaned)
    # İşaret cümle sonundayken "...metin ." kalıntısını düzelt
    return re.sub(r" +([,.!?;:])", r"\1", cleaned)


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def topic_matches(heading: str, topic: str) -> bool:
    """Başlık ↔ konu adı eşleşmesi (tam ya da anlamlı alt-metin).

    LLM başlığı konu adından sapabilir; kapsama eşlemesinde esneklik sağlar.
    """
    a = _normalize(heading)
    b = _normalize(topic)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(b) >= 4 and b in a:
        return True
    return len(a) >= 4 and a in b


def _slide_content_for_topic(topic: dict, slides: list[dict]) -> str:
    refs = [int(r) for r in topic.get("slide_refs", []) if str(r).isdigit()]
    if refs:
        selected = [s for s in slides if s["slide_no"] in refs]
        if selected:
            return "\n\n".join(f"[Slide {s['slide_no']}] {s['content_text']}" for s in selected)
    return "\n\n".join(f"[Slide {s['slide_no']}] {s['content_text']}" for s in slides)


def _slides_digest(slides: list[dict], max_chars: int = SLIDES_CONTEXT_CHARS) -> str:
    """Sunum metnini konu çıkarımı bütçesine TÜM slaytları kapsayacak şekilde sığdırır.

    Eskiden `"\\n\\n".join(...)[:SLIDES_CONTEXT_CHARS]` düz kırpılıyordu: 38 slaytlık
    sunumda 30. slayttan sonrası prompt'a hiç girmiyor, o slaytların konuları nota
    hiç alınmıyordu (2026-09-17 canlı vaka: 50 slaytlık sunumda 37-50 arası kayıptı).
    Bütçe önce her slayda eşit dağıtılır, artan pay uzun slaytların gövdesine verilir;
    böylece her slaydın en azından girişi (başlık + ilk satırlar) prompt'a girer.
    Sunum bütçeye sığıyorsa çıktı eskisiyle birebir aynıdır (tam metin).
    """
    parts = [(f"[Slide {s['slide_no']}] ", (s.get("content_text") or "").strip()) for s in slides]
    gaps = 2 * (len(parts) - 1)
    if sum(len(p) + len(b) for p, b in parts) + gaps <= max_chars:
        return "\n\n".join(p + b for p, b in parts)

    budget = max(0, max_chars - gaps - sum(len(p) for p, _ in parts))
    alloc = [min(len(b), max(80, budget // len(parts))) for _, b in parts]
    remaining = budget - sum(alloc)
    while remaining > 0:
        cut = [i for i, (_, b) in enumerate(parts) if alloc[i] < len(b)]
        if not cut:
            break
        step = max(1, remaining // len(cut))
        for i in cut:
            add = min(step, len(parts[i][1]) - alloc[i], remaining)
            alloc[i] += add
            remaining -= add
            if remaining <= 0:
                break
    lines = []
    for (prefix, body), take in zip(parts, alloc, strict=True):
        if take < len(body):
            body = body[: max(0, take - 2)].rstrip() + " …"
        lines.append(prefix + body)
    return "\n\n".join(lines)


def _strip_own_heading(section: str, topic_name: str) -> str:
    """Bölüm metninin başındaki kendi başlığını kaldırır (yeniden üretim turlarında).

    `_replace_section` yeni bloğa başlığı kendisi ekler; LLM çıktısı başlıkla
    başlıyorsa kopya oluşurdu (bölüm ayrıştırmayı bozar).
    """
    pattern = re.compile(rf"^#{{2,4}}\s+{re.escape(topic_name)}\s*\n+", re.MULTILINE)
    return pattern.sub("", section, count=1).strip()


def _section_for_topic(content_md: str, topic_name: str) -> str:
    pattern = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
    match = None
    for m in pattern.finditer(content_md):
        if topic_matches(m.group(2), topic_name):
            match = m
            break
    if match is None:
        return ""
    start = match.end()
    next_heading = re.search(r"^#{1,4}\s+", content_md[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content_md)
    return content_md[start:end].strip()


async def load_kazanimlar(db, course_id: int, tenant_id: str) -> str:
    """Dersin en son yüklenen syllabus/müfredat materyalinin metnini döner.

    Materyal yoksa (ya da metni boşsa) boş string döner — not/quiz üretimi
    kazanımsız da normal şekilde çalışmaya devam eder.
    """
    cursor = await db.execute(
        "SELECT extracted_text FROM materials WHERE course_id = ? AND tenant_id = ? "
        "AND type = 'syllabus' ORDER BY id DESC LIMIT 1",
        (course_id, tenant_id),
    )
    row = await cursor.fetchone()
    text = (row["extracted_text"] if row else None) or ""
    return text[:KAZANIMLAR_MAX_CHARS]


async def _safe_hybrid_search(course_id: int, query: str, keywords: list[str]) -> list[dict]:
    """`retrieval.hybrid_search` sarmalayıcısı — embedding/lancedb hatasında boş liste döner.

    Kapsama/atıf düzeltme turlarında (2026-09-06 kullanıcı geri bildirimi: üretim bu
    aşamalarda sessizce iptal oluyordu) beklenmeyen bir retrieval hatası tüm akışı
    ÇÖKERTMEMELİ — üst katman zaten "kaynak yok" durumunu web/slayt yedeğiyle ele alıyor.

    `hybrid_search` senkron ve ağır bir çağrıdır (bge-m3 CPU inference + LanceDB
    okuması). Doğrudan çağrılırsa tüm event loop'u bloklar — tek bir not üretimi
    bunu 10+ kez yaptığından, o process'teki HER kullanıcının isteği bu süre boyunca
    beklerdi. `to_thread` ile executor'a devredilir.
    """
    try:
        return await asyncio.to_thread(retrieval.hybrid_search, course_id, query, keywords)
    except Exception:
        logger.warning("retrieval başarısız, yedek zincire düşülüyor: %s", query, exc_info=True)
        return []


# ── LLM adımları ───────────────────────────────────────────────────────

async def _extract_topics(
    slides: list[dict], course_id: int, chapter_id: int, tenant_id: str, kazanimlar: str
) -> tuple[list[dict], str | None]:
    """Konular + notun GENEL ANA BAŞLIĞI (note_title).

    note_title prompt ile istenir (şema: {"note_title": ..., "topics": ...}); model
    döndürmezse None döner — çağıran taraf chapter başlığıyla düşer (kullanıcı isteği:
    genel başlık MUTLAKA olmalı).
    """

    async def _attempt() -> tuple[list[dict], str | None]:
        data = await llm_service.chat_json(
            [
                {
                    "role": "user",
                    "content": TOPIC_EXTRACTION_PROMPT.format(
                        slides=_slides_digest(slides),
                        dil_talimati=dil_talimati(settings.not_dili),
                        kazanimlar=kazanimlar_blok(kazanimlar),
                    ),
                }
            ],
            kind="topic_extraction",
            reasoning_effort=NOTE_REASONING_EFFORT,
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        )
        topics = data.get("topics", [])
        clean = [t for t in topics if isinstance(t, dict) and t.get("topic", "").strip()]
        raw_title = data.get("note_title")
        note_title = raw_title.strip() if isinstance(raw_title, str) else None
        return clean, (note_title or None)

    clean, note_title = await _attempt()
    if not clean:
        # Ücretsiz LLM zinciri ara sıra boş/geçersiz JSON döndürüyor (bkz. generation_logs
        # id=51, 2026-09-05 — dolu slaytlarla bile gerçekleşti). Tek seferlik yeniden deneme,
        # kalıcı arıza yerine geçici sağlayıcı tekilliğini tolere eder.
        clean, note_title = await _attempt()
    return clean, note_title


async def _check_coverage(
    topics: list[dict], content_md: str, course_id: int, chapter_id: int, tenant_id: str
) -> list[str]:
    topic_names = [t["topic"] for t in topics]
    data = await llm_service.chat_json(
        [
            {
                "role": "user",
                "content": COVERAGE_CHECK_PROMPT.format(
                    topics=json.dumps(topic_names, ensure_ascii=False),
                    note=content_md[:NOTE_CONTEXT_CHARS],
                ),
            }
        ],
        kind="coverage_check",
        reasoning_effort=NOTE_REASONING_EFFORT,
        tenant_id=tenant_id,
        course_id=course_id,
        chapter_id=chapter_id,
    )
    missing = data.get("missing", [])
    return [m for m in missing if isinstance(m, str) and m.strip()]


# ── Üretim yardımcıları ────────────────────────────────────────────────

def _numbered_sources(chunks: list[dict]) -> str:
    return "\n".join(
        f"[{idx}] (sayfa {c['page'] or '-'} / slide {c['slide'] or '-'}) {c['text']}"
        for idx, c in enumerate(chunks, start=1)
    )


def _numbered_web_sources(chunks: list[dict]) -> str:
    lines: list[str] = []
    for idx, c in enumerate(chunks, start=1):
        header = c.get("title") or c.get("url") or "web kaynağı"
        lines.append(f"[{idx}] ({header}) {c['text']}")
    return "\n".join(lines)


def _web_sources_to_chunks(web_sources: list[dict]) -> list[dict]:
    """Web sonuçlarını chunk benzeri listeye çevirir (atıf zincirinin geri kalanıyla uyumlu)."""
    return [
        {
            "chunk_id": f"web-{i + 1}",
            "text": s["text"],
            "material_id": None,
            "page": None,
            "slide": None,
            "score": 1.0,
            "url": s["url"],
            "title": s["title"],
            "quote": s["quote"],
        }
        for i, s in enumerate(web_sources)
    ]


def _build_prompt(topic: dict, slides: list[dict], chunks: list[dict], kazanimlar: str) -> str:
    return NOTE_GENERATION_PROMPT.format(
        topic=topic["topic"],
        slide_content=_slide_content_for_topic(topic, slides),
        numbered_sources=_numbered_sources(chunks),
        dil_talimati=dil_talimati(settings.not_dili, json_sema=False),
        kazanimlar=kazanimlar_blok(kazanimlar),
    )


def _ensure_topic_heading(section: str, topic_name: str) -> str:
    """Bölüm kendi `### {konu}` başlığıyla başlamıyorsa ekler."""
    text = section.strip()
    if re.match(rf"^#{{2,4}}\s+{re.escape(topic_name)}\s*$", text, re.MULTILINE):
        return text
    return f"### {topic_name}\n\n{text}"


def _deterministic_slide_section(topic: dict, slides: list[dict]) -> str:
    """LLM başarısız olsa bile slayt içeriğinden asla boş olmayan deterministik bölüm."""
    return f"### {topic['topic']}\n\n{_slide_content_for_topic(topic, slides)}"


async def _generate_fallback_section(
    topic: dict,
    slides: list[dict],
    course_id: int,
    chapter_id: int,
    course_name: str,
    tenant_id: str,
    kazanimlar: str,
    allow_web: bool = True,
) -> tuple[str, list[str], str]:
    """Kitapta kaynak yokken yedek kaynak zinciri.

    allow_web=True → web → slayt → deterministik slayt; allow_web=False → yalnızca
    slayt → deterministik slayt.
    Dönüş: (bölüm, deltalar, durum mesajı). Bölüm asla boş dönmez.
    """
    deltas: list[str] = []
    name = topic["topic"]

    # (a) Web kaynakları
    if allow_web and await web_search_service.web_search_enabled():
        web_sources = await web_search_service.search_web(name, course_name)
        if web_sources:
            chunks = _web_sources_to_chunks(web_sources)
            prompt = NOTE_GENERATION_WEB_PROMPT.format(
                topic=name,
                numbered_sources=_numbered_web_sources(chunks),
                dil_talimati=dil_talimati(settings.not_dili, json_sema=False),
                kazanimlar=kazanimlar_blok(kazanimlar),
            )
            try:
                stream = note_cleanup.SectionStream()
                async for delta in llm_service.chat_stream(
                    [{"role": "user", "content": prompt}],
                    kind="note_generation_web",
                    max_tokens=SECTION_MAX_TOKENS,
                    reasoning_effort=NOTE_REASONING_EFFORT,
                    tenant_id=tenant_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                ):
                    emitted = stream.feed(delta)
                    if emitted:
                        deltas.append(emitted)
                section = _strip_note_markers(stream.cleaned())
                if section:
                    return (
                        _ensure_topic_heading(section, name),
                        deltas,
                        f"“{name}” için web kaynakları kullanılıyor…",
                    )
            except llm_service.LLMError:
                logger.warning("web not üretimi başarısız; slayt yedeğine düşülüyor: %s", name)

    # (b) Slayt (rehber) içeriğinden tam not
    prompt = NOTE_SLIDE_ONLY_PROMPT.format(
        topic=name,
        slide_content=_slide_content_for_topic(topic, slides),
        dil_talimati=dil_talimati(settings.not_dili, json_sema=False),
        kazanimlar=kazanimlar_blok(kazanimlar),
    )
    try:
        stream = note_cleanup.SectionStream()
        async for delta in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            kind="note_generation_slide_only",
            max_tokens=SECTION_MAX_TOKENS,
            reasoning_effort=NOTE_REASONING_EFFORT,
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        ):
            emitted = stream.feed(delta)
            if emitted:
                deltas.append(emitted)
        # Model yasağa rağmen [n]/⟨n⟩ biçiminde işaret bırakırsa temizlenir —
        # kullanıcıya asla numara işareti gösterilmez.
        section = _strip_note_markers(stream.cleaned())
        if section:
            return (
                _ensure_topic_heading(section, name),
                deltas,
                f"“{name}” sunum içeriğinden yazılıyor…",
            )
    except llm_service.LLMError:
        logger.warning("slayt not üretimi başarısız; deterministik bölüme düşülüyor: %s", name)

    # (c) Her iki yol da başarısız: slayt metninden deterministik bölüm (asla boş değil,
    # LLM gerektirmez — anında biter).
    return (
        _deterministic_slide_section(topic, slides),
        deltas,
        f"“{name}” sunum içeriğinden yazılıyor…",
    )


async def _regen_topic(
    topic: dict,
    slides: list[dict],
    course_id: int,
    chapter_id: int,
    course_name: str,
    tenant_id: str,
    kazanimlar: str,
) -> str | None:
    """Kapsama düzeltme turu için konuyu yeniden üretir (stream'siz).

    Kitapta kaynak yoksa aynı zinciri izler (web → slayt yedeği); bölüm asla boş dönmez.
    Boş yanıt "bu turda değişiklik yok" sayılır (çağıran `None` görür).
    """
    chunks = await _safe_hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
    if not chunks:
        section, _deltas, _msg = await _generate_fallback_section(
            topic,
            slides,
            course_id,
            chapter_id,
            course_name,
            tenant_id,
            kazanimlar,
        )
        return _strip_own_heading(section, topic["topic"])
    prompt = _build_prompt(topic, slides, chunks, kazanimlar)
    parts: list[str] = []
    try:
        async for delta in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            kind="note_regeneration",
            max_tokens=SECTION_MAX_TOKENS,
            reasoning_effort=NOTE_REASONING_EFFORT,
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        ):
            parts.append(delta)
    except llm_service.LLMError:
        # Sağlayıcı zinciri tükendi (2026-09-05 kullanıcı geri bildirimi: bu, zaten üretilmiş
        # notu tamamen çöpe atıyordu) — bu turda değişiklik yok sayılır, önceki bölüm korunur.
        logger.warning("konu yeniden üretimi başarısız, mevcut bölüm korunuyor: %s", topic["topic"])
        return None
    section = _strip_own_heading(
        note_cleanup.normalize_note_markdown("".join(parts)), topic["topic"]
    )
    if not section:
        # Boş akış (reasoning sağlayıcısı yanıt bütçesini gizli reasoning'e harcayabiliyor)
        # "değişiklik yok" sayılır: çağıran taraflar boş bloğu MEVCUT bölümün üzerine
        # yazdığından, aksi halde iyi bir bölüm tamamen boşaltılabiliyordu (2026-09-17
        # canlı vaka: chapter 13 notunda "Uyarıcı-Uyarıcı İlişkilendirmesi" bölümü
        # başlıktan ibaret kalmıştı).
        logger.warning("boş yeniden üretim yanıtı, mevcut bölüm korunuyor: %s", topic["topic"])
        return None
    return _strip_note_markers(section)


async def _safe_regen_topic(*args, **kwargs) -> str | None:
    """`_regen_topic` sarmalayıcısı — beklenmeyen hatada (LLM dışı: retrieval/db/…)
    turu "değişiklik yok" sayar, tüm üretimi ÇÖKERTMEZ (2026-09-06 kullanıcı geri
    bildirimi: kapsama düzeltme turlarında üretim sessizce iptal oluyordu)."""
    try:
        return await _regen_topic(*args, **kwargs)
    except Exception:
        logger.warning("konu yeniden üretimi beklenmeyen hatayla başarısız", exc_info=True)
        return None


async def _safe_fallback_section(*args, **kwargs) -> tuple[str, list[str], str] | None:
    """`_generate_fallback_section` sarmalayıcısı — beklenmeyen hatada `None` döner
    (çağıran taraf mevcut bölümü korur) — aynı gerekçeyle `_safe_regen_topic` gibi."""
    try:
        return await _generate_fallback_section(*args, **kwargs)
    except Exception:
        logger.warning("yedek bölüm üretimi beklenmeyen hatayla başarısız", exc_info=True)
        return None


async def _save_note(
    chapter_id: int,
    content_md: str,
    citations_json: dict,
    topics_json: list[dict],
    tenant_id: str,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO notes "
            "(tenant_id, chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                chapter_id,
                content_md,
                json.dumps(citations_json, ensure_ascii=False),
                json.dumps(topics_json, ensure_ascii=False),
                llm_service.last_model_label(),
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("not kimliği alınamadı")
        return row_id
    finally:
        await db.close()


# ── Kaynakça kaldırıldı (2026-09-19) ──────────────────────────────────
# Atıf sistemi ve kaynakça üretimi tamamen kaldırıldı: not yalnız öğretici metinden
# oluşur, kullanıcıya atıf/kaynakça/kaynak uyarısı GÖSTERİLMEZ. Kaynak temelli üretim
# korunur (promptlar KAYNAK_ROL_AYRIMI ile kaynaklara bağlar).


# ── Ana akış ───────────────────────────────────────────────────────────

async def generate_notes_stream(chapter_id: int, tenant_id: str = LOCAL_TENANT_ID):
    """Not üretim hattı — SSE olayları yield eder (Faz 3.1)."""
    try:
        async for event in _generate(chapter_id, tenant_id):
            yield event
    except NoteGenerationError as exc:
        yield {"type": "error", "message": str(exc)}
    except llm_service.LLMError as exc:
        # API/anahtar/kota hataları kullanıcıya net Türkçe mesajla gider
        yield {"type": "error", "message": str(exc)}
    except Exception:
        logger.exception("not üretimi başarısız: chapter=%s", chapter_id)
        yield {
            "type": "error",
            "message": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
        }


async def _generate(chapter_id: int, tenant_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id, title FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise NoteGenerationError("Chapter bulunamadı")
        course_id = chapter["course_id"]
        chapter_title = chapter["title"]
        cursor = await db.execute(
            "SELECT name FROM courses WHERE id = ? AND tenant_id = ?", (course_id, tenant_id)
        )
        course_row = await cursor.fetchone()
        course_name = course_row["name"] if course_row else "ders"
        cursor = await db.execute(
            "SELECT slide_no, content_text FROM slides WHERE chapter_id = ? AND tenant_id = ? "
            "ORDER BY slide_no ASC",
            (chapter_id, tenant_id),
        )
        slides = [dict(r) for r in await cursor.fetchall()]
        kazanimlar = await load_kazanimlar(db, course_id, tenant_id)
    finally:
        await db.close()

    if not slides:
        raise NoteGenerationError(
            "Bu chapter'da henüz guide slides yok. Önce sunum yükleyin."
        )

    # 1) Konu çıkarımı (+ notun genel ana başlığı)
    yield {"type": "status", "percent": 6, "message": "Konular belirleniyor…"}
    topics, note_title = await _extract_topics(slides, course_id, chapter_id, tenant_id, kazanimlar)
    if not topics:
        raise NoteGenerationError(
            "Sunumdan konu çıkarılamadı. Sunum içeriğini kontrol edip tekrar deneyin."
        )
    # Genel başlık garantisi (kullanıcı isteği): model vermezse chapter başlığı düşer.
    general_title = (note_title or chapter_title or "").strip() or "Ders Notu"

    # 2+3) Konu bazlı map-reduce üretim (stream'li) — atıfsız
    sections: list[str] = []

    for i, topic in enumerate(topics):
        base = 10 + int(72 * i / max(len(topics), 1))
        yield {
            "type": "status",
            "percent": base,
            "message": f"“{topic['topic']}” için kaynaklar taranıyor…",
        }
        chunks = await _safe_hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
        if chunks:
            yield {
                "type": "status",
                "percent": base + 3,
                "message": f"“{topic['topic']}” notu yazılıyor…",
            }
            prompt = _build_prompt(topic, slides, chunks, kazanimlar)
            section = ""
            # Boş akış toleransı: reasoning sağlayıcısı (opencode/deepseek) ara sıra yanıt
            # bütçesini tamamen gizli reasoning'e harcayıp BOŞ metin döndürüyor; tek
            # seferlik yeniden deneme geçici tekilliği tolere eder (aynı desen
            # `_extract_topics`'te de var). Boş bölüm aksi halde içerik değeri olmayan
            # ham slayt dökümüne düşüyordu (2026-09-17 canlı vaka: chapter 13 notunun
            # 12/12 bölümü deterministik slayt dökümüydü).
            for _attempt in range(2):
                stream = note_cleanup.SectionStream()
                try:
                    async for delta in llm_service.chat_stream(
                        [{"role": "user", "content": prompt}],
                        kind="note_generation",
                        max_tokens=SECTION_MAX_TOKENS,
                        reasoning_effort=NOTE_REASONING_EFFORT,
                        tenant_id=tenant_id,
                        course_id=course_id,
                        chapter_id=chapter_id,
                    ):
                        emitted = stream.feed(delta)
                        if emitted:
                            yield {"type": "delta", "text": emitted}
                    section = stream.cleaned()
                except llm_service.LLMError:
                    # Sağlayıcı zinciri tükendi — bu konu deterministik yedeğe düşer, üretim
                    # bütünüyle iptal EDİLMEZ (2026-09-05 kararı: her koşulda not teslim).
                    logger.warning(
                        "konu üretimi başarısız, deterministik yedeğe düşülüyor: %s",
                        topic["topic"],
                    )
                    section = ""
                    break
                if section:
                    break
                logger.warning("boş bölüm yanıtı, bir kez daha deneniyor: %s", topic["topic"])
            if section:
                sections.append(_strip_note_markers(section))
                continue

        if not chunks:
            # Kitapta kaynak yok → web → slayt yedeği → deterministik slayt (her koşulda not)
            result = await _safe_fallback_section(
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
            )
            if result is None:
                # Beklenmeyen hata (LLM dışı) — anında biten deterministik yedeğe düş,
                # üretim asla çökmesin (2026-09-06 kullanıcı geri bildirimi).
                section, deltas, status_message = (
                    _deterministic_slide_section(topic, slides),
                    [],
                    f"“{topic['topic']}” sunum içeriğinden yazılıyor…",
                )
            else:
                section, deltas, status_message = result
            yield {"type": "status", "percent": base + 3, "message": status_message}
            for delta in deltas:
                yield {"type": "delta", "text": delta}
            sections.append(section)
            continue

        # Kaynak bulundu ama LLM iki denemede de boş döndü: anında biten deterministik bölüm.
        yield {
            "type": "status",
            "percent": base + 3,
            "message": f"“{topic['topic']}” sunum içeriğinden yazılıyor…",
        }
        sections.append(_deterministic_slide_section(topic, slides))

    # Kayıt öncesi SON savunma: bölümler zaten normalize edilerek geldi, burada
    # birleşim düzeyinde de uygulanır (bölümler arası sızmış JSON/kod çiti kalmasın;
    # 2026-09-18 vaka: ham JSON zarfı `notes.content_md`ye yazılmıştı).
    content_md = note_cleanup.normalize_note_markdown("\n\n".join(s for s in sections if s))

    # 3.5) Genel ana başlık (kullanıcı isteği: MUTLAKA olmalı). Model note_title döndürmediyse
    # chapter başlığı düşer. H1 her zaman içeriğin EN ÜSTÜNE eklenir: düzgün üretilen not da
    # "### Konu" ile başladığı için "ilk satır başlık mı" koşulu H1'i fiilen hiç eklemiyordu
    # (2026-09-18 kullanıcı bildirimi: genel başlık eksik). (Yapışık/duplicate başlık onarımı
    # kayıt öncesinde yapılır — bkz. _repair_heading_structure; _dedupe_adjacent_headings
    # H1'i asla düşürmez.)
    content_md = f"# {general_title}\n\n{content_md}"

    # 4) Kapsama doğrulama + yeniden üretim (max 3 iterasyon) — bu bir kalite kontrolü,
    # başarısız olması (ör. yedek modelin geçerli JSON üretememesi) zaten üretilmiş notu
    # ÇÖPE ATMAMALI; "eksik konu yok" varsayılıp not olduğu gibi kaydedilir.
    yield {"type": "status", "percent": 86, "message": "Kapsama doğrulanıyor…"}
    missing: list[str] = []
    try:
        missing = await _check_coverage(topics, content_md, course_id, chapter_id, tenant_id)
    except llm_service.LLMError:
        logger.warning("kapsama doğrulaması başarısız oldu, atlanıyor: chapter=%s", chapter_id)
        missing = []
    for _ in range(MAX_COVERAGE_ITERATIONS):
        if not missing:
            break
        for topic in topics:
            if topic["topic"] not in missing:
                continue
            section = await _safe_regen_topic(
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
            )
            if section is None:
                continue
            # eski bölümü yenisiyle değiştir
            pattern = re.compile(
                rf"^#{{2,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
            )
            new_block = f"### {topic['topic']}\n\n{section}"
            content_md, replaced = _replace_section(content_md, pattern, new_block)
            if not replaced:
                content_md += f"\n\n{new_block}"
        try:
            missing = await _check_coverage(topics, content_md, course_id, chapter_id, tenant_id)
        except llm_service.LLMError:
            logger.warning("kapsama doğrulaması başarısız oldu, atlanıyor: chapter=%s", chapter_id)
            missing = []

    # 5) Başlık yapısı onarımı + son temizlik. Atıf doğrulama zinciri KALDIRILDI:
    # kullanıcıya atıf gösterilmez. Kalan adımlar yalnız başlık yapısını sağlamlaştırır ve
    # yasağa rağmen sızmış numara işaretlerini temizler. Kaynakça YAZILMAZ.
    yield {"type": "status", "percent": 93, "message": "Not düzenleniyor…"}
    content_md = _repair_heading_structure(content_md)
    content_md = _merge_repeated_memory_headings(content_md)
    content_md = _strip_note_markers(content_md)

    # 6) Kayıt. Kaynakça üretimi kaldırıldı; citations_json geriye uyumluluk için
    # boş atıf listeleriyle yazılır (quiz/flashcard üretimi ve coverage router'ı okur).
    yield {"type": "status", "percent": 98, "message": "Not kaydediliyor…"}
    citations_json = {
        "topics": [
            {"topic": topic["topic"], "citations": []}
            for topic in topics
        ]
    }
    topics_json = [
        {
            "topic": t["topic"],
            "keywords": t.get("keywords", []),
            "slide_refs": t.get("slide_refs", []),
        }
        for t in topics
    ]
    note_id = await _save_note(chapter_id, content_md, citations_json, topics_json, tenant_id)

    yield {
        "type": "done",
        "note": {
            "id": note_id,
            "chapter_id": chapter_id,
            "content_md": content_md,
            "citations_json": citations_json,
            "topics_json": topics_json,
            "model_used": llm_service.last_model_label(),
        },
    }


# Prompt'un (v4) yasağa rağmen ürettiği hafıza alt başlıkları — İÇERİK SIRASI adlarıdır,
# ekranda başlık OLMAMALI (kullanıcı isteği: "içerikler dursun ama başlık olmasın").
# Sadece tam satır başlığı kaldırılır; konu başlıkları korunur.
_MEMORY_SUBSECTION_NAMES = (
    "hatırlatıcı",
    "ne işe yarar",
    "ne işe yarar?",
    "kavramlar",
)


def _strip_memory_subsection_headings(content_md: str) -> str:
    """Konu BÖLÜMLERİ içindeki hafıza alt başlık satırlarını siler; içerik satırları durur.

    normalize ederek eşler ("### Hatırlatıcı", "**Hatırlatıcı**", "### Ne işe yarar?");
    `## Kaynakça` bölümü TARANMAZ (kaynakça satırları bu adlarla eşleşemez ama güvence).
    """
    lines = content_md.split("\n")
    out: list[str] = []
    in_bibliography = False
    for line in lines:
        if re.match(r"^##\s+Kaynakça\s*$", line):
            in_bibliography = True
            out.append(line)
            continue
        m = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if not in_bibliography and m:
            name = m.group(1).strip().lower()
            if name in _MEMORY_SUBSECTION_NAMES:
                continue  # başlık satırı atılır; altındaki içerik satırları aynen akar
        out.append(line)
    return "\n".join(out)


def _merge_repeated_memory_headings(content_md: str) -> str:
    """Aynı adlı hafıza alt başlıklarını TEK başlığa birleştirir (kayıp içeriği önler).

    Model, üç hafıza parçasını TEK bölümde yazması gerekirken ara sıra her hafıza parçası
    için AYRI "### Hatırlatıcı" başlığı açıp konu bölümünü KAPATIYOR. Bölüm yenileme +
    yapışık başlık onarımı bu başlıkları gerçek konu bölümlerine TAŞIR; aynı adlı başlıklar
    sonra birleştirilir (ikincisinin içeriği ilkinin altına akar). Yalnız tam eşleşen adlar;
    konu başlıklarına dokunmaz.
    """
    lines = content_md.split("\n")
    out: list[str] = []
    offsets: dict[str, int] = {}
    in_bibliography = False
    for line in lines:
        if re.match(r"^##\s+Kaynakça\s*$", line):
            in_bibliography = True
            out.append(line)
            continue
        m = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if in_bibliography or not m:
            out.append(line)
            continue
        name = m.group(1).strip().lower()
        if name in _MEMORY_SUBSECTION_NAMES:
            if name in offsets:
                out[offsets[name]] = ""  # ikinci başlık: konumu sil (içerik akar)
            else:
                offsets[name] = len(out)
            out.append(line)
            continue
        out.append(line)
    return "\n".join(out)


_GLUED_HEADING_RE = re.compile(r"(?<![\n#])(#{1,6}\s+\S)")


def _split_glued_headings(content_md: str) -> str:
    """Satır ortasında kalmış başlığı (`...metin.### Başlık`) yeni satıra alır.

    LLM ara sıra sonraki konunun başlığını önceki bölümün son satırına YAPIŞTIRIP
    yazıyor (2026-09-18 canlı koşu: `...birleştirir.### Kesitsel Araştırma Tasarımı`).
    Yapışık başlık `^#{1,4}` ile eşleşmediği için bölüm ayrışması ve atıf çipi
    eşlemesi bozuluyordu (kullanıcının "kaynakça eksik" bildiriminin kök nedeni).
    Belgenin İLK konumu atlanır: dosya başındaki meşru H1 (genel not başlığı) önüne
    boş satır almadan kalır.
    """

    def _sub(m: re.Match) -> str:
        return m.group(0) if m.start() == 0 else f"\n\n{m.group(1)}"

    return _GLUED_HEADING_RE.sub(_sub, content_md)


def _dedupe_adjacent_headings(content_md: str) -> str:
    """Arka arkaya gel duplicate başlıkları tekilleştirir (not 26/27 koşularında
    aynı konu başlığı iki kez peş peşe göründü). Normalize: küçük harf + noktalama temizliği.
    """
    lines = content_md.split("\n")
    out: list[str] = []

    def _norm(s: str) -> str:
        return re.sub(r"[^\w\s]", "", s).strip().lower()

    last_heading: str | None = None
    last_was_h1 = False
    dropped = False
    for line in lines:
        m = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if m:
            normalized = _norm(m.group(1))
            is_h1 = line.startswith("# ")
            if (
                last_heading is not None
                and normalized == last_heading
                and not (is_h1 and not last_was_h1)
            ):
                # komşu duplicate başlık — atla. H1 (genel not başlığı) ASLA düşürülmez;
                # ama H1'den sonra gelen AYNI adlı `###` başlığı düşer: note_title fallback
                # chapter başlığını H1'e yazınca "# A\n\n### A\n\n..." çifti oluşuyordu ve
                # modelin gerçek bölümü sahte bir başlığın altında kalmıştı (2026-09-19).
                dropped = True
                continue
            last_heading = normalized
            last_was_h1 = is_h1
        elif line.strip():
            last_heading = None
            last_was_h1 = False
        out.append(line)
    joined = "\n".join(out)
    if dropped:
        # Düşen başlığın ardında Artı boş satır kalmasın ("# A\n\n\nMetin" gibi).
        joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined


def _repair_heading_structure(content_md: str) -> str:
    """Başlık yapısını onarır: yapışık başlıkları böler, komşu duplicate'leri tekilleştirir."""
    return _dedupe_adjacent_headings(_split_glued_headings(content_md))


def _replace_section(
    content_md: str, pattern: re.Pattern, new_block: str
) -> tuple[str, bool]:
    """Başlık bazlı bölümü değiştirir; bulunamazsa (orijinal, False) döner.

    Değiştirilen aralık bir SONRAKİ başlığın `#` işaretine kadar gider; ayırıcı satır
    sonları bu aralığın içinde kaldığından yeni blok eskiden başlığa YAPIŞIYORDU
    (`... [2].### Oral Dönem`) ve o başlık markdown olarak render edilmiyordu
    (2026-09-18; kullanıcı notlarının 9'unda bu iz vardı). Ayırıcı burada yeniden konur.
    """
    match = pattern.search(content_md)
    if not match:
        return content_md, False
    start = match.start()
    end = match.end()
    next_heading = re.search(r"^#{1,4}\s+", content_md[end:], re.MULTILINE)
    if next_heading:
        end += next_heading.start()
    else:
        end = len(content_md)
    prefix = content_md[:start]
    if prefix and not prefix.endswith("\n\n"):
        prefix += _make_section_separator(prefix)
    suffix = content_md[end:]
    if suffix and not suffix.startswith("\n"):
        # Değiştirilen aralığın sonundaki satır sonları aralıkla birlikte silinmişti;
        # yeni blok sonraki başlığa yapışmasın (2026-09-18 düzeltmesi).
        suffix = "\n\n" + suffix
    return prefix + new_block + suffix, True


def _make_section_separator(content_md: str) -> str:
    """Bölümler arasına güvenli ayraç: bir önceki blok satır sonuyla bitmiyorsa
    boş satır ekle — başlık sonraki bölümün metnine YAPIŞMASIN (not 26 hatası:
    `...birleştirir.### Kesitsel ...` yapışıklığı çip kaybına yol açıyordu)."""
    return "" if content_md.endswith("\n\n") else ("\n" if content_md.endswith("\n") else "\n\n")


# _sync_bibliography kaldırıldı (2026-09-19): atıf/kaynakça yok, onarım adımları
# ana akışta (_repair_heading_structure + _merge_repeated_memory_headings +
# _strip_note_markers) çağrılıyor.
