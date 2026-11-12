"""
PayPal Orders v2 Interactive Checkout & Buyer Approval Loop Test Suite
=====================================================================
Verifies:
1. Interactive Checkout Flow (Option 1):
   - Backend calls create_order with custom return_url / cancel_url.
   - Returns approval_url pointing to PayPal sandbox checkout.
   - Payer approval is required before capture.
2. Robust Guard: Capture endpoint rejects unapproved orders (ORDER_NOT_APPROVED)
   with HTTP 422 and leaves database / ledger untouched.
3. Database Confirmation: Hold is ONLY converted to settled after PayPal confirms
   COMPLETED status.
4. Order status endpoint (`GET /api/v1/intents/{intent_id}/order-status`) accurately
   reports live status.
"""

from typing import Dict, Any
from uuid import uuid4
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User
from app.models.intent import Intent
from app.models.ledger import LedgerEntry
from app.services.paypal_client import paypal_client


@pytest.mark.api
async def test_execute_intent_creates_order_and_returns_approval_url(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verifies that calling POST /api/v1/intents/{id}/execute creates a PayPal order,
    places a hold on the source bucket, and returns an approval_url.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Lunch at Chipotle",
        amount=1500,
        currency="USD",
        category="eating_out",
        necessity="freedom",
        recommended_bucket="freedom",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    return_url = f"http://localhost:5173/?paypal_return=true&intent_id={intent.id}"
    resp = await client.post(
        f"/api/v1/intents/{intent.id}/execute",
        json={"return_url": return_url, "cancel_url": "http://localhost:5173/?paypal_cancel=true"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "executing"
    assert data["paypal_order_id"] is not None
    assert "https://www.sandbox.paypal.com/checkoutnow" in data["approval_url"]

    # Verify hold was placed
    hold_stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.intent_id == intent.id)
        .where(LedgerEntry.state == "hold")
    )
    hold = (await seeded_session.exec(hold_stmt)).first()
    assert hold is not None
    assert hold.amount == -1500


@pytest.mark.api
async def test_capture_intent_fails_when_unapproved_and_preserves_database(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Verifies that if PayPal returns ORDER_NOT_APPROVED, the backend returns HTTP 422
    and DOES NOT settle the ledger hold or mark the intent as settled in the database.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Movie ticket",
        amount=2000,
        currency="USD",
        category="entertainment",
        necessity="freedom",
        recommended_bucket="freedom",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    # Execute to create order & hold
    exec_resp = await client.post(f"/api/v1/intents/{intent.id}/execute")
    order_id = exec_resp.json()["paypal_order_id"]

    # Simulate PayPal live response returning ORDER_NOT_APPROVED
    async def mock_capture_unapproved(order_id: str, intent_id: str) -> Dict[str, Any]:
        raise ValueError(
            "ORDER_NOT_APPROVED: Payer has not yet approved the Order on PayPal checkout. "
            "Please log in with your Sandbox Personal Buyer account and click Agree/Continue before capturing."
        )

    monkeypatch.setattr(paypal_client, "capture_order", mock_capture_unapproved)

    # Attempt capture before buyer approval
    cap_resp = await client.post(
        f"/api/v1/intents/{intent.id}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 422, cap_resp.text
    assert "ORDER_NOT_APPROVED" in cap_resp.text

    # CRITICAL CHECK: Verify database was NOT settled
    await seeded_session.refresh(intent)
    assert intent.status == "executing", f"Intent was erroneously marked '{intent.status}'!"

    # Verify hold remains active and NOT posted
    hold_stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.intent_id == intent.id)
        .where(LedgerEntry.state == "hold")
    )
    hold = (await seeded_session.exec(hold_stmt)).first()
    assert hold is not None, "Hold was erroneously removed or settled!"
    assert hold.state == "hold"


@pytest.mark.api
async def test_capture_intent_succeeds_when_approved_and_settles_database(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Verifies that when PayPal confirms the transaction has completed, the hold is
    atomically settled in the ledger and the intent is marked 'settled' in the database.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Groceries at Trader Joe's",
        amount=3500,
        currency="USD",
        category="groceries",
        necessity="daily_living",
        recommended_bucket="daily",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    exec_resp = await client.post(f"/api/v1/intents/{intent.id}/execute")
    order_id = exec_resp.json()["paypal_order_id"]

    # Simulate PayPal confirming payment completed
    real_capture_id = f"CAPTURE-SANDBOX-{uuid4().hex[:8]}"
    async def mock_capture_success(order_id: str, intent_id: str) -> Dict[str, Any]:
        return {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {"id": real_capture_id, "status": "COMPLETED", "amount": {"value": "35.00", "currency_code": "USD"}}
                        ]
                    }
                }
            ],
        }

    monkeypatch.setattr(paypal_client, "capture_order", mock_capture_success)

    cap_resp = await client.post(
        f"/api/v1/intents/{intent.id}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 200, cap_resp.text
    cap_data = cap_resp.json()
    assert cap_data["status"] == "settled"
    assert cap_data["paypal_capture_id"] == real_capture_id

    # Verify intent status in database
    await seeded_session.refresh(intent)
    assert intent.status == "settled"

    # Verify ledger hold was converted to posted with capture_id
    posted_stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.intent_id == intent.id)
        .where(LedgerEntry.state == "posted")
    )
    posted = (await seeded_session.exec(posted_stmt)).first()
    assert posted is not None
    assert posted.paypal_capture_id == real_capture_id


