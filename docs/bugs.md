# FireWallet Bug Tracker

This document tracks known issues, edge cases, root-cause analyses, and architectural bugs across development phases.

Related: **[problems.md](problems.md) (Core Build Gate & Action Plan)**, [TRINITY_RULES.md](TRINITY_RULES.md), [decisions.md](decisions.md).

> [!IMPORTANT]
> **Bug Resolution Verification Gate ([problems.md](problems.md)):**
> Every bug fix must include regression tests verified against the criteria in **[problems.md](problems.md)** (e.g., Problem 4 for diagnostic chip response diversity `BUG-007`, and Problem 5 for deterministic emergency rules `BUG-008`).

---

## BUG-001: AI Coach Chat Messages and Responses Doubling

- **Bug ID**: `BUG-001`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/App.jsx`), AI Coach Integration
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
When sending a query to the AI Financial Coach in the UI (via either 1-tap analytical chips or direct text submission), the user's message appeared twice in the chat stream, and the coach returned two identical responses in parallel.

### 2. Root Cause
1. **`useEffect` Double Invocation in React 18 `<StrictMode>`**:
   `useEffect(() => { if (initialQuery) handleSend(initialQuery); }, [initialQuery])` fired twice on mount while `coachInitialQuery` in `App.jsx` remained populated.
2. **Asynchronous React State Race Condition**:
   `handleSend()` relied solely on React `loading` state rather than a synchronous `useRef` lock, allowing back-to-back calls to dispatch parallel `POST /api/v1/coach/messages` requests.

### 3. Resolution Implemented
1. Added synchronous `isSendingRef` lock and `lastProcessedInitialRef` guard inside `frontend/src/features/coach/CoachDrawer.jsx`.
2. Added `onClearInitialQuery` callback in `frontend/src/App.jsx` so `coachInitialQuery` is cleared immediately upon consumption.
3. Attached an `AbortController` (`signal`) to `sendCoachMessage` in `frontend/src/shared/api.js` and `CoachDrawer.jsx` to cancel stale in-flight requests cleanly on unmount.

---

## BUG-002: Quick Intent Bucket Not Found (Dual-Database Divergence)

- **Bug ID**: `BUG-002`
- **Component**: Backend (`app/core/config.py`, `app/api/v1/auth.py`, `app/api/v1/intents.py`)
- **Severity**: High
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
In the Quick Intent tab, users received an error stating `"Bucket 'freedom' not found"`, blocking all intent evaluations and prevent payments from passing through.

### 2. Root Cause
1. **SQLite Database Path Divergence**: When starting the FastAPI server from `backend/` working directory, SQLite relative path `sqlite+aiosqlite:///./firewallet.db` evaluated to `backend/firewallet.db`. Because previous Alembic migrations and seed scripts were executed from the root directory, root `firewallet.db` had seeded buckets while `backend/firewallet.db` was unseeded or had a user without buckets.
2. **Missing Auto-Provisioning Guard**: `get_current_user` assumed pre-existing buckets and threw a 404 instead of auto-provisioning the 5 core Trinity buckets (`bank`, `daily`, `freedom`, `vault`, `bills`).

### 3. Resolution Implemented
1. Added `resolve_database_url()` in `backend/app/core/config.py` that resolves relative SQLite database paths strictly against the canonical repository root path (`BASE_DIR.parent / "firewallet.db"`).
2. Added auto-provisioning in `backend/app/api/v1/auth.py` inside `get_current_user()`: if a user lacks the 5 Trinity buckets, they are automatically initialized and committed atomically.
3. Synced root `firewallet.db` to `backend/firewallet.db`.

---

## BUG-003: Coach Predetermined Robotic Response Missing Human Warmth

