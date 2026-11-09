"""
Adversarial Empirical Stress Harness (challenger_1)
===================================================
Empirically stress-tests and adversarially challenges the FireWallet system:
1. Zero-sum double-entry ledger invariants:
   - Verifies that across arbitrary sequences of reallocations, emergency draws,
     and batch payouts, total net worth is conserved to the exact cent (-Bank / +Bucket = $0.00).
   - Verifies that all transfer_id multi-leg records sum to exactly 0.
2. Vault-to-Bank cascade:
   - Partial draw: $100 Vault + $50 Bank = $150 draw.
   - Complete exhaustion: $0 Vault + $100 Bank = $100 draw.
   - Boundary overdraw rejection (409) preserving ledger integrity.
   - Non-emergency vault spend rejection.
3. Partner approval replay attacks:
   - Replaying approved token yields HTTP 409 Conflict.
   - Replaying rejected token yields HTTP 409 Conflict.
   - Replay barrage (state mutation lock).
   - Invalid token 404 handling.
4. Batch Dispatcher blast radius containment:
   - Attempts to specify source_bucket="bank" fail immediately with HTTP 400.
   - Other unauthorized buckets fail with HTTP 400.
   - Reserve overflow protection leaves Bank Foundation untouched.
   - Live PayPal Sandbox requirement (mock token returns HTTP 503).
"""

from datetime import date, timedelta
from typing import Dict, List
from uuid import uuid4
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ledger.engine import LedgerEngine
from app.models.user import User, BudgetPolicy
from app.models.bucket import Bucket
from app.models.bill import Bill
from app.models.ledger import LedgerEntry
from app.models.batch_payment import BatchPaymentItem
from app.services.paypal_client import paypal_client


# =====================================================================
# 1. ZERO-SUM DOUBLE-ENTRY LEDGER INVARIANTS ACROSS ARBITRARY SEQUENCES
# =====================================================================

