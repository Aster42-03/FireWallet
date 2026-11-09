"""
Escape Window & Emergency Zero-Delay Override Router
====================================================
Enforces behavioral reflection friction for discretionary Bank raids while granting
instant zero-delay (`cooldown_seconds = 0`) approval for verified medical, safety,
stranded, or utility-shutoff emergencies:
- Non-Emergency Splurges: Mandatory >= 200-character reflection confession + 180s server cooldown.
- Genuine Emergencies: Verified via `is_genuine_emergency` -> 0s cooldown, immediate `approved`
  status, and `intent.status = 'override_approved'`.
- Accountability Partner Dual-Flow: Single-use cryptographic approval token dispatch,
  0s cooldown & 0 chars unlock on partner approval, and outcome alert dispatch.
- Records concise `short_tag` on every override for user review and Coach RAG context.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import logging
import secrets
from typing import Any, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User, BudgetPolicy, PartnerLink, PartnerApproval
from app.models.intent import Intent, Override
from app.schemas.common import OverrideCreate, OverrideResponse
from app.api.v1.auth import get_current_user
from app.agents.rag import distill_short_tag, is_genuine_emergency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/overrides", tags=["Escape Window Overrides"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PartnerOverrideResponse(OverrideResponse):
    partner_token: Optional[str] = None
    partner_approval_url: Optional[str] = None
    partner_email: Optional[str] = None


@router.post("", response_model=PartnerOverrideResponse, status_code=status.HTTP_201_CREATED)
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

    # Cryptographic partner approval token (256-bit URL-safe)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Look up or create active PartnerLink
    stmt_link = select(PartnerLink).where(PartnerLink.user_id == user.id, PartnerLink.active == True)
    partner_link = (await session.exec(stmt_link)).first()
    if not partner_link:
        partner_link = PartnerLink(
            user_id=user.id,
            partner_email="partner@firewallet.local",
            active=True,
        )
        session.add(partner_link)
        await session.commit()
        await session.refresh(partner_link)

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

        approval = PartnerApproval(
            override_id=override.id,
            partner_link_id=partner_link.id,
            token_hash=token_hash,
            status="pending",
        )
        session.add(approval)
        await session.commit()

        logger.warning(f"🚨 [PARTNER ESCALATION] Token: {raw_token} | URL: /partner/approve/{raw_token}")
        print(f"🚨 [PARTNER ESCALATION] Token: {raw_token} | URL: /partner/approve/{raw_token}", flush=True)

        return {
            "id": override.id,
            "status": override.status,
            "ready_at": override.ready_at.isoformat(),
            "cooldown_seconds": 0,
            "partner_required": False,
            "is_emergency": True,
            "short_tag": short_tag,
            "partner_token": raw_token,
            "partner_approval_url": f"/partner/approve/{raw_token}",
            "partner_email": partner_link.partner_email,
        }

    # Non-Emergency Path: Accountability Partner Dual-Flow / Standard Friction
    is_whim_or_short = (
        "really want" in trimmed_body.lower()
        or "really just want" in trimmed_body.lower()
        or len(trimmed_body) < 35
    )

    partner_active = (policy and policy.partner_required_for_bank) or (not is_whim_or_short and len(trimmed_body) >= 35)

    if not partner_active and len(trimmed_body) < min_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Confession must be at least {min_chars} characters. You provided {len(trimmed_body)}.",
        )

    if partner_active and len(trimmed_body) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Please provide a brief reflection (at least 8 characters).",
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

    approval = PartnerApproval(
        override_id=override.id,
        partner_link_id=partner_link.id,
        token_hash=token_hash,
        status="pending",
    )
    session.add(approval)
    await session.commit()

    logger.warning(f"🚨 [PARTNER ESCALATION] Token: {raw_token} | URL: /partner/approve/{raw_token}")
    print(f"🚨 [PARTNER ESCALATION] Token: {raw_token} | URL: /partner/approve/{raw_token}", flush=True)

    return {
        "id": override.id,
        "status": override.status,
        "ready_at": override.ready_at.isoformat(),
        "cooldown_seconds": std_cooldown_secs,
        "partner_required": True,
        "is_emergency": False,
        "short_tag": short_tag,
        "partner_token": raw_token,
        "partner_approval_url": f"/partner/approve/{raw_token}",
        "partner_email": partner_link.partner_email,
    }


@router.post("/{override_id}/check-cooldown")
async def check_cooldown(
    override_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Verify if cooldown elapsed or partner approved, and unlock the intent for execution."""
    stmt = select(Override).where(Override.id == override_id).where(Override.user_id == user.id)
    res = await session.exec(stmt)
    override = res.first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    now = utc_now()
    target_ready = override.ready_at
    if target_ready.tzinfo is None:
        target_ready = target_ready.replace(tzinfo=timezone.utc)

    # If partner approved or emergency, instant unlock bypasses cooldown
    if not override.is_emergency and override.status != "approved" and now < target_ready:
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


@router.post("/{override_id}/cancel")
async def cancel_override(
    override_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Cancel override and dispatch partner outcome alert."""
    stmt = select(Override).where(Override.id == override_id).where(Override.user_id == user.id)
    res = await session.exec(stmt)
    override = res.first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    override.status = "cancelled"
    session.add(override)

    stmt_i = select(Intent).where(Intent.id == override.intent_id)
    res_i = await session.exec(stmt_i)
    intent = res_i.first()
    if intent and intent.status not in ("settled",):
        intent.status = "cancelled"
        session.add(intent)

    await session.commit()

    outcome_msg = f"[PARTNER OUTCOME ALERT] Override {override.id} resolved: CANCELLED by user"
    logger.info(outcome_msg)
    print(outcome_msg, flush=True)

    return {"status": "cancelled", "override_id": override.id}
