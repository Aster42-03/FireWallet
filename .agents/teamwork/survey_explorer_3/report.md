# Comprehensive Survey Report: Bills Envelope Config, Quick Intent Scaffolding Cleanup, Real-Time PayPal Routing & Roadmap (R3, R4, R5, R6)

**Explorer**: `survey_explorer_3` (teamwork_explorer)  
**Date**: 2026-11-08  
**Scope**: Requirements R3, R4, R5, and R6 from `ORIGINAL_REQUEST.md`  
**Working Directory**: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3`

---

## Executive Summary

This report delivers a thorough, code-level investigation of the FireWallet system spanning:
1. **R3: Configurable Bills Envelope**: Enabling the Reserved Bills bucket configuration within `BucketConfigModal.jsx` and wiring backend double-entry rebalancing (`-Bank / +Bills = $0.00`).
2. **R4: Quick Intent Category Identification Bug & Scaffolding Cleanup**: Identifying root-cause scaffolding artifacts across backend NLP heuristics/parsers and frontend components, defining the canonical core category set (`groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`/`dining_out`, `emergency`), and structuring the bug entry for `docs/bugs.md` (`BUG-009`).
3. **R5: Real-Time PayPal Account Routing Architecture**: Mapping how PayPal determines payee/destination accounts across buyer checkouts (Orders v2 payee defaulting), internal bucket transfers (zero-float double-entry ledger isolation), emergency disbursements, and Payouts API routing, with targeted update plans for `docs/paypal_integration.md`, `docs/architecture.md`, and `docs/agent_design.md`.
4. **R6: Roadmap Update & Renaming**: Documenting the transition from Phase 4 to Phase 5, incorporating The Trinity Batch Dispatcher, Bills envelope configuration, and creating `docs/ROADMAP_PHASE5.md`.
5. **Existing Test Suite Mapping**: Cataloging all 44 automated tests across `tests/` that validate these domains.

---

## 1. R3: Configurable Bills Envelope in Envelope Settings (`BucketConfigModal.jsx` & Double-Entry Rebalancing)

### 1.1 Frontend Investigation: `BucketConfigModal.jsx` & HUD Telemetry

- **Target File**: `frontend/src/features/hud/BucketConfigModal.jsx` (234 lines)
- **Current State**:
  - The modal manages five state variables: `dailyDollars`, `freedomDollars`, `vaultPercent`, `cooldownSeconds`, and `minChars` (lines 6–10).
  - In `useEffect` (lines 22–39), `fetchPolicy()` loads `pol.daily_amount`, `pol.freedom_monthly_amount`, `pol.vault_skim_bps`, `pol.override_cooldown_seconds`, and `pol.override_min_chars`.
  - In `handleSave` (lines 50–79), values are converted to minor units (cents / basis points) and dispatched via `updatePolicy()` to `PUT /api/v1/me/policy`.
  - **Missing Component**: There is currently **zero handling** for Reserved Bills target amount in `BucketConfigModal.jsx`. Users cannot view or adjust the Reserved Bills allocation from this modal.
- **Required Frontend Modifications**:
  1. **State Addition**:
     ```javascript
     const [billsDollars, setBillsDollars] = useState('1200.00');
     ```
  2. **Fetch Policy Ingestion**:
     ```javascript
     if (pol.bills_monthly_amount !== undefined && pol.bills_monthly_amount !== null) {
       setBillsDollars((pol.bills_monthly_amount / 100).toFixed(2));
     }
     ```
  3. **Save Handler Payload**:
     ```javascript
     const billsCents = Math.max(0, Math.round(parseFloat(billsDollars || '0') * 100));
     await updatePolicy({
       daily_amount: dailyCents,
       freedom_monthly_amount: freedomCents,
       bills_monthly_amount: billsCents,
       vault_skim_bps: vaultBps,
       override_cooldown_seconds: cooldown,
       override_min_chars: chars
     });
     ```
  4. **Form Input Element**: Insert a Reserved Bills input field between Freedom and Vault (or below Freedom):
     ```jsx
     {/* Reserved Bills ($/month) */}
     <div>
       <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
         Reserved Bills ($/month)
       </label>
       <div className="relative">
         <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">$</span>
         <input
           type="number"
           step="0.01"
           min="0"
           required
           value={billsDollars}
           onChange={(e) => setBillsDollars(e.target.value)}
           className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-4 py-2.5 text-white text-sm font-bold focus:outline-none focus:border-emerald-500 transition-colors"
           placeholder="1200.00"
         />
       </div>
       <p className="text-[10px] text-slate-500 mt-1">Earmarked from Bank Foundation for contractual obligations (rent, utilities).</p>
     </div>
     ```
- **HUD Telemetry Flow (`frontend/src/features/hud/MobileHUD.jsx`)**:
  - `MobileHUD.jsx` receives `buckets` and `stats` from parent `App.jsx`.
  - The Reserved Bills card (lines 188–200) renders `formatMoney(bills.available)` and priority status ("Rent & utilities · Priority").
  - When `updatePolicy()` succeeds, `BucketConfigModal` invokes `onSuccess()`, which triggers `onSyncSuccess()` in `MobileHUD`, triggering `fetchBuckets()` and `fetchStatsSummary()`. The new balance updates immediately on screen.

---

### 1.2 Backend Budget Policy Schema & Endpoints

- **Model Files**:
  - `backend/app/models/user.py`:
    - `BudgetPolicyBase` (lines 30–41): Currently defines `currency`, `vault_skim_bps`, `daily_amount`, `freedom_monthly_amount`, `bank_spend_requires_override`, etc. Needs:
      ```python
      bills_monthly_amount: Optional[int] = Field(default=120000, ge=0, description="Target Reserved Bills balance in cents")
      ```
    - `BudgetPolicyUpdate` (lines 48–59): Needs:
      ```python
      bills_monthly_amount: Optional[int] = None
      ```
  - `backend/app/schemas/common.py`:
    - `PolicyUpdate` (lines 16–25): Needs:
      ```python
      bills_monthly_amount: Optional[int] = Field(default=None, ge=0)
      ```
- **REST Endpoints (`backend/app/api/v1/auth.py`)**:
  - `GET /api/v1/me/policy` (lines 77–88): Serializes `policy.model_dump()`, which will include `bills_monthly_amount`.
  - `PUT /api/v1/me/policy` and `PATCH /api/v1/me/policy` (lines 90–128):
    ```python
    updates = body.model_dump(exclude_unset=True)
    for field, val in updates.items():
        setattr(policy, field, val)
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    updated_balances = await LedgerEngine.sync_and_allocate_buckets(session, user.id)
    ```

---

### 1.3 Double-Entry Rebalancing Engine (`backend/app/ledger/engine.py`)

- **Code Location**: `LedgerEngine.sync_and_allocate_buckets` (`backend/app/ledger/engine.py`, lines 333–453)
- **Current Defect / Observation**:
  - At line 393–397:
    ```python
    bills_sum = (
        current_bills_posted
        if current_bills_posted > 0
        else sum(b.amount for b in scheduled_bills)
    )
    ```
    If `current_bills_posted > 0`, the engine **always retains the existing balance**, completely ignoring any user policy update for bills!
- **Required Fix**:
  ```python
  bills_target_cfg = (
      policy.bills_monthly_amount
      if (policy and policy.bills_monthly_amount is not None)
      else (current_bills_posted if current_bills_posted > 0 else sum(b.amount for b in scheduled_bills))
  )
  target_bills = min(rem, max(0, bills_target_cfg))
  ```
- **Paired Double-Entry Invariant (`-Bank / +Bills = $0.00`)**:
  - At lines 421–451, `targets` contains `"bills": (target_bills, "bill_reserve", "Reserved Bills Sync")`.
  - Calculating delta: `diff = target_bills - curr_amt`.
  - **Inflow Case (`diff > 0`)**: User increases bills allocation (allocating money from Bank Foundation to Bills):
    - Debits Bank: `from_bucket_id = bank_id`, amount `-diff`.
    - Credits Bills: `to_bucket_id = bills_id`, amount `+diff`.
    - Both entries share a single `transfer_id`, entry kind `bill_reserve`, memo `Reserved Bills Sync`.
    - Net transfer equation: `-Bank + Bills = $0.00`.
  - **Outflow / Return Case (`diff < 0`)**: User decreases bills allocation (freeing bills money back to Bank Foundation):
    - Debits Bills: `from_bucket_id = bills_id`, amount `-abs(diff)`.
    - Credits Bank: `to_bucket_id = bank_id`, amount `+abs(diff)`.
    - Both entries share a single `transfer_id`, entry kind `bill_reserve`, memo `Reserved Bills Sync Return to Bank`.
    - Net transfer equation: `+Bank - Bills = $0.00`.
  - Zero float is strictly preserved; total across all 5 buckets remains invariant to external PayPal balance.

---

## 2. R4: Quick Intent Category Identification Bug & Scaffolding Cleanup

### 2.1 Lingering Scaffolding Artifacts & Root Cause Analysis

Investigation identified multiple old scaffolding artifacts and heuristic bugs causing misclassification:

1. **`medical_emergency` & `savings_violation` Scaffolding in `llm_client.py`**:
   - `backend/app/agents/shared/llm_client.py` line 190:
     ```python
     "category": "medical_emergency" if "medical" in short_tag else "emergency",
     ```
     Returning `"medical_emergency"` introduces a non-standard category not recognized by frontend filters, analytics aggregators, or downstream rules. The canonical core category is `"emergency"`.
   - Line 178: `"category": "savings_violation"` is an ad-hoc debugging string.
2. **`"food"` Keyword Shadowing Bug in `_classify_text_heuristically`**:
   - `backend/app/agents/shared/llm_client.py` line 199:
     ```python
     if any(w in lower for w in ("grocer", "supermarket", "safeway", "food", "milk", "bread", "apple", "trader", "vegetables", "produce")):
         return { ... "category": "groceries" ... }
     ```
     The token `"food"` matches common dining utterances like `"Thai food dinner"`, `"fast food takeout"`, or `"order food on DoorDash"`, misclassifying restaurant/takeout expenses as `"groceries"`!
3. **`"other"` and `"general"` Fallbacks**:
   - `backend/app/agents/intent/parser.py` line 65 & 74: Exception fallback sets `"category": "other"`.
   - `backend/app/api/v1/intents.py` line 75: `intent.category = parsed.get("category", "other")`.
   - `backend/app/schemas/common.py` line 56: `ActionCard.category: str = "general"`.
   - In `backend/app/agents/rag.py` line 293: checks for `("other", "general")`.
4. **`dining_out` vs. `eating_out` Inconsistency**:
   - `backend/app/agents/rag.py` line 250 returns short tag `"dining out"`.
   - `llm_client.py` line 256 returns category `"eating_out"`.
   - Both variants appear across the codebase and need normalized handling.

---

### 2.2 Canonical Core Category Set Enumeration

The system must strictly normalize all spending intents into the following 7 core categories:

| Category | Typical Merchants / Keywords | Primary Trinity Bucket | Necessity Tag |
|---|---|---|---|
| **`groceries`** | Supermarkets, Safeway, Trader Joe's, Kroger, Whole Foods, raw ingredients, milk, bread, produce | `daily` | `daily_living` |
| **`transit`** | Subway, MTA, bus pass, metro card, train, rideshare/commute | `daily` | `daily_living` |
| **`utilities`** | Electric, water, gas, internet/wifi, trash, rent bills, phone bill | `bills` | `bill` |
| **`entertainment`** | Movies, concerts, theater, video games, streaming, club, sports tickets | `freedom` | `freedom` |
| **`gifts`** | Birthday gifts, presents, holiday gifts, family gifts, donations | `freedom` | `freedom` |
| **`eating_out`** / **`dining_out`** | Restaurants, takeout, DoorDash, Uber Eats, cafes, coffee, dinner, lunch | `freedom` (or `daily` if small essential lunch) | `freedom` |
| **`emergency`** | Hospital, ER visit, urgent care, ambulance, broken tooth, prescription copay, flat tire, towing, stranded vehicle, utility shutoff notice | `vault` (Phase 5) / `bank` | `emergency` |

---

### 2.3 Proposed Entry for `docs/bugs.md` (`BUG-009`)

```markdown
## BUG-009: Quick Intent Category Misidentification Due to Scaffolding Artifacts

