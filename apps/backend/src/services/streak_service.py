"""Öğrenme alışkanlıkları — streak/günlük hedef türetimi (Yetenek 15).

Saf fonksiyonlar `activity_log` okumalarından kesintisiz gün sayısını ve
günlük hedef ilerlemesini türetir. Kişisel kalır (leaderboard/paylaşım yok).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from ..auth import LOCAL_TENANT_ID
from ..config import settings
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


# ── Öğrenme ilerlemesi göstergesi (Plan #48) ────────────────────────────

# Bir kartın "kalıcı hatırlandı" sayılması için gereken SM-2 aralık eşiği (gün).
# SRS pratiğinde ~3 haftalık aralık kısa vadeli ezberden ayırt edici kabul edilir.
MASTERY_INTERVAL_DAYS = 21.0


def _week_start(today: date) -> date:
    """Bu haftanın Pazartesi günü (bugün dahil) — ISO hafta sınırı."""
    return today - timedelta(days=today.weekday())


def _week_start_param(today: date) -> datetime | str:
    """Hafta başlangıcı zaman filtresi — `feed_service._cutoff` ile aynı ikili biçim:
    SaaS/Postgres'te native `datetime` (asyncpg TIMESTAMPTZ karşılaştırması için),
    SQLite'ta `CURRENT_TIMESTAMP` ile aynı 'YYYY-MM-DD HH:MM:SS' metni."""
    monday = _week_start(today)
    moment = datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    if settings.saas_mode:
        return moment
    return moment.strftime("%Y-%m-%d %H:%M:%S")


async def topics_mastered_this_week(
    course_id: int, tenant_id: str = LOCAL_TENANT_ID, today: date | None = None
) -> list[str]:
    """Bu hafta kalıcı hatırlama eşiğine ulaşan KONU adları — LLM YOK (Plan #48).

    Ölçüt: kartın mevcut aralığı `MASTERY_INTERVAL_DAYS`i karşılıyor VE en son
    tekrarı (`reviewed_at`) bu hafta içinde. `card_reviews` yalnızca son durumu
    tutar (aralık geçmişi yok) — bu yüzden bir kart haftalar önce eşiği geçip bu
    hafta hiç tekrar edilmediyse sayılmaz; bu, kullanıcının o konuyu bu hafta
    fiilen tekrar ettiğini garanti eden kasıtlı bir tasarım seçimidir.

    Konu adı `flashcard_sets.cards_json[card_index]["topic"]`den okunur (bkz.
    services/flashcard_generator.py). Aynı konudaki birden çok kart tek girdiye
    indirgenir.
    """
    today = today or datetime.now(UTC).date()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, cards_json FROM flashcard_sets WHERE course_id = ? AND tenant_id = ?",
            (course_id, tenant_id),
        )
        sets = {row["id"]: json.loads(row["cards_json"] or "[]") for row in await cursor.fetchall()}
        if not sets:
            return []

        placeholders = ", ".join("?" * len(sets))
        cursor = await db.execute(
            "SELECT set_id, card_index FROM card_reviews "  # nosec B608 - araya giren metin sabit `?` yer tutucularıdır; değerler parametreyle geçer
            f"WHERE tenant_id = ? AND set_id IN ({placeholders}) "
            "AND interval_days >= ? AND reviewed_at >= ?",
            (tenant_id, *sets.keys(), MASTERY_INTERVAL_DAYS, _week_start_param(today)),
        )
        rows = list(await cursor.fetchall())
    finally:
        await db.close()

    topics: set[str] = set()
    for row in rows:
        cards = sets.get(row["set_id"], [])
        index = row["card_index"]
        if 0 <= index < len(cards):
            topic = str(cards[index].get("topic") or "").strip()
            if topic:
                topics.add(topic)
    return sorted(topics)
