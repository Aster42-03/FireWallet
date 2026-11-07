# FireWallet: Comprehensive Implementation Roadmap & Next Phases Plan

**Source of Truth:** Post-Phase 2 Milestone  
**Current Milestone Completed:** Phase 1 (Core Environment, Trinity Accounting Invariants, 100% Green Tests) & Phase 2 (Bank-Kept Double-Entry Ledger, Enterprise AG Grid Workbench v32, Alembic Migration Infrastructure).  
**Target Submission / Production Ready:** Complete Hackathon & Production Deployment Requirements.

---

## 1. Executive Summary & Current Milestone Status

FireWallet operates on the **Trinity Architecture**: money is segregated deterministically into 5 strict buckets (**Bank Foundation**, **Daily Living**, **Freedom Envelope**, **Locked Savings Vault**, and **Reserved Bills**), guarded by an **AI Financial Firewall** and analyzed by an **Advanced Reasoning Coach**.

| Phase | Milestone Description | Status | Key Deliverables Completed |
|---|---|---|---|
| **Phase 1** | **Core Engine & Accounting Foundation** | **DONE** | Zero-float minor unit math, 5 Trinity buckets, rule evaluation engine, UV packaging, 23 unit/API tests passing with 0 warnings. |
| **Phase 2** | **Double-Entry Ledger & AG Grid Workbench** | **DONE** | Bank-kept double-entry ledger (`transfer_id` pairing, $\sum \text{legs} = 0$), running balances, AG Grid v32 dark quartz grid, Alembic SQLite/PostgreSQL migrations. |
| **Phase 3** | **Unified Monolithic Agent, RAG Short-Tags, 1-Tap Actions & Hardened Webhooks** | **DONE** | Single-call Groq `llama-3.3-70b-versatile` (`gpt-4o-mini` fallback) returning `CoachDecision` + 1-tap `ActionCard`, persistent 2–5 word `short_tag` RAG memory (`groceries`, `takeout`, `gift for family`), dollar words parser, rich Markdown rendering, 0-second emergency override, status-tracked atomic PayPal webhooks (`0003_phase3_rag_status`), `BUG-001` through `BUG-005` resolved, 39/39 unit/API tests passing with 0 warnings. |
| **Phase 4** | **PayPal Sandbox & Automated Lifecycles** | **PLANNED** | PayPal Orders (v2), Captures, Payouts (Vault skim), Morning Rollover cron, Payday worker. |
| **Phase 5** | **Accountability Partner & Escape Window Hardening** | **PLANNED** | Cryptographic partner approval link, 200-char confession friction, 180s escape cooldown countdown timer, alert dispatch. |
| **Phase 6** | **Production Cloud & Devpost Packaging** | **PLANNED** | Render deployment verification (`render.yaml`), Postman collection test run, APIMatic OpenAPI sync, sub-3-minute video checklist. |

---

## 2. Phase 3: Unified Monolithic Agent & Hardened Webhook Engine (Completed)

### 2.1. Architectural Principle: Monolithic Agent with Structured Outputs
In a hackathon MVP, multi-agent frameworks (CrewAI, LangGraph agent chatter) multiply roundtrip latency by 3x–6x and introduce debugging fragility during live video demonstrations. 

Instead, Phase 3 establishes a clean division of labor:
1. **The AI Agent (The Brain & Voice)**:
   - In a **single, ultra-fast LLM call** (powered by Groq `llama-3.3-70b-versatile` or OpenAI `gpt-4o-mini`), the unified system prompt evaluates the user's spending request or analytical question against the current Trinity telemetry context.
   - Outputs a typed Pydantic schema (`CoachDecision`) containing both the conversational text for the chat bubble AND the structured decision metadata with a pre-configured 1-tap action card (`action_card`).
2. **FastAPI & LedgerEngine (The Guardrails & Execution Layer)**:
   - The AI never moves money or accesses database keys directly.
   - The Python backend validates the decision tag against deterministic Trinity invariants, previewing or executing zero-sum transfers atomically in SQLite / PostgreSQL upon user 1-tap confirmation.

### 2.2. Key Workstreams Delivered

#### Workstream 1: Bug Resolution (`BUG-001: Chat & Response Doubling`)
- **Resolved**: Added synchronous `isSendingRef` lock and `lastProcessedInitialRef` guard inside `CoachDrawer.jsx`.
- Implemented `onClearInitialQuery` callback in `App.jsx` to clear initial query state immediately upon consumption.
- Attached `AbortController` (`signal`) to `sendCoachMessage` to cancel stale in-flight requests cleanly on unmount.

