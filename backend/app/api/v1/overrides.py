from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User, BudgetPolicy
from app.models.intent import Intent, Override
from app.schemas.common import OverrideCreate, OverrideResponse
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/overrides", tags=["Escape Window Overrides"])

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

@router.post("", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)
async def create_override(
    body: OverrideCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt_i = select(Intent).where(Intent.id == body.intent_id).where(Intent.user_id == user.id)
    res_i = await session.exec(stmt_i)
    intent = res_i.first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    stmt_p = select(BudgetPolicy).where(BudgetPolicy.user_id == user.id)
    res_p = await session.exec(stmt_p)
    policy = res_p.first()

    min_chars = policy.override_min_chars if policy else 200
    cooldown_secs = policy.override_cooldown_seconds if policy else 180

    # Gate 1: Mandatory Confession Length Check
    if len(body.body.strip()) < min_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Confession must be at least {min_chars} characters. You provided {len(body.body.strip())}."
        )

    # Gate 2: Server-Enforced Cooldown Timer
    ready_at = utc_now() + timedelta(seconds=cooldown_secs)

    override = Override(
        intent_id=intent.id,
        user_id=user.id,
        body=body.body,
        status="pending",
        ready_at=ready_at
    )
    session.add(override)

    intent.status = "override_pending"
    session.add(intent)
    await session.commit()
    await session.refresh(override)

    return {
        "id": override.id,
        "status": override.status,
        "ready_at": override.ready_at.isoformat(),
        "cooldown_seconds": cooldown_secs,
        "partner_required": policy.partner_required_for_bank if policy else False
    }

@router.post("/{override_id}/check-cooldown")
async def check_cooldown(
    override_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Verify if cooldown elapsed and unlock the intent for execution."""
    stmt = select(Override).where(Override.id == override_id).where(Override.user_id == user.id)
    res = await session.exec(stmt)
    override = res.first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    now = utc_now()
    # Normalize if SQLite returned a naive datetime
    target_ready = override.ready_at
    if target_ready.tzinfo is None:
        target_ready = target_ready.replace(tzinfo=timezone.utc)

    if now < target_ready:
        remaining_secs = int((target_ready - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cooldown active. {remaining_secs} seconds remaining."
        )

    # Mark approved
    override.status = "approved"
    session.add(override)

    stmt_i = select(Intent).where(Intent.id == override.intent_id)
    res_i = await session.exec(stmt_i)
    intent = res_i.first()
    if intent:
        intent.status = "override_approved"
        session.add(intent)

    await session.commit()
    return {"status": "approved", "intent_id": override.intent_id}
