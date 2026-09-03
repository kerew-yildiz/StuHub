"""İhracat router'ı — flashcard (Anki/CSV/MD) indirme + dönem arşivi export/import.

Not export'u (PDF/MD) `routers/notes.py`'dedir. Sözleşme: YETENEKLER/12.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from ..auth import get_tenant_id
from ..db import get_db
from ..services.anki_export import build_apkg, flashcards_to_csv, validate_apkg
from ..services.archive_service import (
    ArchiveError,
    build_term_archive,
    import_term_archive,
)
from ..services.export_service import flashcards_to_md

router = APIRouter(prefix="/api", tags=["exports"])

MD_MEDIA_TYPE = "text/markdown; charset=utf-8"


def _attachment(filename: str, media_type: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": media_type,
    }


def _cards_from_sets(sets: list[dict]) -> list[dict]:
    cards: list[dict] = []
    for card_set in sets:
        for card in json.loads(card_set["cards_json"] or "[]"):
            cards.append(card)
    return cards


async def _sets_for(
    course_id: int, set_id: int | None, tenant_id: str
) -> tuple[str, list[dict]]:
    db = await get_db()
    try:
        if set_id is not None:
            cursor = await db.execute(
                "SELECT fs.id, fs.course_id, fs.cards_json, c.name AS course_name "
                "FROM flashcard_sets fs JOIN courses c ON c.id = fs.course_id "
                "WHERE fs.id = ? AND fs.tenant_id = ?",
                (set_id, tenant_id),
            )
        else:
            cursor = await db.execute(
                "SELECT fs.id, fs.course_id, fs.cards_json, c.name AS course_name "
                "FROM flashcard_sets fs JOIN courses c ON c.id = fs.course_id "
                "WHERE fs.course_id = ? AND fs.tenant_id = ? ORDER BY fs.id",
                (course_id, tenant_id),
            )
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Flashcard seti bulunamadı")
    course_name = rows[0]["course_name"]
    sets = [
        {"id": row["id"], "course_id": row["course_id"], "cards_json": row["cards_json"]}
        for row in rows
    ]
    return course_name, sets


def _cards_response(deck_name: str, cards: list[dict], format: str, stem: str) -> Response:
    if not cards:
        raise HTTPException(
            status_code=422, detail="Bu sette kart yok — önce flashcard oluşturun."
        )
    if format == "apkg":
        data = build_apkg(deck_name, cards)
        validate_apkg(data, len(cards))
        return Response(
            data,
            media_type="application/octet-stream",
            headers=_attachment(f"{stem}.apkg", "application/octet-stream"),
        )
    if format == "csv":
        return Response(
            flashcards_to_csv(cards),
            media_type="text/csv; charset=utf-8",
            headers=_attachment(f"{stem}.csv", "text/csv; charset=utf-8"),
        )
    return Response(
        flashcards_to_md(cards).encode("utf-8"),
        media_type=MD_MEDIA_TYPE,
        headers=_attachment(f"{stem}.md", MD_MEDIA_TYPE),
    )


@router.get("/flashcard-sets/{set_id}/export")
async def export_flashcard_set(
    set_id: int, format: str = "apkg", tenant_id: str = Depends(get_tenant_id)
) -> Response:
    """Bir flashcard setini apkg/csv/md olarak indirir."""
    if format not in ("apkg", "csv", "md"):
        raise HTTPException(status_code=422, detail="format 'apkg', 'csv' veya 'md' olmalı")
    course_name, sets = await _sets_for(0, set_id, tenant_id)
    cards = _cards_from_sets(sets)
    return _cards_response(
        f"StuHub::{course_name}", cards, format, f"stuhub-kartlar-{set_id}"
    )


@router.get("/courses/{course_id}/flashcards/export")
async def export_course_flashcards(
    course_id: int, format: str = "apkg", tenant_id: str = Depends(get_tenant_id)
) -> Response:
    """Dersin TÜM flashcard'larını tek dosyada indirir."""
    if format not in ("apkg", "csv", "md"):
        raise HTTPException(status_code=422, detail="format 'apkg', 'csv' veya 'md' olmalı")
    course_name, sets = await _sets_for(course_id, None, tenant_id)
    cards = _cards_from_sets(sets)
    return _cards_response(
        f"StuHub::{course_name}", cards, format, f"stuhub-kartlar-{course_id}"
    )


@router.get("/terms/{term_id}/archive")
async def export_term_archive(
    term_id: int, include_files: bool = False, tenant_id: str = Depends(get_tenant_id)
) -> Response:
    """Dönemin tamamını arşiv zip'i olarak indirir (Yetenek 12 Format 4)."""
    try:
        data = await build_term_archive(term_id, include_files, tenant_id)
    except ArchiveError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        data,
        media_type="application/zip",
        headers=_attachment(f"stuhub-donem-{term_id}.zip", "application/zip"),
    )


@router.post("/archive/import")
async def import_archive(
    file: UploadFile,
    include_files: bool = False,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    """Arşiv zip'ini yeni bir dönem olarak içe aktarır (yalnızca ekleme yapar)."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Boş dosya yüklendi — arşiv zip olmalı.")
    try:
        return await import_term_archive(raw, include_files, tenant_id)
    except ArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
