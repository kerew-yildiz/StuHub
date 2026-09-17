"""Çalışma süresi (study-time) servisi — chapter heartbeat kaydı + ders/chapter toplamları.

Süre kaynağı: kullanıcı bir chapter görünümündeyken (sekme görünür + son 90 sn içinde
etkileşim) frontend 45 sn'de bir heartbeat gönderir. Her heartbeat, `duration_sec` =
geçen aralık olan bir `study_sessions` satırıdır; `chapter_id` dolu, `course_id` ders
bağlamını taşır.

Idempotentlik: `session_id` (heartbeat UUID'si) bazında — ağ hatasında aynı heartbeat
tekrar gönderilirse mevcut satır döner, süre ikinci kez eklenmez. Cihaz beklenmedik
kapandığında en fazla son (yarım) aralık kaybolur.

Ders ve chapter toplamı `study_totals` ile tek sorguda (GROUP BY chapter_id) okunur:
GROUP BY'ın NULL grubu ders bazlı (chapter'sız) kayıtları temsil eder ve ders toplamına
dahil edilir.
"""

from __future__ import annotations

from typing import Any

# Tek heartbeat'in üst sınırı. Tipik aralık 45 sn; üst sınır sekme askıya alınıp
# geri döndüğünde (aralık uzasa da) günlük toplama absürt değer yazılmasını engeller.
MAX_HEARTBEAT_SEC = 300


async def record_study_heartbeat(
    db: Any,
    tenant_id: str,
    course_id: int,
    chapter_id: int,
    session_id: str,
    duration_sec: int,
) -> dict:
    """Chapter heartbeat'ini kaydeder; `session_id` tekrarında mevcut satırı döner."""
    cursor = await db.execute(
        "SELECT id, course_id, chapter_id, session_id, duration_sec, created_at "
        "FROM study_sessions WHERE tenant_id = ? AND session_id = ?",
        (tenant_id, session_id),
    )
    existing = await cursor.fetchone()
    if existing is not None:
        return dict(existing)

    cursor = await db.execute(
        "INSERT INTO study_sessions "
        "(tenant_id, course_id, chapter_id, session_id, duration_sec) "
        "VALUES (?, ?, ?, ?, ?)",
        (tenant_id, course_id, chapter_id, session_id, duration_sec),
    )
    await db.commit()
    row_id = cursor.lastrowid
    if row_id is None:
        raise RuntimeError("çalışma süresi kaydı oluşturulamadı")
    cursor = await db.execute(
        "SELECT id, course_id, chapter_id, session_id, duration_sec, created_at "
        "FROM study_sessions WHERE id = ?",
        (row_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("beklenen çalışma süresi satırı bulunamadı")
    return dict(row)


async def study_totals(db: Any, tenant_id: str, course_id: int) -> tuple[int, dict[int, int]]:
    """(ders toplamı, {chapter_id: toplam}) — tek GROUP BY sorgusu.

    NULL chapter grubu (chapter dışı/ders bazlı kayıtlar) yalnızca ders toplamına girer.
    """
    cursor = await db.execute(
        "SELECT chapter_id, COALESCE(SUM(duration_sec), 0) AS total FROM study_sessions "
        "WHERE tenant_id = ? AND course_id = ? GROUP BY chapter_id",
        (tenant_id, course_id),
    )
    chapters: dict[int, int] = {}
    total = 0
    for row in await cursor.fetchall():
        seconds = int(row["total"] or 0)
        total += seconds
        chapter_id = row["chapter_id"]
        if chapter_id is not None:
            chapters[int(chapter_id)] = seconds
    return total, chapters
