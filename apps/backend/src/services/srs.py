"""SM-2 uzamsal tekrar — deterministik saf fonksiyonlar (Yetenek 09).

Again/Hard/Good/Easy → kalite 1/3/4/5. `ease_factor` [1.3, 2.5] aralığında
kırpılır; `interval_days` tavanı 365; Again her zaman interval 1 + repetitions 0.
Aynı girdi her zaman aynı çıktıyı verir (zaman bağımlılığı yok; `due_at`
hesabı bu modülün dışındadır).
"""

from __future__ import annotations

MIN_EASE = 1.3
MAX_EASE = 2.5
MAX_INTERVAL_DAYS = 365.0

RATING_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}

FIRST_INTERVAL = 1.0
SECOND_INTERVAL = 6.0
EASY_FIRST_INTERVAL = 4.0


def _clamp_ease(value: float) -> float:
    return round(max(MIN_EASE, min(MAX_EASE, value)), 2)


def _clamp_interval(value: float) -> float:
    return round(min(MAX_INTERVAL_DAYS, value), 2)


def next_review_state(
    ease_factor: float,
    interval_days: float,
    repetitions: int,
    rating: str,
) -> tuple[float, float, int]:
    """SM-2 sonraki durumu döner: (yeni_ease, yeni_interval_gün, yeni_tekrar_sayısı)."""
    if rating not in RATING_QUALITY:
        raise ValueError(
            f"Geçersiz tekrar puanı: {rating!r} — 'again', 'hard', 'good' veya 'easy' olmalı."
        )

    if rating == "again":
        return _clamp_ease(ease_factor - 0.2), FIRST_INTERVAL, 0

    if rating == "hard":
        ease = _clamp_ease(ease_factor - 0.15)
        if interval_days == 0:
            next_interval = FIRST_INTERVAL
        elif interval_days == 1:
            next_interval = SECOND_INTERVAL
        else:
            next_interval = interval_days * 1.2
        return ease, _clamp_interval(next_interval), repetitions + 1

    if rating == "good":
        ease = _clamp_ease(ease_factor + 0.1)
        if interval_days == 0:
            next_interval = FIRST_INTERVAL
        elif interval_days == 1:
            next_interval = SECOND_INTERVAL
        else:
            next_interval = interval_days * ease
        return ease, _clamp_interval(next_interval), repetitions + 1

    # easy
    ease = _clamp_ease(ease_factor + 0.1)
    next_interval = (
        EASY_FIRST_INTERVAL if interval_days == 0 else interval_days * ease * 1.3
    )
    return ease, _clamp_interval(next_interval), repetitions + 1


INITIAL_STATE = {"ease_factor": MAX_EASE, "interval_days": 0.0, "repetitions": 0}
