# Phase 5 Specification & Codebase Investigation Report

**Document**: Phase 5 Technical Specification & Architecture Mapping  
**Author**: `survey_spec_miner_1` (teamwork_spec_miner)  
**Date**: 2026-11-08  
**Target Milestone**: Phase 5 Implementation (R1) — Emergency Vault Allocation, Autonomous Payment Execution (BUG-008), Accountability Partner Dual-Flow Escape Window, and Model Branding Removal.  
**Authoritative Reference Sources**:
- `ORIGINAL_REQUEST.md` (Requirements R1, Acceptance Criteria)
- `/home/aster42/.gemini/antigravity/brain/110647b1-24c2-490f-aaff-6cd41f7efd42/phase5_implementation_plan.md`
- `docs/bugs.md` (BUG-008 Root Cause Analysis & Resolution Plan)
- `docs/problems.md` (Problem 5: Emergency Override Policy & Abuse Protection)
- `docs/TRINITY_RULES.md` & `docs/trinity_logic.md`
- Live codebase: `backend/app/ledger/engine.py`, `backend/app/api/v1/intents.py`, `backend/app/api/v1/overrides.py`, `backend/app/api/v1/coach.py`, `backend/app/agents/insights/coach.py`, `backend/app/agents/intent/parser.py`, `backend/app/agents/rag.py`, `backend/app/agents/shared/llm_client.py`, `frontend/src/features/intent/QuickIntentModal.jsx`, `frontend/src/features/override/EscapeWindowModal.jsx`, `frontend/src/features/coach/CoachDrawer.jsx`, `tests/`

---

## Executive Summary

Phase 5 hardens the FireWallet financial firewall across four core pillars:
1. **Emergency Vault Allocation & Autonomous Execution (BUG-008 Resolution)**:
   Resolves the critical architecture mismatch where emergency spending intents were erroneously drawing from `daily` or `bank`, or being hard-blocked by `can_spend` Rule 1. Verified emergencies (`is_genuine_emergency() = True`) must auto-route to the `vault` bucket with a 0-second cooldown bypass. If the Vault balance is insufficient, funds cascade cleanly from Bank Foundation (`vault_avail` + `bank_remainder`) via balanced double-entry transfers (`emergency_vault_draw`). The AI Coach is empowered to execute verified emergency payments autonomously.
2. **Accountability Partner Escalation & Dual-Flow Escape Window**:
   When an override is initiated and an accountability partner is linked (`partner_required_for_bank` = True or active `PartnerLink` exists), the backend generates a single-use cryptographic approval token (`raw_token`), hashes it for storage (`token_hash`), logs it to server logs, and returns it in the API response for UI testing.
   - **Happy Branch (Partner Approves)**: Partner visits `/partner/approve/{token}` and confirms. Spend unlocks immediately with 0s cooldown and 0 confession characters.
   - **Friction Branch (Partner Unresponsive or Times Out)**: If the partner does not approve before the window, standard friction gates apply: mandatory 200-character reflective confession and a 180-second countdown timer.
   - **Outcome Alerts**: Final outcome alert notifications are dispatched to the partner logging whether the payment was ultimately settled or cancelled.
3. **Model Branding Removal**:
   Strict UI verification ensuring no LLM model or vendor branding (Groq, Llama, OpenAI, Gemini, Claude, ChatGPT, etc.) appears in UI labels, badges, headers, tooltips, or chat bubbles. The UI maintains a clean, neutral "Financial Coach" / "AI Engine Active" presentation.
4. **Test Suite Impact**:
   Existing tests (`test_trinity_rules.py`, `test_api_endpoints.py`, `test_agent_and_rag.py`) currently assume Vault spend is unconditionally denied and emergency spends settle from Bank Foundation (`buckets["bank"] == 62000`). Phase 5 requires updating existing test assertions and introducing dedicated test cases for Vault emergency draw, cascading remainder, partner token generation, partner approval bypass, and partner timeout fallback.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Emergency Vault | Emergency Intent Classification & Vault Routing | Spend intent utterance evaluated by `is_genuine_emergency()`. When genuine (ER, urgent medical, stranded towing, utility shutoff), intent routes `recommended_bucket = "vault"` and `target_kind = "vault"` instead of daily/freedom. | Utterance, merchant name, category, amount | Structured classification payload: `is_emergency: true`, `recommended_bucket: "vault"`, `status: "allowed"` or `"override_approved"`, `cooldown_seconds: 0` | If luxury/splurge terms present (e.g. steakhouse, concert), `is_emergency` returns false and routes to freedom/daily | `backend/app/agents/rag.py:132`, `backend/app/agents/intent/parser.py:81`, `phase5_implementation_plan.md` |
