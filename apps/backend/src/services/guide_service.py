"""Çalışma rehberi üretimi — özet + kavram haritası + karşılaştırma + terim sözlüğü.

Not temellidir (retrieval YOK). Çıktılar `study_guides` tablosuna yazılır;
kavram haritası DAG olarak doğrulanır (çevrim reddedilir).

- Karşılaştırma tablosu (`kind='comparison'`, Plan #24): LLM ile üretilir.
- Terim sözlüğü (Plan #29): tamamen SQL + regex, LLM ÇAĞIRMAZ.
"""

from __future__ import annotations

import json
import logging
import re
from itertools import combinations

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..db import get_db
from ..prompts.guide_prompts import (
    COMPARISON_PROMPT,
    CONCEPT_MAP_PROMPT,
    COURSE_SUMMARY_PROMPT,
    SUMMARY_PROMPT,
    dil_talimati,
)
from . import llm_service

logger = logging.getLogger(__name__)

MAX_NOTE_CHARS = 12000
KINDS = ("summary", "concept_map")
COMPARISON_KIND = "comparison"
MAX_COMPARE_CONCEPTS = 6
COMPARISON_CONTEXT_CHARS = 6000
GLOSSARY_DEFINITION_CHARS = 400


class GuideError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def validate_concept_map(data: dict) -> list[str]:
    """Kavram haritası şemasını doğrular; ihlal listesi döner (boş = geçerli)."""
    errors: list[str] = []
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("düğüm listesi boş/geçersiz")
        return errors
    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or not str(node.get("id", "")).strip():
            errors.append("düğüm id'si eksik")
            continue
        if not str(node.get("label", "")).strip():
            errors.append(f"düğüm {node.get('id')} etiketi boş")
        ids.add(str(node["id"]))
    if not isinstance(edges, list):
        errors.append("kenar listesi geçersiz")
        return errors
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            errors.append("kenar geçersiz")
            continue
        src, dst = str(edge.get("from", "")), str(edge.get("to", ""))
        if src not in ids or dst not in ids:
            errors.append(f"kenar uçları düğümlerde yok: {src}→{dst}")
            continue
        adjacency.setdefault(src, set()).add(dst)
    if _has_cycle(adjacency, ids):
        errors.append("kavram haritası çevrim içeriyor (DAG olmalı)")
    return errors


def _has_cycle(adjacency: dict[str, set[str]], nodes: set[str]) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in nodes}

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in adjacency.get(node, set()):
            if color.get(nxt) == GRAY:
                return True
            if color.get(nxt) == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[n] == WHITE and visit(n) for n in nodes)


def validate_summary(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("summary_md"), str) or not data["summary_md"].strip():
        errors.append("summary_md boş")
    for field in ("key_terms", "exam_focus"):
        value = data.get(field)
        if not isinstance(value, list) or not value or not all(
            isinstance(v, str) and v.strip() for v in value
        ):
            errors.append(f"{field} boş/geçersiz")
    return errors


async def _latest_note_md(chapter_id: int, tenant_id: str) -> tuple[int, str]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.id, c.course_id, n.content_md FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "WHERE n.chapter_id = ? AND c.tenant_id = ? ORDER BY n.id DESC LIMIT 1",
            (chapter_id, tenant_id),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        raise GuideError("Önce not oluştur — rehber notun üzerinden üretilir.")
    return row["course_id"], row["content_md"]


