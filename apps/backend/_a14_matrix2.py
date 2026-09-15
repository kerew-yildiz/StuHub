"""Alan-14 tanı matrisi #2: iş hatası (indexing_jobs.error) sızıntısı + yarıda kesilen yükleme."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("STUHUB_DATA_DIR", tempfile.mkdtemp(prefix="a14b_"))
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

from src.config import settings  # noqa: E402
from src.db import get_db, init_db  # noqa: E402
from src.main import app  # noqa: E402

settings.database_url = ""
settings.data_dir = Path(os.environ["STUHUB_DATA_DIR"])

LEAK_PATTERNS = [
    (r"Traceback \(most recent call last\)", "python traceback"),
    (r'File "[^"]+", line \d+', "kaynak dosya:satır"),
    (r"[A-Za-z]:[\\/]{1,2}Users", "windows mutlak yol"),
    (r"/(?:home|mnt|tmp|var|data)/[\w./-]+", "unix mutlak yol"),
    (r"site-packages", "site-packages"),
    (r"\b(?:pymupdf|fitz|mupdf|zipfile|BadZipFile|asyncpg|aiosqlite|lxml|PIL|docx|pptx|ebooklib)\b", "iç kütüphane adı"),
    (r"\bErrno \d+", "errno"),
]


def scan(text: str) -> list[str]:
    return [lbl for pat, lbl in LEAK_PATTERNS if re.search(pat, text or "", re.IGNORECASE)]


# (uzantı, materyal türü) — hepsi ALLOWED_EXTENSIONS'ta geçerli, içerik çöp
CASES = [
    ("bozuk.pptx", "slides"),
    ("bozuk.docx", "docx"),
    ("bozuk.epub", "epub"),
    ("bozuk.png", "image"),
    ("bozuk-syllabus.pdf", "syllabus"),
    ("bozuk.mp3", "audio"),
]


async def jobs_for(course: int) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, material_id, kind, status, error FROM indexing_jobs WHERE course_id = ? "
            "ORDER BY id",
            (course,),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def main() -> None:
    await init_db()
    transport = httpx.ASGITransport(app=app)
    out = []
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=600) as c:
        term = (await c.post("/api/terms", json={"name": "[TEST] Alan14b"})).json()["id"]
        course = (await c.post(f"/api/terms/{term}/courses", json={"name": "[TEST] Alan14b"})).json()["id"]

        for fname, mtype in CASES:
            r = await c.post(
                f"/api/courses/{course}/materials",
                files={"file": (fname, os.urandom(4096), "application/octet-stream")},
                data={"type": mtype},
            )
            print(f"{fname:<22} type={mtype:<9} HTTP {r.status_code}")

        await asyncio.sleep(2)
        js = await jobs_for(course)
        print("\n--- indexing_jobs.error (kullanıcıya GET /api/indexing-jobs/{id} ile görünür) ---")
        for j in js:
            leaks = scan(j["error"])
            flag = f"  <<< SIZINTI {leaks}" if leaks else ""
            print(f"job {j['id']} mat={j['material_id']} kind={j['kind']} status={j['status']}")
            print(f"   error: {(j['error'] or '')[:400]}{flag}")
            out.append({**j, "sizinti": leaks})

        # --- K7 yarıda kesilen yükleme: multipart gövdesinin ortasında bağlantı kopar
        print("\n--- K7 yarıda kesilen yükleme ---")
        boundary = "----a14boundary"
        head = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="type"\r\n\r\ntextbook\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="yarim.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()

        async def kesik_govde():
            yield head
            yield b"%PDF-1.4\n" + b"K" * (2 * 1024 * 1024)
            await asyncio.sleep(0.2)
            raise ConnectionError("istemci bağlantıyı kesti (simülasyon)")

        try:
            await c.post(
                f"/api/courses/{course}/materials",
                content=kesik_govde(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            print("  beklenmedik: istek tamamlandı")
        except Exception as exc:
            print(f"  istemci tarafı kopuş: {type(exc).__name__}: {str(exc)[:120]}")

        await asyncio.sleep(1)
        d = settings.materials_dir / str(course)
        disk = sorted((p.name, p.stat().st_size) for p in d.iterdir()) if d.exists() else []
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT id, filepath FROM materials WHERE course_id = ?", (course,)
            )
            mats = [dict(r) for r in await cur.fetchall()]
        finally:
            await db.close()
        yarim_disk = [x for x in disk if "yarim" in x[0]]
        yarim_db = [m for m in mats if "yarim" in m["filepath"]]
        print(f"  diskte 'yarim' dosyası: {yarim_disk}")
        print(f"  DB'de 'yarim' kaydı   : {yarim_db}")
        print(f"  toplam disk: {len(disk)} dosya, toplam materials satırı: {len(mats)}")

        h = await c.get("/health")
        print(f"  kopuştan sonra /health: {h.status_code} {h.text}")

        out.append(
            {
                "senaryo": "K7 yarıda kesilme",
                "yarim_disk": yarim_disk,
                "yarim_db": yarim_db,
                "health": h.status_code,
            }
        )

    Path("_a14_matrix2_sonuc.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


asyncio.run(main())
