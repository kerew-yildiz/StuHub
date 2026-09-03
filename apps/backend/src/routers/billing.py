"""Lemon Squeezy abonelik webhook'u — plan yükseltme/indirme (KARAR-SAAS-GECISI.md soru 3).

Yalnızca SaaS modunda (`settings.saas_mode`) anlamlıdır; yerel modda 404 döner
(çağrılacak bir Lemon Squeezy mağazası yok). İmza `LEMONSQUEEZY_WEBHOOK_SECRET`
ile HMAC-SHA256 doğrulanır (Lemon Squeezy dokümantasyonu: `X-Signature` başlığı,
ham istek gövdesi üzerinde hesaplanır — bu yüzden Pydantic modeli değil, ham
`Request.body()` kullanılır).

Karşılanan olaylar (`meta.event_name`):
- `subscription_created` / `subscription_updated`: `subscriptions` upsert edilir,
  `profiles.plan` `plans.lemonsqueezy_variant_id` eşlemesiyle güncellenir.
- `subscription_cancelled` / `subscription_expired`: kiracı `free` plana düşürülür.

Diğer olaylar (ör. `order_created`) yok sayılır — 200 döner ki Lemon Squeezy
yeniden denemesin.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request

from ..config import settings
from ..db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

_DOWNGRADE_EVENTS = {"subscription_cancelled", "subscription_expired"}
_UPSERT_EVENTS = {"subscription_created", "subscription_updated"}


def _verify_signature(raw_body: bytes, signature: str | None) -> bool:
    if not settings.lemonsqueezy_webhook_secret or not signature:
        return False
    digest = hmac.new(
        settings.lemonsqueezy_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


async def _plan_for_variant(variant_id: str | None) -> str:
    if not variant_id:
        return "free"
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT name FROM plans WHERE lemonsqueezy_variant_id = ?", (str(variant_id),)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return dict(row)["name"] if row else "free"


async def _apply_subscription(tenant_id: str, attrs: dict, subscription_id: str) -> None:
    plan = await _plan_for_variant(attrs.get("variant_id"))
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO subscriptions "
            "(tenant_id, lemonsqueezy_subscription_id, lemonsqueezy_customer_id, plan, status, "
            "current_period_end) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (lemonsqueezy_subscription_id) DO UPDATE SET "
            "plan = excluded.plan, status = excluded.status, "
            "current_period_end = excluded.current_period_end, updated_at = now()",
            (
                tenant_id,
                subscription_id,
                str(attrs.get("customer_id", "")),
                plan,
                attrs.get("status", "active"),
                attrs.get("renews_at"),
            ),
        )
        await db.execute("UPDATE profiles SET plan = ? WHERE id = ?", (plan, tenant_id))
        await db.commit()
    finally:
        await db.close()


async def _downgrade(subscription_id: str) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT tenant_id FROM subscriptions WHERE lemonsqueezy_subscription_id = ?",
            (subscription_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return
        tenant_id = dict(row)["tenant_id"]
        await db.execute(
            "UPDATE subscriptions SET status = 'expired', updated_at = now() "
            "WHERE lemonsqueezy_subscription_id = ?",
            (subscription_id,),
        )
        await db.execute("UPDATE profiles SET plan = 'free' WHERE id = ?", (tenant_id,))
        await db.commit()
    finally:
        await db.close()


@router.post("/webhook", status_code=200)
async def lemonsqueezy_webhook(request: Request) -> dict[str, bool]:
    """Lemon Squeezy abonelik yaşam döngüsü olaylarını işler."""
    if not settings.saas_mode:
        raise HTTPException(status_code=404)
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")
    if not _verify_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Geçersiz webhook imzası")

    payload = json.loads(raw_body)
    event_name = payload.get("meta", {}).get("event_name")
    custom_data = payload.get("meta", {}).get("custom_data", {})
    tenant_id = custom_data.get("tenant_id")
    data = payload.get("data", {})
    attrs = data.get("attributes", {})
    subscription_id = str(data.get("id", ""))

    if event_name in _UPSERT_EVENTS and tenant_id:
        await _apply_subscription(tenant_id, attrs, subscription_id)
    elif event_name in _DOWNGRADE_EVENTS:
        await _downgrade(subscription_id)
    else:
        logger.info("lemonsqueezy webhook yok sayıldı: %s", event_name)

    return {"ok": True}
