# Handoff Report: Bills Envelope Config, Quick Intent Scaffolding Fix, PayPal Routing & Roadmap (R3, R4, R5, R6)

**Agent**: `survey_explorer_3`  
**Working Directory**: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3`  
**Report Artifact**: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/report.md`  
**Handoff Type**: Hard (Investigation complete)

---

## 1. Observation

1. **R3 (Bills Envelope Config & Rebalancing)**:
   - `frontend/src/features/hud/BucketConfigModal.jsx` (lines 6–10, 50–79): Contains state and inputs for `dailyDollars`, `freedomDollars`, `vaultPercent`, `cooldownSeconds`, and `minChars`. There is no state variable or input for Reserved Bills target amount (`billsDollars`).
   - `backend/app/models/user.py` (`BudgetPolicyBase`, lines 30–41; `BudgetPolicyUpdate`, lines 48–59): Contains `vault_skim_bps`, `daily_amount`, `freedom_monthly_amount`. It does not contain `bills_monthly_amount`.
   - `backend/app/schemas/common.py` (`PolicyUpdate`, lines 16–25): Does not contain `bills_monthly_amount`.
   - `backend/app/ledger/engine.py` (`sync_and_allocate_buckets`, lines 393–397):
     ```python
     bills_sum = (
         current_bills_posted
         if current_bills_posted > 0
         else sum(b.amount for b in scheduled_bills)
     )
     ```
     This hardcodes retaining `current_bills_posted` when greater than zero, preventing user policy updates from adjusting the bills allocation.
   - `backend/app/ledger/engine.py` (lines 421–451): Paired double-entry transfers (`diff = target_amt - curr_amt`) are already wired to create debits and credits between `bank` and the target bucket (`-Bank / +Bucket = $0.00`).

2. **R4 (Quick Intent Category Bug & Scaffolding Cleanup)**:
   - `backend/app/agents/shared/llm_client.py` (lines 178, 190, 199):
     - Line 178 returns `"category": "savings_violation"`.
     - Line 190 returns `"category": "medical_emergency" if "medical" in short_tag else "emergency"`.
     - Line 199: `if any(w in lower for w in ("grocer", "supermarket", "safeway", "food", "milk", ...)): return { ... "category": "groceries" ... }`. The `"food"` token catches general food and dining utterances (e.g., "Thai food", "fast food") and assigns them to `groceries` before line 256 (`eating_out`) can evaluate.
   - `backend/app/agents/intent/parser.py` (lines 65, 74): Exception fallback returns `"category": "other"`.
   - `backend/app/api/v1/intents.py` (lines 75, 126): Defaults to `"other"` and `"general"`.
   - `docs/bugs.md`: Currently logs bugs `BUG-001` through `BUG-008`. The next entry is `BUG-009`.

3. **R5 (Real-Time PayPal Account Routing)**:
   - `backend/app/services/paypal_client.py` (`create_order`, lines 150–170): `purchase_units` omits `payee`. In PayPal Orders v2, an omitted payee defaults to the API credentials' business account (`PAYPAL_CLIENT_ID`).
   - `backend/app/services/paypal_client.py` (`create_payout`, lines 284–301): `items[0].receiver` explicitly routes payouts to the passed `receiver_email`.
   - `backend/app/jobs/lifecycles.py` (line 154): Vault skim payout routes to `receiver_email="vault@sandbox.paypal.com"`.
   - `backend/app/api/v1/bills.py` (line 66): Bill payment payout routes to `receiver_email=bill.payee_email`.
   - Internal bucket reallocations (`LedgerEngine.record_double_entry_transfer`) are purely on-ledger database records and do not invoke external PayPal APIs.

4. **R6 (Roadmap Update and Rename)**:
   - `docs/ROADMAP_PHASE4_PHASE5.md` does not currently exist on disk (referenced in `docs/problems.md` line 405).
   - `ORIGINAL_REQUEST.md` (R6) specifies updating the roadmap to document Phase 5, The Trinity Batch Dispatcher, and Bills envelope configuration, and creating/renaming to `docs/ROADMAP_PHASE5.md`.

5. **Existing Tests**:
   - `backend/.venv/bin/pytest tests/` executed successfully: 44 passed, 1 skipped in 4.64s.

