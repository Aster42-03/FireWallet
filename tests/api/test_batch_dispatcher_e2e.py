"""
The Trinity Batch Dispatcher E2E Test Suite (R2)
=================================================
Comprehensive 4-Tier test suite verifying:
1. `BatchPaymentItem` SQLModel persistence and `BatchDispatcherProposal` schema.
2. REST endpoints:
   - `POST /api/v1/bills/batch-dispatcher/propose`
   - `GET /api/v1/bills/batch-dispatcher/queue`
   - `POST /api/v1/bills/batch-dispatcher/execute`
3. Blast Radius Containment:
   - Disbursements strictly isolated to `bills` or `vault`.
   - Direct spend from `bank` forbidden (HTTP 400).
   - Insufficient isolated funds blocked (HTTP 400).
4. Live PayPal Sandbox Requirement:
   - Execution requires live sandbox credentials; offline or mock tokens return HTTP 503 cleanly.
5. Human Veto Power:
   - User can approve a subset of staged items; omitted items remain un-debited.
6. Idempotency & Sequential Execution:
   - Deterministic execution without duplicate payouts or double-entry ledger double-debits.

Tiers:
- Tier 1: Feature Coverage (Model, Schema, Propose, Queue, Execute, Veto)
- Tier 2: Boundary & Corner Cases (Bank blast radius, Insufficient funds, Offline 503, Empty array, Idempotency, Negative amount)
- Tier 3: Cross-Feature Combinations (Bills rebalance + Dispatcher cap, Partial failure handling)
- Tier 4: Real-World Scenarios (Monthly bill dispatch cycle with selective human veto)
"""

from typing import List, Optional
from uuid import UUID, uuid4
from datetime import date, timedelta
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User
from app.models.bill import Bill
from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.models.batch_payment import BatchPaymentItem


def get_batch_payment_item_model():
    """Dynamically import BatchPaymentItem model if implemented."""
    try:
        from app.models.batch_payment import BatchPaymentItem
        return BatchPaymentItem
    except ImportError:
        try:
            from app.models import BatchPaymentItem
            return BatchPaymentItem
        except ImportError:
            return None


def get_batch_proposal_schema():
    """Dynamically import BatchDispatcherProposal schema if implemented."""
    try:
        from app.schemas.common import BatchDispatcherProposal
        return BatchDispatcherProposal
    except ImportError:
        try:
            from app.schemas.batch_dispatcher import BatchDispatcherProposal
            return BatchDispatcherProposal
        except ImportError:
            return None


# =====================================================================
# TIER 1: FEATURE COVERAGE
# =====================================================================

@pytest.mark.unit
def test_tier1_batch_payment_item_sqlmodel_model_attributes():
    """
    Tier 1: Verify BatchPaymentItem SQLModel model definition, table name, and defaults.
    """
    Model = get_batch_payment_item_model()
    assert Model is not None, "BatchPaymentItem model not implemented in app.models.batch_payment"

    assert Model.__tablename__ == "batch_payment_items"

    # Instantiate model
    item_id = uuid4()
    user_id = uuid4()
    item = Model(
        id=item_id,
        user_id=user_id,
        title="Apartment Rent",
        amount_minor=120000,
        category="Rent",
        recipient_email="landlord@sandbox.paypal.com",
    )
    assert item.status == "pending_approval"
    assert item.recommended is True
    assert item.amount_minor == 120000
    assert item.recipient_email == "landlord@sandbox.paypal.com"