| 2 | Emergency Vault | LedgerEngine Emergency Vault Spend Unlock | Updates `LedgerEngine.can_spend()`: Rule 1 permits direct spend from `vault` when `is_emergency` is true. Normal non-emergency spends remain strictly denied. | `user_id`, `amount_minor`, `source_kind="vault"`, `is_emergency=True` | `Tuple(True, "allowed", "Emergency vault draw permitted")` | Non-emergency vault spend returns `(False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden.")` | `backend/app/ledger/engine.py:118`, `docs/bugs.md:209`, `problems.md:Problem 5` |
| 3 | Emergency Vault | Vault-to-Bank Cascade Allocation | If available Vault funds are less than the emergency amount, all available Vault funds are drawn and the remainder is cascaded from Bank Foundation via paired double-entry transfer (`emergency_vault_draw`). | `amount_minor`, `vault_avail`, `bank_avail` | Balanced double-entry transfer legs (`-bank_remainder / +vault`), single hold on Vault for total amount | Returns HTTP 409 / Insufficient funds if total pool `vault_avail + bank_avail < amount_minor` | `phase5_implementation_plan.md:68`, `ORIGINAL_REQUEST.md:R1` |
| 4 | Emergency Vault | AI Coach Autonomous Payment Execution | When Coach verifies an emergency expense, Coach generates pre-configured 1-tap `ActionCard(action_type="paypal_checkout", label="Emergency Autonomous Pay $XX.XX via Vault (0s Delay)", target_bucket="vault", is_emergency=True)`. Upon trigger, server creates PayPal sandbox order and auto-captures atomically. | `CoachExecuteActionRequest` with `target_bucket="vault"`, `is_emergency=True`, `auto_capture_demo=True` | `CoachExecuteActionResponse` with `status: "settled"`, `source_bucket: "vault"`, `paypal_order_id`, `paypal_capture_id` | If PayPal sandbox is offline or credentials missing, fails cleanly with HTTP 409 / 502 with descriptive message | `backend/app/agents/insights/coach.py:303`, `backend/app/api/v1/coach.py:148`, `phase5_implementation_plan.md:80` |
| 5 | Emergency Vault | QuickIntentModal Instant Emergency Unlock | In `QuickIntentModal.jsx`, when `verdict.is_emergency` is true, displays emergency banner ("Genuine emergency detected — 0s delay bypass eligible!"), auto-selects Vault, and exposes direct 1-tap "Emergency Pay via PayPal" button. | Intent evaluation response with `is_emergency: true` | Instant payment execution trigger bypassing modal redirect | If execution fails, displays inline error banner with error detail | `frontend/src/features/intent/QuickIntentModal.jsx:222`, `phase5_implementation_plan.md:104` |
| 6 | Partner Escalation | Cryptographic Partner Token Generation & Link Dispatch | When an override is requested and `partner_required_for_bank` is active, backend generates single-use cryptographic token (`secrets.token_urlsafe(32)`), stores SHA-256 hash in `partner_approvals`, outputs token in server logs, and returns token in API response. | `intent_id`, user partner configuration | `OverrideResponse` including `partner_token: str`, `partner_approval_url: str`, `status: "pending"` | Returns HTTP 404 if intent not found; falls back to standard friction if partner not configured | `backend/app/models/user.py:84`, `backend/app/api/v1/overrides.py:35`, `phase5_implementation_plan.md:88` |
| 7 | Partner Escalation | Partner Decision Public Inspection Endpoint | Public `GET /api/v1/partner/approve/{token}` allowing accountability partner to inspect the proposed expenditure, category, amount, user reason, and approval expiration. | `token: str` in URL path | JSON containing `override_id`, `amount_cents`, `utterance`, `short_tag`, `status`, `expires_at` | HTTP 404 if token invalid; HTTP 410 if token already used or expired | `phase5_implementation_plan.md:91` |
| 8 | Partner Escalation | Partner Decision Submission Endpoint | Public `POST /api/v1/partner/approve/{token}/decision` where partner submits `{"decision": "approved" | "rejected"}`. | `token: str`, `decision: "approved" \| "rejected"` | JSON with `status: "approved" \| "rejected"`, `override_id`, `decided_at` | HTTP 400 for invalid decision strings; HTTP 409 if already decided | `backend/app/api/v1/overrides.py`, `phase5_implementation_plan.md:92` |
| 9 | Partner Escalation | Immediate Unlock on Partner Approval | If partner decision is `"approved"`, `Override.status` becomes `"approved"`, `Override.ready_at` set to `utc_now()`, `Intent.status` becomes `"override_approved"`. Cooldown is 0s, 0 confession characters required. | Partner approval action or polling `GET /overrides/{id}` / `check-cooldown` | Instant transition to executable checkout state | If attempted before approval without confession, returns HTTP 409 | `phase5_implementation_plan.md:8`, `ORIGINAL_REQUEST.md:R1` |
| 10 | Partner Escalation | Friction Fallback on Unresponsive Partner | If partner fails to approve within the window (or link expires/rejects), system enforces Gate 1 (200-character confession) and Gate 2 (180-second countdown timer). | Unresponsive partner or expired approval token | Cooldown active: `seconds_left: 180`, textarea enabled with `min_chars: 200` | Premature check-cooldown calls return HTTP 409 Conflict | `backend/app/api/v1/overrides.py:105`, `phase5_implementation_plan.md:9` |
| 11 | Partner Escalation | Final Outcome Alert Logging | Upon payment execution or user cancellation, backend logs a structured outcome alert and records status in `PartnerApproval`, logging whether payment was settled or cancelled. | Payment capture (`captureIntent`) or override cancellation | Server log message (`[PARTNER OUTCOME ALERT] Override {id} resolved: PAYMENT SETTLED/CANCELLED`) + status in DB | Silently logs and fails safely if notification pipeline encounters errors | `ORIGINAL_REQUEST.md:R1`, `phase5_implementation_plan.md:10` |
| 12 | Partner Escalation | EscapeWindowModal Dual-Branch Interface | `EscapeWindowModal.jsx` displays dual-branch state: (1) "Awaiting Partner Approval" card with copyable token/link for testing; (2) Instant unlock card when approved; (3) Fallback 200-char confession + 180s countdown when unapproved. | `isOpen`, `intentId`, override state | Interactive modal with live token copy button, status indicator, countdown timer, and settlement button | Displays rose-colored error banner on network or validation errors | `frontend/src/features/override/EscapeWindowModal.jsx`, `phase5_implementation_plan.md:115` |
| 13 | Model Branding | Frontend Model Branding Audit & Removal | Ensure no vendor/model names (Groq, Llama, OpenAI, Gemini, Claude, ChatGPT, Mistral) are displayed in UI text, tooltips, buttons, or chat bubbles. Status pills show "AI Engine Active" / "Deterministic Mode". | Frontend source code & rendered DOM | Completely brand-neutral UI | N/A | `ORIGINAL_REQUEST.md:R1`, `CoachDrawer.jsx:347` |
| 14 | Model Branding | Coach Status API Generic Decoupling | `GET /api/v1/coach/status` reports engine connectivity while frontend consumes `status: "online" | "local_fallback"` without rendering vendor strings. | HTTP GET `/api/v1/coach/status` | JSON `{ status: "online", provider: ..., model: ..., has_live_keys: true }` | Falls back to `{ status: "local_fallback", has_live_keys: false }` if offline | `backend/app/api/v1/coach.py:39`, `frontend/src/features/coach/CoachDrawer.jsx:86` |

