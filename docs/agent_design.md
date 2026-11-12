# Agent Design: Monolithic Single-Call Architecture & Deterministic Guardrails (`Propose → Verify → Confirm → Execute`)

FireWallet pairs proactive spending control with reactive financial literacy. For production reliability and hackathon performance, FireWallet avoids fragile multi-agent frameworks (which multiply latency and failure points) and instead uses a **monolithic single-call agent with structured outputs** (powered by Groq `openai/gpt-oss-120b` or OpenAI `gpt-4o-mini`) strictly paired with **deterministic Python guardrails** (`LedgerEngine`).

Related: **[problems.md](problems.md) (Problem 4 & Problem 5 — AI Visibility, Eval & Emergency Guardrail Gates)**, [architecture.md](architecture.md), [insights.md](insights.md), [TRINITY_RULES.md](TRINITY_RULES.md), [paypal_integration.md](paypal_integration.md).

```mermaid
flowchart LR
  subgraph Stage 1: Propose (Single LLM Call)
    Agent[Monolithic Agent<br/><i>Groq openai/gpt-oss-120b / OpenAI</i><br/>Structured Output: CoachDecision]
  end

  subgraph Stage 2: Verify (Deterministic Python)
    PolicyEngine[Policy Engine & Guardrails<br/><i>can_spend & Emergency Verifier</i>]
    LedgerHold[Ledger HOLD / Transfer<br/><i>SQLModel Lock</i>]
  end

  subgraph Stage 3: Confirm (Human Commitment)
    ActionCard[1-Tap Action Card<br/><i>[Pay $24 with PayPal]</i><br/><i>[Escape Window / Emergency Unlock]</i>]
  end

  subgraph Stage 4: Execute (PayPal & Settlement)
    PayPalClient[PayPal Executor<br/><i>Orders v2 & Payouts Sandbox</i>]
    WebhookReconcile[Webhook Router<br/><i>/api/v1/webhooks/paypal</i>]
  end

  Agent -->|CoachDecision + ActionCard| ActionCard
  ActionCard -->|1-Click User Confirmation| PolicyEngine
  PolicyEngine -->|Authorized| LedgerHold
  LedgerHold -->|Active Hold| PayPalClient
  PayPalClient -->|Payment Capture| WebhookReconcile
```

---

## 1. The Monolithic Agent (`CoachDecision`) & The Agentic Pattern

FireWallet's agentic commerce loop follows a strict four-step invariant: **Propose → Verify → Confirm → Execute**. Instead of multiple LLM agents chatting with each other, a single LLM call handles both the **Voice** (conversational text) and the **Proposal** (`CoachDecision` + `ActionCard`), while deterministic code verifies and executes.

### Schema (`CoachDecision`)
```json
{
  "reply": "Everyday groceries fit comfortably in your Daily Allowance ($52 remaining).",
  "status": "allowed",
  "confidence": 0.95,
  "rationale": "Sufficient Daily Living balance.",
  "target_bucket": "daily",
  "is_emergency": false,
  "cooldown_seconds": 0,
  "action_card": {
    "action_type": "paypal_checkout",
    "title": "Pay $24.00 with PayPal",
    "amount_cents": 2400,
    "target_bucket": "daily"
  }
}
```

### Emergency Override Detection (Zero-Cooldown Rule)
When evaluating Escape Window overrides (`POST /api/v1/overrides`):
- **Valid Emergency** (e.g. medical copay, urgent car repair, critical utility):
  - `is_emergency = true`
  - `cooldown_seconds = 0` $\rightarrow$ **Immediate unlock without delay!**
- **Non-Emergency Splurge** (e.g. takeout, concert tickets, impulse luxury):
  - `is_emergency = false`
  - `cooldown_seconds = 180` $\rightarrow$ **Enforces standard 180s cooldown timer + 200-char confession**.

---

## 2. Stage 1 (Propose): Intent Agent (`agents/intent/`)

The Intent Agent is the proactive gate: no PayPal call can be initiated until the user's natural-language *why* is parsed, categorized, and evaluated.

### Hard boundaries
- The Intent Agent **must not** call PayPal HTTP endpoints.
- The Intent Agent **must not** debit balances or create ledger holds directly.
- The Intent Agent **must not** approve policy overrides.
- If the LLM is unavailable or times out, the system **fails closed**: the API returns HTTP 503, and no PayPal order or hold is created.

### Input
Supplied to the agent by `POST /intents`:
- `utterance` (e.g., *"Buying groceries at Trader Joe's"*, *"Late-night DoorDash sushi"*)
- `amount_minor` (integer cents, from form input)
- `currency` (`"USD"`)
- `merchant_name` (optional string)
- `local_time` (user-local hour and weekday for late-night heuristics)
- `bucket_snapshot` (current available balances of Bank, Daily, Freedom, Vault, Bills injected by the server from PostgreSQL)

