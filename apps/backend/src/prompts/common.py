"""Ortak prompt yardımcıları (v2 — Bölüm 17, Yetenek 13/15)."""

from __future__ import annotations


def dil_talimati(not_dili: str) -> str:
    """Ayarlanan üretim dili için prompt talimatı (tr/en/auto).

    settings `not_dili`: tr (varsayılan) | en | auto.
    """
    if not_dili == "en":
        return "Tüm çıktıları İngilizce yaz."
    if not_dili == "auto":
        return "Çıktı dilini kaynak içeriğin diliyle eşleştir (kaynak Türkçeyse Türkçe yaz)."
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