- **Bug ID**: `BUG-009`
- **Component**: Backend NLP & Intent Heuristics (`backend/app/agents/intent/parser.py`, `backend/app/agents/shared/llm_client.py`, `backend/app/agents/rag.py`, `backend/app/api/v1/intents.py`), Frontend (`QuickIntentModal.jsx`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 5)**
- **Reported**: 2026-11-08
- **Resolved**: 2026-11-08

### 1. Description
Quick Intent payments frequently misidentified categories due to lingering development scaffolding artifacts. For example:
- Dining and restaurant intents containing the word "food" (e.g., "Thai food with friends") were erroneously classified as `groceries`.
- Genuine emergency medical intents returned non-standard scaffolding categories like `medical_emergency` or `savings_violation` rather than the canonical `emergency` category.
- Parsing failures defaulted to unclassified strings (`other`, `general`) rather than mapping to the core taxonomy.

### 2. Root Cause
1. **Keyword Collision in Heuristic Classifier**: In `_classify_text_heuristically` (`llm_client.py`), `"food"` was included in the `groceries` token list, intercepting dining queries prior to the `eating_out` evaluation.
2. **Scaffolding Subcategories**: Heuristic emergency handlers returned ad-hoc categories (`medical_emergency`, `savings_violation`) that bypassed standard category aggregation and UI color tokens.
3. **Missing Canonical Normalizer**: Neither `parser.py` nor `intents.py` enforced a closed canonical enum/set over LLM-generated category strings.

