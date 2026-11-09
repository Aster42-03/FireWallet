# Data Model (Modern SQLModel ORM)

Async database access via modern **SQLModel** (SQLAlchemy 2.0 async + Pydantic v2) + **asyncpg** (production on Render) / **aiosqlite** (zero-config local dev). Money is modeled strictly in **`BIGINT` minor units** (integer cents). UUIDs for primary keys. Timestamps in `TIMESTAMPTZ` with timezone awareness (`datetime.now(timezone.utc)`).

Related: **[problems.md](problems.md) (Core Build & Schema Invariants Gate)**, [TRINITY_RULES.md](TRINITY_RULES.md), [api_contracts.md](api_contracts.md).

> [!IMPORTANT]
> **Data Tier Verification Gate ([problems.md](problems.md)):**
> Every model, migration, and query must be verified against PostgreSQL (Docker / Render) to test real enum types, JSONB, and `SELECT ... FOR UPDATE` row locks (per **[problems.md](problems.md) Problem 2**). Zero floats are permitted anywhere in ledger math.

All models in `backend/app/models/` adhere to the **Tripartite SQLModel Pattern**:
1. `*Base(SQLModel)`: Defines common attributes, constraints, and validation.
2. `*(Base, table=True)`: Persistent relational tables with primary keys, indexes, and foreign keys.
3. `*Read(Base)` & `*Update(SQLModel)`: API response and update DTOs.
4. Native Pydantic v2 serialization via `.model_dump()` throughout the entire codebase.

The double-entry ledger is the single source of truth for all balances. Analytics read models and the Insights Coach execute read-only queries against this schema. Alembic owns DDL migrations.

---

## ER Diagram (Active Relational Tables)

```
users
  ├── budget_policies (1:1 configuration)
  ├── buckets (bank, daily, freedom, vault, bills)
  │     └── ledger_entries (double-entry transactions)
  ├── intents (spend intentions & classifications)
  │     ├── agent_runs (kind='intent')
  │     ├── overrides (Escape Window & emergency friction)
  │     └── ledger_entries.intent_id
  ├── coach_threads
  │     ├── coach_messages
  │     └── agent_runs (kind='insights')
  ├── bills (recurring scheduled obligations)
  └── partner_links
        └── partner_approvals

paypal_webhook_events (idempotency log for inbound PayPal webhooks)
```

> [!NOTE]
> - **PayPal Integration:** Account credentials, client secrets, and target payout emails (`PAYPAL_VAULT_RECEIVER_EMAIL`, `PAYPAL_BILL_PAYEE_EMAIL`) are managed via server-side environment variables (`backend/.env`). Live liquid balances are queried on-demand from the PayPal Sandbox Reporting API (`GET /v1/reporting/balances`).
> - **Automated Lifecycles:** Midnight rollover and payday routines run via deterministic service jobs and API endpoints (`app/jobs/lifecycles.py` via `POST /api/v1/paypal/rollover` and `POST /api/v1/paypal/payday`) without requiring a separate `daily_runs` table.

---

## Types & Enums (PostgreSQL)

```sql
CREATE TYPE bucket_kind AS ENUM ('bank', 'daily', 'freedom', 'vault', 'bills', 'paypal_clearing');
CREATE TYPE intent_status AS ENUM (
  'draft', 'parsed', 'allowed', 'denied', 'needs_override',
  'override_pending', 'override_approved', 'override_rejected', 'override_expired',
  'hold', 'executing', 'settled', 'failed'
);
CREATE TYPE necessity AS ENUM ('bill', 'daily_living', 'freedom', 'ambiguous');
CREATE TYPE override_status AS ENUM ('pending', 'ready', 'approved', 'rejected', 'expired');
CREATE TYPE bill_status AS ENUM ('scheduled', 'paying', 'paid', 'blocked_insufficient', 'canceled');
CREATE TYPE ledger_state AS ENUM ('hold', 'posted', 'released', 'pending_paypal');
CREATE TYPE paypal_account_role AS ENUM ('user_buyer', 'vault_receiver', 'bill_payee', 'merchant');
CREATE TYPE agent_run_kind AS ENUM ('intent', 'insights');
CREATE TYPE coach_message_role AS ENUM ('user', 'assistant', 'system', 'tool');
```

---

## Tables

### `users`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | CITEXT UNIQUE | User email address |
| `display_name` | TEXT | Display name / nickname |
| `timezone` | TEXT | IANA timezone, e.g. `America/New_York` |
| `created_at` | TIMESTAMPTZ | Default `now()` |

### `budget_policies`

Configures the user's Trinity bucket caps, Vault skim basis points, and behavioral friction rules.

