# FireWallet Roadmap: Phase 5 & The Trinity Batch Dispatcher

This document details the transition from **Phase 4** to **Phase 5**, cataloging the completed architectural milestones, newly delivered capabilities, security guardrails, and verification results powering **FireWallet**.

Related Documents:
- **[paypal_integration.md](paypal_integration.md)**: Real-Time PayPal Account Routing Architecture (Orders v2, Payouts, Ledger Boundary)
- **[architecture.md](architecture.md)**: Split Monorepo & Monolithic Single-Call Architecture
- **[agent_design.md](agent_design.md)**: Monolithic Single-Call Agent & Deterministic Guardrails
- **[features.md](features.md)**: The Trinity Batch Dispatcher Specification
- **[bugs.md](bugs.md)**: Defect Registry (`BUG-008`, `BUG-009`)
- **[TRINITY_RULES.md](TRINITY_RULES.md)**: Mathematical Invariants for Bank, Daily, Freedom, Vault, and Bills

---

## Roadmap Overview & Phase Status

| Phase | Core Objective | Key Deliverables | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Foundation & Core Rules | Triple-envelope engine (Bank, Daily, Freedom), zero-float integer cents, can_spend policy | **COMPLETED** |
| **Phase 2** | PayPal Sandbox & Webhooks | Orders v2 checkout, Payouts for bills, webhook reconciliation, idempotency | **COMPLETED** |
| **Phase 3** | Multi-Surface UI & Analytics | Mobile HUD, Foundational AG Grid Deep Ledger, Groq monolithic agent, RAG short tags | **COMPLETED** |
| **Phase 4** | Live Balance Sync & Configurable Envelopes | Reporting Balances API, 1-tap balance sync, envelope policy sliders, BUG-007 resolution | **COMPLETED** |
| **Phase 5** | Autonomous Execution, Partner Escape & Batch Dispatcher | Emergency Vault bypass (BUG-008), Partner dual-flow escape, Trinity Batch Dispatcher, Bills config, BUG-009 | **COMPLETED** |
| **v2.0+** | Post-Hackathon Extensions | Predictive cash flow smoothing, multi-currency localization, multi-sig escrow | **PLANNED** |

---

## 1. Phase 4 Retrospective: Completed Capabilities

Phase 4 hardened FireWallet's foundation, delivering real-time balance reconciliation and envelope configurability:

1. **Live PayPal Account Balance Detection**:
   - Integrated PayPal Reporting Balances API (`GET /v1/reporting/balances`), returning live available and total balances tagged with provenance (`source: "live" | "simulated"`).
2. **Zero-Sum 1-Tap Balance Sync**:
   - `POST /api/v1/paypal/sync-balance` compares external PayPal available cash with the internal bucket sum (`Bank + Daily + Freedom + Vault + Bills`).
   - If discrepancies exist (external deposits/adjustments), the system executes a balanced double-entry inflow into Bank Foundation (`+Bank = delta`), preserving total mathematical equality across internal envelopes and external balance.
3. **Configurable Envelopes & Sliders**:
   - Added user policy configuration via `PUT /api/v1/me/policy` and `frontend/src/features/hud/BucketConfigModal.jsx`.
   - Supported configurable Daily Living allowance ($/day), Freedom envelope allocation ($/month), Vault skim rate (bps), override cooldown timers, and minimum confession character lengths.
4. **Model Branding Neutrality**:
   - Audited the entire frontend UI to eliminate all third-party model and vendor branding (e.g., Groq, Llama, OpenAI, Gemini), presenting a cohesive, unbranded "AI Financial Coach" persona.
5. **Analytical Chips Diversity (`BUG-007`)**:
   - Resolved repetitive heuristic responses on HUD analytical chips, ensuring dynamic LLM generation across distinct diagnostic prompts.

---

## 2. Phase 5 Implementation Details

Phase 5 introduces autonomous emergency payment execution, social accountability partner escalation, agentic batch payout dispatching, and envelope configuration parity.

### 2.1 Emergency Vault Allocation & Autonomous Payment Execution (`BUG-008`)
- **Problem Solved**: Genuine medical, vehicular, or life-safety emergencies were previously blocked by standard friction timers or misrouted to discretionary envelopes.
- **Auto-Routing to Vault**: When an intent is verified as a genuine emergency (`is_genuine_emergency() = True`), the engine auto-routes the intent to the `vault` bucket with a **0s cooldown bypass**.
- **Cascading Bank Draw**: If the Vault balance is insufficient to cover the emergency amount, the engine executes an atomic cascading draw: allocating all available Vault funds and drawing the remainder from `bank` via a balanced double-entry transfer (`emergency_vault_draw`).
- **AI Coach Autonomous Execution**: Once payment details (recipient, amount, necessity) are verified, the AI Coach is empowered to execute the transaction autonomously via `POST /api/v1/coach/action` (`auto_capture_demo=True` or direct PayPal order generation), settling the emergency without artificial friction delays.

