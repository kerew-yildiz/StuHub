"""SM-2 uzamsal tekrar — deterministik saf fonksiyonlar (Yetenek 09).

Again/Hard/Good/Easy → kalite 1/3/4/5. `ease_factor` [1.3, 2.5] aralığında
kırpılır; `interval_days` tavanı 365; Again her zaman interval 1 + repetitions 0.
`next_review_state` aynı girdi için her zaman aynı çıktıyı verir (zaman
bağımlılığı yok; `due_at` hesabı bu modülün dışındadır).

Ek iki saf fonksiyon (Plan #9 / #12) zamanı GİRDİ olarak alır — `datetime.now()`
çağrısı yok, dolayısıyla bunlar da tam deterministik ve testtedir:
- `compress_to_deadline` — tekrar kuyruğunu sınav tarihine sıkıştırır (Plan #9).
- `retention_estimate` — SM-2 aralığından üstel bozunmayla hatırlama tahmini (Plan #12).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import cast

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


# ── Sınav geri sayım planlayıcısı (Plan #9) ────────────────────────────────


def _as_date(value: date | datetime | str | None) -> date | None:
    """Tarih benzeri değeri `date`e indirger; boş/bozuk değer için None döner."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _study_days(exam_date: date, today: date) -> list[date]:
    """Sınava kadarki çalışma günleri: bugün .. sınavdan bir gün öncesi.

    Sınav bugünse tek gün (bugün) döner — kalan her şey bugüne sığmak zorunda.
    Sınav geçmişse pencere boştur.
    """
    if exam_date < today:
        return []
    span = (exam_date - today).days
    if span == 0:
        return [today]
    return [today + timedelta(days=offset) for offset in range(span)]


def compress_to_deadline(
    reviews: Iterable[Mapping[str, object]],
    exam_date: date,
    today: date,
) -> dict[str, list[str]]:
    """Tekrar kuyruğunu sınav tarihine sıkıştırır; günlük dağıtım döner.

    `reviews` öğeleri en az `card_id` ve `due_at` (date/datetime/ISO metin/None)
    anahtarlarını taşır. Vadesi sınavdan SONRAYA düşen, vadesi geçmiş ve hiç
    tekrar edilmemiş kartlar pencerenin tamamına dağıtılabilir; pencere içinde
    vadesi olan kart doğal gününde kalır (o gün doluysa sınavdan önceki daha
    hafif bir güne kayar, asla sınavdan sonraya).

    Yerleştirme en kısıtlı karttan (en geç başlayabilenden) başlar ve her kartı
    izin verilen aralıktaki EN AZ yüklü güne koyar — aşırı yük böylece günlere
    dengeli bölünür. Dönüş: {'YYYY-MM-DD': [card_id, ...]}, yalnızca dolu günler.
    """
    days = _study_days(exam_date, today)
    if not days:
        return {}

    first, last = days[0], days[-1]
    entries: list[tuple[int, str]] = []
    for review in reviews:
        card_id = str(review["card_id"])
        due = _as_date(cast("date | datetime | str | None", review.get("due_at")))
        # 0 = yeni / vadesi geçmiş / sınav sonrasına taşan
        earliest = 0 if due is None or due <= first or due > last else (due - first).days
        entries.append((earliest, card_id))

    # En kısıtlı kart önce yerleşir; kalan esnek kartlar boşlukları doldurur.
    entries.sort(key=lambda entry: (-entry[0], entry[1]))

    buckets: list[list[str]] = [[] for _ in days]
    for earliest, card_id in entries:
        target = min(range(earliest, len(days)), key=lambda index: (len(buckets[index]), index))
        buckets[target].append(card_id)

    return {
        day.isoformat(): cards for day, cards in zip(days, buckets, strict=True) if cards
    }


# ── Unutma eğrisi (Plan #12) ───────────────────────────────────────────────

# SM-2 aralıkları hedef tutma oranı ~%90 olacak şekilde seçilir: t = interval
# anında R = 0.9 olmasını isteriz, yani stabilite = interval / -ln(0.9).
TARGET_RETENTION = 0.9
_DECAY_AT_INTERVAL = -math.log(TARGET_RETENTION)


def _as_datetime(value: date | datetime | str | None) -> datetime | None:
    """Zaman benzeri değeri UTC farkındalı `datetime`a çevirir (naive → UTC varsayılır)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        moment = datetime(value.year, value.month, value.day)
    else:
        try:
            moment = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def retention_estimate(
    ease: float,
    interval_days: float,
    last_review: date | datetime | str | None,
    now: date | datetime | str,
) -> float:
    """Kartın `now` anındaki tahmini hatırlama oranı — 0..1 (Ebbinghaus tarzı).

    R = exp(-Δt / S); stabilite S, SM-2 aralığından türetilir:
    S = interval_days · (ease / 2.5) / -ln(0.9). Yani ideal kartta (ease 2.5)
    aralığın sonunda R ≈ 0.9; zor kartta (ease 1.3) aynı aralıkta daha düşük.

    Sınır durumlar: hiç tekrar edilmemiş kart (last_review yok veya interval 0)
    → 0.0; aynı gün/aynı an tekrar (Δt ≤ 0) → 1.0.
    """
    if last_review is None or interval_days <= 0:
        return 0.0
    last = _as_datetime(last_review)
    current = _as_datetime(now)
    if last is None or current is None:
        return 0.0

    elapsed_days = (current - last).total_seconds() / 86400.0
    if elapsed_days <= 0:
        return 1.0

    stability = interval_days * (_clamp_ease(ease) / MAX_EASE) / _DECAY_AT_INTERVAL
    return round(math.exp(-elapsed_days / stability), 4)
