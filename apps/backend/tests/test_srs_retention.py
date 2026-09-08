"""`srs.compress_to_deadline` + `srs.retention_estimate` testleri (Plan #9 / #12).

İki fonksiyon da saf: zaman girdi olarak verilir, IO/LLM yok — sınır durumlar
(geçmiş sınav, sınav günü, hiç tekrar edilmemiş kart, aynı gün tekrar) burada.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.services import srs

TODAY = date(2026, 6, 1)


def _cards(count: int, due: date | None) -> list[dict]:
    return [{"card_id": f"c{index}", "due_at": due} for index in range(count)]


# ── compress_to_deadline ───────────────────────────────────────────────────


def test_compress_pulls_post_exam_cards_before_exam():
    """Vadesi sınavdan sonraya düşen kart sınav öncesine çekilir."""
    exam = date(2026, 6, 5)
    plan = srs.compress_to_deadline(
        [
            {"card_id": "late-1", "due_at": date(2026, 7, 20)},
            {"card_id": "late-2", "due_at": date(2026, 12, 1)},
        ],
        exam,
        TODAY,
    )

    assert set(plan) <= {"2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"}
    assert sorted(card for cards in plan.values() for card in cards) == ["late-1", "late-2"]
    assert max(plan) < exam.isoformat()  # sınav gününe hiçbir şey konmaz


def test_compress_keeps_natural_due_day_when_not_overloaded():
    """Yük yoksa pencere içindeki kart kendi vade gününde kalır."""
    plan = srs.compress_to_deadline(
        [
            {"card_id": "a", "due_at": TODAY},
            {"card_id": "b", "due_at": date(2026, 6, 3)},
            {"card_id": "c", "due_at": date(2026, 6, 6)},
        ],
        date(2026, 6, 10),
        TODAY,
    )

    assert plan == {"2026-06-01": ["a"], "2026-06-03": ["b"], "2026-06-06": ["c"]}


def test_compress_balances_overload_across_days():
    """Aşırı yük günlere dengeli bölünür (gün başına fark en fazla 1 kart)."""
    plan = srs.compress_to_deadline(
        _cards(10, date(2026, 8, 1)),  # hepsi sınav sonrasına taşıyor
        date(2026, 6, 5),  # 4 çalışma günü
        TODAY,
    )

    loads = sorted(len(cards) for cards in plan.values())
    assert len(plan) == 4
    assert loads == [2, 2, 3, 3]
    assert sum(loads) == 10


def test_compress_new_and_overdue_cards_enter_window():
    """Hiç tekrar edilmemiş (due_at None) ve vadesi geçmiş kart plana girer."""
    plan = srs.compress_to_deadline(
        [
            {"card_id": "new", "due_at": None},
            {"card_id": "overdue", "due_at": date(2026, 5, 20)},
        ],
        date(2026, 6, 3),
        TODAY,
    )

    assert sorted(card for cards in plan.values() for card in cards) == ["new", "overdue"]


def test_compress_exam_today_uses_single_day():
    """Sınav bugünse tüm kartlar bugüne sığmak zorunda."""
    plan = srs.compress_to_deadline(_cards(3, None), TODAY, TODAY)

    assert plan == {"2026-06-01": ["c0", "c1", "c2"]}


def test_compress_past_exam_returns_empty_plan():
    """Sınav geçmişse çalışma penceresi yok — boş plan."""
    assert srs.compress_to_deadline(_cards(5, None), date(2026, 5, 30), TODAY) == {}


def test_compress_accepts_iso_string_due_dates():
    """`due_at` SQLite'tan gelen ISO metin de olabilir."""
    plan = srs.compress_to_deadline(
        [{"card_id": "s", "due_at": "2026-06-04 09:30:00"}],
        date(2026, 6, 10),
        TODAY,
    )

    assert plan == {"2026-06-04": ["s"]}


# ── retention_estimate ─────────────────────────────────────────────────────

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def test_retention_never_reviewed_is_zero():
    """Hiç tekrar edilmemiş kart: last_review yok veya interval 0 → 0.0."""
    assert srs.retention_estimate(2.5, 0.0, None, NOW) == 0.0
    assert srs.retention_estimate(2.5, 10.0, None, NOW) == 0.0
    assert srs.retention_estimate(2.5, 0.0, NOW - timedelta(days=3), NOW) == 0.0


def test_retention_same_moment_review_is_full():
    """Aynı an/aynı gün tekrar edilen kart tam hatırlanır."""
    assert srs.retention_estimate(2.5, 6.0, NOW, NOW) == 1.0
    assert srs.retention_estimate(2.5, 6.0, NOW + timedelta(hours=2), NOW) == 1.0


def test_retention_at_interval_end_matches_sm2_target():
    """İdeal kartta (ease 2.5) aralığın sonunda tutma oranı ≈ %90."""
    value = srs.retention_estimate(2.5, 6.0, NOW - timedelta(days=6), NOW)
    assert abs(value - srs.TARGET_RETENTION) < 0.001


def test_retention_decays_monotonically():
    """Zaman ilerledikçe tahmin düşer ve 0..1 aralığında kalır."""
    series = [
        srs.retention_estimate(2.5, 6.0, NOW - timedelta(days=elapsed), NOW)
        for elapsed in (0, 3, 6, 30, 200)
    ]

    assert series == sorted(series, reverse=True)
    assert all(0.0 <= value <= 1.0 for value in series)
    assert series[-1] < 0.1


def test_retention_harder_cards_decay_faster():
    """Aynı aralıkta düşük ease (zor kart) daha hızlı unutulur."""
    easy = srs.retention_estimate(2.5, 10.0, NOW - timedelta(days=10), NOW)
    hard = srs.retention_estimate(1.3, 10.0, NOW - timedelta(days=10), NOW)

    assert hard < easy


def test_retention_accepts_naive_sqlite_timestamp():
    """SQLite CURRENT_TIMESTAMP metni (naive, UTC) parse edilir ve UTC sayılır."""
    value = srs.retention_estimate(2.5, 6.0, "2026-05-26 12:00:00", NOW)

    assert abs(value - srs.TARGET_RETENTION) < 0.001
