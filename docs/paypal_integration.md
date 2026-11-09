# PayPal integration (sandbox)

FireWallet’s hackathon story is **intent-driven money movement**, not a mock wallet with a PayPal badge. This file maps every FireWallet action to sandbox APIs.

**Environment:** sandbox only. Base URL `https://api-m.sandbox.paypal.com`. Never mix live credentials.

Related: **[problems.md](problems.md) (Problem 1 — Real PayPal End-to-End Gate)**, [TRINITY_RULES.md](TRINITY_RULES.md), [agent_design.md](agent_design.md), [insights.md](insights.md), [security.md](security.md), [hackathon_overview.md](hackathon_overview.md).

## Why this mapping

PayPal sandbox does not give each user five native “buckets.” **SQLite / PostgreSQL is the double-entry bucket ledger** implementing the Trinity voluntary-commitment architecture. PayPal **executes**:

- Live account balance detection (**Reporting Balances API**: `GET /v1/reporting/balances`, tagged with `source: "live" | "simulated"`)
- Buyer checkout for merchant spend (**Orders v2**)
- Transfers for payday Vault skim and bill pay (**Payouts**)
- Buyer session (**Seeded Sandbox Buyer** for frictionless judge testing; optional Identity OAuth)
- Settlement truth (**Webhooks** at `POST /api/v1/webhooks/paypal`)

If a demo path never hits `api-m.sandbox.paypal.com`, it is not a FireWallet demo.

> [!IMPORTANT]
> The **Insights Coach** (`agents/insights/`) functions primarily as a financial literacy and affordability advisor. By default, the Coach does not initiate unconstrained payments. In Phase 5, two strictly governed execution paths are supported: (1) **Autonomous Emergency Payment Execution (`BUG-008`)**, where verified genuine emergencies empower the Coach to execute transactions autonomously once payment details are verified, and (2) **The Trinity Batch Dispatcher**, where the Coach generates structured batch payment proposals for user review and sequential backend payout dispatch.

## Accounts (sandbox dashboard)

