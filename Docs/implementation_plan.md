# FireWallet: Comprehensive Implementation Roadmap & Next Phases Plan

**Source of Truth:** Post-Phase 2 Milestone  
**Current Milestone Completed:** Phase 1 (Core Environment, Trinity Accounting Invariants, 100% Green Tests) & Phase 2 (Bank-Kept Double-Entry Ledger, Enterprise AG Grid Workbench v32, Alembic Migration Infrastructure).  
**Target Submission / Production Ready:** Complete Hackathon & Production Deployment Requirements.

---

## 1. Executive Summary & Current Milestone Status

FireWallet operates on the **Trinity Architecture**: money is segregated deterministically into 5 strict buckets (**Bank Foundation**, **Daily Living**, **Freedom Envelope**, **Locked Savings Vault**, and **Reserved Bills**), guarded by an **AI Financial Firewall** and analyzed by an **Advanced Reasoning Coach**.

| Phase | Milestone Description | Status | Key Deliverables Completed |
|---|---|---|---|
| **Phase 1** | **Core Engine & Accounting Foundation** | **DONE** | Zero-float minor unit math, 5 Trinity buckets, rule evaluation engine, UV packaging, 23 unit/API tests passing with 0 warnings. |
| **Phase 2** | **Double-Entry Ledger & AG Grid Workbench** | **DONE** | Bank-kept double-entry ledger (`transfer_id` pairing, $\sum \text{legs} = 0$), running balances, AG Grid v32 dark quartz grid, Alembic SQLite/PostgreSQL migrations. |
| **Phase 3** | **AI Coach Deep Agent Architecture** | **PLANNED** | Multi-turn memory, thread persistence, fix `BUG-001` (message doubling), tool calling (affordability simulations, runway projections, policy optimizer). |
| **Phase 4** | **PayPal Sandbox & Automated Lifecycles** | **PLANNED** | PayPal Orders (v2), Captures, Payouts (Vault skim), Webhook listener, Morning Rollover cron, Payday worker. |
| **Phase 5** | **Accountability Partner & Escape Window** | **PLANNED** | Cryptographic partner approval link, 200-char confession friction, 180s escape cooldown countdown timer, alert dispatch. |
| **Phase 6** | **Production Cloud & Devpost Packaging** | **PLANNED** | Render deployment verification (`render.yaml`), Postman collection test run, APIMatic OpenAPI sync, sub-3-minute video checklist. |

---

## 2. Phase 3: AI Coach Deep Agent Architecture & Memory

### Objective
Elevate the Financial Coach from single-turn analytical prompt completions into an autonomous, stateful reasoning agent capable of multi-turn conversational interrogation, deep ledger tool calling, and predictive financial simulations.

### Key Tasks & Work Breakdown

#### 3.1. Bug Resolution (`BUG-001: Chat & Response Doubling`)
- **Root Cause**: React Strict Mode re-mounts trigger `useEffect` on `initialQuery` twice; un-cleared parent state in `App.jsx` re-fires queries on render; concurrent async calls dispatch identical twin requests before state locks.
- **Tasks**:
  1. Add `hasFiredRef = useRef(false)` in `CoachDrawer.jsx` to guard against duplicate initial queries.
  2. Implement `onClearInitialQuery={() => setCoachInitialQuery('')}` callback in `App.jsx`.
  3. Introduce ref-based request locking (`isSendingRef.current`) and `AbortController` request cancellation.
  4. Implement client-generated message IDs (`client_message_id`) for server-side idempotency.

#### 3.2. Multi-Turn Thread & Message Persistence
- **Backend**:
  - Connect `backend/app/models/coach.py` (`CoachThread`, `CoachMessage`) to the `/api/v1/coach/messages` endpoint.
  - Persist conversation history so the user can switch between topics (e.g., "Grocery Audit", "Rent Planning", "Holiday Freedom Budget").
  - Provide `/api/v1/coach/threads` CRUD endpoints and thread deletion.
- **Frontend**:
  - Add thread selector / history sidebar inside `CoachDrawer`.
  - Persist active thread in local storage for seamless page reloads.

#### 3.3. Coach Agent Tool Calling (Function Calling)
- Implement structured tool-use routines in `backend/app/agents/insights/coach.py`:
  1. `simulate_affordability(amount, item_name, category)`: Projects what happens to Daily burn rate and Freedom envelope if a proposed purchase is completed.
  2. `project_vault_runway(months)`: Computes automated skim trajectory based on gross income and policy `vault_skim_bps`.
  3. `recommend_policy_tune()`: Analyzes 30-day velocity drift and recommends adjustments to `daily_amount` or `vault_skim_bps`.
  4. `explain_bank_double_entry_flow()`: Interrogates paired legs for specific `transfer_id` values and explains why each allocation occurred.

#### 3.4. Citation & Chart Deep Linking
- Add interactive citation pills to coach messages:
  - Clicking a cited `transfer_id` auto-highlights the corresponding paired rows in AG Grid.
  - Clicking a cited bucket navigates to that bucket's filtered transaction journal.

---

## 3. Phase 4: PayPal Sandbox & Automated Money Movement

### Objective
Integrate real PayPal Sandbox APIs to move money safely under the supervision of the AI Firewall, ensuring every PayPal order and payout maps directly to a two-phase ledger hold and capture.

### Key Tasks & Work Breakdown

