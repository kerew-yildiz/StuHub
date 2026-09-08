"""Feed havuzu doldurucu — son 24 saatte kullanılan derslerin havuzunu hedefte tutar.

`workers/indexer` ile aynı kalıp: lifespan'de tek görev olarak koşan sonsuz döngü,
`stop_event` ile durur. Router her GET'te de doldurma tetikler; bu döngü kullanıcı
istek göndermediği aralıklarda (ör. kullanıcı feed'i kapattı, havuz yarım kaldı)
havuzu tamamlar, böylece bir sonraki açılış anında hazır soru bulur.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from ..config import settings
from ..services import feed_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30.0
ACTIVE_WINDOW_HOURS = 24

# Turlar arasında ilerleyen imleç — her tur listenin farklı bir diliminden başlar ki
# sınır konduğunda listenin sonundaki dersler hiç sıra alamamazlık etmesin.
_cursor = 0


async def topup_active_courses() -> int:
    """Etkin derslerin havuzunu `TARGET_POOL`'a yaklaştırır; eklenen soru sayısını döner.

    Bir turda en fazla `settings.feed_topup_batch` ders işlenir ve tur, kaldığı yerden
    değil her seferinde listenin başından değil — `_cursor` ile sırayla ilerler; böylece
    hiçbir ders açlığa düşmez. Sınır olmadan döngü tüm aktif (kiracı, ders) çiftlerini
    sırayla geziyordu: tek bir yavaş LLM partisi (dakikalarca sürebilir) tüm sırayı
    bloklar, birkaç yüz aktif derste bir tur hiç tamamlanmazdı.
    """
    courses = await feed_service.active_course_ids(ACTIVE_WINDOW_HOURS)
    if not courses:
        return 0

    global _cursor
    batch = max(1, settings.feed_topup_batch)
    start = _cursor % len(courses)
    window = (courses + courses)[start : start + batch]
    _cursor = (start + batch) % len(courses)

    added = 0
    for tenant_id, course_id in window:
        if await feed_service.pool_size(course_id, tenant_id) >= feed_service.TARGET_POOL:
            continue
        added += await feed_service.ensure_pool(course_id, tenant_id)
    return added


async def worker_loop(stop_event: asyncio.Event) -> None:
    """Lifespan'de çalışan sürekli döngü (30 sn)."""
    while not stop_event.is_set():
        try:
            await topup_active_courses()
        except Exception:
            logger.exception("feed_topup worker hatası")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
