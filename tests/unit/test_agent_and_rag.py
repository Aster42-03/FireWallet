"""
Agent, Short-Tag Distillation & RAG Memory Tests:
- Short-Tag Distillation (`groceries`, `takeout`, `gift for family`, `movie ticket`)
- RAG Historical Context Retrieval & Coach Citations
- Groq `llama-3.3-70b-versatile` Primary -> OpenAI `gpt-4o-mini` Fallback Cascade
- Emergency Zero-Delay Override (`cooldown_seconds == 0`) vs Luxury Splurge Guardrail
- Unified Monolithic Coach 1-Tap Action Cards (`paypal_checkout` & `sweep_to_vault`)
"""

import pytest
import httpx

from app.core.config import settings
from app.agents.rag import distill_short_tag, is_genuine_emergency
from app.agents.shared.llm_client import LLMClient, is_configured_api_key


@pytest.mark.unit
def test_short_tag_distillation_examples():
    """Verify concise 2-5 word summary tags match expected user categories."""
    assert distill_short_tag("Buying weekly groceries at Trader Joe's") == "groceries"
    assert distill_short_tag("Ordering late-night takeout from DoorDash") == "takeout"
    assert distill_short_tag("Picking up a birthday gift for family") == "gift for family"
    assert distill_short_tag("Can I afford to buy a $15 movie ticket today?") == "movie ticket"
    assert distill_short_tag("Urgent ER hospital copay for ankle injury") == "emergency medical care"
    assert distill_short_tag("Sweep $40 to vault savings") == "vault sweep"
    assert distill_short_tag("Spending $500 on luxury jacket") == "luxury jacket"
    assert distill_short_tag("Can I spend twenty dollars on takeout?") == "takeout"
    assert distill_short_tag("Explain how my rollover streak works") == "rollover streak"
    assert distill_short_tag("Why is my Bank Foundation bucket locked by default?") == "bank lock rule"
    assert distill_short_tag("Explain the high-friction Escape Window and cooldown") == "escape window rule"


@pytest.mark.unit
def test_parse_amount_cents_from_currency_signs_and_dollar_words():
    """Verify parsing amounts from $ signs, digits, and natural language dollar words."""
    from app.agents.rag import parse_amount_cents_from_text

    assert parse_amount_cents_from_text("Can I buy a $15 movie ticket?") == 1500
    assert parse_amount_cents_from_text("Can I spend 25 bucks on dinner?") == 2500
    assert parse_amount_cents_from_text("twenty dollars for books") == 2000
    assert parse_amount_cents_from_text("100 USD for shoes") == 10000
    assert parse_amount_cents_from_text("fifteen dollars for takeout") == 1500
    assert parse_amount_cents_from_text("fifty cents for candy") == 50
    assert parse_amount_cents_from_text("just saying hello") is None


@pytest.mark.unit
def test_emergency_detection_vs_luxury_false_positive():
    """
    Verify genuine medical/stranded/shutoff emergencies pass while luxury steakhouse
    celebrations mentioning 'emergency reserves' are strictly rejected as emergencies.
    """
    emerg_er, _ = is_genuine_emergency("At city hospital ER needing urgent $150 x-ray copay", "City Hospital")
    assert emerg_er is True

    emerg_car, _ = is_genuine_emergency("Stranded on highway with flat tire needing tow truck", "AAA Towing")
    assert emerg_car is True

    emerg_util, _ = is_genuine_emergency("Emergency power shutoff notice, paying electric utility", "ConEd")
    assert emerg_util is True

    false_pos, _ = is_genuine_emergency(
        "I am choosing to spend $120.00 from my emergency reserves because I am celebrating "
        "my best friend's promotion tonight at a steakhouse.",
        merchant_name="Prime Steak",
    )
    assert false_pos is False


@pytest.mark.unit
def test_llm_client_groq_primary_and_openai_fallback(monkeypatch: pytest.MonkeyPatch):
    """Verify placeholder key filtering and Groq -> OpenAI provider ordering."""
    assert is_configured_api_key("") is False
    assert is_configured_api_key("your_openai_or_gemini_api_key") is False
    assert is_configured_api_key("your_groq_api_key") is False
    assert is_configured_api_key("gsk_real_key_abc123456") is True
    assert is_configured_api_key("sk-proj-real_key_xyz987") is True

    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_real_key_abc123456")
    monkeypatch.setattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-proj-real_key_xyz987")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gpt-4o-mini")

    client = LLMClient()
    chain = client.get_provider_chain()
    assert len(chain) == 2
    assert chain[0][0] == "groq"
    assert chain[0][3] == "llama-3.3-70b-versatile"
    assert chain[1][0] == "openai"
    assert chain[1][3] == "gpt-4o-mini"


