# Dispatch: Milestone 2 - Configurable Bills Allocation in Envelope Settings (worker_m2)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Project Architecture & Contracts: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Investigation Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/report.md` (Section 1: R3)

## Role & Mission
You are `worker_m2`, an instance of `teamwork_worker`.
Your mission is to implement M2: Configurable Bills Allocation in Envelope Settings across backend models, ledger engine, API, and frontend `BucketConfigModal.jsx`.

## Exclusive Write Ownership
You exclusively own and may edit:
- `backend/app/models/user.py`
- `backend/app/schemas/common.py`
- `backend/app/ledger/engine.py`
- `frontend/src/features/hud/BucketConfigModal.jsx`
- `frontend/src/shared/api.js`

You MUST NOT edit files owned by other milestones.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Technical Specifications
1. Backend Models & Schemas:
   - In `backend/app/models/user.py`:
     - Add `bills_monthly_amount: Optional[int] = Field(default=120000, ge=0)` to `BudgetPolicyBase` and `BudgetPolicyUpdate`.
   - In `backend/app/schemas/common.py`:
     - Add `bills_monthly_amount: Optional[int] = None` to `PolicyUpdate`.
2. Backend Ledger Engine (`backend/app/ledger/engine.py`):
   - In `sync_and_allocate_buckets`:
     - Update lines 393-397 so `bills_sum` / `target_bills` evaluates `policy.bills_monthly_amount` when present:
       ```python
       if policy and policy.bills_monthly_amount is not None:
           target_bills = policy.bills_monthly_amount
       else:
           target_bills = current_bills_posted if current_bills_posted > 0 else sum(b.amount for b in scheduled_bills)
       ```
     - Ensure the rebalancing block (lines 421-451) executes balanced paired double-entry transfers (`diff = target_bills - current_bills_posted`, debited/credited with `bank` via `record_double_entry_transfer`) enforcing `-Bank / +Bills = $0.00` with zero sum.
3. Frontend Integration (`frontend/src/features/hud/BucketConfigModal.jsx` & `frontend/src/shared/api.js`):
   - In `BucketConfigModal.jsx`:
     - Add an input field for Reserved Bills target ($ USD).
     - Initialize from `policy.bills_monthly_amount` (converting cents to dollars `/ 100`).
     - On save, include `bills_monthly_amount: Math.round(parseFloat(billsDollars) * 100)` in `onSave(payload)`.
   - In `frontend/src/shared/api.js`:
     - Ensure policy update payload passes `bills_monthly_amount` to `PUT /api/v1/me/policy`.
4. Verification:
   - Run `backend/.venv/bin/pytest tests/`.
   - Verify double-entry transfer math and that total ledger balance remains balanced.

## Completion Criteria
1. Changes implemented cleanly in target files.
2. All tests pass (`backend/.venv/bin/pytest tests/`).
3. Write `handoff.md` in `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
4. Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).


## 2026-11-08T14:45:42Z
You are worker_m2, an instance of teamwork_worker.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/DISPATCH.md, /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md, and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md.
Follow all instructions in DISPATCH.md.
Implement M2: Configurable Bills Allocation in Envelope Settings across user model, policy schemas, ledger engine, and BucketConfigModal.jsx.
Run tests and verify.
Write handoff.md in your working directory and notify parent orchestrator (28249f08-094c-49f2-824d-ac8a44bcc29f).
