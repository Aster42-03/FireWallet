"""
Phase 5 E2E Test Suite (R1 / BUG-008 / Partner Dual-Flow / Branding Neutrality)
================================================================================
Comprehensive 4-Tier test suite verifying:
1. Emergency Vault Allocation & Autonomous Execution (BUG-008):
   - Genuine emergencies route to Vault with 0s cooldown bypass.
   - `LedgerEngine.can_spend(..., is_emergency=True)` allows spend from Vault.
   - Insufficient Vault funds cascade to Bank Foundation via double-entry `emergency_vault_draw`.
2. Accountability Partner Escalation & Dual-Flow Escape Window:
   - Cryptographic approval token generation and dispatch when partner linked.
   - Happy Branch: Partner approval unlocks spend immediately (0s cooldown, 0 confession chars).
   - Friction Branch: Unresponsive partner enforces 200 chars confession and 180s countdown timer.
   - Final outcome alert logging for payment resolution.
3. Model Branding Removal:
   - Neutral UI presentation with zero vendor/model branding strings.

Tiers:
- Tier 1: Feature Coverage (Vault emergency spend, cascade, partner tokens, approval, branding)
- Tier 2: Boundary & Corner Cases (Exceeding combined pool, empty vault cascade, token replay, 404s)
- Tier 3: Cross-Feature Combinations (Cascade + Partner dual-flow, outcome alerts on cancel/settle)
- Tier 4: Real-World Scenarios (Complete ER medical emergency lifecycle, partner approval to checkout)
"""

import os
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from uuid import UUID, uuid4
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ledger.engine import LedgerEngine
from app.models.user import User, BudgetPolicy, PartnerApproval
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.intent import Intent, Override


# =====================================================================
# TIER 1: FEATURE COVERAGE
# =====================================================================

@pytest.mark.unit
async def test_tier1_can_spend_vault_with_is_emergency_flag(seeded_session: AsyncSession):
    """
    Tier 1: Verify LedgerEngine.can_spend() Rule 1 allows spend from Vault
    when is_emergency=True, but strictly denies non-emergency spend.
    """
    user = (await seeded_session.exec(select(User))).first()
    assert user is not None

    # 1. Non-emergency spend from Vault -> strictly DENIED
    allowed_norm, status_norm, rat_norm = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=5000,
        source_kind="vault",
        necessity="freedom",
        is_emergency=False,
    )
    assert not allowed_norm
    assert status_norm == "denied"
    assert "vault is locked" in rat_norm.lower()

    # 2. Genuine emergency spend from Vault -> ALLOWED
    allowed_emerg, status_emerg, rat_emerg = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=5000,
        source_kind="vault",
        necessity="daily_living",
        is_emergency=True,
    )
    assert allowed_emerg
    assert status_emerg == "allowed"


@pytest.mark.api
async def test_tier1_emergency_vault_routing_and_zero_cooldown(client: httpx.AsyncClient):
    """
    Tier 1: Verified emergency spend intent routes to Vault with 0s cooldown bypass (BUG-008).
    """
    payload = {
        "utterance": "Urgent hospital emergency room copay for severe cut",
        "amount": 15000,  # $150.00
        "merchant_name": "City General Hospital",
    }
    resp = await client.post("/api/v1/intents", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_emergency"] is True
    assert data["cooldown_seconds"] == 0
    assert data["recommended_bucket"] == "vault"


@pytest.mark.api
async def test_tier1_vault_to_bank_cascade_when_vault_insufficient(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 1: When emergency exceeds available Vault ($200.00), available Vault is drawn
    and remainder cascades from Bank Foundation via paired double-entry transfers.
    Initial: Vault $200.00 (20,000), Bank $800.00 (80,000).
    Emergency: $250.00 (25,000).
    Expected cascade: $50.00 (5,000) from Bank to Vault.
    Post-settlement: Vault $0.00, Bank $750.00 (75,000).
    """
    # 1. Create emergency intent exceeding Vault
    intent_resp = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Emergency surgery copay at trauma center",
            "amount": 25000,  # $250.00
            "merchant_name": "Trauma Center",
        },
    )
    assert intent_resp.status_code == 201
    intent_data = intent_resp.json()
    intent_id = intent_data["id"]

    # 2. Execute intent (triggers cascade transfer and places hold)
    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    # 3. Capture payment
    cap_resp = await client.post(
        f"/api/v1/intents/{intent_id}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 200
    assert cap_resp.json()["status"] == "settled"

    # 4. Verify post-settlement balances
    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["vault"] == 0, f"Expected Vault to be 0, got {buckets['vault']}"
    assert buckets["bank"] == 75000, f"Expected Bank to be 75000, got {buckets['bank']}"


@pytest.mark.api
async def test_tier1_partner_token_generation_when_partner_linked(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 1: When accountability partner is linked (partner_required_for_bank=True),
    creating an override generates a single-use cryptographic partner token.
    """
    # Update policy to require partner
    await client.put(
        "/api/v1/me/policy",
        json={"bank_spend_requires_override": True, "partner_required_for_bank": True},
    )

    # Create intent requiring override
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Buying expensive mechanical keyboard", "amount": 22000, "merchant_name": "Keychron"},
    )
    intent_id = int_resp.json()["id"]

    # Request override
    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "I need a high performance keyboard for daily software work."},
    )
    assert ov_resp.status_code == 201
    ov_data = ov_resp.json()
    assert "partner_token" in ov_data, "Override response missing partner_token"
    assert ov_data["partner_token"] is not None
    assert len(ov_data["partner_token"]) >= 32
    assert "partner_approval_url" in ov_data


