from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.intent import Intent, Override
from app.models.bucket import Bucket
from app.schemas.common import IntentCreate, IntentResponse, IntentExecuteResponse, IntentCaptureRequest
from app.api.v1.auth import get_current_user
from app.agents.intent.parser import parse_intent_utterance
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
    """Submit a natural language intent for proactive AI classification and rule verification."""
    intent = Intent(
        user_id=user.id,
        utterance=body.utterance,
        amount=body.amount,
        currency=body.currency,
        merchant_name=body.merchant_name,
        client_idempotency_key=idempotency_key or None
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    # Invoke Stage 1: Intent Parser
    parsed = await parse_intent_utterance(
        session=session,
        intent_id=intent.id,
        utterance=body.utterance,
        amount_minor=body.amount,
        merchant_name=body.merchant_name or ""
    )

    intent.category = parsed.get("category", "other")
    intent.necessity = parsed.get("necessity", "freedom")
    intent.recommended_bucket = parsed.get("recommended_bucket", "freedom")

    # Determine default source bucket
    target_kind = intent.recommended_bucket if intent.recommended_bucket in ("daily", "freedom", "bank", "bills") else "freedom"
    stmt_b = select(Bucket).where(Bucket.user_id == user.id).where(Bucket.kind == target_kind)
    res_b = await session.exec(stmt_b)
    bucket_obj = res_b.first()
    if bucket_obj:
        intent.source_bucket_id = bucket_obj.id

    # Evaluate Stage 2: Policy Guardrail (Deterministic can_spend)
    is_allowed, policy_status, rationale = await LedgerEngine.can_spend(
        session=session,
        user_id=user.id,
        amount_minor=body.amount,
        source_kind=target_kind,
        necessity=intent.necessity
    )

    intent.status = policy_status
    session.add(intent)
    await session.commit()

    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    target_avail = balances.get(target_kind, {}).get("available", 0)

    return {
        "id": intent.id,
        "status": intent.status,
        "category": intent.category,
        "necessity": intent.necessity,
        "recommended_bucket": intent.recommended_bucket,
        "confidence": parsed.get("confidence", 0.95),
        "rationale": parsed.get("rationale") or rationale,
        "flags": parsed.get("flags", []),
        "source_bucket": target_kind,
        "balances_after_preview": {
            f"{target_kind}_available": max(0, target_avail - body.amount) if is_allowed else target_avail
        },
        "override_required": (intent.status == "needs_override")
    }

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

    # Verify status
    if intent.status not in ("allowed", "override_approved"):
        raise HTTPException(status_code=409, detail=f"Cannot execute intent in status '{intent.status}'. Override required.")

    # Place atomic ledger HOLD
    if not intent.source_bucket_id:
        raise HTTPException(status_code=400, detail="No source bucket configured")

    hold = await LedgerEngine.place_hold(
        session=session,
        user_id=user.id,
        bucket_id=intent.source_bucket_id,
        amount_minor=intent.amount,
        intent_id=intent.id
    )

    # Call PayPal Sandbox to create order
    order_res = await paypal_client.create_order(
        intent_id=str(intent.id),
        amount_cents=intent.amount,
        description=f"{intent.category or 'Spend'}: {intent.utterance[:50]}"
    )

    intent.paypal_order_id = order_res.get("id")
    intent.status = "executing"
    session.add(intent)
    await session.commit()

    # Find approval URL
    approval_url = next(
        (link["href"] for link in order_res.get("links", []) if link.get("rel") in ("approve", "payer-action")),
        f"https://www.sandbox.paypal.com/checkoutnow?token={intent.paypal_order_id}"
    )

    return {
        "status": "executing",
        "paypal_order_id": intent.paypal_order_id,
        "approval_url": approval_url
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

    # Capture order in PayPal sandbox
    cap_res = await paypal_client.capture_order(order_id=body.paypal_order_id, intent_id=str(intent.id))

    capture_id = f"CAPTURE-{body.paypal_order_id[:8]}"
    try:
        capture_id = cap_res["purchase_units"][0]["payments"]["captures"][0]["id"]
    except Exception:
        pass

    # Settle ledger hold
    await LedgerEngine.settle_hold(session, intent.id, capture_id)

    intent.status = "settled"
    session.add(intent)
    await session.commit()

    return {"status": "settled", "paypal_capture_id": capture_id}
