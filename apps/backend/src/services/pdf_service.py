"""PDF metin çıkarımı — pymupdf (Yetenek 01).

pymupdf AGPL-3.0'dır: kişisel yerel kullanımda kabul (yol haritası Bölüm 7).
"""

from __future__ import annotations

import pymupdf  # PyMuPDF (eski adı fitz)

# Metin oranı bu karakter sayısının altındaysa sayfa "taranmış/boş" sayılır
SCANNED_PAGE_MIN_CHARS = 40


class PdfError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşır."""


def extract_pdf_pages(path: str) -> list[dict]:
    """Sayfa bazlı metin çıkarır: [{"page": 1, "text": "..."}, ...].

    Hatalar: şifreli PDF → PdfError("PDF şifreli; şifreyi kaldırıp tekrar yükleyin.")
             bozuk/okunamaz → PdfError("PDF okunamadı, dosya bozuk olabilir.")
    """
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise PdfError("PDF okunamadı, dosya bozuk olabilir.") from exc

    try:
        if doc.needs_pass:
            raise PdfError("PDF şifreli; şifreyi kaldırıp tekrar yükleyin.")
        pages: list[dict] = []
        for i in range(1, doc.page_count + 1):
            page = doc.load_page(i - 1)
            raw = page.get_text("text")
            text = raw.replace("\xa0", " ").strip() if isinstance(raw, str) else ""
            pages.append({"page": i, "text": text})
        return pages
    finally:
        doc.close()


def likely_scanned_pages(pages: list[dict]) -> list[int]:
    """Metin oranı düşük sayfaları döner (OCR yedeği için — marker-pdf).

    OCR başarısız olsa bile sayfa "boş" işaretlenir, iş devam eder (Yetenek 01 hata modları).
    """
    return [p["page"] for p in pages if len(p["text"]) < SCANNED_PAGE_MIN_CHARS]
