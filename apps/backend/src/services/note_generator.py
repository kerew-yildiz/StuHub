"""Map-reduce not üretimi — konu çıkarımı, hibrit retrieval, kapsama, atıf doğrulama (Faz 3.1).

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
from . import llm_service, retrieval, web_search_service

logger = logging.getLogger(__name__)

MAX_COVERAGE_ITERATIONS = 3
# Ders için yüklenmiş syllabus/müfredat materyalinin prompt'a eklenecek azami karakter
# sayısı — dev bir PDF metni tüm topic/section promptlarını şişirmesin diye kırpılır.
KAZANIMLAR_MAX_CHARS = 4000
QUOTE_WINDOW_CHARS = 240
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

def _extract_citation_numbers(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"\[(\d+)\]", text)]


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def topic_matches(heading: str, topic: str) -> bool:
    """Başlık ↔ konu adı eşleşmesi (tam ya da anlamlı alt-metin).

    LLM başlığı konu adından sapabilir; kapsama/atıf eşlemesinde esneklik sağlar.
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


def _fuzzy_match(quote: str, chunk_text: str) -> bool:
    """Normalize fuzzy substring eşleşmesi (Yetenek 06 §2)."""
    q = _normalize(quote)
    t = _normalize(chunk_text)
    if not q or not t:
        return False
    if q in t:
        return True
    prefix = q[:60]
    return len(prefix) >= 20 and prefix in t


def _quote_before_citation(text: str, number: int) -> str:
    """[n] işaretinden hemen önceki cümleyi alıntı adayı olarak döner.

    Markdown başlık satırları (`### ...`) ve boş satırlar alıntıdan ayıklanır —
    tek cümlelik bölümlerde başlığın alıntıya karışıp fuzzy eşleşmeyi bozmasını
    önler (kullanıcı geri bildirimi).
    """
    marker = f"[{number}]"
    idx = text.find(marker)
    if idx == -1:
        return ""
    window = text[max(0, idx - QUOTE_WINDOW_CHARS) : idx]
    sentences = [s for s in re.split(r"(?<=[.!?…])\s+", window) if s.strip()]
    quote = sentences[-1].strip() if sentences else window.strip()
    lines = [
        line.strip()
        for line in quote.split("\n")
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return lines[-1] if lines else quote


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
    pattern = re.compile(rf"^#{{1,4}}\s+{re.escape(topic_name)}\s*\n+", re.MULTILINE)
    return pattern.sub("", section, count=1).strip()


def _section_for_topic(content_md: str, topic_name: str) -> str:
    pattern = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
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


def _chunk_to_citation(number: int, chunk: dict) -> dict:
    if chunk.get("url"):
        # Web kaynağı atfı: kaynak kimliği yok; url/title doğrudan atıfa taşınır.
        return {
            "id": number,
            "source_type": "web",
            "source_id": None,
            "page": None,
            "slide": None,
            "chunk_id": chunk["chunk_id"],
            "url": chunk.get("url"),
            "title": chunk.get("title"),
            "quote": "",
            "chunk_text": chunk["text"],
        }
    return {
        "id": number,
        "source_type": "textbook" if chunk["page"] is not None else "slides",
        "source_id": chunk["material_id"],
        "page": chunk["page"],
        "slide": chunk["slide"],
        "chunk_id": chunk["chunk_id"],
        "quote": "",
        "chunk_text": chunk["text"],
    }


# ── LLM adımları ───────────────────────────────────────────────────────

async def _extract_topics(
    slides: list[dict], course_id: int, chapter_id: int, tenant_id: str, kazanimlar: str
) -> list[dict]:
    async def _attempt() -> list[dict]:
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
        return [t for t in topics if isinstance(t, dict) and t.get("topic", "").strip()]

    clean = await _attempt()
    if not clean:
        # Ücretsiz LLM zinciri ara sıra boş/geçersiz JSON döndürüyor (bkz. generation_logs
        # id=51, 2026-09-05 — dolu slaytlarla bile gerçekleşti). Tek seferlik yeniden deneme,
        # kalıcı arıza yerine geçici sağlayıcı tekilliğini tolere eder.
        clean = await _attempt()
    return clean


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
        dil_talimati=dil_talimati(settings.not_dili),
        kazanimlar=kazanimlar_blok(kazanimlar),
    )


def _section_citations(section: str, chunks: list[dict]) -> list[dict]:
    citations = []
    for n in _extract_citation_numbers(section):
        if 1 <= n <= len(chunks):
            citation = _chunk_to_citation(n, chunks[n - 1])
            citation["quote"] = _quote_before_citation(section, n)
            citations.append(citation)
    return citations


