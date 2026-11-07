"""
Quick Intent Firewall Router
============================
Fast validation entrypoint (`POST /api/v1/intents`) powered by the Unified Agent
and deterministic `LedgerEngine` guardrails:
1. Distills & records a concise 2-5 word `short_tag` (e.g. 'groceries', 'takeout',
   'gift for family') for user review and Coach RAG retrieval.
2. Evaluates `verdict` ('accepted', 'rejected', 'refer_to_coach') and returns a
   pre-configured 1-tap `ActionCard` button.
3. Exposes `GET /api/v1/intents/tags` so users and the Coach can inspect recorded tags.
4. Handles two-phase PayPal Sandbox order creation (`execute`) and hold settlement (`capture`).
"""

from typing import Any, Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User, BudgetPolicy
from app.models.intent import Intent
from app.models.bucket import Bucket
from app.schemas.common import (
    ActionCard,
    IntentCaptureRequest,
    IntentCreate,
    IntentExecuteResponse,
    IntentResponse,
)
from app.api.v1.auth import get_current_user
from app.agents.intent.parser import parse_intent_utterance
from app.agents.rag import distill_short_tag, normalize_short_tag
from app.ledger.engine import LedgerEngine
from app.services.paypal_client import paypal_client

router = APIRouter(prefix="/intents", tags=["Intent Firewall"])