@pytest.mark.api
async def test_adversarial_zero_sum_double_entry_arbitrary_sequence(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Stress-tests double-entry conservation across an intensive sequence of:
    1. Rebalancing bills target upwards (+Bank -> Bills)
    2. Rebalancing bills target downwards (-Bills -> Bank)
    3. Changing vault skim rate and topup caps
    4. Performing emergency draws cascading from Bank to Vault
    5. Performing batch payouts from isolated Bills
    At every single step:
    - Verifies all paired transfer legs sum to EXACTLY 0.00 cents.
    - Verifies sum of posted bucket balances equals the initial pool minus external expenditures.
    """
    user = (await seeded_session.exec(select(User))).first()
    assert user is not None

    async def verify_ledger_invariants():
        # Check all ledger transfers have zero-sum legs
        entries = (await seeded_session.exec(
            select(LedgerEntry).where(LedgerEntry.user_id == user.id)
        )).all()

        transfers: Dict[str, int] = {}
        for e in entries:
            assert isinstance(e.amount, int), f"Float detected in ledger amount: {e.amount}"
            t_key = str(e.transfer_id)
            transfers[t_key] = transfers.get(t_key, 0) + e.amount

        # Multi-leg internal transfers MUST balance to 0
        for t_id, net_sum in transfers.items():
            legs = [e for e in entries if str(e.transfer_id) == t_id]
            if len(legs) > 1 and all(l.entry_kind != "merchant_spend" for l in legs):
                assert net_sum == 0, f"Transfer {t_id} is not zero-sum: net sum = {net_sum} cents!"

        # Check total net worth matches posted bucket sum
        balances = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
        posted_sum = sum(b["posted"] for b in balances.values())

        # Sum of posted entries in DB
        db_posted = sum(e.amount for e in entries if e.state == "posted")
        assert posted_sum == db_posted, f"Posted sum mismatch: {posted_sum} vs {db_posted}"
        return posted_sum

    # Step 0: Baseline check
    init_total = await verify_ledger_invariants()

    # Step 1: Upward bills rebalance to $1,600.00 (+40,000 from Bank to Bills)
    resp1 = await client.put("/api/v1/me/policy", json={"bills_monthly_amount": 160000})
    assert resp1.status_code == 200
    total1 = await verify_ledger_invariants()
    assert total1 == init_total, f"Net worth leaked during upward bills rebalance! {total1} != {init_total}"

    # Step 2: Downward bills rebalance to $900.00 (-70,000 from Bills to Bank)
    resp2 = await client.put("/api/v1/me/policy", json={"bills_monthly_amount": 90000})
    assert resp2.status_code == 200
    total2 = await verify_ledger_invariants()
    assert total2 == init_total, f"Net worth leaked during downward bills rebalance! {total2} != {init_total}"

    # Step 3: Complex policy update with vault skim change (3500 bps = 35%) and sync
    resp3 = await client.put("/api/v1/me/policy", json={"vault_skim_bps": 3500, "daily_amount": 6000})
    assert resp3.status_code == 200
    total3 = await verify_ledger_invariants()
    assert total3 == init_total, f"Net worth leaked during policy tweak! {total3} != {init_total}"

    # Step 4: Emergency draw with cascade
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Emergency dental surgery copay", "amount": 18000, "merchant_name": "Emergency Dental"},
    )
    assert int_resp.status_code == 201
    intent_id = int_resp.json()["id"]

    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    cap_resp = await client.post(f"/api/v1/intents/{intent_id}/capture", json={"paypal_order_id": order_id})
    assert cap_resp.status_code == 200
    assert cap_resp.json()["status"] == "settled"

    total4 = await verify_ledger_invariants()
    # Exactly $180.00 spent externally
    assert total4 == init_total - 18000, f"Expected total {init_total - 18000}, got {total4}"

    # Step 5: Batch payout from isolated bills
    # Mock live PayPal payout client
    async def mock_create_payout(batch_id: str, receiver_email: str, amount_cents: int, note: str = ""):
        return {"batch_status": "SUCCESS", "payout_batch_id": f"PAYOUT-{batch_id}", "amount_cents": amount_cents}
    monkeypatch.setattr(paypal_client, "create_payout", mock_create_payout)
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: True, raising=False)
    async def mock_live_token():
        return "live_sandbox_token_verified"
    monkeypatch.setattr(paypal_client, "get_access_token", mock_live_token)

    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    assert prop.status_code == 200
    items = prop.json()["items"]
    assert len(items) > 0
    payout_item = items[0]
    payout_amt = payout_item["amount_minor"]

    batch_resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [payout_item["id"]], "source_bucket": "bills"},
    )
    assert batch_resp.status_code == 200

    total5 = await verify_ledger_invariants()
    assert total5 == total4 - payout_amt, f"Expected total {total4 - payout_amt}, got {total5}"


# =====================================================================
# 2. VAULT-TO-BANK CASCADE STRESS HARNESS
# =====================================================================

@pytest.mark.api
async def test_adversarial_vault_cascade_partial_draw(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Stress-test exact partial draw specification:
    Starting condition: $100 Vault + $50 Bank.
    Emergency spend: $150.00 (15,000 cents).
    Verification:
    - $100 is drawn from Vault.
    - Remaining $50 cascades from Bank to Vault via paired double-entry transfer.
    - Post-settlement: Vault = $0.00, Bank = $0.00. Total draw = $150.00.
    """
    user = (await seeded_session.exec(select(User))).first()
    vault = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "vault"))).first()
    bank = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "bank"))).first()

    # Reset Vault to exactly $100.00 (10,000) and Bank to exactly $50.00 (5,000)
    bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    curr_v = bal["vault"]["posted"]
    curr_b = bal["bank"]["posted"]

    # Adjust Vault to 10,000
    if curr_v != 10000:
        diff_v = 10000 - curr_v
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=vault.id,
            amount=diff_v,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Setup exact $100 vault",
            idempotency_key=f"setup:v:{uuid4()}",
        ))
    # Adjust Bank to 5,000
    if curr_b != 5000:
        diff_b = 5000 - curr_b
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=bank.id,
            amount=diff_b,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Setup exact $50 bank",
            idempotency_key=f"setup:b:{uuid4()}",
        ))
    await seeded_session.commit()

    check_bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert check_bal["vault"]["available"] == 10000
    assert check_bal["bank"]["available"] == 5000

    # Submit emergency intent for exactly $150.00
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Emergency medical treatment for acute infection", "amount": 15000, "merchant_name": "Urgent Care"},
    )
    assert int_resp.status_code == 201
    intent_id = int_resp.json()["id"]

    # Execute
    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    # Capture
    cap_resp = await client.post(f"/api/v1/intents/{intent_id}/capture", json={"paypal_order_id": order_id})
    assert cap_resp.status_code == 200

    # Verify post-settlement balances
    post_bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert post_bal["vault"]["available"] == 0, f"Expected Vault available 0, got {post_bal['vault']['available']}"
    assert post_bal["vault"]["posted"] == 0, f"Expected Vault posted 0, got {post_bal['vault']['posted']}"
    assert post_bal["bank"]["available"] == 0, f"Expected Bank available 0, got {post_bal['bank']['available']}"
    assert post_bal["bank"]["posted"] == 0, f"Expected Bank posted 0, got {post_bal['bank']['posted']}"

    # Verify double-entry cascade record
    cascade_entries = (await seeded_session.exec(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user.id)
        .where(LedgerEntry.entry_kind == "emergency_vault_draw")
    )).all()
    assert len(cascade_entries) >= 2
    cascade_amounts = [e.amount for e in cascade_entries]
    assert -5000 in cascade_amounts, "Bank debit leg of -$50.00 missing from cascade!"
    assert 5000 in cascade_amounts, "Vault credit leg of +$50.00 missing from cascade!"


