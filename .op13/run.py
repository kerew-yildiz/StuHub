"""Op13 indeksleme ölçüm koşucusu (test amaçlı, repoya commit edilmez)."""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("OP13_BASE", "http://172.25.176.1:8010")
TOKEN = open("/tmp/op13_token").read().strip()
COURSE = int(os.environ.get("OP13_COURSE", "8"))


def req(method, path, data=None, ctype=None):
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + TOKEN)
    if ctype:
        r.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def multipart(path, field_type):
    boundary = uuid.uuid4().hex
    fname = os.path.basename(path)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{field_type}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n".encode()
    )
    parts.append(open(path, "rb").read())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def jobs():
    return req("GET", f"/api/courses/{COURSE}/indexing-jobs")[1]


def upload_and_time(pdf, label, poll=0.25, timeout=900):
    body, ctype = multipart(pdf, "textbook")
    t0 = time.time()
    status, mat = req("POST", f"/api/courses/{COURSE}/materials", body, ctype)
    t_upload = time.time() - t0
    if status != 201:
        print(json.dumps({"label": label, "error": mat, "http": status}))
        return None
    mid = mat["id"]
    samples = []
    t_first_proc = None
    done = None
    while time.time() - t0 < timeout:
        js = jobs()
        job = next((j for j in js if j["material_id"] == mid), None)
        if job:
            el = round(time.time() - t0, 3)
            if not samples or samples[-1][1:] != (job["status"], job["progress"]):
                samples.append((el, job["status"], job["progress"]))
            if job["status"] == "processing" and t_first_proc is None:
                t_first_proc = el
            if job["status"] in ("done", "failed"):
                done = job
                break
        time.sleep(poll)
    total = round(time.time() - t0, 3)
    _, m2 = req("GET", f"/api/materials/{mid}")
    out = {
        "label": label,
        "material_id": mid,
        "job_id": done["id"] if done else None,
        "http": status,
        "upload_request_s": round(t_upload, 3),
        "total_s": total,
        "status": done["status"] if done else "timeout",
        "error": done.get("error") if done else None,
        "page_count": m2.get("page_count") if isinstance(m2, dict) else None,
        "progress_samples": samples,
    }
    print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        pdf, label = arg.split("=", 1)
        upload_and_time(pdf, label)
