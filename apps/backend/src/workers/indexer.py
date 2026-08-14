"""Arka plan indeksleyici — bekleyen işleri işler (Faz 2.2)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from ..db import get_db
from ..services.indexer import run_indexing_job

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


async def recover_stale_jobs() -> int:
    """Yarım kalmış (processing) işleri pending'e döndürür (çökme kurtarma)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE indexing_jobs SET status='pending', updated_at=CURRENT_TIMESTAMP "
            "WHERE status='processing'"
        )
        await db.commit()
        return cursor.rowcount or 0
    finally:
        await db.close()


async def process_pending_jobs() -> int:
    """Bekleyen işleri atomik olarak claim edip arka plan görevi olarak başlatır.

    Aynı işin iki kez başlatılmaması için satır pending→processing geçişi WHERE ile korunur.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM indexing_jobs WHERE status = 'pending' ORDER BY id"
        )
        rows = await cursor.fetchall()
        started = 0
        for row in rows:
            update = await db.execute(
                "UPDATE indexing_jobs SET status='processing', updated_at=CURRENT_TIMESTAMP "
                "WHERE id = ? AND status = 'pending'",
                (row["id"],),
            )
            if update.rowcount == 1:
                await db.commit()
                asyncio.create_task(run_indexing_job(row["id"]))
                started += 1
        return started
    finally:
        await db.close()


async def worker_loop(stop_event: asyncio.Event) -> None:
    """Lifespan'de çalışan sürekli döngü: bekleyen işleri tarar."""
    while not stop_event.is_set():
        try:
            await process_pending_jobs()
        except Exception:
            logger.exception("indexer worker hatası")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
