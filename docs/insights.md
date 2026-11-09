# Financial Coach & Deep Intelligence

The **Financial Coach** (`agents/insights/`) is FireWallet’s reactive AI reasoning partner. While the **Intent Gateway** proactively enforces the Trinity bucket constraints to block impulsive spending, the Coach operates beside the mobile HUD and the desktop **AG Grid** workbench to build financial literacy, explain complex spending patterns, and provide deep analytical reasoning.

Related: **[problems.md](problems.md) (Problem 4 — AI Layer & Tool Visibility Gate)**, [TOOL_STACK.md](TOOL_STACK.md), [architecture.md](architecture.md), [frontend.md](frontend.md), [api_contracts.md](api_contracts.md), [TRINITY_RULES.md](TRINITY_RULES.md).

> [!IMPORTANT]
> **AI Layer Verification Gate ([problems.md](problems.md) Problem 4):**
> The Coach must be visibly live, consequential, and grounded in real telemetry:
> - **Tool Citations:** Responses must cite live verified tool calls (e.g. *"Checked: Freedom $5.00, Daily $52.00, 14 transactions"*).
> - **Live Transparency:** Active model and provider are reported via `GET /api/v1/coach/status`, badging messages with live attribution (`openai/gpt-oss-120b`). Offline fallback must only appear as a badged Offline Mode.
> - **Eval Harness:** Category and necessity accuracy evaluated across 30–50 labeled intents with prompt-injection defense results.

---

## 1. Advanced Reasoning Persona & Tone

The Coach uses an **Advanced Reasoning Model** configured to balance high-level financial analysis with plain-spoken clarity:

- **Tone:** Calm, encouraging, objective, and deeply analytical. Never uses scolding, shame, or Wall Street jargon.
- **Audience:** Tailored for **students** on tight allowances and **irregular/gig earners** managing fluctuating income bursts, while scaling up to complex analytical inquiries from power users on the desktop AG Grid view.
- **Dual Communication Mode:**
  - **Quick Mobile Advice (HUD Mode):** Short, actionable answers (e.g., *"You have $25 left in Freedom. This $20 ticket fits comfortably."*).
  - **Deep Analytical Reasoning (Desktop AG Grid Mode):** Multi-variable comparative analysis (e.g., *"Between October 1st and October 15th, your grocery spending accelerated 38% compared to September. This was offset by a 4-day Daily rollover streak, keeping your Bank foundation untouched."*).

---

## 2. Interactive Intelligence Loops

### Loop A: Chart & Statistic Literacy (`chart_id`)
Tapping "Ask Coach" on any mobile HUD chart emits its stable `chart_id`:
- *User asks:* “What does this pie chart mean?” with `chart_id="chart_pie_week"`.
- *Coach reply:* “This chart shows where your Daily Allowance went over the last 7 days: 62% ($78) to groceries and 38% ($48) to transit. Your grocery spending is well within your $40 daily target.”

### Loop B: Contextual Affordability Simulation (`simulate_afford`)
Simulates the impact of a prospective expense against Trinity invariants:
- *User asks:* “Can I afford a $20 movie ticket tonight?”
- *Coach tool:* Calls `simulate_afford(amount_minor=2000, category="entertainment")`.
- *Coach reply:* “Yes, you can afford it! You have $45 remaining in your Freedom envelope. Spending $20 leaves $25 of fun money for the rest of the month without affecting groceries or rent.”
- *Handoff:* Attaches `suggest_intent` linking to `/intent`.

### Loop C: Firewall Explanations
Helps users understand why a specific transaction was blocked:
- *User asks:* “Why was my DoorDash order blocked earlier?”
- *Coach reply:* “Your Freedom envelope is at $0 for the month, and your Daily Allowance only had $6 left. FireWallet blocked the purchase because otherwise, it would have raided your Bank bucket, which is reserved for your upcoming $1,200 rent payment. If you must order, use the Escape Window override on your dashboard.”

### Loop D: Deep Analysis & AG Grid Interrogation (`filter_context`)
When using the desktop **AG Grid** workbench (`/analytics/deep-ledger`), the user can select rows or apply complex filters and click **"Analyze with Coach"**:
- *Context Passed:* Filtered transaction rows (`category='eating_out'`, dates: last 45 days).
- *User asks:* “Why did my dining-out spending surge recently, and how did it affect my rollover?”
- *Coach reasoning:*
  1. Calls `query_deep_ledger()` and `detect_spending_anomalies(category="eating_out")`.
  2. Identifies a 42% acceleration in dining expenses concentrated on weekend late nights.
  3. Notes that while Daily rollover absorbed 60% of the variance, Freedom was prematurely depleted 12 days before the end of the month.
  4. Recommends raising the Daily target by $5/day or transferring leftover Freedom surplus to Vault at month's end.

---

## 3. Strict Guardrails & Security Boundaries

1. **Strictly Read-Only:**
   - The Coach has **no tools** to write to the database or call PayPal APIs.
   - It cannot create Orders, execute Payouts, alter bucket balances, or grant overrides.
   - If asked to *"Buy this for me"*, the Coach provides an affordability evaluation and a 1-tap deep link to `/intent`.
2. **Session Scoping:** All queries to the Deep Analysis Layer automatically inject `user_id = session.user_id`. The model cannot inspect or query other users' financial records.
3. **No Vault Raids:** The Coach strictly defends the locked savings invariant and will never recommend spending Vault funds.
4. **No Investment or Tax Advice:** Deflects stock picks, crypto speculation, and tax filing questions back to everyday cash-flow mindfulness.

---

## 4. Deep Analysis Tool Set (`backend/app/analytics/deep_analytics.py`)

The Coach interacts with the backend using the following deterministic read-only tools:

### `get_analytics_summary()`
Returns current bucket balances, weekly burn rate, and days until next payday.

### `get_chart_context(chart_id: str)`
Retrieves data backing a visual chart:
- `chart_pie_week`: Category spending breakdown and percentages over the trailing 7 days.
- `chart_rollover_30d`: Daily end-of-day leftover balances over the last 30 days.
- `chart_freedom_burn`: Freedom envelope spend trajectory across the current month.

### `simulate_afford(amount_minor: int, category: str)`
Simulates the impact of a prospective purchase against `can_spend`:
- Tests Daily and Freedom availability.
- Assesses whether the spend would trigger a Bank raid or require an Escape Window override.
- Returns a structured feasibility payload.

### `query_deep_ledger(filters: dict, group_by: Optional[str] = None)`
Queries the foundational Deep Analysis Layer with granular parameters matching active AG Grid filters (e.g. buckets, transaction states, categories, date intervals).

### `detect_spending_anomalies(category: Optional[str] = None, window_days: int = 30)`
Analyzes spending velocity and identifies transactions or category aggregates that deviate significantly ($>2\sigma$) from the user's historical rolling baseline.

---

## 5. Future Agentic Loop: The Trinity Batch Dispatcher (Google AI Studio / Gemini Integration)

Documented for post-hackathon implementation in [features.md](features.md#1-the-trinity-batch-dispatcher).

In this loop, the Coach integrates with Google AI Studio / Gemini structured outputs to propose batch bill disbursements:
- **Proposal Generation:** Uses `BatchDispatcherProposal` schema (Pydantic v2) to bundle upcoming bills against isolated Vault/Bills earmarks.
- **Safety Invariant:** The Coach outputs structured recommendations and risk assessments; the user retains explicit veto power via the Staging Area before any execution occurs. Core emergency bank funds remain structurally insulated.