### Output schema (Pydantic / JSON Mode)
The agent must return structured JSON matching this schema:

```json
{
  "category": "groceries",
  "necessity": "daily_living",
  "recommended_bucket": "daily",
  "confidence": 0.95,
  "rationale": "Everyday groceries belong in your Daily Allowance.",
  "flags": []
}
```

- **necessity:** `bill` | `daily_living` | `freedom` | `ambiguous`
- **recommended_bucket:** `bills` | `daily` | `freedom` | `bank` | `none`
- **category:** `rent`, `utilities`, `groceries`, `transit`, `healthcare`, `eating_out`, `entertainment`, `gaming`, `shopping`, `subscription`, `transfer`, `other`
- **flags:** `late_night`, `merchant_luxury`, `recurring_like`, `possible_bill`

### Routing rules
- `necessity = daily_living` $\rightarrow$ routes to `daily`. If Daily is exhausted, user is prompted to wait for the morning top-up or perform a Bank friction override.
- `necessity = freedom` $\rightarrow$ routes to `freedom`. If Freedom is burned, hard stop: requires override.
- `necessity = bill` $\rightarrow$ routes to `bills` or `bank`.
- `necessity = ambiguous` $\rightarrow$ system prompts user to pick Daily vs Freedom before proceeding.

---

## 2. Stage 2: Policy Engine (`ledger/`)

The Policy Engine is **deterministic Python code**; it is **NOT** an LLM.

### Responsibilities
1. Takes the parsed intent output and evaluates `can_spend(user, amount, source_bucket, necessity, override_state)`.
2. Verifies available balance (`posted - holds >= amount`).
3. Enforces Trinity bucket rules:
   - Bank direct spend requires completed override (confession + cooldown + optional partner 2FA).
   - Vault spend is forbidden.
   - Bills bucket is reserved for verified bills.
   - Daily and Freedom spend cannot exceed their respective available balances without an override.
4. Executes row-level database locking (`SELECT ... FOR UPDATE` on the bucket) and records a ledger row with `state = 'hold'`.

---

## 3. Stage 3: PayPal Executor (`paypal/`)

The PayPal Executor is **deterministic Python code** interfacing with the sandbox REST API (`api-m.sandbox.paypal.com`); it is **NOT** an LLM.

### Responsibilities
1. Only activates after the ledger `HOLD` has successfully committed.
2. Translates minor units to PayPal decimal strings without float rounding (e.g. `2450` cents $\rightarrow$ `"24.50"`).
3. Creates PayPal Orders v2 with `intent=CAPTURE` and returns the sandbox approval URL to the PWA.
4. Handles buyer return from PayPal hosted flow and triggers `POST /v2/checkout/orders/{id}/capture`.
5. Reconciles with PayPal Webhook (`PAYMENT.CAPTURE.COMPLETED`):
   - Validates webhook signature.
   - Checks `paypal_webhook_events.event_id` for idempotency.
   - Releases the `HOLD` and records the settled debit in `ledger_entries`.
