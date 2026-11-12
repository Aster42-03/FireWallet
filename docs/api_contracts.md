# API Contracts Specification

FastAPI generates OpenAPI 3.1 contracts dynamically from SQLModel and Pydantic schemas (see [openapi.json](openapi.json)). This document serves as the hand-written reference contract for the frontend, agents, and external integrations.

Related: **[problems.md](problems.md) (Core Build & API Contract Gate)**, [openapi.json](openapi.json), [architecture.md](architecture.md).

> [!IMPORTANT]
> **API Verification Gate ([problems.md](problems.md)):**
> Every route must be verified against **[problems.md](problems.md)**: Webhook endpoint path is strictly `/api/v1/webhooks/paypal` (Problem 1), PayPal balance queries report `source: "live" | "simulated"` (Problem 1), and lifecycle simulation controls are exposed for judge testing (Problem 2).

- **Base URL Prefix:** All API endpoints are namespaced under `/api/v1` (configured via `settings.API_V1_STR`), with the exception of system root `/` and `/health`.
- **Authentication:** Session cookie or `Authorization: Bearer <token>` established after Login with PayPal (or seeded sandbox demo user). Webhook routes are verified cryptographically via PayPal signature headers.
- **Money Format:** **integer minor units** (`amount: 2450` = $24.50) plus ISO currency `currency: "USD"`. Float amounts are strictly rejected across all endpoints.

---

## Common Error Codes

| HTTP Status | Trigger Condition |
| :--- | :--- |
| **401 Unauthorized** | Missing, expired, or invalid user session. |
| **404 Not Found** | Target resource (intent, override, thread, bill) does not exist for the authenticated user. |
| **409 Conflict** | Cooldown still active, insufficient bucket balance, or state machine conflict. |
| **422 Unprocessable Content** | Pydantic validation failure (e.g., negative amount, missing utterance, or confession < 200 chars). |
| **503 Service Unavailable** | LLM inference or PayPal Sandbox API failure; **fail-closed, no partial captures**. |

### Example 409 Cooldown Conflict:
```json
{
  "error": "cooldown_active",
  "detail": "Cooldown active. 142 seconds remaining.",
  "ready_at": "2026-11-08T18:30:00Z"
}
```

### Example 503 Coach Service Unavailable:
```json
{
  "error": "coach_unavailable",
  "detail": "Financial Coach reasoning model is temporarily offline. Deep AG Grid analytics and core firewall remain active."
}
```

---

## 1. User & Policy (`/api/v1/me`)

