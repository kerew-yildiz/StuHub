"""Konuşarak tekrar — transkript ↔ not konu anahtar kelime örtüşmesi (Plan #47).

LLM YOK: kapsanan/atlanan konular kelime-sınırlı, büyük/küçük harf duyarsız alt-dize
eşleşmesiyle bulunur (bkz. `guide_service._term_pattern` ile aynı desen).
"""

from __future__ import annotations

import re


def _term_pattern(term: str) -> re.Pattern[str]:
    """Terimi kelime sınırlarıyla, büyük/küçük harf duyarsız arayan desen."""
    return re.compile(rf"(?<!\w){re.escape(term.casefold())}(?!\w)")


def _contains_term(haystack: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False
    return _term_pattern(term).search(haystack) is not None


def compare_transcript(transcript: str, topics_meta: list[dict]) -> tuple[list[str], list[str]]:
    """(kapsanan konular, atlanan konular) sırasıyla notun `topics_json`'ına göre.

    Bir konu, adı ya da anahtar kelimelerinden (`topics_json[i]["keywords"]`) en az
    biri transkriptte geçiyorsa "kapsanan" sayılır; giriş sırası korunur.
    """
    normalized = transcript.casefold()
    covered: list[str] = []
    missed: list[str] = []
    for meta in topics_meta:
        name = str(meta.get("topic") or "").strip()
        if not name:
            continue
        terms = [name, *(str(k) for k in meta.get("keywords", []) if k)]
        if any(_contains_term(normalized, term) for term in terms):
            covered.append(name)
        else:
            missed.append(name)
    return covered, missed