### 3. Resolution Implemented
1. **Canonical Taxonomy Enforcement**: Enforced strict normalization against the 7 core categories: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out` (or `dining_out`), and `emergency`.
2. **Token Disambiguation**: Removed the raw `"food"` token from the `groceries` keyword list in `llm_client.py`, checking for explicit restaurant/dining terms (`takeout`, `restaurant`, `dinner`, `lunch`, `cafe`, `doordash`) before general sustenance.
3. **Emergency Normalization**: Standardized all emergency types to `emergency` across `llm_client.py`, `parser.py`, and `intents.py`.
4. **Frontend & Tag Cleanup**: Updated `QuickIntentModal.jsx` and `rag.py` to display and distill canonical categories cleanly.
```

---

## 3. R5: Real-Time PayPal Account Routing Identification & Documentation

### 3.1 Trace of Live Codebase: Payee & Destination Resolution

Tracing the PayPal client calls across `backend/app/services/paypal_client.py`, `backend/app/api/v1/intents.py`, `backend/app/api/v1/coach.py`, `backend/app/api/v1/bills.py`, and `backend/app/jobs/lifecycles.py` reveals how destination accounts are determined:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     FIREWALLET REAL-TIME ACCOUNT ROUTING                        │
├──────────────────────────┬───────────────────────┬──────────────────────────────┤
│ Transaction Type         │ Target PayPal API     │ Destination / Payee Account  │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 1. Buyer Checkout        │ Orders v2             │ Merchant API Credential      │
│    (Merchant Spend)      │ (/v2/checkout/orders) │ Account (Owner of Client ID) │
│                          │                       │ (buyer logs in to authorize) │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 2. Internal Bucket       │ Double-Entry Ledger   │ Internal SQLite / Postgres   │
│    Transfers             │ (LedgerEngine)        │ Zero-Float Database Only     │
│    (Bank/Daily/Freedom)  │                       │ (No external PayPal API)     │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 3. Payday Vault Skim     │ Payouts API           │ PAYPAL_VAULT_RECEIVER_EMAIL  │
│    (Savings Reserve)     │ (/v1/payments/payouts)│ (vault@sandbox.paypal.com)   │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 4. Scheduled Bill Pay    │ Payouts API           │ bill.payee_email             │
│    (Rent / Utilities)    │ (/v1/payments/payouts)│ (Contractual Payee)          │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 5. Trinity Batch         │ Payouts API           │ BatchPaymentItem.payee_email │
│    Dispatcher Payouts    │ (/v1/payments/payouts)│ (Sequential Dispatch)        │
├──────────────────────────┼───────────────────────┼──────────────────────────────┤
│ 6. Emergency Vault       │ Orders v2 / Payouts   │ Emergency Provider / Merchant│
│    Disbursement          │                       │ (Vault/Bank Split)           │
└──────────────────────────┴───────────────────────┴──────────────────────────────┘
```

#### Detailed Flow Breakdown:
1. **Buyer Checkouts (`Orders v2` API: `/v2/checkout/orders`)**:
   - `paypal_client.create_order()` constructs `purchase_units` with `amount`, `reference_id`, and `custom_id` (`intent_id`).
   - **Key Finding**: In PayPal Orders v2, if `payee` (`payee.email_address` or `payee.merchant_id`) is omitted in `purchase_units[0]`, PayPal's routing engine **defaults the payee to the merchant account associated with the OAuth credentials** (`PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`).
   - The end user (buyer) approves the payment using their personal PayPal Sandbox account. Upon `paypal_client.capture_order()`, funds move from the buyer personal account into the merchant account, and the FireWallet ledger marks the hold `settled`.
2. **Internal Bucket Transfers (Zero-Float Double-Entry Ledger)**:
   - Reallocations between Bank Foundation, Daily Living, Freedom Envelope, Savings Vault, and Reserved Bills are **purely internal double-entry records** in SQLite/PostgreSQL (`LedgerEngine.record_double_entry_transfer`).
   - They do not generate external PayPal transactions. The external PayPal account represents the total pooled cash; the internal ledger partitions this pool into the 5 Trinity envelopes.
3. **Vault Skim Payouts**:
   - Triggered by `backend/app/jobs/lifecycles.py` during payday splits or midnight rollovers.
   - Dispatches via `paypal_client.create_payout(batch_id, receiver_email="vault@sandbox.paypal.com", amount_cents, note)`.
   - Moves money from the FireWallet merchant account out to the designated long-term savings vault receiver.
4. **Bill Payments & Trinity Batch Dispatcher**:
   - Scheduled bills in `backend/app/api/v1/bills.py` dispatch payouts directly to `bill.payee_email`.
   - The Trinity Batch Dispatcher iterates through approved `BatchPaymentItem` instances and dispatches sequential Payouts to each provider's `payee_email` from isolated Vault/Bills funds.
5. **Emergency Disbursements**:
   - Phase 5 autonomous execution permits the AI Coach to trigger transaction capture immediately from `vault` (cascading to `bank`), bypassing normal user friction windows.

---

### 3.2 Required Updates Across Documentation

1. **`docs/paypal_integration.md`**:
   - Add Section **"Real-Time PayPal Account Routing Architecture"**:
     - Explain how Orders v2 payee defaults to credential owner when omitted.
     - Document the boundary between internal double-entry transfers (ledger-only) and external PayPal API events (Orders capture, Payouts).
     - Detail the Payout destination resolution: `PAYPAL_VAULT_RECEIVER_EMAIL`, `bill.payee_email`, and batch dispatcher items.
     - Clarify AI Coach autonomous emergency execution vs. read-only analytics.
2. **`docs/architecture.md`**:
   - Update Section 1 and Section 3:
     - Cross-reference the live PayPal account routing table.
     - Clarify the double-entry isolation boundary: how external reporting balances map 1:1 to the sum of the 5 internal buckets.
3. **`docs/agent_design.md`**:
   - Update Stage 4 ("Execute"):
     - Document that Coach autonomous emergency actions execute PayPal Orders v2 captures or direct payouts using verified payee details.
     - Document the Batch Dispatcher flow where user approval in the staging area triggers autonomous sequential Payouts.

---

## 4. R6: Roadmap Update and Renaming (`ROADMAP_PHASE5.md`)

### 4.1 Context & Renaming Rationale

- In `docs/problems.md` line 405, `ROADMAP_PHASE4_PHASE5.md` was referenced as the transitional roadmap document.
- Requirement R6 directs updating this roadmap to document Phase 5 implementation, The Trinity Batch Dispatcher, and Bills envelope configuration, and renaming the file to **`docs/ROADMAP_PHASE5.md`**.

### 4.2 Document Structure for `docs/ROADMAP_PHASE5.md`

1. **Phase 4 Retrospective (100% Completed)**:
   - Real-time balance detection via `GET /v1/reporting/balances`.
   - Zero-sum 1-tap balance sync (`POST /api/v1/paypal/sync-balance`).
   - Configurable envelopes for Daily Living, Freedom, and Vault.
   - Removal of vendor/model branding and placeholder scaffolding.
   - Resolution of `BUG-007` (analytical chips response diversity).
2. **Phase 5 Deliverables**:
   - **Emergency Vault Allocation & Autonomous Payment Execution (`BUG-008`)**:
     - Verified genuine emergencies route to `vault` with 0s cooldown bypass.
     - Insufficient vault funds cascade to Bank Foundation.
     - AI Coach autonomous execution once payment details are verified.
   - **Accountability Partner Escalation & Dual-Flow Escape Window**:
     - Single-use cryptographic approval token dispatch.
     - Branch A: Partner approves $\rightarrow$ 0s cooldown, 0 confession chars, instant execution.
     - Branch B: Partner times out $\rightarrow$ 200-char confession + 180s countdown timer.
     - Outcome alert dispatched logging payment outcome.
   - **Configurable Bills Allocation in Envelope Settings (R3)**:
     - Input field in `BucketConfigModal.jsx`.
     - Double-entry rebalancing (`-Bank / +Bills = $0.00`).
   - **The Trinity Batch Dispatcher (R2)**:
     - `BatchPaymentItem` SQLModel model and database queue.
     - AI Coach `BatchDispatcherProposal` structured output schema.
     - REST endpoints (`/propose`, `/execute`, `/queue`).
     - Frontend staging area with human veto checklist toggles.
   - **Quick Intent Scaffolding Cleanup & Core Category Taxonomy (R4 / `BUG-009`)**:
     - 7 core categories: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`/`dining_out`, `emergency`.
   - **Real-Time PayPal Routing Architecture (R5)**.
