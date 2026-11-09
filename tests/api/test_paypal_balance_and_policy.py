"""
PayPal Balance Detection, Bucket Sync, Policy Reallocation & Analytics Chips Tests:
- PayPal Reporting API balance detection (`GET /v1/reporting/balances`)
- Zero-sum double-entry bucket synchronization (`POST /api/v1/paypal/sync-balance`)
- Configurable envelope reallocation (`PUT /api/v1/me/policy`)
- Automated Midnight Rollover & Payday lifecycles
- Distinct responses for Advanced Analytics diagnostic chips (`BUG-007`)
"""

import pytest
import httpx

from app.services.paypal_client import PayPalClient, paypal_client


@pytest.mark.unit
def test_parse_paypal_to_cents_zero_float():
    """Verify decimal strings from PayPal convert to exact integer cents without float drift."""
    assert PayPalClient.parse_paypal_to_cents("0.00") == 0
    assert PayPalClient.parse_paypal_to_cents("24.50") == 2450
    assert PayPalClient.parse_paypal_to_cents("1842.99") == 184299
    assert PayPalClient.parse_paypal_to_cents("500") == 50000
    assert PayPalClient.parse_paypal_to_cents("-19.05") == -1905


@pytest.mark.api
async def test_detect_and_sync_paypal_balance_matches_bucket_sum(client: httpx.AsyncClient):
    """
    Verify GET /api/v1/paypal/balance detects account balance and
    POST /api/v1/paypal/sync-balance synchronizes all 5 buckets so their sum
    strictly equals the synced PayPal balance while maintaining zero-sum double-entry health.
    """
    bal_resp = await client.get("/api/v1/paypal/balance")
    assert bal_resp.status_code == 200
    bal_data = bal_resp.json()
    assert bal_data["currency"] == "USD"
    assert bal_data["available_cents"] > 0

    # Sync to a specific actual account balance ($3,000.00 = 300000 cents)
    sync_resp = await client.post(
        "/api/v1/paypal/sync-balance",
        json={"override_balance_cents": 300000},
    )
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["status"] == "synced"
    assert sync_data["paypal_balance"]["synced_cents"] == 300000

    buckets_map = {b["kind"]: b["available"] for b in sync_data["buckets"]}
    total_across_buckets = sum(buckets_map.values())
    assert total_across_buckets == 300000

    # Vault should be 20% of $3,000 = $600 (60000 cents), Daily = $40 (4000), Freedom = $150 (15000)
    assert buckets_map["vault"] == 60000
    assert buckets_map["daily"] == 4000
    assert buckets_map["freedom"] == 15000
    assert buckets_map["bills"] == 120000
    assert buckets_map["bank"] == 300000 - (60000 + 4000 + 15000 + 120000)

    # Verify double-entry reconciliation remains balanced in deep ledger
    deep_resp = await client.get("/api/v1/analytics/deep-ledger")
    assert deep_resp.status_code == 200
    assert deep_resp.json()["aggregates"]["double_entry_balanced"] is True


@pytest.mark.api
async def test_configurable_envelopes_policy_reallocation(client: httpx.AsyncClient):
    """
    Verify updating Daily ($/day), Freedom ($/month), and Vault (%) via PUT /api/v1/me/policy
    immediately reallocates bucket balances via zero-sum transfers from/to Bank Foundation.
    """
    pol_get = await client.get("/api/v1/me/policy")
    assert pol_get.status_code == 200

    # Update Daily to $60.00 (6000), Freedom to $200.00 (20000), Vault to 25% (2500 bps)
    pol_put = await client.put(
        "/api/v1/me/policy",
        json={
            "daily_amount": 6000,
            "freedom_monthly_amount": 20000,
            "vault_skim_bps": 2500,
        },
    )
    assert pol_put.status_code == 200
    put_data = pol_put.json()
    assert put_data["status"] == "updated"
    assert put_data["policy"]["daily_amount"] == 6000
    assert put_data["policy"]["freedom_monthly_amount"] == 20000
    assert put_data["policy"]["vault_skim_bps"] == 2500

    buckets_map = {b["kind"]: b["available"] for b in put_data["buckets"]}
    assert buckets_map["daily"] == 6000
    assert buckets_map["freedom"] == 20000


@pytest.mark.api
async def test_midnight_rollover_and_payday_lifecycles(client: httpx.AsyncClient):
    """Verify automated Midnight Rollover and Payday Allocation lifecycles."""
    rollover_resp = await client.post(
        "/api/v1/paypal/rollover",
        json={"sweep_surplus_to_vault": True},
    )
    assert rollover_resp.status_code == 200
    r_data = rollover_resp.json()
    assert r_data["status"] == "completed"
    assert r_data["swept_to_vault_cents"] > 0

    payday_resp = await client.post(
        "/api/v1/paypal/payday",
        json={"gross_income_cents": 100000, "dispatch_vault_payout": True},
    )
    assert payday_resp.status_code == 200
    p_data = payday_resp.json()
    assert p_data["status"] == "allocated"
    assert p_data["vault_allocated_cents"] == 20000
    assert p_data["payout_batch_id"] is not None


@pytest.mark.api
async def test_advanced_analytics_chips_return_distinct_answers(client: httpx.AsyncClient):
    """
    Regression test for BUG-007:
    Clicking each of the 4 diagnostic chips in the Advanced Analytics section
    (with active filter_context attached) must return 4 distinct replies and short_tags.
    """
    filter_ctx = {
        "view_mode": "all",
        "bucket": None,
        "state": None,
        "entry_kind": None,
        "selected_rows": None,
        "total_shown": 14,
    }

    chips = [
        ("Explain my Bank double-entry flows and where income moved.", "bank double-entry flows"),
        ("Diagnose my Daily living velocity, runway in days, and rollover streak.", "velocity and runway"),
        ("Analyze active grid records for spending anomalies and deviations.", "spending anomalies"),
        ("How is my monthly Freedom envelope trajectory tracking against rent?", "freedom vs rent"),
    ]

    replies = set()
    for prompt, expected_tag in chips:
        resp = await client.post(
            "/api/v1/coach/messages",
            json={"utterance": prompt, "filter_context": filter_ctx},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["short_tag"] == expected_tag
        replies.add(data["reply"])

    # Every chip must produce a unique answer
    assert len(replies) == 4
