"""Map-reduce not üretimi — konu çıkarımı, hibrit retrieval, kapsama, atıf doğrulama (Faz 3.1).

`generate_notes_stream(chapter_id)` bir async generator'dır; SSE olayları yield eder:
  {"type": "status", "percent": int, "message": str}
  {"type": "delta", "text": str}
  {"type": "done", "note": {...}}
  {"type": "error", "message": str}
"""

from __future__ import annotations

import json
import logging
import re

from ..config import settings
from ..db import get_db
from ..prompts.note_prompts import (
    CITATION_CONFIRM_PROMPT,
    COVERAGE_CHECK_PROMPT,
    NOTE_GENERATION_PROMPT,
    TOPIC_EXTRACTION_PROMPT,
)
from . import llm_service, retrieval

logger = logging.getLogger(__name__)

MAX_COVERAGE_ITERATIONS = 3
MAX_TOPICS = 12
QUOTE_WINDOW_CHARS = 240
SLIDES_CONTEXT_CHARS = 8000
NOTE_CONTEXT_CHARS = 6000


class NoteGenerationError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


# ── Metin yardımcıları ─────────────────────────────────────────────────

def _extract_citation_numbers(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"\[(\d+)\]", text)]


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


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
    """[n] işaretinden hemen önceki cümleyi alıntı adayı olarak döner."""
    marker = f"[{number}]"
    idx = text.find(marker)
    if idx == -1:
        return ""
    window = text[max(0, idx - QUOTE_WINDOW_CHARS) : idx]
    sentences = re.split(r"(?<=[.!?…])\s+", window)
    return sentences[-1].strip() if sentences else window.strip()


def _slide_content_for_topic(topic: dict, slides: list[dict]) -> str:
    refs = [int(r) for r in topic.get("slide_refs", []) if str(r).isdigit()]
    if refs:
        selected = [s for s in slides if s["slide_no"] in refs]
        if selected:
            return "\n\n".join(f"[Slide {s['slide_no']}] {s['content_text']}" for s in selected)
    return "\n\n".join(f"[Slide {s['slide_no']}] {s['content_text']}" for s in slides)


def _strip_own_heading(section: str, topic_name: str) -> str:
    """Bölüm metninin başındaki kendi başlığını kaldırır (yeniden üretim turlarında).

    `_replace_section` yeni bloğa başlığı kendisi ekler; LLM çıktısı başlıkla
    başlıyorsa kopya oluşurdu (bölüm ayrıştırmayı bozar).
    """
    pattern = re.compile(rf"^#{{1,4}}\s+{re.escape(topic_name)}\s*\n+", re.MULTILINE)
    return pattern.sub("", section, count=1).strip()


def _section_for_topic(content_md: str, topic_name: str) -> str:
    pattern = re.compile(rf"^#{{1,4}}\s+{re.escape(topic_name)}\s*$", re.MULTILINE)
    match = pattern.search(content_md)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^#{1,4}\s+", content_md[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content_md)
    return content_md[start:end].strip()


def _chunk_to_citation(number: int, chunk: dict) -> dict:
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

async def _extract_topics(slide_text: str, course_id: int, chapter_id: int) -> list[dict]:
    data = await llm_service.chat_json(
        [
            {
                "role": "user",
                "content": TOPIC_EXTRACTION_PROMPT.format(slides=slide_text[:SLIDES_CONTEXT_CHARS]),
            }
        ],
        kind="topic_extraction",
        course_id=course_id,
        chapter_id=chapter_id,
    )
    topics = data.get("topics", [])
    clean = [t for t in topics if isinstance(t, dict) and t.get("topic", "").strip()]
    return clean[:MAX_TOPICS]


async def _check_coverage(
    topics: list[dict], content_md: str, course_id: int, chapter_id: int
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
        course_id=course_id,
        chapter_id=chapter_id,
    )
    missing = data.get("missing", [])
    return [m for m in missing if isinstance(m, str) and m.strip()]


