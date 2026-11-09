"""
Configurable Bills Envelope & Double-Entry Rebalancing E2E Test Suite (R3)
==========================================================================
Comprehensive 4-Tier test suite verifying that the Reserved Bills target amount
can be configured via budget policy (`bills_monthly_amount`), and that changes
trigger paired double-entry transfers between Bank Foundation and Reserved Bills
(`-Bank / +Bills = $0.00`), strictly preserving the zero-float ledger invariant.

Tiers:
- Tier 1: Feature Coverage (Policy GET/PUT/PATCH, double-entry records, HUD balance updates)
- Tier 2: Boundary & Corner Cases (0 amount, negative amount, unchanged target, excessive target)
- Tier 3: Cross-Feature Combinations (5-bucket zero-sum preservation, deep-ledger reconciliation)
- Tier 4: Real-World Scenarios (Seasonal bill expansion and subsequent rollback to Bank Foundation)
"""

from uuid import UUID
import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, BudgetPolicy
from app.models.ledger import LedgerEntry
from app.ledger.engine import LedgerEngine


# =====================================================================
# TIER 1: FEATURE COVERAGE
# =====================================================================

@pytest.mark.api
async def test_tier1_get_policy_returns_bills_monthly_amount(client: httpx.AsyncClient):
    """
    Tier 1: Verify GET /api/v1/me/policy includes bills_monthly_amount.
    Authoritative default: 120,000 cents ($1,200.00).
    """
    resp = await client.get("/api/v1/me/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert "bills_monthly_amount" in data, "Policy response missing 'bills_monthly_amount' field"
    assert data["bills_monthly_amount"] == 120000


@pytest.mark.api
async def test_tier1_update_bills_target_inflow_from_bank(client: httpx.AsyncClient):
    """
    Tier 1: Increasing bills allocation moves funds from Bank to Bills.
    Initial state: Bills target is 120,000 cents.
    Target: $1,500.00 (150,000) -> Delta +$300.00 (+30,000).
    Expected: Bills available becomes 150,000 cents.
    """
    # 1. Establish initial bucket balances
    init_b = {b["kind"]: b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"]}

    resp = await client.put(
        "/api/v1/me/policy",
        json={
            "bills_monthly_amount": 150000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "updated"
    assert data["policy"]["bills_monthly_amount"] == 150000

    # Verify HUD buckets reflect reallocation
    b_resp = await client.get("/api/v1/buckets")
    assert b_resp.status_code == 200
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bills"] == 150000, f"Expected bills to be 150000, got {buckets['bills']}"


@pytest.mark.api
async def test_tier1_update_bills_target_outflow_return_to_bank(client: httpx.AsyncClient):
    """
    Tier 1: Decreasing bills allocation returns funds from Bills back to Bank.
    Initial state: Bills target is 120,000 cents.
    Target: $1,000.00 (100,000) -> Delta -$200.00 (-20,000).
    Expected: Bills available becomes 100,000 cents.
    """
    resp = await client.put(
        "/api/v1/me/policy",
        json={
            "bills_monthly_amount": 100000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "updated"
    assert data["policy"]["bills_monthly_amount"] == 100000

    b_resp = await client.get("/api/v1/buckets")
    assert b_resp.status_code == 200
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bills"] == 100000


@pytest.mark.api
async def test_tier1_patch_policy_preserves_bills_amount(client: httpx.AsyncClient):
    """
    Tier 1: PATCH /api/v1/me/policy updating daily_amount should leave bills_monthly_amount intact.
    """
    patch_resp = await client.patch(
        "/api/v1/me/policy",
        json={"daily_amount": 5000},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["status"] == "updated"
    assert data["policy"]["daily_amount"] == 5000
    assert data["policy"]["bills_monthly_amount"] == 120000


@pytest.mark.api
async def test_tier1_double_entry_ledger_records_verified(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 1: Verify paired double-entry ledger entries exist with shared transfer_id and net zero sum.
    """
    # Trigger rebalance: Bills 120000 -> 140000 (+20000 from Bank)
    await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 140000},
    )

    # Inspect LedgerEntry table for bill_reserve transfer
    entries = (
        await seeded_session.exec(
            select(LedgerEntry).where(LedgerEntry.entry_kind == "bill_reserve")
        )
    ).all()

    # Find the newly created transfer
    transfers = {}
    for e in entries:
        transfers.setdefault(e.transfer_id, []).append(e)

    # Find the transfer of 20000
    rebalance_pair = [pair for pair in transfers.values() if len(pair) == 2 and abs(pair[0].amount) == 20000]
    assert len(rebalance_pair) > 0, "No paired double-entry transfer found for bills rebalancing"

    pair = rebalance_pair[0]
    total_delta = sum(e.amount for e in pair)
    assert total_delta == 0, f"Double-entry violation: pair sum is {total_delta}, expected 0"


@pytest.mark.api
async def test_tier1_hud_buckets_endpoint_reflects_rebalanced_bills(client: httpx.AsyncClient):
    """
    Tier 1: Verify HUD /api/v1/buckets telemetry reports updated available balance immediately.
    """
    await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 130000},
    )

    resp = await client.get("/api/v1/buckets")
    assert resp.status_code == 200
    bills_bucket = next(b for b in resp.json()["buckets"] if b["kind"] == "bills")
    assert bills_bucket["available"] == 130000


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =====================================================================

@pytest.mark.api
async def test_tier2_bills_target_zero_cents_deallocates_to_bank(client: httpx.AsyncClient):
    """
    Tier 2: Setting bills_monthly_amount to 0 cents is valid.
    Bills available becomes 0, returning funds to Bank Foundation pool.
    """
    resp = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy"]["bills_monthly_amount"] == 0

    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bills"] == 0


@pytest.mark.api
async def test_tier2_negative_bills_target_rejected_422(client: httpx.AsyncClient):
    """
    Tier 2: Negative bills target must be rejected with HTTP 422 Unprocessable Entity.
    """
    resp = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": -1000},
    )
    assert resp.status_code == 422


@pytest.mark.api
async def test_tier2_bills_target_unchanged_idempotent_no_spurious_entries(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession,
):
    """
    Tier 2: Calling PUT twice with identical policy produces 0 new ledger rows on second call.
    """
    # First call synchronizes all policy targets
    r1 = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 125000},
    )
    assert r1.status_code == 200

    count_before = len((await seeded_session.exec(select(LedgerEntry))).all())

    # Second call with identical payload must be idempotent
    r2 = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 125000},
    )
    assert r2.status_code == 200

    count_after = len((await seeded_session.exec(select(LedgerEntry))).all())
    assert count_after == count_before, (
        f"Spurious ledger entries generated on idempotent policy PUT: {count_after} vs {count_before}"
    )


@pytest.mark.api
async def test_tier2_bills_target_exceeding_bank_funds_capped(client: httpx.AsyncClient):
    """
    Tier 2: Setting a target requiring more funds than Bank available
    must be capped at available bank funds rather than plunging Bank negative.
    """
    resp = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 620000},
    )
    assert resp.status_code == 200

    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bank"] >= 0, "Bank Foundation balance went negative!"


@pytest.mark.api
async def test_tier2_string_or_float_minor_units_handled_strictly(client: httpx.AsyncClient):
    """
    Tier 2: Passing a string or malformed type returns 422.
    """
    resp = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": "not_an_int"},
    )
    assert resp.status_code == 422


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# =====================================================================

@pytest.mark.api
async def test_tier3_bills_rebalancing_preserves_zero_sum_across_all_five_buckets(
    client: httpx.AsyncClient,
):
    """
    Tier 3: The total net worth across all 5 Trinity buckets before rebalance
    must exactly equal total net worth after rebalance.
    """
    # 1. Capture initial sum
    r1 = await client.get("/api/v1/buckets")
    sum_before = sum(b["available"] for b in r1.json()["buckets"])

    # 2. Rebalance: move +$250.00 into bills
    await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 145000},
    )

    # 3. Capture post-update sum
    r2 = await client.get("/api/v1/buckets")
    sum_after = sum(b["available"] for b in r2.json()["buckets"])

    assert sum_after == sum_before, (
        f"Zero-float ledger invariant violated! Sum before: {sum_before}, sum after: {sum_after}"
    )


@pytest.mark.api
async def test_tier3_deep_ledger_aggregates_remain_balanced_after_bills_rebalance(
    client: httpx.AsyncClient,
):
    """
    Tier 3: Deep Ledger workbench aggregates report double_entry_balanced is True after bills update.
    """
    await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 135000},
    )

    resp = await client.get("/api/v1/analytics/deep-ledger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["aggregates"]["double_entry_balanced"] is True


@pytest.mark.api
async def test_tier3_multiple_consecutive_reallocations_stable(client: httpx.AsyncClient):
    """
    Tier 3: Multiple rapid reallocations (inflow, outflow, inflow) leave balances completely accurate.
    """
    targets = [150000, 110000, 160000, 120000]
    for target in targets:
        resp = await client.put(
            "/api/v1/me/policy",
            json={"bills_monthly_amount": target},
        )
        assert resp.status_code == 200

    b_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert buckets["bills"] == 120000


# =====================================================================
# TIER 4: REAL-WORLD SCENARIOS
# =====================================================================

@pytest.mark.api
async def test_tier4_winter_heating_envelope_expansion_and_spring_reduction(
    client: httpx.AsyncClient,
):
    """
    Tier 4: Realistic seasonal workflow:
    1. User notices winter electricity and heating bills are higher.
    2. Opens Envelope Settings modal and increases Bills from $1,200.00 to $1,450.00.
    3. Verifies Bills increases to $1,450.00.
    4. In spring, user dials Bills back down to $1,200.00.
    5. Verifies Bills restores cleanly to $1,200.00 and system total net worth is conserved.
    """
    # Baseline sum
    sum_initial = sum(b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"])

    # 1. Winter expansion
    r_winter = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 145000},
    )
    assert r_winter.status_code == 200
    b_winter = {b["kind"]: b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"]}
    assert b_winter["bills"] == 145000

    sum_winter = sum(b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"])
    assert sum_winter == sum_initial

    # 2. Spring reduction
    r_spring = await client.put(
        "/api/v1/me/policy",
        json={"bills_monthly_amount": 120000},
    )
    assert r_spring.status_code == 200
    b_spring = {b["kind"]: b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"]}
    assert b_spring["bills"] == 120000

    sum_spring = sum(b["available"] for b in (await client.get("/api/v1/buckets")).json()["buckets"])
    assert sum_spring == sum_initial