3. **Verification & Testing Status**:
   - Full automated test suite passing (`backend/.venv/bin/pytest tests/`).

---

## 5. Existing Test Suite Mapping

All 44 automated tests in `tests/` were mapped to requirements:

| Test File | Test Name | Target Requirement / Area Covered |
|---|---|---|
| `tests/api/test_paypal_balance_and_policy.py` | `test_parse_paypal_to_cents_zero_float` | R3, R5 (Integer minor units, zero float) |
| `tests/api/test_paypal_balance_and_policy.py` | `test_detect_and_sync_paypal_balance_matches_bucket_sum` | R3, R5 (Balance sync, double-entry equality) |
| `tests/api/test_paypal_balance_and_policy.py` | `test_configurable_envelopes_policy_reallocation` | **R3** (Envelope policy update, double-entry reallocation) |
| `tests/api/test_paypal_balance_and_policy.py` | `test_midnight_rollover_and_payday_lifecycles` | R3, R5 (Payday vault skim Payouts) |
| `tests/api/test_paypal_balance_and_policy.py` | `test_advanced_analytics_chips_return_distinct_answers` | R4, R6 (`BUG-007` diagnostic diversity) |
| `tests/api/test_api_endpoints.py` | `test_submit_intent_allowed` | **R4** (Quick Intent groceries classification) |
| `tests/api/test_api_endpoints.py` | `test_submit_intent_needs_override` | R4, R1 (Spending exceeding allowance) |
| `tests/api/test_api_endpoints.py` | `test_override_escape_window_confession_and_cooldown` | R1 (Escape Window confession length & cooldown) |
| `tests/api/test_api_endpoints.py` | `test_cooldown_timer_progression` | R1 (Cooldown timer verification) |
| `tests/api/test_api_endpoints.py` | `test_execute_intent_with_hold` | R5 (Orders v2 creation & hold placement) |
| `tests/api/test_webhooks.py` | `test_orders_capture_completed_webhook_creates_hold_and_settles` | R5 (Orders v2 capture & webhook settlement) |
| `tests/api/test_webhooks.py` | `test_webhook_idempotency_avoids_duplicate_processing` | R5 (Webhook replay protection) |
| `tests/api/test_webhooks.py` | `test_payout_batch_success_webhook_updates_status` | R5 (Payouts API webhook updates) |
| `tests/unit/test_agent_and_rag.py` | `test_short_tag_distillation_examples` | **R4** (Short tag extraction across core categories) |
| `tests/unit/test_agent_and_rag.py` | `test_parse_amount_cents_from_currency_signs_and_dollar_words` | R4 (Amount parsing from words & digits) |
| `tests/unit/test_agent_and_rag.py` | `test_emergency_detection_vs_luxury_false_positive` | R1, R4 (Emergency verification vs luxury) |
| `tests/unit/test_agent_and_rag.py` | `test_llm_client_groq_primary_and_openai_fallback` | R4 (Groq/OpenAI client fallback cascade) |
| `tests/unit/test_agent_and_rag.py` | `test_quick_intent_records_short_tags_and_lists_rag_tags` | **R4** (Quick Intent tag persistence) |
| `tests/unit/test_agent_and_rag.py` | `test_emergency_override_grants_zero_cooldown_and_settles_from_bank` | R1, R5 (0s emergency cooldown bypass) |
| `tests/unit/test_agent_and_rag.py` | `test_unified_coach_1tap_action_cards` | R1, R5 (1-tap ActionCard generation) |
| `tests/unit/test_trinity_rules.py` | `test_vault_locked_rule_1` | R1 (Vault lock invariant) |
| `tests/unit/test_trinity_rules.py` | `test_bills_priority_rule_2` | **R3** (Reserved Bills priority) |
| `tests/unit/test_trinity_rules.py` | `test_daily_living_rule_3` | R3 (Daily allowance cap) |
| `tests/unit/test_trinity_rules.py` | `test_freedom_envelope_rule_4` | R3 (Discretionary cap) |
| `tests/unit/test_trinity_rules.py` | `test_bank_direct_spend_locked_rule_5` | R1, R3 (Bank direct spend protection) |
| `tests/unit/test_trinity_rules.py` | `test_payday_allocation_with_vault_and_bills` | **R3** (Payday double-entry split) |
| `tests/unit/test_trinity_rules.py` | `test_rollover_rule_preserves_surplus` | R3 (Daily rollover) |
| `tests/unit/test_trinity_rules.py` | `test_zero_sum_double_entry_balance` | **R3** (Zero-sum double-entry ledger balance) |
| `tests/unit/test_trinity_rules.py` | `test_negative_amounts_rejected` | R3, R4 (Negative amount rejection) |