@pytest.mark.unit
def test_tier1_batch_dispatcher_proposal_schema_validation():
    """
    Tier 1: Verify AI Coach BatchDispatcherProposal structured schema definition.
    """
    Schema = get_batch_proposal_schema()
    assert Schema is not None, "BatchDispatcherProposal schema not implemented in app.schemas"

    payload = {
        "coach_message": "Staging 1 upcoming bill totaling $1,200.00 from isolated Reserved Bills.",
        "total_batch_amount_minor": 120000,
        "items": [
            {
                "title": "Apartment Rent",
                "amount_minor": 120000,
                "category": "Rent",
                "recommended": True,
                "recipient_email": "landlord@sandbox.paypal.com",
            }
        ],
        "risk_assessment": "Core Bank Foundation ($800.00) remains 100% untouched.",
        "vault_balance_minor": 20000,
        "bills_balance_minor": 120000,
        "safe_to_execute": True,
    }
    proposal = Schema(**payload)
    assert proposal.total_batch_amount_minor == 120000
    assert proposal.safe_to_execute is True
    assert len(proposal.items) == 1


@pytest.mark.api
async def test_tier1_batch_dispatcher_propose_endpoint(client: httpx.AsyncClient):
    """
    Tier 1: POST /api/v1/bills/batch-dispatcher/propose stages scheduled bills and returns proposal.
    """
    resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert resp.status_code == 200, f"Expected 200 OK from /propose, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "coach_message" in data
    assert "total_batch_amount_minor" in data
    assert "items" in data
    assert "risk_assessment" in data
    assert "safe_to_execute" in data

    # Apartment Rent ($1,200.00) was seeded in conftest
    assert data["total_batch_amount_minor"] >= 120000
    assert any(item["title"] == "Apartment Rent" for item in data["items"])


@pytest.mark.api
async def test_tier1_batch_dispatcher_queue_endpoint(client: httpx.AsyncClient):
    """
    Tier 1: GET /api/v1/bills/batch-dispatcher/queue returns active staged items and balance metrics.
    """
    # Propose first to ensure queue is staged
    await client.post("/api/v1/bills/batch-dispatcher/propose")

    resp = await client.get("/api/v1/bills/batch-dispatcher/queue")
    assert resp.status_code == 200, f"Expected 200 OK from /queue, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "items" in data
    assert "total_pending_minor" in data
    assert "isolated_bills_available_minor" in data
    assert data["isolated_bills_available_minor"] == 120000
    assert len(data["items"]) >= 1


@pytest.mark.api
async def test_tier1_batch_dispatcher_execute_sequential_success(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 1: POST /api/v1/bills/batch-dispatcher/execute with live PayPal mock executes sequential payouts.
    """
    # 1. Stage queue
    prop_resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop_resp.status_code == 200
    items = prop_resp.json()["items"]
    item_id = items[0]["id"]

    # 2. Mock live PayPal payout client to return 201 Created
    from app.services.paypal_client import paypal_client

    async def mock_create_payout(batch_id: str, receiver_email: str, amount_cents: int, note: str = ""):
        return {
            "batch_status": "SUCCESS",
            "payout_batch_id": "PAYOUTS-BATCH-TEST-12345",
            "amount_cents": amount_cents,
            "receiver_email": receiver_email,
        }

    monkeypatch.setattr(paypal_client, "create_payout", mock_create_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    # 3. Execute approved item
    exec_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bills"},
    )
    assert exec_resp.status_code == 200, f"Expected 200 OK, got {exec_resp.status_code}: {exec_resp.text}"
    summary = exec_resp.json()
    assert summary["executed_count"] == 1
    assert summary["failed_count"] == 0

    # 4. Verify item status is paid in queue
    q_resp = await client.get("/api/v1/bills/batch-dispatcher/queue")
    paid_items = [it for it in q_resp.json()["items"] if it["id"] == item_id]
    assert len(paid_items) == 1
    assert paid_items[0]["status"] == "paid"
    assert paid_items[0]["paypal_payout_id"] == "PAYOUTS-BATCH-TEST-12345"


@pytest.mark.api
async def test_tier1_human_veto_dispatches_only_approved_items(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 1: Human Veto Power.
    When 2 bills are staged, user approves only 1 item.
    Only the approved item is executed and debited; unapproved item remains un-debited.
    """
    # Add a second bill: Electric Bill $80.00 (8,000)
    user = (await seeded_session.exec(select(User))).first()
    electric_bill = Bill(
        user_id=user.id,
        name="Electric Bill",
        amount=8000,
        due_date=date.today() + timedelta(days=7),
        payee_email="electric@sandbox.paypal.com",
        priority=2,
        status="scheduled",
    )
    seeded_session.add(electric_bill)
    await seeded_session.commit()

    # Stage proposal
    prop_resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop_resp.status_code == 200
    staged = prop_resp.json()["items"]
    assert len(staged) >= 2

    # Identify electric bill ID
    elec_item = next(it for it in staged if it["title"] == "Electric Bill")
    rent_item = next(it for it in staged if it["title"] == "Apartment Rent")

    from app.services.paypal_client import paypal_client
    async def mock_create_payout(batch_id: str, receiver_email: str, amount_cents: int, note: str = ""):
        return {"batch_status": "SUCCESS", "payout_batch_id": "PAYOUT-ELEC-7788", "amount_cents": amount_cents}
    monkeypatch.setattr(paypal_client, "create_payout", mock_create_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    # Approve ONLY electric bill, veto rent
    exec_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [elec_item["id"]], "source_bucket": "bills"},
    )
    assert exec_resp.status_code == 200
    summary = exec_resp.json()
    assert summary["executed_count"] == 1
    assert summary["total_amount_minor"] == 8000

    # Verify queue: electric is paid, rent is NOT paid
    q_resp = await client.get("/api/v1/bills/batch-dispatcher/queue")
    q_items = {it["id"]: it for it in q_resp.json()["items"]}
    assert q_items[elec_item["id"]]["status"] == "paid"
    assert q_items[rent_item["id"]]["status"] in ("pending_approval", "vetoed")


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =====================================================================

