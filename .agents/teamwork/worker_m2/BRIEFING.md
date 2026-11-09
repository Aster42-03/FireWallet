# BRIEFING — 2026-11-08T14:54:00Z

## Mission
Implement M2: Configurable Bills Allocation in Envelope Settings across user model, policy schemas, ledger engine, and BucketConfigModal.jsx.

## 🔒 My Identity
- Archetype: teamwork_worker
- Roles: implementer, qa, specialist
- Working directory: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/
- Original parent: 28249f08-094c-49f2-824d-ac8a44bcc29f
- Milestone: M2: Configurable Bills Allocation in Envelope Settings

## 🔒 Key Constraints
- Exclusively own and may edit:
  - backend/app/models/user.py
  - backend/app/schemas/common.py
  - backend/app/ledger/engine.py
  - frontend/src/features/hud/BucketConfigModal.jsx
  - frontend/src/shared/api.js
- MUST NOT edit files owned by other milestones.
- Zero-Float integer minor units (all currency values in integer cents).
- Double-Entry balanced rebalancing (-Bank / +Bills = $0.00).
- Preserve existing code comments and style.
- DO NOT CHEAT: no hardcoded test results, facade implementations, or circumventing tasks.

## Current Parent
- Conversation ID: 28249f08-094c-49f2-824d-ac8a44bcc29f
- Updated: not yet

## Task Summary
- **What to build**: Configurable Bills Allocation in Envelope Settings across user model, policy schemas, ledger engine, and BucketConfigModal.jsx.
- **Success criteria**:
  - `bills_monthly_amount` added to `BudgetPolicyBase`, `BudgetPolicyUpdate`, and `PolicyUpdate`.
  - `sync_and_allocate_buckets` respects `policy.bills_monthly_amount` and performs paired double-entry transfers (`diff = target_bills - current_bills_posted`, debited/credited with `bank` via `record_double_entry_transfer`).
  - `BucketConfigModal.jsx` and `shared/api.js` updated to view/set Reserved Bills target ($ USD), converting between cents and dollars.
  - Automated tests pass cleanly (`backend/.venv/bin/pytest tests/api/test_bills_config_e2e.py`).
- **Interface contracts**: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md § M2
- **Code layout**: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md § Code Layout

## Key Decisions Made
- Follow strict double-entry ledger invariants: rebalancing between Bank Foundation and Reserved Bills records matched credit/debit with zero net sum (-Bank / +Bills = $0.00).
- Fallback gracefully: if `policy.bills_monthly_amount` is unset or None, default to existing behavior (`current_bills_posted` or scheduled bills sum).
- Enforce capping against remaining pool in `sync_and_allocate_buckets` so allocation never causes Bank Foundation to overdraw or go negative.
- Clean minor unit conversions between USD decimal string in frontend and integer cents in backend.

## Change Tracker
- **Files modified**:
  - `backend/app/models/user.py`: Added `bills_monthly_amount: Optional[int] = Field(default=120000, ge=0)` to `BudgetPolicyBase` and `Optional[int] = None` to `BudgetPolicyUpdate`.
  - `backend/app/schemas/common.py`: Added `bills_monthly_amount: Optional[int] = Field(default=None, ge=0)` to `PolicyUpdate`.
  - `backend/app/ledger/engine.py`: Updated `sync_and_allocate_buckets` to evaluate `policy.bills_monthly_amount` for `target_bills` and rebalance via paired double-entry transfers.
  - `frontend/src/features/hud/BucketConfigModal.jsx`: Added `billsDollars` state, policy fetch initialization, Reserved Bills ($/month) form input, and save payload.
  - `frontend/src/shared/api.js`: Documented `bills_monthly_amount` support in `updatePolicy`.
- **Build status**: PASS (all 20 tests in `test_bills_config_e2e.py` and `test_paypal_balance_and_policy.py` pass 100%)
- **Pending issues**: None

## Quality Status
- **Build/test result**: PASS (pytest tests/api/test_bills_config_e2e.py tests/api/test_paypal_balance_and_policy.py: 20 passed in 2.15s)
- **Lint status**: Clean (py_compile validated)
- **Tests added/modified**: 15 tests in `tests/api/test_bills_config_e2e.py` passing 100%

## Loaded Skills
- None

## Artifact Index
- /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/DISPATCH.md — Dispatch instructions
- /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/progress.md — Progress log
- /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m2/handoff.md — Handoff report