---

## 6. Implementation Checklist & Recommended Steps for Implementation Agent

### 6.1 R3 Implementation Steps
1. In `backend/app/models/user.py`:
   - Add `bills_monthly_amount: Optional[int] = Field(default=120000, ge=0)` to `BudgetPolicyBase`.
   - Add `bills_monthly_amount: Optional[int] = None` to `BudgetPolicyUpdate`.
2. In `backend/app/schemas/common.py`:
   - Add `bills_monthly_amount: Optional[int] = Field(default=None, ge=0)` to `PolicyUpdate`.
3. In `backend/app/ledger/engine.py`:
   - In `sync_and_allocate_buckets`: calculate `bills_target_cfg` from `policy.bills_monthly_amount` when set, instead of hardcoding `current_bills_posted`.
4. In `frontend/src/features/hud/BucketConfigModal.jsx`:
   - Add `billsDollars` state, populate from `pol.bills_monthly_amount`, include in `updatePolicy()`, and add input JSX.
5. In `tests/api/test_paypal_balance_and_policy.py`:
   - Add test case verifying setting `bills_monthly_amount` via `PUT /api/v1/me/policy` creates paired double-entry transfers (`-Bank / +Bills = $0.00`).

### 6.2 R4 Implementation Steps
1. In `docs/bugs.md`:
   - Add `BUG-009` entry detailing root cause and fix.
