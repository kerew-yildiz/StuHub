"""Tek seferlik teşhis: Supabase bağlantısı açılabiliyor mu, kaç bağlantı açık.
Test kampanyası sırasında oluşturuldu, sonra silinecek."""
import asyncio
import time

import asyncpg

from src.config import settings


async def main() -> None:
    t0 = time.time()
    try:
        conn = await asyncio.wait_for(asyncpg.connect(settings.database_url), timeout=25)
    except Exception as exc:  # noqa: BLE001 - teşhis scripti
        print("BAGLANTI HATASI:", type(exc).__name__, str(exc)[:200], round(time.time() - t0, 2), "sn")
        return
    print("BAGLANTI OK:", round(time.time() - t0, 2), "sn")
    try:
        print("select 1 ->", await conn.fetchval("select 1"))
        toplam = await conn.fetchval("select count(*) from pg_stat_activity")
        benim = await conn.fetchval(
            "select count(*) from pg_stat_activity where usename = current_user"
        )
        print("pg_stat_activity toplam:", toplam, "| bu kullanici:", benim)
    finally:
        await conn.close()


asyncio.run(main())
