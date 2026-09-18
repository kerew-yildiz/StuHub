"""Tek seferlik veri onarımı — `notes.content_md` içindeki model JSON zarflarını temizler.

2026-09-18 vakası: not üretimi modelin JSON zarfını (`{"content": "### ..."}`) ham
olarak kaydetti; not ekranında ```json bloğu tüm notu tek kod bloğuna çevirdiği için
markdown işaretleri, `\\n` kaçışları ve atıflar ham göründü. Üretim hattı artık
`note_cleanup.normalize_note_markdown` ile temizliyor (bkz. `services/note_generator`);
bu script AYNI fonksiyonla geçmişte bozuk kaydedilmiş notları onarır.

Kullanım (repo kökünden ya da `apps/backend` içinden):

    apps/backend/.venv/bin/python apps/backend/scripts/repair_note_content.py --dry-run
    apps/backend/.venv/bin/python apps/backend/scripts/repair_note_content.py --apply

`DATABASE_URL` (SaaS/Postgres) tanımlıysa ona, değilse yerel SQLite'a bağlanır.
Onarım sonrası metin boşalacaksa (yalnızca şema dökümü dönen not) satır DEĞİŞTİRİLMEZ —
mevcut içerik korunur ve raporlanır. `--apply` öncesi değişecek satırların ham hâli
`data/not-onarim-yedek-<zaman>.json` dosyasına yazılır.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import settings  # noqa: E402
from src.db import get_db  # noqa: E402
from src.services.note_cleanup import normalize_note_markdown  # noqa: E402

PREVIEW_CHARS = 160


async def repair(*, apply: bool) -> int:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, content_md FROM notes ORDER BY id")
        rows = await cursor.fetchall()
        changed: list[tuple[int, str, str]] = []
        skipped: list[int] = []
        for row in rows:
            raw = row["content_md"] or ""
            clean = normalize_note_markdown(raw)
            if clean == raw.strip():
                continue
            if not clean.strip():
                skipped.append(row["id"])
                continue
            changed.append((row["id"], raw, clean))

        print(f"taranan not: {len(rows)} | onarılacak: {len(changed)} | atlanan: {len(skipped)}")
        if skipped:
            print(f"  atlananlar (boşalacağı için dokunulmadı): {skipped}")
        for note_id, raw, clean in changed:
            print(f"  #{note_id}: {len(raw)} → {len(clean)} karakter")
            print(f"    önce: {raw[:PREVIEW_CHARS]!r}")
            print(f"    sonra: {clean[:PREVIEW_CHARS]!r}")

        if not apply or not changed:
            print("kuru çalıştırma: yazılmadı" if not apply else "yazılacak satır yok")
            return 0

        backup = settings.data_dir / f"not-onarim-yedek-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(
            json.dumps(
                [{"id": note_id, "content_md": raw} for note_id, raw, _clean in changed],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"yedek: {backup}")
        for note_id, _raw, clean in changed:
            await db.execute("UPDATE notes SET content_md = ? WHERE id = ?", (clean, note_id))
        await db.commit()
        print(f"{len(changed)} not onarıldı")
        return 0
    finally:
        await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="değişiklikleri veritabanına yaz (varsayılan: kuru)"
    )
    parser.add_argument("--dry-run", action="store_true", help="yalnızca raporla (varsayılan)")
    args = parser.parse_args()
    return asyncio.run(repair(apply=args.apply and not args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
