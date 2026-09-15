"""Alan-14 K7: yarıda kesilen yükleme — GERÇEK soket, gerçek uvicorn sunucusu.

Kendi uvicorn'unu 127.0.0.1:8099'da yerel (SQLite) modda ayağa kaldırır, multipart
gövdesinin ortasında TCP bağlantısını kapatır ve diskte/DB'de artık kalıp kalmadığını
ölçer. Kullanıcının 8000/5180 portlarına dokunmaz.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

DATA = Path(tempfile.mkdtemp(prefix="a14k7_"))
os.environ["STUHUB_DATA_DIR"] = str(DATA)
os.environ["DATABASE_URL"] = ""

import uvicorn  # noqa: E402

from src.config import settings  # noqa: E402
from src.main import app  # noqa: E402

settings.database_url = ""
settings.data_dir = DATA

PORT = 8099
config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
server = uvicorn.Server(config)
threading.Thread(target=server.run, daemon=True).start()
for _ in range(100):
    if server.started:
        break
    time.sleep(0.1)
print("uvicorn hazır:", server.started)

import httpx  # noqa: E402

base = f"http://127.0.0.1:{PORT}"
term = httpx.post(f"{base}/api/terms", json={"name": "[TEST] A14 K7"}, timeout=60).json()["id"]
course = httpx.post(
    f"{base}/api/terms/{term}/courses", json={"name": "[TEST] A14 K7"}, timeout=60
).json()["id"]
print("term", term, "course", course)


def sayim() -> tuple[list, int]:
    d = settings.materials_dir / str(course)
    disk = sorted((p.name, p.stat().st_size) for p in d.iterdir() if p.is_file()) if d.exists() else []
    con = sqlite3.connect(settings.db_path)
    n = con.execute("SELECT COUNT(*) FROM materials WHERE course_id = ?", (course,)).fetchone()[0]
    con.close()
    return disk, n


print("önce:", sayim())

# --- multipart gövdesinin ortasında bağlantıyı kes
boundary = "----a14k7"
head = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="type"\r\n\r\ntextbook\r\n'
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="yarim.pdf"\r\n'
    "Content-Type: application/pdf\r\n\r\n"
).encode()
# Content-Length 20 MB ilan edilir ama yalnızca ~4 MB gönderilip soket kapatılır.
ilan = len(head) + 20 * 1024 * 1024 + len(f"\r\n--{boundary}--\r\n".encode())
istek = (
    f"POST /api/courses/{course}/materials HTTP/1.1\r\n"
    f"Host: 127.0.0.1:{PORT}\r\n"
    f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
    f"Content-Length: {ilan}\r\n"
    "Connection: close\r\n\r\n"
).encode()

s = socket.create_connection(("127.0.0.1", PORT), timeout=20)
s.sendall(istek + head)
gonderilen = 0
blok = b"%PDF-1.4\n" + b"K" * (256 * 1024 - 9)
while gonderilen < 4 * 1024 * 1024:
    s.sendall(blok)
    gonderilen += len(blok)
print(f"gövdenin {gonderilen} baytı gönderildi (ilan edilen {ilan}), soket şimdi kapatılıyor")
s.close()  # bağlantı yarıda kopar

time.sleep(3)
disk, n = sayim()
print("sonra:", (disk, n))
yarim = [x for x in disk if "yarim" in x[0]]
print("ARTIK dosya:", yarim)
print("ARTIK DB satırı sayısı (beklenen 0):", n)

h = httpx.get(f"{base}/health", timeout=30)
print("kopuştan sonra /health:", h.status_code, h.text)

# Sunucu hâlâ yeni yükleme kabul ediyor mu?
r = httpx.post(
    f"{base}/api/courses/{course}/materials",
    files={"file": ("saglam.pdf", b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n", "application/pdf")},
    data={"type": "textbook"},
    timeout=120,
)
print("kopuş sonrası yeni yükleme:", r.status_code, r.text[:200])
server.should_exit = True
time.sleep(1)
