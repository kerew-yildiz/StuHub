"""Alan-14 geçici tanı: Supabase Postgres pooler'a TCP erişimi (Windows'tan)."""
import socket
import time

HOST, PORT = "aws-0-eu-central-1.pooler.supabase.com", 5432
try:
    infos = socket.getaddrinfo(HOST, PORT, proto=socket.IPPROTO_TCP)
    print("dns:", sorted({i[4][0] for i in infos}))
except Exception as exc:
    print("dns ERR", exc)

for i in range(5):
    t = time.time()
    try:
        with socket.create_connection((HOST, PORT), timeout=10) as s:
            s.settimeout(5)
            # Postgres sunucusu bağlantıda ilk baytı istemciden bekler; sadece TCP'yi ölç.
            print(f"{i} TCP OK {round(time.time() - t, 2)}s peer={s.getpeername()[0]}")
    except Exception as exc:
        print(f"{i} TCP ERR {type(exc).__name__} {str(exc)[:80]} {round(time.time() - t, 2)}s")
    time.sleep(1)