---

## Edge Cases

| # | Feature | Input / Condition | Observed & Required Behavior |
|---|---------|-------------------|-----------------------------|
| 1 | Emergency Vault Routing | Utterance contains "emergency reserves" while celebrating: e.g. "Spend $150 from emergency reserves celebrating promotion at steakhouse" | `is_genuine_emergency` recognizes luxury/celebration keywords (`steakhouse`, `celebrating`), strips savings reference, returns `is_emergency=False`. Intent routes to `freedom` or `daily`, requires full 200-char confession + 180s timer. |
| 2 | Emergency Vault Routing | Legitimate emergency: "Urgent ER visit for broken ankle, copay $180" | `is_genuine_emergency` matches acute medical care pattern, returns `is_emergency=True`. Intent auto-routes `recommended_bucket="vault"`. `can_spend` allows spend with 0s cooldown. |
| 3 | Vault Cascade | Emergency amount = $250.00; Vault available = $200.00; Bank available = $800.00 | Cascade draws all $200.00 from Vault. Remainder of $50.00 is transferred from Bank to Vault via zero-sum double-entry (`emergency_vault_draw`). Hold of $250.00 placed on Vault. Resulting balances: Vault = $0.00, Bank = $750.00. |
| 4 | Vault Cascade | Emergency amount = $1,200.00; Vault available = $200.00; Bank available = $800.00 (Total available = $1,000.00) | Total available funds in Vault + Bank ($1,000.00) < proposed emergency amount ($1,200.00). System denies request with HTTP 409: "Insufficient emergency reserves across Vault and Bank Foundation." |
| 5 | Vault Cascade | Emergency amount = $60.00; Vault available = $0.00; Bank available = $800.00 | 100% of the emergency cascades from Bank Foundation to Vault via `record_double_entry_transfer(from=bank, to=vault, amount=6000, entry_kind="emergency_vault_draw")`. Vault holds and settles $60.00. Resulting balances: Vault = $0.00, Bank = $740.00. |
| 6 | Non-Emergency Vault Access | User explicitly requests to spend from Vault for non-emergency: "Can I buy a $500 laptop from Vault?" | `LedgerEngine.can_spend` strictly evaluates Rule 1 (`is_emergency=False`). Hard-denied: "Vault is locked long-term savings. Direct spend is strictly forbidden." |
| 7 | Partner Escalation | Partner approves token via `POST /api/v1/partner/approve/{token}/decision` within window | Token verified; `partner_approvals.status = "approved"`, `overrides.status = "approved"`, `overrides.ready_at = utc_now()`, `intents.status = "override_approved"`. 0s cooldown and 0 confession characters enforced. User can immediately execute PayPal checkout. |
| 8 | Partner Escalation | Partner decision endpoint called with invalid/garbage token: `GET /api/v1/partner/approve/invalid-token-123` | Backend checks token hash; returns HTTP 404: "Partner approval request not found or invalid token." |
| 9 | Partner Escalation | Partner attempts to approve or reject already decided token | Backend detects `PartnerApproval.status != "pending"`; returns HTTP 409 Conflict: "Partner approval has already been decided." Single-use token replay prevented. |
| 10 | Partner Escalation | Partner does not respond / times out | Frontend and backend fall back to friction path. If user submits confession < 200 characters, returns HTTP 422: "Confession must be at least 200 characters." If user calls `check-cooldown` before 180 seconds, returns HTTP 409: "Cooldown active. X seconds remaining." |
| 11 | Partner Outcome Alert | User cancels override in Escape Window after partner approved | System detects override abandonment / cancellation. Server logs: `[PARTNER OUTCOME ALERT] Override {id} resolved: CANCELLED by user`. Database updates record without executing ledger debit. |
| 12 | Partner Outcome Alert | User completes PayPal payment after partner approval or countdown | `executeIntent` creates order and `captureIntent` settles payment. Server logs: `[PARTNER OUTCOME ALERT] Override {id} resolved: PAYMENT EXECUTED ($XX.XX, PayPal Order {order_id})`. |
| 13 | Coach Autonomous Execution | User asks Coach: "Emergency! Tire blew out on highway, tow truck costs $65" | Coach RAG detects genuine stranded emergency, sets `is_emergency=True`, targets `vault`, auto-creates approved Intent & Override, and returns 1-tap `ActionCard(action_type="paypal_checkout", label="Emergency Autonomous Pay $65.00 via Vault (0s Delay)", target_bucket="vault")`. Triggering immediately creates PayPal order and captures hold. |
| 14 | Model Branding Suppression | Backend LLM client is configured with Groq `llama-3.3-70b-versatile` | Frontend CoachDrawer displays "AI Engine Active" pill and "Financial Coach" title. Message text does not contain vendor self-identifications. DOM inspector confirms zero vendor branding strings in rendered markup. |