def _ensure_topic_heading(section: str, topic_name: str) -> str:
    """Bölüm kendi `### {konu}` başlığıyla başlamıyorsa ekler."""
    text = section.strip()
    if re.match(rf"^#{{1,4}}\s+{re.escape(topic_name)}\s*$", text, re.MULTILINE):
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
) -> tuple[str, list[dict], list[str], str]:
    """Kitapta kaynak yokken (ya da atıf sorunu giderilirken) kaynak zinciri.

    allow_web=True → web → slayt → deterministik slayt; allow_web=False → yalnızca
    slayt → deterministik slayt (atıfsız, doğrulaması garantili temiz).
    Dönüş: (bölüm, atıflar, deltalar, durum mesajı). Bölüm asla boş dönmez.
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
                dil_talimati=dil_talimati(settings.not_dili),
                kazanimlar=kazanimlar_blok(kazanimlar),
            )
            try:
                parts: list[str] = []
                async for delta in llm_service.chat_stream(
                    [{"role": "user", "content": prompt}],
                    kind="note_generation_web",
                    max_tokens=SECTION_MAX_TOKENS,
                    reasoning_effort=NOTE_REASONING_EFFORT,
                    tenant_id=tenant_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                ):
                    parts.append(delta)
                    deltas.append(delta)
                section = "".join(parts).strip()
                if section:
                    return (
                        _ensure_topic_heading(section, name),
                        _section_citations(section, chunks),
                        deltas,
                        f"“{name}” için web kaynakları kullanılıyor…",
                    )
            except llm_service.LLMError:
                logger.warning("web not üretimi başarısız; slayt yedeğine düşülüyor: %s", name)

    # (b) Slayt (rehber) içeriğinden tam not
    prompt = NOTE_SLIDE_ONLY_PROMPT.format(
        topic=name,
        slide_content=_slide_content_for_topic(topic, slides),
        dil_talimati=dil_talimati(settings.not_dili),
        kazanimlar=kazanimlar_blok(kazanimlar),
    )
    try:
        parts = []
        async for delta in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            kind="note_generation_slide_only",
            max_tokens=SECTION_MAX_TOKENS,
            reasoning_effort=NOTE_REASONING_EFFORT,
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        ):
            parts.append(delta)
            deltas.append(delta)
        section = "".join(parts).strip()
        if section:
            return (
                _ensure_topic_heading(section, name),
                [],
                deltas,
                f"“{name}” sunum içeriğinden yazılıyor…",
            )
    except llm_service.LLMError:
        logger.warning("slayt not üretimi başarısız; deterministik bölüme düşülüyor: %s", name)

    # (c) Her iki yol da başarısız: slayt metninden deterministik bölüm (asla boş değil,
    # LLM gerektirmez — anında biter).
    return (
        _deterministic_slide_section(topic, slides),
        [],
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
) -> tuple[str | None, list[dict]]:
    """Kapsama/atıf düzeltme turu için konuyu yeniden üretir (stream'siz).

    Kitapta kaynak yoksa aynı zinciri izler (web → slayt yedeği); bölüm asla boş dönmez.
    Boş yanıt "bu turda değişiklik yok" sayılır (çağıran `None` görür).
    """
    chunks = await _safe_hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
    if not chunks:
        section, citations, _deltas, _msg = await _generate_fallback_section(
            topic, slides, course_id, chapter_id, course_name, tenant_id, kazanimlar
        )
        return _strip_own_heading(section, topic["topic"]), citations
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
        return None, []
    section = _strip_own_heading("".join(parts).strip(), topic["topic"])
    if not section:
        # Boş akış (reasoning sağlayıcısı yanıt bütçesini gizli reasoning'e harcayabiliyor)
        # "değişiklik yok" sayılır: çağıran taraflar boş bloğu MEVCUT bölümün üzerine
        # yazdığından, aksi halde iyi bir bölüm tamamen boşaltılabiliyordu (2026-09-17
        # canlı vaka: chapter 13 notunda "Uyarıcı-Uyarıcı İlişkilendirmesi" bölümü
        # başlıktan ibaret kalmıştı).
        logger.warning("boş yeniden üretim yanıtı, mevcut bölüm korunuyor: %s", topic["topic"])
        return None, []
    return section, _section_citations(section, chunks)


async def _safe_regen_topic(*args, **kwargs) -> tuple[str | None, list[dict]]:
    """`_regen_topic` sarmalayıcısı — beklenmeyen hatada (LLM dışı: retrieval/db/…)
    turu "değişiklik yok" sayar, tüm üretimi ÇÖKERTMEZ (2026-09-06 kullanıcı geri
    bildirimi: kapsama/atıf düzeltme turlarında üretim sessizce iptal oluyordu)."""
    try:
        return await _regen_topic(*args, **kwargs)
    except Exception:
        logger.warning("konu yeniden üretimi beklenmeyen hatayla başarısız", exc_info=True)
        return None, []


async def _safe_fallback_section(*args, **kwargs) -> tuple[str, list[dict], list[str], str] | None:
    """`_generate_fallback_section` sarmalayıcısı — beklenmeyen hatada `None` döner
    (çağıran taraf mevcut bölümü korur) — aynı gerekçeyle `_safe_regen_topic` gibi."""
    try:
        return await _generate_fallback_section(*args, **kwargs)
    except Exception:
        logger.warning("yedek bölüm üretimi beklenmeyen hatayla başarısız", exc_info=True)
        return None


async def _validate_citations(
    content_md: str,
    topic_citations: dict[str, list[dict]],
    course_id: int,
    chapter_id: int,
) -> list[str]:
    """Her [n] atfını DETERMİNİSTİK olarak çözümler; çözümsüz atıflı konuları döner.

    PERFORMANS NOTU (kullanıcı geri bildirimi): atıf başına LLM onay çağrısı
    (citation_confirm) kaldırıldı — yüzlerce küçük çağrı üretimi dakikalarca
    uzatıyordu. Doğrulama artık yalnız fuzzy eşleşmeyle yapılır; eşleşmeyen
    atıf "sorunlu konu" sayılır ve üst katmanın yedek zinciri devreye girer.
    """
    problems: list[str] = []
    for topic_name, citations in topic_citations.items():
        section = _section_for_topic(content_md, topic_name)
        if not section:
            continue
        for citation in citations:
            quote = citation["quote"] or _quote_before_citation(section, citation["id"])
            if _fuzzy_match(quote, citation["chunk_text"]):
                continue
            problems.append(topic_name)
            break
    return list(dict.fromkeys(problems))


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


def _strip_internal(citations: list[dict]) -> list[dict]:
    """chunk_text dahili doğrulama içindir; kayıtlı JSON'a girmez (Yetenek 06 şeması)."""
    return [{k: v for k, v in c.items() if k != "chunk_text"} for c in citations]


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
            "SELECT id, course_id FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise NoteGenerationError("Chapter bulunamadı")
        course_id = chapter["course_id"]
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

    # 1) Konu çıkarımı
    yield {"type": "status", "percent": 6, "message": "Konular belirleniyor…"}
    topics = await _extract_topics(slides, course_id, chapter_id, tenant_id, kazanimlar)
    if not topics:
        raise NoteGenerationError(
            "Sunumdan konu çıkarılamadı. Sunum içeriğini kontrol edip tekrar deneyin."
        )

    # 2+3) Konu bazlı map-reduce üretim (stream'li)
    sections: list[str] = []
    topic_citations: dict[str, list[dict]] = {}

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
                parts = []
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
                        parts.append(delta)
                        yield {"type": "delta", "text": delta}
                    section = "".join(parts).strip()
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
                sections.append(section)
                topic_citations[topic["topic"]] = _section_citations(section, chunks)
                continue

        if not chunks:
            # Kitapta kaynak yok → web → slayt yedeği → deterministik slayt (her koşulda not)
            result = await _safe_fallback_section(
                topic, slides, course_id, chapter_id, course_name, tenant_id, kazanimlar
            )
            if result is None:
                # Beklenmeyen hata (LLM dışı) — anında biten deterministik yedeğe düş,
                # üretim asla çökmesin (2026-09-06 kullanıcı geri bildirimi).
                section, citations, deltas, status_message = (
                    _deterministic_slide_section(topic, slides),
                    [],
                    [],
                    f"“{topic['topic']}” sunum içeriğinden yazılıyor…",
                )
            else:
                section, citations, deltas, status_message = result
            yield {"type": "status", "percent": base + 3, "message": status_message}
            for delta in deltas:
                yield {"type": "delta", "text": delta}
            sections.append(section)
            topic_citations[topic["topic"]] = citations
            continue

        # Kaynak bulundu ama LLM iki denemede de boş döndü: anında biten deterministik bölüm.
        yield {
            "type": "status",
            "percent": base + 3,
            "message": f"“{topic['topic']}” sunum içeriğinden yazılıyor…",
        }
        sections.append(_deterministic_slide_section(topic, slides))
        topic_citations[topic["topic"]] = []

    content_md = "\n\n".join(s for s in sections if s)

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
            section, citations = await _safe_regen_topic(
                topic, slides, course_id, chapter_id, course_name, tenant_id, kazanimlar
            )
            if section is None:
                continue
            # eski bölümü yenisiyle değiştir
            pattern = re.compile(
                rf"^#{{1,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
            )
            new_block = f"### {topic['topic']}\n\n{section}"
            content_md, replaced = _replace_section(content_md, pattern, new_block)
            if replaced:
                topic_citations[topic["topic"]] = citations
            else:
                content_md += f"\n\n{new_block}"
                topic_citations[topic["topic"]] = citations
        try:
            missing = await _check_coverage(topics, content_md, course_id, chapter_id, tenant_id)
        except llm_service.LLMError:
            logger.warning("kapsama doğrulaması başarısız oldu, atlanıyor: chapter=%s", chapter_id)
            missing = []

    # 5) Atıf doğrulama — çözümsüz atıf kabul edilmez (Yetenek 06)
    yield {"type": "status", "percent": 93, "message": "Atıflar doğrulanıyor…"}
    problems = await _validate_citations(
        content_md, topic_citations, course_id, chapter_id
    )
    if problems:
        for topic in topics:
            if topic["topic"] not in problems:
                continue
            section, citations = await _safe_regen_topic(
                topic, slides, course_id, chapter_id, course_name, tenant_id, kazanimlar
            )
            if section is None:
                continue
            new_block = f"### {topic['topic']}\n\n{section}"
            pattern = re.compile(
                rf"^#{{1,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
            )
            content_md, replaced = _replace_section(content_md, pattern, new_block)
            if replaced:
                topic_citations[topic["topic"]] = citations
        problems = await _validate_citations(
            content_md, topic_citations, course_id, chapter_id
        )
    if problems:
        # SON GÜVENCE 1: çözümsüz atıflı konuları yedek zincirle (web → slayt) yeniden üret —
        # not ASLA atıf hatasıyla bitmez (kullanıcı kararı: her koşulda not teslim edilir).
        yield {
            "type": "status",
            "percent": 95,
            "message": "Atıf sorunları gideriliyor…",
        }
        for topic in topics:
            if topic["topic"] not in problems:
                continue
            result = await _safe_fallback_section(
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
                allow_web=True,
            )
            if result is None:
                continue
            section, citations, _deltas, _msg = result
            new_block = f"### {topic['topic']}\n\n{_strip_own_heading(section, topic['topic'])}"
            pattern = re.compile(
                rf"^#{{1,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
            )
            content_md, replaced = _replace_section(content_md, pattern, new_block)
            if not replaced:
                content_md += f"\n\n{new_block}"
            topic_citations[topic["topic"]] = citations
        problems = await _validate_citations(
            content_md, topic_citations, course_id, chapter_id
        )
    if problems:
        # SON GÜVENCE 2: slayt temelli atıfsız bölüm — doğrulaması garantili temiz.
        for topic in topics:
            if topic["topic"] not in problems:
                continue
            result = await _safe_fallback_section(
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
                allow_web=False,
            )
            if result is None:
                continue
            section, citations, _deltas, _msg = result
            new_block = f"### {topic['topic']}\n\n{_strip_own_heading(section, topic['topic'])}"
            pattern = re.compile(
                rf"^#{{1,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
            )
            content_md, replaced = _replace_section(content_md, pattern, new_block)
            if not replaced:
                content_md += f"\n\n{new_block}"
            topic_citations[topic["topic"]] = citations
        problems = await _validate_citations(
            content_md, topic_citations, course_id, chapter_id
        )
    if problems:
        # SON ÇARE: bölümler korunur, çözümsüz konuların atıfları düşürülür (asla hata dönmez).
        # LLM gerektirmez, anında biter.
        logger.warning("çözümsüz atıf kalan konular (atıflar düşürüldü): %s", problems)
        for topic_name in problems:
            topic_citations[topic_name] = []

    # 6) Kayıt
    yield {"type": "status", "percent": 98, "message": "Not kaydediliyor…"}
    citations_json = {
        "topics": [
            {"topic": name, "citations": _strip_internal(cites)}
            for name, cites in topic_citations.items()
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


def _replace_section(content_md: str, pattern: re.Pattern, new_block: str) -> tuple[str, bool]:
    """Başlık bazlı bölümü değiştirir; bulunamazsa (orijinal, False) döner."""
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
    return content_md[:start] + new_block + content_md[end:], True
