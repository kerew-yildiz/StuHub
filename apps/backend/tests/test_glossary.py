"""Terim sözlüğü testleri (Plan #29 — LLM YOK).

`course_glossary` tamamen SQL + regex üzerinde çalışır: terimler `study_guides`
özetlerinin `key_terms` alanından birleşir, tanım/ilk geçiş bilgisi notların markdown
metninden çıkarılır. Bu yüzden testler LLM'i mock'lamaz, tam tersini doğrular:
`chat_json` çağrılırsa test patlar.
"""

from __future__ import annotations

import json

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services import guide_service
from src.services.guide_service import course_glossary

CHAPTER1_NOTE = """# Veri Yapıları

## Doğrusal yapılar
Yığın LIFO düzeniyle çalışır. Son eklenen ilk çıkar.
- **Kuyruk**: FIFO düzeniyle çalışır, ilk eklenen ilk çıkar.
"""

CHAPTER2_NOTE = """## Hiyerarşik yapılar
Ağaç, düğümlerin bir kök altında toplandığı yapıdır. Yığın burada da anılır.
"""


def _summary(key_terms: list[str], summary_md: str = "Özet") -> str:
    return json.dumps(
        {"summary_md": summary_md, "key_terms": key_terms, "exam_focus": ["odak"]},
        ensure_ascii=False,
    )


async def _seed(tmp_path, *, tenant_id: str = "local") -> None:
    """İki chapter + notları + chapter/ders düzeyi özetler."""
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO terms (id, tenant_id, name) VALUES (1, ?, '2026 Bahar')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO courses (id, tenant_id, term_id, name) VALUES (1, ?, 1, 'Veri Yapıları')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO chapters (id, tenant_id, course_id, title) "
            "VALUES (1, ?, 1, 'Yığın ve Kuyruk')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO chapters (id, tenant_id, course_id, title) VALUES (2, ?, 1, 'Ağaçlar')",
            (tenant_id,),
        )
        await db.execute(
            "INSERT INTO notes (id, tenant_id, chapter_id, content_md) VALUES (1, ?, 1, ?)",
            (tenant_id, CHAPTER1_NOTE),
        )
        await db.execute(
            "INSERT INTO notes (id, tenant_id, chapter_id, content_md) VALUES (2, ?, 2, ?)",
            (tenant_id, CHAPTER2_NOTE),
        )
        # Chapter özetleri + ders geneli özet (kind='summary').
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (1, ?, 1, 1, 'summary', ?)",
            (tenant_id, _summary(["Yığın", "Kuyruk"])),
        )
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (2, ?, 1, 2, 'summary', ?)",
            (tenant_id, _summary(["Ağaç", "Yığın"])),
        )
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (3, ?, 1, NULL, 'summary', ?)",
            (tenant_id, _summary(["Graf", "Kuyruk"])),
        )
        await db.commit()


@pytest.fixture(autouse=True)
def _forbid_llm(monkeypatch):
    """Sözlük yolu LLM çağırmaz — çağırırsa test başarısız olur."""

    async def explode(*args, **kwargs):  # pragma: no cover - çağrılmaması gerekir
        raise AssertionError("terim sözlüğü LLM çağırmamalı")

    monkeypatch.setattr(guide_service.llm_service, "chat_json", explode)


async def test_glossary_merges_chapter_and_course_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)

    entries = await course_glossary(1)

    # Tekilleştirilmiş ve alfabetik (Kuyruk hem chapter hem ders özetinde geçiyor).
    assert [e["term"] for e in entries] == ["Ağaç", "Graf", "Kuyruk", "Yığın"]

    by_term = {e["term"]: e for e in entries}

    # Terimi bildiren rehber chapter 2 ama ilk geçiş de chapter 2 notunda.
    agac = by_term["Ağaç"]
    assert agac["definition"] == "Ağaç, düğümlerin bir kök altında toplandığı yapıdır."
    assert (agac["chapter_id"], agac["note_id"]) == (2, 2)
    assert agac["chapter_title"] == "Ağaçlar"
    assert agac["heading"] == "Hiyerarşik yapılar"
    assert agac["position"] == CHAPTER2_NOTE.index("Ağaç,")

    # Ders geneli özetten gelen, hiçbir notta geçmeyen terim: bağlantısız kalır.
    graf = by_term["Graf"]
    assert graf["definition"] == ""
    assert graf["chapter_id"] is None
    assert graf["chapter_title"] is None
    assert graf["note_id"] is None
    assert graf["position"] is None
    assert graf["heading"] is None

    # Madde işaretli + kalın yazılmış terim: markdown temizlenir.
    kuyruk = by_term["Kuyruk"]
    assert kuyruk["definition"] == "Kuyruk: FIFO düzeniyle çalışır, ilk eklenen ilk çıkar."
    assert (kuyruk["chapter_id"], kuyruk["note_id"]) == (1, 1)
    assert kuyruk["heading"] == "Doğrusal yapılar"

    # Birden fazla notta geçen terim: chapter sırasına göre İLK geçiş kazanır.
    yigin = by_term["Yığın"]
    assert yigin["definition"] == "Yığın LIFO düzeniyle çalışır."
    assert (yigin["chapter_id"], yigin["note_id"]) == (1, 1)
    assert yigin["chapter_title"] == "Yığın ve Kuyruk"