### `GET /api/v1/me`
Retrieves current authenticated user and active Trinity policy.

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@sandbox.paypal.com",
  "display_name": "Aster",
  "timezone": "America/New_York",
  "policy": {
    "currency": "USD",
    "vault_skim_bps": 2000,
    "daily_amount": 4000,
    "freedom_monthly_amount": 15000,
    "bank_spend_requires_override": true,
    "vault_spend_allowed": false,
    "override_min_chars": 200,
    "override_cooldown_seconds": 180,
    "partner_required_for_bank": false,
    "freedom_leftover_sweep_to_vault": false
  }
}
```

### `GET /api/v1/me/policy`
Retrieves the user's active `BudgetPolicy`.

### `PUT /api/v1/me/policy` & `PATCH /api/v1/me/policy`
Updates envelope limits, Vault skim basis points, or reflection friction settings.
```json
{
  "daily_amount": 4500,
  "freedom_monthly_amount": 20000,
  "vault_skim_bps": 2500,
  "override_min_chars": 200,
  "override_cooldown_seconds": 180
}
```

---

## 2. Buckets & Ledger (`/api/v1/buckets`, `/api/v1/ledger`)

### `GET /api/v1/buckets`
Returns balance summaries for all 5 Trinity buckets (`bank`, `daily`, `freedom`, `vault`, `bills`).
```json
{
  "buckets": [
    { "kind": "bank", "name": "Bank Foundation", "available": 85000, "held": 0, "pending_paypal": 0 },
    { "kind": "daily", "name": "Daily Living", "available": 4000, "held": 0, "pending_paypal": 0 },
    { "kind": "freedom", "name": "Freedom Envelope", "available": 12000, "held": 0, "pending_paypal": 0 },
    { "kind": "vault", "name": "Savings Vault", "available": 45000, "held": 0, "pending_paypal": 0 },
    { "kind": "bills", "name": "Reserved Bills", "available": 120000, "held": 0, "pending_paypal": 0 }
  ]
}
```

### `GET /api/v1/ledger`
Queries chronological double-entry ledger entries with filtering and pagination.
- **Query Parameters:** `bucket_kind` (string), `state` (`hold`, `posted`, `released`), `limit` (default: 50), `offset` (default: 0).

---

## 3. Intent Gateway (Proactive Firewall)

### `POST /api/v1/intents`
Submits a natural-language spend intention to the NLP classifier and deterministic policy engine.
Request:
```json
{
  "utterance": "Buying fresh groceries for dinner at Trader Joe's",
  "amount": 2450,
  "currency": "USD",
  "merchant_name": "Trader Joe's"
}
```
Response `200`:
```json
{
  "id": "intent-uuid",
  "status": "allowed",
  "short_tag": "groceries",
  "target_bucket": "daily",
  "confidence": 0.96,
  "rationale": "Sufficient Daily Living balance.",
  "is_emergency": false,
  "cooldown_seconds": 0,
  "action_card": {
    "action_type": "paypal_checkout",
    "title": "Pay $24.50 with PayPal",
    "description": "Drawn from Daily Living ($40.00 remaining).",
    "button_text": "Confirm & Pay $24.50",
    "amount_cents": 2450,
    "target_bucket": "daily"
  }
}
```

### `GET /api/v1/intents/tags`
Retrieves recorded unique 2-5 word `short_tag` values associated with the user's past intents (e.g. `groceries`, `takeout`, `train ticket`) for RAG lookup.

### `GET /api/v1/intents/{id}`
Retrieves the status, tags, and lifecycle logs of a single spend intent.

### `POST /api/v1/intents/{id}/confirm`
User confirms intention. Verifies deterministic `can_spend` and places an atomic double-entry `HOLD` lock.

### `POST /api/v1/intents/{id}/execute`
Creates a PayPal Sandbox Order (v2) with `intent=CAPTURE` and returns the `approval_url`.

### `POST /api/v1/intents/{id}/capture`
Captures an approved PayPal order and transitions ledger hold to `settled`.

---

## 4. Escape Window & Overrides (`/api/v1/overrides`)

### `POST /api/v1/overrides`
Initiates an Escape Window override to spend from Bank Foundation or execute an emergency transaction.
Request:
```json
{
  "intent_id": "intent-uuid",
  "body": "I understand my Freedom envelope is empty. I am choosing to raid Bank Foundation for this urgent equipment repair because I have client deliverables due tomorrow morning."
}
```
Response `201` (Discretionary Splurge Path):
```json
{
  "id": "override-uuid",
  "status": "pending",
  "ready_at": "2026-11-08T18:33:00Z",
  "cooldown_seconds": 180,
  "partner_required": false,
  "is_emergency": false,
  "short_tag": "equipment repair"
}
```
Response `201` (Verified Emergency Path):
```json
{
  "id": "override-uuid",
  "status": "approved",
  "ready_at": "2026-11-08T18:30:00Z",
  "cooldown_seconds": 0,
  "partner_required": false,
  "is_emergency": true,
  "short_tag": "emergency repair"
}
```

### `POST /api/v1/overrides/{override_id}/check-cooldown`
Verifies whether the cooldown countdown has expired. If `now >= ready_at`, marks override as `approved` and unlocks the associated intent for checkout.

---

## 5. Financial Coach & Deep Analytics (`/api/v1/coach`, `/api/v1/analytics`)

### `GET /api/v1/coach/status`
Returns connectivity, active LLM provider, and active model (e.g. `Groq: openai/gpt-oss-120b`).

### `POST /api/v1/coach/messages`
Sends a query to the Unified Monolithic Financial Coach.
Request:
```json
{
  "message": "Can I afford to spend $35 on sushi tonight?",
  "chart_id": null,
  "filter_context": null
}
```
Response `200`:
```json
{
  "id": "msg-uuid",
  "thread_id": "thread-uuid",
  "role": "coach",
  "reply": "You currently have $40.00 left in your Daily Living envelope. Spending $35.00 fits within today's limit, leaving $5.00 for the rest of the day.",
  "status": "allowed",
  "target_bucket": "daily",
  "confidence": 0.95,
  "action_card": {
    "action_type": "paypal_checkout",
    "title": "Pay $35.00 with PayPal",
    "description": "Drawn from Daily Living",
    "button_text": "Confirm & Pay $35.00",
    "amount_cents": 3500,
    "target_bucket": "daily"
  },
  "provider": "Groq",
  "model": "openai/gpt-oss-120b"
}
```

### `POST /api/v1/coach/execute-action`
Executes a 1-tap action card button directly from the Coach chat stream (`paypal_checkout` or `sweep_to_vault`).

### `GET /api/v1/coach/threads`
Lists user conversation threads with the Coach.

### `GET /api/v1/coach/threads/{id}/messages`
Retrieves message history for a specific conversation thread.

### `GET /api/v1/stats/summary`
Returns high-level HUD summary telemetry (burn rates, rollover streaks, days to payday).

### `GET /api/v1/analytics/deep-ledger`
Powers the foundational **AG Grid** desktop deep analytics workbench. Supports column filtering, multi-column sorting, date intervals, and category groupings.

### `GET /api/v1/analytics/anomalies`
Detects spending spikes exceeding $1.5\sigma$ above the rolling historical baseline.

---

## 6. PayPal Sandbox & Automated Lifecycles (`/api/v1/paypal`)

### `GET /api/v1/paypal/balance`
Directly queries the PayPal Sandbox Reporting API (`GET /v1/reporting/balances?currency_code=USD`) for live liquid account balances.

### `POST /api/v1/paypal/sync-balance`
Queries the live PayPal Sandbox balance and synchronizes all 5 Trinity buckets via zero-sum double-entry ledger transfers according to the user's active `BudgetPolicy`.
Request:
```json
{
  "override_balance_cents": null
}
```

### `POST /api/v1/paypal/rollover`
Executes the user-local midnight rollover routine: records rollover streaks, evaluates unspent Daily funds, optionally sweeps surplus to Vault, and replenishes Daily from Bank.

### `POST /api/v1/paypal/payday`
Executes income inflow allocation: splits incoming capital into Bills reservations, Vault savings skims (with optional automated PayPal Payout to Vault Receiver), and Bank Foundation.
Request:
```json
{
  "gross_income_cents": 250000,
  "dispatch_vault_payout": true
}
```

---

## 7. Bills (`/api/v1/bills`)

### `GET /api/v1/bills`
Lists scheduled obligations, due dates, and payment statuses.

### `POST /api/v1/bills`
Registers a new recurring bill obligation.

### `POST /api/v1/bills/{id}/pay`
Executes an immediate bill payout from reserved Bills funds.

### `POST /api/v1/bills/batch-dispatcher/propose`
Analyzes pending obligations and current isolated balances, returning a `BatchDispatcherProposal` with coach guidance and human veto options.

### `GET /api/v1/bills/batch-dispatcher/queue`
Returns all currently staged `BatchPaymentItem` records for the user along with isolated reserve balances.

### `POST /api/v1/bills/batch-dispatcher/stage-intent`
Stages an evaluated intent or custom obligation into the Batch Dispatcher staging queue.
Request (`BatchStageIntentRequest`):
```json
{
  "recipient_email": "payee@sandbox.paypal.com",
  "amount_cents": 3500,
  "currency": "USD",
  "category": "utilities",
  "source_bucket": "bills",
  "note": "Quarterly Water Bill"
}
```
Response (`BatchStageIntentResponse`):
```json
{
  "success": true,
  "batch_item_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "recipient_email": "payee@sandbox.paypal.com",
  "amount_cents": 3500,
  "source_bucket": "bills",
  "status": "pending_approval"
}
```

### `POST /api/v1/bills/batch-dispatcher/execute`
Atomically dispatches approved obligations via PayPal Batch Payouts (`POST /v1/payments/payouts`) with blast radius containment.
Request (`BatchExecuteRequest`):
```json
{
  "approved_item_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
  "source_bucket": "bills"
}
```
Response (`BatchExecutionSummary`):
```json
{
  "status": "completed",
  "payout_batch_id": "PAYOUT-NDM5R6RLZJWKG",
  "batch_status": "SUCCESS",
  "executed_count": 1,
  "failed_count": 0,
  "total_amount_minor": 3500,
  "remaining_isolated_balance_minor": 116500,
  "message": "Batch payout of 1 item(s) ($35.00) completed via PayPal Sandbox."
}
```

### `GET /api/v1/bills/batch-dispatcher/status/{payout_batch_id}`
Queries live PayPal settlement status and atomically updates `BatchPaymentItem`, `Bill`, and `Intent` records in SQLite.
Response (`BatchStatusResponse`):
```json
{
  "payout_batch_id": "PAYOUT-NDM5R6RLZJWKG",
  "batch_status": "SUCCESS",
  "time_created": "2026-11-12T16:03:47Z",
  "time_completed": "2026-11-12T16:04:20Z",
  "total_amount": "35.00",
  "fees": "0.25",
  "items": []
}
```

---

## 8. Webhooks (`/api/v1/webhooks/paypal`)

### `POST /api/v1/webhooks/paypal`
Receives raw PayPal webhook event notifications (`PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.PAYOUTSBATCH.SUCCESS`, etc.). Validates PayPal cryptographic signature headers and reconciles ledger holds atomically (`pending -> processed`).
