# Investigation & Specification Report: The Trinity Batch Dispatcher (R2)

**Timestamp:** 2026-11-08T14:42:00Z  
**Agent:** `survey_spec_miner_2` (`teamwork_spec_miner`)  
**Mission Scope:** R2 — The Trinity Batch Dispatcher Implementation (`docs/features.md`, `ORIGINAL_REQUEST.md`)

---

## 1. Executive Summary

The **Trinity Batch Dispatcher** is an agentic financial workflow bridging AI Coach bill analysis with autonomous payout execution. It automates recurring contractual obligations (rent, utilities) from isolated Vault and Reserved Bills funds while enforcing two strict invariants:
1. **Blast Radius Containment:** Disbursements can *only* be drawn from isolated `bills` or `vault` reserves. The core emergency reserve and Bank Foundation are structurally insulated against autonomous modification.
2. **Human-in-the-Loop Veto Power:** The agent never dispatches payouts autonomously without explicit user confirmation in a Staging Area checklist where each item can be approved or vetoed.
3. **Live PayPal Sandbox Requirement & Clean Failure:** Execution strictly requires live PayPal Sandbox credentials and active connectivity, failing cleanly (HTTP 503/400) if offline or unconfigured, rather than masking failures with mock sandbox tokens.
4. **Sequential Idempotent Execution:** Payouts are executed sequentially with deterministic `sender_batch_id` idempotency keys, updating double-entry ledger entries and database states atomically.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Database Model | `BatchPaymentItem` SQLModel | Persists queued, approved, paid, and vetoed payment items adhering to the Tripartite SQLModel pattern and integer minor-unit rules. | Model attributes: `id`, `user_id`, `bill_id`, `title`, `amount_minor`, `category`, `status`, `recommended`, `recipient_email`, `paypal_payout_id`, `sender_batch_id`, `error_message`, `created_at`, `updated_at`, `paid_at`. | Persisted SQLite/PostgreSQL table `batch_payment_items` & Pydantic read models (`BatchPaymentItemRead`). | Validation error (422) if `amount_minor <= 0` or missing required fields. | `docs/features.md` §1.4 B, `docs/data_model.md` §Future Schema Extensions |
| 2 | Structured Schema | `BatchDispatcherProposal` | Structured Pydantic v2 output schema for AI Coach proposing staged bill disbursements from isolated reserves. | AI reasoning inputs: scheduled bills, available Vault/Bills balances, cash flow constraints. | JSON adhering to schema: `coach_message`, `total_batch_amount_minor`, `items` (`BatchPaymentItemDTO`), `risk_assessment`, `vault_balance_minor`, `bills_balance_minor`, `safe_to_execute`. | Pydantic validation error if types or minor-unit constraints fail. | `docs/features.md` §1.4 A, `docs/agent_design.md` §5, `docs/insights.md` §5 |
| 3 | REST API | `POST /api/v1/bills/batch-dispatcher/propose` | Generates a structured `BatchDispatcherProposal`, stages upcoming scheduled bills, and creates `BatchPaymentItem` records with status `pending_approval`. | `user: User = Depends(get_current_user)`, optional body `{ "force_refresh": bool }`. | HTTP 200 OK: `BatchDispatcherProposal` containing staged items with database UUIDs. | HTTP 401 if unauthenticated; HTTP 500 if database error. | `docs/features.md` §1.6, `ORIGINAL_REQUEST.md` R2.1 |
| 4 | REST API | `GET /api/v1/bills/batch-dispatcher/queue` | Queries active staged queue items and execution history for the authenticated user, including summary metrics. | `user: User = Depends(get_current_user)`, optional query param `status: Optional[str]`. | HTTP 200 OK: `{ "items": List[BatchPaymentItemRead], "total_pending_minor": int, "total_paid_minor": int, "isolated_bills_available_minor": int, "isolated_vault_available_minor": int }`. | HTTP 401 if unauthenticated. | `docs/features.md` §1.6, `ORIGINAL_REQUEST.md` R2.1 |
| 5 | REST API | `POST /api/v1/bills/batch-dispatcher/execute` | Validates blast radius invariants, verifies live PayPal Sandbox credentials, and executes sequential PayPal Payouts for approved item IDs. | `user: User = Depends(get_current_user)`, body `{ "approved_item_ids": List[UUID], "source_bucket": "bills" }`. | HTTP 200 OK: `BatchExecutionSummary` with execution status, count, total debited cents, item results, and remaining isolated balance. | HTTP 400 if empty items, invalid bucket, or insufficient isolated reserves; HTTP 503 if offline/missing PayPal credentials; HTTP 404 if item IDs not found. | `docs/features.md` §1.6, `ORIGINAL_REQUEST.md` R2.1 |
| 6 | Security / Policy | Blast Radius Containment | Restricts batch payout fund sources strictly to `bills` or `vault` buckets; prevents agentic modification of Bank Foundation. | Source bucket check (`source_bucket in ("bills", "vault")`) & available isolated balance check against total approved cents. | Enforces invariant; blocks execution if Bank Foundation is targeted or isolated funds are insufficient. | HTTP 400 Bad Request with invariant protection error message. | `docs/features.md` §1.5, `docs/TRINITY_RULES.md` §8 |
| 7 | Payment Gateway | Live PayPal Sandbox Enforcement | Requires valid, reachable PayPal Sandbox credentials for batch execution; disallows silent mock fallback. | `paypal_client.get_access_token()` verification: detects mock token (`mock_sandbox_access_token`) or network connection drop. | Permitted execution only with genuine PayPal Sandbox OAuth token. | HTTP 503 Service Unavailable with clean, descriptive error. | `ORIGINAL_REQUEST.md` R2.1, `backend/app/services/paypal_client.py` |
| 8 | Payment Gateway | Idempotent Sequential Payouts | Executes sequential outbound PayPal Payouts (`POST /v1/payments/payouts`) with deterministic `sender_batch_id` and atomic double-entry ledger settlement. | Per-item payout payload: `sender_batch_id`, receiver email, minor amount formatted to decimal `{dollars}.{cc}`, memo. | PayPal Payout Batch ID, item status updated to `paid`, `LedgerEntry` posted debit created. | Item marked `failed` with `error_message` on PayPal refusal; ledger untouched for failed item. | `docs/paypal_integration.md` §Future Agentic Flow, `backend/app/services/paypal_client.py` |
| 9 | Frontend UI | Staging Area Interface | Interactive interface for users to review proposed payouts, inspect risk assessment, toggle human veto on individual obligations, and authorize dispatch. | Staged queue items fetched from `/queue`, user toggle interactions, user click on "Authorize Dispatch". | Real-time status display showing item-by-item dispatch progress, success/failure badges, and live transaction IDs. | Displays informative warning banners on network error, offline PayPal sandbox, or insufficient isolated funds. | `docs/features.md` §1.2 & §1.3, `ORIGINAL_REQUEST.md` R2.2 |
| 10 | Frontend API | Client API Integration | Client fetch functions in `frontend/src/shared/api.js` for proposing, querying, and executing batch disbursements. | Parameters: `approved_item_ids`, `source_bucket`, `status`. | Typed JSON responses matching backend Pydantic schemas. | Propagates backend error details into user-facing toasts and modal banners. | `frontend/src/shared/api.js` |