async def _save_guide(
    course_id: int,
    chapter_id: int | None,
    kind: str,
    content: dict,
    tenant_id: str,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO study_guides "
            "(tenant_id, course_id, chapter_id, kind, content_json, model_used) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                course_id,
                chapter_id,
                kind,
                json.dumps(content, ensure_ascii=False),
                llm_service.last_model_label(),
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise GuideError("Rehber kimliği alınamadı")
    finally:
        await db.close()
    return {"id": row_id, "course_id": course_id, "chapter_id": chapter_id, "kind": kind}



async def _produce(
    prompt: str,
    validator,
    kind: str,
    course_id: int,
    chapter_id: int | None,
    tenant_id: str,
    log_kind: str = "guide",
) -> dict:
    """LLM çağrısı + doğrulama + kayıt; geçersiz çıktıda tek yeniden üretim."""
    for attempt in range(2):
        data = await llm_service.chat_json(
            [{"role": "user", "content": prompt}],
            kind=log_kind,
            tenant_id=tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
        )
        errors = validator(data)
        if errors:
            logger.warning("rehber doğrulama hatası (deneme %s): %s", attempt + 1, errors)
            if attempt == 1:
                raise GuideError(
                    "Rehber çıktısı geçersiz. Lütfen tekrar deneyin."
                )
            continue
        return await _save_guide(course_id, chapter_id, kind, data, tenant_id)
    raise GuideError("Rehber üretilemedi. Lütfen tekrar deneyin.")


async def generate_chapter_guide(
    chapter_id: int, kind: str, tenant_id: str = LOCAL_TENANT_ID
) -> dict:
    """Chapter seviyesi özet ya da kavram haritası üretir ve kaydeder."""
    if kind not in KINDS:
        raise GuideError("kind 'summary' veya 'concept_map' olmalı")
    course_id, content_md = await _latest_note_md(chapter_id, tenant_id)
    note_md = content_md[:MAX_NOTE_CHARS]
    if kind == "summary":
        prompt = SUMMARY_PROMPT.format(
            dil_talimati=dil_talimati(settings.not_dili), note_md=note_md
        )
        return await _produce(prompt, validate_summary, kind, course_id, chapter_id, tenant_id)
    prompt = CONCEPT_MAP_PROMPT.format(
        dil_talimati=dil_talimati(settings.not_dili), note_md=note_md
    )
    return await _produce(prompt, validate_concept_map, kind, course_id, chapter_id, tenant_id)


async def generate_course_guide(
    course_id: int, kind: str, tenant_id: str = LOCAL_TENANT_ID
) -> dict:
    """Ders seviyesi özet ya da kavram haritası üretir ve kaydeder (Yetenek 13)."""
    if kind not in KINDS:
        raise GuideError("kind 'summary' veya 'concept_map' olmalı")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM chapters WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        row = await cursor.fetchone()
        if row is None or row["c"] == 0:
            raise GuideError("Bu derste chapter yok — önce chapter oluşturun.")
    finally:
        await db.close()

    if kind == "concept_map":
        return await _course_concept_map(course_id, tenant_id)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.content_md, c.title FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "WHERE c.course_id = ? AND c.tenant_id = ? ORDER BY c.id",
            (course_id, tenant_id),
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()
    if not rows:
        raise GuideError("Önce chapter notları oluştur — ders rehberi notların birleşimidir.")

    notes_md = "\n\n".join(
        f"## {r['title']}\n{r['content_md'][:MAX_NOTE_CHARS // max(len(rows), 1)]}"
        for r in rows
    )
    prompt = COURSE_SUMMARY_PROMPT.format(
        dil_talimati=dil_talimati(settings.not_dili), notes_md=notes_md
    )
    return await _produce(prompt, validate_summary, kind, course_id, None, tenant_id)


async def _course_concept_map(course_id: int, tenant_id: str) -> dict:
    """Ders kavram haritası: chapter haritalarının birleşimi (çevrim kontrolü ile)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT content_json FROM study_guides "
            "WHERE course_id = ? AND tenant_id = ? AND chapter_id IS NOT NULL "
            "AND kind = 'concept_map' ORDER BY id",
            (course_id, tenant_id),
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()

    chapter_guides = [json.loads(r["content_json"]) for r in rows]
    if not chapter_guides:
        raise GuideError(
            "Önce chapter kavram haritaları oluştur — ders haritası onların birleşimidir."
        )

    nodes: list[dict] = []
    edges: list[dict] = []
    used_ids: set[str] = set()
    for index, guide in enumerate(chapter_guides):
        prefix = f"c{index + 1}_"
        for node in guide.get("nodes", []):
            node_id = f"{prefix}{node['id']}"
            if node_id in used_ids:
                continue
            used_ids.add(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "label": node["label"],
                    "importance": node.get("importance", 1),
                }
            )
        for edge in guide.get("edges", []):
            edges.append(
                {
                    "from": f"{prefix}{edge['from']}",
                    "to": f"{prefix}{edge['to']}",
                    "label": edge.get("label", ""),
                }
            )

    merged = {"nodes": nodes, "edges": edges}
    if validate_concept_map(merged):
        raise GuideError("Chapter haritaları çevrimli birleşim üretti — tekrar deneyin.")
    return await _save_guide(course_id, None, "concept_map", merged, tenant_id)


async def get_latest_guide(
    course_id: int | None,
    chapter_id: int | None,
    kind: str,
    tenant_id: str = LOCAL_TENANT_ID,
) -> dict | None:
    """Son rehberi döner (yoksa None)."""
    db = await get_db()
    try:
        if chapter_id is not None:
            cursor = await db.execute(
                "SELECT id, course_id, chapter_id, kind, content_json, created_at, model_used "
                "FROM study_guides WHERE chapter_id = ? AND kind = ? AND tenant_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (chapter_id, kind, tenant_id),
            )
        else:
            cursor = await db.execute(
                "SELECT id, course_id, chapter_id, kind, content_json, created_at, model_used "
                "FROM study_guides WHERE course_id = ? AND chapter_id IS NULL AND kind = ? "
                "AND tenant_id = ? ORDER BY id DESC LIMIT 1",
                (course_id, kind, tenant_id),
            )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "course_id": row["course_id"],
        "chapter_id": row["chapter_id"],
        "kind": row["kind"],
        "content_json": json.loads(row["content_json"]),
        "created_at": row["created_at"],
        "model_used": row["model_used"],
    }


# ── Karşılaştırma tablosu (Plan #24 — LLM kullanır) ─────────────────────


def validate_comparison(
    data: dict, expected_pairs: set[frozenset[str]] | None = None
) -> list[str]:
    """Karşılaştırma tablosu şemasını doğrular; ihlal listesi döner (boş = geçerli).

    `expected_pairs` verilirse çıktının tam olarak istenen kavram çiftlerini
    kapsaması beklenir (eksik/fazla ikili geçersizdir).
    """
    errors: list[str] = []
    concepts = data.get("concepts")
    if (
        not isinstance(concepts, list)
        or len(concepts) < 2
        or not all(isinstance(c, str) and c.strip() for c in concepts)
    ):
        errors.append("concepts en az 2 dolu metin olmalı")

    pairs = data.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        errors.append("pairs boş/geçersiz")
        return errors

    seen: set[frozenset[str]] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            errors.append("ikili geçersiz")
            continue
        first, second = str(pair.get("a", "")).strip(), str(pair.get("b", "")).strip()
        if not first or not second or first.casefold() == second.casefold():
            errors.append("ikili kavram adları eksik ya da aynı")
            continue
        seen.add(frozenset({first.casefold(), second.casefold()}))
        label = f"{first}–{second}"

        similarities = pair.get("similarities")
        if (
            not isinstance(similarities, list)
            or not similarities
            or not all(isinstance(s, str) and s.strip() for s in similarities)
        ):
            errors.append(f"{label}: benzerlikler boş/geçersiz")

        differences = pair.get("differences")
        if not isinstance(differences, list) or len(differences) < 2:
            errors.append(f"{label}: en az 2 fark gerekli")
        else:
            for diff in differences:
                if not isinstance(diff, dict) or not all(
                    isinstance(diff.get(key), str) and diff[key].strip()
                    for key in ("aspect", "a", "b")
                ):
                    errors.append(f"{label}: fark satırı eksik (aspect/a/b)")
                    break

        confusion = pair.get("confusion")
        if not isinstance(confusion, str) or not confusion.strip():
            errors.append(f"{label}: karıştırılan nokta boş")

    if expected_pairs is not None and seen != expected_pairs:
        errors.append("ikili listesi istenen kavram çiftleriyle örtüşmüyor")
    return errors


def _normalized_concepts(concepts: list[str]) -> list[str]:
    """Boşları atar, büyük/küçük harf duyarsız tekilleştirir, sırayı korur."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        term = concept.strip()
        if not term or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        cleaned.append(term)
    return cleaned


async def _course_summary_guides(
    course_id: int, tenant_id: str
) -> list[tuple[int | None, dict]]:
    """Dersin (chapter_id, özet içeriği) listesi — her hedef için en yeni kayıt."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT sg.chapter_id AS chapter_id, sg.content_json AS content_json "
            "FROM study_guides sg WHERE sg.course_id = ? AND sg.tenant_id = ? "
            "AND sg.kind = 'summary' AND sg.id = ("
            "  SELECT MAX(s2.id) FROM study_guides s2 "
            "  WHERE s2.course_id = sg.course_id AND s2.tenant_id = sg.tenant_id "
            "  AND s2.kind = 'summary' AND ("
            "    (s2.chapter_id IS NULL AND sg.chapter_id IS NULL)"
            "    OR s2.chapter_id = sg.chapter_id"
            "  )"
            ") ORDER BY sg.id",
            (course_id, tenant_id),
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()
    guides: list[tuple[int | None, dict]] = []
    for row in rows:
        try:
            content = json.loads(row["content_json"])
        except (TypeError, ValueError):
            logger.warning("bozuk özet içeriği atlandı (chapter %s)", row["chapter_id"])
            continue
        if isinstance(content, dict):
            guides.append((row["chapter_id"], content))
    return guides


def _comparison_context(guides: list[tuple[int | None, dict]]) -> str:
    """Karşılaştırma prompt'unun ders bağlamı: özet metinleri + anahtar terimler."""
    parts: list[str] = []
    for chapter_id, content in guides:
        label = "Ders geneli" if chapter_id is None else f"Bölüm {chapter_id}"
        terms = [t for t in content.get("key_terms", []) if isinstance(t, str) and t.strip()]
        summary_md = content.get("summary_md")
        block = [f"## {label}"]
        if terms:
            block.append("Anahtar terimler: " + ", ".join(terms))
        if isinstance(summary_md, str) and summary_md.strip():
            block.append(summary_md.strip())
        parts.append("\n".join(block))
    return "\n\n".join(parts)[:COMPARISON_CONTEXT_CHARS]


async def compare(
    course_id: int, concepts: list[str], tenant_id: str = LOCAL_TENANT_ID
) -> dict:
    """Seçilen kavramları ikili karşılaştırır ve `kind='comparison'` olarak kaydeder.

    LLM kullanır: bağlam dersin `study_guides` özetlerinden (anahtar terimler +
    özet metni) kurulur, çıktı `validate_comparison` ile doğrulanır.
    """
    cleaned = _normalized_concepts(concepts)
    if len(cleaned) < 2:
        raise GuideError("Karşılaştırma için en az 2 farklı kavram seçin.")
    if len(cleaned) > MAX_COMPARE_CONCEPTS:
        raise GuideError(
            f"En fazla {MAX_COMPARE_CONCEPTS} kavram karşılaştırılabilir — daha az kavram seçin."
        )

    guides = await _course_summary_guides(course_id, tenant_id)
    if not guides:
        raise GuideError(
            "Önce özet üret — karşılaştırma dersin anahtar terimleri üzerinden çalışır."
        )

    pairs = list(combinations(cleaned, 2))
    prompt = COMPARISON_PROMPT.format(
        dil_talimati=dil_talimati(settings.not_dili),
        concepts="\n".join(f"- {concept}" for concept in cleaned),
        pairs="\n".join(f"- {first} ↔ {second}" for first, second in pairs),
        context_md=_comparison_context(guides),
    )
    expected_pairs = {frozenset({a.casefold(), b.casefold()}) for a, b in pairs}

    def validator(data: dict) -> list[str]:
        return validate_comparison(data, expected_pairs)

    return await _produce(
        prompt,
        validator,
        COMPARISON_KIND,
        course_id,
        None,
        tenant_id,
        log_kind=COMPARISON_KIND,
    )


# ── Terim sözlüğü (Plan #29 — LLM YOK, SQL + regex) ─────────────────────


_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s*")
_EMPHASIS_RE = re.compile(r"[*`_]+")
_SENTENCE_BREAK_RE = re.compile(r"[.!?](?:\s|$)")


def _term_pattern(term: str) -> re.Pattern[str]:
    """Terimi kelime sınırlarıyla, büyük/küçük harf duyarsız arayan desen."""
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)


