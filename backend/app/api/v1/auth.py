from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User, BudgetPolicy
from app.schemas.common import PolicyUpdate

router = APIRouter(tags=["Auth & Policy"])

async def get_current_user(session: AsyncSession = Depends(get_session)) -> User:
    """Retrieve demo user (or create default on the fly if needed)."""
    stmt = select(User).limit(1)
    result = await session.exec(stmt)
    user = result.first()
    if not user:
        user = User(email="demo-user@sandbox.paypal.com", display_name="Aster (Demo)")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create default Trinity policy
        policy = BudgetPolicy(
            user_id=user.id,
            currency="USD",
            vault_skim_bps=2000,
            daily_amount=4000,
            freedom_monthly_amount=15000,
            bank_spend_requires_override=True,
            vault_spend_allowed=False,
            override_min_chars=200,
            override_cooldown_seconds=180
        )
        session.add(policy)
        await session.commit()
    return user

@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(BudgetPolicy).where(BudgetPolicy.user_id == user.id)
    result = await session.exec(stmt)
    policy = result.first()
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "policy": policy.model_dump() if policy else {}
    }

@router.patch("/me/policy")
async def update_policy(
    body: PolicyUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(BudgetPolicy).where(BudgetPolicy.user_id == user.id)
    result = await session.exec(stmt)
    policy = result.first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, val)
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return {"status": "updated", "policy": policy.model_dump()}