---

## Detailed Codebase Mapping

### 1. Backend Components

#### `backend/app/ledger/engine.py`
- **Location**: `backend/app/ledger/engine.py:87-144` (`can_spend`)
- **Current Behavior**:
  ```python
  # Rule 1: Vault is locked long-term savings
  if source_kind == "vault":
      return False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden."
  ```
  Unconditionally denies spend from `vault`. Does not accept or check `is_emergency`.
- **Required Changes**:
  1. Add `is_emergency: bool = False` to `can_spend` signature.
  2. Modify Rule 1:
     ```python
     # Rule 1: Vault is locked long-term savings (Emergency exception)
     if source_kind == "vault":
         if not is_emergency:
             return False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden."
         # When is_emergency is True, permit spend from Vault
     ```
  3. In balance check: if `source_kind == "vault"` and `is_emergency` is True:
     - Check combined available balance `vault_avail + bank_avail >= amount_minor`.
     - If sufficient, allow spend (`is_allowed = True, status = "allowed"`).
  4. In `place_hold` & `settle_hold`: support entry kind `emergency_vault_draw`.

#### `backend/app/api/v1/intents.py`
- **Location**: `backend/app/api/v1/intents.py:40-180` (`submit_intent`) & `256-320` (`execute_intent`)
- **Current Behavior**:
  - `submit_intent` calls `can_spend` without `is_emergency`.
  - When `is_emergency` is true, sets `cooldown_seconds = 0` but sets `action_card` to `open_override`, forcing user into Escape Window.
  - In `execute_intent`: only places hold on single bucket `intent.source_bucket_id`. If `override_approved`, falls back to Bank if source lacks funds, never cascading from Vault to Bank.
