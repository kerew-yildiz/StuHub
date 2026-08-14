"""Dönem arşivi — export/import (Yetenek 12 Format 4).

Arşiv: zip içinde manifest.json (sürüm 1) + courses/{id}/ altında ders/chapter
metadata'sı, not/quiz/flashcard/chat/guide JSON'ları ve opsiyonel materyal
dosyaları. Import yalnızca EKLEME yapar (mevcut veri asla silinmez), kimlikleri
yeniden eşler ve çakışan dönem adına " (içe aktarıldı)" ekini ekler.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ..config import settings
from ..db import get_db

logger = logging.getLogger(__name__)

ARCHIVE_VERSION = 1
TERM_SUFFIX = " (içe aktarıldı)"


class ArchiveError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(archive: zipfile.ZipFile, name: str) -> dict:
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ArchiveError(f"Arşiv dosyası bozuk: {name}") from exc


def _safe_filename(name: str | None, fallback: str) -> str:
    base = Path(name or fallback).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base)
    return cleaned or fallback


# Sabit SQL şablonları — dinamik SQL kurulumu YASAK (B608 politikası).
# id listesi tek parametre olarak JSON dizisiyle geçer (json_each).
_SELECT_BY_IDS: dict[tuple[str, str], str] = {
    ("chapters", "course_id"): (
        "SELECT * FROM chapters WHERE course_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("notes", "chapter_id"): (
        "SELECT * FROM notes WHERE chapter_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("quizzes", "chapter_id"): (
        "SELECT * FROM quizzes WHERE chapter_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("flashcard_sets", "course_id"): (
        "SELECT * FROM flashcard_sets "
        "WHERE course_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("chat_messages", "course_id"): (
        "SELECT * FROM chat_messages "
        "WHERE course_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("study_guides", "course_id"): (
        "SELECT * FROM study_guides "
        "WHERE course_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
    ("materials", "course_id"): (
        "SELECT * FROM materials "
        "WHERE course_id IN (SELECT value FROM json_each(?)) ORDER BY id"
    ),
}


async def _fetch_rows(table: str, where_col: str, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    query = _SELECT_BY_IDS.get((table, where_col))
    if query is None:
        raise ValueError(f"desteklenmeyen sorgu: {table}.{where_col}")
    db = await get_db()
    try:
        cursor = await db.execute(query, (json.dumps(ids),))
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
    return rows


async def build_term_archive(term_id: int, include_files: bool) -> bytes:
    """Dönemin tamamını arşiv zip'ine paketler (bayt döner)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, name FROM terms WHERE id = ?", (term_id,))
        term = await cursor.fetchone()
        if term is None:
            raise ArchiveError("Dönem bulunamadı")
        cursor = await db.execute(
            "SELECT id, name, instructor, metadata_json FROM courses "
            "WHERE term_id = ? ORDER BY id",
            (term_id,),
        )
        courses = [dict(row) for row in await cursor.fetchall()]
        course_ids = [c["id"] for c in courses]
    finally:
        await db.close()

    chapters = await _fetch_rows("chapters", "course_id", course_ids)
    chapters_by_course: dict[int, list[dict]] = {}
    for chapter in chapters:
        chapters_by_course.setdefault(chapter["course_id"], []).append(chapter)

    materials: dict[int, list[dict]] = {}
    if include_files:
        for row in await _fetch_rows("materials", "course_id", course_ids):
            materials.setdefault(row["course_id"], []).append(row)

    manifest = {
        "app": "stuhub",
        "version": ARCHIVE_VERSION,
        "generated_at": _now_iso(),
        "term": term["name"],
        "courses": course_ids,
        "materials_included": include_files,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for course in courses:
            prefix = f"courses/{course['id']}"
            archive.writestr(
                f"{prefix}/course.json", json.dumps(course, ensure_ascii=False)
            )
            archive.writestr(
                f"{prefix}/chapters.json",
                json.dumps(chapters_by_course.get(course["id"], []), ensure_ascii=False),
            )
            if include_files:
                for row in materials.get(course["id"], []):
                    archive.writestr(
                        f"{prefix}/materials/{row['id']}.json",
                        json.dumps(row, ensure_ascii=False),
                    )
                    path = Path(row["filepath"])
                    if path.exists() and path.is_file():
                        archive.write(path, f"{prefix}/materials/{row['id']}.bin")

        chapter_ids = [c["id"] for c in chapters]
        for row in await _fetch_rows("notes", "chapter_id", chapter_ids):
            prefix = f"chapters/{row['chapter_id']}"
            archive.writestr(
                f"{prefix}/note-{row['id']}.json", json.dumps(row, ensure_ascii=False)
            )
        for row in await _fetch_rows("quizzes", "chapter_id", chapter_ids):
            prefix = f"chapters/{row['chapter_id']}"
            archive.writestr(
                f"{prefix}/quiz-{row['id']}.json", json.dumps(row, ensure_ascii=False)
            )

        for row in await _fetch_rows("flashcard_sets", "course_id", course_ids):
            archive.writestr(
                f"courses/{row['course_id']}/flashcards/{row['id']}.json",
                json.dumps(row, ensure_ascii=False),
            )
        for row in await _fetch_rows("chat_messages", "course_id", course_ids):
            archive.writestr(
                f"courses/{row['course_id']}/chats/{row['id']}.json",
                json.dumps(row, ensure_ascii=False),
            )
        for row in await _fetch_rows("study_guides", "course_id", course_ids):
            archive.writestr(
                f"courses/{row['course_id']}/guides/{row['id']}.json",
                json.dumps(row, ensure_ascii=False),
            )
    return buffer.getvalue()


async def import_term_archive(data: bytes, include_files: bool) -> dict:
    """Arşivi yeni bir dönem olarak içe aktarır; kimlikleri yeniden eşler.

    Tüm metadata doğrulaması yazma öncesinde yapılır (atomik davranış).
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        bad_file = archive.testzip()
        if bad_file is not None:
            raise ArchiveError(f"Arşiv bozuk: {bad_file}")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchiveError("Arşiv dosyası açılamadı") from exc

    manifest = _read_json(archive, "manifest.json")
    if manifest.get("app") != "stuhub" or manifest.get("version") != ARCHIVE_VERSION:
        raise ArchiveError(
            "Arşiv sürümü desteklenmiyor — yalnızca StuHub arşiv sürümü 1 kabul edilir."
        )

    course_ids = manifest.get("courses")
    if not isinstance(course_ids, list) or not all(isinstance(i, int) for i in course_ids):
        raise ArchiveError("Arşiv ders listesi geçersiz")

    # ── Ön doğrulama: tüm ders/chapter metadata'sı belleğe alınır ──────────
    planned: list[dict] = []
    for old_course_id in course_ids:
        course = _read_json(archive, f"courses/{old_course_id}/course.json")
        chapters_json = _read_json(archive, f"courses/{old_course_id}/chapters.json")
        if not isinstance(chapters_json, list):
            raise ArchiveError("Arşiv chapter listesi geçersiz")
        chapters = [
            c
            for c in chapters_json
            if isinstance(c, dict) and isinstance(c.get("id"), int)
        ]
        planned.append({"course": course, "chapters": chapters})

    # ── Dönem kaydı (ad çakışmasında ek) ───────────────────────────────────
    db = await get_db()
    try:
        term_name = str(manifest.get("term") or "İçe aktarılan dönem")
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM terms WHERE name = ?", (term_name,)
        )
        row = await cursor.fetchone()
        if row is not None and row["c"] > 0:
            term_name = f"{term_name}{TERM_SUFFIX}"
        cursor = await db.execute("INSERT INTO terms (name) VALUES (?)", (term_name,))
        await db.commit()
        term_id = cursor.lastrowid
        if term_id is None:
            raise ArchiveError("Dönem kimliği alınamadı")
    finally:
        await db.close()

    chapter_map: dict[int, int] = {}
    material_count = 0
    summary_courses: list[dict] = []

    try:
        for item in planned:
            course = item["course"]
            db = await get_db()
            try:
                cursor = await db.execute(
                    "INSERT INTO courses (term_id, name, instructor, metadata_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        term_id,
                        course.get("name") or "Ders",
                        course.get("instructor"),
                        course.get("metadata_json") or "{}",
                    ),
                )
                await db.commit()
                new_course_id = cursor.lastrowid
                if new_course_id is None:
                    raise ArchiveError("Ders kimliği alınamadı")
            finally:
                await db.close()
            summary_courses.append(
                {
                    "old_id": course.get("id"),
                    "new_id": new_course_id,
                    "name": course.get("name"),
                }
            )

            for chapter in item["chapters"]:
                db = await get_db()
                try:
                    cursor = await db.execute(
                        "INSERT INTO chapters (course_id, title, created_at) "
                        "VALUES (?, ?, ?)",
                        (
                            new_course_id,
                            chapter.get("title") or f"Chapter {chapter['id']}",
                            chapter.get("created_at"),
                        ),
                    )
                    await db.commit()
                    new_chapter_id = cursor.lastrowid
                    if new_chapter_id is None:
                        raise ArchiveError("Chapter kimliği alınamadı")
                finally:
                    await db.close()
                chapter_map[chapter["id"]] = new_chapter_id
                await _import_rows(
                    archive,
                    prefix=f"chapters/{chapter['id']}",
                    old_chapter_id=chapter["id"],
                    new_chapter_id=new_chapter_id,
                )

            await _import_course_rows(archive, course.get("id"), new_course_id, chapter_map)

            if include_files and manifest.get("materials_included"):
                material_count += await _import_materials(
                    archive, course.get("id"), new_course_id
                )

        return {
            "term_id": term_id,
            "term_name": term_name,
            "courses": summary_courses,
            "materials_imported": material_count,
        }
    except ArchiveError:
        raise
    except Exception:
        logger.exception("arşiv import başarısız")
        raise ArchiveError("Arşiv içe aktarılamadı. Dosya bozuk olabilir.") from None


async def _import_rows(
    archive: zipfile.ZipFile,
    prefix: str,
    old_chapter_id: int,
    new_chapter_id: int,
) -> None:
    """Bir chapter'ın not + quiz kayıtlarını yeni kimlikle ekler."""
    for name in archive.namelist():
        if not name.startswith(f"{prefix}/") or not name.endswith(".json"):
            continue
        row = _read_json(archive, name)
        if name.endswith(f"note-{row.get('id')}.json"):
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO notes (chapter_id, content_md, citations_json,"
                    " topics_json, generated_at, model_used) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        new_chapter_id,
                        row.get("content_md", ""),
                        row.get("citations_json", "{}"),
                        row.get("topics_json", "[]"),
                        row.get("generated_at"),
                        row.get("model_used"),
                    ),
                )
                await db.commit()
            finally:
                await db.close()
        elif name.endswith(f"quiz-{row.get('id')}.json"):
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO quizzes (chapter_id, questions_json, created_at)"
                    " VALUES (?, ?, ?)",
                    (
                        new_chapter_id,
                        row.get("questions_json", "{}"),
                        row.get("created_at"),
                    ),
                )
                await db.commit()
            finally:
                await db.close()


