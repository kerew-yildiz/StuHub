"""PDF metin çıkarımı testleri (Yetenek 01)."""

import pymupdf

from src.services.pdf_service import PdfError, extract_pdf_pages, likely_scanned_pages

from conftest import TURKISH_FONT_FILE

# Türkçe karakter destekli sistem fontu (varsayılan Helvetica Türkçe glif içermez)
FONT_FILE = TURKISH_FONT_FILE


def _make_pdf(path, texts):
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11, fontname="arial", fontfile=FONT_FILE)
    doc.save(str(path))
    doc.close()


def test_extract_pdf_pages(tmp_path):
    pdf = tmp_path / "kitap.pdf"
    _make_pdf(pdf, ["İlk sayfa içeriği.", "İkinci sayfa içeriği.", ""])
    pages = extract_pdf_pages(str(pdf))
    assert len(pages) == 3
    assert pages[0] == {"page": 1, "text": "İlk sayfa içeriği."}
    assert pages[1]["page"] == 2
    assert pages[2]["text"] == ""


def test_scanned_detection(tmp_path):
    pdf = tmp_path / "taranmis.pdf"
    _make_pdf(pdf, ["Kısa."] * 2 + ["Uzun ve anlamlı içerik satırı." * 3])
    pages = extract_pdf_pages(str(pdf))
    scanned = likely_scanned_pages(pages)
    assert 1 in scanned and 2 in scanned
    assert 3 not in scanned


def test_encrypted_pdf_error(tmp_path):
    pdf = tmp_path / "sifreli.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Gizli", fontsize=11)
    # pyright stubs PDF_ENCRYPT_* sabitlerini bilmez
    encryption = pymupdf.PDF_ENCRYPT_AES_256  # pyright: ignore[reportAttributeAccessIssue]
    doc.save(str(pdf), encryption=encryption, user_pw="sifre", owner_pw="sahip")
    doc.close()
    try:
        extract_pdf_pages(str(pdf))
        raise AssertionError("şifreli PDF hatasız geçmemeli")
    except PdfError as exc:
        assert "şifreli" in str(exc)


def test_corrupt_pdf_error(tmp_path):
    bad = tmp_path / "bozuk.pdf"
    bad.write_bytes(b"bu bir pdf degil")
    try:
        extract_pdf_pages(str(bad))
        raise AssertionError("bozuk PDF hatasız geçmemeli")
    except PdfError as exc:
        assert "bozuk" in str(exc)