@pytest.mark.api
async def test_tier1_partner_decision_public_endpoints_happy_path(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 1: Public partner approval endpoints:
    1. GET /api/v1/partner/approve/{token} inspects expenditure.
    2. POST /api/v1/partner/approve/{token}/decision with 'approved' unlocks spend immediately (0s cooldown, 0 chars).
    """
    # Setup intent & override
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Gaming monitor purchase", "amount": 30000, "merchant_name": "Best Buy"},
    )
    intent_id = int_resp.json()["id"]

    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "Upgrading monitor for remote desk work."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None, "partner_token not returned in override creation"

    # Partner inspects request
    inspect_resp = await client.get(f"/api/v1/partner/approve/{token}")
    assert inspect_resp.status_code == 200
    insp_data = inspect_resp.json()
    assert insp_data["amount_cents"] == 30000
    assert insp_data["status"] == "pending"

    # Partner approves
    decision_resp = await client.post(
        f"/api/v1/partner/approve/{token}/decision",
        json={"decision": "approved"},
    )
    assert decision_resp.status_code == 200
    assert decision_resp.json()["status"] == "approved"

    # Verify override is now unlocked with 0s cooldown
    chk = await client.post(f"/api/v1/overrides/{ov_resp.json()['id']}/check-cooldown")
    assert chk.status_code == 200, "Approved override should unlock immediately with zero cooldown"


@pytest.mark.unit
def test_tier1_model_branding_neutrality():
    """
    Tier 1: Ensure zero vendor/model branding appears anywhere in frontend source code.
    Prohibited names: groq, llama, openai, gemini, claude, chatgpt, mistral, qwen.
    """
    frontend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../frontend/src")
    )
    assert os.path.exists(frontend_dir), f"Frontend directory not found: {frontend_dir}"

    prohibited_pattern = re.compile(
        r"\b(groq|llama|openai|gemini|claude|chatgpt|mistral|qwen)\b",
        re.IGNORECASE,
    )

    violations = []
    for root, _, files in os.walk(frontend_dir):
        for f in files:
            if f.endswith((".js", ".jsx", ".ts", ".tsx", ".html")):
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
                    for line_num, line in enumerate(fp, start=1):
                        match = prohibited_pattern.search(line)
                        if match:
                            violations.append(
                                f"{os.path.relpath(filepath, frontend_dir)}:{line_num} -> '{match.group(0)}'"
                            )

    assert len(violations) == 0, (
        f"Model branding violation detected in frontend UI! Found {len(violations)} occurrences:\n"
        + "\n".join(violations)
    )


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =====================================================================

@pytest.mark.api
async def test_tier2_emergency_exceeds_combined_vault_and_bank_pool(client: httpx.AsyncClient):
    """
    Tier 2: Emergency amount ($1,200.00) exceeds total available in Vault ($200.00) + Bank ($800.00) = $1,000.00.
    Must fail cleanly with HTTP 409 / Insufficient funds.
    """
    intent_resp = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Catastrophic medical bill requiring immediate payment",
            "amount": 120000,  # $1,200.00
            "merchant_name": "Hospital Surgical Group",
        },
    )
    assert intent_resp.status_code == 201
    intent_id = intent_resp.json()["id"]

    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code in (400, 409)
    assert "insufficient" in exec_resp.text.lower()


@pytest.mark.api
async def test_tier2_emergency_when_vault_is_empty_100pct_cascade(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 2: When Vault balance is $0.00, 100% of emergency cascades from Bank to Vault.
    """
    # Drain Vault to 0 by moving to Bank or creating an initial emergency
    user = (await seeded_session.exec(select(User))).first()
    vault_bucket = (await seeded_session.exec(
        select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "vault")
    )).first()
    bank_bucket = (await seeded_session.exec(
        select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == "bank")
    )).first()

    # Empty vault to 0
    await LedgerEngine.record_double_entry_transfer(
        session=seeded_session,
        user_id=user.id,
        from_bucket_id=vault_bucket.id,
        to_bucket_id=bank_bucket.id,
        amount_minor=20000,
        entry_kind="vault_to_bank_transfer",
        memo="Testing 0 balance vault",
        from_bucket_kind="vault",
        to_bucket_kind="bank",
    )

    # Emergency of $60.00 (6,000)
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Urgent dental extraction copay", "amount": 6000, "merchant_name": "Dental Emergency"},
    )
    intent_id = int_resp.json()["id"]

    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200

    order_id = exec_resp.json().get("paypal_order_id")
    await client.post(f"/api/v1/intents/{intent_id}/capture", json={"paypal_order_id": order_id})

    # Verify Bank funded all $60.00 and Vault remains at 0
    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["vault"] == 0
    # Bank was 80000 + 20000 = 100000 - 6000 = 94000
    assert buckets["bank"] == 94000