---

## 3. Edge Cases & Observed / Expected Behavior

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|-----------------------------|
| 1 | Blast Radius Containment | User attempts to execute batch payouts exceeding available isolated balance in `bills` / `vault` (e.g. approved $1,500.00 when Bills bucket only has $1,200.00). | **HTTP 400 Bad Request**: Returns `"Reserve Protection Active: Insufficient isolated Vault/Bills funds ($1,200.00 available, $1,500.00 requested). Bank Foundation cannot be raided by Batch Dispatcher."` Bank Foundation remains 100% untouched. |
| 2 | Blast Radius Containment | Caller passes `source_bucket="bank"` in `POST /api/v1/bills/batch-dispatcher/execute`. | **HTTP 400 Bad Request**: Returns `"Batch Dispatcher is strictly restricted to isolated 'bills' or 'vault' reserves. Direct spend from 'bank' is forbidden."` |
| 3 | Live PayPal Sandbox Requirement | Environment variables `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` are unconfigured, placeholder, or system is offline (`Temporary failure in name resolution`). | **HTTP 503 Service Unavailable**: Returns clean error: `"Live PayPal Sandbox credentials and active network connection required for batch payout execution. System offline or sandbox credentials unconfigured."` No mock payouts are recorded. |
| 4 | Human Veto Power | User toggles off 2 of 3 staged bills in the Staging Area interface, then clicks "Authorize Dispatch". | Backend processes **only** the 1 approved item ID. The unapproved items remain `pending_approval` or are marked `vetoed`. Only the approved item is debited from ledger and paid via PayPal. |
| 5 | Empty Approved Array | User calls `POST /api/v1/bills/batch-dispatcher/execute` with `approved_item_ids: []`. | **HTTP 400 Bad Request**: Returns `"No items approved for execution."` |
| 6 | Idempotent Re-Execution | User double-clicks "Authorize Dispatch" or network retries an already `paid` batch item ID. | Execution skips already `paid` items, returns existing `paypal_payout_id`, and avoids duplicate PayPal API calls or double-debits on the ledger. |
| 7 | Cross-User Security | User A submits `approved_item_ids` belonging to User B. | **HTTP 404 Not Found** (or item filtered out): Items are scoped by `user_id == user.id`. Foreign items are never processed. |
| 8 | Partial Batch Failure | First item succeeds (PayPal returns 201), second item fails (e.g. PayPal rejects recipient email). | First item commits with status `paid` and ledger debit; second item commits with status `failed` and `error_message`. Execution summary returns `status="partial_failure"` with individual result details. |
| 9 | Zero or Negative Amount | Staged item has `amount_minor <= 0`. | Rejected during schema validation or creation with **HTTP 422 Unprocessable Entity** (`amount_minor must be > 0`). |
| 10 | Zero Scheduled Bills | User calls `POST /api/v1/bills/batch-dispatcher/propose` when no bills are scheduled (`status == "scheduled"`). | Returns `BatchDispatcherProposal` with empty items list, `total_batch_amount_minor = 0`, and coach message: `"No upcoming scheduled obligations found to stage at this time."` |

