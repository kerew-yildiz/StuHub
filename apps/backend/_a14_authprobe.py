"""Alan-14 geçici tanı betiği: backend venv'inde JWT doğrulama zincirini adım adım dener."""
import sys, time, traceback
sys.path.insert(0, ".")
from src.config import settings
from src import auth

tok = open(sys.argv[1], encoding="utf-8").read().strip()
print("saas_mode", settings.saas_mode)
print("supabase_url set:", bool(settings.supabase_url), "hs256 secret set:", bool(settings.supabase_jwt_secret))
t = time.time()
try:
    c = auth._get_jwk_client()
    print("jwk client:", c is not None, round(time.time() - t, 2), "s")
    t = time.time()
    k = c.get_signing_key_from_jwt(tok)
    print("signing key ok", round(time.time() - t, 2), "s")
    t = time.time()
    p = auth._decode_with_jwks(tok, c)
    print("decode ok", round(time.time() - t, 2), "s sub=", p.get("sub"))
except Exception:
    traceback.print_exc()
print("total elapsed check done")