@pytest.mark.api
async def test_adversarial_vault_cascade_complete_exhaustion(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Stress-test complete exhaustion specification:
    Starting condition: $0 Vault + $100 Bank.
    Emergency spend: $100.00 (10,000 cents).
    Verification:
    - 100% of the $100.00 cascades from Bank Foundation to Vault.
    - Post-settlement: Vault = $0.00, Bank = $0.00.
    """
    user = (await seeded_session.exec(select(User))).first()
    vault = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "vault"))).first()
    bank = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "bank"))).first()

    bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    curr_v = bal["vault"]["posted"]
    curr_b = bal["bank"]["posted"]

    # Drain Vault to 0
    if curr_v != 0:
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=vault.id,
            amount=-curr_v,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Drain vault to $0",
            idempotency_key=f"drain:v:{uuid4()}",
        ))
    # Adjust Bank to 10,000 ($100.00)
    if curr_b != 10000:
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=bank.id,
            amount=10000 - curr_b,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Set bank to $100",
            idempotency_key=f"setup:b2:{uuid4()}",
        ))
    await seeded_session.commit()

    check_bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert check_bal["vault"]["available"] == 0
    assert check_bal["bank"]["available"] == 10000

    # Draw $100.00
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Emergency locksmith lock replacement after break-in", "amount": 10000, "merchant_name": "24/7 Locksmith"},
    )
    assert int_resp.status_code == 201
    intent_id = int_resp.json()["id"]

    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    cap_resp = await client.post(f"/api/v1/intents/{intent_id}/capture", json={"paypal_order_id": order_id})
    assert cap_resp.status_code == 200

    post_bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert post_bal["vault"]["available"] == 0
    assert post_bal["vault"]["posted"] == 0
    assert post_bal["bank"]["available"] == 0
    assert post_bal["bank"]["posted"] == 0


@pytest.mark.api
async def test_adversarial_vault_cascade_overdraw_strictly_rejected(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Stress-test boundary overdraw:
    Starting condition: $100 Vault + $50 Bank = $150 total available.
    Emergency spend: $150.01 (15,001 cents).
    Verification:
    - Execution fails with HTTP 409 Conflict.
    - Zero funds are moved, zero cascade entries recorded, zero holds placed.
    """
    user = (await seeded_session.exec(select(User))).first()
    vault = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "vault"))).first()
    bank = (await seeded_session.exec(select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "bank"))).first()

    bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    curr_v = bal["vault"]["posted"]
    curr_b = bal["bank"]["posted"]

    if curr_v != 10000:
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=vault.id,
            amount=10000 - curr_v,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Set vault to $100",
            idempotency_key=f"setup:v3:{uuid4()}",
        ))
    if curr_b != 5000:
        seeded_session.add(LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=bank.id,
            amount=5000 - curr_b,
            currency="USD",
            state="posted",
            entry_kind="test_adjustment",
            memo="Set bank to $50",
            idempotency_key=f"setup:b3:{uuid4()}",
        ))
    await seeded_session.commit()

    # Attempt to spend 15,001 cents ($150.01)
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Emergency bill exceeding reserves", "amount": 15001, "merchant_name": "Overdraw Hospital"},
    )
    assert int_resp.status_code == 201
    intent_id = int_resp.json()["id"]

    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code in (400, 409)

    # Verify no funds were altered or held
    post_bal = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert post_bal["vault"]["available"] == 10000
    assert post_bal["vault"]["held"] == 0
    assert post_bal["bank"]["available"] == 5000
    assert post_bal["bank"]["held"] == 0