---

## 4. Deep-Dive Specification by Subsystem

### 4.1 Backend Database Model (`BatchPaymentItem`)

File target: `backend/app/models/batch_payment.py` (and re-exported in `backend/app/models/__init__.py`).

```python
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class BatchPaymentItemBase(SQLModel):
    title: str = Field(description="Name of the bill or obligation (e.g., 'Rent', 'Electric Bill')")
    amount_minor: int = Field(gt=0, description="Amount in integer minor units (cents)")
    category: str = Field(default="Bills", description="Category of the expense (e.g., 'Rent', 'Utilities')")
    status: str = Field(default="pending_approval", index=True, description="'pending_approval', 'approved', 'paid', 'vetoed', 'executing', 'failed'")
    recommended: bool = Field(default=True, description="True if AI coach recommends paying this batch item")
    recipient_email: Optional[str] = Field(default=None, description="PayPal recipient email for Payouts")
    paypal_payout_id: Optional[str] = Field(default=None, index=True, description="PayPal Payout item/batch identifier")
    sender_batch_id: Optional[str] = Field(default=None, index=True, description="Idempotent PayPal batch identifier")
    error_message: Optional[str] = Field(default=None, description="Failure reason if payout failed")

class BatchPaymentItem(BatchPaymentItemBase, table=True):
    __tablename__ = "batch_payment_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    bill_id: Optional[UUID] = Field(default=None, foreign_key="bills.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    paid_at: Optional[datetime] = Field(default=None, index=True)

class BatchPaymentItemRead(BatchPaymentItemBase):
    id: UUID
    user_id: UUID
    bill_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
```

### 4.2 AI Coach Structured Output Schema (`BatchDispatcherProposal`)

File target: `backend/app/schemas/common.py` (or `backend/app/schemas/batch_dispatcher.py`).

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class BatchPaymentItemDTO(BaseModel):
    id: Optional[UUID] = Field(default=None, description="Database UUID if item is already staged")
    bill_id: Optional[UUID] = Field(default=None, description="Linked bill ID if from scheduled bills")
    title: str = Field(description="Name of the bill or obligation, e.g., 'Apartment Rent'")
    amount_minor: int = Field(gt=0, description="Exact monetary amount in integer minor units (cents)")
    category: str = Field(default="Bills", description="Category of the expense, e.g., 'Rent', 'Utilities'")
    recommended: bool = Field(default=True, description="True if the AI strongly recommends paying this in current batch")
    recipient_email: Optional[str] = Field(default=None, description="PayPal recipient email")
    due_date: Optional[str] = Field(default=None, description="Due date string if applicable")

class BatchDispatcherProposal(BaseModel):
    coach_message: str = Field(description="Empathetic, clear explanation of the proposed batch payment plan.")
    total_batch_amount_minor: int = Field(description="Sum of all recommended batch items in integer minor units (cents)")
    items: List[BatchPaymentItemDTO] = Field(description="List of queued obligations for user review and veto.")
    risk_assessment: str = Field(description="Security note verifying that emergency and primary bank funds remain untouched.")
    vault_balance_minor: int = Field(default=0, description="Available balance in Vault (cents)")
    bills_balance_minor: int = Field(default=0, description="Available balance in Reserved Bills (cents)")
    safe_to_execute: bool = Field(default=True, description="True if isolated funds cover total batch")
