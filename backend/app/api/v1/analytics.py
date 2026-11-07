"""
Analytics & AG Grid API Router
==============================
Provides endpoints powering the Desktop AG Grid Workbench (/analytics/deep-ledger)
and statistical spending anomaly detection.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.schemas.common import DeepLedgerResponse
from app.api.v1.auth import get_current_user
from app.analytics.deep_analytics import query_deep_ledger, detect_spending_anomalies

router = APIRouter(prefix="/analytics", tags=["Deep Analytics & AG Grid"])

@router.get("/deep-ledger", response_model=DeepLedgerResponse)
async def get_deep_ledger(
    bucket: Optional[str] = Query(default=None, description="Filter by bucket kind ('bank', 'daily', etc.)"),
    state: Optional[str] = Query(default=None, description="Filter by transaction state ('posted', 'hold', 'released')"),
    category: Optional[str] = Query(default=None, description="Filter by category ('groceries', 'utilities', etc.)"),
    entry_kind: Optional[str] = Query(default=None, description="Filter by entry kind ('merchant_spend', 'vault_skim', etc.)"),
    from_date: Optional[datetime] = Query(default=None, alias="from", description="Earliest ISO timestamp"),
    to_date: Optional[datetime] = Query(default=None, alias="to", description="Latest ISO timestamp"),
    limit: int = Query(default=100, le=500, description="Page size limit"),
    offset: int = Query(default=0, description="Offset for pagination"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Primary data source for the Desktop AG Grid 'Advanced Ledger & Audit Log' view.
    Returns double-entry transaction items with running balances, audit correlation IDs,
    zero-sum verification, and spending velocity metrics.
    """
    return await query_deep_ledger(
        session=session,
        user_id=user.id,
        bucket=bucket,
        state=state,
        category=category,
        entry_kind=entry_kind,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset
    )

@router.get("/anomalies")
async def get_anomalies(
    category: Optional[str] = Query(default=None, description="Filter by spending category"),
    days: int = Query(default=30, description="Rolling lookback window in days"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Detects unusual spending spikes exceeding 1.5 standard deviations (>1.5 sigma) above historical mean.
    """
    anomalies = await detect_spending_anomalies(
        session=session,
        user_id=user.id,
        category=category,
        days=days
    )
    return {
        "days": days,
        "count": len(anomalies),
        "anomalies": anomalies
    }