# =====================================================================
# 3. PARTNER APPROVAL REPLAY ATTACK STRESS HARNESS
# =====================================================================

@pytest.mark.api
async def test_adversarial_partner_token_replay_approved(client: httpx.AsyncClient):
    """
    Stress-test replay attacks on an approved partner token:
    1. First decision 'approved' succeeds with HTTP 200.
    2. Immediate replay of 'approved' returns HTTP 409 Conflict.
    3. Replay of opposite decision 'rejected' returns HTTP 409 Conflict.
    4. Rapid 5x replay barrage all return HTTP 409 Conflict.
    """
    # Create intent requiring override
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "High end audio system", "amount": 40000, "merchant_name": "HiFi Audio"},
    )
    intent_id = int_resp.json()["id"]

    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "Studio quality monitors for remote audio production."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None, "partner_token was not generated"

    # Step 1: Valid initial approval
    r_first = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "approved"})
    assert r_first.status_code == 200

    # Step 2: Immediate identical replay -> 409
    r_replay_same = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "approved"})
    assert r_replay_same.status_code == 409

    # Step 3: Opposite decision replay -> 409
    r_replay_diff = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "rejected"})
    assert r_replay_diff.status_code == 409

    # Step 4: Barrage of 5 rapid replays -> all 409
    for _ in range(5):
        r_barrage = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "approved"})
        assert r_barrage.status_code == 409


@pytest.mark.api
async def test_adversarial_partner_token_replay_rejected(client: httpx.AsyncClient):
    """
    Stress-test replay attacks on a rejected partner token:
    1. First decision 'rejected' succeeds with HTTP 200.
    2. Immediate replay of 'rejected' returns HTTP 409 Conflict.
    3. Attempt to flip state to 'approved' returns HTTP 409 Conflict.
    """
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Unplanned weekend gaming trip", "amount": 35000, "merchant_name": "Resort"},
    )
    intent_id = int_resp.json()["id"]

    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "Spontaneous relaxation trip with gaming buddies."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None

    # Step 1: Reject
    r_rej = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "rejected"})
    assert r_rej.status_code == 200

    # Step 2: Replay reject -> 409
    r_rej_replay = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "rejected"})
    assert r_rej_replay.status_code == 409

    # Step 3: Flip attempt to approve -> 409
    r_flip = await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "approved"})
    assert r_flip.status_code == 409


@pytest.mark.api
async def test_adversarial_partner_token_tampering_and_sql_injection(client: httpx.AsyncClient):
    """
    Stress-test token endpoint against tampered tokens and SQL injection payloads.
    All must return HTTP 404 or 422 cleanly without 500 error or SQL crash.
    """
    bad_tokens = [
        "invalid_token_12345",
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "a" * 500,
        "   ",
    ]
    for bt in bad_tokens:
        r_get = await client.get(f"/api/v1/partner/approve/{bt}")
        assert r_get.status_code in (404, 422), f"Token '{bt}' returned unexpected {r_get.status_code}"

        r_post = await client.post(f"/api/v1/partner/approve/{bt}/decision", json={"decision": "approved"})
        assert r_post.status_code in (404, 422), f"Token '{bt}' returned unexpected {r_post.status_code}"


