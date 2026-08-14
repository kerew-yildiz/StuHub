"""FIB eşleştirme normalizasyonu (Yetenek 04 §4) — deterministik, interaksiyonda LLM yok."""

from __future__ import annotations

import re

_COMBINING_DOT = "\u0307"


def _turkish_lower(text: str) -> str:
    """Türkçe küçük harf: İ→i, I→ı; Python'un İ.lower() ürettiği birleşik nokta temizlenir."""
    text = text.replace("İ", "i").replace("I", "ı")
    lowered = text.lower()
    return lowered.replace("i" + _COMBINING_DOT, "i")


def normalize_fib(text: str) -> str:
    """Türkçe normalizasyon: küçük harf, noktalama temizliği, fazla boşluk silme.

    i/ı ayrımı korunur (Türkçe için zorunlu); noktalama işaretleri boşlukla değiştirilir.
    """
    normalized = _turkish_lower(text)
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def fib_is_correct(user_answer: str, accepted_answers: list[str]) -> bool:
    """Kullanıcı cevabını normalize edip kabul listesiyle eşleştirir."""
    user_norm = normalize_fib(user_answer)
    if not user_norm:
        return False
    return any(normalize_fib(accepted) == user_norm for accepted in accepted_answers)