def _strip_markdown(text: str) -> str:
    cleaned = _EMPHASIS_RE.sub("", _BULLET_RE.sub("", text))
    return re.sub(r"\s+", " ", cleaned).strip()


def _heading_before(content_md: str, index: int) -> str | None:
    """İlk geçişin altında bulunduğu en yakın markdown başlığı (yoksa None)."""
    heading: str | None = None
    for match in _HEADING_RE.finditer(content_md):
        if match.start() >= index:
            break
        heading = match.group(2).strip()
    return heading


def _definition_at(content_md: str, match: re.Match[str]) -> str:
    """Terimin ilk geçtiği cümle — tanım olarak kullanılır (markdown temizlenir)."""
    line_start = content_md.rfind("\n", 0, match.start()) + 1
    line_end = content_md.find("\n", match.end())
    if line_end == -1:
        line_end = len(content_md)
    line = content_md[line_start:line_end]
    offset = match.start() - line_start

    begin = 0
    for break_match in _SENTENCE_BREAK_RE.finditer(line):
        if break_match.end() > offset:
            break
        begin = break_match.end()
    tail = _SENTENCE_BREAK_RE.search(line, max(offset, begin))
    end = tail.end() if tail else len(line)
    return _strip_markdown(line[begin:end])[:GLOSSARY_DEFINITION_CHARS]


