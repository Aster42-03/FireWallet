import json
import uuid
from datetime import date
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.intent import Intent
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.bill import Bill
from app.models.batch_payment import BatchPaymentItem
from app.models.webhook import PayPalWebhookEvent
from app.ledger.engine import LedgerEngine

@pytest.mark.api
async def test_paypal_webhook_capture_completed_settles_hold(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """
    Verify that PAYMENT.CAPTURE.COMPLETED webhook converts a pending ledger hold
    into a settled posted debit and transitions intent status to 'settled'.
    """
    # 1. Fetch user and daily bucket
    stmt_b = select(Bucket).where(Bucket.kind == "daily")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    # 2. Create an executing intent with an active hold
    intent = Intent(
        user_id=bucket.user_id,
        utterance="Groceries at Trader Joe's",
        amount=2500,  # $25.00
        currency="USD",
        category="groceries",
        necessity="daily_living",
        recommended_bucket="daily",
        source_bucket_id=bucket.id,
        status="executing",
        paypal_order_id="ORDER-TEST-WEBHOOK-001"
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    # Place atomic ledger hold
    hold_entry = await LedgerEngine.place_hold(
        session=seeded_session,
        user_id=bucket.user_id,
        bucket_id=bucket.id,
        amount_minor=2500,
        intent_id=intent.id,
        paypal_order_id="ORDER-TEST-WEBHOOK-001"
    )
    assert hold_entry.state == "hold"

    # 3. Construct PayPal webhook payload
    event_id = f"WH-EVENT-{uuid.uuid4()}"
    capture_id = f"CAPTURE-REAL-{uuid.uuid4().hex[:8]}"
    webhook_payload = {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "create_time": "2026-11-07T10:00:00Z",
        "resource_type": "capture",
        "resource": {
            "id": capture_id,
            "status": "COMPLETED",
            "custom_id": str(intent.id),
            "amount": {
                "currency_code": "USD",
                "value": "25.00"
            },
            "supplementary_data": {
                "related_ids": {
                    "order_id": "ORDER-TEST-WEBHOOK-001"
                }
            }
        }
    }

    # 4. Dispatch webhook to API
    resp = await client.post(
        "/api/v1/webhooks/paypal",
        json=webhook_payload,
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["event_id"] == event_id
    assert data["event_type"] == "PAYMENT.CAPTURE.COMPLETED"

    # 5. Verify database reconciliation
    # Intent should be settled
    await seeded_session.refresh(intent)
    assert intent.status == "settled"

    # Hold entry should be converted to posted with capture_id
    stmt_e = select(LedgerEntry).where(LedgerEntry.id == hold_entry.id)
    updated_entry = (await seeded_session.exec(stmt_e)).first()
    assert updated_entry.state == "posted"
    assert updated_entry.paypal_capture_id == capture_id

    # Webhook event must be audited with status='processed'
    stmt_w = select(PayPalWebhookEvent).where(PayPalWebhookEvent.event_id == event_id)
    wh_record = (await seeded_session.exec(stmt_w)).first()
    assert wh_record is not None
    assert wh_record.intent_id == intent.id
    assert wh_record.status == "processed"
    assert wh_record.error_message is None

@pytest.mark.api
async def test_paypal_webhook_idempotency_duplicate_ignored(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """
    Verify that duplicate PayPal webhook deliveries are recognized and ACKed with 200 OK
    without re-processing or raising an error.
    """
    event_id = f"WH-DUP-{uuid.uuid4()}"
    webhook_payload = {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-DUP-001",
            "status": "COMPLETED"
        }
    }

    # First delivery
    resp1 = await client.post("/api/v1/webhooks/paypal", json=webhook_payload)
    assert resp1.status_code == 200
    assert resp1.json()["ok"] is True

    # Duplicate delivery
    resp2 = await client.post("/api/v1/webhooks/paypal", json=webhook_payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "duplicate_ignored"
    assert data2["event_id"] == event_id

@pytest.mark.api
async def test_paypal_webhook_capture_denied_releases_hold(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """
    Verify that PAYMENT.CAPTURE.DENIED webhook releases the hold and marks intent as denied.
    """
    stmt_b = select(Bucket).where(Bucket.kind == "daily")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    intent = Intent(
        user_id=bucket.user_id,
        utterance="Declined Card Spend",
        amount=1500,
        currency="USD",
        source_bucket_id=bucket.id,
        status="executing"
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    hold_entry = await LedgerEngine.place_hold(
        session=seeded_session,
        user_id=bucket.user_id,
        bucket_id=bucket.id,
        amount_minor=1500,
        intent_id=intent.id
    )

    event_id = f"WH-DENIED-{uuid.uuid4()}"
    webhook_payload = {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.DENIED",
        "resource": {
            "id": "CAPTURE-DENIED-001",
            "custom_id": str(intent.id)
        }
    }

    resp = await client.post("/api/v1/webhooks/paypal", json=webhook_payload)
    assert resp.status_code == 200

    await seeded_session.refresh(intent)
    assert intent.status == "denied"

    await seeded_session.refresh(hold_entry)
    assert hold_entry.state == "released"

@pytest.mark.api
async def test_paypal_webhook_checkout_order_approved(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """
    Verify that CHECKOUT.ORDER.APPROVED webhook transitions intent status to 'approved'.
    """
    stmt_b = select(Bucket).where(Bucket.kind == "freedom")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    order_id = f"ORDER-APPROVED-{uuid.uuid4().hex[:8]}"
    intent = Intent(
        user_id=bucket.user_id,
        utterance="Concert ticket",
        amount=5000,
        currency="USD",
        source_bucket_id=bucket.id,
        status="executing",
        paypal_order_id=order_id
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    event_id = f"WH-APPROVE-{uuid.uuid4()}"
    webhook_payload = {
        "id": event_id,
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {
            "id": order_id
        }
    }

    resp = await client.post("/api/v1/webhooks/paypal", json=webhook_payload)
    assert resp.status_code == 200

    await seeded_session.refresh(intent)
    assert intent.status == "approved"

@pytest.mark.api
async def test_paypal_webhook_invalid_payload(client: httpx.AsyncClient):
    """
    Verify that malformed or non-JSON payloads are rejected with 400 Bad Request.
    """
    resp = await client.post(
        "/api/v1/webhooks/paypal",
        content=b"not a valid json string",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400


@pytest.mark.api
async def test_paypal_webhook_rejects_invalid_signature(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch
):
    """
    Verify raw body bytes are passed to signature verification and HTTP 400 is returned when invalid.
    """
    from app.services.paypal_client import paypal_client

    captured_raw: list[bytes] = []

    async def fake_verify(headers: dict, raw_body: bytes) -> bool:
        captured_raw.append(raw_body)
        return False

    monkeypatch.setattr(paypal_client, "verify_webhook_signature", fake_verify)

    raw_bytes = b'{"id":"WH-BAD-SIG","event_type":"PAYMENT.CAPTURE.COMPLETED"}'
    resp = await client.post(
        "/api/v1/webhooks/paypal",
        content=raw_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert captured_raw == [raw_bytes]


@pytest.mark.api
async def test_paypal_webhook_retries_pending_event_and_ignores_once_processed(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """
    Verify status-aware idempotency: a pre-existing event with status='pending' or 'failed'
    is NOT ignored, settles cleanly to 'processed', and is only ignored on subsequent replays.
    """
    event_id = f"WH-PENDING-{uuid.uuid4()}"
    pending_ev = PayPalWebhookEvent(
        event_id=event_id,
        event_type="PAYMENT.CAPTURE.COMPLETED",
        payload_json="{}",
        status="pending",
    )
    seeded_session.add(pending_ev)
    await seeded_session.commit()

    payload = {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"id": "CAPTURE-RETRY-001", "status": "COMPLETED"},
    }

    # First delivery against 'pending' row -> must process and promote to 'processed'
    resp1 = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["ok"] is True
    assert resp1.json()["status"] == "processed"

    await seeded_session.refresh(pending_ev)
    assert pending_ev.status == "processed"

    # Second delivery now that status == 'processed' -> duplicate_ignored
    resp2 = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate_ignored"


@pytest.mark.api
async def test_paypal_webhook_atomic_rollback_and_500_on_settlement_error(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch
):
    """
    Verify that if LedgerEngine.settle_hold raises an error, the transaction rolls back
    atomically and returns HTTP 500 so PayPal retries delivery cleanly.
    """
    stmt_b = select(Bucket).where(Bucket.kind == "daily")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    intent = Intent(
        user_id=bucket.user_id,
        utterance="Atomic rollback test spend",
        short_tag="groceries",
        amount=1200,
        currency="USD",
        source_bucket_id=bucket.id,
        status="executing",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    hold_entry = await LedgerEngine.place_hold(
        session=seeded_session,
        user_id=bucket.user_id,
        bucket_id=bucket.id,
        amount_minor=1200,
        intent_id=intent.id,
    )

    real_settle = LedgerEngine.settle_hold

    async def failing_settle(*args, **kwargs):
        raise RuntimeError("Simulated DB failure during settle_hold")

    monkeypatch.setattr(LedgerEngine, "settle_hold", failing_settle)

    event_id = f"WH-ROLLBACK-{uuid.uuid4()}"
    payload = {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"id": "CAP-FAIL-1", "custom_id": str(intent.id)},
    }

    # 1. Failing attempt must return HTTP 500 and roll back webhook log + hold state
    resp_fail = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp_fail.status_code == 500

    stmt_w = select(PayPalWebhookEvent).where(PayPalWebhookEvent.event_id == event_id)
    assert (await seeded_session.exec(stmt_w)).first() is None

    await seeded_session.refresh(hold_entry)
    assert hold_entry.state == "hold"

    # 2. Restore settle_hold -> PayPal retry succeeds atomically!
    monkeypatch.setattr(LedgerEngine, "settle_hold", real_settle)
    resp_ok = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "processed"

    await seeded_session.refresh(hold_entry)
    assert hold_entry.state == "posted"


@pytest.mark.api
async def test_paypal_webhook_payouts_batch_success_promotes_items(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verify that PAYMENT.PAYOUTSBATCH.SUCCESS webhook updates BatchPaymentItem
    and linked Bill records to 'paid'.
    """
    stmt_b = select(Bucket).where(Bucket.kind == "bills")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    batch_id = f"PAYOUT-WH-{uuid.uuid4().hex[:12]}"
    bill = Bill(
        user_id=bucket.user_id,
        name="Quarterly Insurance",
        amount=22000,
        due_date=date(2026, 12, 1),
        payee_email="insurance@sandbox.paypal.com",
        status="scheduled",
    )
    seeded_session.add(bill)
    await seeded_session.commit()
    await seeded_session.refresh(bill)

    item = BatchPaymentItem(
        user_id=bucket.user_id,
        bill_id=bill.id,
        title="Quarterly Insurance",
        amount_minor=22000,
        source_bucket="bills",
        status="executing",
        paypal_payout_id=batch_id,
    )
    seeded_session.add(item)
    await seeded_session.commit()
    await seeded_session.refresh(item)

    event_id = f"WH-PAYOUT-SUCCESS-{uuid.uuid4()}"
    payload = {
        "id": event_id,
        "event_type": "PAYMENT.PAYOUTSBATCH.SUCCESS",
        "resource": {
            "batch_header": {
                "payout_batch_id": batch_id,
                "batch_status": "SUCCESS"
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    await seeded_session.refresh(item)
    await seeded_session.refresh(bill)
    assert item.status == "paid"
    assert bill.status == "paid"
    assert bill.last_payout_batch_id == batch_id


@pytest.mark.api
async def test_paypal_webhook_payouts_batch_denied_marks_failed(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verify that PAYMENT.PAYOUTSBATCH.DENIED webhook updates BatchPaymentItem
    records to 'failed'.
    """
    stmt_b = select(Bucket).where(Bucket.kind == "bills")
    bucket = (await seeded_session.exec(stmt_b)).first()
    assert bucket is not None

    batch_id = f"PAYOUT-WH-DENY-{uuid.uuid4().hex[:12]}"
    item = BatchPaymentItem(
        user_id=bucket.user_id,
        title="Denied Server Bill",
        amount_minor=8500,
        source_bucket="bills",
        status="executing",
        paypal_payout_id=batch_id,
    )
    seeded_session.add(item)
    await seeded_session.commit()
    await seeded_session.refresh(item)

    event_id = f"WH-PAYOUT-DENIED-{uuid.uuid4()}"
    payload = {
        "id": event_id,
        "event_type": "PAYMENT.PAYOUTSBATCH.DENIED",
        "resource": {
            "batch_header": {
                "payout_batch_id": batch_id,
                "batch_status": "DENIED"
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/paypal", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    await seeded_session.refresh(item)
    assert item.status == "failed"
    assert "denied" in item.error_message.lower()
