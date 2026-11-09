# 5-Component Handoff Report: survey_spec_miner_2 (The Trinity Batch Dispatcher R2)

**Timestamp:** 2026-11-08T14:45:00Z  
**Agent:** `survey_spec_miner_2` (`teamwork_spec_miner`)  
**Assignment:** Survey and specify The Trinity Batch Dispatcher (R2: `BatchPaymentItem` SQLModel, `BatchDispatcherProposal` schema, REST endpoints, live PayPal Sandbox requirement & failure handling, frontend staging area interface).

---

## 1. Observation

1. **Task Requirements:**
   - In `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md` (lines 18-22):
     `"### R2. The Trinity Batch Dispatcher Implementation (docs/features.md)`
     `1. Backend: Implement BatchPaymentItem SQLModel database model, AI Coach BatchDispatcherProposal structured output schema, and REST endpoints (POST /api/v1/bills/batch-dispatcher/propose, POST /api/v1/bills/batch-dispatcher/execute, GET /api/v1/bills/batch-dispatcher/queue) enforcing vault/bills blast radius containment and idempotent sequential PayPal Payouts. Require live PayPal Sandbox credentials for batch payout execution and fail cleanly if offline or credentials are missing.`
     `2. Frontend: Implement a Staging Area interface allowing human veto toggling of queued payment items before dispatch, and displaying real-time execution status."`
2. **Authoritative Feature Specification:**
   - In `/home/aster42/projects/full-stack/FireWallet/docs/features.md`:
     - Lines 93-107 define `BatchPaymentItemDTO` and `BatchDispatcherProposal` Pydantic models.
     - Lines 114-140 define `BatchPaymentItemBase`, `BatchPaymentItem`, and `BatchPaymentItemRead` SQLModel classes.
     - Lines 145-150 define safety guardrails: Blast Radius Containment (isolated Vault/Bills only), Human-in-the-Loop Veto Power, Idempotent Execution, and Deterministic Balance Check.
     - Lines 157-159 define REST endpoints (`/propose`, `/execute`, `/queue`).
3. **Current Codebase State:**
   - In `backend/app/models/bill.py`: Only `BillBase`, `Bill`, and `BillRead` are defined. `BatchPaymentItem` does not exist yet.
   - In `backend/app/schemas/common.py`: Neither `BatchPaymentItemDTO` nor `BatchDispatcherProposal` is defined yet.
   - In `backend/app/api/v1/bills.py`: Only `GET /bills`, `POST /bills`, and `POST /bills/{bill_id}/pay` are implemented. No `/batch-dispatcher/*` endpoints exist.
   - In `backend/app/services/paypal_client.py`: Lines 81-86, 101-105, 115-118, 271-277, 308-314, and 319-325 fall back to `mock_sandbox_access_token` and `PAYOUT-MOCK-{batch_id[:8]}` when credentials are unconfigured or when offline. When executed in the sandbox via `backend/.venv/bin/python -c "import asyncio; from app.services.paypal_client import paypal_client; print(asyncio.run(paypal_client.get_access_token())[:15])"`, output was:
     `Network error connecting to PayPal OAuth: [Errno -3] Temporary failure in name resolution. Using simulated sandbox token.`
     `mock_sandbox_ac`
   - In `frontend/src/features/hud/MobileHUD.jsx`: Line 188 renders the Reserved Bills card displaying available bills funds, but has no button opening a batch dispatcher or staging interface.
   - In `frontend/src/shared/api.js`: No batch dispatcher API client methods exist.
4. **Current Test Suite:**
   - Running `backend/.venv/bin/pytest tests/` exited with code 0: `44 passed, 1 skipped in 4.67s`.

---

## 2. Logic Chain

