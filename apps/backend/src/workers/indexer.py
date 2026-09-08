"""Arka plan indeksleyici — bekleyen işleri işler (Faz 2.2).

Çok-instance güvenliği (yol haritası Aşama 0-10/0-11):

- Her process açılışta bir `WORKER_ID` üretir; claim ettiği işlere bunu yazar ve
  iş sürerken `heartbeat_at`'i tazeler.
- Kurtarma (`recover_stale_jobs`) yalnızca heartbeat'i bayatlamış işleri geri alır —
  başka bir instance'ın o an işlediği iş kuyruğa geri KONMAZ. Eskiden açılışta
  `status='processing'` olan her satır sahibine bakılmadan pending'e çevriliyordu;
  rolling deploy'da (eski + yeni instance bir arada) bu, aktif işlerin ikinci kez
  işlenmesine ve embedding/LLM maliyetinin iki katına çıkmasına yol açıyordu.
- Eşzamanlılık `settings.indexer_concurrency` ile sınırlıdır (backpressure).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from contextlib import suppress
from datetime import UTC, datetime

from ..config import settings
from ..db import get_db
from ..services.indexer import run_indexing_job

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0

# Bu process'in kimliği. PID tek başına yetmez (farklı makinelerde/konteynerlerde
# çakışır), bu yüzden rastgele bir sonek eklenir.
WORKER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

# `heartbeat_at` bu aralıkla tazelenir.
HEARTBEAT_INTERVAL_SECONDS = 15.0
# Heartbeat bu süredir güncellenmemişse iş "bayat" sayılır ve kurtarılır. Aralığın
# birkaç katı seçilir ki geçici bir yavaşlama işi yanlışlıkla kurtarılmasın.
STALE_AFTER_SECONDS = 90.0


def _now_param() -> datetime | str:
    """Zaman filtresi/yazma parametresi — SaaS/Postgres'te native `datetime`, SQLite'ta metin.

    asyncpg `TIMESTAMPTZ` kolonuyla karşılaştırılan parametrenin gerçek `datetime`
    olmasını şart koşar; SQLite tarafında `CURRENT_TIMESTAMP` 'YYYY-MM-DD HH:MM:SS'
    (UTC) yazdığı için aynı biçimde metin kullanılır (bkz. quota._month_start).
    """
    now = datetime.now(UTC)
    if settings.saas_mode:
        return now
    return now.strftime("%Y-%m-%d %H:%M:%S")


def _stale_cutoff_param() -> datetime | str:
    cutoff = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() - STALE_AFTER_SECONDS, tz=UTC
    )
    if settings.saas_mode:
        return cutoff
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


async def recover_stale_jobs() -> int:
    """Sahipsiz/bayat `processing` işleri pending'e döndürür; kurtarılan sayısını döner.

    Kurtarma ölçütü:
    - Bu process'in KENDİ önceki kimliğiyle kalmış işler (aynı konteyner yeniden
      başlamışsa kimlik değiştiği için bunlar da bayat gruba düşer), ve
    - `heartbeat_at` boş (eski sürümden kalma satırlar) ya da eşikten eski olanlar.

    Canlı bir worker'ın heartbeat'i taze olduğu sürece işine dokunulmaz.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE indexing_jobs SET status='pending', worker_id=NULL, "
            "updated_at=CURRENT_TIMESTAMP "
            "WHERE status='processing' "
            "AND (heartbeat_at IS NULL OR heartbeat_at < ?)",
            (_stale_cutoff_param(),),
        )
        await db.commit()
        recovered = cursor.rowcount or 0
    finally:
        await db.close()
    if recovered:
        logger.info("bayat indeksleme işi kurtarıldı: %d", recovered)
    return recovered


# Çalışan iş görevleri — hem eşzamanlılık sınırı hem de görevlerin canlı tutulması için.
# `asyncio.create_task`'ın dönüşü bir yerde tutulmazsa görev çöp toplayıcı tarafından
# iş ortasında toplanabilir (asyncio'nun belgelenmiş tuzağı); set bunu da engeller.
_running: set[asyncio.Task] = set()


def running_job_count() -> int:
    return len(_running)


async def _touch_heartbeat(job_id: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE indexing_jobs SET heartbeat_at = ? WHERE id = ? AND worker_id = ?",
            (_now_param(), job_id, WORKER_ID),
        )
        await db.commit()
    finally:
        await db.close()


async def _run_with_heartbeat(job_id: int, tenant_id: str) -> None:
    """İşi çalıştırır ve süresince `heartbeat_at`'i tazeler.

    Heartbeat ayrı bir görevdedir; iş bittiğinde (başarı ya da hata) iptal edilir.
    """

    async def beat() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                await _touch_heartbeat(job_id)
            except Exception:
                # Heartbeat yazılamazsa iş durmamalı; en kötü ihtimalle iş bayat
                # sayılıp başka bir worker tarafından tekrar alınır.
                logger.warning("heartbeat yazılamadı (iş %s)", job_id, exc_info=True)

    beater = asyncio.create_task(beat())
    try:
        await run_indexing_job(job_id, tenant_id)
    finally:
        beater.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beater


async def process_pending_jobs() -> int:
    """Bekleyen işleri atomik olarak claim edip arka plan görevi olarak başlatır.

    Aynı işin iki kez başlatılmaması için satır pending→processing geçişi WHERE ile korunur.

    Eşzamanlılık `settings.indexer_concurrency` ile sınırlıdır: bir turda yalnızca boş
    kapasite kadar iş claim edilir. Sınır olmadan 50 eşzamanlı yükleme 50 paralel
    indeksleme başlatıyordu — hepsi aynı thread havuzunda bge-m3 batch'i işlediği için
    bellek patlaması ve event loop açlığı oluyordu. Kapasite dolduğunda işler `pending`
    kalır (claim EDİLMEZ), böylece kuyrukta görünür ve restart'ta kaybolmazlar.
    """
    capacity = settings.indexer_concurrency - len(_running)
    if capacity <= 0:
        return 0

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, tenant_id FROM indexing_jobs WHERE status = 'pending' "
            "ORDER BY id LIMIT ?",
            (capacity,),
        )
        rows = await cursor.fetchall()
        started = 0
        for row in rows:
            # Claim ile birlikte sahiplik ve ilk heartbeat de yazılır: iş bu andan
            # itibaren "canlı" sayılır ve başka bir instance'ın kurtarmasına takılmaz.
            update = await db.execute(
                "UPDATE indexing_jobs SET status='processing', worker_id=?, "
                "heartbeat_at=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id = ? AND status = 'pending'",
                (WORKER_ID, _now_param(), row["id"]),
            )
            if update.rowcount == 1:
                await db.commit()
                task = asyncio.create_task(_run_with_heartbeat(row["id"], row["tenant_id"]))
                _running.add(task)
                task.add_done_callback(_running.discard)
                started += 1
        return started
    finally:
        await db.close()


async def worker_loop(stop_event: asyncio.Event) -> None:
    """Lifespan'de çalışan sürekli döngü: bekleyen işleri tarar, bayatları kurtarır."""
    since_recovery = 0.0
    while not stop_event.is_set():
        try:
            await process_pending_jobs()
            # Kurtarma periyodik olarak da çalışır (yalnızca açılışta değil): başka bir
            # instance çökerse işleri sonsuza dek 'processing' takılı kalmasın.
            since_recovery += POLL_INTERVAL_SECONDS
            if since_recovery >= STALE_AFTER_SECONDS:
                since_recovery = 0.0
                await recover_stale_jobs()
        except Exception:
            logger.exception("indexer worker hatası")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