@pytest.mark.api
async def test_get_order_status_endpoint(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Verifies that GET /api/v1/intents/{intent_id}/order-status returns the live
    approval state from PayPal Orders v2.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Concert ticket",
        amount=5000,
        currency="USD",
        category="entertainment",
        necessity="freedom",
        recommended_bucket="freedom",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    await client.post(f"/api/v1/intents/{intent.id}/execute")

    # Mock PayPal returning APPROVED
    async def mock_get_order(order_id: str) -> Dict[str, Any]:
        return {
            "id": order_id,
            "status": "APPROVED",
            "payer": {"payer_id": "PAYER-12345", "email_address": "buyer@personal.example.com"},
            "links": [
                {"rel": "approve", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"}
            ]
        }

    monkeypatch.setattr(paypal_client, "get_order", mock_get_order)

    status_resp = await client.get(f"/api/v1/intents/{intent.id}/order-status")
    assert status_resp.status_code == 200, status_resp.text
    status_data = status_resp.json()
    assert status_data["order_status"] == "APPROVED"
    assert status_data["payer_id"] == "PAYER-12345"


@pytest.mark.api
async def test_paypal_order_id_captured_in_deep_analytics_ag_grid(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    BUG-012 Verification:
    Verify that when an intent is executed and captured via PayPal Orders v2:
    1. The PayPal Order ID is immediately attached to the LedgerEntry hold record.
    2. Upon capture, both paypal_order_id and paypal_capture_id are persisted on LedgerEntry.
    3. The Deep Analytics endpoint (/analytics/deep-ledger) powering the AG Grid workbench
       returns both paypal_order_id and paypal_capture_id on the item rows.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Weekend grocery run at Whole Foods",
        amount=4200,
        currency="USD",
        category="groceries",
        necessity="daily_living",
        recommended_bucket="daily",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    # 1. Execute intent -> creates PayPal Order & hold
    exec_resp = await client.post(f"/api/v1/intents/{intent.id}/execute")
    assert exec_resp.status_code == 200, exec_resp.text
    order_id = exec_resp.json()["paypal_order_id"]
    assert order_id is not None

    # Check hold entry directly in DB
    hold_entry = (
        await seeded_session.exec(
            select(LedgerEntry)
            .where(LedgerEntry.intent_id == intent.id)
            .where(LedgerEntry.state == "hold")
        )
    ).first()
    assert hold_entry is not None
    assert hold_entry.paypal_order_id == order_id, "paypal_order_id was not propagated to hold entry!"

    # 2. Complete capture
    expected_capture_id = f"CAPTURE-AG-GRID-{uuid4().hex[:8]}"
    async def mock_capture_success(order_id: str, intent_id: str) -> Dict[str, Any]:
        return {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {"id": expected_capture_id, "status": "COMPLETED", "amount": {"value": "42.00", "currency_code": "USD"}}
                        ]
                    }
                }
            ],
        }

    monkeypatch.setattr(paypal_client, "capture_order", mock_capture_success)

    cap_resp = await client.post(
        f"/api/v1/intents/{intent.id}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 200, cap_resp.text

    # 3. Query Deep Analytics endpoint powering AG Grid
    deep_resp = await client.get("/api/v1/analytics/deep-ledger?limit=50")
    assert deep_resp.status_code == 200, deep_resp.text
    deep_data = deep_resp.json()

    # Find the settled grocery row
    matched_item = next(
        (it for it in deep_data["items"] if it["id"] == str(hold_entry.id)),
        None
    )
    assert matched_item is not None, "Ledger row not found in Deep Analytics response!"
    assert matched_item["paypal_order_id"] == order_id, f"Expected order_id {order_id}, got {matched_item.get('paypal_order_id')}"
    assert matched_item["paypal_capture_id"] == expected_capture_id, f"Expected capture_id {expected_capture_id}, got {matched_item.get('paypal_capture_id')}"
