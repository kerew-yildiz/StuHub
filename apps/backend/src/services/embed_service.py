"""Yerel embedding — sentence-transformers + bge-m3 (Yetenek 01).

Embedding kesinlikle yereldir: uzak embedding API'sine (HF Inference dahil) düşülmez
(gizlilik sözleşmesi, yol haritası Bölüm 8). Model yüklenemezse iş failed olur.
"""

from __future__ import annotations

import threading

from ..config import settings

DEFAULT_MODEL = "BAAI/bge-m3"

_lock = threading.Lock()
_model = None
_model_name: str | None = None


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


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Metinleri vektörlere çevirir (L2 normalize — kosinüs uyumlu)."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
