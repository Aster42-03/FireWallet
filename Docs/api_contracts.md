# API contracts (draft)

FastAPI generates OpenAPI from SQLModel and Pydantic schemas. This document serves as the hand-written reference contract for the frontend, agents, and external integrations.

Auth: Session cookie or `Authorization: Bearer <token>` established after Login with PayPal (or seeded sandbox demo user). Webhook routes are unsigned by JWT but verified cryptographically via PayPal signature headers.

Money format: **integer minor units** (`amount: 2450` = $24.50) plus ISO currency `currency: "USD"`. Float amounts are strictly rejected.

---

## Common errors

| HTTP | When |
| --- | --- |
| 401 | Missing or expired user session |
| 409 | Cooldown active, idempotency conflict, or daily job already executed |
| 422 | Pydantic validation failure (e.g. negative amount or missing utterance) |
| 503 | LLM or PayPal unavailable; **fail-closed, no partial captures** |

Example 409 Error Body:
```json
{
  "error": "cooldown_active",
  "detail": "Escape window cooldown still active",
  "ready_at": "2026-11-01T12:03:00Z"
}
```

Example 503 Coach Error Body:
```json
{
  "error": "coach_unavailable",
  "detail": "Financial Coach reasoning model is temporarily offline. Deep AG Grid analytics and core firewall remain active."
}
```

---

## User & Policy

### `GET /me`
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

### `PATCH /me/policy`
Updates policy fields. Takes effect on subsequent transactions or scheduled jobs; not retroactive.

---

## Buckets & Ledger

### `GET /buckets`
Returns available, held, and in-flight amounts across all Trinity buckets.

```json
{
  "currency": "USD",
  "buckets": [
    { "kind": "bank", "name": "Bank", "available": 80000, "held": 0, "pending_paypal": 0 },
    { "kind": "daily", "name": "Daily Allowance", "available": 5200, "held": 0, "pending_paypal": 0 },
    { "kind": "freedom", "name": "Freedom", "available": 9000, "held": 0, "pending_paypal": 0 },
    { "kind": "vault", "name": "Vault", "available": 20000, "held": 0, "pending_paypal": 0 },
    { "kind": "bills", "name": "Bills", "available": 120000, "held": 0, "pending_paypal": 0 }
  ]
}
```

### `GET /ledger?bucket=daily&limit=50&cursor=`
Returns paginated double-entry ledger items.

```json
{
  "items": [
    {
      "id": "uuid",
      "bucket": "daily",
      "amount": -2450,
      "state": "posted",
      "intent_id": "uuid",
      "utterance": "Buying groceries",
      "paypal_capture_id": "8XY12345678",
      "posted_at": "2026-10-28T14:22:00Z"
    }
  ],
  "next_cursor": null
}
```

---

## Intent Gateway (Proactive Firewall)

### `POST /intents`
Header: `Idempotency-Key: <uuid>`

Request:
```json
{
  "utterance": "Buying groceries",
  "amount": 2450,
  "currency": "USD",
  "merchant_name": "Trader Joe's"
}
```

Response `201` (Allowed):
```json
{
  "id": "intent-uuid",
  "status": "allowed",
  "category": "groceries",
  "necessity": "daily_living",
  "recommended_bucket": "daily",
  "confidence": 0.96,
  "rationale": "Everyday groceries belong in your Daily Allowance.",
  "flags": [],
  "source_bucket": "daily",
  "balances_after_preview": {
    "daily_available": 2750
  }
}
```

Response `201` (Denied / Needs Override):
```json
{
  "id": "intent-uuid",
  "status": "needs_override",
  "category": "eating_out",
  "necessity": "freedom",
  "recommended_bucket": "freedom",
  "confidence": 0.92,
  "rationale": "Freedom envelope is depleted for this month. Dipping into Bank requires an Escape Window override.",
  "flags": ["late_night"],
  "source_bucket": "bank",
  "override_required": true
}
```

### `GET /intents/{id}`
Returns current lifecycle status (`allowed`, `hold`, `executing`, `settled`, `failed`).

### `POST /intents/{id}/confirm`
User accepts agent routing.

### `POST /intents/{id}/execute`
Creates ledger `HOLD` and PayPal Orders v2 record.

Response `200`:
```json
{
  "status": "executing",
  "paypal_order_id": "5O190127TN364715T",
  "approval_url": "https://www.sandbox.paypal.com/checkoutnow?token=5O190127TN364715T"
}
```

### `POST /intents/{id}/capture`
Client submits token after buyer completes PayPal approval modal:
```json
{
  "paypal_order_id": "5O190127TN364715T",
  "payer_id": "ABCDEF123456"
}
```

---

## Overrides (Escape Window)

### `POST /overrides`
Request:
```json
{
  "intent_id": "intent-uuid",
  "body": "I understand my Freedom envelope is empty. I am choosing to raid Bank for this takeout because I am working through the night on a project deadline."
}
```

Response `201`:
```json
{
  "id": "override-uuid",
  "status": "pending",
  "ready_at": "2026-10-28T22:33:00Z",
  "cooldown_seconds": 180,
  "partner_required": false
}
```

### `POST /overrides/{id}/partner-approve`
Body: `{ "token": "<magic_token>" }`. Approves Bank override if partner requirement is enabled.

---

## Deep Analytics & Financial Coach

### `GET /stats/summary?from=&to=`
Returns deterministic spending analytics for the mobile HUD. Runs entirely via SQL in `analytics/` without needing an LLM.