- **Required Changes**:
  1. In `submit_intent`:
     - If `intent.is_emergency`:
       - Force `target_kind = "vault"` and `intent.recommended_bucket = "vault"`.
       - Assign `intent.source_bucket_id = vault_bucket.id`.
       - Call `LedgerEngine.can_spend(..., is_emergency=True)`.
       - If allowed, set `verdict = "accepted"`, `cooldown_seconds = 0`, status = `"allowed"`.
       - Construct ActionCard:
         ```python
         action_card = ActionCard(
             action_type="paypal_checkout",
             label=f"Emergency Pay ${body.amount / 100:.2f} via PayPal (Vault 0s Delay)",
             short_tag=intent.short_tag,
             utterance=body.utterance,
             amount_cents=body.amount,
             category=intent.category or "emergency",
             necessity="daily_living",
             target_bucket="vault",
             is_emergency=True,
             verdict="accepted",
         )
         ```
  2. In `execute_intent`:
     - If `intent.is_emergency`:
       - Retrieve balances: `vault_avail = balances["vault"]["available"]`, `bank_avail = balances["bank"]["available"]`.
       - If `vault_avail < intent.amount`:
         - Calculate remainder: `cascade_amount = intent.amount - vault_avail`.
         - Execute double-entry cascade transfer:
           ```python
           await LedgerEngine.record_double_entry_transfer(
               session=session,
               user_id=user.id,
               from_bucket_id=balances["bank"]["bucket_id"],
               to_bucket_id=balances["vault"]["bucket_id"],
               amount_minor=cascade_amount,
               entry_kind="emergency_vault_draw",
               memo=f"Emergency Cascade from Bank to Vault ({intent.short_tag})",
               from_bucket_kind="bank",
               to_bucket_kind="vault",
           )
           ```
       - Place hold on Vault bucket for `intent.amount` with memo `f"[EMERGENCY VAULT DRAW] {intent.short_tag}"`.

#### `backend/app/agents/insights/coach.py` & `backend/app/api/v1/coach.py`
- **Location**: `backend/app/agents/insights/coach.py:294-350` & `backend/app/api/v1/coach.py:148-260`
- **Current Behavior**:
  - `coach.py:307`: `chosen_kind = "daily" if daily_avail >= amount_cents else "bank"`. Never targets Vault!
  - `coach.py:295`: If `target_bucket == "vault"`, rejects spend outright.
  - `api/v1/coach.py:154`: `target_kind = body.target_bucket if body.target_bucket in ("daily", "freedom", "bills", "bank") else "freedom"`. Drops `vault`!
