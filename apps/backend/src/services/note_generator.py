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
from pathlib import Path

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

# Atıf işaretleri: materyal kaynaklı `[3]`, web kaynaklı `⟨3⟩` (U+27E8 / U+27E9).
# Model tek biçim (`[n]`) üretir; ayrımı `_resolve_citations` yapar. TARAYICI tek
# noktadır: numaralandırma, alıntı çıkarma ve doğrulama aynı desenden beslenir.
_MARKER_RE = re.compile(r"\[(\d+)\]|⟨(\d+)⟩")


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
    """`[n]` / `⟨n⟩` işaretinden hemen önceki cümleyi alıntı adayı olarak döner.

    Markdown başlık satırları (`### ...`) ve boş satırlar alıntıdan ayıklanır —
    tek cümlelik bölümlerde başlığın alıntıya karışıp fuzzy eşleşmeyi bozmasını
    önler (kullanıcı geri bildirimi).
    """
    idx = -1
    for marker in (f"[{number}]", f"⟨{number}⟩"):
        found = text.find(marker)
        if found != -1 and (idx == -1 or found < idx):
            idx = found
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


class _CitationRegistry:
    """Not üretimi boyunca `chunk_id → global atıf numarası` kaydı (1'den artan sayaç).

    Bölümler kendi kaynak listesine göre yerel `[1..n]` üretir (prompt böyle yazılmıştır);
    bölümler birleşince numaralar çakışıyordu. Kayıt, yerel numarayı global numaraya
    çevirir ve AYNI chunk'a her zaman AYNI numarayı verir (tekrar üretmez). Numara ataması
    üretim boyunca (yeniden üretim turları dahil) yaşadığı için numaralar kaymaz.
    """

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}
        self._citations: dict[int, dict] = {}

    def resolve(self, chunk: dict) -> dict:
        """Chunk'ın global atıf kaydını döner; ilk görülüşünde sıradaki numarayı atar."""
        number = self._ids.get(chunk["chunk_id"])
        if number is None:
            number = len(self._ids) + 1
            self._ids[chunk["chunk_id"]] = number
            self._citations[number] = _chunk_to_citation(number, chunk)
        return self._citations[number]

    def ordered(self) -> list[dict]:
        """Global numara sırasına göre tüm atıflar (kaynakça bu sırayı kullanır)."""
        return [self._citations[n] for n in sorted(self._citations)]