#### 4.1. Two-Phase Spend Flow (Orders v2 API)
- **Workflow**:
  1. When intent status is `allowed`, frontend renders the PayPal Checkout Button.
  2. User taps PayPal -> backend calls `POST /v2/checkout/orders` with intent `CAPTURE` and minor unit amount.
  3. Ledger engine places a `hold` on the designated bucket (`Daily` or `Freedom`).
  4. User approves sandbox payment in PayPal modal.
  5. Backend calls `POST /v2/checkout/orders/{id}/capture`.
  6. Ledger converts `hold` into settled `posted` debit.

#### 4.2. Automated Vault Skim (Payouts API)
- **Workflow**:
  1. When a Payday inflow occurs, policy calculates `skim = floor(gross * vault_skim_bps / 10000)`.
  2. Ledger places double-entry transfer `Bank → Vault` (`-amount` Bank, `+amount` Vault).
  3. Background worker invokes PayPal Payouts API (`POST /v1/payments/payouts`) sending skim funds to `PAYPAL_VAULT_RECEIVER_EMAIL`.
  4. Record `paypal_payout_item_id` in `ledger_entries`.

#### 4.3. PayPal Webhook Listener & Idempotency
- **Endpoint**: `POST /api/v1/webhooks/paypal`
- **Events Handled**:
  - `PAYMENT.CAPTURE.COMPLETED`: Reconcile external card / PayPal capture with ledger hold.
  - `PAYMENT.PAYOUTSBATCH.SUCCESS`: Confirm automated vault skim or bill payout delivery.
  - `CHECKOUT.ORDER.APPROVED`: Trigger immediate backend capture if client drops offline.
- **Security**:
  - Verify PayPal Webhook signature headers (`PAYPAL-AUTH-ALGO`, `PAYPAL-TRANSMISSION-SIG`, `PAYPAL-CERT-URL`).
  - Store event IDs in `paypal_webhook_events` with unique constraint to prevent duplicate processing.

#### 4.4. Automated Background Workers & Schedulers
- **Morning Daily Top-Up Worker (`backend/app/jobs/daily_topup.py`)**:
  - Runs daily at user's local midnight.
  - If `Daily.available < policy.daily_amount`, executes balanced double-entry transfer from `Bank → Daily`.
  - Preserves positive rollover if `Daily.available >= policy.daily_amount`.
- **Bill Auto-Payment Worker (`backend/app/jobs/bill_manager.py`)**:
  - Scans `bills` table for upcoming due dates within 48 hours.
  - Dispatches payout to landlord / utility payee from `Bills` bucket.

---

## 4. Phase 5: Accountability Partner & Escape Window Hardening

### Objective
Turn the "Escape Window" from a simple text form into a high-friction psychological deterrence circuit featuring partner alerts, cryptographic approval tokens, and strict cool-off countdowns.

### Key Tasks & Work Breakdown

#### 5.1. Escape Window High-Friction UI
- **Components**: `frontend/src/features/override/EscapeWindowModal.jsx`
- **Friction Elements**:
  1. **Mandatory 200-Character Confession**: Real-time character counter requiring the user to explicitly justify dipping into Bank/Rent funds.
  2. **180-Second Cooldown Timer**: Visual progress ring preventing purchase completion until the timer expires.
  3. **Visual Impact Preview**: Live AG Grid simulation showing rent shortfall if funds are raided.

#### 5.2. Partner Verification & Multi-Sig Approval
- **Endpoints**:
  - `POST /api/v1/overrides/{id}/request-partner-approval`: Generates HMAC-SHA256 one-time token and emails accountability partner.
  - `GET /api/v1/overrides/partner-approve?token=...`: Web page allowing the partner to approve or veto the impulsive spend.
- **Data Model**:
  - `PartnerApproval` table linked to `Override`, tracking status (`pending`, `approved`, `vetoed`) and token hash.

---

## 5. Phase 6: Production Cloud Deployment & Hackathon Packaging

### Objective
Package FireWallet for public hackathon judging, seamless zero-config evaluation, and live high-availability deployment on Render.

### Key Tasks & Work Breakdown

#### 5.1. Render Cloud Deployment
- Verify `render.yaml` blueprint with:
  1. **PostgreSQL Database** (`firewallet-db`): PostgreSQL 16 on Render.
  2. **FastAPI Web Service** (`firewallet-api`): With release command `alembic upgrade head && python -m app.jobs.seed`.
  3. **React Static Site** (`firewallet-web`): Built with Vite (`npm run build`), served via Render CDN.

#### 5.2. Developer Tooling & Verification Assets
- **Postman Collection (`postman_collection.json`)**:
  - Pre-configure environment variables for Base URL, Demo Token, and PayPal Sandbox keys.
  - Automate test assertions covering all endpoints (`/health`, `/buckets`, `/intents`, `/analytics/deep-ledger`, `/coach/messages`).
- **APIMatic OpenAPI Integration**:
  - Ensure `backend/app/main.py` generates 100% compliant OpenAPI 3.1 JSON (`/openapi.json`).
  - Generate typed SDK artifacts for judge validation.

#### 5.3. Hackathon Demo Video & Devpost Submission
- Follow the 3-minute demo script in `Docs/demo_script.md`:
  - 0:00 - 0:30: The Problem (impulse spending, rent stress).
  - 0:30 - 1:15: Mobile HUD & Intent Gateway (allowed groceries vs blocked late-night sushi).
  - 1:15 - 2:00: Escape Window & 180s Cooldown friction.
  - 2:00 - 2:40: Desktop AG Grid Workbench (double-entry flows, zero-sum verification, deep coach interrogation).
  - 2:40 - 3:00: Real PayPal Sandbox settlement & Render cloud proof.