```

### 4.3 REST Endpoints Specification

Location: `backend/app/api/v1/bills.py` (extending router with `/batch-dispatcher` sub-routes).

#### 1. `POST /api/v1/bills/batch-dispatcher/propose`
- **Request:** Optional JSON `{ "force_refresh": false }`.
- **Logic:**
  1. Authenticates user.
  2. Loads active scheduled bills (`status == 'scheduled'`) ordered by priority and due date.
  3. Queries available balances for `bills` and `vault` via `LedgerEngine.get_bucket_balances()`.
  4. Formulates `BatchDispatcherProposal` with risk assessment verifying Bank Foundation is untouched.
  5. For each proposed bill, inserts/updates `BatchPaymentItem` with status `pending_approval`.
  6. Returns proposal JSON including generated item UUIDs.
- **Response (200 OK):**
  ```json
  {
    "coach_message": "I've reviewed your upcoming contractual obligations. Staging 1 bill totaling $1,200.00 from your isolated Reserved Bills bucket.",
    "total_batch_amount_minor": 120000,
    "items": [
      {
        "id": "c1f72a9b-...",
        "bill_id": "8a2f1b4c-...",
        "title": "Apartment Rent",
        "amount_minor": 120000,
        "category": "Rent",
        "recommended": true,
        "recipient_email": "landlord@sandbox.paypal.com",
        "due_date": "2026-11-13"
      }
    ],
    "risk_assessment": "Isolated Reserved Bills ($1,200.00) completely covers this batch. Core Bank Foundation ($800.00) and Vault long-term savings ($200.00) remain 100% untouched.",
    "vault_balance_minor": 20000,
    "bills_balance_minor": 120000,
    "safe_to_execute": true
  }
  ```

#### 2. `GET /api/v1/bills/batch-dispatcher/queue`
- **Request:** Query parameter `status` (optional, e.g. `?status=pending_approval`).
- **Logic:**
  1. Queries `BatchPaymentItem` for authenticated user.
  2. Aggregates pending minor cents, paid minor cents, and current available isolated balances.
- **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "id": "c1f72a9b-...",
        "user_id": "...",
        "bill_id": "...",
        "title": "Apartment Rent",
        "amount_minor": 120000,
        "category": "Rent",
        "status": "pending_approval",
        "recommended": true,
        "recipient_email": "landlord@sandbox.paypal.com",
        "paypal_payout_id": null,
        "sender_batch_id": null,
        "error_message": null,
        "created_at": "2026-11-08T14:40:00Z",
        "updated_at": "2026-11-08T14:40:00Z",
        "paid_at": null
      }
    ],
    "total_pending_minor": 120000,
    "total_paid_minor": 0,
    "isolated_bills_available_minor": 120000,
    "isolated_vault_available_minor": 20000
  }
  ```

#### 3. `POST /api/v1/bills/batch-dispatcher/execute`
- **Request Body:**
  ```json
  {
    "approved_item_ids": ["c1f72a9b-..."],
    "source_bucket": "bills"
  }
  ```
