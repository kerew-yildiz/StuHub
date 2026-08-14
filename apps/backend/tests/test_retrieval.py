"""Hibrit retrieval testleri (Faz 3.1) — LanceDB gerçek, embedding mock'lu."""

import pytest

from src.config import settings
from src.services import embed_service, vector_store
from src.services.retrieval import hybrid_search

DIM = 8


@pytest.fixture(autouse=True)
def _mock_embed(monkeypatch):
    # deterministik vektörler: metindeki "a" sayısına göre ilk bileşen
    def fake_embed(texts):
        vectors = []
        for text in texts:
            vec = [0.0] * DIM
            vec[0] = text.lower().count("a") / max(len(text), 1)
            vec[1] = 1.0
            vectors.append(vec)
        return vectors

    monkeypatch.setattr(embed_service, "embed_texts", fake_embed)


def _chunks(course_id: int, material_id: int):
    return [
        {
            "chunk_id": f"chk_{material_id}_1_1",
            "course_id": course_id,
            "material_id": material_id,
            "page": 1,
            "slide": None,
            "text": "Bağlı listeler, düğümler ve işaretçiler ile çalışır.",
            "vector": [0.5] * DIM,
        },
        {
            "chunk_id": f"chk_{material_id}_2_1",
            "course_id": course_id,
            "material_id": material_id,
            "page": 2,
            "slide": None,
            "text": "Sıralama algoritmaları karşılaştırma yapar.",
            "vector": [0.2] * DIM,
        },
    ]


async def test_hybrid_search_returns_ranked_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    course_id, material_id = 1, 7
    vector_store.upsert_chunks(course_id, _chunks(course_id, material_id))

    results = hybrid_search(course_id, "bağlı listeler", ["düğüm", "işaretçi"])
    assert len(results) == 2
    assert all("material_id" in r for r in results)
    # keyword boost: 1. chunk "düğüm"+"işaretçi" içeriyor
    assert results[0]["chunk_id"] == f"chk_{material_id}_1_1"
    assert results[0]["score"] > results[1]["score"]


async def test_hybrid_search_empty_when_no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert hybrid_search(99, "soru") == []
