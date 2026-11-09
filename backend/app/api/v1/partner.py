"""
Accountability Partner Decision Router
======================================
Public endpoints allowing an accountability partner to review and decide on
Escape Window spend overrides using single-use cryptographic tokens:
- `GET /api/v1/partner/approve/{token}`: Inspect proposed expenditure, category, and reason.
- `POST /api/v1/partner/approve/{token}/decision`: Submit decision ('approved' or 'rejected').
  - Approval: Unlocks transaction immediately with 0s cooldown and 0 confession characters.
  - Rejection / Timeout: Enforces standard friction gates.
  - Single-use: Replays return HTTP 409 Conflict.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import logging
from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import PartnerApproval
from app.models.intent import Intent, Override

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/partner", tags=["Accountability Partner"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PartnerDecisionRequest(BaseModel):
    decision: str  # "approved" or "rejected"


@router.get("/approve/{token}")
async def inspect_partner_approval(
    token: str,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Public inspection endpoint for an accountability partner to review
    the proposed expenditure before deciding.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(PartnerApproval).where(PartnerApproval.token_hash == token_hash)
    res = await session.exec(stmt)
    approval = res.first()
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner approval request not found or invalid token."
        )

    stmt_o = select(Override).where(Override.id == approval.override_id)
    override = (await session.exec(stmt_o)).first()
    if not override:
        raise HTTPException(status_code=404, detail="Associated override not found")

    stmt_i = select(Intent).where(Intent.id == override.intent_id)
    intent = (await session.exec(stmt_i)).first()

    created_ref = override.created_at or override.ready_at
    if created_ref and created_ref.tzinfo is None:
        created_ref = created_ref.replace(tzinfo=timezone.utc)

    return {
        "override_id": override.id,
        "amount_cents": intent.amount if intent else 0,
        "utterance": intent.utterance if intent else override.body,
        "short_tag": override.short_tag,
        "category": intent.category if intent else "discretionary",
        "status": approval.status,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "expires_at": (created_ref + timedelta(hours=24)).isoformat() if created_ref else None,
    }


@router.post("/approve/{token}/decision")
async def submit_partner_decision(
    token: str,
    body: PartnerDecisionRequest,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Public decision submission endpoint for an accountability partner.
    Approving unlocks spend immediately with 0s cooldown delay.
    """
    decision = body.decision.strip().lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be exactly 'approved' or 'rejected'."
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(PartnerApproval).where(PartnerApproval.token_hash == token_hash)
    res = await session.exec(stmt)
    approval = res.first()
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner approval request not found or invalid token."
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Partner approval has already been decided."
        )

    stmt_o = select(Override).where(Override.id == approval.override_id)
    override = (await session.exec(stmt_o)).first()
    if not override:
        raise HTTPException(status_code=404, detail="Associated override not found")

    stmt_i = select(Intent).where(Intent.id == override.intent_id)
    intent = (await session.exec(stmt_i)).first()

    now = utc_now()
    created_at = override.created_at
    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now > created_at + timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Partner approval token has expired."
            )

    approval.decided_at = now

    if decision == "approved":
        approval.status = "approved"
        override.status = "approved"
        override.ready_at = now
        if intent:
            intent.status = "override_approved"
        log_msg = f"[PARTNER ESCALATION] Partner APPROVED override {override.id}. Spend unlocked with 0s cooldown."
        logger.info(log_msg)
        print(log_msg, flush=True)
    else:
        approval.status = "rejected"
        override.status = "rejected"
        if intent:
            intent.status = "rejected"
        log_msg = f"[PARTNER ESCALATION] Partner REJECTED override {override.id}."
        logger.info(log_msg)
        print(log_msg, flush=True)

    session.add(approval)
    session.add(override)
    if intent:
        session.add(intent)
    await session.commit()

    return {
        "status": decision,
        "override_id": override.id,
        "decided_at": approval.decided_at.isoformat(),
    }
