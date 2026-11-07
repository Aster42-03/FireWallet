# FireWallet Documentation

Living specification and architectural manual for **FireWallet**: a proactive budgeting and financial firewall application built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). 

FireWallet implements the **Trinity** four-bucket architecture (**Bank**, **Daily Allowance**, **Freedom**, and **Vault**) paired with a dual-surface frontend (minimalist mobile HUD on `/` and foundational **AG Grid** desktop deep analytics workbench on `/analytics/deep-ledger`), an intent-first spend firewall, and a reactive AI Financial Coach with an Advanced Reasoning Model.

---

## Core Specification Index

| Document | Purpose |
| :--- | :--- |
| **[TOOL_STACK.md](TOOL_STACK.md)** | **Confirmed Tool Ecosystem:** FastAPI, SQLite/PostgreSQL, React/Tailwind, PayPal Sandbox, Render, AG Grid, Postman, APIMatic. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | **System Design & Repo Layout:** Split monorepo (`/backend` + `/frontend`), database schemas, 3-agent pipeline, and Deep Analysis Layer. |
| **[TRINITY_RULES.md](TRINITY_RULES.md)** | **Mathematical & Behavioral Logic:** Rules for Bank, Daily Allowance with rollovers, Vault, Freedom, and the Escape Window. |
| **[SETUP_GUIDE.md](SETUP_GUIDE.md)** | **Local & Cloud Run Guide:** Virtual environment (`uv`/`pip`), PayPal sandbox configuration, Postman tests, and Render deployment. |
| **[openapi.json](openapi.json)** | **APIMatic-Compatible Contract:** Exported OpenAPI 3.1 schema for SDK generation and typed context. |
| **[hackathon_overview.md](hackathon_overview.md)** | Dates, submission rules, judging criteria, prize strategy, and decision filters. |
| **[product.md](product.md)** | Core philosophy, student and irregular earner personas, surfaces, and non-goals. |
| **[agent_design.md](agent_design.md)** | Multi-agent boundaries: Intent Parser, Policy Guardrail, PayPal Executor, and Financial Coach. |
| **[insights.md](insights.md)** | Financial Coach Advanced Reasoning Model, chart literacy loops (`chart_id`), affordability, and AG Grid deep queries. |
| **[paypal_integration.md](paypal_integration.md)** | PayPal Sandbox REST mappings: Orders v2, Payouts, Identity, and Webhooks. |
| **[data_model.md](data_model.md)** | Database schemas, SQLModel mapped models, indexes, and analytics joins. |
| **[api_contracts.md](api_contracts.md)** | REST JSON DTOs, endpoint signatures, deep ledger query endpoints, and error responses. |
| **[frontend.md](frontend.md)** | Dual-surface frontend: Minimalist mobile HUD (`/`) and Desktop AG Grid Advanced Ledger (`/analytics/deep-ledger`). |
| **[workflows.md](workflows.md)** | User lifecycles, payday splits, rollover top-ups, deep analysis flows, and sequence diagrams. |
| **[security.md](security.md)** | Secret hygiene, webhook signature verification, 2FA, and PII protection. |
| **[demo_script.md](demo_script.md)** | Sub-3-minute video storyboard proving the firewall live on mobile with desktop AG Grid inspection. |
| **[decisions.md](decisions.md)** | Architectural Decision Records (ADRs 001–019). |

---

## Tech Stack Summary

- **Backend:** FastAPI (Python 3.12+), core **`uv`** package & environment manager (`uv.lock`), modern **SQLModel ORM** (SQLAlchemy 2.0 async + Pydantic v2 `.model_dump()`), dual-engine support for **SQLite** (local dev) and **PostgreSQL** (production on Render), Alembic.
- **Frontend (Dual-Surface):** Core **`npm`** package manager with **`fnm`** (Node 20+), Vite, Tailwind CSS, and AG Grid:
  - *Mobile View (`/`):* Clean, minimalist Tailwind cards for Bank, Daily (with rollover), safe Vault/Bills, Freedom meter, Quick Intent FAB, and Coach drawer.
  - *Desktop Admin View (`/analytics/deep-ledger`):* High-density **AG Grid** "Advanced Ledger & Audit Log" with multi-column sorting, grouping, state filtering, and direct Coach interrogation.
- **Financial Engine:** PayPal Sandbox REST APIs (`api-m.sandbox.paypal.com`) utilizing Orders v2, Payouts, Identity, and Webhooks.
- **AI & Agent Pipeline:**
  1. *Intent Parser:* Structured natural language categorization and necessity classification.
  2. *Policy Guardrail:* Deterministic `can_spend` rules, row locking, and hold placement.
  3. *Financial Coach:* Advanced Reasoning Model answering complex financial questions, explaining charts, and simulating affordability.
- **Developer & Deployment Tools:**
  - **Render:** Foundational cloud hosting for FastAPI web service, Managed PostgreSQL database, and React static site (powers live Devpost URL & wins Render Sponsor Prize).
  - **AG Grid:** Foundational enterprise desktop grid for the Deep Analysis Layer (wins AG Grid Sponsor Prize).
  - **Postman:** Pre-flight smoke-testing and payload verification via `postman_collection.json`.
  - **APIMatic:** OpenAPI SDK context to eliminate code generation hallucinations.
