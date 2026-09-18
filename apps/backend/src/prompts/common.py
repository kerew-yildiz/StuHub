"""Ortak prompt yardımcıları (v2 — Bölüm 17, Yetenek 13/15)."""

from __future__ import annotations

# ── Paylaşılan prompt kural blokları (DRY) ──────────────────────────────
# Aynı kural cümlesi birden çok prompt dosyasında birebir geçiyor; metin burada tek
# kaynaktan yayınlanır, tüketici prompt dosyaları bunları şablonlarına ekler.
# Şablonlar `.format()` ile kullanıldığı için bu sabitler süslü parantez İÇERMEZ.

# note_prompts.NOTE_GENERATION_PROMPT (kural 1) + chat_prompts.DIRECT_SYSTEM_PROMPT (kural 1)
KAYNAK_DISI_BILGI_YASAGI = (
    "SADECE sağlanan kaynak parçalarını kullan; kaynaklarda olmayan bilgi EKLEME."
)

# chat_prompts: DIRECT (kural 3) + SOCRATIC (kural 4) + QUIZ (kural 4)
ATIF_LISTESI_KURALI = (
    "[n] numaraları yalnızca aşağıda verilen kaynak listesinden olacak; "
    "listede olmayan numara KULLANMA."
)


def dil_talimati(not_dili: str, *, json_sema: bool = True) -> str:
    """Ayarlanan üretim dili için prompt talimatı (tr/en/auto).

    settings `not_dili`: tr (varsayılan) | en | auto.

    `json_sema=False`: MARKDOWN üreten promptlar için (not bölümleri). Varsayılan
    metindeki "JSON anahtar adları şemada verildiği gibi İngilizce kalacak" cümlesi
    JSON şemalı çağrılar için yazılmıştı; markdown not promptuna girince model
    notu JSON zarfına sarıyordu (2026-09-18 vaka: `{"content": "...", ...}` —
    İngilizce anahtarlar, ham JSON kaydı). Markdown promptlarında bu cümle geçmez.
    """
    if not_dili == "en":
        return "Tüm çıktıları İngilizce yaz."
    if not_dili == "auto":
        return "Çıktı dilini kaynak içeriğin diliyle eşleştir (kaynak Türkçeyse Türkçe yaz)."
    if json_sema:
        return (
            "Tüm çıktıları Türkçe yaz. JSON anahtar adları şemada verildiği gibi "
            "İngilizce kalacak."
        )
    return "Tüm çıktıları Türkçe yaz."


def kazanimlar_blok(kazanimlar: str) -> str:
    """Müfredat/kazanım metnini prompt'a eklenecek bölüm bloğuna çevirir.

    Ders için syllabus materyali yüklenmemişse `kazanimlar` boştur ve bu fonksiyon
    boş string döner — placeholder yerine hiçbir şey basılmaz, prompt cümle akışı
    bozulmaz (bkz. note_generator._load_kazanimlar, quiz_generator._generate_feed_topic).
    """
    if not kazanimlar.strip():
        return ""
    return f"\nKAZANIMLAR (müfredat hedefleri — varsa önceliklendir):\n{kazanimlar}\n"