### 2.2 Accountability Partner Dual-Flow Escape Window
- **Single-Use Cryptographic Token**:
  - When an override is created for a user with a linked partner (`partner_required_for_bank = True`), the backend generates a secure 256-bit URL-safe token.
  - The token is stored as a SHA-256 hash in `partner_approvals` and returned via API response (`OverrideResponse.partner_token`) for easy testing and display in UI / server logs.
- **Dual-Flow Branching**:
  - **Branch A (Partner Approves)**: If the partner approves via public endpoints (`POST /api/v1/partner/approve/{token}/decision` with `action="approved"`), the spend is unlocked **immediately** with **0s cooldown** and **0 confession characters** required.
  - **Branch B (Partner Timeout Fallback)**: If the partner does not approve before the configured time window expires, the system falls back to strict friction gates: enforcing a **200-character reflective confession** and a **180-second countdown timer**.
- **Partner Public Endpoints**:
  - `GET /api/v1/partner/approve/{token}`: Public review screen displaying spend amount, merchant, and reason.
  - `POST /api/v1/partner/approve/{token}/decision`: Partner submits approval or denial.
- **Outcome Alert Dispatch**:
  - Regardless of the branch taken, upon spend settlement or cancellation, an automated outcome alert is dispatched and logged: `[PARTNER OUTCOME ALERT] Override {id} resolved: {outcome}`.

### 2.3 The Trinity Batch Dispatcher
- **Architecture**: Bridges AI Coach bill obligation analysis with autonomous sequential payout execution across PayPal REST APIs.
- **Tripartite SQLModel Database Model**:
  - `BatchPaymentItem` table persists queued batch items (`id`, `user_id`, `bill_id`, `recipient_name`, `payee_email`, `amount_minor`, `currency`, `source_bucket`, `status`, `paypal_payout_item_id`).
- **Structured Proposal Schema**:
  - AI Coach produces `BatchDispatcherProposal` adhering to strict Pydantic v2 schemas (`coach_message`, `total_batch_amount_minor`, `items: List[BatchPaymentItemDTO]`, `risk_assessment`).
  - The risk assessment explicitly verifies that Bank Foundation and emergency reserves remain untouched.
- **REST Endpoints**:
  - `POST /api/v1/bills/batch-dispatcher/propose`: Analyzes upcoming obligations and returns structured batch proposals.
  - `GET /api/v1/bills/batch-dispatcher/queue`: Fetches active staged queue items and execution history.
  - `POST /api/v1/bills/batch-dispatcher/execute`: Takes approved item IDs and sequentially executes PayPal Payouts.
- **Blast Radius Containment**:
  - Payout funds are strictly drawn from isolated `bills` or `vault` buckets. Any attempt to draw batch payouts from `bank` is rejected with HTTP 400.
- **Live PayPal Sandbox Guard**:
  - Execution strictly requires live PayPal Sandbox credentials (`access_token != "mock_sandbox_access_token"`).
  - If offline or credentials are missing, the endpoint fails cleanly with HTTP 503 (`Service Unavailable: Live PayPal Sandbox credentials required`).
- **Frontend Staging Area (`BatchDispatcherModal.jsx`)**:
  - Human-in-the-loop interface allowing user veto toggling of individual items before dispatch.
  - Displays real-time sequential execution status, recipient emails, and payout batch IDs.

### 2.4 Configurable Bills Allocation in Envelope Settings (`BucketConfigModal.jsx`)
- **Frontend Input**:
  - Added a dedicated input field for Reserved Bills ($/month) in `frontend/src/features/hud/BucketConfigModal.jsx`.
  - Ingests `policy.bills_monthly_amount` and converts between major USD and integer cents.
- **Double-Entry Rebalancing**:
  - Backend models (`BudgetPolicyBase`, `BudgetPolicyUpdate`, `PolicyUpdate`) support `bills_monthly_amount`.
  - In `LedgerEngine.sync_and_allocate_buckets`: adjusting the bills allocation computes the delta and executes paired double-entry transfers between Bank Foundation and Reserved Bills:
    - Inflow: `-Bank / +Bills = $0.00` (earmarking contractual obligations from bank).
    - Outflow / Return: `+Bank / -Bills = $0.00` (returning excess reserves to bank).
  - Preserves zero external float and maintains exact bucket sum equality with external PayPal balances.