- **Invariant & Guardrail Pipeline:**
  1. **User Authentication:** Enforces `user.id`.
  2. **Empty Check:** `approved_item_ids` must not be empty (HTTP 400).
  3. **Blast Radius Check:** `source_bucket` must be in `("bills", "vault")`. Direct target of `bank` is rejected with HTTP 400.
  4. **Reserve Sufficiency Check:** Queries `LedgerEngine.get_bucket_balances()`. Total approved minor amount must not exceed `balances[source_bucket]["available"]`. Violations fail with HTTP 400.
  5. **Live PayPal Sandbox Credentials Check:**
     - Must check `paypal_client.client_id` and `client_secret` (not empty and not dummy placeholder).
     - Calls `paypal_client.get_access_token()`. If token returns `"mock_sandbox_access_token"` or network error occurs, fails immediately with HTTP 503 (`"Live PayPal Sandbox connection required for batch payout execution; network offline or credentials invalid."`).
  6. **Sequential Execution Loop:**
     - For each approved item:
       - Skip if already `status == "paid"`.
       - Mark `status = "executing"`.
       - Generate `sender_batch_id = f"batch_{str(item.id).replace('-', '')[:20]}"`.
       - Call PayPal Payouts API (`POST /v1/payments/payouts`).
       - On success (HTTP 201):
         - Set `item.status = "paid"`, `item.paypal_payout_id = payout_batch_id`, `item.paid_at = utc_now()`.
         - Insert posted debit ledger entry (`entry_kind = "bill_payout"`, `amount = -amount_minor`, `idempotency_key = f"batch_payout:{item.id}"`).
         - If linked `bill_id`, update `Bill.status = "paid"`.
       - On failure:
         - Set `item.status = "failed"`, `item.error_message = error_str`.
  7. **Mark Vetoed Items:** Any items in queue for this user in `pending_approval` that were omitted from `approved_item_ids` can be marked `status = "vetoed"`.
  8. **Response (200 OK):**
     ```json
     {
       "status": "completed",
       "executed_count": 1,
       "failed_count": 0,
       "total_amount_minor": 120000,
       "results": [
         {
           "item_id": "c1f72a9b-...",
           "title": "Apartment Rent",
           "status": "paid",
           "paypal_payout_id": "PAYOUTS-BATCH-994821",
           "error_message": null
         }
       ],
       "remaining_isolated_balance_minor": 0,
       "message": "Batch payout of 1 item ($1,200.00) completed successfully via PayPal Sandbox."
     }
     ```

### 4.4 Live PayPal Sandbox Credential & Failure Handling

The requirement explicitly states:
> *"Require live PayPal Sandbox credentials for batch payout execution and fail cleanly if offline or credentials are missing."*

Currently, `backend/app/services/paypal_client.py` has fallback logic in lines 81-86, 101-105, 115-118, 271-277, 309-314, and 319-325 that silently generates `mock_sandbox_access_token` and `PAYOUT-MOCK-...` when credentials are unconfigured or offline.
For batch dispatcher execution:
1. `paypal_client` must expose a method or flag (e.g. `async def create_live_payout(...)` or `require_live=True` flag in `create_payout()`, or checking whether `token == "mock_sandbox_access_token"`).
2. If `token == "mock_sandbox_access_token"`, or if `httpx.RequestError` occurs, raise `RuntimeError("Live PayPal Sandbox credentials and active internet connection are required for batch payout execution.")`.
3. In the FastAPI endpoint, intercept this and return **HTTP 503 Service Unavailable** with detail:
   `"Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured."`
4. The batch items must transition to `failed` with this error message recorded in `error_message`, providing full transparent auditability to the user.

### 4.5 Frontend Staging Area Interface

File target: `frontend/src/features/bills/BatchDispatcherModal.jsx` (and integration into `MobileHUD.jsx` and `App.jsx`).

**Key UI Components:**
1. **Modal Header:**
   - Title: "The Trinity Batch Dispatcher"
   - Subtitle: "Agentic Bill Pay Staging & Human Veto Gate"
   - Close button (`X`).
2. **Blast Radius & Reserve Status Banner:**
   - Displays:
     - Reserved Bills available: `$1,200.00`
     - Vault Savings available: `$200.00`
     - Bank Foundation (Protected Remainder): `$800.00` with Lock icon and green badge: "Bank Foundation Untouched".
3. **AI Coach Proposal Card:**
   - Coach message explaining staged obligations.
   - Risk assessment alert confirming zero breach of core reserves.
   - "Refresh AI Staging" button with spinner.
4. **Interactive Staged Queue Checklist (Human Veto Power):**
   - Table / list of items.
   - Each row has:
     - Checkbox or Toggle Switch (Enabled = Approved, Disabled = Vetoed).
     - Title (e.g. "Apartment Rent"), category badge ("Rent"), recipient email ("landlord@sandbox.paypal.com").
     - Amount in dollars (`$1,200.00`).
     - AI Recommendation chip (`"Recommended"`).
     - Current status badge (`pending_approval`, `paid`, `vetoed`, `failed`, `executing`).
5. **Real-Time Execution Status Tracker:**
   - Progress bar showing step-by-step sequential progress (`Executing 1 of 2...`).
   - Live execution log showing PayPal Payout batch IDs and individual statuses.
   - Clear failure banner if PayPal Sandbox is offline or credentials missing.
6. **Footer Actions:**
   - Summary of approved total: `Total Approved: $1,200.00 (1 item)`.
   - "Authorize Batch Dispatch" button (emerald, disabled if 0 items approved or if total exceeds isolated balance).
   - "Cancel" button.

---

## 5. Codebase Mapping & Required Implementation Touchpoints

