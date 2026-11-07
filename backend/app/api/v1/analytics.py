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
    bucket: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None, alias="from"),
    to_date: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Foundational data source for the Desktop AG Grid 'Advanced Ledger & Audit Log' view.
    Provides multi-column filtering, state grouping, and audit correlation IDs.
    """
    return await query_deep_ledger(
        session=session,
        user_id=user.id,
        bucket=bucket,
        state=state,
        category=category,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset
    )

@router.get("/anomalies")
async def get_anomalies(
    category: Optional[str] = Query(default=None),
    days: int = Query(default=30),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    anomalies = await detect_spending_anomalies(session=session, user_id=user.id, category=category, days=days)
    return {"count": len(anomalies), "anomalies": anomalies}
