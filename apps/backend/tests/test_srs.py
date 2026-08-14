"""SM-2 saf fonksiyon testleri (Yetenek 09 — determinizm + sınırlar)."""

from __future__ import annotations

import pytest

from src.services.srs import (
    INITIAL_STATE,
    MAX_EASE,
    MAX_INTERVAL_DAYS,
    MIN_EASE,
    next_review_state,
)


def test_again_resets_interval_and_reps():
    ease, interval, reps = next_review_state(2.5, 30.0, 5, "again")
    assert ease == 2.3
    assert interval == 1.0
    assert reps == 0


def test_fresh_hard():
    ease, interval, reps = next_review_state(2.5, 0.0, 0, "hard")
    assert ease == 2.35
    assert interval == 1.0
    assert reps == 1


def test_fresh_good():
    # 2.5 + 0.1 → 2.6 üst sınırdan kırpılır
    ease, interval, reps = next_review_state(2.5, 0.0, 0, "good")
    assert ease == MAX_EASE
    assert interval == 1.0
    assert reps == 1


def test_fresh_easy():
    ease, interval, reps = next_review_state(2.5, 0.0, 0, "easy")
    assert ease == MAX_EASE
    assert interval == 4.0
    assert reps == 1


def test_second_review_goes_to_six_days():
    _, interval_hard, _ = next_review_state(2.35, 1.0, 1, "hard")
    _, interval_good, _ = next_review_state(2.5, 1.0, 1, "good")
    assert interval_hard == 6.0
    assert interval_good == 6.0


def test_good_scales_with_ease():
    _, interval, _ = next_review_state(2.5, 6.0, 2, "good")
    assert interval == round(6.0 * 2.5, 2)  # 15.0


def test_easy_scales_with_ease_times_1_3():
    _, interval, _ = next_review_state(2.5, 6.0, 2, "easy")
    assert interval == round(6.0 * 2.5 * 1.3, 2)  # 19.5


def test_ease_floor():
    ease, _, _ = next_review_state(1.31, 10.0, 3, "again")
    assert ease == MIN_EASE  # 1.31 - 0.2 = 1.11 → 1.3
    ease, _, _ = next_review_state(1.3, 10.0, 3, "again")
    assert ease == MIN_EASE


def test_interval_cap():
    _, interval, _ = next_review_state(2.5, 300.0, 10, "easy")
    assert interval == MAX_INTERVAL_DAYS  # 300×2.5×1.3 = 975 → 365


def test_hard_interval_scales():
    _, interval, _ = next_review_state(2.35, 10.0, 2, "hard")
    assert interval == 12.0  # 10 × 1.2


def test_invalid_rating_raises():
    with pytest.raises(ValueError):
        next_review_state(2.5, 0.0, 0, "meh")


def test_determinism():
    first = next_review_state(2.4, 5.0, 2, "good")
    second = next_review_state(2.4, 5.0, 2, "good")
    assert first == second


def test_initial_state():
    assert INITIAL_STATE == {"ease_factor": 2.5, "interval_days": 0.0, "repetitions": 0}