- **Required Changes**:
  1. In `coach.py`:
     - When `det_emerg` is True:
       - Set `target_bucket = "vault"`, `action_type = "paypal_checkout"`, `decision_status = "accepted"`.
       - Create pre-approved Intent with `recommended_bucket = "vault"`, `is_emergency = True`, `status = "allowed"`.
       - Create ActionCard:
         ```python
         action_card = ActionCard(
             action_type="paypal_checkout",
             label=f"Emergency Autonomous Pay ${amount_cents / 100:.2f} via Vault (0s Delay)",
             short_tag=short_tag,
             utterance=utterance[:120],
             amount_cents=amount_cents,
             category=category if category != "general" else "emergency",
             necessity="daily_living",
             target_bucket="vault",
             is_emergency=True,
             verdict="accepted",
         )
         ```
  2. In `execute_coach_action` (`backend/app/api/v1/coach.py`):
     - Allow `"vault"` in allowable target buckets when `is_emergency` is True.
     - Implement vault-to-bank cascade logic when Vault funds < `amount_cents`.
     - Support autonomous execution: automatically create order, capture order, settle hold, and return settled response atomically.

#### `backend/app/api/v1/overrides.py`
- **Location**: `backend/app/api/v1/overrides.py:34-182`
- **Current Behavior**:
  - Implements 200-char confession and 180s cooldown.
  - Includes `"partner_required": policy.partner_required_for_bank`, but does NOT generate any token or provide partner endpoints.
- **Required Changes**:
  1. In `create_override`:
     - If user has partner linked (`BudgetPolicy.partner_required_for_bank` is True or active `PartnerLink` exists):
       - Generate cryptographic raw token: `raw_token = secrets.token_urlsafe(32)`.
       - Compute hash: `token_hash = hashlib.sha256(raw_token.encode()).hexdigest()`.
       - Create `PartnerApproval(override_id=override.id, partner_link_id=partner_link.id, token_hash=token_hash, status="pending")`.
       - Log token in server log:
         `logger.warning(f"🚨 [PARTNER ESCALATION] Token: {raw_token} | URL: /partner/approve/{raw_token}")`
       - Return `partner_token: raw_token`, `partner_approval_url: f"/partner/approve/{raw_token}"` in `OverrideResponse`.
  2. Add Public Endpoints:
     - `GET /api/v1/partner/approve/{token}`:
       - Hash token, look up `PartnerApproval` where `token_hash == hash`.
       - Return override details (amount, utterance, category, short_tag, user display name, status).
     - `POST /api/v1/partner/approve/{token}/decision`:
       - Accept `{"decision": "approved" | "rejected"}`.
       - If approved:
         - `PartnerApproval.status = "approved"`, `decided_at = utc_now()`.
         - `Override.status = "approved"`, `ready_at = utc_now()`.
         - `Intent.status = "override_approved"`.
         - Log outcome alert: `[PARTNER ESCALATION] Partner APPROVED override {override_id}. Spend unlocked with 0s cooldown.`
       - If rejected:
         - `PartnerApproval.status = "rejected"`, `Override.status = "rejected"`.
  3. Add Final Outcome Alert logging on execute/capture and cancel.

#### `backend/app/models/user.py` & `backend/app/schemas/common.py`
- `OverrideResponse` in `common.py`:
  Add `partner_token: Optional[str] = None`, `partner_approval_url: Optional[str] = None`, `partner_email: Optional[str] = None`.
- `PartnerApproval` table in `user.py`:
  Ensure fields match Alembic migration 0001: `id`, `override_id`, `partner_link_id`, `status`, `token_hash`, `decided_at`.

---

### 2. Frontend Components

#### `frontend/src/features/intent/QuickIntentModal.jsx`
- **Location**: `frontend/src/features/intent/QuickIntentModal.jsx:222-305`
- **Current State**: Displays small amber badge `Genuine emergency detected — 0-second zero-delay unlock eligible!`, but button says "Instant Emergency Override (0s Delay)", which opens `EscapeWindowModal`.
- **Required Update**:
  - When `verdict.is_emergency` is True:
    - Target bucket card clearly highlights `Vault (Emergency Reserve)`.
    - Main action button becomes `Emergency Pay $XX.XX via PayPal (Vault · 0s Delay)`.
    - Clicking executes payment directly through `handleExecutePayPal()` with 0s delay bypass.