async def _llm_confirms_quote(
    quote: str, chunk_text: str, course_id: int, chapter_id: int
) -> bool:
    data = await llm_service.chat_json(
        [
            {
                "role": "user",
                "content": CITATION_CONFIRM_PROMPT.format(
                    quote=quote[:400], chunk_text=chunk_text[:1200]
                ),
            }
        ],
        kind="citation_confirm",
        course_id=course_id,
        chapter_id=chapter_id,
    )
    return bool(data.get("supported"))


# ── Üretim yardımcıları ────────────────────────────────────────────────

def _numbered_sources(chunks: list[dict]) -> str:
    return "\n".join(
        f"[{idx}] (sayfa {c['page'] or '-'} / slide {c['slide'] or '-'}) {c['text']}"
        for idx, c in enumerate(chunks, start=1)
    )


def _build_prompt(topic: dict, slides: list[dict], chunks: list[dict]) -> str:
    return NOTE_GENERATION_PROMPT.format(
        topic=topic["topic"],
        slide_content=_slide_content_for_topic(topic, slides),
        numbered_sources=_numbered_sources(chunks),
    )


def _section_citations(section: str, chunks: list[dict]) -> list[dict]:
    citations = []
    for n in _extract_citation_numbers(section):
        if 1 <= n <= len(chunks):
            citation = _chunk_to_citation(n, chunks[n - 1])
            citation["quote"] = _quote_before_citation(section, n)
            citations.append(citation)
    return citations


async def _regen_topic(
    topic: dict, slides: list[dict], course_id: int, chapter_id: int
) -> tuple[str | None, list[dict]]:
    """Kapsama/atıf düzeltme turu için konuyu yeniden üretir (stream'siz)."""
    chunks = retrieval.hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
    if not chunks:
        return None, []
    prompt = _build_prompt(topic, slides, chunks)
    parts: list[str] = []
    async for delta in llm_service.chat_stream(
        [{"role": "user", "content": prompt}],
        kind="note_regeneration",
        course_id=course_id,
        chapter_id=chapter_id,
    ):
        parts.append(delta)
    section = _strip_own_heading("".join(parts).strip(), topic["topic"])
    return section, _section_citations(section, chunks)


async def _validate_citations(
    content_md: str,
    topic_citations: dict[str, list[dict]],
    course_id: int,
    chapter_id: int,
) -> list[str]:
    """Her [n] atfını çözümler; çözümsüz kalan atıfların konularını döner."""
    problems: list[str] = []
    for topic_name, citations in topic_citations.items():
        section = _section_for_topic(content_md, topic_name)
        if not section:
            continue
        for citation in citations:
            quote = citation["quote"] or _quote_before_citation(section, citation["id"])
            if _fuzzy_match(quote, citation["chunk_text"]):
                continue
            supported = await _llm_confirms_quote(
                quote, citation["chunk_text"], course_id, chapter_id
            )
            if not supported:
                problems.append(topic_name)
                break
    return list(dict.fromkeys(problems))


