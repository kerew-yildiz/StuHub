"""Alan 12 (syllabus/kazanımlar) test sondası — geçici, test kampanyası sonunda silinecek."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

API = "http://172.25.176.1:8010"
OUT = Path("../../data/alan12-test").resolve()
OUT.mkdir(parents=True, exist_ok=True)

KAZANIM_METNI = [
    "[TEST] IZLENCE - Kimya 101 Ders Izlencesi",
    "",
    "OGRENME KAZANIMLARI",
    "K1: Mol kavramini tanimlar ve Avogadro sayisini kullanarak hesap yapar.",
    "K2: Kimyasal denklemleri denklestirir ve sinirlayici bileseni belirler.",
    "K3: Ideal gaz yasasini uygulayarak basinc-hacim-sicaklik iliskisini cozer.",
    "K4: Asit-baz titrasyonunda esdeger noktayi hesaplar.",
    "K5: Termokimyada entalpi degisimini Hess yasasi ile bulur.",
]


def syllabus_pdf(path: Path, satirlar: list[str]) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for satir in satirlar:
        page.insert_text((60, y), satir, fontsize=12)
        y += 22
    doc.save(str(path))
    doc.close()


def token() -> str:
    url = os.environ["VITE_SUPABASE_URL"].rstrip("/")
    key = os.environ["VITE_SUPABASE_ANON_KEY"]
    r = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": key, "Content-Type": "application/json"},
        json={"email": "kerew.yildiz@gmail.com", "password": "KereM*01"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(Path("../../.env").resolve())

    # Windows saati Supabase'e göre ~6.6 sn geride (2026-09-11 ölçümü) — taze token'ın
    # iat'ı gelecekte kaldığı için backend ilk saniyelerde 401 veriyor; bekleyip geçiyoruz.
    import time as _t

    _t.sleep(10)
    tok = token()
    h = {"Authorization": f"Bearer {tok}"}
    log: dict = {}

    async with httpx.AsyncClient(base_url=API, headers=h, timeout=120) as c:
        # 1) [TEST] dönem + ders (kullanıcının 2026 Güz dönemine dokunulmaz)
        r = await c.post("/api/terms", json={"name": "[TEST] Alan12 Syllabus"})
        log["term_post"] = [r.status_code, r.text[:300]]
        term_id = r.json()["id"]

        r = await c.post(
            f"/api/terms/{term_id}/courses",
            json={"name": "[TEST] Kimya 101 Syllabus", "instructor": "[TEST] Hoca"},
        )
        log["course_post"] = [r.status_code, r.text[:300]]
        course_id = r.json()["id"]

        # 2) syllabus PDF yükle
        pdf = OUT / "alan12-izlence.pdf"
        syllabus_pdf(pdf, KAZANIM_METNI)
        r = await c.post(
            f"/api/courses/{course_id}/materials",
            files={"file": ("alan12-izlence.pdf", pdf.read_bytes(), "application/pdf")},
            data={"type": "syllabus"},
        )
        log["syllabus_upload"] = [r.status_code, r.text[:400]]
        material_id = r.json()["id"]

        # 3) extracted_text dolana kadar bekle (indeksleme async)
        for i in range(60):
            await asyncio.sleep(2)
            r = await c.get(f"/api/materials/{material_id}")
            body = r.json()
            if body.get("extracted_text"):
                log["extracted_text_wait_s"] = (i + 1) * 2
                log["extracted_text_head"] = body["extracted_text"][:300]
                break
        else:
            log["extracted_text_wait_s"] = "TIMEOUT >120s"
            log["extracted_text_head"] = None
        log["material_get"] = [r.status_code, {k: v for k, v in body.items() if k != "extracted_text"}]

        r = await c.get(f"/api/courses/{course_id}/materials")
        log["materials_list"] = [r.status_code, [(m["id"], m["type"], m["display_name"]) for m in r.json()]]

    print(json.dumps({"term_id": term_id, "course_id": course_id, "material_id": material_id, "log": log}, ensure_ascii=False, indent=2))
    (OUT / "step1.json").write_text(
        json.dumps({"term_id": term_id, "course_id": course_id, "material_id": material_id, "log": log}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