#### Workstream 2: Unified Monolithic Agent (`CoachDecision` & 1-Tap Action Card)
- Defined typed `ActionCard` and `CoachDecision` Pydantic models in `backend/app/schemas/common.py`.
- Consolidated reasoning into a single LLM call with `json_mode=True`.
- Added explicit Groq `llama-3.3-70b-versatile` support with graceful fallback cascade to `gpt-4o-mini` and deterministic mock heuristics.
- Pre-filled 1-tap action card buttons rendered in both Quick Intent modal and Coach chat drawer.

#### Workstream 3: Emergency Zero-Cooldown Override Rule
- Implemented `is_genuine_emergency()` NLP verification in `backend/app/agents/rag.py`.
- If an override confession represents a valid medical, safety, or critical infrastructure emergency (e.g. emergency room, broken pipe, stranded vehicle), the system assigns `cooldown_seconds = 0` and auto-approves the transfer from `bank` immediately without waiting 180 seconds.
- Discretionary or celebration splurges (e.g. "celebrating promotion at steakhouse") preserve the full 200-char confession friction and 180s reflection timer.

#### Workstream 4: Bulletproof PayPal Webhook & Ledger Settlement Router
- Extended `PayPalWebhookEvent` model with indexed `status: str = "pending"` and `error_message: Optional[str] = None`.
- Executed Alembic migration `0003_phase3_rag_status`.
- Enforced strict requirements on `/api/v1/webhooks/paypal`:
  1. **Raw Body Preservation**: Read `raw_body = await request.body()` before JSON parsing.
  2. **Signature Verification**: Verified via `paypal_client.verify_webhook_signature()`; returns HTTP 400 if invalid.
  3. **Robust Idempotency with Status Tracking**: Checks `paypal_webhook_events` by `event_id`. Ignores duplicates only if status is `"processed"`. Pending or failed events are safely retried.
  4. **Atomic Transactions & Rollback**: Wrapped database logging and ledger settlement (`LedgerEngine.settle_hold`) inside `try...except`. On failure, rolls back session, marks status `"failed"`, and returns HTTP 500 so PayPal retries. On success, sets status `"processed"` and commits atomically.

#### Workstream 5: Short-Tag Distillation & RAG Context Memory
- Built `distill_short_tag()` to condense user prompts into concise 2–5 word tags (e.g. `groceries`, `takeout`, `gift for family`, `movie ticket`, `vault sweep`).
- Persisted `short_tag` on both `Intent` and `CoachMessage` database tables.
- Built `retrieve_rag_context()` to query historical spending patterns by tag, injecting past frequency and average spend amounts into the Coach system prompt.

#### Workstream 6: Dollar Words, Human Conversational Warmth & Markdown Chat
- Built `parse_amount_cents_from_text()` supporting `$XX`, numbers + currency words (`15 dollars`, `50 cents`), and full word numbers (`twenty dollars`, `fifteen bucks`).
- Replaced robotic fallback templates with dynamic conversational replies incorporating user financial telemetry (name, daily balance, rollover streak).
- Created zero-dependency `MarkdownRenderer.jsx` rendering bold, italics, inline code, headers, and bullet lists in the chat UI.
- Wired PayPal approval URLs to launch the configured PayPal sandbox environment directly.

---

## 3. Phase 4: PayPal Sandbox & Automated Lifecycles (Next Phase)

### 3.1. Overview
Phase 4 connects live PayPal developer sandbox credentials to execute end-to-end payment creation, authorization holds, capture callbacks, and scheduled zero-sum background lifecycles.

### 3.2. Detailed Workstreams
1. **End-to-End PayPal Orders v2 Checkout**:
   - Create PayPal order (`POST /v2/checkout/orders`) with intent `AUTHORIZE` or `CAPTURE`.
   - Store PayPal Order ID on `Intent` and `LedgerEntry`.
   - Launch PayPal checkout popup/redirect and capture via webhook or explicit client capture endpoint.
2. **Automated Midnight Rollover Worker**:
   - At 00:00 midnight: compute unspent Daily balance ($B_{\text{daily}}$).
   - If $B_{\text{daily}} > 0$: transfer remainder from `daily` to `vault` or `freedom` according to user's `rollover_mode`.
   - Re-fill `daily` bucket from `bank` up to user's daily allowance ($L_{\text{daily}}$).
   - Increment `rollover_streak_days`.
3. **Payday Allocation Worker**:
   - Triggered on direct deposit webhook or scheduled pay frequency (bi-weekly/monthly).
   - Segregates income into `bills` (reserved 30-day bill obligations), `daily` (14-day daily pool), `freedom` (discretionary fun), and `vault` (long-term savings).
4. **Automated Vault Skim via PayPal Payouts**:
   - Skim micro-savings ($1–$5 on every transaction) directly to user's designated high-yield savings account or secondary PayPal vault email via PayPal Payouts API.