---

## 2. Logic Chain

1. **R3 Logic**:
   - Adding `bills_monthly_amount: Optional[int] = Field(default=120000, ge=0)` to `BudgetPolicyBase`, `BudgetPolicyUpdate`, and `PolicyUpdate` permits the user to persist a custom bills target via `PUT /api/v1/me/policy`.
   - In `LedgerEngine.sync_and_allocate_buckets`, checking `policy.bills_monthly_amount` allows `target_bills` to reflect the user's configured target rather than hardcoding `current_bills_posted`.
   - Because lines 421–451 in `LedgerEngine.sync_and_allocate_buckets` already compute `diff = target_amt - curr_amt` and execute `record_double_entry_transfer` with `bank`, changing `bills_monthly_amount` automatically triggers balanced zero-sum transfers (`-Bank / +Bills = $0.00` when diff > 0, or `+Bank / -Bills = $0.00` when diff < 0).
   - Adding the input field in `BucketConfigModal.jsx` exposes this control to the user, with immediate updates reflected on the HUD upon save.

2. **R4 Logic**:
   - In `llm_client.py`, removing `"food"` from the `groceries` token list prevents dining utterances containing "food" from being misrouted to `groceries`.
   - Normalizing emergency classification to strictly return `"emergency"` removes lingering scaffolding labels (`medical_emergency`, `savings_violation`).
   - Defining the canonical set (`groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`/`dining_out`, `emergency`) and documenting the fix under `BUG-009` in `docs/bugs.md` ensures full consistency across frontend, parser, and database records.

3. **R5 Logic**:
   - Documenting the exact routing rules in `docs/paypal_integration.md`, `docs/architecture.md`, and `docs/agent_design.md` resolves ambiguity around how money moves in PayPal sandbox: Orders v2 buyer checkouts default to the credential merchant account, internal transfers stay on-ledger with zero float, and Payouts route directly to target emails (`vault@sandbox.paypal.com`, `bill.payee_email`, `BatchPaymentItem.payee_email`).

4. **R6 Logic**:
   - Creating `docs/ROADMAP_PHASE5.md` captures Phase 4 completion and details Phase 5 implementation (Emergency Vault, Partner Dual-Flow), Trinity Batch Dispatcher, and Bills envelope configuration.

---

## 3. Caveats

- **No Caveats**: All relevant files, schemas, endpoints, tests, and documentation paths were directly inspected and verified in the live workspace.

---

## 4. Conclusion

- **R3**: Readily implementable by adding `bills_monthly_amount` to `BudgetPolicyBase`/`PolicyUpdate`, updating `sync_and_allocate_buckets` to prioritize `policy.bills_monthly_amount`, and adding the input field in `BucketConfigModal.jsx`.
- **R4**: Scaffolding artifacts (`food` token collision, `medical_emergency`, `savings_violation`, `other`) identified and remediation mapped to canonical 7-category taxonomy; `BUG-009` structured for `docs/bugs.md`.
- **R5**: PayPal routing traced across Orders v2, double-entry ledger, emergency disbursements, and Payouts; documentation update plan prepared for `docs/paypal_integration.md`, `docs/architecture.md`, and `docs/agent_design.md`.
- **R6**: Roadmap update and rename specifications established for `docs/ROADMAP_PHASE5.md`.

---

## 5. Verification Method

To independently verify all findings and test proposals:
1. Run test suite:
   ```bash
   backend/.venv/bin/pytest tests/
   ```
2. Inspect target code locations:
   - `frontend/src/features/hud/BucketConfigModal.jsx` (lines 6–79)
   - `backend/app/models/user.py` (lines 30–59)
   - `backend/app/schemas/common.py` (lines 16–25)
   - `backend/app/ledger/engine.py` (lines 390–450)
   - `backend/app/agents/shared/llm_client.py` (lines 173–260)
   - `backend/app/services/paypal_client.py` (lines 150–170, 280–305)
   - `docs/bugs.md` (lines 196–231)
3. Invalidation Conditions:
   - If `PUT /api/v1/me/policy` cannot reallocate `bills` without breaking total ledger equality, the zero-sum invariant would be violated.