```json
{
  "spent_by_bucket": { "daily": 12000, "freedom": 4000 },
  "spent_by_category": { "groceries": 8000, "eating_out": 4000 },
  "rollover_end_of_day": [
    { "date": "2026-10-26", "daily_available": 1800 },
    { "date": "2026-10-27", "daily_available": 2400 }
  ],
  "vault_in": 20000,
  "bills_paid": 120000,
  "overrides_count": 1,
  "charts": [
    {
      "id": "chart_pie_week",
      "title": "7-Day Spend by Category",
      "type": "pie",
      "data": [
        { "category": "groceries", "amount": 8000, "percentage": 66.7 },
        { "category": "eating_out", "amount": 4000, "percentage": 33.3 }
      ]
    },
    {
      "id": "chart_rollover_30d",
      "title": "Daily Rollover Trail",
      "type": "sparkline",
      "data": [
        { "date": "2026-10-26", "rollover": 1800 },
        { "date": "2026-10-27", "rollover": 2400 }
      ]
    },
    {
      "id": "chart_freedom_burn",
      "title": "Freedom Envelope Burn",
      "type": "progress",
      "data": {
        "allocated": 15000,
        "spent": 4000,
        "remaining": 11000
      }
    }
  ]
}
```

### `GET /analytics/deep-ledger`
Powers the foundational desktop **AG Grid** "Advanced Ledger & Audit Log" view. Supports server-side filtering, multi-sorting, and date intervals.

Parameters:
- `bucket` (optional): `bank`, `daily`, `freedom`, `vault`, `bills`
- `state` (optional): `hold`, `posted`, `released`
- `category` (optional)
- `from` / `to` (ISO 8601 timestamps)
- `limit` (default: 100), `offset` (default: 0)
- `sort_by` (default: `created_at`), `sort_order` (`asc` / `desc`)

Response `200`:
```json
{
  "total_count": 284,
  "items": [
    {
      "id": "entry-uuid",
      "transfer_id": "transfer-uuid",
      "created_at": "2026-10-28T14:22:00Z",
      "category": "groceries",
      "bucket": "daily",
      "amount": -2450,
      "state": "posted",
      "utterance": "Trader Joe's groceries",
      "merchant": "Trader Joe's",
      "paypal_order_id": "5O190127TN364715T",
      "paypal_capture_id": "8XY12345678"
    }
  ],
  "aggregates": {
    "total_debits": 142050,
    "total_credits": 250000,
    "active_holds": 3500
  }
}
```

### `POST /coach/messages`
Sends a query to the Financial Coach (powered by the Advanced Reasoning Model). Can optionally target a `chart_id` or active AG Grid `filter_context`.

Request (General or Affordability Query):
```json
{
  "thread_id": "optional-uuid",
  "utterance": "Can I afford a $20 movie ticket tonight?",
  "chart_id": null,
  "filter_context": null
}
```

Response `200`:
```json
{
  "thread_id": "thread-uuid",
  "message_id": "msg-uuid",
  "reply": "Yes! You have $110 left in your Freedom envelope for this month. Spending $20 leaves $90 of fun money and protects your upcoming rent and grocery funds.",
  "citations": {
    "buckets": ["freedom"],
    "range": "current_month"
  },
  "suggest_intent": {
    "utterance": "Movie ticket",
    "amount": 2000,
    "category": "entertainment",
    "target_bucket": "freedom"
  }
}
```

Request with AG Grid `filter_context` (Deep Analysis Query):
```json
{
  "thread_id": "thread-uuid",
  "utterance": "Why did my dining-out spending surge recently, and how did it affect my rollover cushion?",
  "chart_id": null,
  "filter_context": {
    "category": "eating_out",
    "bucket": "freedom",
    "from": "2026-09-01T00:00:00Z",
    "to": "2026-10-28T00:00:00Z"
  }
}
```

Response `200`:
```json
{
  "thread_id": "thread-uuid",
  "message_id": "msg-uuid",
  "reply": "Based on the 14 transactions filtered in your ledger: Dining out accelerated 42% over the last 14 days, primarily driven by three weekend delivery orders totaling $115. While your Daily rollover cushion absorbed 60% of the variance, your Freedom envelope is now within $12 of empty with 3 days left in the month. To protect your Bank foundation, I recommend cooking from your Daily grocery allowance through Friday.",
  "citations": {
    "buckets": ["freedom", "daily", "bank"],
    "range": "60d",
    "transaction_count": 14
  },
  "suggest_intent": null
}
```

### `GET /coach/threads`
Lists user conversation threads with the Coach.

### `GET /coach/threads/{id}/messages`
Retrieves message history for a thread.

---

## Bills

### `GET /bills`
Lists scheduled bills and payment statuses.

### `POST /bills`
Registers a new bill.
```json
{
  "name": "Rent",
  "amount": 120000,
  "currency": "USD",
  "priority": 1,
  "due_date": "2026-11-01",
  "payee_email": "landlord@sandbox.paypal.com"
}
```

### `POST /bills/{id}/pay`
Executes an immediate bill payout from Bills/Bank reserve.

---

## Webhooks

### `POST /webhooks/paypal`
Receives raw PayPal webhook notifications (`PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.PAYOUTSBATCH.SUCCESS`, etc.). Verified via PayPal signature headers. Returns `200 { "ok": true }`.
