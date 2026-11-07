import json
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.webhook import PayPalWebhookEvent
from app.models.intent import Intent
from app.ledger.engine import LedgerEngine
from app.services.paypal_client import paypal_client

logger = logging.getLogger("webhooks")
router = APIRouter(prefix="/webhooks", tags=["PayPal Webhooks"])

@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Public webhook receiver with cryptographic signature verification and idempotency check.
    """
    raw_body = await request.body()
    headers = dict(request.headers)

    # 1. Cryptographic Signature Verification
    is_valid = await paypal_client.verify_webhook_signature(headers=headers, raw_body=raw_body)
    if not is_valid:
        logger.warning("PayPal Webhook signature verification failed.")
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid JSON")

    event_id = event_data.get("id")
    event_type = event_data.get("event_type", "UNKNOWN")

    # 2. Idempotency Check
    stmt = select(PayPalWebhookEvent).where(PayPalWebhookEvent.event_id == event_id)
    res = await session.exec(stmt)
    if res.first():
        logger.info(f"Duplicate webhook event {event_id} ignored.")
        return {"status": "duplicate_ignored", "event_id": event_id}

    # Record event
    webhook_log = PayPalWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload_json=raw_body.decode("utf-8")
    )
    session.add(webhook_log)
    await session.commit()

    # 3. Route specific event types
    resource = event_data.get("resource", {})
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        capture_id = resource.get("id")
        custom_id = resource.get("custom_id")
        if custom_id:
            try:
                intent_uuid = UUID(custom_id)
                stmt_i = select(Intent).where(Intent.id == intent_uuid)
                res_i = await session.exec(stmt_i)
                intent = res_i.first()
                if intent:
                    await LedgerEngine.settle_hold(session, intent.id, capture_id)
                    intent.status = "settled"
                    session.add(intent)
                    await session.commit()
                    logger.info(f"Settled intent {intent_uuid} via capture {capture_id}")
            except Exception as e:
                logger.error(f"Error settling intent from webhook: {e}")

    return {"ok": True, "event_id": event_id, "event_type": event_type}