@router.post("", response_model=IntentResponse, status_code=status.HTTP_201_CREATED)
async def submit_intent(
    body: IntentCreate,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Submits a natural language spend intent for proactive single-call AI classification,
    `short_tag` recording, deterministic rule verification, and 1-tap `ActionCard` generation.
    """
    initial_tag = normalize_short_tag(body.short_tag, fallback_utterance=body.utterance, merchant_name=body.merchant_name)

    intent = Intent(
        user_id=user.id,
        utterance=body.utterance,
        short_tag=initial_tag,
        amount=body.amount,
        currency=body.currency,
        merchant_name=body.merchant_name,
        client_idempotency_key=idempotency_key or None,
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    # Stage 1: Single-Call NLP Intent Parser
    parsed = await parse_intent_utterance(
        session=session,
        intent_id=intent.id,
        utterance=body.utterance,
        amount_minor=body.amount,
        merchant_name=body.merchant_name or "",
    )

    intent.category = parsed.get("category", "other")
    intent.necessity = parsed.get("necessity", "freedom")
    intent.recommended_bucket = parsed.get("recommended_bucket", "freedom")
    intent.short_tag = normalize_short_tag(
        body.short_tag or parsed.get("short_tag"),
        fallback_utterance=body.utterance,
        category=intent.category,
        merchant_name=body.merchant_name,
    )
    intent.is_emergency = bool(parsed.get("is_emergency", False))

    # Determine target Trinity bucket
    valid_buckets = ("daily", "freedom", "bank", "bills", "vault")
    target_kind = intent.recommended_bucket if intent.recommended_bucket in valid_buckets else "freedom"
    stmt_b = select(Bucket).where(Bucket.user_id == user.id).where(Bucket.kind == target_kind)
    res_b = await session.exec(stmt_b)
    bucket_obj = res_b.first()
    if bucket_obj:
        intent.source_bucket_id = bucket_obj.id

    # Stage 2: Deterministic Policy Guardrail (`LedgerEngine.can_spend`)
    is_allowed, policy_status, rationale = await LedgerEngine.can_spend(
        session=session,
        user_id=user.id,
        amount_minor=body.amount,
        source_kind=target_kind,
        necessity=intent.necessity,
    )

    intent.status = policy_status
    session.add(intent)
    await session.commit()

    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    target_avail = balances.get(target_kind, {}).get("available", 0)

    # Fetch user policy cooldown for non-emergency overrides
    pol_res = await session.exec(select(BudgetPolicy).where(BudgetPolicy.user_id == user.id))
    policy = pol_res.first()
    std_cooldown = policy.override_cooldown_seconds if policy else 180

    if policy_status == "allowed":
        verdict = "accepted"
        cooldown_seconds = 0
        action_card = ActionCard(
            action_type="paypal_checkout",
            label=f"Pay ${body.amount / 100:.2f} via PayPal ({target_kind.capitalize()})",
            short_tag=intent.short_tag,
            utterance=body.utterance,
            amount_cents=body.amount,
            currency=body.currency,
            category=intent.category or "general",
            necessity=intent.necessity or "freedom",
            target_bucket=target_kind,
            merchant_name=body.merchant_name,
            intent_id=intent.id,
            is_emergency=intent.is_emergency,
            verdict="accepted",
        )
    elif policy_status == "needs_override":
        verdict = "refer_to_coach"
        cooldown_seconds = 0 if intent.is_emergency else std_cooldown
        action_card = ActionCard(
            action_type="open_override",
            label=(
                f"Emergency Unlock (${body.amount / 100:.2f} · 0s Delay)"
                if intent.is_emergency
                else f"Reason with Coach / Escape Window (${body.amount / 100:.2f})"
            ),
            short_tag=intent.short_tag,
            utterance=body.utterance,
            amount_cents=body.amount,
            currency=body.currency,
            category=intent.category or "general",
            necessity=intent.necessity or "freedom",
            target_bucket=target_kind,
            merchant_name=body.merchant_name,
            intent_id=intent.id,
            is_emergency=intent.is_emergency,
            verdict="refer_to_coach",
        )
    else:
        verdict = "rejected"
        cooldown_seconds = None
        action_card = None

    return {
        "id": intent.id,
        "status": intent.status,
        "verdict": verdict,
        "short_tag": intent.short_tag,
        "category": intent.category,
        "necessity": intent.necessity,
        "recommended_bucket": intent.recommended_bucket,
        "confidence": parsed.get("confidence", 0.95),
        "rationale": rationale if not is_allowed else (parsed.get("rationale") or rationale),
        "flags": parsed.get("flags", []),
        "source_bucket": target_kind,
        "balances_after_preview": {
            f"{target_kind}_available": max(0, target_avail - body.amount) if is_allowed else target_avail
        },
        "override_required": (intent.status == "needs_override"),
        "is_emergency": intent.is_emergency,
        "cooldown_seconds": cooldown_seconds,
        "action_card": action_card,
    }


@router.get("/tags")
async def list_recorded_short_tags(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Returns recorded `short_tag` items and rolled-up category frequencies so both
    the user and the Coach can review historical tags ('groceries', 'takeout', etc.).
    """
    stmt = (
        select(Intent)
        .where(Intent.user_id == user.id)
        .order_by(col(Intent.created_at).desc())
        .limit(50)
    )
    intents = (await session.exec(stmt)).all()

    items: List[Dict[str, Any]] = []
    rollup: Dict[str, Dict[str, Any]] = {}

    for it in intents:
        tag = it.short_tag or distill_short_tag(it.utterance, category=it.category, merchant_name=it.merchant_name)
        items.append({
            "intent_id": it.id,
            "short_tag": tag,
            "utterance": it.utterance,
            "amount": it.amount,
            "category": it.category,
            "bucket": it.recommended_bucket,
            "status": it.status,
            "is_emergency": it.is_emergency,
            "created_at": it.created_at.isoformat(),
        })
        agg = rollup.setdefault(tag, {"short_tag": tag, "count": 0, "total_cents": 0})
        agg["count"] += 1
        agg["total_cents"] += it.amount

    sorted_rollup = sorted(rollup.values(), key=lambda x: x["total_cents"], reverse=True)
    return {"total": len(items), "rollup": sorted_rollup, "items": items}


@router.get("/{intent_id}")
async def get_intent_status(
    intent_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(Intent).where(Intent.id == intent_id).where(Intent.user_id == user.id)
    result = await session.exec(stmt)
    intent = result.first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    return intent.model_dump()


@router.post("/{intent_id}/confirm")
async def confirm_intent(
    intent_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(Intent).where(Intent.id == intent_id).where(Intent.user_id == user.id)
    result = await session.exec(stmt)
    intent = result.first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    if intent.status in ("allowed", "override_approved"):
        return {"status": "confirmed", "intent_id": intent.id}
    raise HTTPException(status_code=400, detail=f"Cannot confirm intent in status '{intent.status}'")


@router.post("/{intent_id}/execute", response_model=IntentExecuteResponse)
async def execute_intent(
    intent_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(Intent).where(Intent.id == intent_id).where(Intent.user_id == user.id)
    result = await session.exec(stmt)
    intent = result.first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    if intent.status not in ("allowed", "override_approved"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot execute intent in status '{intent.status}'. Override required.",
        )

    # Resolve source bucket; if override_approved and original bucket lacks funds, draw from Bank Foundation
    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    hold_bucket_id = intent.source_bucket_id

    if intent.status == "override_approved":
        current_b_avail = 0
        for b_info in balances.values():
            if b_info["bucket_id"] == hold_bucket_id:
                current_b_avail = b_info["available"]
                break
        if current_b_avail < intent.amount and "bank" in balances:
            hold_bucket_id = balances["bank"]["bucket_id"]
            intent.source_bucket_id = hold_bucket_id

    if not hold_bucket_id:
        raise HTTPException(status_code=400, detail="No source bucket configured")

    tag = intent.short_tag or distill_short_tag(intent.utterance, category=intent.category, merchant_name=intent.merchant_name)
    await LedgerEngine.place_hold(
        session=session,
        user_id=user.id,
        bucket_id=hold_bucket_id,
        amount_minor=intent.amount,
        intent_id=intent.id,
        memo=f"{tag}: {intent.utterance[:50]}",
    )

    order_res = await paypal_client.create_order(
        intent_id=str(intent.id),
        amount_cents=intent.amount,
        description=f"{tag}: {intent.utterance[:50]}",
    )

    intent.paypal_order_id = order_res.get("id")
    intent.status = "executing"
    session.add(intent)
    await session.commit()

    approval_url = next(
        (link["href"] for link in order_res.get("links", []) if link.get("rel") in ("approve", "payer-action")),
        f"https://www.sandbox.paypal.com/checkoutnow?token={intent.paypal_order_id}",
    )

    return {
        "status": "executing",
        "paypal_order_id": intent.paypal_order_id,
        "approval_url": approval_url,
        "short_tag": tag,
    }


@router.post("/{intent_id}/capture")
async def capture_intent(
    intent_id: UUID,
    body: IntentCaptureRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(Intent).where(Intent.id == intent_id).where(Intent.user_id == user.id)
    result = await session.exec(stmt)
    intent = result.first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    cap_res = await paypal_client.capture_order(order_id=body.paypal_order_id, intent_id=str(intent.id))

    capture_id = f"CAPTURE-{body.paypal_order_id[:8]}"
    try:
        capture_id = cap_res["purchase_units"][0]["payments"]["captures"][0]["id"]
    except Exception:
        pass

    await LedgerEngine.settle_hold(session, intent.id, capture_id)

    intent.status = "settled"
    session.add(intent)
    await session.commit()

    return {
        "status": "settled",
        "paypal_capture_id": capture_id,
        "short_tag": intent.short_tag,
    }
