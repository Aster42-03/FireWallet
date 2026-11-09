# Project: FireWallet Phase 5 & Trinity Batch Dispatcher

## Architecture
FireWallet is a full-stack financial firewall and autonomous budget governor.
- **Backend**: FastAPI + SQLModel + SQLite/PostgreSQL, double-entry zero-sum ledger (`LedgerEngine`), multi-agent AI system (Intent Parser, Coach, Policy Gatekeeper), PayPal SDK / REST integration (Orders v2 & Payouts).
- **Frontend**: React (Vite) + Tailwind CSS single-page HUD (`MobileHUD`), modals (`QuickIntentModal`, `EscapeWindowModal`, `BucketConfigModal`, `BatchDispatcherModal`, `CoachDrawer`), real-time reactive state (`shared/api.js`).
- **Core Guardrails**:
  - Zero-Float integer minor units (all currency values in integer cents).
  - Bank Foundation inviolability (cannot be directly spent; protected from blast radius).
  - Locked Savings Vault isolation (locked for long-term savings; only opened for verified life/medical emergencies).
  - Double-Entry balanced rebalancing (`-Bank / +Bucket = $0.00`).
  - Idempotent payment execution with sequential audit records.

## Code Layout
- Backend Models: `backend/app/models/` (`user.py`, `bill.py`, `batch_payment.py`, `ledger.py`, `__init__.py`)
- Backend Schemas: `backend/app/schemas/` (`common.py`)
- Backend Ledger: `backend/app/ledger/` (`engine.py`)
- Backend Agents: `backend/app/agents/` (`intent/`, `insights/coach.py`, `shared/llm_client.py`)
- Backend Endpoints: `backend/app/api/v1/` (`intents.py`, `bills.py`, `coach.py`, `overrides.py`, `partner.py`)
- Backend Services: `backend/app/services/` (`paypal_client.py`)
- Frontend Features: `frontend/src/features/` (`hud/`, `intent/`, `escape/`, `bills/`, `coach/`)
- Frontend Shared API: `frontend/src/shared/api.js`
- Documentation: `docs/` (`bugs.md`, `features.md`, `paypal_integration.md`, `architecture.md`, `agent_design.md`, `ROADMAP_PHASE5.md`)
- Tests: `tests/` (`unit/`, `api/`, `e2e/`)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Quick Intent Category Classification Bug Fix | Clean up scaffolding artifacts in parser/heuristics and frontend, align to core category taxonomy, log BUG-009 | M1 | ORIGINAL_REQUEST R4, survey_explorer_3 |
| 2 | Configurable Bills Allocation in Envelopes | Add Reserved Bills target input in BucketConfigModal and support double-entry rebalancing (-Bank / +Bills = $0) via policy update | M2 | ORIGINAL_REQUEST R3, survey_explorer_3 |
| 3 | Emergency Vault Allocation (BUG-008) | Verified emergencies route to `vault` with 0s cooldown bypass; cascade from bank if vault funds insufficient | M3 | ORIGINAL_REQUEST R1, survey_spec_miner_1 |
| 4 | AI Coach Autonomous Emergency Payment Execution | Coach executes transactions autonomously once payment details verified | M3 | ORIGINAL_REQUEST R1, survey_spec_miner_1 |
| 5 | Accountability Partner Token Generation & Public Endpoints | Generate 256-bit token on override creation, return in API, log to console, expose /partner/approve endpoints | M3 | ORIGINAL_REQUEST R1, survey_spec_miner_1 |
| 6 | Accountability Partner Dual-Flow Escape Window | Partner approval gives 0s cooldown & 0 chars; timeout fallback enforces 200 chars & 180s timer; dispatch outcome alerts | M3 | ORIGINAL_REQUEST R1, survey_spec_miner_1 |
| 7 | Model Branding Neutrality | Verify zero vendor/model branding appears anywhere in frontend UI | M3 | ORIGINAL_REQUEST R1, survey_spec_miner_1 |
| 8 | BatchPaymentItem SQLModel Model | Persistent table for queued batch payouts following Tripartite SQLModel pattern | M4 | ORIGINAL_REQUEST R2, survey_spec_miner_2 |
| 9 | BatchDispatcherProposal Structured Schema | AI Coach structured proposal schema with risk assessment protecting Bank Foundation | M4 | ORIGINAL_REQUEST R2, survey_spec_miner_2 |
| 10 | Batch Dispatcher REST Endpoints | /propose, /execute, and /queue endpoints enforcing Vault/Bills blast radius containment and sequential PayPal Payouts | M4 | ORIGINAL_REQUEST R2, survey_spec_miner_2 |
| 11 | Live PayPal Sandbox Requirement for Batch Execution | Intercept offline/mock tokens on batch execution and return HTTP 503 if credentials unconfigured or offline | M4 | ORIGINAL_REQUEST R2, survey_spec_miner_2 |
| 12 | Frontend Batch Dispatcher Staging Area | Human veto toggling interface for queued items and real-time execution status display | M4 | ORIGINAL_REQUEST R2, survey_spec_miner_2 |
| 13 | Real-Time PayPal Account Routing Documentation | Identify and document payee/destination resolution across Orders v2, double-entry ledger, disbursements, and Payouts | M5 | ORIGINAL_REQUEST R5, survey_explorer_3 |
| 14 | Phase 5 Roadmap Update and Renaming | Document Phase 4 completion and Phase 5 features in docs/ROADMAP_PHASE5.md | M5 | ORIGINAL_REQUEST R6, survey_explorer_3 |
| 15 | E2E Testing Suite & Regression Gate | Comprehensive opaque-box and integration test coverage across all new endpoints and flows, passing 100% | M6 | ORIGINAL_REQUEST Verification |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Quick Intent Bug Fix & Scaffolding Cleanup (R4) | Fix parser/heuristics category collision, clean scaffolding artifacts, log BUG-009 | none | DONE |
| M2 | Configurable Bills Envelope & Rebalancing (R3) | BucketConfigModal Reserved Bills field, BudgetPolicy bills_monthly_amount, double-entry rebalancing | none | DONE |
| M3 | Phase 5 Emergency Vault & Partner Dual-Flow (R1) | Emergency Vault spend & cascade (BUG-008), coach autonomous execution, partner approval dual-flow & tokens, branding check | M1, M2 | DONE |
| M4 | The Trinity Batch Dispatcher (R2) | BatchPaymentItem model, BatchDispatcherProposal schema, REST endpoints, live sandbox guard, frontend staging modal | M2 | DONE |
| M5 | PayPal Routing Documentation & Roadmap (R5, R6) | Update docs/paypal_integration.md, docs/architecture.md, docs/agent_design.md, create docs/ROADMAP_PHASE5.md | none | DONE |
| M6 | Final Milestone: 100% E2E Test Suite & Hardening | Full regression pass across pytest tests/, integration tests for all new endpoints | M1, M2, M3, M4, M5 | DONE |