- **Bug ID**: `BUG-003`
- **Component**: Backend LLM Orchestration (`backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
When sending conversational greetings like `"hello"`, `"hey coach"`, or general inquiries, the coach responded with a cold, canned robotic boilerplate (`"Trinity Coach Evaluation: You have requested..."`) lacking personal financial context, warmth, and natural conversation.

### 2. Root Cause
The fallback cascade in `call_unified_coach` used a rigid template assuming every prompt was a strict spend inquiry, ignoring greetings, conversational inquiries, and dynamic ledger context (user name, daily balance, rollover streak).

### 3. Resolution Implemented
1. Replaced static template with dynamic context-aware conversational generation in `backend/app/agents/shared/llm_client.py`.
2. Incorporated user's name (`Aster`), daily balance, freedom balance, and rollover streak directly into conversational greetings and check-ins.
3. Errors now log full tracebacks to `logger.error` while communicating clear, warm, natural language explanations to the user without robotic jargon.

---

## BUG-004: Missing 1-Tap Action Cards for Words & Dollar Inquiries

- **Bug ID**: `BUG-004`
- **Component**: Backend RAG & Coach Engine (`backend/app/agents/rag.py`, `backend/app/agents/insights/coach.py`, `backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
The 1-tap action button was missing when users asked about common spending activities without typing an explicit `$` symbol (e.g. `"fifteen dollars"`, `"twenty bucks"`, `"50 cents"`, or `"Can I buy a coffee?"`).

### 2. Root Cause
1. Regex only recognized `\$\d+` syntax, ignoring word numbers (`twenty dollars`, `fifty cents`) and currency terms (`bucks`, `usd`).
2. Spend prompts without explicit amounts were assigned `action_type: "none"` without inferring common standard defaults.

### 3. Resolution Implemented
1. Built `parse_amount_cents_from_text()` in `backend/app/agents/rag.py` supporting `$XX`, numbers + words (`15 dollars`, `50 cents`), and full word numbers (`twenty dollars`, `fifteen bucks`, `fifty cents`).
2. Added default amount inference in `call_unified_coach` for common spend queries (`coffee`: $5.00, `takeout`: $18.00, `groceries`: $35.00, `vault sweep`: $25.00), automatically presenting ready-to-pay 1-tap action cards.

---

## BUG-005: Raw Markdown Unrendered in Coach Chat Bubbles

- **Bug ID**: `BUG-005`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/features/coach/MarkdownRenderer.jsx`)
- **Severity**: Low
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
Coach messages containing markdown syntax (`**bold**`, `*italics*`, `### headers`, `- bullets`, `` `code` ``) rendered as raw text characters instead of formatted rich typography.

### 2. Root Cause
`CoachDrawer.jsx` was rendering `msg.content` directly inside a text `<div>`.

### 3. Resolution Implemented
1. Created lightweight zero-dependency `MarkdownRenderer.jsx` parsing bold, italics, inline code, headers, bullet lists, and numbered lists.
2. Integrated `MarkdownRenderer` into `CoachDrawer.jsx`.

---

## BUG-006: Quick Chat Buttons Failing to Output Messages & Missing Insight Actions

- **Bug ID**: `BUG-006`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/features/hud/MobileHUD.jsx`, `frontend/src/App.jsx`), Backend Insights (`backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
1. When clicking the quick chat buttons in Mobile HUD (e.g. "Can I afford the $20 movie ticket?"), the Coach drawer opened but no user message or coach reply was outputted to the chat stream.
2. The quick chat buttons were hardcoded to sample spending questions rather than informative financial insights (such as explaining rollover streak, why Bank is locked, vault sweep mechanics, and velocity diagnostics).

### 2. Root Cause
1. **StrictMode Mount-Abort Race Condition**:
   - In `CoachDrawer.jsx`, `useEffect` had an unmount cleanup function: `return () => { abortControllerRef.current?.abort(); }`.
   - In React 18 development mode (`<StrictMode>`), opening the drawer mounted the component, dispatched `handleSend`, and simultaneously called `onClearInitialQuery?.()` which set `coachInitialQuery = ""` in `App.jsx`.
   - React StrictMode immediately ran cleanup (invoking `abort()`, dropping the in-flight request) and remounted the component.
   - On remount, `initialQuery` was already `""` (cleared by the first mount), leaving `messages` reset to the initial welcome state with no message ever sent or received.
2. **Re-render Dependency Churn**: `handleSend` had `input` in its dependency array, recreating the function on every keystroke and causing effect dependency churn.
3. **Missing First-Class Insight Handlers**: In `llm_client.py`, questions regarding rollover streak, Bank locking, or Escape Window friction lacked structured mock and fallback handlers.

### 3. Resolution Implemented
1. **Structured Query ID Tracking**:
   - In `App.jsx`, `handleOpenCoachWithQuery` passes a unique query object: `{ id: timestamp, text: query }`.
   - In `CoachDrawer.jsx`, `lastProcessedIdRef` tracks dispatched query IDs, executing `handleSend` exactly once per unique button tap even under StrictMode.
   - Decoupled `input` from `handleSend` via `inputRef` so keystrokes do not recreate callback references.
   - Scoped `abortController` cleanup strictly to drawer close events (`!isOpen`), preventing initial mount unmounts from killing in-flight queries.
2. **Dedicated Insight Quick Chips in HUD and Coach**:
   - Replaced sample spending buttons in `MobileHUD.jsx` with actual financial insights:
     - `✦ Explain rollover streak`
     - `🔒 Why is Bank locked?`
     - `⚡ How Vault sweep works`
     - `📊 Diagnose spend velocity`
     - `🔥 Escape Window friction`
   - Added an interactive Quick Insight Suggestion Chips bar inside `CoachDrawer.jsx` directly above the chat input form for one-tap insight exploration.
3. **Structured Backend Insight Handlers**:
   - Added explicit handlers in `backend/app/agents/shared/llm_client.py` and `rag.py` delivering rich Markdown explanations for rollover streaks, Rule 4 locked Bank Foundation, and Escape Window friction.
   - Verified via unit and API integration tests in `tests/unit/test_agent_and_rag.py`.

---

## BUG-007: Advanced Analytics Diagnostic Chips Returning Identical Canned Responses

- **Bug ID**: `BUG-007`
- **Component**: Backend Coach & LLM Fallback (`backend/app/agents/shared/llm_client.py`, `backend/app/agents/insights/coach.py`, `backend/app/agents/rag.py`), Frontend (`frontend/src/features/analytics/DeepLedgerGrid.jsx`, `frontend/src/features/coach/CoachDrawer.jsx`)
- **Severity**: Medium / Moderate
- **Status**: **Resolved (Fixed in Phase 4)**
- **Reported**: 2026-11-08
- **Resolved**: 2026-11-08

### 1. Description
In the **Advanced Analytics** (`DeepLedgerGrid.jsx`) section, clicking any of the 1-tap diagnostic chips (*🏦 Explain Bank Double-Entry Flows*, *⚡ Diagnose Velocity & Runway*, *🔍 Detect Spending Anomalies*, or *🎯 Freedom Envelope vs Rent Protection*) caused the Coach sidebar to output the exact same generic response (`"### 📊 Deep Ledger & Flow Diagnostics..."`) regardless of which chip was clicked. Additionally, clicking chips when the sidebar was already open or closed could fail to clear `coachInitialQuery` cleanly.

### 2. Root Cause
1. **Catch-All Filter Context Short-Circuit in `llm_client.py`**:
   - Whenever any chip in `DeepLedgerGrid.jsx` was clicked, `handleAnalyzeContext()` attached `filterContext` to the request.
   - `coach.py` injected `"Active Filter & Deep Audit Context:"` into `last_msg`.
   - In `backend/app/agents/shared/llm_client.py`, the very first `if` branch checked `if any(w in uq_lower for w in ("grid", "ledger", "filter", "velocity", "runway", "double-entry", "audit")) or "active filter" in last_msg:` and immediately returned a single static response before evaluating the specific topic of the prompt.
2. **Uninvoked `onClearInitialQuery` Callback**:
   - `CoachDrawer.jsx` received `onClearInitialQuery` as a prop from `App.jsx` but never invoked it after consuming `initialQuery`, leaving stale query state in parent memory.

### 3. Resolution Implemented
1. **Topic-Specific Diagnostic Handlers**:
   - Refactored `backend/app/agents/shared/llm_client.py` and `backend/app/agents/rag.py` to evaluate the specific analytical question first (*Bank double-entry flows*, *Daily velocity & runway*, *Spending anomalies*, *Freedom trajectory vs Rent protection*), generating distinct, telemetry-driven Markdown analyses for each chip.
2. **Clean Query Lifecycle in `CoachDrawer.jsx`**:
   - Invoked `onClearInitialQuery?.()` immediately after consuming `initialQuery` and added a dedicated `🏦 Bank double-entry flows` chip inside the Coach drawer.

---

## BUG-008: Emergency Intent Drawing from Bank/Daily Instead of Vault

- **Bug ID**: `BUG-008`
- **Component**: Backend (`app/api/v1/intents.py`, `app/api/v1/overrides.py`, `app/ledger/engine.py`, `app/agents/insights/coach.py`, `app/agents/intent/parser.py`), Frontend (`QuickIntentModal.jsx`, `CoachDrawer.jsx`)
- **Severity**: High
- **Status**: **Open / Investigating**
- **Reported**: 2026-11-08
- **Target Fix Milestone**: Emergency & Retrospective Trust Protocol / Bucket Architecture Alignment

### 1. Description
When a user submits an emergency spending intent (e.g., medical emergency, ER visit, emergency car repair, critical utility shutoff) in Quick Intent or through the AI Coach 1-tap action button, the system does not draw funds from the `vault` (or Vault Emergency Sub-Bucket). Instead, `can_spend` and `execute_intent` draw funds from `daily` or `bank`, or block the intent because `can_spend` hard-forbids any spend from `vault`.

### 2. Root Cause
1. **Strict Vault Lock in `can_spend`**:
   `LedgerEngine.can_spend` explicitly denies any spend where `source_kind == "vault"` ("Vault is locked long-term savings. Direct spend is strictly forbidden.").
2. **Fallback to Bank in `execute_intent` and `coach.py`**:
   - In `app/api/v1/intents.py`, `execute_intent` checks if `intent.status == "override_approved"` and falls back to `bank` when the original bucket lacks funds: `hold_bucket_id = balances["bank"]["bucket_id"]`.
   - In `coach.py`, when `det_emerg` is true, the handler sets `chosen_kind = "daily" if daily_avail >= amount_cents else "bank"`.
3. **Emergency Override Specification vs Code Mismatch**:
   `TRINITY_RULES.md` states:
   > "If the Intent Parser detects a high-urgency emergency classification, standard cooldown timers and friction locks are bypassed instantly to prevent transaction failure. Funds are drawn from the dedicated **Vault Emergency Sub-Bucket**."
   However, the implementation never configured `vault` as an allowable emergency source or designated how emergency funds are drawn from Vault reserves.

### 3. Resolution Plan (Aligned with ADR-020 & problems.md Problem 5)
1. **Vault Definition Clarification:**
   - The Vault is not an untouchable external retirement vehicle; it houses the **Emergency Reserve + Pre-designated Sinking Goals** (e.g. equipment, camera). True long-term investments are held in external accounts and swept outward upon Coach reasoning.
2. **Dual-Signal Deterministic Verification:**
   - The LLM outputs `is_emergency` and `category` as a proposal. Only deterministic Python code in `LedgerEngine.can_spend` approves emergency status, requiring BOTH a verified emergency category (`healthcare`, `transit`, `utilities`) AND the emergency flag. Non-emergency categories (e.g. `eating_out`) face the full 200-char confession + 180s cooldown timer.
3. **Emergency Policy & Abuse Tests ([problems.md](problems.md) Problem 5):**
   - Implement `emergency_cap_minor` and `emergency_max_per_7d` limits in `budget_policies`.
   - Add the 4 required abuse regression tests:
     - `test_vault_spend_without_emergency_denied`
     - `test_emergency_under_cap_allowed`
     - `test_second_emergency_within_7d_gets_full_friction`
     - `test_fake_emergency_in_non_emergency_category_gets_full_friction`

---

## BUG-009: Quick Intent Category Classification Collision from Lingering Scaffolding Artifacts

- **Bug ID**: `BUG-009`
- **Component**: Backend NLP & Intent Heuristics (`backend/app/agents/intent/parser.py`, `backend/app/agents/shared/llm_client.py`, `backend/app/agents/rag.py`, `backend/app/api/v1/intents.py`), Frontend (`QuickIntentModal.jsx`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 5 / M1)**
- **Reported**: 2026-11-08
- **Resolved**: 2026-11-08

### 1. Description / Symptom
Quick Intent spending utterances frequently misidentified categories due to lingering development scaffolding artifacts:
- Dining and restaurant intents containing the keyword "food" (e.g., "Thai food with friends", "fast food order") were erroneously classified as `groceries` before the `eating_out` evaluation branch could be reached.
- Emergency intents returned non-standard scaffolding categories such as `medical_emergency` or `savings_violation` rather than the canonical core `emergency` category.
- Parsing failures defaulted to unclassified scaffolding strings (`other`, `general`) rather than mapping to the core taxonomy.

### 2. Root Cause
1. **Keyword Collision in Heuristic Classifier**: In `_classify_text_heuristically` (`backend/app/agents/shared/llm_client.py`), `"food"` was included in the `groceries` token list, intercepting dining queries prior to the `eating_out` evaluation.
2. **Scaffolding Subcategories**: Heuristic emergency and vault-access handlers returned ad-hoc categories (`medical_emergency`, `savings_violation`) that bypassed standard category aggregation, budgeting rules, and UI color tokens.
3. **Missing Canonical Normalizer**: Neither `parser.py` nor `intents.py` enforced a closed canonical enum/set over LLM-generated or heuristic category strings, and exception fallbacks produced `other`.

### 3. Resolution Implemented (Fix)
1. **Canonical Core Category Set**: Defined and enforced strict normalization against the 7 core canonical categories: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out` (or `dining_out`), and `emergency`.
2. **Token Disambiguation in Heuristics**: Removed the raw `"food"` keyword from the `groceries` token list in `llm_client.py`, adding store tokens (`whole foods`, `kroger`, `aldi`) to prevent restaurant/dining intents from misclassifying as groceries while ensuring actual grocery shopping classifies accurately.
3. **Emergency Normalization**: Standardized all emergency types (`medical_emergency`, `savings_violation`) to `emergency` in `llm_client.py` and `parser.py`.
4. **Scaffolding Fallback Cleanup**: Replaced dummy `"category": "other"` fallback in `parser.py` with `normalize_category()` and deterministic heuristic classification on parse failures, ensuring all returned intents belong to the 7 core categories.

### 4. Verification
- Verified deterministic heuristic classification across all 7 core categories (`groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`, `emergency`).
- Verified that "Thai food dinner" classifies as `eating_out` and "urgent hospital ER copay" classifies as `emergency`.
- Ran full automated test suite `pytest tests/` passing 44 existing tests with zero regressions.

---

## BUG-010: AI Coach Not Staging Payments From Persistent Memory & Quick Intent Lacks Batch Staging Option

- **Bug ID**: `BUG-010`
- **Component**: Backend AI Coach (`backend/app/agents/insights/coach.py`, `backend/app/api/v1/bills.py`), Frontend Quick Intent (`frontend/src/features/intent/QuickIntentModal.jsx`, `frontend/src/features/bills/BatchDispatcherModal.jsx`, `frontend/src/App.jsx`)
- **Severity**: High
- **Status**: **Resolved (Fixed in Phase 5 / Dual Ingestion Staging)**
- **Reported**: 2026-11-08
- **Resolved**: 2026-11-08

### 1. Description / Symptom
1. **AI Agent Fails to Stage Payments from Memory**: When users mentioned recurring bills or upcoming obligations to the AI Coach (e.g., "Please stage my electric bill of $75 to electric@state.gov"), the Coach recorded short-tags and memories, but `POST /bills/batch-dispatcher/propose` solely read from the static `bills` table (`where status = 'scheduled'`). It never queried or synthesized obligations stored in persistent memory (`intents`, `coach_messages`, or RAG tags) to propose and stage `batch_payment_items`.
2. **Quick Intent Lacked "Add to Batch Staging" Action**: When a user submitted an intent via the Quick Intent modal (`QuickIntentModal.jsx`), the only available execution paths were immediate 1-by-1 PayPal checkout (`Pay with PayPal Sandbox`) or Escape Window override. Users could not stage multiple payments into the batch queue to execute together in one go via the Batch Dispatcher.

### 2. Root Cause
1. **Decoupled Bill Staging Source**: In `backend/app/api/v1/bills.py`, `propose_batch` only selected from `Bill` records. The AI Coach's conversation loop (`handle_coach_query` in `coach.py`) never created `BatchPaymentItem` rows when the user asked to stage/queue an expense, and `propose_batch` ignored non-bill items.
2. **Missing UI Action & API Endpoint**: `QuickIntentModal.jsx` lacked a button and state to stage into `batch-dispatcher`, and the backend did not expose `POST /api/v1/bills/batch-dispatcher/stage-intent`.

### 3. Resolution Implemented (Fix)
1. **API Endpoint (`POST /api/v1/bills/batch-dispatcher/stage-intent`)**:
   - Implemented endpoint validating minor unit amount ($>0$), recipient email, and source bucket restricted strictly to isolated `bills` or `vault` reserves.
   - Inserts `BatchPaymentItem(status="pending_approval")` linking to the optional `intent_id`.
   - Updated `execute_batch` to mark linked `Intent`s as `settled` upon execution.
2. **AI Coach Memory Staging**:
   - In `backend/app/agents/insights/coach.py`, added detection of staging requests. When detected, the Coach deterministically creates a `BatchPaymentItem` with `status="pending_approval"`, isolated `source_bucket="bills"`, and returns `action_type="stage_batch"` with an ActionCard to view in the Batch Dispatcher.
   - In `backend/app/api/v1/bills.py` (`propose_batch`), enhanced query to sweep unstaged recurring bill/utility `Intent`s recorded in persistent memory and included all active `pending_approval` batch payment items in the proposal.
3. **Frontend Direct Quick Intent Staging**:
   - In `frontend/src/shared/api.js`, added `stageIntentToBatch()`.
   - In `QuickIntentModal.jsx`, added an **"Add to Batch Queue"** action button alongside "Pay Now" on the validated verdict screen, complete with Payee email confirmation prompt and a one-click transition to the Batch Dispatcher modal.
   - In `BatchDispatcherModal.jsx`, added source badges (`Quick Intent`, `Coach Memory`) distinguishing staged origins from scheduled bills.
   - In `App.jsx`, elevated `isBatchDispatcherOpen` state to ensure unified modal access across Mobile HUD, desktop grid, and quick intent modal.

### 4. Verification
- Added automated E2E tests in `tests/api/test_batch_dispatcher_e2e.py`:
  - `test_stage_intent_to_batch_dispatcher`: Tests `POST /stage-intent` and appearance in proposed batch queue.
  - `test_propose_batch_includes_unstaged_memory_intents`: Tests automatic proposal of unstaged recurring bill memory intents.
  - `test_ai_coach_stages_payment_from_chat`: Tests that chatting "Please stage my electric bill of $75 to electric@state.gov" creates a `BatchPaymentItem` and returns `action_type="stage_batch"`.
- Full automated test suite passes: `pytest tests/` (130 passed, 1 skipped in 13.93s).

---

## BUG-011: PayPal Order Capture Attempted Before Buyer Approval (ORDER_NOT_APPROVED)

- **Bug ID**: `BUG-011`
- **Component**: Backend PayPal Service (`backend/app/services/paypal_client.py`), Intents API (`backend/app/api/v1/intents.py`, `backend/app/api/v1/coach.py`), Frontend Checkout Modals (`QuickIntentModal.jsx`, `EscapeWindowModal.jsx`, `CoachDrawer.jsx`, `App.jsx`, `shared/api.js`)
- **Severity**: Critical
- **Status**: **Resolved (Fixed in PayPal Interactive Approval Loop)**
- **Reported**: 2026-11-09
- **Resolved**: 2026-11-09

### 1. Description / Symptom
When paying for an intent via PayPal Sandbox, attempting to capture funds resulted in an HTTP 422 error from PayPal's Orders v2 API with issue `ORDER_NOT_APPROVED` ("Payer has not yet approved the Order for payment").
Previously, in offline/development modes, `paypal_client.capture_order` caught non-200 responses and returned a synthetic `COMPLETED` capture dictionary, causing the backend ledger engine to settle funds and commit `settled` state to the database even though PayPal had rejected the transaction.

### 2. Root Cause
1. **PayPal Orders v2 Lifecycle**: In PayPal's Orders v2 API, an order starts in the `CREATED` state. The Capture endpoint (`POST /v2/checkout/orders/{id}/capture`) cannot be invoked until the buyer logs in and approves the order, transitioning it to `APPROVED`.
2. **Missing Buyer Approval Loop**: The application attempted to call `execute_intent` and `capture_intent` in an immediate sequential chain without redirecting the buyer's browser to PayPal's approval URL (`rel: "approve"` / `https://www.sandbox.paypal.com/checkoutnow?token=...`).
3. **Database Premature Settlement Vulnerability**: In live sandbox mode, non-200 PayPal responses were silently swallowed by a mock fallback in `paypal_client.py`, creating fake transaction records in the database.

### 3. Resolution Implemented (Fix)
1. **Option 1: Standard Interactive Checkout Approval Loop**:
   - `backend/app/services/paypal_client.py`:
     - Added `return_url` and `cancel_url` parameters to `create_order`, configuring `application_context` with `landing_page="LOGIN"` and `user_action="PAY_NOW"`.
     - Added `get_order(order_id)` to poll live PayPal status (`CREATED`, `APPROVED`, `COMPLETED`).
     - Removed silent mock capture fallback; detects `ORDER_NOT_APPROVED` from PayPal error details and raises `ValueError("ORDER_NOT_APPROVED: ...")`.
   - `backend/app/api/v1/intents.py`:
     - Updated `execute_intent` to accept `return_url` and return `approval_url`, `paypal_order_id`, and `order_status: "CREATED"`.
     - Added `GET /api/v1/intents/{intent_id}/order-status` returning real-time order status, approval links, and payer details.
     - Updated `capture_intent`: strictly verifies that PayPal confirms `status in ("COMPLETED", "PENDING")` before settling ledger holds and updating the database to `settled`.
   - `backend/app/api/v1/coach.py`:
     - In live sandbox mode, `execute_coach_action` transitions to `status="awaiting_approval"` and returns `approval_url`.
2. **Frontend Interactive Approval Flow**:
   - `frontend/src/features/intent/QuickIntentModal.jsx` & `frontend/src/features/override/EscapeWindowModal.jsx`:
     - Opens PayPal approval URL in the browser.
     - Displays sandbox buyer instructions, provides an explicit "I've Approved on PayPal — Complete & Settle" button, and auto-polls order status.
     - Renders verified completion details (Capture ID, Order ID, debited bucket).
   - `frontend/src/features/coach/CoachDrawer.jsx`:
     - 1-tap checkout ActionCards support interactive sandbox approval and complete/settle execution.
   - `frontend/src/App.jsx`:
     - Added redirect return listener for `?paypal_return=true&intent_id=...&token=...` to automatically verify, capture, and update ledger upon PayPal redirect.

### 4. Verification
- Added comprehensive automated test suite `tests/api/test_paypal_checkout_approval_loop.py`:
  - `test_execute_intent_returns_approval_url_and_created_status`: Verifies `approval_url` and `CREATED` status.
  - `test_capture_intent_fails_if_not_approved_leaves_db_untouched`: Verifies HTTP 422 `ORDER_NOT_APPROVED` leaves DB intent in `evaluating` and hold intact.
  - `test_capture_intent_succeeds_when_approved_and_settles_ledger`: Verifies settlement only occurs upon PayPal `COMPLETED` capture.
  - `test_get_order_status_endpoint`: Verifies `GET /{intent_id}/order-status`.
- Full automated test suite passes: `pytest tests/` (134 passed, 1 skipped in 14.77s).


