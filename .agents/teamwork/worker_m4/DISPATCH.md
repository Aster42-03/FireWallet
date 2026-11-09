# Dispatch: Milestone 4 - The Trinity Batch Dispatcher (worker_m4)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md` (R2)
- Project Architecture & Contracts: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Survey Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/report.md`
- Feature Spec: `docs/features.md` (lines 93–160)
- Tests: `tests/api/test_batch_dispatcher_e2e.py`

## Role & Mission
You are `worker_m4`, an instance of `teamwork_worker`.
Your mission is to implement M4: The Trinity Batch Dispatcher across backend and frontend.

## Technical Specifications
1. Database Model (`backend/app/models/batch_payment.py`):
   - Implement `BatchPaymentItemBase`, `BatchPaymentItem(table=True)`, `BatchPaymentItemRead` using SQLModel.
   - Fields: `id: str`, `user_id: str`, `bill_id: Optional[str]`, `recipient_name: str`, `payee_email: str`, `amount_minor: int`, `currency: str = "USD"`, `source_bucket: str = "bills"`, `status: str = "pending_approval"`, `paypal_payout_item_id: Optional[str]`, `error_message: Optional[str]`, `created_at`, `updated_at`.
   - Re-export in `backend/app/models/__init__.py`.
2. AI Coach Schema (`backend/app/schemas/common.py`):
   - Implement `BatchPaymentItemDTO` and `BatchDispatcherProposal` (with `coach_message`, `total_batch_amount_minor`, `items: List[BatchPaymentItemDTO]`, `risk_assessment: Dict[str, Any]` asserting Bank Foundation is protected).
3. REST Endpoints (`backend/app/api/v1/bills.py`):
   - `POST /api/v1/bills/batch-dispatcher/propose`: Analyzes pending bills / payout targets, generates `BatchDispatcherProposal`, stages items in `batch_payment_items` with status `"pending_approval"`, returns proposal and item IDs.
   - `GET /api/v1/bills/batch-dispatcher/queue`: Lists staged items with veto states, total isolated balance, and batch summary.
   - `POST /api/v1/bills/batch-dispatcher/execute`:
     - Blast Radius Containment: strictly enforces `source_bucket` in `("bills", "vault")`. If `source_bucket == "bank"` or if batch exceeds available isolated funds, reject immediately with HTTP 400.
     - Live PayPal Sandbox Requirement: check that live sandbox credentials are configured and reachable. If `access_token == "mock_sandbox_access_token"` or offline, reject immediately with HTTP 503 Service Unavailable (do NOT silently simulate success).
     - Sequential Idempotent Execution: iterate approved items, call `paypal_client.create_payout` with deterministic idempotency keys, record ledger debits on success, mark `Bill.status = "paid"`, and update item status to `"paid"` (or `"failed"` on error).
4. Frontend Staging Area (`frontend/src/features/bills/BatchDispatcherModal.jsx`):
   - Interactive Staging checklist modal allowing human veto toggling (approve / veto) for each item before dispatch.
   - Blast radius indicator showing isolated reserve containment (protecting Bank Foundation).
   - Real-time sequential execution tracker displaying status per item.
   - Wire launch trigger into `frontend/src/features/hud/MobileHUD.jsx` (on the Reserved Bills card).

## Exclusive Write Ownership
You exclusively own and may edit:
- `backend/app/models/batch_payment.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/common.py`
- `backend/app/api/v1/bills.py`
- `backend/app/services/paypal_client.py`
- `frontend/src/features/bills/BatchDispatcherModal.jsx`
- `frontend/src/features/hud/MobileHUD.jsx`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Completion Criteria
1. Full Batch Dispatcher implementation completed.
2. All tests in `tests/api/test_batch_dispatcher_e2e.py` pass 100%.
3. Existing test suite passes without regressions.
4. Write `handoff.md` in `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m4/handoff.md`.
5. Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).


## 2026-11-08T14:56:45Z
[Message] sender=28249f08-094c-49f2-824d-ac8a44bcc29f priority=MESSAGE_PRIORITY_HIGH
You are worker_m4, an instance of teamwork_worker.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m4/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m4/DISPATCH.md, /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md, and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md.
Follow all instructions in DISPATCH.md.
Implement M4: The Trinity Batch Dispatcher (BatchPaymentItem model, BatchDispatcherProposal schema, REST endpoints, live sandbox guard, frontend staging modal).
Run tests and verify.
Write handoff.md in your working directory and notify parent orchestrator (28249f08-094c-49f2-824d-ac8a44bcc29f).


## 2026-11-08T15:13:54Z
[Message] sender=28249f08-094c-49f2-824d-ac8a44bcc29f priority=MESSAGE_PRIORITY_HIGH
**Context**: Milestone 4 Status Check
**Content**: Heartbeat check: inspecting progress on The Trinity Batch Dispatcher. We observed backend/app/models/batch_payment.py has been created.
**Action**: Please update progress.md with your current step and let us know your status.