#### `frontend/src/features/coach/CoachDrawer.jsx`
- **Location**: `frontend/src/features/coach/CoachDrawer.jsx:442-528`
- **Current State**: Action card displays `Emergency Verified · 0s Cooldown` with amount and button.
- **Required Update**:
  - When card is an emergency (`card.is_emergency` is true), button label displays: `Emergency Autonomous Pay $XX.XX via Vault (0s Delay)`.
  - Clicking invokes `executeCoachAction(card, autoCaptureDemo=true)` with `target_bucket="vault"`.
  - Immediate real-time feedback with capture and order IDs.

#### `frontend/src/features/override/EscapeWindowModal.jsx`
- **Location**: `frontend/src/features/override/EscapeWindowModal.jsx`
- **Current State**: Has toggle for "Emergency Mode" vs "Standard". Missing partner approval workflow.
- **Required Update**:
  - **Branch 1: Partner Linked & Awaiting Approval**:
    - When `overrideData.partner_required` is true and status is `"pending"`:
      - Display banner: `Awaiting Accountability Partner Approval`.
      - Show interactive copy card with the generated `partner_token` and simulated approval link `/partner/approve/{token}` for easy tester evaluation.
      - Poll status or provide "Simulate Partner Approval" button for hackathon testing.
  - **Branch 2: Partner Approved (Happy Path)**:
    - As soon as partner approves:
      - Banner transitions to Emerald: `Accountability Partner Approved!`.
      - Displays `0s Cooldown · Confession Bypassed`.
      - Activates "Confirm & Pay via PayPal Now" button.
  - **Branch 3: Partner Unresponsive / Timed-out (Friction Path)**:
    - If partner does not approve within timeout:
      - Transition to friction gate: enables confession textarea requiring $\ge 200$ characters.
      - Activates 180-second countdown timer.
  - **Final Outcome Status Display**:
    - Displays footer notification: `Outcome alert dispatched to partner: Payment Settled` (or `Payment Cancelled`).

#### Frontend Model Branding Verification
- **Audit Findings**:
  - `frontend/src/App.jsx`: Clean. Displays "FireWallet", "Trinity Engine".
  - `frontend/src/features/hud/MobileHUD.jsx`: Clean. Displays "Financial Coach Ready", "Trinity HUD".
  - `frontend/src/features/coach/CoachDrawer.jsx`: Clean. Status pill displays "AI Engine Active" / "Deterministic Mode". Title displays "Financial Coach".
  - `frontend/src/features/analytics/DeepLedgerGrid.jsx`: Clean. Displays "Double-Entry Ledger & Audit Workbench".
  - `frontend/src/features/intent/QuickIntentModal.jsx`: Clean. Displays "Quick Intent Gateway", "Reason with Trinity Coach".
  - `frontend/src/features/override/EscapeWindowModal.jsx`: Clean. Displays "THE ESCAPE WINDOW", "Emergency Zero-Delay Verification".
- **Zero Occurrences**: Confirmed zero occurrences of "Groq", "Llama", "OpenAI", "Gemini", "Claude", "ChatGPT", "Mistral", "Qwen" across `frontend/src/`.

---

## Existing Tests & Test Suite Impact Analysis