@pytest.mark.api
async def test_quick_intent_records_short_tags_and_lists_rag_tags(client: httpx.AsyncClient):
    """Verify Quick Intent persists `short_tag`, returns `verdict` + `action_card`, and lists tags."""
    r1 = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Ordering pad thai takeout on Uber Eats",
            "amount": 1900,
            "merchant_name": "Uber Eats",
        },
    )
    assert r1.status_code == 201
    d1 = r1.json()
    assert d1["verdict"] == "accepted"
    assert d1["short_tag"] == "takeout"
    assert d1["action_card"] is not None
    assert d1["action_card"]["action_type"] == "paypal_checkout"
    assert d1["action_card"]["short_tag"] == "takeout"

    r2 = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Buying a thoughtful gift for family",
            "amount": 2500,
            "merchant_name": "Etsy",
        },
    )
    assert r2.status_code == 201
    d2 = r2.json()
    assert d2["verdict"] == "accepted"
    assert d2["short_tag"] == "gift for family"

    tags_resp = await client.get("/api/v1/intents/tags")
    assert tags_resp.status_code == 200
    tags_data = tags_resp.json()
    recorded_tags = {item["short_tag"] for item in tags_data["items"]}
    assert "takeout" in recorded_tags
    assert "gift for family" in recorded_tags
    assert "groceries" in recorded_tags


@pytest.mark.api
async def test_emergency_override_grants_zero_cooldown_and_settles_from_bank(client: httpx.AsyncClient):
    """
    Verify that a genuine medical emergency exceeding Daily Allowance ($52.00) gets
    0-second cooldown approval without the 200-char wall and settles cleanly from Bank.
    """
    # 1. Submit $180.00 ER copay intent (> $52 Daily Allowance)
    intent_resp = await client.post(
        "/api/v1/intents",
        json={
            "utterance": "Urgent ER hospital copay for fractured wrist",
            "amount": 18000,
            "merchant_name": "City General Hospital",
        },
    )
    assert intent_resp.status_code == 201
    intent_data = intent_resp.json()
    assert intent_data["status"] in ("allowed", "needs_override")
    assert intent_data["is_emergency"] is True
    assert intent_data["cooldown_seconds"] == 0
    assert intent_data["short_tag"] == "emergency medical care"

    # 2. Submit concise emergency override (< 200 chars) -> instant approval, 0s cooldown!
    ov_resp = await client.post(
        "/api/v1/overrides",
        json={
            "intent_id": intent_data["id"],
            "body": "At City General ER right now paying x-ray and cast copay.",
        },
    )
    assert ov_resp.status_code == 201
    ov_data = ov_resp.json()
    assert ov_data["is_emergency"] is True
    assert ov_data["cooldown_seconds"] == 0
    assert ov_data["status"] == "approved"
    assert ov_data["short_tag"] == "emergency medical care"

    # 3. Immediate check-cooldown + execute + capture (zero delay!)
    chk = await client.post(f"/api/v1/overrides/{ov_data['id']}/check-cooldown")
    assert chk.status_code == 200

    exec_resp = await client.post(f"/api/v1/intents/{intent_data['id']}/execute")
    assert exec_resp.status_code == 200
    order_id = exec_resp.json()["paypal_order_id"]

    cap_resp = await client.post(
        f"/api/v1/intents/{intent_data['id']}/capture",
        json={"paypal_order_id": order_id},
    )
    assert cap_resp.status_code == 200
    assert cap_resp.json()["status"] == "settled"

    # 4. Verify Locked Savings Vault funded the $180.00 emergency ($200.00 -> $20.00, Bank remains $800.00)
    buckets_resp = await client.get("/api/v1/buckets")
    buckets = {b["kind"]: b["available"] for b in buckets_resp.json()["buckets"]}
    assert buckets["vault"] == 2000
    assert buckets["bank"] == 80000


