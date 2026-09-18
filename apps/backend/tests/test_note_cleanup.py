"""`note_cleanup` normalizasyon testleri (2026-09-18 not-uretim-bozuk-cikti).

Girdi örnekleri kabul testinin istediği beş durumu kapsar: (a) çitli tek nesne,
(b) art arda üç nesne, (c) çitsiz düz markdown, (d) `\\n` kaçışlı içerik,
(e) sitasyonlu içerik — artı gerçek vaka (not 22) ve kesik/JSON-olmayan çit kenarları.
"""

from __future__ import annotations

from pathlib import Path

from src.services.note_cleanup import SectionStream, normalize_note_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "not-uretim-bozuk-ornek.txt"


def test_fenced_single_object_unwrapped():
    raw = '```json\n{"content": "### Konu A\\n\\nBağlı listeler doğrusaldır [1].\\n"}\n```'
    out = normalize_note_markdown(raw)
    assert out == "### Konu A\n\nBağlı listeler doğrusaldır [1]."
    assert "```" not in out and '"content"' not in out


def test_three_consecutive_objects_joined():
    raw = (
        '```json\n{"content": "### Konu A\\n\\nBirinci bilgi [1]."}\n```\n\n'
        '{"content": "### Konu B\\n\\nİkinci bilgi [2]."}\n\n'
        '```json\n{"content": "### Konu C\\n\\nÜçüncü bilgi [3]."}\n```'
    )
    out = normalize_note_markdown(raw)
    assert out.split("\n\n") == [
        "### Konu A",
        "Birinci bilgi [1].",
        "### Konu B",
        "İkinci bilgi [2].",
        "### Konu C",
        "Üçüncü bilgi [3].",
    ]
    assert "json" not in out and '"content"' not in out


def test_plain_markdown_untouched():
    raw = "### Konu A\n\n**Temel Kavramlar:**\n* Düğümler işaretçi taşır [1].\n"
    assert normalize_note_markdown(raw) == raw.strip()


def test_escaped_newlines_decoded():
    raw = '{"content": "### Konu\\n\\nSatır bir.\\nSatır iki [2]."}'
    assert normalize_note_markdown(raw) == "### Konu\n\nSatır bir.\nSatır iki [2]."


def test_bare_escaped_text_decoded():
    raw = '"### Konu\\n\\nKaynaklardan doğrulanmış bilgi [1]."'
    assert normalize_note_markdown(raw) == "### Konu\n\nKaynaklardan doğrulanmış bilgi [1]."


def test_citations_preserved():
    raw = (
        '```json\n{"content": "### Konu A\\n\\nBilgi [3].\\n\\n'
        'Dış bağlantı [kaynak](stuhub-citation://3)."}\n```'
    )
    out = normalize_note_markdown(raw)
    assert "[3]" in out
    assert "[kaynak](stuhub-citation://3)" in out


def test_markdown_with_trailing_schema_dump():
    raw = (
        "### Freud'un Evreleri\n\n* Erojen bölgeler vardır [3].\n\n"
        '```json\n{\n  "topic": "Freud",\n  "summary": "Özet",\n  "stages_count": 5\n}\n```'
    )
    out = normalize_note_markdown(raw)
    assert out == "### Freud'un Evreleri\n\n* Erojen bölgeler vardır [3]."
    assert "stages_count" not in out


def test_non_json_code_fence_preserved():
    raw = '### Konu A\n\n```python\nprint("merhaba")\n```\n'
    assert normalize_note_markdown(raw) == "### Konu A\n\n```python\nprint(\"merhaba\")\n```"


def test_content_less_envelope_returns_empty():
    """İçerik anahtarı olmayan zarf markdown üretmez — çağıran yedeğe düşer."""
    assert normalize_note_markdown('{"topic": "Freud", "summary": "Özet"}') == ""


def test_truncated_envelope_recovered():
    raw = '```json\n{"content": "### Konu A\\n\\nToken bütçesi kesildi, devamı yok'
    out = normalize_note_markdown(raw)
    assert out == "### Konu A\n\nToken bütçesi kesildi, devamı yok"


def test_nested_envelope_unwrapped():
    raw = '{"content": "{\\"content\\": \\"### Konu A\\\\n\\\\nNested [1].\\"}"}'
    assert normalize_note_markdown(raw) == "### Konu A\n\nNested [1]."


def test_real_broken_note_normalized():
    """Kullanıcının ekranındaki HAM içerik (notes.id=22) → düzgün markdown."""
    raw = FIXTURE.read_text(encoding="utf-8")
    out = normalize_note_markdown(raw)

    assert "```" not in out
    assert '"content"' not in out
    assert "\\n" not in out
    assert out.startswith("### Çocuk Gelişimine Giriş ve Tanımı\n\nÇocuk gelişimi,")
    # Üç bölüm başlığı da korunur (3 ayrı üretim çağrısının çıktısı).
    assert out.count("\n### ") + out.startswith("### ") == 3
    # Markdown işaretleri ve sitasyonlar ham hâlde DEĞİL, işlenmiş metin olarak durur.
    assert "**Temel Kavramlar:**" in out
    assert "[3]" in out
    assert len(out) > 2000


def test_section_stream_passes_plain_markdown_through():
    stream = SectionStream()
    emitted = "".join(stream.feed(delta) for delta in ["### Konu", "\n\n", "Bilgi [1]."])
    assert emitted == "### Konu\n\nBilgi [1]."
    assert stream.cleaned() == "### Konu\n\nBilgi [1]."


def test_section_stream_holds_back_json_envelope():
    stream = SectionStream()
    deltas = ['```json\n{"con', 'tent": "### Konu A\\n\\nBilgi [1].', '"}\n```']
    emitted = "".join(stream.feed(delta) for delta in deltas)
    assert emitted == ""  # ham JSON canlı önizlemeye düşmez
    assert stream.cleaned() == "### Konu A\n\nBilgi [1]."


def test_glued_heading_split():
    """Cümleye yapışmış başlık ayrılır (markdown olarak render edilebilsin)."""
    raw = "### Konu A\n\nBir bilgi [2].### Konu B\n\nİkinci bilgi [1]."
    expected = "### Konu A\n\nBir bilgi [2].\n\n### Konu B\n\nİkinci bilgi [1]."
    assert normalize_note_markdown(raw) == expected


def test_metadata_hashes_not_touched():
    """Metin içi `#` (C#, URL çapası) başlık sanılmaz."""
    raw = "### Konu A\n\nC# dili ve https://x.dev/a#bolum bağlantısı."
    assert normalize_note_markdown(raw) == raw
