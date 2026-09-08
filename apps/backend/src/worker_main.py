"""Ayrı worker process'i — HTTP sunucusu olmadan arka plan işçilerini çalıştırır.

`STUHUB_ROLE=worker` ile başlatılan konteynerin giriş noktası (bkz. docker-entrypoint.sh).
API ile aynı imajı kullanır; farkı, uvicorn yerine yalnızca işçi döngülerini çalıştırması.

Ayrı bir worker servisi çalıştırıldığında API tarafındaki işçiler `STUHUB_RUN_WORKERS=false`
ile kapatılmalıdır — aksi halde ikisi de kuyruğu tarar. Bu güvenlidir (claim atomiktir ve
`worker_id`/heartbeat ile korunur) ama gereksiz veritabanı yükü yaratır.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from .db import init_db
from .workers.feed_topup import worker_loop as feed_topup_loop
from .workers.indexer import recover_stale_jobs, worker_loop

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await init_db()
    await recover_stale_jobs()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    # SIGTERM: Railway deploy/scale sırasında konteyneri böyle durdurur — işçiler
    # döngüyü temiz kapatsın ki yarım kalan iş heartbeat'i bayatlayıp kurtarılabilsin.
    for sig in (signal.SIGTERM, signal.SIGINT):
        with __import__("contextlib").suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    logger.info("StuHub worker başladı")
    tasks = [
        asyncio.create_task(worker_loop(stop_event)),
        asyncio.create_task(feed_topup_loop(stop_event)),
    ]
    await stop_event.wait()
    logger.info("StuHub worker durduruluyor")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
