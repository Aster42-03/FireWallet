from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.models.bucket import Bucket

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

async def query_deep_ledger(
    session: AsyncSession,
    user_id: UUID,
    bucket: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Foundational query engine powering the desktop AG Grid view.
    Returns transaction items with rich audit metadata and aggregate summaries.
    """
    stmt = (
        select(LedgerEntry, Intent.category, Intent.utterance, Intent.merchant_name, Bucket.kind)
        .join(Intent, LedgerEntry.intent_id == Intent.id, isouter=True)
        .join(Bucket, LedgerEntry.bucket_id == Bucket.id, isouter=True)
        .where(LedgerEntry.user_id == user_id)
    )

    if bucket:
        stmt = stmt.where(Bucket.kind == bucket)
    if state:
        stmt = stmt.where(LedgerEntry.state == state)
    if category:
        stmt = stmt.where(Intent.category == category)
    if from_date:
        stmt = stmt.where(LedgerEntry.created_at >= from_date)
    if to_date:
        stmt = stmt.where(LedgerEntry.created_at <= to_date)

    # Order newest first
    stmt = stmt.order_by(col(LedgerEntry.created_at).desc())

    # Execute
    result = await session.exec(stmt)
    all_rows = result.all()

    total_count = len(all_rows)
    paged_rows = all_rows[offset:offset + limit]

    items = []
    total_debits = 0
    total_credits = 0
    active_holds = 0

    for entry, cat, utt, merch, b_kind in paged_rows:
        if entry.amount < 0:
            total_debits += abs(entry.amount)
        else:
            total_credits += entry.amount

        if entry.state == "hold":
            active_holds += abs(entry.amount)

        items.append({
            "id": entry.id,
            "transfer_id": entry.transfer_id,
            "created_at": entry.created_at.isoformat(),
            "category": cat or "general",
            "bucket": b_kind or "unknown",
            "amount": entry.amount,
            "state": entry.state,
            "utterance": utt or "Transfer / Direct Post",
            "merchant": merch or "PayPal Merchant",
            "paypal_order_id": entry.paypal_order_id,
            "paypal_capture_id": entry.paypal_capture_id
        })

    return {
        "total_count": total_count,
        "items": items,
        "aggregates": {
            "total_debits": total_debits,
            "total_credits": total_credits,
            "active_holds": active_holds
        }
    }

async def detect_spending_anomalies(
    session: AsyncSession,
    user_id: UUID,
    category: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Detect unusual spikes in spend over the rolling period."""
    cutoff = utc_now() - timedelta(days=days)
    stmt = (
        select(LedgerEntry, Intent.category, Intent.utterance)
        .join(Intent, LedgerEntry.intent_id == Intent.id, isouter=True)
        .where(LedgerEntry.user_id == user_id)
        .where(LedgerEntry.state == "posted")
        .where(LedgerEntry.amount < 0)
        .where(LedgerEntry.created_at >= cutoff)
    )
    result = await session.exec(stmt)
    rows = result.all()

    if not rows:
        return []

    amounts = [abs(e.amount) for e, _, _ in rows]
    mean_val = sum(amounts) / len(amounts)
    std_dev = (sum((x - mean_val) ** 2 for x in amounts) / len(amounts)) ** 0.5

    anomalies = []
    for entry, cat, utt in rows:
        val = abs(entry.amount)
        if val > mean_val + (1.5 * std_dev) and val > 3000:  # Spikes above $30
            anomalies.append({
                "entry_id": entry.id,
                "amount": entry.amount,
                "category": cat or "general",
                "utterance": utt or "Unknown",
                "date": entry.created_at.strftime("%Y-%m-%d"),
                "deviation_ratio": round(val / (mean_val or 1), 2)
            })
    return anomalies
