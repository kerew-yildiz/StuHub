"""Essay grader testleri (Yetenek 05) — LLM mock'lu."""

import pytest

from src.services import essay_grader, llm_service

VALID_GRADE = {
    "score": 7,
    "correct": ["doğru nokta"],
    "missing": ["eksik nokta"],
    "incorrect": ["yok"],
    "unnecessary": ["yok"],
    "explanation": "Puan gerekçesi.",
    "ideal_answer": "İdeal cevap [1].",
    "confidence": 0.9,
}


def _mock_chat_json(monkeypatch, responses):
    calls = {"count": 0}

    async def fake(messages, **kwargs):
        calls["count"] += 1
        if callable(responses):
            return responses(calls["count"])
        return responses[min(calls["count"] - 1, len(responses) - 1)]

    monkeypatch.setattr(llm_service, "chat_json", fake)
    return calls


async def test_grade_valid(monkeypatch):
    calls = _mock_chat_json(monkeypatch, [VALID_GRADE])
    result = await essay_grader.grade_essay(
        question="Soru",
        answer_key={"points": ["nokta"]},
        numbered_sources="[1] kaynak",
        user_answer="Kullanıcı cevabı.",
        course_id=1,
    )
    assert result["score"] == 7
    assert calls["count"] == 1


async def test_grade_empty_answer_is_deterministic(monkeypatch):
    # boş cevapta LLM ÇAĞRILMAZ
    calls = _mock_chat_json(monkeypatch, [])
    result = await essay_grader.grade_essay(
        question="Soru",
        answer_key={"points": ["nokta a", "nokta b"]},
        numbered_sources="[1] kaynak",
        user_answer="   ",
        course_id=1,
    )
    assert result["score"] == 0
    assert result["missing"] == ["nokta a", "nokta b"]
    assert calls["count"] == 0


async def test_grade_low_confidence_regrades(monkeypatch):
    low = dict(VALID_GRADE, confidence=0.2)
    calls = _mock_chat_json(monkeypatch, [low, VALID_GRADE])
    result = await essay_grader.grade_essay(
        question="Soru",
        answer_key={"points": ["nokta"]},
        numbered_sources="[1] kaynak",
        user_answer="Cevap.",
        course_id=1,
    )
    assert result["score"] == 7
    assert calls["count"] == 2


async def test_grade_invalid_output_fails(monkeypatch):
    bad = {"score": 99, "correct": []}
    _mock_chat_json(monkeypatch, [bad, bad])
    with pytest.raises(essay_grader.EssayGradeError):
        await essay_grader.grade_essay(
            question="Soru",
            answer_key={"points": ["nokta"]},
            numbered_sources="[1] kaynak",
            user_answer="Cevap.",
            course_id=1,
        )
