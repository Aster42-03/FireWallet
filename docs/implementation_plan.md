# FireWallet: Comprehensive Implementation Roadmap & Milestones

**Source of Truth:** Post-Phase 4 Milestone & Pre-Submission Action Plan  
**Core Build Gate:** **[problems.md](problems.md)** (*Honest Review and Prioritized Action Plan*)  
**Submission Deadline:** Thu Nov 12, 2026, 12:00 PM PST (Internal Cutoff: Thu Nov 12, 6:00 PM IST)

> [!IMPORTANT]
> **Mandatory Build Verification Rule:** Before starting or completing any engineering workstream, check **[problems.md](problems.md)**. Every build must answer the gating questions in **[problems.md](problems.md)**, satisfy its explicit **"Done when"** criteria, and strictly obey the **Cut List (Section 7)**—if a feature is not in the sub-3-minute video or judge quick start, it receives zero engineering hours before Nov 12.

---

## 1. Executive Summary & Milestone Matrix

FireWallet operates on the **Trinity Architecture**: capital is segregated deterministically into 5 strict buckets (**Bank Foundation**, **Daily Living**, **Freedom Envelope**, **Savings Vault** [with Emergency Reserves & Sinking Goal targets], and **Reserved Bills**), guarded by a **Voluntary-Commitment Financial Firewall** and analyzed by an **Advanced Reasoning Coach**.

| Phase | Milestone Description | Status | Key Deliverables & Verification Gate |
|---|---|---|---|
| **Phase 1** | **Core Engine & Accounting Foundation** | **DONE** | Zero-float minor unit math, 5 Trinity buckets, rule evaluation engine, UV packaging, 23 unit/API tests passing with 0 warnings. |
| **Phase 2** | **Double-Entry Ledger & AG Grid Workbench** | **DONE** | Bank-kept double-entry ledger (`transfer_id` pairing, $\sum \text{legs} = 0$), running balances, AG Grid v32 dark quartz grid, Alembic SQLite/PostgreSQL migrations. |
| **Phase 3** | **Unified Monolithic Agent, RAG Short-Tags, 1-Tap Actions & Hardened Webhooks** | **DONE** | Single-call Groq `openai/gpt-oss-120b` (`gpt-4o-mini` fallback) returning `CoachDecision` + 1-tap `ActionCard`, persistent 2–5 word `short_tag` RAG memory, dollar words parser, rich Markdown rendering, status-tracked atomic PayPal webhooks (`0003_phase3_rag_status`), `BUG-001` through `BUG-005` resolved, 39/39 unit/API tests passing. |
| **Phase 4** | **PayPal Balance Detection, Sync & Configurable Envelopes** | **DONE (Built)** | Balance detection (`GET /v1/reporting/balances` with source tagging), 1-tap balance sync (`POST /api/v1/paypal/sync-balance`), configurable envelopes modal (`Daily`, `Freedom`, `Vault`), removal of billboard branding & scaffolding placeholders, `BUG-007` resolved, live LLM integration cascade, 44 unit/API tests passing. |
| **Phase 5** | **Gating Verification, Emergency Hardening & Voluntary Commitment UX** | **ACTIVE (See [problems.md](problems.md))** | Driven strictly by **[problems.md](problems.md)** Problems 1–5: End-to-end live Render PayPal proof (Order → Capture → Signed Webhook `/api/v1/webhooks/paypal` → Vault Payout), Postgres concurrency test, `DEMO_MODE` controls (Reset, Simulate Next Day, Simulate Payday), deterministic emergency rule (`BUG-008` closure), Protected HUD panel, onboarding commitment step, and Coach tool-call citations + eval harness. |
| **Phase 6** | **Judge-Proof Cloud Deployment, Video & Devpost Packaging** | **ACTIVE (See [problems.md](problems.md))** | Driven strictly by **[problems.md](problems.md)** Problems 2, 6, 9–14: `render.yaml` hardening, `JUDGES.md` 5-step quick start, AG Grid master/detail & Coach row highlighting, secrets/hygiene audit, and sub-3-minute video recording (target 2:30–2:45). |

---

## 2. Prioritized 4-Day Execution Plan (Synced with [problems.md](problems.md))

