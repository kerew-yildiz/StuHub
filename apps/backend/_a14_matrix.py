"""Alan-14 geçici tanı matrisi: materyal yükleme hata yolları (in-process ASGI).

Gerçek router/servis kodunu çalıştırır; her senaryoda HTTP kodu, yanıt gövdesi,
diskte kalan artık ve DB'deki yetim kayıt raporlanır. Sonunda tüm gövdeler
stack-trace sızıntısı için taranır.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("STUHUB_DATA_DIR", tempfile.mkdtemp(prefix="a14_"))
os.environ["DATABASE_URL"] = ""  # yerel/SQLite mod — gerçek Postgres'e dokunma

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import pymupdf  # noqa: E402

from src.config import settings  # noqa: E402
from src.db import get_db, init_db  # noqa: E402
from src.main import app  # noqa: E402

settings.database_url = ""
settings.data_dir = Path(os.environ["STUHUB_DATA_DIR"])

# Sızıntı göstergeleri: Python izleri, dosya sistemi yolları, kütüphane adları
LEAK_PATTERNS = [
    (r"Traceback \(most recent call last\)", "python traceback"),
    (r'File "[^"]+", line \d+', "kaynak dosya:satır"),
    (r"[A-Za-z]:\\\\?Users\\\\?", "windows mutlak yol"),
    (r"/(?:home|mnt|tmp|var)/[\w./-]+", "unix mutlak yol"),
    (r"site-packages", "site-packages yolu"),
    (r"\b(?:pymupdf|fitz|asyncpg|aiosqlite|mupdf|sqlalchemy)\b", "iç kütüphane adı"),
    (r"\bErrno \d+", "errno"),
    (r"postgres(?:ql)?://|password=", "bağlantı dizesi"),
]

RESULTS: list[dict] = []


def scan_leak(text: str) -> list[str]:
    return [label for pat, label in LEAK_PATTERNS if re.search(pat, text, re.IGNORECASE)]


def make_encrypted_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "gizli icerik")
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-parola",
        user_pw="kullanici-parola",
    )
    doc.close()


def make_valid_pdf(path: Path, pages: int = 1) -> None:
    doc = pymupdf.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 72), f"Sayfa {i + 1}: hucre zari ve difuzyon konusu. " * 8)
    doc.save(str(path))
    doc.close()


async def db_rows(course_id: int) -> tuple[list[dict], list[dict]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, type, filepath, page_count FROM materials WHERE course_id = ?",
            (course_id,),
        )
        mats = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute(
            "SELECT id, material_id, status, progress, error FROM indexing_jobs "
            "WHERE course_id = ?",
            (course_id,),
        )
        jobs = [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()
    return mats, jobs


def disk_state(course_id: int) -> list[tuple[str, int]]:
    d = settings.materials_dir / str(course_id)
    if not d.exists():
        return []
    return sorted((p.name, p.stat().st_size) for p in d.iterdir())


def record(name: str, status: int, body: str, disk, mats, jobs, note: str = "") -> None:
    leaks = scan_leak(body) + scan_leak(json.dumps(jobs, ensure_ascii=False))
    RESULTS.append(
        {
            "senaryo": name,
            "http": status,
            "govde": body[:400],
            "disk": disk,
            "materials": mats,
            "jobs": jobs,
            "sizinti": leaks,
            "not": note,
        }
    )
    print(f"\n=== {name}")
    print(f"  HTTP {status}")
    print(f"  gövde: {body[:300]}")
    print(f"  disk artığı: {disk}")
    print(f"  materials: {mats}")
    print(f"  jobs: {jobs}")
    if leaks:
        print(f"  !! SIZINTI: {leaks}")


async def main() -> None:
    await init_db()
    tmp = Path(tempfile.mkdtemp(prefix="a14_files_"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=300) as c:
        r = await c.post("/api/terms", json={"name": "[TEST] Alan14"})
        term = r.json()["id"]
        r = await c.post(f"/api/terms/{term}/courses", json={"name": "[TEST] Alan14 Hata"})
        course = r.json()["id"]
        print("term", term, "course", course)

        # --- K3 bozuk PDF (rastgele bayt, .pdf uzantılı)
        bad = tmp / "bozuk.pdf"
        bad.write_bytes(os.urandom(50_000))
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("bozuk.pdf", bad.read_bytes(), "application/pdf")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K3 bozuk PDF (rastgele bayt)", r.status_code, r.text, disk_state(course), mats, jobs)

        # --- K4 şifreli PDF
        enc = tmp / "sifreli.pdf"
        make_encrypted_pdf(enc)
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("sifreli.pdf", enc.read_bytes(), "application/pdf")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K4 şifreli PDF", r.status_code, r.text, disk_state(course), mats, jobs)

        # --- K5 0 bayt
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("bos.pdf", b"", "application/pdf")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K5 0 bayt dosya", r.status_code, r.text, disk_state(course), mats, jobs)

        # --- K6 limit üstü (sınır geçici olarak 1 MB'a çekilir)
        eski = settings.max_upload_bytes
        settings.max_upload_bytes = 1024 * 1024
        big = b"A" * (3 * 1024 * 1024)
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("buyuk.pdf", big, "application/pdf")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K6 limit üstü (1MB sınır, 3MB dosya)", r.status_code, r.text, disk_state(course), mats, jobs)
        settings.max_upload_bytes = eski

        # --- K8 yanlış MIME: çıplak .txt içerik, PDF uzantısı + application/pdf başlığı
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("aslinda-metin.pdf", "Bu düz bir metin dosyası.\n".encode(), "application/pdf")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K8a yanlış MIME (.txt içerik, .pdf adı)", r.status_code, r.text, disk_state(course), mats, jobs)

        # --- K8b gerçek .txt uzantısı (uzantı kontrolü)
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("notlar.txt", b"metin", "text/plain")},
            data={"type": "textbook"},
        )
        mats, jobs = await db_rows(course)
        record("K8b yanlış uzantı (.txt, type=textbook)", r.status_code, r.text, disk_state(course), mats, jobs)

        # --- K9 aynı anda 5 hatalı yükleme
        async def one(i: int):
            return await c.post(
                f"/api/courses/{course}/materials",
                files={"file": (f"esz-{i}.pdf", os.urandom(20_000), "application/pdf")},
                data={"type": "textbook"},
            )

        rs = await asyncio.gather(*(one(i) for i in range(5)), return_exceptions=True)
        codes = [getattr(x, "status_code", repr(x)) for x in rs]
        h = await c.get("/health")
        mats, jobs = await db_rows(course)
        record(
            "K9 eşzamanlı 5 hatalı yükleme",
            h.status_code,
            f"kodlar={codes} | /health gövdesi={h.text}",
            disk_state(course),
            mats,
            jobs,
            note="HTTP sütunu /health kodudur",
        )

        # --- K10 geçersiz type / olmayan ders (ek hata yolları)
        r = await c.post(
            f"/api/courses/{course}/materials",
            files={"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")},
            data={"type": "haydaa"},
        )
        record("K10a geçersiz materyal türü", r.status_code, r.text, [], [], [])
        r = await c.post(
            "/api/courses/999999/materials",
            files={"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")},
            data={"type": "textbook"},
        )
        record("K10b olmayan ders", r.status_code, r.text, [], [], [])

    print("\n\n########## ÖZET ##########")
    for r in RESULTS:
        flag = " <<< SIZINTI" if r["sizinti"] else ""
        print(f"{r['senaryo']:<45} HTTP {r['http']}{flag}")
    Path("_a14_matrix_sonuc.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("\nJSON: _a14_matrix_sonuc.json")


asyncio.run(main())
