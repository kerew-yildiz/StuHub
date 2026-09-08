"""Materyale Sor (RAG chat) servisi — retrieval + atıflı yanıt + SSE olayları (Faz V2.1).

`stream_chat_answer(course_id, user_message, mode, tenant_id)` bir async generator'dır;
şunları üretir:
  {"type": "citations", "citations": [...]}
  {"type": "delta", "text": str}
  {"type": "done", "message": {...assistant kaydı...}}
Atıf doğrulaması ikinci kez de başarısız olursa `llm_service.LLMError` fırlatır
(router bunu `{"type": "error"}` olayına çevirir).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime

from ..auth import LOCAL_TENANT_ID
from ..db import get_db
from ..prompts.chat_prompts import (
    DIRECT_SYSTEM_PROMPT,
    QUIZ_SYSTEM_PROMPT,
    SOCRATIC_SYSTEM_PROMPT,
)
from . import llm_service, retrieval

MAX_SOURCE_CHARS = 6000
HISTORY_MESSAGES = 6
QUOTE_CHARS = 240

NO_SOURCES_MESSAGE = (
    "Bu dersin indekslenmiş kaynaklarında bu soruya yanıt bulunamadı. "
    "Önce materyalleri indeksleyin ya da soruyu yeniden ifade edin."
)

_SYSTEM_PROMPTS = {
    "direct": DIRECT_SYSTEM_PROMPT,
    "socratic": SOCRATIC_SYSTEM_PROMPT,
    "quiz": QUIZ_SYSTEM_PROMPT,
}


def _source_type(chunk: dict) -> str:
    if chunk.get("page") is not None:
        return "textbook"
    if chunk.get("slide") is not None:
        return "slides"
    return "other"


def _source_label(source_type: str, page: int | None, slide: int | None, n: int) -> str:
    if source_type == "textbook":
        return f"Kitap s.{page}"
    if source_type == "slides":
        return f"Sunum slayt {slide}"
    return f"Kaynak {n}"


def _build_sources(chunks: list[dict]) -> list[dict]:
    """Retrieval chunk'larını numaralı kaynak listesine çevirir (~6000 karakter bütçe)."""
    sources: list[dict] = []
    total = 0
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        if total + len(text) > MAX_SOURCE_CHARS:
            if sources:
                break  # kalan kaynaklar en düşük skorlular — bütçe aşımında atılır
            text = text[:MAX_SOURCE_CHARS]
        n = len(sources) + 1
        stype = _source_type(chunk)
        sources.append(
            {
                "n": n,
                "chunk_id": chunk["chunk_id"],
                "material_id": chunk["material_id"],
                "text": text,
                "page": chunk.get("page"),
                "slide": chunk.get("slide"),
                "source_type": stype,
                "source_label": _source_label(
                    stype, chunk.get("page"), chunk.get("slide"), n
                ),
            }
        )
        total += len(text)
    return sources


def _format_sources(sources: list[dict]) -> str:
    return "\n\n".join(f"[{s['n']}] ({s['source_label']}) {s['text']}" for s in sources)


def _citation_payload(source: dict) -> dict:
    return {
        "id": source["n"],
        "source_type": source["source_type"],
        "source_id": source["material_id"],
        "page": source["page"],
        "slide": source["slide"],
        "chunk_id": source["chunk_id"],
        "source_label": source["source_label"],
        "quote": source["text"][:QUOTE_CHARS],
    }


def _citation_numbers(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"\[(\d+)\]", text)]


def _citations_valid(text: str, n_sources: int) -> bool:
    numbers = _citation_numbers(text)
    return bool(numbers) and all(1 <= n <= n_sources for n in numbers)


def _build_messages(
    mode: str, sources: list[dict], history: list[dict], user_message: str
) -> list[dict]:
    system = _SYSTEM_PROMPTS[mode].format(sources=_format_sources(sources))
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