6. Executes automated Payouts for Vault skims and fixed bill payments.
7. Governs Real-Time PayPal Account Routing (detailed in [docs/paypal_integration.md](paypal_integration.md#real-time-paypal-account-routing-architecture)):
   - **Orders v2 Payee Default**: Omits explicit `payee` in `purchase_units`, defaulting payee routing to the API credentials merchant account.
   - **Internal Envelopes**: Bucket rebalancing is purely on-ledger (`LedgerEngine.record_double_entry_transfer`) with zero external float.
   - **Emergency Disbursements**: Auto-routes to `vault` (cascading to `bank`), executing capture or Payouts with 0s cooldown bypass (`BUG-008`).
   - **Payouts Routing**: Routes explicitly via `items[0].receiver` to target email addresses (`PAYPAL_VAULT_RECEIVER_EMAIL`, `bill.payee_email`, `item.payee_email`).

---

## 4. Stage 4: Insights Coach (`agents/insights/`)

The Insights Coach is a **reactive conversational AI** designed to foster long-term financial literacy and mindfulness. It sits alongside the mobile HUD dashboard.

### Core purpose & persona
- **Tone:** Calm, encouraging, objective, and plain-spoken. Zero condescension or scolding.
- **Audience:** Tailored especially for students, irregular/gig earners, and impulse shoppers, while remaining approachable for anyone.
- **Literacy focus:** Explains financial concepts, explains what charts and statistics mean, provides contextual affordability checks, and helps users understand the "why" behind the Trinity firewall.

### Strict read-only boundary (Default) & Phase 5 Governed Execution
- By default, the Coach has **zero execution tools**. It has no access to raw PayPal API credentials, cannot initiate unconstrained Orders or Payouts, and cannot arbitrarily write to the database ledger.
- If the user asks the Coach to make a non-emergency purchase (e.g., *"Can you buy that $20 movie ticket for me?"* or *"Can I afford dinner out tonight?"*):
  1. The Coach analyzes affordability via the read-only `analytics/` service.
  2. The Coach provides feasibility feedback relative to the user's remaining Daily Allowance and Freedom envelope.
  3. The Coach returns a **deep link** to `/intent` with pre-filled fields (`suggest_intent`).
  4. The user must proceed through the standard Intent Gateway (Stage 1 $\rightarrow$ Stage 2 $\rightarrow$ Stage 3).
- **Phase 5 Governed Execution Paths**:
  1. **Autonomous Emergency Payment Execution (`BUG-008`)**: When a genuine life/medical/critical safety emergency is verified, the Coach is empowered to execute the transaction autonomously once payment details are verified (`POST /api/v1/coach/action`), drawing from `vault` (and cascading to `bank`) with a 0s cooldown bypass.
  2. **The Trinity Batch Dispatcher**: The Coach generates structured proposals (`BatchDispatcherProposal`). After the user reviews and toggles items in the frontend staging modal, the backend executes sequential PayPal Payouts directly to obligation payees. Live sandbox credentials are required.

### Read-only tool set
The Coach interacts with the backend through dedicated read-only tools:
- `get_analytics_summary()`: Retrieves current bucket balances, weekly burn rate, and projected days until next income.
- `get_chart_context(chart_id)`: Explains the exact data, categories, and percentages behind a specific chart rendered on the HUD (e.g. `chart_pie_week`, `chart_rollover_sparkline`).
- `simulate_afford(amount_minor, category)`: Deterministically runs the proposed expense against current Daily and Freedom available balances, returning exact impact on rollover and remaining monthly fun money.

Full details and conversation prompts are specified in [insights.md](insights.md).

---

## 5. Phase 5 Implementation: The Trinity Batch Dispatcher & Autonomous Execution

Implemented in Phase 5 (see [features.md](features.md#1-the-trinity-batch-dispatcher), [ROADMAP_PHASE5.md](ROADMAP_PHASE5.md), and [paypal_integration.md](paypal_integration.md#real-time-paypal-account-routing-architecture)), the AI Coach pairs structured reasoning with governed execution workflows:

### Guardrail Invariant
1. The AI Coach produces **structured proposals** adhering to `BatchDispatcherProposal` (DTOs with titles, amounts in integer cents, categories, and risk assessments).
2. The user holds absolute **veto power** in the staging UI checklist (`BatchDispatcherModal`).
3. The AI Coach **never holds raw PayPal credentials**; the authorized batch is handed to the deterministic FastAPI `LedgerEngine` and PayPal client for sequential payout execution strictly against isolated Vault/Bills funds.
4. **Live Sandbox Requirement**: Execution requires active PayPal Sandbox credentials and returns HTTP 503 if offline or credentials are missing.


---

## 6. Live LLM Integration & Dynamic Generation Audit (Groq & Fallback Cascade)

To eliminate rigid, canned, or predetermined responses, the Financial Coach chat is driven by live LLM generation with transparent model routing:

1. **Active Primary Model (`openai/gpt-oss-120b`)**:
   - Integrated via Groq's high-speed inference engine (`GROQ_BASE_URL="https://api.groq.com/openai/v1"`).
   - Generates responses in ~1.7 seconds with full financial reasoning, context synthesis, and strict JSON schema output (`CoachDecision`).
2. **Dynamic Fallback Cascade**:
   - `backend/app/agents/shared/llm_client.py` implements a resilient multi-tier cascade across active candidate models:
     `["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]`.
   - If a model is deprecated or returns HTTP 404 (`model_not_found`), the client automatically cascades to the next candidate model rather than trapping the conversation in an offline fallback.
3. **Elimination of Canned / Predetermined Traps**:
   - Previously, an outdated model identifier (`llama-3.3-70b-versatile`) failed with Groq 404s, silently diverting all queries into `_local_fallback()`.
   - With live keys and active models configured in `backend/.env`, all user chats (affordability queries, spend simulations, balance inquiries, and double-entry flow breakdowns) are dynamically generated. The only predetermined message is the initial greeting on empty threads.
4. **Attribution & Transparency**:
   - Dedicated health endpoint `GET /api/v1/coach/status` reports live connectivity, provider name, and model name.
   - `CoachMessageResponse` returns `provider` and `model` in its JSON payload, allowing the frontend to badge messages with live LLM attribution.

---

## Audit trail & persistence

Both agents log every execution to PostgreSQL:
- **`agent_runs`**:
  - `kind`: `'intent'` or `'insights'`
  - `model`, `prompt_version`, `latency_ms`
  - `raw_response` (JSONB)
  - `parsed` (JSONB)
  - `error` (nullable string)
- **`coach_threads` & `coach_messages`**:
  - Full transcript of user and assistant interactions.
  - Linked `chart_id` when the message is triggered by tapping a HUD chart.
  - Citations linking back to bucket kinds and time ranges.