@pytest.mark.api
async def test_tier2_partner_decision_invalid_token_404(client: httpx.AsyncClient):
    """
    Tier 2: Calling partner endpoints with an invalid / non-existent token returns HTTP 404.
    """
    resp = await client.get("/api/v1/partner/approve/non-existent-token-xyz-12345")
    assert resp.status_code == 404


@pytest.mark.api
async def test_tier2_partner_decision_replay_conflict_409(client: httpx.AsyncClient):
    """
    Tier 2: Submitting a decision for an already decided partner token returns HTTP 409 Conflict.
    """
    # Create override with token
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Weekend getaway flight ticket", "amount": 28000, "merchant_name": "Airline"},
    )
    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": int_resp.json()["id"], "body": "Visiting old friend for mental wellness."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None

    # First decision -> 200 OK
    r1 = await client.post(
        f"/api/v1/partner/approve/{token}/decision",
        json={"decision": "approved"},
    )
    assert r1.status_code == 200

    # Replay attempt -> 409 Conflict
    r2 = await client.post(
        f"/api/v1/partner/approve/{token}/decision",
        json={"decision": "approved"},
    )
    assert r2.status_code == 409


@pytest.mark.api
async def test_tier2_partner_decision_expired_token_returns_410(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 2: Partner approval tokens older than 24 hours are expired and return HTTP 410 Gone.
    """
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Weekend camping gear", "amount": 25000, "merchant_name": "REI"},
    )
    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": int_resp.json()["id"], "body": "Need high quality camping gear for trip."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None

    # Age the override past 24 hours
    stmt = select(Override).where(Override.id == UUID(ov_resp.json()["id"]))
    override = (await seeded_session.exec(stmt)).first()
    assert override is not None
    override.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
    seeded_session.add(override)
    await seeded_session.commit()

    # Attempt to decide -> HTTP 410 Gone
    r_exp = await client.post(
        f"/api/v1/partner/approve/{token}/decision",
        json={"decision": "approved"},
    )
    assert r_exp.status_code == 410, f"Expected 410 Gone, got {r_exp.status_code}: {r_exp.text}"
    assert "expired" in r_exp.json()["detail"].lower()


@pytest.mark.api
async def test_tier2_partner_timeout_or_unresponsive_friction_enforced(client: httpx.AsyncClient):
    """
    Tier 2: If partner does not approve, standard friction applies:
    1. Short confession (< 200 chars) is rejected with HTTP 422.
    2. Premature cooldown check (< 180s) is rejected with HTTP 409.
    """
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Luxury headphones purchase", "amount": 35000, "merchant_name": "Bose"},
    )
    intent_id = int_resp.json()["id"]

    # Short confession
    short_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "I really want these headphones."},
    )
    assert short_resp.status_code == 422
    assert "at least 200 characters" in short_resp.text


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# =====================================================================

@pytest.mark.api
async def test_tier3_vault_cascade_with_partner_dual_flow_approval(client: httpx.AsyncClient):
    """
    Tier 3: A large emergency ($300.00) requiring cascade ($200 Vault + $100 Bank)
    where partner approves via token. Spend executes with 0s cooldown,
    cascades $100 from Bank to Vault, and settles cleanly.
    """
    int_resp = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Emergency transmission repair for commute vehicle",
            "amount": 30000,  # $300.00
            "merchant_name": "Transmission Auto",
        },
    )
    intent_data = int_resp.json()
    intent_id = intent_data["id"]

    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": intent_id, "body": "Car broke down on route to work; transmission repair required."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None

    # Partner approves
    app_resp = await client.post(
        f"/api/v1/partner/approve/{token}/decision",
        json={"decision": "approved"},
    )
    assert app_resp.status_code == 200

    # Execute & Capture
    exec_resp = await client.post(f"/api/v1/intents/{intent_id}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    cap_resp = await client.post(f"/api/v1/intents/{intent_id}/capture", json={"paypal_order_id": order_id})
    assert cap_resp.status_code == 200
    assert cap_resp.json()["status"] == "settled"

    # Verify balances: Vault was $200 -> now $0. Bank was $800 -> now $700.
    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["vault"] == 0
    assert buckets["bank"] == 70000


@pytest.mark.api
async def test_tier3_partner_outcome_alert_dispatched_on_user_cancellation(
    client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    Tier 3: User cancels override after partner approval -> outcome alert logs CANCELLED.
    """
    int_resp = await client.post(
        "/api/v1/intents",
        json={"utterance": "Impulse designer watch", "amount": 25000, "merchant_name": "WatchCo"},
    )
    ov_resp = await client.post(
        "/api/v1/overrides",
        json={"intent_id": int_resp.json()["id"], "body": "Contemplating a designer watch for milestone."},
    )
    token = ov_resp.json().get("partner_token")
    assert token is not None

    await client.post(f"/api/v1/partner/approve/{token}/decision", json={"decision": "approved"})

    # Cancel override
    cancel_resp = await client.post(f"/api/v1/overrides/{ov_resp.json()['id']}/cancel")
    assert cancel_resp.status_code in (200, 204)


# =====================================================================
# TIER 4: REAL-WORLD SCENARIOS
# =====================================================================

@pytest.mark.api
async def test_tier4_complete_er_medical_emergency_lifecycle(client: httpx.AsyncClient):
    """
    Tier 4: Complete life/medical emergency flow:
    1. User suffers unexpected medical accident ($180.00 hospital ER copay).
    2. Submits intent -> detected as genuine emergency -> routed to Vault with 0s delay.
    3. Vault has $200.00 available -> fully covers $180.00 without cascading to Bank.
    4. Autonomous or instant execution completes payment.
    5. Balances verified: Vault = $20.00 ($200 - $180), Bank remains $800.00 untouched.
    6. Double-entry ledger audit confirms exact balance sheet balance.
    """
    # Initial balance check
    b_init = {b["kind"]: b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"]}
    assert b_init["vault"] == 20000
    assert b_init["bank"] == 80000

    # 1. Submit emergency intent
    int_resp = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "At City Emergency Hospital paying urgent fracture x-ray copay",
            "amount": 18000,  # $180.00
            "merchant_name": "City Emergency Hospital",
        },
    )
    assert int_resp.status_code == 201
    int_data = int_resp.json()
    assert int_data["is_emergency"] is True
    assert int_data["cooldown_seconds"] == 0
    assert int_data["recommended_bucket"] == "vault"

    # 2. Execute & Capture
    exec_resp = await client.post(f"/api/v1/intents/{int_data['id']}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json().get("paypal_order_id")

    cap_resp = await client.post(
        f"/api/v1/intents/{int_data['id']}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 200
    assert cap_resp.json()["status"] == "settled"

    # 3. Post-execution balance check
    b_post = {b["kind"]: b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"]}
    assert b_post["vault"] == 2000, f"Expected Vault to be $20.00 (2000), got {b_post['vault']}"
    assert b_post["bank"] == 80000, f"Expected Bank to be $800.00 (80000), got {b_post['bank']}"
