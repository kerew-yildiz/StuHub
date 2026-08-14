"""Çalışma rehberi üretimi — özet + kavram haritası (Yetenek 13).

Not temellidir (retrieval YOK). Çıktılar `study_guides` tablosuna yazılır;
kavram haritası DAG olarak doğrulanır (çevrim reddedilir).
"""

from __future__ import annotations

import json
import logging

from ..config import settings
from ..db import get_db
from ..prompts.guide_prompts import (
    CONCEPT_MAP_PROMPT,
    COURSE_SUMMARY_PROMPT,
    SUMMARY_PROMPT,
    dil_talimati,
)
from . import llm_service

logger = logging.getLogger(__name__)

MAX_NOTE_CHARS = 12000
KINDS = ("summary", "concept_map")


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


async def _latest_note_md(chapter_id: int) -> tuple[int, str]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.id, c.course_id, n.content_md FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "WHERE n.chapter_id = ? ORDER BY n.id DESC LIMIT 1",
            (chapter_id,),
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
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO study_guides (course_id, chapter_id, kind, content_json, model_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                course_id,
                chapter_id,
                kind,
                json.dumps(content, ensure_ascii=False),
                settings.model,
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
) -> dict:
    """LLM çağrısı + doğrulama + kayıt; geçersiz çıktıda tek yeniden üretim."""
    for attempt in range(2):
        data = await llm_service.chat_json(
            [{"role": "user", "content": prompt}],
            kind="guide",
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
        return await _save_guide(course_id, chapter_id, kind, data)
    raise GuideError("Rehber üretilemedi. Lütfen tekrar deneyin.")


async def generate_chapter_guide(chapter_id: int, kind: str) -> dict:
    """Chapter seviyesi özet ya da kavram haritası üretir ve kaydeder."""
    if kind not in KINDS:
        raise GuideError("kind 'summary' veya 'concept_map' olmalı")
    course_id, content_md = await _latest_note_md(chapter_id)
    note_md = content_md[:MAX_NOTE_CHARS]
    if kind == "summary":
        prompt = SUMMARY_PROMPT.format(
            dil_talimati=dil_talimati(settings.not_dili), note_md=note_md
        )
        return await _produce(prompt, validate_summary, kind, course_id, chapter_id)
    prompt = CONCEPT_MAP_PROMPT.format(
        dil_talimati=dil_talimati(settings.not_dili), note_md=note_md
    )
    return await _produce(prompt, validate_concept_map, kind, course_id, chapter_id)


async def generate_course_guide(course_id: int, kind: str) -> dict:
    """Ders seviyesi özet ya da kavram haritası üretir ve kaydeder (Yetenek 13)."""
    if kind not in KINDS:
        raise GuideError("kind 'summary' veya 'concept_map' olmalı")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM chapters WHERE course_id = ?", (course_id,)
        )
        row = await cursor.fetchone()
        if row is None or row["c"] == 0:
            raise GuideError("Bu derste chapter yok — önce chapter oluşturun.")
    finally:
        await db.close()

    if kind == "concept_map":
        return await _course_concept_map(course_id)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.content_md, c.title FROM notes n "
            "JOIN chapters c ON c.id = n.chapter_id "
            "WHERE c.course_id = ? ORDER BY c.id",
            (course_id,),
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
    return await _produce(prompt, validate_summary, kind, course_id, None)


async def _course_concept_map(course_id: int) -> dict:
    """Ders kavram haritası: chapter haritalarının birleşimi (çevrim kontrolü ile)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT content_json FROM study_guides "
            "WHERE course_id = ? AND chapter_id IS NOT NULL AND kind = 'concept_map' "
            "ORDER BY id",
            (course_id,),
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
    return await _save_guide(course_id, None, "concept_map", merged)


async def get_latest_guide(
    course_id: int | None, chapter_id: int | None, kind: str
) -> dict | None:
    """Son rehberi döner (yoksa None)."""
    db = await get_db()
    try:
        if chapter_id is not None:
            cursor = await db.execute(
                "SELECT id, course_id, chapter_id, kind, content_json, created_at, model_used "
                "FROM study_guides WHERE chapter_id = ? AND kind = ? "
                "ORDER BY id DESC LIMIT 1",
                (chapter_id, kind),
            )
        else:
            cursor = await db.execute(
                "SELECT id, course_id, chapter_id, kind, content_json, created_at, model_used "
                "FROM study_guides WHERE course_id = ? AND chapter_id IS NULL AND kind = ? "
                "ORDER BY id DESC LIMIT 1",
                (course_id, kind),
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