async def _save_note(
    chapter_id: int, content_md: str, citations_json: dict, topics_json: list[dict]
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO notes (chapter_id, content_md, citations_json, topics_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                chapter_id,
                content_md,
                json.dumps(citations_json, ensure_ascii=False),
                json.dumps(topics_json, ensure_ascii=False),
                settings.model,
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

async def generate_notes_stream(chapter_id: int):
    """Not üretim hattı — SSE olayları yield eder (Faz 3.1)."""
    try:
        async for event in _generate(chapter_id):
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


async def _generate(chapter_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, course_id FROM chapters WHERE id = ?", (chapter_id,)
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise NoteGenerationError("Chapter bulunamadı")
        course_id = chapter["course_id"]
        cursor = await db.execute(
            "SELECT slide_no, content_text FROM slides WHERE chapter_id = ? ORDER BY slide_no ASC",
            (chapter_id,),
        )
        slides = [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()

    if not slides:
        raise NoteGenerationError(
            "Bu chapter'da henüz guide slides yok. Önce sunum yükleyin."
        )

    slide_text = "\n\n".join(f"[Slide {s['slide_no']}] {s['content_text']}" for s in slides)

    # 1) Konu çıkarımı
    yield {"type": "status", "percent": 6, "message": "Konular belirleniyor…"}
    topics = await _extract_topics(slide_text, course_id, chapter_id)
    if not topics:
        raise NoteGenerationError(
            "Sunumdan konu çıkarılamadı. Sunum içeriğini kontrol edip tekrar deneyin."
        )

    # 2+3) Konu bazlı map-reduce üretim (stream'li)
    sections: list[str] = []
    topic_citations: dict[str, list[dict]] = {}
    topic_chunks: dict[str, list[dict]] = {}

    for i, topic in enumerate(topics):
        base = 10 + int(72 * i / max(len(topics), 1))
        yield {
            "type": "status",
            "percent": base,
            "message": f"“{topic['topic']}” için kaynaklar taranıyor…",
        }
        chunks = retrieval.hybrid_search(course_id, topic["topic"], topic.get("keywords", []))
        if not chunks:
            topic_citations[topic["topic"]] = []
            topic_chunks[topic["topic"]] = []
            yield {
                "type": "status",
                "percent": base + 2,
                "message": f"“{topic['topic']}” için kaynak bulunamadı (uyarılı not).",
            }
            sections.append(
                f"### {topic['topic']}\n\n"
                "> ⚠️ Bu konu için ders kitabında kaynak bulunamadı; "
                "rehber içeriğe göre eksik not edildi."
            )
            continue

        yield {
            "type": "status",
            "percent": base + 3,
            "message": f"“{topic['topic']}” notu yazılıyor…",
        }
        prompt = _build_prompt(topic, slides, chunks)
        parts: list[str] = []
        async for delta in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            kind="note_generation",
            course_id=course_id,
            chapter_id=chapter_id,
        ):
            parts.append(delta)
            yield {"type": "delta", "text": delta}
        section = "".join(parts).strip()
        sections.append(section)
        topic_citations[topic["topic"]] = _section_citations(section, chunks)
        topic_chunks[topic["topic"]] = chunks

    content_md = "\n\n".join(s for s in sections if s)

    # 4) Kapsama doğrulama + yeniden üretim (max 3 iterasyon)
    yield {"type": "status", "percent": 86, "message": "Kapsama doğrulanıyor…"}
    missing = await _check_coverage(topics, content_md, course_id, chapter_id)
    for _ in range(MAX_COVERAGE_ITERATIONS):
        if not missing:
            break
        for topic in topics:
            if topic["topic"] not in missing:
                continue
            section, citations = await _regen_topic(topic, slides, course_id, chapter_id)
            if section is None:
                continue
            # eski bölümü yenisiyle değiştir
            replaced = False
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
        missing = await _check_coverage(topics, content_md, course_id, chapter_id)
    if missing:
        content_md += "\n\n> ⚠️ Eksik konular (kaynak bulunamadı): " + ", ".join(missing)

    # 5) Atıf doğrulama — çözümsüz atıf kabul edilmez (Yetenek 06)
    yield {"type": "status", "percent": 93, "message": "Atıflar doğrulanıyor…"}
    problems = await _validate_citations(
        content_md, topic_citations, course_id, chapter_id
    )
    if problems:
        for topic in topics:
            if topic["topic"] not in problems:
                continue
            section, citations = await _regen_topic(topic, slides, course_id, chapter_id)
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
        raise NoteGenerationError(
            "Atıf doğrulaması tamamlanamadı (çözümsüz atıflar). Lütfen üretimi tekrar deneyin."
        )

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
    note_id = await _save_note(chapter_id, content_md, citations_json, topics_json)

    yield {
        "type": "done",
        "note": {
            "id": note_id,
            "chapter_id": chapter_id,
            "content_md": content_md,
            "citations_json": citations_json,
            "topics_json": topics_json,
            "model_used": settings.model,
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