Create in [developer.paypal.com](https://developer.paypal.com/) → Apps & Credentials (Sandbox) + Sandbox Accounts:

| Role | Type | Used for |
| --- | --- | --- |
| **App** | REST app | Client ID / secret, webhook ID |
| **Merchant (FireWallet)** | Business | Receives captures; sends payouts; app owner |
| **User (buyer)** | Personal | Login + approve Orders |
| **Vault receiver** | Business or Personal | Destination for skimmed savings |
| **Bill payee** | Business | Rent / utilities stand-in |
| **Freedom merchant** | Business | Demo “game skin / takeout” capture |

Store emails in env/seed, not in git.

Suggested env:

```
PAYPAL_ENV=sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_VAULT_RECEIVER_EMAIL=
PAYPAL_BILL_PAYEE_EMAIL=
```

User-linked emails live in `paypal_accounts` after Identity.

## Auth

### App token (client credentials)

`POST /v1/oauth2/token` with Basic(client_id:secret), `grant_type=client_credentials`.

Cache `access_token` until `expires_in` minus 60s. Single asyncio lock on refresh.

Scopes needed in the app (as granted by the dashboard): payments, payouts, openid/identity, webhooks.

### Login with PayPal (user)

User connects a sandbox personal account. Store `payer_id`, email, refresh material per `paypal_accounts`. This is how judges see **PayPal is identity**, not only a server-side secret.

v1 can also seed a linked sandbox buyer if Identity setup slips; document it as a demo fallback, not the intended path.

## FireWallet action → PayPal API

| FireWallet action | PayPal | Notes |
| --- | --- | --- |
| User signs in / links wallet | Identity / Connect | `paypal_accounts` row |
| Merchant spend after intent allow | **Orders v2** create → user approve → capture | `intent=CAPTURE`, defaults payee to developer merchant account |
| Payday credit (demo) | Payout **to user** or Orders capture **as employer → merchant** then ledger credit | Prefer Payout from merchant to user sandbox email so income is visible in PayPal |
| Vault skim | **Payouts** batch item to vault receiver | Dispatches to `PAYPAL_VAULT_RECEIVER_EMAIL` (`vault@sandbox.paypal.com`) |
| Daily top-up | Ledger-only double-entry transfer | Zero external float (`-Bank / +Daily = $0.00`), purely on-ledger database record |
| Bill pay | **Payouts** to bill payee email | Item amount = bill, receiver = `bill.payee_email` |
| Trinity Batch Dispatcher | **Payouts** sequential items | Suggested by Coach, approved in Staging Area, dispatched to `item.payee_email` |
| AI Coach Emergency Execution (BUG-008) | **Orders v2** capture / Payouts | Coach executes verified emergency transactions autonomously from Vault/Bank (0s bypass) |
| Refund / undo failed demo | Orders refund / Payout not reversible easily | Prefer release HOLD; refund only if capture already settled |
| Ask Insights Coach for advice | *None (Read-only analytics)* | Coach provides financial literacy; returns deep link to `/intent` |

---

## Real-Time PayPal Account Routing Architecture

FireWallet bridges deterministic double-entry accounting with real-time PayPal money movement. The system strictly distinguishes between **external PayPal execution events** (which interact directly with `api-m.sandbox.paypal.com`) and **internal envelope reallocations** (which are strictly zero-float database ledger records).

### Real-Time Account Routing Map

| Movement Type | Target PayPal API | Payee / Destination Resolution | Internal Ledger State & Invariants |
| :--- | :--- | :--- | :--- |
| **1. Buyer Checkout** (Daily, Freedom, Merchant Spend) | **Orders v2** (`POST /v2/checkout/orders` & `/capture`) | **Defaults to Merchant Business Account** (`PAYPAL_CLIENT_ID` owner) when `payee` is omitted in `purchase_units[0]` | Placed on `hold` in source bucket; transitions to `posted` (settled debit) on capture or webhook receipt |
| **2. Internal Envelope Transfers** (Bank ↔ Daily ↔ Freedom ↔ Vault ↔ Bills) | **Double-Entry Ledger Only** (`LedgerEngine.record_double_entry_transfer`) | **None** (Internal database records; zero external PayPal API invocation) | Zero external float; atomic database transactions creating balanced legs (`-from_bucket + to_bucket = $0.00`) |
| **3. Payday Savings Vault Skim** | **Payouts API** (`POST /v1/payments/payouts`) | Explicitly routed to `receiver_email = PAYPAL_VAULT_RECEIVER_EMAIL` (default: `vault@sandbox.paypal.com`) | Debit `bank`, credit `vault` on ledger; dispatches external transfer to isolated savings account |
| **4. Contractual Bill Payments** | **Payouts API** (`POST /v1/payments/payouts`) | Explicitly routed to `receiver_email = bill.payee_email` (target vendor/landlord) | Debits `bills` bucket; records `payout_batch_id` on `bills` table |
| **5. Trinity Batch Dispatcher** | **Payouts API** (`POST /v1/payments/payouts`) | Explicitly routed to each item's `payee_email` (`items[0].receiver = item.payee_email`) | Iterates approved queue items; debits isolated `bills` or `vault` reserves; requires live sandbox credentials |
| **6. Emergency Disbursements (BUG-008)** | **Orders v2 / Payouts API** | Direct to emergency service provider or recipient email (`receiver_email`); AI Coach autonomous execution | 0s cooldown bypass; draws from `vault`, cascading remainder from `bank` if vault insufficient |

### Detailed Mechanics & Routing Invariants

#### 1. Orders v2 Buyer Checkouts (Payee Resolution Default)
When creating merchant checkout orders via `paypal_client.create_order()`, FireWallet constructs the `purchase_units` payload specifying `amount`, `reference_id`, `custom_id` (`intent_id`), and `description`:
- **Omitted Payee Default:** In PayPal Orders v2 specifications, if `payee` (`payee.email_address` or `payee.merchant_id`) is omitted within `purchase_units[0]`, PayPal's routing engine **automatically defaults the payee to the merchant account associated with the OAuth credentials** (`PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`).
- **Authorization & Capture Flow:** The end user (buyer) approves the payment using their personal PayPal Sandbox account. Upon invocation of `paypal_client.capture_order()` (or webhook receipt of `PAYMENT.CAPTURE.COMPLETED`), funds move from the personal sandbox buyer into the FireWallet developer merchant account. The ledger converts the bucket `hold` to a settled `posted` debit.

#### 2. Internal Bucket Transfers (Zero External Float, Atomic Database Transactions)
Reallocations between envelopes—such as moving funds between Bank Foundation, Daily Living, Freedom Envelope, Savings Vault, and Reserved Bills—are **purely on-ledger database records**:
- **Mechanism:** Executed via `LedgerEngine.record_double_entry_transfer(session, user_id, from_bucket_id, to_bucket_id, amount_minor, entry_kind, memo)`.
- **Zero External API Overhead:** These transfers do **not** invoke external PayPal APIs. The external PayPal account holds the pooled cash; the internal ledger deterministically partitions this pool into the 5 Trinity envelopes.
- **Atomic Balance Invariant:** Every transfer records paired debit (`-amount`) and credit (`+amount`) entries sharing a single unique `transfer_id`. Total system balance across all five buckets remains constant (`-Source + Destination = $0.00`), guaranteeing zero synthetic money creation and zero external float.

#### 3. Emergency Disbursements & AI Coach Autonomous Execution (`BUG-008`)
Emergency payouts represent a critical exception to standard friction gates:
- **0s Cooldown Bypass:** Verified genuine emergencies (`is_genuine_emergency() = True`) bypass the standard 180-second countdown and 200-character reflective confession gates.
- **Vault Draw & Cascade:** Funds draw primarily from the locked Savings `vault`. If available vault balance is less than the emergency cost, the remainder automatically cascades from `bank` via a balanced double-entry transfer (`emergency_vault_draw`).
- **AI Coach Autonomous Execution:** Once payment details (recipient, amount, necessity) are verified, the AI Coach is empowered to trigger transaction execution autonomously via `POST /api/v1/coach/action` (`auto_capture_demo=True` or PayPal checkout generation), settling the emergency without delay.
- **Disbursement Routing:** Emergency funds are routed either via Orders v2 capture to the provider merchant account or via Payouts API directly to the recipient's verified PayPal email address.

#### 4. Payouts API & The Trinity Batch Dispatcher
The PayPal Payouts REST API (`POST /v1/payments/payouts`) is utilized for outbound disbursements where FireWallet acts as the sender:
- **Receiver Routing:** `paypal_client.create_payout(batch_id, receiver_email, amount_cents, note)` explicitly sets `items[0].receiver = receiver_email` and `items[0].recipient_type = "EMAIL"`.
  - **Vault Skims:** Routes to `PAYPAL_VAULT_RECEIVER_EMAIL` (defaulting to `vault@sandbox.paypal.com`), physically walling off long-term savings into a dedicated savings sandbox account.
  - **Bill Payments:** Routes directly to contractual obligations via `bill.payee_email`.
  - **The Trinity Batch Dispatcher:** Iterates through human-approved `BatchPaymentItem` records, sequentially executing payouts to each obligation's `payee_email` while enforcing blast radius containment (drawing exclusively from `bills` or `vault`, strictly protecting `bank`).
- **Live Sandbox Guard:** Batch payout execution strictly requires live PayPal Sandbox credentials (`access_token != "mock_sandbox_access_token"`). If offline or credentials are not configured, the endpoint fails cleanly with HTTP 503 (`Service Unavailable: Live PayPal Sandbox credentials required`).

---

### Decision: which movements are on-PayPal vs ledger-only

To stay **deep** without lying:

**Always PayPal:**

1. User-facing **merchant payment** (Orders v2; payee defaults to developer merchant account).
2. **Vault skim** (Payouts to `PAYPAL_VAULT_RECEIVER_EMAIL`).
3. **Bill pay** (Payouts to `bill.payee_email`).
4. **Trinity Batch Dispatcher** (Sequential Payouts to `item.payee_email` from Vault/Bills).
5. **Emergency disbursements** (Orders capture or Payouts to emergency recipient).
6. **Payday** (Payout or capture into the user’s PayPal, then ledger).

**Ledger-only (internal buckets):** Bank ↔ Daily ↔ Freedom ↔ Bills ↔ Vault rebalancing. These are psychological envelopes partitioning one PayPal balance. The firewall is the **intent agent + holds**, not five separate PayPal business wallets.


## Intent-driven Orders (merchant spend)

Never create an Order until:

- `intents.status` is `allowed` or `override_approved`
- ledger HOLD succeeded
- amount/currency match the intent

### Create

`POST /v2/checkout/orders`

- `intent`: `CAPTURE`
- `purchase_units[0].amount`: from intent (major units string, e.g. `"12.50"`) — convert from minor units in `paypal/`
- `purchase_units[0].custom_id` or `reference_id`: `intent_id` (UUID)
- `purchase_units[0].description`: truncated agent category + user intent (PayPal-safe length)
- `payment_source` / application context: return URLs to PWA `/pay/return` and `/pay/cancel`

Store `paypal_order_id` on the intent.

### Approve & Capture Loop (Option 1: Two-Phase Interactive Buyer Approval)

In PayPal Orders v2 specifications, orders are created in the `CREATED` state. The Capture endpoint **cannot** be called until the buyer authenticates and approves the transaction, which transitions the Order to `APPROVED`. FireWallet enforces a two-phase interactive approval loop across Quick Intent, Escape Window, Coach Drawer, and return redirect routing:

#### 1. Phase 1: Order Creation & Approval URL Dispatch
- Endpoint: `POST /api/v1/intents/{id}/execute` with `IntentExecuteRequest(return_url, cancel_url)`
- Backend creates PayPal Order with `application_context`:
  - `landing_page: "LOGIN"` (forces Sandbox Personal Buyer credentials prompt)
  - `user_action: "PAY_NOW"` (displays "Pay Now" / "Agree & Continue" button on PayPal)
- PayPal returns links array containing `rel: "approve"` (`https://www.sandbox.paypal.com/checkoutnow?token=...`).
- Response payload:
  ```json
  {
    "status": "awaiting_approval",
    "paypal_order_id": "8XY1234567890",
    "approval_url": "https://www.sandbox.paypal.com/checkoutnow?token=8XY1234567890",
    "order_status": "CREATED"
  }
  ```

#### 2. Interactive Buyer Approval on PayPal Sandbox
- Frontend launches or redirects to `approval_url`.
- User signs in with Sandbox Personal Buyer email/password and confirms transaction.
- Order transitions on PayPal from `CREATED` → `APPROVED`.

#### 3. Real-Time Status Inquiries & Redirect Return
- **Polling Endpoint**: `GET /api/v1/intents/{id}/order-status` queries live PayPal Orders v2 status (`CREATED`, `APPROVED`, `COMPLETED`), returning `IntentOrderStatusResponse`.
- **Redirect Return Listener**: Upon buyer approval, PayPal redirects back to `return_url` (`/?paypal_return=true&intent_id={id}&token={order_id}&PayerID={payer_id}`). `App.jsx` intercepts the URL params, dispatches capture, refreshes ledger balances, and cleans browser history.
- **In-App Manual Trigger**: If checkout opened in a popup/tab, modals provide an **"I've Approved on PayPal — Complete & Settle"** action button.

#### 4. Phase 2: Capture Verification & Ledger Settlement
- Endpoint: `POST /api/v1/intents/{id}/capture`
- Backend invokes `POST /v2/checkout/orders/{order_id}/capture`.
- **Strict Database Settlement Invariant**:
  - If PayPal returns `ORDER_NOT_APPROVED` (HTTP 422), backend rejects with HTTP 422: `"PayPal reports buyer approval is not finished yet. Payer must approve the Order on PayPal before capture can be executed."` The database ledger hold remains untouched in `evaluating` status.
  - Settle hold and set `intent.status = "settled"` **strictly and exclusively** when PayPal returns `status in ("COMPLETED", "PENDING")`.
  - Capture ID and Payer details are recorded on the Intent. Webhook `PAYMENT.CAPTURE.COMPLETED` serves as idempotent confirmation.

### Capture

`POST /v2/checkout/orders/{id}/capture`

On API success, status `executing` until webhook. Do not mark `settled` on capture HTTP alone if we also listen for webhooks — **prefer webhook as settlement**, capture HTTP as `capture_requested` + optimistic UI.

### Idempotency

PayPal-Request-Id header = `intent:{uuid}:capture`. Retries must reuse it.

## Payouts (vault, bills, payday)

`POST /v1/payments/payouts`

```
sender_batch_header.sender_batch_id = stable key
  e.g. vault:{user_id}:{income_event_id}
       bill:{bill_id}:{due_date}
       payday:{user_id}:{local_date}
items[].receiver = sandbox email
items[].amount.value / currency
items[].note = human string
items[].sender_item_id = ledger_entry id or bill id
```

Poll `GET /v1/payments/payouts/{batch_id}` if webhook is delayed. Webhook still wins for final posting.

Unclaimed payouts: surface in UI; do not credit destination bucket as available.

## Webhooks

Register sandbox webhooks to a public URL (`/api/v1/webhooks/paypal`). Local: ngrok / Cloudflare tunnel. Hosted: Render.

Verify using PayPal signature verification (transmission id, time, cert, actual signature) against `PAYPAL_WEBHOOK_ID`. Reject invalid with 400. **ACK 200** for valid duplicates.

| Event (indicative) | FireWallet handler |
| --- | --- |
| `CHECKOUT.ORDER.APPROVED` | Optional; wait for capture |
| `PAYMENT.CAPTURE.COMPLETED` | Settle HOLD; store capture id |
| `PAYMENT.CAPTURE.DENIED` / `REFUNDED` | Release or reverse ledger |
| `PAYMENT.PAYOUTSBATCH.SUCCESS` | Settle payout lines |
| `PAYMENT.PAYOUTS-ITEM.FAILED` / `UNCLAIMED` | Mark pending/failed; do not spend |

Insert `paypal_webhook_events.event_id` first (unique). If conflict, return 200.

Raw payload stored for replay (SOP).

## Failure and retry

| Failure | Behavior |
| --- | --- |
| Orders create 4xx | Release HOLD; intent `failed`; no retry without new intent |
| Capture 5xx / timeout | Leave HOLD; retry capture with same PayPal-Request-Id |
| Payout 5xx | Retry same `sender_batch_id` |
| Webhook out of order | Handlers must be state-based (`if already settled: noop`) |
| Token 401 | Refresh client credentials once, retry |

## What we will not fake for judges

Do **not**:

- Show a green “Paid with PayPal” toast after only a SQL update
- Use production API by accident
- Hardcode capture IDs
- Skip buyer approval in the **recorded demo** (sandbox login is the proof)

Acceptable demo shortcuts (label in SOP):

- Seeded sandbox passwords
- Pre-linked `paypal_accounts`
- Tunnel URL in `.env`
- One merchant SKU for all Freedom purchases

## Dev-time tools (not runtime)

- [PayPal AI Toolkit](https://github.com/paypal/AI-Toolkit) and [MCP server](https://github.com/paypal/paypal-mcp-server) — help write integration code
- Official Postman collection: `base_url=https://api-m.sandbox.paypal.com`
- Sandbox MCP SSE: `https://mcp.sandbox.paypal.com/sse`

The **in-app** agent must not be “the PayPal MCP chatting with the user.” It must be FireWallet’s intent gateway that **then** calls our `paypal/` client.

## Agentic commerce (prize framing)

PayPal wants AI **behind the wheel** of money movement. FireWallet’s sequence is the submission talking point:

1. Human states **why**.
2. Agent classifies and **refuses or routes**.
3. Only then does PayPal create an Order or Payout.
4. Webhook closes the books.

That is the integration, not a chatbot beside a checkout button.

### Agentic Flow: The Trinity Batch Dispatcher (Phase 5)
Documented in [features.md](features.md#1-the-trinity-batch-dispatcher) and [ROADMAP_PHASE5.md](ROADMAP_PHASE5.md):
- Extends PayPal Payouts into an autonomous sequential batch dispatcher suggested by the AI Coach.
- Leverages `POST /v1/payments/payouts` with deterministic `sender_batch_id` values generated per approved item.
- Preserves Human Veto Power: user toggles approve/veto on staged items before execution.
- Restricts payouts exclusively to verified `items[0].receiver = item.payee_email` destinations with funds drawn strictly from Vault/Bills reserve.
- Enforces Live PayPal Sandbox credential validation (fails cleanly with HTTP 503 if credentials are unconfigured or offline).


## Implementation notes for FastAPI

- `httpx.AsyncClient` to sandbox
- Timeouts explicit
- Never log access tokens or secrets
- Convert minor units → PayPal decimal strings with banker’s rounding banned; use integer cents and format `{dollars}.{cc}`
- Currency `USD` until policy says otherwise

## Open questions

- JS SDK vs server-only redirect for Orders approval
- Vault as PayPal Vault **payment tokens** (card vault) vs our savings Vault — **different concepts**. Do not confuse names in UI: our Vault is a **bucket**, not PayPal Vault API, unless we later store a payment method.
- Hyperwallet / Braintree: out of v1 unless a demo needs them
