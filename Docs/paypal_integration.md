# PayPal integration (sandbox)

FireWallet’s hackathon story is **intent-driven money movement**, not a mock wallet with a PayPal badge. This file maps every FireWallet action to sandbox APIs.

**Environment:** sandbox only. Base URL `https://api-m.sandbox.paypal.com`. Never mix live credentials.

Related: [trinity_logic.md](trinity_logic.md), [agent_design.md](agent_design.md), [insights.md](insights.md), [security.md](security.md), [hackathon_overview.md](hackathon_overview.md).

## Why this mapping

PayPal sandbox does not give each user four native “buckets.” **PostgreSQL is the bucket ledger** implementing the Trinity architecture. PayPal **executes**:

- Buyer checkout for merchant spend (**Orders v2**)
- Transfers for payday skim, daily top-up, vault lock, bill pay (**Payouts**)
- Login (**Identity** / Login with PayPal)
- Settlement truth (**Webhooks**)

If a demo path never hits `api-m.sandbox.paypal.com`, it is not a FireWallet demo.

> [!IMPORTANT]
> The **Insights Coach** (`agents/insights/`) is **NOT** a PayPal execution path. It is a read-only financial literacy and affordability agent. The Coach has zero access to PayPal tools or credentials and cannot trigger Orders or Payouts. All spend must originate through the **Intent Agent** (`agents/intent/`).

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
| Merchant spend after intent allow | **Orders v2** create → user approve → capture | `intent=CAPTURE` |
| Payday credit (demo) | Payout **to user** or Orders capture **as employer → merchant** then ledger credit | Prefer Payout from merchant to user sandbox email so income is visible in PayPal |
| Vault skim | **Payouts** batch item to vault receiver | Same `sender_batch_id` on retry |
| Daily top-up | Ledger-only **or** Payout if Daily is a distinct PayPal receiver | Draft: **ledger-only for Daily/Freedom/Bank splits**, Payout for **Vault and Bills** so PayPal traffic is real without four accounts per user |
| Bill pay | **Payouts** to bill payee email | Item amount = bill |
| Refund / undo failed demo | Orders refund / Payout not reversible easily | Prefer release HOLD; refund only if capture already settled |
| Ask Insights Coach for advice | *None (Read-only analytics)* | Coach has **no PayPal access**; returns deep link to `/intent` |

### Decision: which movements are on-PayPal vs ledger-only

To stay **deep** without lying:

**Always PayPal:**

1. User-facing **merchant payment** (Orders).
2. **Vault skim** (Payout away from spendable merchant/user).
3. **Bill pay** (Payout to payee).
4. **Payday** (Payout or capture into the user’s PayPal, then ledger).

**Ledger-only (internal buckets):** Bank ↔ Daily ↔ Freedom. These are psychological buckets on one PayPal balance. The firewall is the **intent agent + holds**, not four PayPal wallets.

If we later want visual PayPal activity for Daily, add optional Payouts between sandbox emails. Do not block v1 on that.

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

### Approve

Sandbox buyer logs in on PayPal hosted flow (or JS SDK if we add it). PWA must round-trip `token`/`PayerID` to `POST /intents/{id}/capture`.

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

Register sandbox webhooks to a public URL (`/webhooks/paypal`). Local: ngrok / Cloudflare tunnel. Hosted: Render.

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
