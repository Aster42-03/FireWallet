# Decisions (ADR Log)

Architectural Decision Records governing **FireWallet**. Every architectural change must be checked against **[problems.md](problems.md) (Core Build & Verification Gate)** and [hackathon_overview.md](hackathon_overview.md).

Status: **accepted** = active architectural specification. **superseded** = replaced by a later ADR. **proposed** = open option.

---

## ADR-001 — Docs-only first, then code

**Status:** accepted  
**Context:** Complex financial domain (double-entry ledger + PayPal Sandbox + AI agent guardrails).  
**Decision:** Maintain authoritative specifications in `docs/` synchronized with `backend/` and `frontend/`.  
**Consequences:** Every build must check against **[problems.md](problems.md)** and keep docs and code aligned.

## ADR-002 — Monorepo FastAPI + React Dual-Surface Web App (Tailwind HUD + AG Grid Desktop)

**Status:** accepted  
**Decision:** `backend/` (FastAPI, uv, SQLModel + asyncpg / aiosqlite) and `frontend/` (React, Vite, Tailwind CSS, AG Grid, fnm).  
**Why:** Clean monorepo separating asynchronous backend services from a dual-surface SPA: minimalist mobile HUD (`view='hud'`) and an enterprise AG Grid ledger (`view='deep-ledger'`).

## ADR-003 — Ledger source of truth, PayPal executes (`Voluntary-Commitment Model`)

**Status:** accepted  
**Decision:** Relational double-entry ledger holds bucket balances via SQLModel (SQLite for local dev, PostgreSQL for production). PayPal Orders v2, Payouts, and Webhooks move and confirm external money. Internal Bank ↔ Daily ↔ Freedom allocations are ledger-enforced commitment boundaries; Vault skims, bills, and merchant checkouts execute real PayPal API calls.  
**Why:** PayPal Sandbox is not a multi-subaccount bank; combining a voluntary-commitment double-entry ledger with real PayPal Orders and Vault Payouts delivers genuine financial friction and real money movement.

## ADR-004 — Daily rollover is top-up, not reset

**Status:** accepted  
**Decision:** Unused Daily balance remains intact. The midnight rollover job tops Daily up to `daily_amount` from Bank (or preserves a higher accumulated rollover balance).  
**Why:** Rewards daily restraint; unspent allowance compounds into future spending power.

## ADR-005 — Freedom is calendar-month, leftover stays

**Status:** accepted  
**Decision:** Credit Freedom once per user-local month from Bank. Leftover does not sweep unless `freedom_leftover_sweep_to_vault` is enabled.  
**Why:** “Once burned, gone” for monthly impulse spending.

## ADR-006 — Bills beat Vault skim on short income

**Status:** accepted  
**Decision:** If `vault_skim + bills_due > gross_income`, fund Bills reservations first and skim only the remainder.  
**Why:** Essentials (rent and utilities) always take priority over savings skims.

## ADR-007 — Bank spend requires Escape Window friction

**Status:** accepted  
**Decision:** Non-emergency Bank Foundation raids require a written confession (`>= 200` chars) and a server-enforced cooldown (`override_cooldown_seconds`). No one-click bypass for impulse spending.  
**Why:** Core psychological firewall protecting rent and foundation reserves.

## ADR-008 — Intent-first agent is in-process FastAPI, not PayPal MCP at runtime

**Status:** accepted  
**Decision:** LLM inference runs inside FastAPI (`app/agents/`) via structured JSON outputs. The LLM never holds PayPal credentials or calls PayPal directly.  
**Why:** Deterministic safety boundary (`propose → verify → confirm → execute`).

## ADR-009 — Money as integer minor units

**Status:** accepted  
**Decision:** All monetary values are stored and computed as `BIGINT` minor units (integer cents). Conversion to two-decimal strings (`"24.50"`) happens strictly at the PayPal HTTP edge.  
**Why:** Eliminates IEEE 754 floating-point rounding bugs.

## ADR-010 — Sandbox only

**Status:** accepted  
**Decision:** Enforce `api-m.sandbox.paypal.com` (`PAYPAL_ENV=sandbox`). Refuse live production PayPal URLs in v1.  
**Why:** Hackathon compliance and financial safety.

## ADR-011 — AG Grid for Desktop Deep Analytics & Advanced Ledger

**Status:** accepted  
**Decision:** Integrate AG Grid as the desktop "Advanced Ledger & Audit Log" workbench (`view='deep-ledger'`). Unlocks multi-column sorting, granular filtering, category grouping, double-entry `transfer_id` inspection, and direct "Analyze with Coach" actions.  
**Why:** Delivers an enterprise financial auditing experience and targets the AG Grid Sponsor category.

## ADR-012 — Deterministic Lifecycle Endpoints & Jobs

**Status:** accepted  
**Decision:** Expose midnight rollover (`POST /api/v1/paypal/rollover`) and payday allocation (`POST /api/v1/paypal/payday`) as deterministic job modules callable both via scheduled cron tasks and `DEMO_MODE` judge simulation controls.  
**Why:** Allows judges to immediately test time-based mechanics (Rollover Rule and Payday Vault Payouts) on demand without waiting until midnight.

