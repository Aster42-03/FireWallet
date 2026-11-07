"""
FireWallet Deep Analytics & Telemetry Engine
============================================
Computes analytical telemetry, running balances, zero-sum audits, and velocity metrics
powering both the Desktop AG Grid Workbench and the AI Financial Coach.

Core Capabilities:
1. Chronological Running Balances:
   Calculates running bucket balances across all posted transactions in exact chronological order.
2. Zero-Sum Double-Entry Verification:
   Audits all internal transfer legs sharing a transfer_id to verify that sum(legs) == 0.
3. Velocity & Runway Telemetry:
   Calculates 7-day rolling burn rate (cents/day), projected runway in days, and Freedom monthly burn %.
4. Statistical Anomaly Detection:
   Flags spending spikes exceeding 1.5 standard deviations (>1.5 sigma) above the historical mean.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.models.bucket import Bucket
from app.models.user import BudgetPolicy

def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

async def query_deep_ledger(
    session: AsyncSession,
    user_id: UUID,
    bucket: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    entry_kind: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Foundational query engine powering the desktop AG Grid view (/analytics/deep-ledger).
    
    Computes:
    - Running bucket balances per entry across historical posted transactions.
    - Double-entry provenance (direction, entry_kind, counterparty_bucket, memo).
    - Aggregate statistics (total credits, total debits, active holds, internal volume).
    - Velocity metrics (burn rate, projected runway days, Freedom burn percentage).
    
    Args:
        session: Active AsyncSession.
        user_id: UUID of the requesting user.
        bucket: Optional filter by bucket kind ('bank', 'daily', etc.).
        state: Optional filter by transaction state ('posted', 'hold', 'released').
        category: Optional filter by spending category ('groceries', 'transit', etc.).
        entry_kind: Optional filter by entry kind ('merchant_spend', 'vault_skim', etc.).
        from_date: Optional lower bound datetime.
        to_date: Optional upper bound datetime.
        limit: Pagination limit.
        offset: Pagination offset.
        
    Returns:
        Dict containing total_count, list of items, and comprehensive aggregates.
    """
    # 1. Fetch all user buckets to map IDs and kinds
    b_stmt = select(Bucket).where(Bucket.user_id == user_id)
    b_res = await session.exec(b_stmt)
    user_buckets = {b.id: b.kind for b in b_res.all()}

    # 2. Compute chronological running balance per bucket across all posted entries
    chrono_stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user_id)
        .order_by(col(LedgerEntry.created_at).asc(), col(LedgerEntry.id).asc())
    )
    chrono_res = await session.exec(chrono_stmt)
    all_chrono = chrono_res.all()

    running_map: Dict[UUID, int] = {}
    transfer_sums: Dict[UUID, int] = {}
    bucket_running_acc: Dict[UUID, int] = {bid: 0 for bid in user_buckets}

    for e in all_chrono:
        if e.state == "posted":
            bucket_running_acc[e.bucket_id] = bucket_running_acc.get(e.bucket_id, 0) + e.amount
        running_map[e.id] = bucket_running_acc.get(e.bucket_id, 0)
        transfer_sums[e.transfer_id] = transfer_sums.get(e.transfer_id, 0) + e.amount

    # 3. Build query for filtered rows
    stmt = (
        select(LedgerEntry, Intent.category, Intent.utterance, Intent.merchant_name, Intent.necessity, Bucket.kind)
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
    if entry_kind:
        stmt = stmt.where(LedgerEntry.entry_kind == entry_kind)
    if from_date:
        stmt = stmt.where(LedgerEntry.created_at >= from_date)
    if to_date:
        stmt = stmt.where(LedgerEntry.created_at <= to_date)

    # Order newest first for table presentation
    stmt = stmt.order_by(col(LedgerEntry.created_at).desc(), col(LedgerEntry.id).desc())

    # Execute query
    result = await session.exec(stmt)
    all_rows = result.all()

    total_count = len(all_rows)
    paged_rows = all_rows[offset:offset + limit]

    items = []
    total_debits = 0
    total_credits = 0
    active_holds = 0
    merchant_outflows = 0
    internal_transfers_volume = 0
    payday_inflows = 0

    internal_kinds = {"vault_skim", "bill_reserve", "freedom_allocation", "morning_topup", "internal_transfer"}

    for entry, cat, utt, merch, nec, b_kind in paged_rows:
        is_internal = entry.entry_kind in internal_kinds

        if entry.amount < 0:
            total_debits += abs(entry.amount)
            if not is_internal:
                merchant_outflows += abs(entry.amount)
            else:
                internal_transfers_volume += abs(entry.amount)
        else:
            total_credits += entry.amount
            if entry.entry_kind == "payday_inflow":
                payday_inflows += entry.amount

        if entry.state == "hold":
            active_holds += abs(entry.amount)

        direction = "CREDIT" if entry.amount >= 0 else "DEBIT"

        items.append({
            "id": entry.id,
            "transfer_id": entry.transfer_id,
            "created_at": entry.created_at.isoformat(),
            "category": cat or ("income" if entry.amount > 0 else "allocation" if is_internal else "general"),
            "bucket": b_kind or "unknown",
            "amount": entry.amount,
            "state": entry.state,
            "direction": direction,
            "entry_kind": entry.entry_kind,
            "counterparty_bucket": entry.counterparty_bucket or ("paypal_merchant" if not is_internal else "bank"),
            "memo": entry.memo or utt or ("Direct Income" if entry.amount > 0 else "Direct Debit"),
            "running_balance": running_map.get(entry.id, 0),
            "is_internal_transfer": is_internal,
            "necessity": nec or ("bill" if entry.entry_kind == "bill_reserve" else "freedom" if entry.entry_kind == "freedom_allocation" else "daily_living"),
            "utterance": utt or entry.memo or "Transfer / Direct Post",
            "merchant": merch or (entry.counterparty_bucket if is_internal else "PayPal Merchant"),
            "paypal_order_id": entry.paypal_order_id,
            "paypal_capture_id": entry.paypal_capture_id
        })

    # 4. Check zero-sum balance for all internal transfers (reconciliation invariant)
    internal_transfers = [entry for entry in all_chrono if entry.entry_kind in internal_kinds]
    double_entry_balanced = True
    for it in internal_transfers:
        if transfer_sums.get(it.transfer_id, 0) != 0:
            double_entry_balanced = False
            break

    # 5. Compute Velocity & Runway Metrics
    now = utc_now()
    seven_days_ago = now - timedelta(days=7)
    recent_daily_spends = [
        abs(e.amount) for e in all_chrono
        if e.state == "posted" and e.amount < 0
        and user_buckets.get(e.bucket_id) == "daily"
        and e.entry_kind == "merchant_spend"
        and e.created_at >= seven_days_ago
    ]
    daily_burn_rate = int(sum(recent_daily_spends) / 7) if recent_daily_spends else 3400  # cents/day

    # Query policy for target amounts
    pol_stmt = select(BudgetPolicy).where(BudgetPolicy.user_id == user_id)
    pol_res = await session.exec(pol_stmt)
    policy = pol_res.first()
    daily_target = policy.daily_amount if policy else 4000
    freedom_monthly = policy.freedom_monthly_amount if policy else 15000

    daily_avail = max(0, bucket_running_acc.get(next((bid for bid, k in user_buckets.items() if k == "daily"), None), 5200))
    freedom_avail = max(0, bucket_running_acc.get(next((bid for bid, k in user_buckets.items() if k == "freedom"), None), 9000))
    daily_runway_days = round(daily_avail / (daily_burn_rate or 1), 1) if daily_burn_rate > 0 else 99.0
    freedom_spent = max(0, freedom_monthly - freedom_avail)
    freedom_burn_pct = round((freedom_spent / (freedom_monthly or 1)) * 100, 1)

    return {
        "total_count": total_count,
        "items": items,
        "aggregates": {
            "total_debits": total_debits,
            "total_credits": total_credits,
            "active_holds": active_holds,
            "merchant_outflows": merchant_outflows,
            "internal_transfers_volume": internal_transfers_volume,
            "payday_inflows": payday_inflows,
            "double_entry_balanced": double_entry_balanced,
            "velocity_metrics": {
                "daily_burn_rate": daily_burn_rate,
                "daily_runway_days": daily_runway_days,
                "freedom_burn_pct": freedom_burn_pct,
                "daily_target": daily_target,
                "rollover_retained": max(0, daily_avail - daily_target)
            }
        }
    }

async def detect_spending_anomalies(
    session: AsyncSession,
    user_id: UUID,
    category: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Detect unusual spikes in spend over a rolling window (>1.5 sigma above mean).
    
    Args:
        session: Active AsyncSession.
        user_id: UUID of user.
        category: Optional category filter.
        days: Rolling lookback window in days (default 30).
        
    Returns:
        List of detected anomaly records with deviation ratios.
    """
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
        if val > mean_val + (1.5 * std_dev) and val > 3000:  # Spikes above $30 threshold
            anomalies.append({
                "entry_id": entry.id,
                "amount": entry.amount,
                "category": cat or "general",
                "utterance": utt or "Unknown",
                "date": entry.created_at.strftime("%Y-%m-%d"),
                "deviation_ratio": round(val / (mean_val or 1), 2)
            })
    return anomalies

async def compute_deep_financial_insights(
    session: AsyncSession,
    user_id: UUID,
    filter_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compile structured telemetry for the Advanced Reasoning Coach agent.
    Combines filtered AG Grid ledger data, anomalies, velocity, and zero-sum verification.
    
    Args:
        session: Active AsyncSession.
        user_id: UUID of the user.
        filter_context: Active filter state passed from frontend AG Grid.
        
    Returns:
        Structured dictionary synthesized for prompt injection.
    """
    filters = filter_context or {}
    ledger_data = await query_deep_ledger(
        session=session,
        user_id=user_id,
        bucket=filters.get("bucket"),
        state=filters.get("state"),
        category=filters.get("category"),
        entry_kind=filters.get("entry_kind"),
        limit=50
    )
    anomalies = await detect_spending_anomalies(session=session, user_id=user_id)
    aggs = ledger_data["aggregates"]

    return {
        "filtered_count": ledger_data["total_count"],
        "aggregates": aggs,
        "velocity_metrics": aggs.get("velocity_metrics", {}),
        "anomalies": anomalies,
        "sample_items": ledger_data["items"][:10],
        "zero_sum_reconciled": aggs.get("double_entry_balanced", True)
    }