## Interface Contracts

### M1 (Quick Intent) ↔ System
- Canonical Category Taxonomy: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out` (or `dining_out`), `emergency`.
- Removed Scaffolding Labels: `medical_emergency` -> `emergency`, `savings_violation` -> `emergency` or proper category.
- Parser heuristic in `llm_client.py`: `"food"` token removed from groceries to allow `"eating_out"` classification.

### M2 (Bills Allocation) ↔ Ledger Engine
- `BudgetPolicyBase`: add `bills_monthly_amount: Optional[int] = Field(default=120000, ge=0)`.
- `PolicyUpdate`: add `bills_monthly_amount: Optional[int] = None`.
- `sync_and_allocate_buckets`: `target_bills = policy.bills_monthly_amount if policy.bills_monthly_amount is not None else ...`
- Transfer semantics: `diff = target_bills - current_bills_posted`; if diff != 0: `record_double_entry_transfer(from_bucket="bank", to_bucket="bills", amount=diff)` maintaining `-Bank / +Bills = $0.00`.

### M3 (Phase 5 Emergency Vault & Partner Dual-Flow) ↔ API & Ledger
- `LedgerEngine.can_spend(..., is_emergency: bool = False)`: if `source_kind == "vault"`: allowed if `is_emergency=True`.
- Intent submission: if emergency, `recommended_bucket = "vault"`.
- Spend execution: draw from `vault`; if vault available < amount, cascade remainder from `bank` via balanced double-entry transfer `emergency_vault_draw`.
- Partner token: 256-bit URL-safe token stored as SHA-256 hash in `partner_approvals`. Returned in `OverrideResponse.partner_token`.
- Partner decision routes: `GET /api/v1/partner/approve/{token}`, `POST /api/v1/partner/approve/{token}/decision`.
- Instant unlock: sets `Override.status = "approved"`, `Override.ready_at = now`, 0s cooldown, 0 confession chars.
- Fallback: 200 chars confession + 180s countdown timer.
- Outcome alert: logged to stdout/logger `[PARTNER OUTCOME ALERT] Override {id} resolved: {outcome}`.

### M4 (The Trinity Batch Dispatcher) ↔ Payouts & Bills
- Database Model: `BatchPaymentItem` (table `batch_payment_items`, fields `id`, `user_id`, `bill_id`, `recipient_name`, `payee_email`, `amount_minor`, `currency`, `source_bucket`, `status`, `paypal_payout_item_id`, `created_at`, `updated_at`).
- Schemas: `BatchPaymentItemDTO`, `BatchDispatcherProposal` (with `risk_assessment`).
- Blast Radius: `source_bucket` restricted to `vault` or `bills`. Any attempt to spend from `bank` returns 400.
- Live PayPal Sandbox Requirement: `token != "mock_sandbox_access_token"` verified; if mock, return 503 Service Unavailable.
- Endpoints: `POST /api/v1/bills/batch-dispatcher/propose`, `GET /api/v1/bills/batch-dispatcher/queue`, `POST /api/v1/bills/batch-dispatcher/execute`.
- Frontend: `BatchDispatcherModal.jsx` with approve/veto toggle for each item, blast radius indicator, and live progress state.