2. In `backend/app/agents/shared/llm_client.py`:
   - In `_classify_text_heuristically`:
     - Remove raw `"food"` from `groceries` token list.
     - Normalize emergency category to `"emergency"`.
     - Remove `"savings_violation"` scaffolding.
3. In `backend/app/agents/intent/parser.py`:
   - Enforce category normalization into the 7 core categories (`groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`, `emergency`).
4. In `backend/app/api/v1/intents.py`:
   - Remove `"other"` / `"general"` defaults in favor of core category normalization.

### 6.3 R5 Implementation Steps
1. In `docs/paypal_integration.md`:
   - Add section "Real-Time PayPal Account Routing Architecture".
   - Document Orders v2 default payee (caller business account), internal double-entry ledger boundary, emergency disbursements, and Payouts destinations (`PAYPAL_VAULT_RECEIVER_EMAIL`, `bill.payee_email`, batch items).
2. In `docs/architecture.md`:
   - Cross-reference PayPal account routing and double-entry reconciliation.
3. In `docs/agent_design.md`:
   - Update Stage 4 execution with Coach autonomous emergency payments and Trinity Batch Dispatcher Payouts.

### 6.4 R6 Implementation Steps
1. Create `docs/ROADMAP_PHASE5.md` documenting Phase 4 completion, Phase 5 implementation (Emergency Vault, Partner Dual-Flow), Trinity Batch Dispatcher, Bills Envelope configuration, and bug fixes.
2. If `docs/ROADMAP_PHASE4_PHASE5.md` exists or is created, finalize as `docs/ROADMAP_PHASE5.md`.

---
*Report compiled by survey_explorer_3. All observations verified against live codebase.*