async def _load_history(course_id: int, tenant_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT role, content FROM chat_messages WHERE course_id = ? AND tenant_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (course_id, tenant_id, HISTORY_MESSAGES),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()
    history = [{"role": r["role"], "content": r["content"]} for r in rows]
    history.reverse()
    return history


def _row_to_message(row: dict) -> dict:
    data = dict(row)
    data["citations_json"] = json.loads(data["citations_json"] or "[]")
    return data


async def _save_message(
    course_id: int, role: str, content: str, citations: list[dict], mode: str, tenant_id: str
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO chat_messages (tenant_id, course_id, role, content, citations_json, mode) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                course_id,
                role,
                content,
                json.dumps(citations, ensure_ascii=False),
                mode,
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("mesaj kimliği alınamadı")
        cursor = await db.execute(
            "SELECT id, role, content, citations_json, mode, created_at "
            "FROM chat_messages WHERE id = ? AND tenant_id = ?",
            (row_id, tenant_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("kaydedilen mesaj bulunamadı")
    finally:
        await db.close()
    return _row_to_message(dict(row))


async def _log_activity(course_id: int, tenant_id: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO activity_log (tenant_id, date, kind, count, course_id) "
            "VALUES (?, ?, 'chat', 1, ?) "
            "ON CONFLICT(tenant_id, date, kind, COALESCE(course_id, 0)) "
            "DO UPDATE SET count = count + 1",
            (tenant_id, datetime.now().date().isoformat(), course_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _stream_answer(messages: list[dict], course_id: int, tenant_id: str):
    """LLM deltalarını `delta` olayları olarak akıtır."""
    async for delta in llm_service.chat_stream(
        messages, kind="chat", course_id=course_id, tenant_id=tenant_id
    ):
        yield {"type": "delta", "text": delta}


async def stream_chat_answer(
    course_id: int, user_message: str, mode: str, tenant_id: str = LOCAL_TENANT_ID
):
    """Kullanıcı sorusuna atıflı yanıt üretir; SSE olayları yield eder (Faz V2.1)."""
    history = await _load_history(course_id, tenant_id)
    await _save_message(course_id, "user", user_message, [], mode, tenant_id)

    # Senkron ve ağır (bge-m3 inference + LanceDB okuması) — doğrudan çağrılırsa
    # event loop'u ve dolayısıyla diğer tüm istekleri bloklar.
    chunks = await asyncio.to_thread(retrieval.hybrid_search, course_id, user_message)
    if not chunks:
        yield {"type": "citations", "citations": []}
        yield {"type": "delta", "text": NO_SOURCES_MESSAGE}
        assistant = await _save_message(
            course_id, "assistant", NO_SOURCES_MESSAGE, [], mode, tenant_id
        )
        await _log_activity(course_id, tenant_id)
        yield {"type": "done", "message": assistant}
        return

    sources = _build_sources(chunks)
    citations = [_citation_payload(s) for s in sources]
    yield {"type": "citations", "citations": citations}

    messages = _build_messages(mode, sources, history, user_message)
    text = ""
    async for event in _stream_answer(messages, course_id, tenant_id):
        yield event
        text += event["text"]
    text = text.strip()

    if not _citations_valid(text, len(sources)):
        # İstemci bu olayda biriken metni SIFIRLAR (ilk deneme yanıtı iptal).
        yield {
            "type": "retry",
            "message": "Atıf doğrulaması başarısız — yanıt yeniden üretiliyor…",
        }
        corrective = (
            "Önceki yanıtın atıfları geçersizdi. Yalnızca verilen kaynak numaralarını "
            f"kullan (1-{len(sources)}); listede olmayan numara kullanma ve her "
            "iddianı [n] biçiminde atıfla."
        )
        messages = [*messages, {"role": "user", "content": corrective}]
        text = ""
        async for event in _stream_answer(messages, course_id, tenant_id):
            yield event
            text += event["text"]
        text = text.strip()
        if not _citations_valid(text, len(sources)):
            raise llm_service.LLMError(
                "Yanıt atıf doğrulamasından geçemedi. Lütfen tekrar deneyin."
            )

    used = sorted({n for n in _citation_numbers(text) if 1 <= n <= len(sources)})
    citations_json = [citations[n - 1] for n in used]
    assistant = await _save_message(course_id, "assistant", text, citations_json, mode, tenant_id)
    await _log_activity(course_id, tenant_id)
    yield {"type": "done", "message": assistant}
