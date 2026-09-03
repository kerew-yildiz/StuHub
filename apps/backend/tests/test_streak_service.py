"""Streak/günlük hedef saf fonksiyon + activity_log testleri (Yetenek 15)."""

from __future__ import annotations

from datetime import date, timedelta

import aiosqlite
import pytest

from src.config import settings
from src.db import init_db
from src.services.streak_service import (
    compute_streak,
    load_active_dates,
    load_today_counts,
    log_activity,
    progress_percent,
    today_progress,
)

TODAY = date(2026, 8, 15)


def _days(*offsets: int) -> set[str]:
    return {(TODAY - timedelta(days=o)).isoformat() for o in offsets}


def test_streak_starts_today_when_active():
    assert compute_streak(_days(0, 1, 2), TODAY) == 3


def test_streak_starts_yesterday_when_today_inactive():
    assert compute_streak(_days(1, 2, 3), TODAY) == 3


def test_streak_zero_when_both_missing():
    assert compute_streak(_days(2, 3), TODAY) == 0
    assert compute_streak(set(), TODAY) == 0


def test_streak_breaks_at_gap():
    assert compute_streak(_days(0, 2), TODAY) == 1


def test_today_progress_and_percent():
    counts = {"quiz": 2, "chat": 1}
    assert today_progress(counts, 3) == (3, 3)
    assert progress_percent(counts, 3) == 100
    assert today_progress(counts, 5) == (3, 5)
    assert progress_percent(counts, 5) == 60
    assert progress_percent({"flashcard": 10}, 3) == 100  # tavan


async def test_log_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()

    await log_activity("quiz", course_id=1)
    await log_activity("quiz", course_id=1)
    await log_activity("chat", course_id=1)

    counts = await load_today_counts()
    assert counts["quiz"] == 2
    assert counts["chat"] == 1

    course_counts = await load_today_counts(course_id=1)
    assert course_counts["quiz"] == 2

    assert await load_active_dates() != set()

    async with aiosqlite.connect(tmp_path / "stuhub.db") as db:
        cursor = await db.execute("SELECT COUNT(*) AS c FROM activity_log")
        row = await cursor.fetchone()
        assert row is not None and row[0] == 2  # quiz tek satırda birleşti


async def test_log_invalid_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    await init_db()
    with pytest.raises(ValueError):
        await log_activity("meh")