## ADR-013 — Standardized Frontend Toolchain (`npm` + `fnm`)

**Status:** accepted  
**Decision:** Standardize on `npm` with `fnm` (Node 20+) and a single `package-lock.json` in `frontend/`.  
**Why:** Reproducible builds across local dev and Render static hosting.

## ADR-014 — Seeded Sandbox Buyer with Live PayPal Balance Sync

**Status:** accepted  
**Decision:** Pre-seed the demo user ("Aster") with a linked sandbox buyer profile and provide 1-tap live PayPal Sandbox balance detection (`GET /v1/reporting/balances` via `POST /api/v1/paypal/sync-balance`), tagging balances as `live` or `simulated`.  
**Why:** Ensures judges can test end-to-end checkout and balance sync immediately without OAuth redirect blockers.

## ADR-015 — Single currency USD

**Status:** accepted for v1  
**Decision:** Policy currency `USD`. Reject currency mismatches with HTTP 422.  
**Why:** Clean sandbox testing and deterministic accounting.

## ADR-016 — Product brand FireWallet, architecture Trinity (5 Bucket Kinds)

**Status:** accepted  
**Decision:** Name the user-facing product **FireWallet** and retain **Trinity** as the underlying 5-bucket architecture (`bank`, `daily`, `freedom`, `vault`, `bills`) documented in [TRINITY_RULES.md](TRINITY_RULES.md).  
**Why:** "FireWallet" communicates proactive spending protection, while "Trinity" names the core bucket engine.

## ADR-017 — Logical Separation of Intent Classification and Read-Only Coaching

**Status:** superseded by ADR-021  
**Decision:** Separate proactive spend classification (`agents/intent/`) from reactive financial literacy coaching (`agents/insights/`), while keeping `ledger/` strictly deterministic and keeping the Coach strictly read-only.  
**Why:** Prevents conversational LLM outputs from directly executing payments. Unified into a single-call structured schema in ADR-021.

## ADR-018 — Cloud Hosting on Render (`render.yaml`)

**Status:** accepted  
**Decision:** Deploy FastAPI web service, Managed PostgreSQL database, and React static site on Render via `render.yaml`.  
**Why:** Provides the public HTTPS URL required for PayPal Sandbox webhook verification (`/api/v1/webhooks/paypal`) and targets the Render Sponsor category.

## ADR-019 — Deep Analytics Layer & Telemetry-Grounded Coach

**Status:** accepted  
**Decision:** Implement `backend/app/analytics/deep_analytics.py` computing spending velocity, bucket drift, and statistical anomalies ($>1.5\sigma$), feeding both the AG Grid workbench and the Financial Coach.  
**Why:** Grounds Coach answers in exact double-entry ledger telemetry rather than generic advice.

## ADR-020 — Vault Internal Separation (Emergency Reserve + Sinking Goals) & Deterministic Emergency Verification

**Status:** accepted  
**Context:** Previously, documents disagreed on whether the Vault was permanently locked long-term savings or an emergency source (`BUG-008`, [problems.md](problems.md) Problem 5).  
**Decision:**
1. **Vault Purpose:** The `vault` bucket is **not** an external retirement account; it houses the user's **Emergency Reserve** plus **Pre-designated Sinking Goals** (e.g., saving for a camera or equipment). True long-term wealth and investments live in a separate external account and are swept outward upon reasoning with the Coach.
2. **Internal Separation:** Within the Vault, emergency reserves stay locked until an actual emergency strikes and is verified. Pre-designated goal funds unlock only when their target criteria are met.
3. **Deterministic Verification:** The LLM classifies `category` and `is_emergency`, but deterministic Python code in `LedgerEngine` verifies emergency eligibility (requiring both an emergency category such as medical/safety/transit/utility-shutoff and verified emergency signals) before unlocking Vault emergency reserves or bypassing standard reflection cooldowns.

## ADR-021 — Monolithic Single-Call Agent (`CoachDecision`), Groq Model Cascade & `Propose → Verify → Confirm → Execute`

**Status:** accepted  
**Context:** Multi-agent LLM frameworks multiply latency (3x–6x) and failure points during live demos. Additionally, hardcoded single model IDs risk 404 deprecation ([problems.md](problems.md) Problem 4).  
**Decision:**
1. Use a **Monolithic Single-Call Architecture** returning a strict JSON schema (`CoachDecision` + 1-tap `ActionCard`) in one inference pass.
2. Route inference through a resilient Groq model cascade (`openai/gpt-oss-120b` primary) with OpenAI (`gpt-4o-mini`) secondary fallback and a clearly badged `local_fallback` offline mode exposed on `GET /api/v1/coach/status`.
3. Enforce the **Propose → Verify → Confirm → Execute** pattern: the LLM *proposes* a verdict and `ActionCard`; deterministic Python (`LedgerEngine.can_spend`) *verifies* invariants; the user *confirms* via 1-tap button; and `paypal_client.py` *executes* the PayPal Order or Payout.
