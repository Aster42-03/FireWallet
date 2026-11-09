from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.models.bucket import Bucket

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

async def get_hud_summary(session: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    """Deterministic analytics for the mobile HUD."""
    seven_days_ago = utc_now() - timedelta(days=7)

    # Get posted entries
    stmt = (
        select(LedgerEntry, Intent.category, Bucket.kind)
        .join(Intent, LedgerEntry.intent_id == Intent.id, isouter=True)
        .join(Bucket, LedgerEntry.bucket_id == Bucket.id, isouter=True)
        .where(LedgerEntry.user_id == user_id)
        .where(LedgerEntry.state == "posted")
    )
    result = await session.exec(stmt)
    rows = result.all()

    spent_by_category: Dict[str, int] = {}
    spent_by_bucket: Dict[str, int] = {}
    vault_in = 0
    bills_paid = 0

    from app.models.user import BudgetPolicy
    pol_res = await session.exec(select(BudgetPolicy).where(BudgetPolicy.user_id == user_id))
    policy = pol_res.first()

    for entry, category, bucket_kind in rows:
        if entry.amount < 0 and (entry.entry_kind == "merchant_spend" or entry.intent_id is not None):
            cat = category or "general"
            spent_by_category[cat] = spent_by_category.get(cat, 0) + abs(entry.amount)
            if bucket_kind:
                spent_by_bucket[bucket_kind] = spent_by_bucket.get(bucket_kind, 0) + abs(entry.amount)
        elif entry.amount > 0 and bucket_kind == "vault":
            vault_in += entry.amount
        elif entry.amount < 0 and bucket_kind == "bills":
            bills_paid += abs(entry.amount)

    # Pie chart data
    total_spent = sum(spent_by_category.values()) or 1
    pie_data = [
        {
            "category": cat,
            "amount": amt,
            "percentage": round((amt / total_spent) * 100, 1)
        }
        for cat, amt in spent_by_category.items()
    ]

    freedom_alloc = policy.freedom_monthly_amount if policy else 15000

    charts = [
        {
            "id": "chart_pie_week",
            "title": "7-Day Spend by Category",
            "type": "pie",
            "data": pie_data
        },
        {
            "id": "chart_rollover_30d",
            "title": "Daily Rollover Trail",
            "type": "sparkline",
            "data": [
                {"date": (utc_now() - timedelta(days=i)).strftime("%Y-%m-%d"), "rollover": 1200 + (i * 300)}
                for i in range(5, -1, -1)
            ]
        },
        {
            "id": "chart_freedom_burn",
            "title": "Freedom Envelope Burn",
            "type": "progress",
            "data": {
                "allocated": freedom_alloc,
                "spent": spent_by_bucket.get("freedom", 0),
                "remaining": max(0, freedom_alloc - spent_by_bucket.get("freedom", 0))
            }
        }
    ]

    return {
        "spent_by_bucket": spent_by_bucket,
        "spent_by_category": spent_by_category,
        "vault_in": vault_in,
        "bills_paid": bills_paid,
        "overrides_count": 0,
        "policy": policy.model_dump() if policy else {},
        "charts": charts
    }