| Test File | Test Name | Existing Assertion | Impact of Phase 5 Changes | Required Action |
|-----------|-----------|--------------------|---------------------------|-----------------|
| `tests/unit/test_trinity_rules.py` | `test_can_spend_rule_1_vault_is_locked` | Verifies `source_kind="vault"` returns `status="denied"` ("Vault is locked..."). | Validates non-emergency rule. When `is_emergency=False`, this must still pass. | Keep existing test; add new test `test_can_spend_rule_1_vault_emergency_allowed` verifying `is_emergency=True` succeeds with `status="allowed"`. |
| `tests/unit/test_trinity_rules.py` | *New Test Needed* | N/A | Need unit verification for emergency vault draw under cap, exceeding cap with bank cascade, and exceeding both buckets. | Add: (1) `test_vault_emergency_spend_allowed`; (2) `test_vault_emergency_cascade_from_bank`; (3) `test_vault_emergency_insufficient_total_denied`. |
| `tests/unit/test_agent_and_rag.py` | `test_emergency_detection_vs_luxury_false_positive` | Verifies `is_genuine_emergency` accepts ER/towing/shutoff and rejects steakhouse splurge. | Core classifier behavior. Continues to pass without modification. | Keep as-is. |
| `tests/unit/test_agent_and_rag.py` | `test_emergency_override_grants_zero_cooldown_and_settles_from_bank` | Asserts emergency intent settles from BANK: `buckets["bank"] == 62000` (80000 - 18000 = 62000). | **DIRECT CONFLICT with BUG-008 fix**: In Phase 5, $180.00 emergency must draw from Vault ($200.00 available), leaving Vault at $20.00 (2000 cents) and Bank untouched at $800.00 (80000 cents). | Update test to verify Vault is debited first: `assert buckets["vault"] == 2000` and `assert buckets["bank"] == 80000`. Add companion cascade test where emergency ($250.00) exceeds Vault ($200.00) and draws remainder from Bank. |
| `tests/unit/test_agent_and_rag.py` | `test_unified_coach_one_tap_actions_and_rag_context` | Verifies Coach PayPal checkout and Vault sweep. | Does not cover Coach autonomous emergency execution. | Add test verifying Coach autonomous emergency execution targets `vault` and auto-settles payment. |
| `tests/api/test_api_endpoints.py` | `test_override_escape_window_confession_and_cooldown` | Tests non-emergency 200-character confession requirement and 180s cooldown timer. | Validates non-partner friction path. Continues to pass. | Keep as-is; add `test_override_partner_approval_immediate_unlock` and `test_override_partner_rejection_or_timeout_fallback`. |
| `tests/api/test_paypal_balance_and_policy.py` | `test_policy_update_endpoint` | Tests updating policy fields including `override_cooldown_seconds` and `override_min_chars`. | Model already supports `partner_required_for_bank`. | Add test updating `partner_required_for_bank=True`. |
| `tests/unit/test_models.py` | `test_user_and_policy_model_dump` | Tests User, BudgetPolicy, LedgerEntry, Bill serialization. | `PartnerLink` and `PartnerApproval` are defined in `app.models.user`. | Add test verifying `PartnerLink` and `PartnerApproval` SQLModel serialization. |

---

## Verification Commands & Criteria

1. **Unit & API Test Execution**:
   ```bash
   backend/.venv/bin/pytest tests/unit/test_trinity_rules.py tests/api/test_api_endpoints.py tests/unit/test_agent_and_rag.py -v
   ```
2. **Whole Test Suite**:
   ```bash
   backend/.venv/bin/pytest tests/
   ```
   *Expected outcome*: 100% passing tests with 0 failures and 0 warnings treated as errors.
3. **Frontend Branding Verification**:
   ```bash
   grep -riE "(groq|llama|openai|gemini|claude|chatgpt)" frontend/src/
   ```
   *Expected outcome*: 0 matching lines.

---

## Summary of Technical Specifications for Phase 5 Implementers

1. **BUG-008 Emergency Vault Routing**:
   - Primary source for emergency spend is `vault`.
   - `LedgerEngine.can_spend()` accepts `is_emergency=True` and allows spending from `vault`.
   - Cascade logic: If `vault_avail < amount_minor`, transfer remainder `amount_minor - vault_avail` from `bank` to `vault` via `record_double_entry_transfer(..., entry_kind="emergency_vault_draw")`, then place hold on `vault`.
   - AI Coach generates `ActionCard` with `target_bucket="vault"` and executes payment autonomously upon verification.
2. **Accountability Partner Dual-Flow**:
   - `POST /api/v1/overrides`: When partner linked, generate cryptographic token, save hash to `PartnerApproval`, log to stdout/logs, and return token in response.
   - Public endpoints: `GET /api/v1/partner/approve/{token}` and `POST /api/v1/partner/approve/{token}/decision`.
   - Partner approval unlocks immediately (0s cooldown, 0 confession chars).
   - Partner timeout/unresponsiveness falls back to 200 chars + 180s cooldown timer.
   - Final outcome alert logged for payment settlement vs cancellation.
3. **Model Branding**:
   - Frontend is clean of vendor names. Maintain generic branding ("Financial Coach", "AI Engine Active", "Trinity Engine").
4. **Tests**:
   - Update `test_emergency_override_grants_zero_cooldown_and_settles_from_bank` to expect Vault debit rather than Bank debit.
   - Add tests for vault emergency spend, vault-to-bank cascade, partner approval token generation, partner instant unlock, and partner timeout fallback.
