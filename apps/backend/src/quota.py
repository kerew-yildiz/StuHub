"""SaaS kota bekçiliği — plan başına aylık LLM üretim sınırı (KARAR-SAAS-GECISI.md soru 3).

Yerel modda (`settings.saas_mode` False) kota yok: bugünkü sınırsız davranış korunur.
SaaS modunda her üretim ucu (not/quiz/flashcard/overall/essay/chat) çağrıdan ÖNCE
`enforce_quota` dependency'sini kullanır: kiracının planı `profiles.plan` → limiti
`plans.monthly_quota` (NULL = sınırsız) → bu takvim ayındaki `generation_logs` satır
sayısı ile karşılaştırılır. Aşıldıysa 402 Payment Required döner (yükseltme mesajı).

Sayaç `generation_logs`'a dayanır — her LLM çağrısı zaten `llm_service.log_generation`
ile buraya işleniyor (bkz. services/llm_service.py), kota için ayrı bir sayaç
tutulmuyor.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends

from .auth import LOCAL_TENANT_ID, AuthError, get_tenant_id
from .config import settings
from .db import get_db


class QuotaExceededError(AuthError):
    def __init__(self, plan: str, limit: int) -> None:
        super().__init__(
            detail=(
                f"Bu ayki '{plan}' plan kotanız ({limit} üretim) doldu. "
                "Devam etmek için planınızı yükseltin."
            ),
            status_code=402,
        )


def _month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def _plan_and_quota(tenant_id: str) -> tuple[str, int | None]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT p.plan, pl.monthly_quota FROM profiles p "
            "JOIN plans pl ON pl.name = p.plan WHERE p.id = ?",
            (tenant_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    if row is None:
        # Profil henüz açılmamış (get_tenant_id her zaman auto-provision eder,
        # bu yüzden pratikte oluşmaz) — en kısıtlı varsayılana düş.
        return "free", 0
    data = dict(row)
    return data["plan"], data["monthly_quota"]


async def _usage_this_month(tenant_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM generation_logs WHERE tenant_id = ? AND created_at >= ?",
            (tenant_id, _month_start_iso()),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return dict(row)["n"] if row else 0


async def enforce_quota(tenant_id: str = Depends(get_tenant_id)) -> str:
    """Kota aşılmışsa 402 fırlatır; aksi halde `tenant_id`'yi olduğu gibi döner
    (üretim router'larında `tenant_id` parametresi yerine doğrudan kullanılabilir)."""
    if not settings.saas_mode or tenant_id == LOCAL_TENANT_ID:
        return tenant_id
    plan, limit = await _plan_and_quota(tenant_id)
    if limit is None:
        return tenant_id
    used = await _usage_this_month(tenant_id)
    if used >= limit:
        raise QuotaExceededError(plan, limit)
    return tenant_id