async def _course_chapter_notes(
    course_id: int, tenant_id: str
) -> tuple[dict[int, str], list[tuple[int, int, str]]]:
    """(chapter başlıkları, [(chapter_id, note_id, content_md)]) — chapter sırasıyla."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, title FROM chapters WHERE course_id = ? AND tenant_id = ? ORDER BY id",
            (course_id, tenant_id),
        )
        titles = {row["id"]: row["title"] for row in await cursor.fetchall()}
        cursor = await db.execute(
            "SELECT c.id AS chapter_id, n.id AS note_id, n.content_md AS content_md "
            "FROM chapters c JOIN notes n ON n.chapter_id = c.id "
            "WHERE c.course_id = ? AND c.tenant_id = ? AND n.tenant_id = ? AND n.id = ("
            "  SELECT MAX(n2.id) FROM notes n2 "
            "  WHERE n2.chapter_id = c.id AND n2.tenant_id = n.tenant_id"
            ") ORDER BY c.id",
            (course_id, tenant_id, tenant_id),
        )
        notes = [
            (row["chapter_id"], row["note_id"], row["content_md"] or "")
            for row in await cursor.fetchall()
        ]
    finally:
        await db.close()
    return titles, notes


async def course_glossary(course_id: int, tenant_id: str = LOCAL_TENANT_ID) -> list[dict]:
    """Ders düzeyinde terim sözlüğü — chapter özetlerinin anahtar terimlerini birleştirir.

    LLM ÇAĞIRMAZ: terimler `study_guides.content_json.key_terms`'ten gelir; tanım,
    ilk geçiş konumu ve başlık notların markdown metninden deterministik regex ile
    çıkarılır. Alfabetik sıralı liste döner (rehber yoksa boş liste).
    """
    guides = await _course_summary_guides(course_id, tenant_id)
    if not guides:
        return []

    # Terim → terimi bildiren ilk rehberin chapter_id'si (ders geneli rehber için None).
    sources: dict[str, tuple[str, int | None]] = {}
    for chapter_id, content in guides:
        for term in content.get("key_terms", []):
            if not isinstance(term, str) or not term.strip():
                continue
            key = term.strip().casefold()
            if key not in sources:
                sources[key] = (term.strip(), chapter_id)
    if not sources:
        return []

    titles, notes = await _course_chapter_notes(course_id, tenant_id)

    entries: list[dict] = []
    for term, source_chapter_id in sources.values():
        pattern = _term_pattern(term)
        entry = {
            "term": term,
            "definition": "",
            "chapter_id": source_chapter_id,
            "chapter_title": (
                titles.get(source_chapter_id) if source_chapter_id is not None else None
            ),
            "note_id": None,
            "position": None,
            "heading": None,
        }
        for chapter_id, note_id, content_md in notes:
            match = pattern.search(content_md)
            if match is None:
                continue
            entry.update(
                {
                    "definition": _definition_at(content_md, match),
                    "chapter_id": chapter_id,
                    "chapter_title": titles.get(chapter_id),
                    "note_id": note_id,
                    "position": match.start(),
                    "heading": _heading_before(content_md, match.start()),
                }
            )
            break
        entries.append(entry)

    entries.sort(key=lambda item: item["term"].casefold())
    return entries
