"""Sınav sonrası muhasebe — tek cümlelik LLM özeti (Plan #44).

Form + rapor tamamen deterministik (router katmanında); LLM yalnızca kaçırılan soru/sebep
dağılımından tek cümlelik çalışma tavsiyesi üretmek için burada kullanılır.
"""

from __future__ import annotations

from ..auth import LOCAL_TENANT_ID
from ..config import settings
from ..prompts.common import dil_talimati
from ..prompts.postmortem_prompts import POSTMORTEM_SUMMARY_PROMPT
from . import llm_service

ITEM_CHARS = 200
MAX_ITEMS_IN_PROMPT = 40


class PostmortemSummaryError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


async def summarize_postmortem(
    *,
    exam_title: str,
    items: list[dict],
    course_id: int,
    tenant_id: str = LOCAL_TENANT_ID,
) -> str:
    """Kaçırılan soru + sebep listesinden tek cümlelik Türkçe çalışma tavsiyesi üretir."""
    lines = "\n".join(
        f"- {item['question'][:ITEM_CHARS]} → {item['reason']}"
        for item in items[:MAX_ITEMS_IN_PROMPT]
    )
    prompt = POSTMORTEM_SUMMARY_PROMPT.format(
        exam_title=exam_title[:200],
        items=lines,
        dil_talimati=dil_talimati(settings.not_dili),
    )
    data = await llm_service.chat_json(
        [{"role": "user", "content": prompt}],
        kind="exam_postmortem",
        tenant_id=tenant_id,
        course_id=course_id,
    )
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise PostmortemSummaryError("Özet üretilemedi. Lütfen tekrar deneyin.")
    return summary.strip()