### 2.5 Quick Intent Category Identification Bug & Scaffolding Cleanup (`BUG-009`)
- **Bug Resolution**:
  - Logged `BUG-009` in `docs/bugs.md`.
  - Removed lingering development scaffolding artifacts across parser heuristics (`llm_client.py`), category taxonomies (`parser.py`), and frontend components (`QuickIntentModal.jsx`).
  - Removed raw `"food"` keyword collision from `groceries` token list so dining/takeout queries correctly classify as `eating_out`.
  - Standardized all emergency types to canonical `emergency` (eliminating `medical_emergency` and `savings_violation` scaffolding strings).
- **Canonical Core Category Taxonomy**:
  1. `groceries` (Daily Living)
  2. `transit` (Daily Living)
  3. `utilities` (Reserved Bills)
  4. `entertainment` (Freedom Envelope)
  5. `gifts` (Freedom Envelope)
  6. `eating_out` / `dining_out` (Freedom Envelope)
  7. `emergency` (Vault / Emergency Reserve)

### 2.6 Real-Time PayPal Account Routing Architecture
- Identified and comprehensively documented payee and destination account determination across all money flows in `docs/paypal_integration.md`:
  - **Orders v2 Buyer Checkouts**: Default payee resolution to the developer merchant account (`PAYPAL_CLIENT_ID` owner) when `payee` is omitted.
  - **Internal Envelope Transfers**: Zero external float; purely on-ledger database records via `LedgerEngine.record_double_entry_transfer`.
  - **Emergency Disbursements**: Direct draw from Vault (and cascading Bank) via Orders v2 capture or Payouts directly to provider/recipient emails.
  - **Payouts API Routing**: Explicitly routes outbound funds via `items[0].receiver` to target emails (`PAYPAL_VAULT_RECEIVER_EMAIL`, `bill.payee_email`, and batch item `payee_email`).
- Cross-referenced across `docs/architecture.md` and `docs/agent_design.md`.

---

## 3. Verification & Compliance Matrix

| Requirement | Acceptance Criteria | Test / Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **R1 (Phase 5 & BUG-008)** | Emergency routes to `vault` with 0s cooldown bypass; cascades to bank; Coach autonomous execution; Partner dual-flow escape window; 0 branding | `tests/unit/test_trinity_rules.py`<br/>`tests/unit/test_agent_and_rag.py`<br/>`tests/api/test_api_endpoints.py` | **VERIFIED** |
| **R2 (Batch Dispatcher)** | `BatchPaymentItem` persistence; `BatchDispatcherProposal` schema; `/propose`, `/execute`, `/queue` endpoints; live sandbox check; staging modal | `tests/api/` & model schemas;<br/>Live PayPal credentials check | **VERIFIED** |
| **R3 (Bills Envelope)** | `BucketConfigModal.jsx` input; policy persistence; double-entry rebalancing (`-Bank / +Bills = $0`); HUD balance update | `tests/api/test_paypal_balance_and_policy.py` (`test_configurable_envelopes_policy_reallocation`) | **VERIFIED** |
| **R4 (Quick Intent Fix)** | `BUG-009` logged; scaffolding removed; canonical 7 categories; `"food"` keyword disambiguated | `tests/unit/test_agent_and_rag.py` (`test_short_tag_distillation_examples`, `test_quick_intent_records_short_tags`) | **VERIFIED** |
| **R5 (PayPal Routing)** | Account routing documented in `docs/paypal_integration.md`, cross-referenced in `architecture.md` and `agent_design.md` | Document review & inspection against `paypal_client.py`, `intents.py`, `bills.py` | **VERIFIED** |
| **R6 (Roadmap Rename)** | Roadmap updated with Phase 4 retro & Phase 5 implementation details; finalized as `docs/ROADMAP_PHASE5.md` | Inspect `docs/ROADMAP_PHASE5.md` | **VERIFIED** |

---

## 4. Architectural Invariants Preserved in Phase 5

1. **Zero-Float Integer Minor Units**:
   - Every monetary calculation remains strictly in integer minor units (cents). Floating-point currency math is banned across all backend engines, models, and ledger entries.
2. **Double-Entry Zero-Sum Balance**:
   - Internal money movement across envelopes always pairs equal debits and credits (`-from + to = $0.00`). Total envelope balance strictly reconciles 1:1 with external PayPal balance.
3. **Bank Foundation Inviolability**:
   - Bank funds cannot be directly spent via standard checkouts. Raids require explicit Escape Window overrides with confession/cooldown friction or emergency cascade authorization.
4. **Locked Savings Vault Isolation**:
   - Vault funds are locked against discretionary spending. Only verified genuine life/medical/critical safety emergencies or explicit user-authorized bill batches may draw from Vault reserves.
5. **Human-in-the-Loop Veto Power**:
   - Autonomous batch disbursements cannot execute without explicit human review and staging area confirmation.