| File Path | Action | Description of Changes |
|-----------|--------|------------------------|
| `backend/app/models/batch_payment.py` | Create | Define `BatchPaymentItemBase`, `BatchPaymentItem` (table `batch_payment_items`), and `BatchPaymentItemRead`. |
| `backend/app/models/__init__.py` | Modify | Re-export `BatchPaymentItemBase`, `BatchPaymentItem`, `BatchPaymentItemRead` for automatic table registration by `init_db()`. |
| `backend/app/schemas/common.py` | Modify | Define `BatchPaymentItemDTO`, `BatchDispatcherProposal`, `BatchExecuteRequest`, `BatchExecutionItemResult`, and `BatchExecutionSummary`. |
| `backend/app/api/v1/bills.py` | Modify | Implement `POST /bills/batch-dispatcher/propose`, `GET /bills/batch-dispatcher/queue`, and `POST /bills/batch-dispatcher/execute` with blast radius containment and PayPal sandbox checks. |
| `backend/app/services/paypal_client.py` | Modify | Provide `require_live=True` option or `has_live_credentials()` helper so Batch Dispatcher can reject mock fallbacks cleanly. |
| `frontend/src/shared/api.js` | Modify | Add `fetchBatchQueue()`, `proposeBatch()`, and `executeBatch()` client functions. |
| `frontend/src/features/bills/BatchDispatcherModal.jsx` | Create | Implement Staging Area interface with human veto checklist, blast radius indicators, and real-time execution tracker. |
| `frontend/src/features/hud/MobileHUD.jsx` | Modify | Add trigger button ("Batch Dispatcher" / "Staging Area") on the Reserved Bills card. |
| `frontend/src/App.jsx` | Modify | Integrate `BatchDispatcherModal` state and handlers. |
| `tests/api/test_batch_dispatcher.py` | Create | Automated unit & API tests covering proposal generation, blast radius containment (400), PayPal sandbox offline requirement (503), sequential payout execution, and human veto power. |

---

## 6. Verification and Test Inventory

### 6.1 Baseline Verification
- Current test suite status: 45 collected, 44 passed, 1 skipped in 4.67s (`pytest tests/`).
- Database schema initialization: `init_db()` in `backend/app/database.py` automatically registers all models imported in `app.models` via `SQLModel.metadata.create_all`.

### 6.2 Test Matrix for The Trinity Batch Dispatcher

1. **`test_batch_payment_item_model_creation`**:
   - Asserts creation of `BatchPaymentItem` with valid fields, positive `amount_minor`, and default status `pending_approval`.
   - Asserts validation fails when `amount_minor <= 0`.
2. **`test_batch_dispatcher_propose_endpoint`**:
   - Seeds a scheduled bill (`Apartment Rent`, $1,200.00).
   - Calls `POST /api/v1/bills/batch-dispatcher/propose`.
   - Asserts response 200, schema adheres to `BatchDispatcherProposal`, and staged item exists in `batch_payment_items` table.
3. **`test_batch_dispatcher_queue_endpoint`**:
   - Calls `GET /api/v1/bills/batch-dispatcher/queue`.
   - Asserts list of staged items, verifies summary calculations (`total_pending_minor`).
4. **`test_batch_dispatcher_execute_blast_radius_containment`**:
   - Submits approved item exceeding available isolated bills balance.
   - Asserts response 400 Bad Request with invariant protection error.
   - Asserts Bank Foundation balance is 100% untouched.
5. **`test_batch_dispatcher_execute_live_paypal_required_offline_failure`**:
   - Simulates offline/unconfigured PayPal credentials.
   - Calls `POST /api/v1/bills/batch-dispatcher/execute`.
   - Asserts response 503 Service Unavailable, items marked `failed` with clear error message, and no fake payout recorded.
6. **`test_batch_dispatcher_execute_sequential_success`**:
   - Mocks live PayPal payout success response.
   - Calls `POST /api/v1/bills/batch-dispatcher/execute`.
   - Asserts response 200 OK, item status `paid`, `paypal_payout_id` populated, and double-entry posted debit recorded in ledger.
7. **`test_batch_dispatcher_human_veto`**:
   - Stages 2 bills, approves only 1 item in `approved_item_ids`.
   - Asserts only the approved item is executed, while the unapproved item remains unexecuted / marked vetoed.
8. **`test_batch_dispatcher_idempotency`**:
   - Re-submits an already-paid item ID.
   - Asserts execution is idempotent and does not debit ledger twice.