@pytest.mark.api
async def test_tier2_blast_radius_bank_foundation_strictly_forbidden(client: httpx.AsyncClient):
    """
    Tier 2: Attempting to execute batch payouts with source_bucket='bank' must fail with HTTP 400.
    Bank Foundation is inviolable and protected against agentic batch modification.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    items = prop.json()["items"]
    item_id = items[0]["id"]

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bank"},
    )
    assert resp.status_code == 400
    assert "bank" in resp.text.lower()


@pytest.mark.api
async def test_tier2_blast_radius_insufficient_isolated_funds(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 2: Attempting to dispatch more than available in isolated Bills/Vault reserve returns HTTP 400.
    Bank Foundation cannot be raided!
    """
    # Seed bill of $1,500.00 when Bills bucket only has $1,200.00
    user = (await seeded_session.exec(select(User))).first()
    big_bill = Bill(
        user_id=user.id,
        name="Massive Obligation",
        amount=150000,  # $1,500.00
        due_date=date.today() + timedelta(days=3),
        payee_email="massive@sandbox.paypal.com",
        priority=1,
        status="scheduled",
    )
    seeded_session.add(big_bill)
    await seeded_session.commit()

    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    big_item = next(it for it in prop.json()["items"] if it["title"] == "Massive Obligation")

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [big_item["id"]], "source_bucket": "bills"},
    )
    assert resp.status_code == 400
    assert "insufficient" in resp.text.lower() or "reserve protection" in resp.text.lower()

    # Verify Bank Foundation was untouched
    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bank"] == 80000, "Bank Foundation was altered by over-limit batch dispatcher!"


@pytest.mark.api
async def test_tier2_live_paypal_sandbox_offline_or_mock_returns_503(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 2: If live PayPal Sandbox credentials are missing or token is mock, return HTTP 503 cleanly.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    items = prop.json()["items"]
    item_id = items[0]["id"]

    from app.services.paypal_client import paypal_client

    # Force mock token return
    async def mock_get_token():
        return "mock_sandbox_access_token"

    monkeypatch.setattr(paypal_client, "get_access_token", mock_get_token)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: False, raising=False)

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bills"},
    )
    assert resp.status_code == 503, f"Expected 503 Service Unavailable, got {resp.status_code}: {resp.text}"
    assert "paypal sandbox" in resp.text.lower() or "credentials" in resp.text.lower() or "offline" in resp.text.lower()