async def _import_course_rows(
    archive: zipfile.ZipFile,
    old_course_id: int,
    new_course_id: int,
    chapter_map: dict[int, int],
) -> None:
    """Flashcard/chat/guide kayıtlarını yeni kurs kimliğiyle ekler."""
    for kind, _table in (
        ("flashcards", "flashcard_sets"),
        ("chats", "chat_messages"),
        ("guides", "study_guides"),
    ):
        prefix = f"courses/{old_course_id}/{kind}/"
        for name in archive.namelist():
            if not name.startswith(prefix) or not name.endswith(".json"):
                continue
            row = _read_json(archive, name)
            db = await get_db()
            try:
                if kind == "flashcards":
                    old_chapter = row.get("chapter_id")
                    mapped_chapter = (
                        chapter_map.get(old_chapter)
                        if isinstance(old_chapter, int)
                        else None
                    )
                    await db.execute(
                        "INSERT INTO flashcard_sets (course_id, chapter_id, cards_json,"
                        " created_at, model_used) VALUES (?, ?, ?, ?, ?)",
                        (
                            new_course_id,
                            mapped_chapter,
                            row.get("cards_json", "[]"),
                            row.get("created_at"),
                            row.get("model_used"),
                        ),
                    )
                elif kind == "chats":
                    await db.execute(
                        "INSERT INTO chat_messages (course_id, role, content,"
                        " citations_json, mode, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            new_course_id,
                            row.get("role", "user"),
                            row.get("content", ""),
                            row.get("citations_json", "[]"),
                            row.get("mode", "direct"),
                            row.get("created_at"),
                        ),
                    )
                else:
                    old_chapter = row.get("chapter_id")
                    mapped_chapter = (
                        chapter_map.get(old_chapter)
                        if isinstance(old_chapter, int)
                        else None
                    )
                    await db.execute(
                        "INSERT INTO study_guides (course_id, chapter_id, kind,"
                        " content_json, created_at, model_used) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            new_course_id,
                            mapped_chapter,
                            row.get("kind", "summary"),
                            row.get("content_json", "{}"),
                            row.get("created_at"),
                            row.get("model_used"),
                        ),
                    )
                await db.commit()
            finally:
                await db.close()


async def _import_materials(
    archive: zipfile.ZipFile,
    old_course_id: int,
    new_course_id: int,
) -> int:
    """Materyal kayıtlarını ve (varsa) dosyalarını yeni kursa taşır."""
    prefix = f"courses/{old_course_id}/materials/"
    imported = 0
    target_dir = settings.materials_dir / str(new_course_id)
    for name in archive.namelist():
        if not name.startswith(prefix) or not name.endswith(".json"):
            continue
        row = _read_json(archive, name)
        bin_name = f"{name[:-5]}.bin"
        stored_path = ""
        if bin_name in archive.namelist():
            target_dir.mkdir(parents=True, exist_ok=True)
            filename = _safe_filename(row.get("filepath"), f"material_{row.get('id')}.bin")
            target = target_dir / filename
            target.write_bytes(archive.read(bin_name))
            stored_path = str(target)
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO materials (course_id, type, filepath, extracted_text,"
                " page_count, vector_ns) VALUES (?, ?, ?, ?, ?, NULL)",
                (
                    new_course_id,
                    row.get("type", "textbook"),
                    stored_path,
                    row.get("extracted_text"),
                    row.get("page_count"),
                ),
            )
            await db.commit()
        finally:
            await db.close()
        imported += 1
    return imported