@pytest.mark.api
async def test_unified_coach_one_tap_actions_and_rag_context(client: httpx.AsyncClient):
    """
    Verify Unified Monolithic Coach returns `CoachDecision`, `short_tag`, RAG citations,
    and executable 1-tap `ActionCard` payloads for both PayPal checkout and Vault sweeps.
    """
    # 1. Ask Coach about a $16 takeout purchase -> returns 1-tap PayPal ActionCard
    coach_resp = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "Can I buy $16 takeout tonight?"},
    )
    assert coach_resp.status_code == 200
    c_data = coach_resp.json()
    assert c_data["short_tag"] == "takeout"
    assert c_data["decision"]["status"] == "accepted"
    assert c_data["action_card"] is not None
    assert c_data["action_card"]["action_type"] == "paypal_checkout"
    assert c_data["action_card"]["amount_cents"] == 1600
    assert "rag_memory" in c_data["citations"]

    # Execute 1-tap PayPal ActionCard (creates PayPal order, returns approval_url)
    exec_pay = await client.post("/api/v1/coach/execute-action", json=c_data["action_card"])
    assert exec_pay.status_code == 200
    pay_data = exec_pay.json()
    assert pay_data["status"] == "awaiting_approval"
    assert pay_data["short_tag"] == "takeout"
    assert pay_data["source_bucket"] == "freedom"
    assert pay_data["paypal_order_id"] is not None
    assert "approval_url" in pay_data

    # Complete capture after buyer approval (Option 1 Interactive Checkout Loop)
    cap_resp = await client.post(
        f"/api/v1/intents/{pay_data['intent_id']}/capture",
        json={"paypal_order_id": pay_data["paypal_order_id"]},
    )
    assert cap_resp.status_code == 200
    cap_data = cap_resp.json()
    assert cap_data["status"] == "settled"

    # 2. Ask Coach to sweep $30 to Vault -> returns 1-tap sweep_to_vault ActionCard
    sweep_msg = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "Please sweep $30 to vault savings", "thread_id": c_data["thread_id"]},
    )
    assert sweep_msg.status_code == 200
    s_data = sweep_msg.json()
    assert s_data["short_tag"] == "vault sweep"
    assert s_data["action_card"]["action_type"] == "sweep_to_vault"
    assert s_data["action_card"]["amount_cents"] == 3000

    exec_sweep = await client.post("/api/v1/coach/execute-action", json=s_data["action_card"])
    assert exec_sweep.status_code == 200
    assert exec_sweep.json()["destination_bucket"] == "vault"

    # Verify balances: Freedom ($90 - $16 = $74), Bank ($800 - $30 = $770), Vault ($200 + $30 = $230)
    b_resp = await client.get("/api/v1/buckets")
    b_map = {b["kind"]: b["available"] for b in b_resp.json()["buckets"]}
    assert b_map["freedom"] == 7400
    assert b_map["bank"] == 77000
    assert b_map["vault"] == 23000

    # 3. Follow-up query about takeout -> RAG memory retrieves the newly recorded 'takeout' tag!
    followup = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "How much did I spend on takeout recently?", "thread_id": c_data["thread_id"]},
    )
    assert followup.status_code == 200

    # 4. Insight quick queries: Rollover Streak & Locked Bank explanation
    streak_msg = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "Explain how my rollover streak works and how unspent Daily funds roll over."},
    )
    assert streak_msg.status_code == 200
    st_data = streak_msg.json()
    assert "Rollover" in st_data["reply"] or "streak" in st_data["reply"].lower()
    assert st_data["short_tag"] == "rollover streak"

    bank_lock_msg = await client.post(
        "/api/v1/coach/messages",
        json={"utterance": "Why is my Bank Foundation bucket locked by default and how does it protect my bills?"},
    )
    assert bank_lock_msg.status_code == 200
    bl_data = bank_lock_msg.json()
    assert "Bank Foundation" in bl_data["reply"] or "Rule 4" in bl_data["reply"]
    assert bl_data["short_tag"] == "bank lock rule"
    rag_mem = followup.json()["citations"]["rag_memory"]
    matched_tags = {m["short_tag"] for m in rag_mem["matches"]}
    assert "takeout" in matched_tags
