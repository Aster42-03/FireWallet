# Decisions (ADR log)

First-draft defaults so other docs can be concrete. Change by adding a new ADR and updating dependents. Hackathon constraints in [hackathon_overview.md](hackathon_overview.md) are not ADRs.

Status: **accepted** = current draft. **proposed** = still easy to flip.

## ADR-001 — Docs-only first, then code

**Status:** accepted  
**Context:** Empty repo; product is non-trivial (ledger + PayPal + agent).  
**Decision:** Populate `docs/` before scaffolding FastAPI/React.  
**Consequences:** Implementation must follow these files or update them in the same change.

## ADR-002 — Monorepo FastAPI + React PWA (Tailwind HUD + AG Grid Desktop)

**Status:** accepted  
**Decision:** `backend/` (FastAPI, uv, SQLModel + asyncpg / aiosqlite) and `frontend/` (React, Vite, Tailwind CSS, AG Grid, fnm).  
**Why:** Clean monorepo separating asynchronous backend services from a dual-surface frontend: minimalist mobile HUD on `/` and a deep AG Grid ledger on desktop.

## ADR-003 — Ledger source of truth, PayPal executes

**Status:** accepted  
**Decision:** Relational double-entry ledger holds balances via SQLModel (SQLite for local dev, PostgreSQL for production). PayPal Orders/Payouts/Webhooks move and confirm money. Internal Bank↔Daily↔Freedom are ledger-only. Vault skim, bills, and merchant spend always hit PayPal.  
**Why:** Sandbox is not a four-account bank. Still a non-trivial PayPal integration.

## ADR-004 — Daily rollover is top-up, not reset

**Status:** accepted  
**Decision:** Unused Daily remains. Morning job tops Daily up to `daily_amount` from Bank.  
**Why:** Matches the Rollover Rule in the product outline; discipline compounds into future spending power.

## ADR-005 — Freedom is calendar-month, leftover stays

**Status:** accepted  
**Decision:** Credit Freedom once per user-local month from Bank. Leftover does not sweep unless `freedom_leftover_sweep_to_vault`.  
**Why:** “Once burned, gone” for spending; leftover surplus is still hedonism, not rent.

## ADR-006 — Bills beat Vault skim on short income

**Status:** accepted  
**Decision:** If skim + bill reserve > gross, fund Bills first.  
**Why:** Firewall is essentials-first.

## ADR-007 — Bank spend and cross-bucket chaos require friction

**Status:** accepted  
**Decision:** Confession + cooldown; partner 2FA when enabled for Bank. No one-click override. Vault spend off by default with no override.  
**Why:** Core product firewall.

## ADR-008 — Intent-first agent is in-process FastAPI, not PayPal MCP at runtime

**Status:** accepted  
**Decision:** OpenAI-compatible LLM in `agents/intent/`. MCP/AI Toolkit for developers. Agent cannot call PayPal.  
**Why:** Agentic commerce story + safety. Judges see a product.

## ADR-009 — Money as integer minor units

**Status:** accepted  
**Decision:** `BIGINT` cents. Convert to PayPal decimal strings only at the HTTP edge.  
**Why:** Avoid float rounding errors.

## ADR-010 — Sandbox only

**Status:** accepted  
**Decision:** `api-m.sandbox.paypal.com`. Refuse live in v1.  
**Why:** Hackathon rules; safety.

## ADR-011 — AG Grid is Foundational for Desktop Deep Analytics & Advanced Ledger

**Status:** accepted  
**Decision:** Integrate AG Grid as a foundational architectural component for the desktop "Advanced Ledger & Audit Log" view (`/analytics/deep-ledger`). While mobile maintains a minimalist Tailwind card layout, the desktop view unlocks AG Grid's enterprise multi-column sorting, granular filtering, category grouping, and direct "Analyze with Coach" actions.  
**Why:** Delivers an enterprise-grade financial auditing experience for desktop users, directly connects visual ledger states with the AI reasoning coach, and qualifies FireWallet for the **AG Grid Sponsor Prize**.

## ADR-012 — In-process jobs for demo

**Status:** proposed  
**Decision:** Scheduler inside API process; unique `(user_id, local_date, kind)`. Extract workers if hosted needs it.  
**Why:** Fewer moving parts for judges.

## ADR-013 — npm vs pnpm

**Status:** proposed  
**Decision:** npm until someone pins pnpm in frontend. One lockfile only.  
**Why:** fnm + Vite; avoid two package managers.

## ADR-014 — Identity login with seeded fallback

**Status:** proposed  
**Decision:** Login with PayPal is the intended auth. SOP seed may pre-link a sandbox buyer if Identity slips.  
**Why:** Deep PayPal vs. demo reliability.

## ADR-015 — Single currency USD

**Status:** accepted for v1  
**Decision:** Policy currency USD. Reject mismatches.  
**Why:** Sandbox US testing is the documented path.

## ADR-016 — Product brand FireWallet, architecture Trinity

**Status:** accepted  
**Decision:** Rename the user-facing product to **FireWallet**. Retain **Trinity** as the 4-bucket architectural foundation (Bank, Daily Allowance, Freedom, Vault) documented in [trinity_logic.md](trinity_logic.md) and [TRINITY_RULES.md](TRINITY_RULES.md).  
**Why:** "FireWallet" communicates the active financial firewall and liquidity restriction, while "Trinity" describes the underlying multi-bucket invariant engine. Git repository directory remains `Trinity`.

## ADR-017 — Dual LLM agents + deterministic policy + analytics; Coach cannot pay

**Status:** accepted  
**Decision:** Deploy two separate LLM agents with distinct responsibilities:
1. **Intent Agent** (`agents/intent/`): Structured parse of spend *why*. Proactive gating. Fails closed.
2. **Insights Coach** (`agents/insights/`): Reactive conversational coach for financial literacy and affordability simulation. Read-only tools querying `app.analytics`.
The policy engine (`ledger/`) is strictly deterministic code. The coach **never** executes orders or writes to the ledger; if spend is requested, it provides affordability reasoning and returns a deep link to `/intent`.  
**Why:** Separates proactive authorization guardrails from reactive literacy coaching. Prevents conversational LLM hallucinations from touching money.

## ADR-018 — Foundational Cloud Hosting on Render

**Status:** accepted  
**Decision:** Standardize on Render (`render.yaml`) as our foundational production deployment platform for the FastAPI backend, Managed PostgreSQL database, and React static site.  
**Why:** Provides an active production URL for the Devpost submission, guarantees stable public HTTPS for PayPal sandbox webhook delivery, and strongly targets the **Render Sponsor Prize**.

## ADR-019 — Deep Analytics Layer & Advanced Reasoning Coach

**Status:** accepted  
**Decision:** Implement a dedicated Deep Analytics Layer (`backend/app/analytics/deep_analytics.py`) that computes spending velocity, cross-bucket drift, and anomaly detection. Pair this layer with an **Advanced Reasoning Model** in the Financial Coach (`agents/insights/`) capable of answering complex, multi-period financial queries and ingesting active AG Grid filter states.  
**Why:** Elevates the Financial Coach from simple FAQ lookups to a genuine financial reasoning partner that can explain deep ledger trends and answer complex questions like *"Why did my grocery spending surge 40% between the 1st and 15th compared to last month?"*.

---

When you edit a rule in [trinity_logic.md](trinity_logic.md) or PayPal mapping, add an ADR here even if it is one paragraph.
