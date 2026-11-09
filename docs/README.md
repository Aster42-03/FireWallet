# FireWallet Documentation

Living specification and architectural manual for **FireWallet**: a proactive budgeting and financial firewall web application built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). 

> [!IMPORTANT]
> **Core Build & Verification Gate — [problems.md](problems.md):**
> Every build, feature change, and deployment check must be verified against **[problems.md](problems.md)** (*Honest Review and Prioritized Action Plan*). Before considering any build or task complete, verify that it satisfies the ranked gating requirements, the **"Done when"** acceptance tests, the **Cut List (Section 7)**, and the **Repo Verification Checklist (Section 8)**.

---

## Core Philosophy: The Voluntary-Commitment Model

Nobody can tie someone down if they are set on finding a loophole. **FireWallet is a voluntary commitment layer built for people who *want* financial discipline and need friction to keep it.** Once you commit to routing your spending through FireWallet, it enforces your own rules at the point of payment and moves savings out of reach where it can.

- **One-Sentence Differentiator:** Envelope apps (YNAB-style), "pots" (Monzo-style), and AI budgeting chatbots (Cleo-style) analyze or label money *after* the fact; **FireWallet puts an LLM-parsed "why" and a deterministic policy engine (`propose → verify → confirm → execute`) in front of the payment itself.**
- **The Trinity Architecture:** Segregates capital into 5 strict buckets (**Bank Foundation**, **Daily Allowance**, **Freedom Envelope**, **Savings Vault** [housing Emergency Reserves & Pre-designated Sinking Goals, while long-term investments are swept to external accounts], and reserved **Bills**).

---

## Core Specification Index

| Document | Purpose |
| :--- | :--- |
| **[problems.md](problems.md)** | **CORE BUILD GATE & ACTION PLAN:** Prioritized gating issues, 4-day execution schedule, "Done when" tests, Cut List, and Repo Verification Checklist. **Check every build against this file.** |
| **[TOOL_STACK.md](TOOL_STACK.md)** | **Confirmed Tool Ecosystem:** FastAPI, SQLite/PostgreSQL, React/Tailwind, PayPal Sandbox, Render, AG Grid, Postman, APIMatic. |
| **[architecture.md](architecture.md)** | **System Design & Repo Layout:** Split monorepo (`/backend` + `/frontend`), database schemas, Monolithic Single-Call Agent, and Deep Analysis Layer. |
| **[TRINITY_RULES.md](TRINITY_RULES.md)** | **Mathematical & Behavioral Logic:** Rules for Bank, Daily Allowance with rollovers, Vault (Emergency Reserve + Sinking Goals), Freedom, and the Escape Window. |
| **[manual.md](manual.md)** | **Comprehensive Developer Manual:** Architecture guide, project tree, module index, local setup, and testing commands. |
| **[implementation_plan.md](implementation_plan.md)** | **Execution Roadmap & Milestones:** Living tracker of deliverables from Phase 1 through Phase 6 mapped against [problems.md](problems.md). |
| **[bugs.md](bugs.md)** | **Bug Tracker:** Root-cause analyses, test cases, and resolution verification (`BUG-001` through `BUG-008`). |
| **[sops.md](sops.md)** | **Standard Operating Procedures:** Pre-flight smoke testing, migration runbooks, and release checklists. |
| **[SETUP_GUIDE.md](SETUP_GUIDE.md)** | **Local & Cloud Run Guide:** Virtual environment (`uv`), PayPal sandbox configuration, Postman tests, and Render deployment. |
| **[openapi.json](openapi.json)** | **APIMatic-Compatible Contract:** Exported OpenAPI 3.1 schema for SDK generation and typed context (all 29 live routes). |
| **[hackathon_overview.md](hackathon_overview.md)** | Dates, submission rules, judging criteria, prize strategy, and decision filters. |
| **[product.md](product.md)** | Voluntary-commitment philosophy, student and irregular earner personas, surfaces, limitations, and non-goals. |
| **[agent_design.md](agent_design.md)** | Single-call Groq/OpenAI architecture, `propose → verify → confirm → execute` pattern, `CoachDecision` schema, 1-tap `ActionCard`, RAG short-tags, and deterministic guardrails. |
| **[insights.md](insights.md)** | Financial Coach reasoning persona, chart literacy loops (`chart_id`), affordability, and AG Grid deep queries. |
| **[paypal_integration.md](paypal_integration.md)** | PayPal Sandbox REST mappings: Reporting Balances, Orders v2, Payouts, Identity, and Webhooks (`/api/v1/webhooks/paypal`). |
| **[data_model.md](data_model.md)** | Database schemas, SQLModel mapped models, indexes, and analytics joins. |
| **[api_contracts.md](api_contracts.md)** | REST JSON DTOs, endpoint signatures (`/api/v1`), deep ledger query endpoints, and error responses. |
| **[frontend.md](frontend.md)** | Dual-surface frontend: In-app toggle between Minimalist Mobile HUD (`view='hud'`) and Desktop AG Grid Advanced Ledger (`view='deep-ledger'`). |
| **[workflows.md](workflows.md)** | User lifecycles, payday splits, rollover top-ups, deep analysis flows, and sequence diagrams. |
| **[features.md](features.md)** | Post-Hackathon v2.0+ Roadmap (The Trinity Batch Dispatcher, Partner Multi-Sig, Cash Flow Smoothing). |
| **[security.md](security.md)** | Secret hygiene, webhook signature verification, 2FA, and PII protection. |
| **[demo_script.md](demo_script.md)** | Sub-3-minute video storyboard proving the firewall live on mobile with desktop AG Grid inspection. |
| **[decisions.md](decisions.md)** | Architectural Decision Records (ADRs 001–021). |