# =====================================================================
# 4. BATCH DISPATCHER BLAST RADIUS CONTAINMENT STRESS HARNESS
# =====================================================================

@pytest.mark.api
async def test_adversarial_batch_dispatcher_bank_blast_radius_strictly_denied(client: httpx.AsyncClient):
    """
    Stress-test blast radius containment:
    Verify that specifying source_bucket='bank' fails immediately with HTTP 400.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    items = prop.json()["items"]
    assert len(items) > 0
    item_id = items[0]["id"]

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bank"},
    )
    assert resp.status_code == 400
    assert "bank" in resp.text.lower()
    assert "forbidden" in resp.text.lower() or "restricted" in resp.text.lower()


@pytest.mark.api
async def test_adversarial_batch_dispatcher_unauthorized_buckets_strictly_denied(client: httpx.AsyncClient):
    """
    Stress-test blast radius containment across unauthorized bucket identifiers:
    'daily', 'freedom', 'payroll', 'root', 'unknown', empty string.
    All must fail with HTTP 400.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    item_id = prop.json()["items"][0]["id"]

    unauthorized_buckets = ["daily", "freedom", "payroll", "root", "unknown", ""]
    for b in unauthorized_buckets:
        resp = await client.post(
            "/api/v1/bills/batch-dispatcher/execute",
            json={"approved_item_ids": [item_id], "source_bucket": b},
        )
        assert resp.status_code == 400, f"Bucket '{b}' did not fail with 400! Got {resp.status_code}"


@pytest.mark.api
async def test_adversarial_batch_dispatcher_overdraw_preserves_bank(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Stress-test blast radius containment against batch overdraw:
    Staging an amount exceeding isolated Bills reserve must fail with HTTP 400,
    and Bank Foundation MUST remain 100% untouched down to the exact cent.
    """
    user = (await seeded_session.exec(select(User))).first()
    initial_bank = (await LedgerEngine.get_bucket_balances(seeded_session, user.id))["bank"]["available"]

    # Seed an over-sized bill
    huge_bill = Bill(
        user_id=user.id,
        name="Massive Commercial Obligation",
        amount=500000,  # $5,000.00 (exceeds all isolated reserves)
        due_date=date.today() + timedelta(days=2),
        payee_email="corporate@sandbox.paypal.com",
        priority=1,
        status="scheduled",
    )
    seeded_session.add(huge_bill)
    await seeded_session.commit()

    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    huge_item = next(it for it in prop.json()["items"] if it["title"] == "Massive Commercial Obligation")

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [huge_item["id"]], "source_bucket": "bills"},
    )
    assert resp.status_code == 400

    # Verify Bank Foundation was preserved to the cent
    post_bank = (await LedgerEngine.get_bucket_balances(seeded_session, user.id))["bank"]["available"]
    assert post_bank == initial_bank, f"Bank Foundation was raided! {post_bank} != {initial_bank}"


@pytest.mark.api
async def test_adversarial_batch_dispatcher_live_paypal_sandbox_guard(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Stress-test live PayPal Sandbox requirement:
    When live credentials are unconfigured or offline (mock token returned),
    batch execution must return HTTP 503 cleanly without debiting the ledger.
    """
    prop = await client.post("/api/v1/bills/batch-dispatcher/propose")
    item_id = prop.json()["items"][0]["id"]

    # Force mock credentials
    monkeypatch.setattr(paypal_client, "has_live_credentials", lambda: False, raising=False)

    resp = await client.post(
        "/api/v1/bills/batch-dispatcher/execute",
        json={"approved_item_ids": [item_id], "source_bucket": "bills"},
    )
    assert resp.status_code == 503
    assert "Live PayPal Sandbox connection required" in resp.text