def _resolve_citations(
    section: str, chunks: list[dict], registry: _CitationRegistry
) -> tuple[str, list[dict]]:
    """Bölüm metnini global numaralara çevirir; (yeni metin, atıflar) döner.

    Yerel `[n]` → global numara; web kaynağı `⟨n⟩`, kitap/slayt `[n]` (görsel tip
    ayrımını backend yapar, model tek biçim üretir). Aynı chunk bölümde birden çok
    geçerse TEK atıf kaydı olur. Çözümsüz (aralık dışı) numaranın metni değiştirilmez.
    """
    quotes: dict[int, str] = {}
    used: dict[int, dict] = {}

    def _rewrite(match: re.Match[str]) -> str:
        local = int(match.group(1) or match.group(2))
        if not 1 <= local <= len(chunks):
            return match.group(0)
        citation = registry.resolve(chunks[local - 1])
        if local not in quotes:
            # Alıntı ÖZGÜN metinden çıkarılır — yeniden yazım sırasında işaret kaymasın.
            quotes[local] = _quote_before_citation(section, local)
        used[local] = citation
        number = citation["id"]
        return f"⟨{number}⟩" if citation["source_type"] == "web" else f"[{number}]"

    text = _MARKER_RE.sub(_rewrite, section)
    citations = [{**used[local], "quote": quotes[local]} for local in used]
    return text, citations


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
    *,
    registry: _CitationRegistry,
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
                section = stream.cleaned()
                if section:
                    section, citations = _resolve_citations(section, chunks, registry)
                    return (
                        _ensure_topic_heading(section, name),
                        citations,
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
        # Bu yol asla atıf listesi döndürmez ([] — aşağıda); model yine de yasağa
        # rağmen [n]/⟨n⟩ biçiminde bir işaret bırakırsa gövdede sahipsiz kalır ve
        # kaynakça senkronizasyonu (_sync_bibliography) onu YANLIŞLIKLA gerçek bir
        # atıfla eşleştirebilir (kayıttaki başka bir numarayla çakışarak). Kaynağı
        # olmayan bu yolda işaretler baştan temizlenir.
        section = _MARKER_RE.sub("", stream.cleaned())
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
    *,
    registry: _CitationRegistry,
) -> tuple[str | None, list[dict]]:
    """Kapsama/atıf düzeltme turu için konuyu yeniden üretir (stream'siz).

    Kitapta kaynak yoksa aynı zinciri izler (web → slayt yedeği); bölüm asla boş dönmez.
    Boş yanıt "bu turda değişiklik yok" sayılır (çağıran `None` görür).
    """
    chunks = await _safe_hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
    if not chunks:
        section, citations, _deltas, _msg = await _generate_fallback_section(
            topic,
            slides,
            course_id,
            chapter_id,
            course_name,
            tenant_id,
            kazanimlar,
            registry=registry,
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
        return None, []
    section, citations = _resolve_citations(section, chunks, registry)
    return section, citations


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


# ── Kaynakça (model değil, KOD üretir) ─────────────────────────────────

# Yüklenen dosyalar `{uuid4().hex}_{özgün ad}` olarak saklanır (bkz. routers/materials.py).
_UUID_PREFIX_RE = re.compile(r"^[0-9a-f]{32}_")


def _material_label(filepath: str) -> str:
    """Materyalin görünen adı (UUID öneki gizlenir)."""
    return _UUID_PREFIX_RE.sub("", Path(filepath).name)


async def _load_material_labels(course_id: int, tenant_id: str) -> dict[int, str]:
    """Kaynakça için {materyal_id: görünen ad}. Okunamazsa boş döner — kaynakça
    "Ders materyali" ile yazılır, not üretimi bu yüzden çökmez."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, filepath FROM materials WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        return {row["id"]: _material_label(row["filepath"]) for row in await cursor.fetchall()}
    except Exception:
        logger.warning("materyal adları okunamadı, kaynakça genel adla yazılıyor", exc_info=True)
        return {}
    finally:
        await db.close()


def _md_safe(text: str) -> str:
    """Markdown yapısını bozabilecek karakterleri temizler (tek satıra indirir)."""
    return re.sub(r"[\[\]<>|\n\r]+", " ", text).strip()


def _bibliography_block(
    registry: _CitationRegistry,
    topic_citations: dict[str, list[dict]],
    labels: dict[int, str],
) -> str:
    """Notun sonuna eklenen `## Kaynakça` bölümü (model yazmaz).

    Yalnız notta GERÇEKTEN kalan atıflar listelenir: yeniden üretimde düşen atıf
    kaynakçaya girmez. Sıra global numara sırasıdır. Atıf yoksa "" döner.
    """
    used = {c["id"] for cites in topic_citations.values() for c in cites}
    lines: list[str] = []
    for citation in registry.ordered():
        number = citation["id"]
        if number not in used:
            continue
        if citation["source_type"] == "web":
            title = _md_safe(citation.get("title") or "") or "Web kaynağı"
            url = (citation.get("url") or "").strip()
            marker = f"⟨{number}⟩"
            # URL otomatik bağlantı (`<url>`) — markdown bağlantı sözdizimini bozmaz
            # ve tıklanabilir kalır (URL içinde parantez olsa bile).
            body = f"{marker} {title} — <{url}>" if url and " " not in url else f"{marker} {title}"
            lines.append(f"- {body}")
            continue
        raw_source_id = citation.get("source_id")
        name = (
            _md_safe(labels.get(int(raw_source_id)) or "")
            if isinstance(raw_source_id, int)
            else ""
        ) or "Ders materyali"
        marker = f"[{number}]"
        if citation["source_type"] == "textbook" and citation.get("page") is not None:
            lines.append(f"- {marker} {name}, s. {citation['page']}")
        elif citation["source_type"] == "slides" and citation.get("slide") is not None:
            lines.append(f"- {marker} {name}, slayt {citation['slide']}")
        else:
            lines.append(f"- {marker} {name}")
    return "## Kaynakça\n\n" + "\n".join(lines) if lines else ""


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

    # 2+3) Konu bazlı map-reduce üretim (stream'li)
    sections: list[str] = []
    topic_citations: dict[str, list[dict]] = {}
    # Global atıf kaydı: bölümler kendi yerel [1..n] numaralarını üretir, birleştirmede
    # global numaraya çevrilir (numaralar bölümler arasında ÇAKIŞMAZ; bkz. _CitationRegistry).
    registry = _CitationRegistry()

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
                section, citations = _resolve_citations(section, chunks, registry)
                sections.append(section)
                topic_citations[topic["topic"]] = citations
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
                registry=registry,
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

    # Kayıt öncesi SON savunma: bölümler zaten normalize edilerek geldi, burada
    # birleşim düzeyinde de uygulanır (bölümler arası sızmış JSON/kod çiti kalmasın;
    # 2026-09-18 vaka: ham JSON zarfı `notes.content_md`ye yazılmıştı).
    content_md = note_cleanup.normalize_note_markdown("\n\n".join(s for s in sections if s))

    # 3.5) Genel ana başlık (kullanıcı isteği: MUTLAKA olmalı). Model note_title döndürmediyse
    # chapter başlığı düşer. H1 her zaman içeriğin EN ÜSTÜNE eklenir: düzgün üretilen not da
    # "### Konu" ile başladığı için "ilk satır başlık mı" koşulu H1'i fiilen hiç eklemiyordu
    # (2026-09-18 kullanıcı bildirimi: genel başlık eksik). (Yapışık/duplicate başlık onarımı
    # kaynakça senkronizasyonunda yapılır — bkz. _sync_bibliography; _dedupe_adjacent_headings
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
            section, citations = await _safe_regen_topic(
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
                registry=registry,
            )
            if section is None:
                continue
            # eski bölümü yenisiyle değiştir
            pattern = re.compile(
                rf"^#{{2,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
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
                topic,
                slides,
                course_id,
                chapter_id,
                course_name,
                tenant_id,
                kazanimlar,
                registry=registry,
            )
            if section is None:
                continue
            new_block = f"### {topic['topic']}\n\n{section}"
            pattern = re.compile(
                rf"^#{{2,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
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
                registry=registry,
            )
            if result is None:
                continue
            section, citations, _deltas, _msg = result
            new_block = f"### {topic['topic']}\n\n{_strip_own_heading(section, topic['topic'])}"
            pattern = re.compile(
                rf"^#{{2,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
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
                registry=registry,
            )
            if result is None:
                continue
            section, citations, _deltas, _msg = result
            new_block = f"### {topic['topic']}\n\n{_strip_own_heading(section, topic['topic'])}"
            pattern = re.compile(
                rf"^#{{2,4}}\s+{re.escape(topic['topic'])}\s*$", re.MULTILINE
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
        # LLM gerektirmez, anında biter. Düşen konunun gövdede kalmış sahipsiz çipleri
        # kayıt aşamasından önce _sync_bibliography tarafından da temizlenir.
        logger.warning("çözümsüz atıf kalan konular (atıflar düşürüldü): %s", problems)
        for topic_name in problems:
            topic_citations[topic_name] = []

    # 6) Kaynakça + kayıt. Kaynakça not içeriğinin PARÇASI olarak yazılır: PDF/dışa
    # aktarımda ve not görüntüleyicide aynen çıkar. Doğrulama turlarından SONRA eklenir
    # (kaynakça metni kapsama/atıf denetimine girmesin).
    # SENKRONİZASYON (kullanıcı isteği: "kaynakça tüm atıfları kapsamalı"): gövde
    # gerçeği (çipler) ile topic_citations kayıtları eşitlenir, başlık yapısı onarılır
    # (yapışık/duplicate başlık), kaynakça YALNIZ gövdede duran atıflarla yazılır.
    content_md, topic_citations = _sync_bibliography(
        content_md,
        registry,
        topic_citations,
        await _load_material_labels(course_id, tenant_id),
        atilmis_konular=set(problems or ()),
    )

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


# Prompt'un (v4) yasağa rağmen ürettiği hafıza alt başlıkları — İÇERİK SIRASI adlarıdır,
# ekranda başlık OLMAMALI (kullanıcı isteği: "içerikler dursun ama başlık olmasın").
# Sadece tam satır başlığı kaldırılır; konu başlıkları ve ## Kaynakça korunur.
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


def _sync_bibliography(
    content_md: str,
    registry: _CitationRegistry,
    topic_citations: dict[str, list[dict]],
    labels: dict[int, str],
    atilmis_konular: set[str] | None = None,
) -> tuple[str, dict[str, list[dict]]]:
    """Kaynakçayı gövdeyle SENKRONİZE eder (kullanıcı isteği: kaynakça tüm atıfları kapsamalı).

    Gövde, son kayıtlı topic_citations'a göre geride kalabilir: yedek zincirdeki
    `if not replaced: content_md += new_block` (atıf kaydı güncellenmez) ve regen
    turlarında bölümün iki kez yazılması bu uyuşmazlığın kaynaklarıdır. Bu yüzden
    kaynakça üretmeden ÖNCE:
    1. Başlık yapısı onarılır (yapışık başlık bölünür, komşu duplicate tekilleştirilir) —
       aksi halde çipler doğru bölüme eşlenemez.
    2. Her konunun çipleri GERÇEK gövdeden sayılır; topic_citations kayıtları buna
       göre budanır.
    3. Kaynakça YALNIZ gövdede gerçekten duran atıflarla yazılır — her çipin kaynağı
       mutlaka listede olur.
    Dönüş: (onarılmış content_md, güncellenmiş topic_citations).
    """
    atilmis_konular = set(atilmis_konular or ())
    content_md = _repair_heading_structure(content_md)
    content_md = _merge_repeated_memory_headings(content_md)

    def _nums(m: re.Match) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", m.group(0))]

    kalan_idler = {c["id"] for c in registry.ordered()}
    govde_numaralari: set[int] = set()
    for m in _MARKER_RE.finditer(content_md):
        govde_numaralari.update(n for n in _nums(m) if n in kalan_idler)

    # SON ÇARE'de AÇIKÇA atılan konu (atilmis_konular): gövdede kalmış sahipsiz çipler
    # TEMİZLENİR — bu çipler doğrulanmadı, kaynakçada da listelenemez. Sadece kayıt listesi
    # boş olan konuya dokunulmaz (boş kayıt meşrudur: konu gerçekten atıfsız yazılmıştır).
    for ad in atilmis_konular:
        bolum = _section_for_topic(content_md, ad)
        if not bolum:
            continue
        yeni_bolum = bolum
        for n in {x for m in _MARKER_RE.finditer(bolum) for x in _nums(m) if x in kalan_idler}:
            yeni_bolum = re.sub(
                rf"(?<!\d)({re.escape(f'[{n}]')}|{re.escape(f'⟨{n}⟩')})(?!\d)",
                "",
                yeni_bolum,
            )
        content_md = content_md.replace(bolum, yeni_bolum)
        govde_numaralari = {
            x
            for m in _MARKER_RE.finditer(content_md)
            for x in _nums(m)
            if x in kalan_idler
        }

    # Topic kayıtlarını gövde gerçeğiyle eşitle (kayıtta olup gövdede olmayan atıf düşer)
    guncel: dict[str, list[dict]] = {}
    for topic_name, cites in topic_citations.items():
        guncel[topic_name] = [c for c in cites if c["id"] in govde_numaralari]

    # Bölüm ayrıştırması değişmiş olabilir (duplicate birleşimi, yapışık başlık bölünmesi):
    # her konunun bölümündeki çipleri bulup kaydı o bölümün çipleriyle eşle. Kaydı HİÇ
    # kurulmamış konu (yedek zincirin `content_md += new_block` ekleme yolu — çip gövdede
    # ama kayıt yok) gövdesindeki çiplerden YENİDEN kurulur; aksi halde gövdede çipi duran
    # kaynak kaynakçada hiç yer alırdı (kullanıcı isteği: "kaynakça tüm atıfları kapsamalı").
    tum_atiflar = {c["id"]: dict(c) for c in registry.ordered()}
    for topic_name in list(guncel.keys()):
        bolum = _section_for_topic(content_md, topic_name)
        if not bolum:
            continue
        bolum_nums: set[int] = set()
        for m in _MARKER_RE.finditer(bolum):
            bolum_nums.update(_nums(m))
        mevcut = {c["id"]: c for c in guncel[topic_name]}
        if not mevcut and topic_name not in atilmis_konular:
            mevcut = tum_atiflar
        guncel[topic_name] = [mevcut[n] for n in sorted(bolum_nums) if n in mevcut]

    kaynakca = _bibliography_block(registry, guncel, labels)
    if kaynakca:
        govde = content_md.split("## Kaynakça")[0].rstrip()
        content_md = f"{govde}\n\n{kaynakca}"
    return content_md, guncel
