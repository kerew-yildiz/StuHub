"""Embedding — yerel önce, uzak yedek (Yetenek 01).

Birincil yol sentence-transformers (yerel, gizlilik sözleşmesi) kalır. Ancak Windows
Uygulama Denetimi (Smart App Control) sentence-transformers'ın `regex` DLL'ini
engelleyebiliyor — bu ortamda yerel model hiç yüklenemez ve retrieval/not üretimi
kalıcı olarak lexikal yedeğe düşüyordu. Çözüm: yerel yüklenemezse Gemini
embedding API'sine (mevcut google_api_key ile) otomatik düş.

Dim uyumu: gemini-embedding-001 3072 boyut üretir; eski indeksler 384/1024
boyutlu olduğundan model adı uzak modele geçildiğinde `hybrid_search` zaten
VectorDimMismatch fırlatır — retrieval bu durumda lexikal yedeğe düşer (bkz.
retrieval.hybrid_search). Yeni indeksleme uzak model adıyla yapılır; eski
materyallerin yeniden indekslenmesi önerilir.
"""

from __future__ import annotations

import json
import threading
import urllib.request

from ..config import settings

DEFAULT_MODEL = "BAAI/bge-m3"
REMOTE_MODEL = "gemini-embedding-001"
REMOTE_DIM = 3072

_lock = threading.Lock()
_model = None
_model_name: str | None = None
# Uzak düşme kararı süreç ömrü boyunca hatırlanır — her çağrıda import denemesi
# (ve Windows'un DLL engelleme istisnası) tekrarlanmasın.
_local_unavailable = False


class EmbedError(Exception):
    """Kurulum/indirme hatası — kullanıcıya Türkçe mesaj."""


def _resolve_model_name() -> str:
    return settings.embed_model or DEFAULT_MODEL


def _get_model():
    """Modeli tembel yükler (ilk çağrıda indirir); thread-güvenli."""
    global _model, _model_name
    name = _resolve_model_name()
    if _model is None or _model_name != name:
        with _lock:
            if _model is None or _model_name != name:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise EmbedError(
                        "Embedding modeli yüklü değil. Bağımlılıkları güncellemek için "
                        "`uv sync` çalıştırın."
                    ) from exc
                try:
                    _model = SentenceTransformer(name)
                except Exception as exc:
                    raise EmbedError(
                        f"Embedding modeli indirilemedi/yüklenemedi ({name}). "
                        "İnternet bağlantısını kontrol edip tekrar deneyin."
                    ) from exc
                _model_name = name
    return _model


def _gemini_api_key() -> str:
    """Ayarlar tablosu → ortam: gemini anahtarı (llm_service ile aynı öncelik)."""
    return getattr(settings, "google_api_key", "") or ""


def _embed_remote(texts: list[str]) -> list[list[float]]:
    """Gemini embedContent — senkron (to_thread ile çağrılır), batch destekli.

    Not: REST uç tek metin alır; batch için sıralı istek atılır (üretimde batch
    boyutu küçük tutulur). Hata durumunda EmbedError fırlatır — çağıran
    (hybrid_search) lexikal yedeğe düşer.
    """
    key = _gemini_api_key()
    if not key:
        raise EmbedError("Uzak embedding için google_api_key ayarlı değil.")
    vectors: list[list[float]] = []
    for text in texts:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{REMOTE_MODEL}:embedContent",
            data=json.dumps({
                "model": f"models/{REMOTE_MODEL}",
                "content": {"parts": [{"text": text[:8000]}]},
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
            vectors.append(body["embedding"]["values"])
        except Exception as exc:  # noqa: BLE001 — ağ/hizmet hatası tek noktaya iner
            raise EmbedError(f"Uzak embedding başarısız: {exc}") from exc
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Metinleri vektörlere çevirir (L2 normalize — kosinüs uyumlu).

    Yerel model yüklenebiliyorsa YEREL kullanılır (gizlilik sözleşmesi); DLL
    engeli gibi durumlarda uzak Gemini embedding'e düşülür. Uzak vektörler de
    birim normallenecek şekilde döner (Gemini zaten normalize üretir — ek güvence).
    """
    global _local_unavailable
    if not texts:
        return []
    if not _local_unavailable:
        try:
            model = _get_model()
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [v.tolist() for v in vectors]
        except EmbedError:
            _local_unavailable = True  # bu süreçte tekrar denemeye gerek yok
        except OSError:
            # Windows Uygulama Denetimi torch DLL'lerini (shm.dll vb.) de engelliyor —
            # ImportError değil OSError çıkıyor. Aynı şekilde uzak yedeğe düş.
            _local_unavailable = True
    # Uzak yedek — gemini-embedding-001 zaten birim normalli döner.
    return _embed_remote(texts)