1. **Step 1 (Model Specification):** `BatchPaymentItem` table (`batch_payment_items`) must be created following the Tripartite SQLModel pattern (`BatchPaymentItemBase`, `BatchPaymentItem(table=True)`, `BatchPaymentItemRead`). It must link optionally to `bills.id` and track statuses (`pending_approval`, `approved`, `vetoed`, `executing`, `paid`, `failed`). Re-exporting it in `app.models.__init__.py` ensures `init_db()` registers it automatically at app lifespan startup (based on Observation 2 & 3).
2. **Step 2 (Schema Specification):** `BatchDispatcherProposal` in `app.schemas.common` must strictly use integer minor units (`amount_minor: int`, `total_batch_amount_minor: int`, `vault_balance_minor: int`, `bills_balance_minor: int`) per the zero-float integer rule (Observation 2).
3. **Step 3 (Blast Radius Containment):** The batch dispatcher must only debit `bills` or `vault` buckets. In `POST /execute`, any request specifying `source_bucket="bank"` or where `total_approved_amount > available_isolated_reserve` must immediately fail with HTTP 400 Bad Request, preserving Bank Foundation inviolability (Observation 1 & 2).
4. **Step 4 (Live PayPal Requirement):** Because `paypal_client.py` defaults to returning mock tokens and mock payouts during sandbox network errors, `POST /execute` must explicitly verify that `token != "mock_sandbox_access_token"` and that live sandbox credentials are configured and reachable. If offline or missing, it must return HTTP 503 Service Unavailable and record `status="failed"` on the items rather than silently simulating success (Observation 1 & 3).
5. **Step 5 (Sequential Idempotency):** The execution loop must iterate sequentially through approved items, pass unique `sender_batch_id` values, record ledger posted debits with unique `idempotency_key = f"batch_payout:{item.id}"`, and update `Bill.status = "paid"` if linked (Observation 1 & 2).
6. **Step 6 (Frontend Staging Area):** A dedicated `BatchDispatcherModal.jsx` component must provide an interactive checklist with individual approve/veto toggles, blast radius indicator cards, and a real-time sequential execution tracker. It can be launched directly from the Reserved Bills card on the Mobile HUD (Observation 1, 2, & 3).

---

## 3. Caveats

- **Network Sandboxing:** In the current test environment, outbound internet connectivity to `api-m.sandbox.paypal.com` is disabled by the execution sandbox (yielding DNS name resolution failure). Automated test suites must mock HTTP responses for `POST /v1/payments/payouts` to verify the success path while directly verifying that live credential requirements correctly reject mock access tokens with HTTP 503 when live connectivity is missing.
- **Alternative Interpretation on Staging Route:** `docs/workflows.md` mentions a URL route `/bills/staging`. In a Single Page Application without react-router, modal state in `App.jsx` triggered from the HUD / Coach action card provides identical staging functionality while maintaining compatibility with the existing view model (`hud` vs `deep-ledger`).

---

## 4. Conclusion

The Trinity Batch Dispatcher (R2) specification has been completely mined, cross-referenced, and documented.
All interface contracts, data models, schemas, endpoint behaviors, invariant protections, live credential checks, and frontend staging requirements are detailed in:
`/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/report.md`.

The implementation team can immediately execute against this specification by adding:
1. `backend/app/models/batch_payment.py`
2. `backend/app/schemas/common.py` (batch schemas)
3. `backend/app/api/v1/bills.py` (`/batch-dispatcher/*` endpoints)
4. `frontend/src/features/bills/BatchDispatcherModal.jsx` & `frontend/src/shared/api.js`
5. `tests/api/test_batch_dispatcher.py`

---

## 5. Verification Method

1. **Inspect Documentation Report:**
   Read `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/report.md` to verify all feature contracts, tables, and edge cases.
2. **Verify Baseline Test Suite:**
   Run:
   ```bash
   backend/.venv/bin/pytest tests/
   ```
   Confirm all 44 unit and API tests pass without regression.
3. **Verify Database Table Registration Mechanism:**
   Inspect `backend/app/database.py` line 80-84 and verify `init_db()` calls `SQLModel.metadata.create_all` using models registered in `app.models`.
4. **Verify PayPal Client Offline Behavior:**
   Run:
   ```bash
   backend/.venv/bin/python -c "import asyncio; from app.services.paypal_client import paypal_client; print(asyncio.run(paypal_client.get_access_token()))"
   ```
   Confirm it returns `mock_sandbox_access_token` under offline network sandboxing, confirming the exact condition that `POST /bills/batch-dispatcher/execute` must detect and intercept.