| Column | Type | Notes |
| --- | --- | --- |
| `user_id` | UUID PK FK users | 1:1 user policy configuration |
| `currency` | CHAR(3) | Default `'USD'` |
| `vault_skim_bps` | INT | Basis points skimmed to Vault on payday (e.g. 2000 = 20%) |
| `daily_amount` | BIGINT | Target Daily balance in minor units (e.g. 4000 = $40.00) |
| `freedom_monthly_amount` | BIGINT | Minor units credited to Freedom each calendar month |
| `bank_spend_requires_override` | BOOL | Default `true` |
| `vault_spend_allowed` | BOOL | Default `false` (Vault Emergency Reserve unlocked only on verified emergencies) |
| `override_min_chars` | INT | Confession length requirement (default: 200) |
| `override_cooldown_seconds` | INT | Escape window cooldown timer (default: 180) |
| `partner_required_for_bank` | BOOL | Requires partner 2FA approval for Bank overrides |
| `freedom_leftover_sweep_to_vault` | BOOL | Default `false` |
| `updated_at` | TIMESTAMPTZ | |

> **Vault Internal Allocation Model:** The `vault` bucket partitions capital into:
> 1. **Emergency Reserve:** Stays locked until an actual emergency strikes and is verified via zero-delay emergency bypass (`is_emergency=true`).
> 2. **Pre-designated Sinking Goals:** Earmarked for specific target purchases (e.g. equipment, camera).
> *Long-Term Savings & Investments:* Held in external bank/investment accounts, swept outward upon Coach reasoning.

### `buckets`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK users | |
| `kind` | bucket_kind | `bank`, `daily`, `freedom`, `vault`, `bills` |
| `name` | TEXT | UI display label |

Unique constraint: `(user_id, kind)`. Balances are calculated dynamically from `ledger_entries`.

### `ledger_entries`

Double-entry ledger: each movement consists of balanced legs sharing a `transfer_id`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `transfer_id` | UUID | Groups balanced transaction legs |
| `user_id` | UUID FK users | Denormalized for rapid querying |
| `bucket_id` | UUID FK buckets | Target bucket |
| `amount` | BIGINT | Signed minor units: `+` credit, `-` debit |
| `currency` | CHAR(3) | Default `'USD'` |
| `state` | ledger_state | `hold`, `posted`, `released`, `pending_paypal` |
| `intent_id` | UUID FK intents | Nullable correlation to spend intent |
| `bill_id` | UUID FK bills | Nullable correlation to scheduled bill |
| `paypal_order_id` | TEXT | Nullable PayPal Orders ID |
| `paypal_capture_id` | TEXT | Nullable PayPal Capture ID |
| `paypal_payout_item_id` | TEXT | Nullable PayPal Payout Item ID |
| `idempotency_key` | TEXT UNIQUE | Enforces single-execution |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `posted_at` | TIMESTAMPTZ | Timestamp when settled |

Indexes:
- `(user_id, created_at DESC)`
- `(bucket_id, state)` for computing available = `sum(posted) - holds`
- `(intent_id)`

### `intents`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK users | |
| `utterance` | TEXT | User natural language *why* |
| `amount` | BIGINT | Minor units from form |
| `currency` | CHAR(3) | Default `'USD'` |
| `merchant_name` | TEXT | Optional merchant label |
| `category` | TEXT | Classified category |
| `necessity` | necessity | `bill`, `daily_living`, `freedom`, `ambiguous` |
| `recommended_bucket` | bucket_kind | Proposed Trinity bucket |
| `source_bucket_id` | UUID | Bucket selected after user confirm |
| `status` | intent_status | Lifecycle status |
| `client_idempotency_key` | TEXT | Client header key |
| `paypal_order_id` | TEXT | PayPal Orders v2 reference |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `agent_runs`

Audit trail recording LLM executions across both Intent and Insights agents.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `kind` | agent_run_kind | `'intent'` or `'insights'` |
| `intent_id` | UUID FK intents | Nullable (set for Intent Agent runs) |
| `thread_id` | UUID FK coach_threads | Nullable (set for Coach runs) |
| `model` | TEXT | LLM model identifier |
| `prompt_version` | TEXT | Prompt template version hash |
| `latency_ms` | INT | Execution duration in ms |
| `raw_response` | JSONB | Unparsed model output |
| `parsed` | JSONB | Extracted tool calls or JSON payload |
| `error` | TEXT | Error text if failed |
| `created_at` | TIMESTAMPTZ | |

### `coach_threads`

