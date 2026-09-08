"""Kaynak kapsama router'ı — notun kitabın hangi sayfalarını kullandığı (Plan #31).

Tamamen deterministik: kapsama bilgisi not üretiminde kaydedilen atıf metadata'sından
(`notes.citations_json` → `{"topics": [{"topic": ..., "citations": [{page, source_id, ...}]}]}`,
`services/note_generator.py:_chunk_to_citation` / `:700`) ve `materials.page_count`
(indeksleme sonunda yazılır, `services/indexer.py:147`) okunur. LLM çağrısı YOK.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_tenant_id
from ..db import get_db

router = APIRouter(prefix="/api", tags=["coverage"])

# Sayfa numarası taşıyan tek materyal türü: 'textbook' (`indexer.EXTRACTORS` → "pages";
# slides 'slide', medya türleri 'segments' üretir, ikisinde de `page` boştur).
_PAGED_MATERIAL_TYPE = "textbook"


class MaterialCoverage(BaseModel):
    """Tek kitap/materyal için kapsama kırılımı."""

    material_id: int
    filename: str
    total_pages: int
    covered_pages: list[int]
    uncovered_ranges: list[list[int]]
    coverage_ratio: float


class CoverageOut(BaseModel):
    """Chapter kapsama özeti.

    Üst düzey alanlar tüm sayfalı materyallerin sayfa numarası birleşimidir
    (`total_pages` = en uzun materyalin sayfa sayısı); tek ders kitabı olan olağan
    durumda bu doğrudan o kitabın kapsamasıdır. Materyal bazlı kesin değerler
    `materials` listesindedir.
    """

    chapter_id: int
    note_id: int | None
    total_pages: int
    covered_pages: list[int]
    uncovered_ranges: list[list[int]]
    coverage_ratio: float
    materials: list[MaterialCoverage]
    # Notta atıf verilen ama bu derste artık var olmayan materyal id'leri — genelde
    # course_id yeniden kullanıldığında vector store'da miras kalan eski embedding'lerin
    # işareti (2026-09-08 kritik incelemede tespit edildi). Kök nedeni düzeltmez,
    # yalnızca sessizce %0'a düşen kapsamayı görünür/teşhis edilebilir kılar.
    orphaned_source_ids: list[int]


def _uncovered_ranges(covered: set[int], total_pages: int) -> list[list[int]]:
    """Kapsanmayan sayfaları bitişik kapalı aralıklara indirger: [[12, 18], [40, 41]]."""
    ranges: list[list[int]] = []
    start: int | None = None
    for page in range(1, total_pages + 1):
        if page in covered:
            if start is not None:
                ranges.append([start, page - 1])
                start = None
        elif start is None:
            start = page
    if start is not None:
        ranges.append([start, total_pages])
    return ranges


def _cited_pages(citations_json: str | None) -> dict[int, set[int]]:
    """Kayıtlı atıf JSON'undan {material_id: {sayfa, ...}} çıkarır.

    Slayt/web atıflarında `page` boştur, kendiliğinden dışarıda kalır. Bozuk JSON
    kapsamayı sıfırlar, hata fırlatmaz — gösterge kritik yol değil.
    """
    try:
        data = json.loads(citations_json or "{}")
    except (TypeError, ValueError):
        return {}
    pages: dict[int, set[int]] = {}
    topics = data.get("topics") if isinstance(data, dict) else None
    for topic in topics or []:
        if not isinstance(topic, dict):
            continue
        for citation in topic.get("citations") or []:
            if not isinstance(citation, dict):
                continue
            page, material_id = citation.get("page"), citation.get("source_id")
            if isinstance(page, bool) or isinstance(material_id, bool):
                continue
            if not isinstance(page, int) or not isinstance(material_id, int):
                continue
            pages.setdefault(material_id, set()).add(page)
    return pages


def _ratio(covered_count: int, total_pages: int) -> float:
    return round(covered_count / total_pages, 4) if total_pages else 0.0


@router.get("/chapters/{chapter_id}/coverage", response_model=CoverageOut)
async def get_chapter_coverage(
    chapter_id: int, tenant_id: str = Depends(get_tenant_id)
) -> CoverageOut:
    """Chapter'ın en güncel notunun kitap sayfalarını ne kadar kapsadığını döner.

    Not yoksa kapsama sıfırdır (hata değil): tüm sayfalar kapsanmayan sayılır.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT course_id FROM chapters WHERE id = ? AND tenant_id = ?",
            (chapter_id, tenant_id),
        )
        chapter = await cursor.fetchone()
        if chapter is None:
            raise HTTPException(status_code=404, detail="Chapter bulunamadı")

        cursor = await db.execute(
            "SELECT id, filepath, page_count FROM materials "
            "WHERE course_id = ? AND tenant_id = ? AND type = ? ORDER BY id",
            (chapter["course_id"], tenant_id, _PAGED_MATERIAL_TYPE),
        )
        material_rows = [dict(row) for row in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT id FROM materials WHERE course_id = ? AND tenant_id = ?",
            (chapter["course_id"], tenant_id),
        )
        known_material_ids = {row["id"] for row in await cursor.fetchall()}

        cursor = await db.execute(
            "SELECT id, citations_json FROM notes WHERE chapter_id = ? AND tenant_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (chapter_id, tenant_id),
        )
        note = await cursor.fetchone()
    finally:
        await db.close()

    note_id = note["id"] if note is not None else None
    cited = _cited_pages(note["citations_json"] if note is not None else None)
    orphaned_source_ids = sorted(set(cited) - known_material_ids)

    materials: list[MaterialCoverage] = []
    for row in material_rows:
        material_id = row["id"]
        pages = cited.get(material_id, set())
        # page_count indeksleme bitmeden boş kalır; o durumda atıf gören en yüksek
        # sayfa toplam kabul edilir ki oran anlamsız (sıfıra bölme) olmasın.
        total_pages = row["page_count"] or (max(pages) if pages else 0)
        covered = sorted(p for p in pages if 1 <= p <= total_pages)
        materials.append(
            MaterialCoverage(
                material_id=material_id,
                filename=Path(row["filepath"]).name,
                total_pages=total_pages,
                covered_pages=covered,
                uncovered_ranges=_uncovered_ranges(set(covered), total_pages),
                coverage_ratio=_ratio(len(covered), total_pages),
            )
        )

    total_pages = max((m.total_pages for m in materials), default=0)
    covered_union = sorted({p for m in materials for p in m.covered_pages})
    return CoverageOut(
        chapter_id=chapter_id,
        note_id=note_id,
        total_pages=total_pages,
        covered_pages=covered_union,
        uncovered_ranges=_uncovered_ranges(set(covered_union), total_pages),
        coverage_ratio=_ratio(len(covered_union), total_pages),
        materials=materials,
        orphaned_source_ids=orphaned_source_ids,
    )
