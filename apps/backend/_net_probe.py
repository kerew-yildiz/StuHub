"""Tek seferlik teşhis: Windows Python sürecinden Supabase'e HTTPS ve Postgres erişimi.
Test kampanyası sırasında oluşturuldu, sonra silinecek."""
import asyncio
import time
import urllib.request

from src.config import settings

JWKS = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json" if getattr(settings, "supabase_url", "") else ""


def urllib_testi(url: str) -> None:
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            print(f"urllib {url[:60]}... -> {r.status} ({time.time() - t0:.2f} sn)")
    except Exception as exc:  # noqa: BLE001 - teşhis
        print(f"urllib HATA {type(exc).__name__}: {str(exc)[:120]} ({time.time() - t0:.2f} sn)")


async def pg_testi() -> None:
    import asyncpg

    t0 = time.time()
    try:
        conn = await asyncio.wait_for(asyncpg.connect(settings.database_url), timeout=20)
        print(f"asyncpg BAGLANDI ({time.time() - t0:.2f} sn), select 1 ->", await conn.fetchval("select 1"))
        await conn.close()
    except Exception as exc:  # noqa: BLE001 - teşhis
        print(f"asyncpg HATA {type(exc).__name__}: {str(exc)[:120]} ({time.time() - t0:.2f} sn)")


urllib_testi("https://www.google.com")
if JWKS:
    urllib_testi(JWKS)
else:
    print("supabase_url ayarı yok, JWKS testi atlandı")
asyncio.run(pg_testi())