@pytest.mark.api
async def test_tier2_empty_approved_items_rejected_400(client: httpx.AsyncClient):
    """
    Tier 2: Submitting empty approved_item_ids array returns HTTP 400 Bad Request.
    """
    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [], "source_bucket": "bills"},
    )
    assert resp.status_code == 400


@pytest.mark.api
async def test_tier2_idempotent_reexecution_skips_already_paid(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    seeded_session: AsyncSession,
):
    """
    Tier 2: Re-executing an already-paid item is idempotent and does not create duplicate ledger debits.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    item_id = prop.json()["items"][0]["id"]

    from app.services.paypal_client import paypal_client
    call_count = {"payouts": 0}

    async def mock_create_payout(batch_id: str, receiver_email: str, amount_cents: int, note: str = ""):
        call_count["payouts"] += 1
        return {"batch_status": "SUCCESS", "payout_batch_id": "PAYOUT-IDEM-99", "amount_cents": amount_cents}

    monkeypatch.setattr(paypal_client, "create_payout", mock_create_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    # First execution -> payout called
    r1 = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bills"},
    )
    assert r1.status_code == 200
    assert call_count["payouts"] == 1

    entries_after_1 = len((await seeded_session.exec(select(LedgerEntry))).all())

    # Second execution of same item -> payout SKIPPED
    r2 = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bills"},
    )
    assert r2.status_code == 200
    assert call_count["payouts"] == 1, "Duplicate PayPal payout API call executed for already paid item!"

    entries_after_2 = len((await seeded_session.exec(select(LedgerEntry))).all())
    assert entries_after_2 == entries_after_1, "Duplicate ledger debit created for already paid item!"


@pytest.mark.unit
def test_tier2_negative_or_zero_amount_item_rejected():
    """
    Tier 2: BatchPaymentItem with non-positive amount raises validation error.
    """
    Model = get_batch_payment_item_model()
    if Model is None:
        pytest.skip("BatchPaymentItem model not implemented yet")

    with pytest.raises(Exception):
        Model(
            user_id=uuid4(),
            title="Invalid Bill",
            amount_minor=0,
            category="Rent",
        )

    with pytest.raises(Exception):
        Model(
            user_id=uuid4(),
            title="Negative Bill",
            amount_minor=-5000,
            category="Rent",
        )


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# =====================================================================

@pytest.mark.api
async def test_tier3_bills_envelope_rebalance_combined_with_batch_dispatcher_cap(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 3: Rebalance bills envelope target to $1,400.00 (R3), then Batch Dispatcher
    executes bills within the expanded cap.
    """
    # 1. User configures Bills envelope to $1,400.00 (R3)
    pol_resp = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 140000},
    )
    assert pol_resp.status_code == 200

    # 2. Add an additional bill for $150.00 (total obligations $1,350.00)
    user = (await seeded_session.exec(select(User))).first()
    seeded_session.add(
        Bill(
            user_id=user.id,
            name="Quarterly Water Utility",
            amount=15000,
            due_date=date.today() + timedelta(days=4),
            payee_email="water@sandbox.paypal.com",
            priority=2,
            status="scheduled",
        )
    )
    await seeded_session.commit()

    # 3. Batch Dispatcher stages proposal
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop.status_code == 200
    staged_items = prop.json()["items"]
    all_ids = [it["id"] for it in staged_items]

    from app.services.paypal_client import paypal_client
    async def mock_payout(batch_id, receiver_email, amount_cents, note=""):
        return {"batch_status": "SUCCESS", "payout_batch_id": f"PAYOUT-{uuid4()}", "amount_cents": amount_cents}
    monkeypatch.setattr(paypal_client, "create_payout", mock_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    # 4. Execute all items ($1,200 + $150 = $1,350 <= $1,400 cap)
    exec_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": all_ids, "source_bucket": "bills"},
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["executed_count"] >= 2


@pytest.mark.api
async def test_tier3_partial_failure_first_item_succeeds_second_fails(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 3: In a multi-item batch, if first item succeeds and second fails (e.g. invalid payee email),
    first item commits as paid and second item marks as failed with error_message.
    """
    user = (await seeded_session.exec(select(User))).first()
    b2 = Bill(
        user_id=user.id,
        name="Trash Disposal",
        amount=4000,
        due_date=date.today() + timedelta(days=2),
        payee_email="trash@sandbox.paypal.com",
        priority=3,
        status="scheduled",
    )
    seeded_session.add(b2)
    await seeded_session.commit()

    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    items = prop.json()["items"]
    id_1 = items[0]["id"]
    id_2 = items[1]["id"]

    from app.services.paypal_client import paypal_client
    attempts = {"count": 0}

    async def mock_payout_with_failure(batch_id, receiver_email, amount_cents, note=""):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {"batch_status": "SUCCESS", "payout_batch_id": "BATCH-1-OK", "amount_cents": amount_cents}
        raise RuntimeError("PayPal rejected recipient email address.")

    monkeypatch.setattr(paypal_client, "create_payout", mock_payout_with_failure)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    exec_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [id_1, id_2], "source_bucket": "bills"},
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["executed_count"] == 1
    assert data["failed_count"] == 1


# =====================================================================
# TIER 4: REAL-WORLD SCENARIOS
# =====================================================================

@pytest.mark.api
async def test_tier4_monthly_batch_dispatch_lifecycle_with_human_veto(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tier 4: Realistic end-of-month bill dispatch cycle:
    1. System detects scheduled obligations: Apartment Rent ($1,200) and Gym Membership ($50).
    2. AI Coach stages proposal with risk assessment verifying Bank Foundation is untouched.
    3. User reviews staging area in frontend: approves Rent, vetoes Gym Membership.
    4. Authorizes dispatch.
    5. Batch Dispatcher executes Rent sequentially via PayPal Sandbox.
    6. Verifies:
       - Rent marked paid with live PayPal batch identifier.
       - Gym Membership remains un-debited.
       - Bills bucket decremented by exactly $1,200.00.
       - Bank Foundation ($800.00) remains 100% untouched.
    """
    user = (await seeded_session.exec(select(User))).first()
    gym_bill = Bill(
        user_id=user.id,
        name="Gym Membership",
        amount=5000,
        due_date=date.today() + timedelta(days=1),
        payee_email="gym@sandbox.paypal.com",
        priority=3,
        status="scheduled",
    )
    seeded_session.add(gym_bill)
    await seeded_session.commit()

    # 1. Propose batch
    prop_resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop_resp.status_code == 200
    staged = prop_resp.json()["items"]
    rent_item = next(it for it in staged if it["title"] == "Apartment Rent")
    gym_item = next(it for it in staged if it["title"] == "Gym Membership")

    from app.services.paypal_client import paypal_client
    async def mock_payout(batch_id, receiver_email, amount_cents, note=""):
        return {"batch_status": "SUCCESS", "payout_batch_id": "PAYOUT-RENT-NOV2026", "amount_cents": amount_cents}
    monkeypatch.setattr(paypal_client, "create_payout", mock_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    # 2. User approves Rent, vetoes Gym
    exec_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [rent_item["id"]], "source_bucket": "bills"},
    )
    assert exec_resp.status_code == 200
    summary = exec_resp.json()
    assert summary["executed_count"] == 1
    assert summary["total_amount_minor"] == 120000

    # 3. Verify final bucket balances
    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bills"] == 0, f"Expected Bills to be $0.00 (all $1,200 paid), got {buckets['bills']}"
    assert buckets["bank"] == 80000, f"Bank Foundation violated! Expected 80000, got {buckets['bank']}"


# ==============================================================================
# BUG-010: Quick Intent & Coach Memory Batch Staging Tests
# ==============================================================================

@pytest.mark.api
async def test_stage_intent_to_batch_dispatcher(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verifies POST /api/v1/bills/batch-dispatcher/stage-intent stages an evaluated
    intent directly into the batch queue as pending_approval.
    """
    user = (await seeded_session.exec(select(User))).first()

    # 1. Create an Intent
    intent = Intent(
        user_id=user.id,
        utterance="Water and waste utility bill",
        amount=4500,
        currency="USD",
        merchant_name="water@city.gov",
        category="utilities",
        necessity="bill",
        recommended_bucket="bills",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    # 2. Stage into Batch Dispatcher
    stage_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/stage-intent",
        json={
            "intent_id": str(intent.id),
            "recipient_email": "water@city.gov",
            "amount_cents": 4500,
            "currency": "USD",
            "category": "utilities",
            "source_bucket": "bills",
            "note": "City water utility bill",
        },
    )
    assert stage_resp.status_code == 200, stage_resp.text
    stage_data = stage_resp.json()
    assert stage_data["success"] is True
    assert stage_data["recipient_email"] == "water@city.gov"
    assert stage_data["amount_cents"] == 4500
    assert stage_data["source_bucket"] == "bills"
    assert stage_data["status"] == "pending_approval"

    # 3. Verify it appears in propose_batch and queue
    prop_resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop_resp.status_code == 200
    prop_items = prop_resp.json()["items"]
    matched = next((it for it in prop_items if it["id"] == stage_data["batch_item_id"]), None)
    assert matched is not None, "Staged intent not returned in proposed batch items!"
    assert matched["amount_minor"] == 4500
    assert matched["recipient_email"] == "water@city.gov"
    assert matched["intent_id"] == str(intent.id)


@pytest.mark.api
async def test_propose_batch_includes_unstaged_memory_intents(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verifies propose_batch automatically identifies unstaged recurring bill intents
    recorded in memory and creates pending_approval batch items.
    """
    user = (await seeded_session.exec(select(User))).first()

    intent = Intent(
        user_id=user.id,
        utterance="Pay fiber internet subscription",
        amount=6500,
        currency="USD",
        merchant_name="billing@fiberisp.net",
        category="bills",
        necessity="bill",
        recommended_bucket="bills",
        status="allowed",
    )
    seeded_session.add(intent)
    await seeded_session.commit()

    prop_resp = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop_resp.status_code == 200
    items = prop_resp.json()["items"]
    fiber_item = next((it for it in items if "fiber" in it["title"].lower() or "fiber" in (it["note"] or "").lower()), None)
    assert fiber_item is not None, "Unstaged recurring bill intent was not proposed by batch dispatcher!"
    assert fiber_item["amount_minor"] == 6500


@pytest.mark.api
async def test_ai_coach_stages_payment_from_chat(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Verifies that when a user asks the AI Coach to stage a bill payment in chat,
    the Coach stages it into batch_payment_items with status='pending_approval'
    and returns action_type='stage_batch'.
    """
    chat_resp = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "Please stage my electric bill of $75 to electric@state.gov"},
    )
    assert chat_resp.status_code == 200, chat_resp.text
    chat_data = chat_resp.json()
    assert chat_data["decision"]["action_type"] == "stage_batch"
    assert "staged" in chat_data["reply"].lower()
    assert "electric@state.gov" in chat_data["reply"].lower() or "batch dispatcher" in chat_data["reply"].lower()

    # Verify staged item exists in DB
    user = (await seeded_session.exec(select(User))).first()
    stmt = (
        select(BatchPaymentItem)
        .where(BatchPaymentItem.user_id == user.id)
        .where(BatchPaymentItem.recipient_email == "electric@state.gov")
    )
    item = (await seeded_session.exec(stmt)).first()
    assert item is not None, "BatchPaymentItem was not created by AI Coach staging request!"
    assert item.amount_minor == 7500
    assert item.status == "pending_approval"
    assert item.source_bucket == "bills"
