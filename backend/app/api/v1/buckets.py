from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.ledger.engine import LedgerEngine
from app.api.v1.auth import get_current_user

router = APIRouter(tags=["Buckets & Ledger"])

@router.get("/buckets")
async def get_buckets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Retrieve available and held balances across all Trinity buckets."""
    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    buckets_list = [
        {
            "kind": kind,
            "name": data["name"],
            "available": data["available"],
            "held": data["held"],
            "pending_paypal": 0
        }
        for kind, data in balances.items()
    ]
    return {
        "currency": "USD",
        "buckets": buckets_list
    }

@router.get("/ledger")
async def get_ledger(
    bucket: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Paginated double-entry ledger entries."""
    stmt = (
        select(LedgerEntry, Intent.utterance)
        .join(Intent, LedgerEntry.intent_id == Intent.id, isouter=True)
        .where(LedgerEntry.user_id == user.id)
        .order_by(col(LedgerEntry.created_at).desc())
        .limit(limit)
    )
    result = await session.exec(stmt)
    rows = result.all()

    items = [
        {
            "id": entry.id,
            "amount": entry.amount,
            "state": entry.state,
            "intent_id": entry.intent_id,
            "utterance": utterance or "Transfer",
            "paypal_capture_id": entry.paypal_capture_id,
            "posted_at": entry.posted_at.isoformat() if entry.posted_at else None
        }
        for entry, utterance in rows
    ]
    return {"items": items, "next_cursor": None}
