"""
Bulletproof PayPal Webhooks & Atomic Ledger Settlement Router
=============================================================
Public FastAPI webhook endpoint (`/api/v1/webhooks/paypal`) adhering strictly to:
1. Raw Body Preservation: Captures `await request.body()` BEFORE parsing JSON so
   cryptographic signature verification succeeds byte-for-byte.
2. Signature Verification: Calls `paypal_client.verify_webhook_signature(headers, raw_body)`,
   returning HTTP 400 if invalid.
3. Robust Status-Aware Idempotency: Checks `PayPalWebhookEvent` by `event_id` and ONLY
   ignores duplicate events if `status == 'processed'`. Pending or failed events are
   safely retried.
4. Atomic Transactions & Rollbacks: Wraps webhook event logging and `LedgerEngine.settle_hold`
   (with `commit=False`) inside a single atomic `try...except` transaction. On any error,
   executes `await session.rollback()` and returns HTTP 500 so PayPal automatically retries;
   on success, sets `status = 'processed'` and commits atomically.
"""

import json
import logging
from datetime import datetime, timezone
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Ingests, verifies, and atomically settles incoming PayPal Webhook notifications.
    """
    # 1. Raw Body Preservation (MUST precede any JSON parsing)
    raw_body = await request.body()
    headers = dict(request.headers)

    # 2. Cryptographic Signature Verification
    is_valid = await paypal_client.verify_webhook_signature(headers=headers, raw_body=raw_body)
    if not is_valid:
        logger.warning("PayPal Webhook cryptographic signature verification failed.")
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid signature")

    try:
        raw_text = raw_body.decode("utf-8")
        event_data = json.loads(raw_text)
    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid JSON")

    event_id = event_data.get("id")
    event_type = event_data.get("event_type", "UNKNOWN")

    if not event_id:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Missing event id")

    # 3. Robust Status-Aware Idempotency Check
    stmt_existing = select(PayPalWebhookEvent).where(PayPalWebhookEvent.event_id == event_id)
    res_existing = await session.exec(stmt_existing)
    existing_event = res_existing.first()

    if existing_event and existing_event.status == "processed":
        logger.info(f"Duplicate webhook event {event_id} has status='processed'. Ignoring with 200 OK.")
        return {"status": "duplicate_ignored", "event_id": event_id}

    # 4. Atomic Transaction Block (DB Logging + Ledger Settlement + Status Promotion)
    resource = event_data.get("resource", {})
    intent_uuid = None

    try:
        if existing_event:
            webhook_log = existing_event
            webhook_log.event_type = event_type
            webhook_log.payload_json = raw_text
            webhook_log.status = "pending"
            webhook_log.error_message = None
        else:
            webhook_log = PayPalWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload_json=raw_text,
                status="pending",
                error_message=None,
            )
        session.add(webhook_log)
        await session.flush()

        # Event: PAYMENT.CAPTURE.COMPLETED -> Settle atomic hold (`commit=False`)
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            capture_id = resource.get("id")
            custom_id = resource.get("custom_id")
            order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")

            intent = None
            if custom_id:
                try:
                    intent_uuid = UUID(custom_id)
                    stmt_i = select(Intent).where(Intent.id == intent_uuid)
                    intent = (await session.exec(stmt_i)).first()
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse custom_id as UUID: {custom_id}")

            if not intent and order_id:
                stmt_o = select(Intent).where(Intent.paypal_order_id == order_id)
                intent = (await session.exec(stmt_o)).first()
                if intent:
                    intent_uuid = intent.id

            if intent:
                await LedgerEngine.settle_hold(
                    session,
                    intent.id,
                    capture_id or f"CAPTURE-{intent.id}",
                    commit=False,
                )
                intent.status = "settled"
                session.add(intent)
                logger.info(f"Atomically settled hold for intent {intent.id} with capture {capture_id}")

        # Event: PAYMENT.CAPTURE.DENIED / DECLINED -> Release hold (`commit=False`)
        elif event_type in ("PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.DECLINED"):
            custom_id = resource.get("custom_id")
            order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")

            intent = None
            if custom_id:
                try:
                    intent_uuid = UUID(custom_id)
                    stmt_i = select(Intent).where(Intent.id == intent_uuid)
                    intent = (await session.exec(stmt_i)).first()
                except (ValueError, TypeError):
                    pass

            if not intent and order_id:
                stmt_o = select(Intent).where(Intent.paypal_order_id == order_id)
                intent = (await session.exec(stmt_o)).first()

            if intent:
                intent_uuid = intent.id
                await LedgerEngine.release_hold(session, intent.id, commit=False)
                intent.status = "denied"
                session.add(intent)
                logger.info(f"Atomically released hold for denied intent {intent.id}")

        # Event: CHECKOUT.ORDER.APPROVED -> Mark intent approved
        elif event_type == "CHECKOUT.ORDER.APPROVED":
            order_id = resource.get("id")
            if order_id:
                stmt_o = select(Intent).where(Intent.paypal_order_id == order_id)
                intent = (await session.exec(stmt_o)).first()
                if intent:
                    intent_uuid = intent.id
                    if intent.status in ("allowed", "pending", "executing"):
                        intent.status = "approved"
                        session.add(intent)

        # Event: PAYMENT.PAYOUTSBATCH.SUCCESS -> Confirm automated Vault skim / Bill payout
        elif event_type == "PAYMENT.PAYOUTSBATCH.SUCCESS":
            batch_id = resource.get("batch_header", {}).get("payout_batch_id")
            logger.info(f"Confirmed automated PayPal Payout delivery: batch_id={batch_id}")

        # Promote webhook event status to 'processed' and commit atomically
        webhook_log.intent_id = intent_uuid
        webhook_log.status = "processed"
        webhook_log.error_message = None
        webhook_log.processed_at = utc_now()
        session.add(webhook_log)

        await session.commit()
        logger.info(f"Atomically committed webhook event {event_id} ({event_type}) as 'processed'.")

    except Exception as exc:
        await session.rollback()
        logger.error(f"Atomic rollback on webhook event {event_id}: {exc}", exc_info=True)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(exc))

    return {
        "ok": True,
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
    }
