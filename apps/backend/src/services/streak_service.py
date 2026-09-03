"""Öğrenme alışkanlıkları — streak/günlük hedef türetimi (Yetenek 15).

Saf fonksiyonlar `activity_log` okumalarından kesintisiz gün sayısını ve
günlük hedef ilerlemesini türetir. Kişisel kalır (leaderboard/paylaşım yok).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..auth import LOCAL_TENANT_ID
from ..db import get_db

ACTIVITY_KINDS = ("note", "quiz", "flashcard", "chat")


def _as_date(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def compute_streak(
    active_dates: set[date] | set[str], today: date | None = None
) -> int:
    """Kesintisiz etkin gün sayısı (Yetenek 15).

    Bugün etkinse bugünden, dün etkinse dünden başlayarak geriye doğru sayar;
    ikisi de yoksa 0 (streak kırılmış sayılmaz, "bugün çalış" durumu).
    """
    today = today or date.today()
    dates = {_as_date(d) for d in active_dates}
    if today in dates:
        cursor = today
    elif today - timedelta(days=1) in dates:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def today_totals(counts: dict[str, int]) -> dict[str, int]:
    """Bilinen etkinlik türlerinin bugünkü sayılarını normalize eder."""
    return {kind: max(counts.get(kind, 0), 0) for kind in ACTIVITY_KINDS}


def today_progress(counts: dict[str, int], daily_goal: int) -> tuple[int, int]:
    """(bugünkü toplam etkinlik, hedef) — hedef en az 1."""
    totals = today_totals(counts)
    return sum(totals.values()), max(daily_goal, 1)


def progress_percent(counts: dict[str, int], daily_goal: int) -> int:
    """Günlük hedefin yüzdesi (0–100, yukarı yuvarlanır, tavan 100)."""
    total, goal = today_progress(counts, daily_goal)
    return min(100, round(100 * total / goal))


async def log_activity(
    kind: str, course_id: int | None = None, tenant_id: str = LOCAL_TENANT_ID
) -> None:
    """activity_log'a etkinlik yazar; aynı gün+tür+kurs için count artırır.

    kind: note | quiz | flashcard | chat (diğerleri ValueError).

    Not: benzersiz indeks (date, kind, COALESCE(course_id, 0)) tenant_id içermez
    (schema.sql değiştirilemez) — bu yüzden ON CONFLICT yerine elle kontrol edilir,
    aksi halde SaaS modunda farklı kiracıların sayaçları birbirine karışırdı.
    """
    if kind not in ACTIVITY_KINDS:
        raise ValueError(f"Geçersiz etkinlik türü: {kind!r}")
    today = datetime.now().date().isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM activity_log WHERE tenant_id = ? AND date = ? AND kind = ? "
            "AND COALESCE(course_id, 0) = COALESCE(?, 0)",
            (tenant_id, today, kind, course_id),
        )
        row = await cursor.fetchone()
        if row is not None:
            await db.execute(
                "UPDATE activity_log SET count = count + 1 WHERE id = ?", (row["id"],)
            )
        else:
            await db.execute(
                "INSERT INTO activity_log (tenant_id, date, kind, count, course_id) "
                "VALUES (?, ?, ?, 1, ?)",
                (tenant_id, today, kind, course_id),
            )
        await db.commit()
    finally:
        await db.close()


async def load_today_counts(
    course_id: int | None = None, tenant_id: str = LOCAL_TENANT_ID
) -> dict[str, int]:
    """Bugünün etkinlik sayılarını döner (opsiyonel kurs filtresi)."""
    db = await get_db()
    try:
        if course_id is None:
            cursor = await db.execute(
                "SELECT kind, SUM(count) AS total FROM activity_log "
                "WHERE date = ? AND tenant_id = ? GROUP BY kind",
                (datetime.now().date().isoformat(), tenant_id),
            )
        else:
            cursor = await db.execute(
                "SELECT kind, SUM(count) AS total FROM activity_log "
                "WHERE date = ? AND course_id = ? AND tenant_id = ? GROUP BY kind",
                (datetime.now().date().isoformat(), course_id, tenant_id),
            )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()
    return {row["kind"]: int(row["total"] or 0) for row in rows}


async def load_active_dates(tenant_id: str = LOCAL_TENANT_ID) -> set[str]:
    """Etkinlik kaydı olan tüm tarihler (streak hesabı için)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT date FROM activity_log WHERE tenant_id = ?", (tenant_id,)
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()
    return {row["date"] for row in rows}
