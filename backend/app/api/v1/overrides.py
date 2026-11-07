"""
Escape Window & Emergency Zero-Delay Override Router
====================================================
Enforces behavioral reflection friction for discretionary Bank raids while granting
instant zero-delay (`cooldown_seconds = 0`) approval for verified medical, safety,
stranded, or utility-shutoff emergencies:
- Non-Emergency Splurges: Mandatory >= 200-character reflection confession + 180s server cooldown.
- Genuine Emergencies: Verified via `is_genuine_emergency` -> 0s cooldown, immediate `approved`
  status, and `intent.status = 'override_approved'`.
- Records concise `short_tag` on every override for user review and Coach RAG context.
"""

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
from app.agents.rag import distill_short_tag, is_genuine_emergency

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
    std_cooldown_secs = policy.override_cooldown_seconds if policy else 180

    # Verify whether the intent + explanation constitute a genuine emergency
    trimmed_body = body.body.strip()
    emerg, _ = is_genuine_emergency(
        f"{intent.utterance} {trimmed_body}",
        merchant_name=intent.merchant_name or "",
        category=intent.category or "",
    )
    is_emerg = bool(intent.is_emergency or emerg)

    short_tag = distill_short_tag(
        f"{intent.utterance} {trimmed_body}",
        category=intent.category,
        merchant_name=intent.merchant_name,
    )

    if is_emerg:
        # Genuine Emergency Path: NO 200-char wall, ZERO cooldown delay!
        if len(trimmed_body) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Please provide a brief description of the emergency (at least 8 characters).",
            )
        now = utc_now()
        override = Override(
            intent_id=intent.id,
            user_id=user.id,
            body=body.body,
            short_tag=short_tag,
            is_emergency=True,
            status="approved",
            ready_at=now,
        )
        session.add(override)

        intent.is_emergency = True
        intent.short_tag = intent.short_tag or short_tag
        intent.status = "override_approved"
        session.add(intent)
        await session.commit()
        await session.refresh(override)

        return {
            "id": override.id,
            "status": override.status,
            "ready_at": override.ready_at.isoformat(),
            "cooldown_seconds": 0,
            "partner_required": False,
            "is_emergency": True,
            "short_tag": short_tag,
        }

    # Non-Emergency Discretionary Splurge Path: Gate 1 (200-char confession) + Gate 2 (180s cooldown)
    if len(trimmed_body) < min_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Confession must be at least {min_chars} characters. You provided {len(trimmed_body)}.",
        )

    ready_at = utc_now() + timedelta(seconds=std_cooldown_secs)
    override = Override(
        intent_id=intent.id,
        user_id=user.id,
        body=body.body,
        short_tag=short_tag,
        is_emergency=False,
        status="pending",
        ready_at=ready_at,
    )
    session.add(override)

    intent.short_tag = intent.short_tag or short_tag
    intent.status = "override_pending"
    session.add(intent)
    await session.commit()
    await session.refresh(override)

    return {
        "id": override.id,
        "status": override.status,
        "ready_at": override.ready_at.isoformat(),
        "cooldown_seconds": std_cooldown_secs,
        "partner_required": policy.partner_required_for_bank if policy else False,
        "is_emergency": False,
        "short_tag": short_tag,
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
    target_ready = override.ready_at
    if target_ready.tzinfo is None:
        target_ready = target_ready.replace(tzinfo=timezone.utc)

    if not override.is_emergency and now < target_ready:
        remaining_secs = int((target_ready - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cooldown active. {remaining_secs} seconds remaining.",
        )

    override.status = "approved"
    session.add(override)

    stmt_i = select(Intent).where(Intent.id == override.intent_id)
    res_i = await session.exec(stmt_i)
    intent = res_i.first()
    if intent:
        intent.status = "override_approved"
        session.add(intent)

    await session.commit()
    return {
        "status": "approved",
        "intent_id": override.intent_id,
        "is_emergency": override.is_emergency,
        "short_tag": override.short_tag,
    }
