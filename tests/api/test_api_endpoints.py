import pytest
import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.intent import Intent

@pytest.mark.api
async def test_health_check(client: httpx.AsyncClient):
    """Verify system health endpoint returns 200 and FireWallet metadata."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "FireWallet"
    assert data["paypal_env"] == "sandbox"

@pytest.mark.api
async def test_get_buckets(client: httpx.AsyncClient):
    """Verify Trinity buckets endpoint returns 5 buckets with calculated available balances."""
    resp = await client.get("/api/v1/buckets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["currency"] == "USD"
    buckets = {b["kind"]: b for b in data["buckets"]}
    assert len(buckets) == 5
    assert buckets["bank"]["available"] == 80000
    assert buckets["daily"]["available"] == 5200
    assert buckets["freedom"]["available"] == 9000
    assert buckets["vault"]["available"] == 20000
    assert buckets["bills"]["available"] == 120000

@pytest.mark.api
async def test_get_hud_summary(client: httpx.AsyncClient):
    """Verify HUD stats summary endpoint generates responsive chart series."""
    resp = await client.get("/api/v1/stats/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "charts" in data
    assert len(data["charts"]) == 3
    chart_ids = [c["id"] for c in data["charts"]]
    assert "chart_pie_week" in chart_ids
    assert "chart_rollover_30d" in chart_ids
    assert "chart_freedom_burn" in chart_ids

@pytest.mark.api
async def test_get_deep_ledger_for_ag_grid(client: httpx.AsyncClient):
    """Verify Desktop AG Grid foundational data source returns rows, aggregates, and pagination."""
    resp = await client.get("/api/v1/analytics/deep-ledger?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_count" in data
    assert data["total_count"] >= 5
    assert "items" in data
    assert "aggregates" in data

    # Test filtering by bucket
    resp_filtered = await client.get("/api/v1/analytics/deep-ledger?bucket=daily")
    assert resp_filtered.status_code == 200
    data_fil = resp_filtered.json()
    assert all(item["bucket"] == "daily" for item in data_fil["items"])

@pytest.mark.api
async def test_submit_intent_allowed(client: httpx.AsyncClient):
    """Verify submitting a legitimate daily living spend yields an allowed intent status."""
    payload = {
        "utterance": "Buying bread and vegetables at Trader Joe's",
        "amount": 1800,  # $18.00 fits within Daily's $52.00
        "merchant_name": "Trader Joe's"
    }
    resp = await client.post("/api/v1/intents", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "allowed"
    assert data["category"] == "groceries"
    assert data["override_required"] is False

@pytest.mark.api
async def test_submit_intent_needs_override(client: httpx.AsyncClient):
    """Verify spending that exhausts the Daily Allowance triggers the needs_override firewall status."""
    payload = {
        "utterance": "Impulse buy luxury winter jacket",
        "amount": 25000,  # $250.00 far exceeds Daily's $52.00 and Freedom's $90.00
        "merchant_name": "Zara"
    }
    resp = await client.post("/api/v1/intents", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "needs_override"
    assert data["override_required"] is True

@pytest.mark.api
async def test_override_escape_window_confession_and_cooldown(
    client: httpx.AsyncClient,
    seeded_session: AsyncSession
):
    """Verify Escape Window enforces minimum 200 characters and blocks premature cooldown unlocking."""
    # 1. Create intent needing override
    intent_resp = await client.post("/api/v1/intents", json={
        "utterance": "Fancy dinner at steakhouse with friends",
        "amount": 12000,  # $120.00
        "merchant_name": "Prime Steak"
    })
    intent_id = intent_resp.json()["id"]

    # 2. Gate 1: Reject short confession (< 200 chars)
    short_body = {
        "intent_id": intent_id,
        "body": "I really just want a good steak tonight, please let me spend."
    }
    short_resp = await client.post("/api/v1/overrides", json=short_body)
    assert short_resp.status_code == 422
    assert "at least 200 characters" in short_resp.json()["detail"]

    # 3. Valid 200+ char confession
    valid_confession = (
        "I am choosing to spend $120.00 from my emergency reserves because I am celebrating "
        "my best friend's promotion tonight. I understand this dips past my Daily Allowance and "
        "I am committing to cutting back on discretionary spending next week to restore my balance."
    )
    assert len(valid_confession) >= 200

    valid_resp = await client.post("/api/v1/overrides", json={
        "intent_id": intent_id,
        "body": valid_confession
    })
    assert valid_resp.status_code == 201
    override_data = valid_resp.json()
    override_id = override_data["id"]
    assert override_data["status"] == "pending"
    assert override_data["cooldown_seconds"] == 180

    # 4. Gate 2: Premature cooldown check (immediately after creation) must fail with HTTP 409
    cooldown_resp = await client.post(f"/api/v1/overrides/{override_id}/check-cooldown")
    assert cooldown_resp.status_code == 409
    assert "Cooldown active" in cooldown_resp.json()["detail"]

@pytest.mark.api
async def test_coach_message_endpoint(client: httpx.AsyncClient):
    """Verify Financial Coach responds with advice, citations, and suggested intents."""
    resp = await client.post("/api/v1/coach/messages", json={
        "utterance": "Can I afford to buy a $15 movie ticket today?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "thread_id" in data
    assert "citations" in data
    assert data["suggest_intent"] is not None
    assert data["suggest_intent"]["amount"] == 1500
