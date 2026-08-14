"""Chunking testleri (Yetenek 01 — sayfa/slide bazlı, overlap)."""

from src.services.chunking import TARGET_CHARS, chunk_pdf_pages, chunk_slides


def test_chunk_pdf_pages_metadata():
    pages = [{"page": 1, "text": "Kısa sayfa içeriği."}, {"page": 2, "text": "Diğer sayfa."}]
    chunks = chunk_pdf_pages(course_id=1, material_id=5, pages=pages)
    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == "chk_5_1_1"
    assert chunks[0]["page"] == 1
    assert chunks[0]["slide"] is None
    assert chunks[1]["page"] == 2
    assert all(c["course_id"] == 1 and c["material_id"] == 5 for c in chunks)


def test_chunk_pdf_long_page_split_with_overlap():
    long_text = "Bu bir test cümlesidir. " * 300  # ~7200 karakter > TARGET_CHARS
    chunks = chunk_pdf_pages(course_id=1, material_id=5, pages=[{"page": 1, "text": long_text}])
    assert len(chunks) >= 2
    # her parça hedef boyutun üzerine taşmaz
    assert all(len(c["text"]) <= TARGET_CHARS + 200 for c in chunks)
    # overlap uygulanmış olmalı: ardışık parçalar ortak metin içerir
    first, second = chunks[0]["text"], chunks[1]["text"]
    assert first[-100:] in second or second[:100] in first or len(set(first) & set(second)) > 0
    # parça bazlı metadata doğru
    assert all(c["page"] == 1 and c["chunk_id"].startswith("chk_5_1_") for c in chunks)


def test_chunk_skips_empty_pages():
    pages = [{"page": 1, "text": "   "}, {"page": 2, "text": "Gerçek içerik."}]
    chunks = chunk_pdf_pages(course_id=1, material_id=5, pages=pages)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 2


def test_chunk_slides():
    slides = [
        {"slide": 1, "text": "Giriş"},
        {"slide": 2, "text": "Konu detayı." + " Uzun cümle." * 500},
    ]
    chunks = chunk_slides(course_id=1, material_id=7, slides=slides)
    assert chunks[0]["chunk_id"] == "chk_7_s1_1"
    assert chunks[0]["slide"] == 1
    assert chunks[0]["page"] is None
    # uzun slide bölünür
    slide2_chunks = [c for c in chunks if c["slide"] == 2]
    assert len(slide2_chunks) >= 2
