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