| Day | Focus & Target Gating Problems | "Done When" Verification Gate |
|---|---|---|
| **Sun Nov 8** | **Scope Freeze + Problem 1 (PayPal E2E Gate) + Problem 5 (Emergency Decision)** | Smoke script runs Order, Capture, signed Webhook (`/api/v1/webhooks/paypal`), and $1 Vault Payout end-to-end. Replaying capture/payout twice never double-posts. Emergency policy documented (ADR-020). |
| **Mon Nov 9** | **Problem 2 (Judge-Proof Demo & Postgres) + Problem 5 (Emergency Implementation)** | Full test suite + concurrency test green on real PostgreSQL. `render.yaml` verified. `DEMO_MODE` controls wired (`Reset Demo`, `Simulate Next Day`, `Simulate Payday`). Emergency rule & 4 abuse tests passing (`BUG-008` closed). |
| **Tue Nov 10** | **Problem 4 (Live AI & Eval) + Problem 3 (Voluntary Commitment & Protected Panel) + Problem 9 (AG Grid)** | Verdict card displays category/necessity/confidence/rationale. Coach shows tool-call citations. Eval table (30–50 intents + prompt-injection tests) in README. Protected panel on HUD + onboarding commitment step. AG Grid highlights Coach-flagged rows without license watermark. |
| **Wed Nov 11** | **Problem 6 (Video) + Problem 11–14 (Docs, `JUDGES.md`, CI, Hygiene)** | `README.md` & `JUDGES.md` complete. GitHub Actions CI green on SQLite + Postgres. 3 video takes recorded (2:30–2:45, captioned, public YouTube). Fresh-clone dry run (< 5 min) on clean machine and mobile phone. |
| **Thu Nov 12** | **Submission Buffer Only (Zero New Features)** | Submitted on Devpost by **6:00 PM IST** (7.5h buffer before 12:00 PM PST deadline). |

---

## 3. Completed Workstreams (Phases 1–4)

### 3.1. Architectural Principle: `Propose → Verify → Confirm → Execute`
1. **Propose (The Monolithic AI Agent)**:
   - Single-call LLM (`openai/gpt-oss-120b` on Groq with `gpt-4o-mini` fallback) classifies natural-language spend intents, distills 2–5 word RAG `short_tag` labels, and proposes a structured `CoachDecision` + `ActionCard`.
2. **Verify (Deterministic Python Guardrails)**:
   - `LedgerEngine.can_spend()` evaluates the proposal against user-configured bucket caps, bills reservations, and emergency verification rules. The LLM never executes payments or mutates balances.
3. **Confirm (Explicit User Commitment)**:
   - The user confirms the 1-tap action card (or completes Escape Window reflection friction for Bank Foundation overrides).
4. **Execute (PayPal Sandbox & Double-Entry Settlement)**:
   - Places an atomic `HOLD`, executes PayPal Orders v2 (`intent=CAPTURE`) or Payouts (`Vault` skim / `Bills`), and settles via verified webhooks at `/api/v1/webhooks/paypal`.

### 3.2. Key Deliverables Built in Phases 1–4
- **`BUG-001` through `BUG-007` Resolved**: Fixed chat doubling, dual-database path divergence, robotic responses, dollar-word parsing, raw markdown rendering, quick chat chips, and diagnostic chip catch-all short-circuiting.
- **PayPal Balance Detection & Sync**: `GET /api/v1/paypal/balance` and `POST /api/v1/paypal/sync-balance`.
- **Configurable Envelopes**: `GET/PUT/PATCH /api/v1/me/policy` and `BucketConfigModal.jsx`.
- **Lifecycle Jobs**: Midnight rollover (`POST /api/v1/paypal/rollover`) and Payday inflow split (`POST /api/v1/paypal/payday`).

---

## 4. Cut List (Strictly Deferred to Post-Hackathon v2.0 — See [features.md](features.md))

Per **[problems.md](problems.md) Section 7**, the following items must **NOT** be built before Nov 12:
- Complex Trust Score / MCC reputation engine (keep a simple monthly emergency counter only)
- Cryptographic partner email magic-link multi-sig & Telegram partner bot
- Trinity Batch Dispatcher & `/bills/staging` UI
- Predictive Cash Flow Smoothing
- Extra sponsor SDKs (Channel3, Bryntum, Zapier, Elastic)
- Multi-currency support, new bucket kinds, or unscripted UI controls