---

## Tech Stack Summary

- **Backend:** FastAPI (Python 3.12+), core **`uv`** package & environment manager (`uv.lock`), modern **SQLModel ORM** (SQLAlchemy 2.0 async + Pydantic v2 `.model_dump()`), dual-engine support for **SQLite** (local dev) and **PostgreSQL** (production on Render), Alembic.
- **Frontend (Dual-Surface SPA):** Core **`npm`** package manager with **`fnm`** (Node 20+), Vite, Tailwind CSS, and AG Grid:
  - *Mobile HUD View (`view='hud'`):* Clean, minimalist Tailwind cards for Bank, Daily (with rollover streak), safe Vault (Emergency + Goals), Bills earmark, Freedom meter, Quick Intent FAB, and Coach drawer.
  - *Desktop Admin View (`view='deep-ledger'`):* High-density **AG Grid** "Advanced Ledger & Audit Log" with multi-column sorting, grouping, state filtering, and direct Coach interrogation.
- **Financial Engine:** PayPal Sandbox REST APIs (`api-m.sandbox.paypal.com`) utilizing Reporting Balances, Orders v2, Payouts, Identity, and Webhooks (`/api/v1/webhooks/paypal`).
- **AI & Agent Pipeline (`Propose → Verify → Confirm → Execute`):**
  - *Monolithic Single-Call Architecture:* Ultra-fast inference powered by Groq (`openai/gpt-oss-120b`) with OpenAI fallback (`gpt-4o-mini`) and badged offline heuristics. Returns conversational text (`reply`) and structured decision metadata (`CoachDecision`) containing 1-tap `ActionCard` buttons in one single JSON packet.
  - *Deterministic Python Guardrails (`LedgerEngine`):* `can_spend` rules, bucket cap enforcement, Vault emergency lock verification, and row-level locking.
- **Developer & Deployment Tools:**
  - **Render:** Cloud hosting for FastAPI web service, Managed PostgreSQL database, and React static site (powers live Devpost URL and targets the Render Sponsor category).
  - **AG Grid:** Enterprise desktop grid for the Deep Analysis Layer (targets the AG Grid Sponsor category).
  - **Postman:** Pre-flight smoke-testing and payload verification via `postman_collection.json`.
  - **APIMatic:** OpenAPI SDK context to eliminate code generation hallucinations.