async def test_glossary_uses_latest_guide_and_latest_note(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        # Chapter 1 için yeniden üretilmiş özet: eski key_terms geçersiz.
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (4, 'local', 1, 1, 'summary', ?)",
            (_summary(["Öbek"]),),
        )
        # Chapter 1 için yeni not: tanım yeni metinden çıkmalı.
        await db.execute(
            "INSERT INTO notes (id, tenant_id, chapter_id, content_md) "
            "VALUES (5, 'local', 1, ?)",
            ("## Bellek\nÖbek dinamik bellek alanıdır. Çerçeveler ayrı tutulur.\n",),
        )
        await db.commit()

    by_term = {e["term"]: e for e in await course_glossary(1)}

    assert "Öbek" in by_term
    assert by_term["Öbek"]["definition"] == "Öbek dinamik bellek alanıdır."
    assert by_term["Öbek"]["note_id"] == 5
    assert by_term["Öbek"]["heading"] == "Bellek"
    # Eski özetin terimleri chapter 1'den düştü; Yığın yalnızca chapter 2 özetinde kaldı
    # ve chapter 1'in yeni notunda geçmediği için ilk geçiş chapter 2'ye kayar.
    assert by_term["Yığın"]["chapter_id"] == 2
    assert by_term["Yığın"]["note_id"] == 2
    assert "Kuyruk" in by_term  # ders geneli özetten gelmeye devam eder


async def test_glossary_tenant_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path, tenant_id="tenant-a")

    mine = await course_glossary(1, tenant_id="tenant-a")
    assert [e["term"] for e in mine] == ["Ağaç", "Graf", "Kuyruk", "Yığın"]

    # Başka kiracı aynı course_id ile hiçbir terim/tanım göremez.
    assert await course_glossary(1, tenant_id="tenant-b") == []


async def test_glossary_empty_states(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute("INSERT INTO terms (id, name) VALUES (1, 'T')")
        await db.execute("INSERT INTO courses (id, term_id, name) VALUES (1, 1, 'C')")
        await db.execute(
            "INSERT INTO chapters (id, course_id, title) VALUES (1, 1, 'B1')"
        )
        await db.commit()

    # Hiç rehber yok.
    assert await course_glossary(1) == []

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        # Rehber var ama anahtar terim listesi boş.
        await db.execute(
            "INSERT INTO study_guides (tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES ('local', 1, 1, 'summary', ?)",
            (_summary([]),),
        )
        # Yalnızca kavram haritası olan chapter da terim üretmez.
        await db.execute(
            "INSERT INTO study_guides (tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES ('local', 1, 1, 'concept_map', ?)",
            (json.dumps({"nodes": [{"id": "k1", "label": "Yığın"}], "edges": []}),),
        )
        await db.commit()

    assert await course_glossary(1) == []


async def test_glossary_skips_corrupt_guide_content(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    await _seed(tmp_path)
    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        await db.execute(
            "INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json) "
            "VALUES (9, 'local', 1, 2, 'summary', '{bozuk')"
        )
        await db.commit()

    # Chapter 2'nin en yeni özeti bozuk → o chapter atlanır, diğerleri korunur.
    terms = [e["term"] for e in await course_glossary(1)]
    assert terms == ["Graf", "Kuyruk", "Yığın"]


async def test_glossary_endpoint(client, tmp_path):
    await _seed(tmp_path)

    missing = await client.get("/api/courses/999/glossary")
    assert missing.status_code == 404

    response = await client.get("/api/courses/1/glossary")
    assert response.status_code == 200
    body = response.json()
    assert [e["term"] for e in body] == ["Ağaç", "Graf", "Kuyruk", "Yığın"]
    assert set(body[0]) == {
        "term",
        "definition",
        "chapter_id",
        "chapter_title",
        "note_id",
        "position",
        "heading",
    }
    # Sözlük yalnızca terim/tanım verir; cevap anahtarı sızdırmaz.
    assert "answer_key" not in response.text