Conversational sessions with the Insights Coach.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK users | ON DELETE CASCADE |
| `title` | TEXT | Generated or initial question title |
| `created_at` | TIMESTAMPTZ | Default `now()` |
| `updated_at` | TIMESTAMPTZ | Updated on new messages |

### `coach_messages`

Individual message turns within an Insights Coach session.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `thread_id` | UUID FK coach_threads | ON DELETE CASCADE |
| `role` | coach_message_role | `'user'`, `'assistant'`, `'tool'`, `'system'` |
| `content` | TEXT | Message text |
| `chart_id` | TEXT | Nullable chart reference (e.g. `'chart_pie_week'`) |
| `citations` | JSONB | Nullable data citation metadata (`{ "buckets": [...], "range": "7d" }`) |
| `suggest_intent` | JSONB | Nullable deep link payload (`{ "utterance": "...", "amount": 2000, "category": "..." }`) |
| `created_at` | TIMESTAMPTZ | |

Index: `(thread_id, created_at ASC)`.

### `overrides`

Friction records for Escape Window bypasses.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `intent_id` | UUID FK intents UNIQUE | Linked to the blocked intent |
| `user_id` | UUID FK users | |
| `body` | TEXT | User confession text |
| `status` | override_status | `pending`, `ready`, `approved`, `rejected`, `expired` |
| `ready_at` | TIMESTAMPTZ | Time when cooldown timer finishes |
| `created_at` | TIMESTAMPTZ | |

### `partner_links` & `partner_approvals`

Accountability partner configuration and 2FA approval records.

- `partner_links`: `id (UUID PK)`, `user_id (UUID FK)`, `partner_email (CITEXT)`, `active (BOOL)`.
- `partner_approvals`: `id (UUID PK)`, `override_id (UUID FK)`, `partner_link_id (UUID FK)`, `token_hash (TEXT)`, `status (TEXT)`, `decided_at (TIMESTAMPTZ)`.

### `bills`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK users | |
| `name` | TEXT | e.g. "Rent", "Electric" |
| `amount` | BIGINT | Minor units |
| `currency` | CHAR(3) | Default `'USD'` |
| `priority` | INT | Priority order (1 = highest / rent first) |
| `due_date` | DATE | Calendar due date |
| `payee_email` | TEXT | PayPal sandbox receiver |
| `status` | bill_status | `scheduled`, `paying`, `paid`, `blocked_insufficient`, `canceled` |
| `last_payout_batch_id` | TEXT | Tracking ID |

### `paypal_webhook_events`

Idempotency log for inbound PayPal webhooks.

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | TEXT PK | PayPal `WH-...` identifier |
| `event_type` | TEXT | e.g. `PAYMENT.CAPTURE.COMPLETED` |
| `payload` | JSONB | Full verified raw event payload |
| `processed_at` | TIMESTAMPTZ | |
| `intent_id` | UUID | Nullable correlated intent |

---

## Analytics Read Models (`analytics/`)

Analytics read models power both the mobile HUD visual charts and the Insights Coach tools. These are deterministic SQL queries executed against the PostgreSQL ledger:

```sql
-- Trailing 7-day spending by category (powers chart_pie_week)
SELECT i.category, -SUM(le.amount) AS spent_cents, COUNT(le.id) AS tx_count
FROM ledger_entries le
JOIN intents i ON i.id = le.intent_id
JOIN buckets b ON b.id = le.bucket_id
WHERE le.user_id = $1
  AND le.state = 'posted'
  AND le.amount < 0
  AND le.posted_at >= (NOW() - INTERVAL '7 days')
GROUP BY i.category;
```

Rollover series snapshots, Freedom burn trajectories, and upcoming bill reserves are computed directly through similar performant queries over indexed columns.

---

## Future Schema Extensions (v2.0)

### `batch_payment_items` (The Trinity Batch Dispatcher)
Detailed specification in [features.md](features.md#1-the-trinity-batch-dispatcher).

Tracks queued and staged obligations proposed by the AI Coach for sequential batch dispatch via PayPal Payouts.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | `default_factory=uuid4` |
| `user_id` | UUID FK users | Indexed |
| `title` | TEXT | Obligation name (e.g., 'Electricity Bill') |
| `amount` | NUMERIC / BIGINT | Amount in minor cents or decimal |
| `category` | TEXT | 'Utilities', 'Rent', etc. |
| `status` | TEXT | `pending_approval`, `approved`, `paid`, `vetoed` |
| `paypal_payout_id` | TEXT | Nullable PayPal Payout item/batch reference |
| `created_at` | TIMESTAMPTZ | Timestamp |
| `updated_at` | TIMESTAMPTZ | Timestamp |
