# Tool & Technology Stack

This document defines the confirmed, foundational tool ecosystem for **FireWallet** (incorporating the **Trinity** bucket financial engine). It provides Cursor, AI assistants, and developers with the exact library choices, directory placements, environment configurations, and architectural integration points for every tool in the system.

Related: **[problems.md](problems.md) (Core Build & Verification Gate)**, [architecture.md](architecture.md), [SETUP_GUIDE.md](SETUP_GUIDE.md).

At its foundation, FireWallet standardizes on **`uv`** as its high-performance Python package and environment manager, **`npm`** (with `fnm`) for frontend Node.js package management, and the modern **SQLModel** ORM (marrying SQLAlchemy 2.0 Async with Pydantic v2) for all database operations.

---

## 1. Master Tool & Technology Matrix

| Tool / Technology | Role & Purpose | Where It Fits in the Architecture | Configuration / Entry Point |
| :--- | :--- | :--- | :--- |
| **uv** | **Foundational Python Package & Environment Manager** | Root & `/backend` — Ultra-fast Rust-based package resolution, lockfile management (`uv.lock`), and virtualenv isolation | `backend/pyproject.toml`, `backend/uv.lock` |
| **npm (+ fnm)** | **Foundational Node.js Package Manager & Runtime** | `/frontend` — Fast frontend package management and reproducible Node 20+ runtime | `frontend/package.json`, `.node-version` |
| **FastAPI (Python 3.12+)** | High-performance asynchronous backend framework | `/backend` — API routes, DTOs, async lifespan, monolithic agent orchestrator | `backend/app/main.py` |
| **SQLModel (Modern ORM)** | Next-gen relational ORM (SQLAlchemy 2.0 async + Pydantic v2) | `/backend/app/models/`, `/backend/app/database.py` — Schema definitions, validation, migrations, and typed async queries | `backend/app/models/__init__.py` |
| **SQLite / PostgreSQL** | Relational database for persistent storage (Dual-Engine Strategy) | `/backend/app/database.py` — Users, Trinity bucket balances, ledger entries, coach threads | SQLite (`sqlite+aiosqlite`) local dev; Postgres (`postgresql+asyncpg`) on Render |
| **React + Tailwind CSS** | Mobile-first frontend UI framework | `/frontend` — Minimalist mobile HUD dashboard, Quick Intent modal, and Insights Coach drawer | `frontend/src/`, `tailwind.config.js`, `vite.config.js` |
| **PayPal Sandbox APIs** | Financial engine & real transaction routing | `backend/app/services/paypal_client.py` — Reporting Balances, Orders v2 (captures), Payouts (vault/bills), Webhooks | Base URL: `https://api-m.sandbox.paypal.com` |
| **Render** | **Foundational Cloud Platform & Live Production Host** | Cloud Infrastructure — FastAPI web service, Managed PostgreSQL DB, React static site | `render.yaml` (Powers live Devpost URL & targets Render Sponsor category) |
| **AG Grid** | **Foundational Desktop Deep Analytics & Advanced Ledger** | `/frontend/src/features/analytics/DeepLedgerGrid.jsx` — Desktop "Advanced Ledger & Audit Log" view | Rendered on desktop surface `view='deep-ledger'` (Targets AG Grid Sponsor category) |
| **Monolithic Financial Coach** | Deep financial analysis, intent evaluation & 1-tap action generation | `backend/app/agents/insights/`, `backend/app/agents/shared/` — Single-call Groq `openai/gpt-oss-120b` returning `CoachDecision` + 1-tap `ActionCard`, paired with deterministic `LedgerEngine` guardrails | High-reasoning LLM client in `backend/app/agents/shared/llm_client.py` |
| **Postman** | API development, smoke-testing, and contract verification | Local / CI — Pre-flight smoke testing of FastAPI endpoints before frontend wiring | `postman_collection.json` (at repo root) |
| **APIMatic** | API context, contract definition & SDK generation | `/docs/` & dev workflow — Feeds verified OpenAPI / PayPal specs to Cursor to eliminate hallucinations | `docs/openapi.json`, APIMatic portal |

---

## 2. In-Depth Tool Specifications

### 2.1. uv (Core Python Package & Environment Manager)

- **Location:** `backend/` and repository root.
- **Role:** **Foundational Python toolchain**. Replaces legacy `pip`, `virtualenv`, and `pip-tools` with an ultra-fast Rust-based package manager.
- **Key Capabilities:**
  - **Deterministic Lockfiles:** `backend/uv.lock` freezes all transitive dependencies with exact cryptographic hashes.
  - **Instant Workspace Sync:** `uv sync` installs the complete virtual environment in milliseconds.
  - **Isolated Execution:** `uv run` executes scripts (`uv run python -m app.jobs.seed`, `uv run uvicorn ...`) with the correct environment without requiring manual activation scripts.
  - **Python 3.12+ Pinning:** Strict adherence to `.python-version` (Python 3.12).

---

### 2.2. npm & fnm (Core Frontend Package & Node Manager)

- **Location:** `frontend/`
- **Role:** **Foundational Node.js toolchain**.
- **Key Capabilities:**
  - **Node.js Runtime Pinning:** Pinned to Node.js 20+ using `fnm` (Fast Node Manager) via `.node-version`.
  - **Reproducible Dependency Tree:** Standardized `npm install` and `package-lock.json` managing Vite, React, Tailwind, and AG Grid.
  - **Build Automation:** `npm run dev` for local hot module replacement (HMR) and `npm run build` producing production-optimized static bundles for Render.

---

### 2.3. Modern SQLModel ORM (SQLAlchemy 2.0 Async + Pydantic v2)

- **Location:** `backend/app/models/`, `backend/app/database.py`
- **Role:** **Next-generation unified data modeling and query layer**. Eliminates the traditional duplication between SQLAlchemy ORM models and Pydantic schemas.
- **Modern Architectural Patterns:**
  - **Tripartite Model Separation:**
    1. `*Base(SQLModel)`: Shared domain fields and Pydantic validation rules.
    2. `*(Base, table=True)`: Persistent SQLAlchemy database entity with primary keys, indexes, foreign keys, and relationships.
    3. `*Read(Base)` & `*Update(SQLModel)`: API serialization DTOs with auto-generated IDs and timestamps.
  - **Pydantic v2 Native Methods:** Strict prohibition of deprecated `.dict()`; all serialization uses `.model_dump()` and `.model_dump_json()`.
  - **Modern Timezone Handling:** Deprecated `datetime.utcnow()` is replaced across all models with `datetime.now(timezone.utc)` (via helper `utc_now()`).
  - **Pure SQLAlchemy 2.0 Async:** Uses `create_async_engine`, `async_sessionmaker`, and async sessions (`from sqlmodel.ext.asyncio.session import AsyncSession`) with 100% asynchronous execution (`await session.exec(select(...))`).

---

### 2.4. FastAPI (Python 3.12+)

- **Location:** `backend/`
- **Role:** Central API gateway, session authenticator, and agent pipeline coordinator.
- **Key Dependencies:**
  - `fastapi>=0.115.0`
  - `uvicorn[standard]>=0.32.0`
  - `sqlmodel>=0.0.22`
  - `httpx>=0.28.0` (async HTTP client for PayPal and LLM endpoints)
  - `pydantic-settings>=2.7.0` (type-safe environment variables)
- **Design Pattern:** Thin HTTP routers in `backend/app/api/v1/` delegating immediately to domain services (`ledger/`, `analytics/`, `services/paypal_client.py`, `agents/`).

---

### 2.5. Relational Database: SQLite / PostgreSQL (Dual-Engine)

- **Location:** `backend/app/database.py`
- **Strategy:**
  - **Local Development:** Default to SQLite via `sqlite+aiosqlite:///./firewallet.db` for instant, zero-dependency setup (no local PostgreSQL daemon or Docker required).
  - **Production / Staging (Render):** Automatically switch to PostgreSQL via `postgresql+asyncpg://...` when `DATABASE_URL` specifies a Postgres connection string.
- **ORM:** **SQLModel** mapped classes ensure identical schema definitions, query syntax, and async transaction patterns across both SQLite and PostgreSQL.
- **Migrations:** Alembic configured for async operations (`backend/alembic/`).

---

### 2.6. React (Vite) + Tailwind CSS

- **Location:** `frontend/`
- **Role:** Delivers a 60fps, mobile-first Heads-Up Display (HUD) installable as a Progressive Web App (PWA).
- **Key Dependencies:**
  - `react`, `react-dom` (v18+)
  - `vite` (ultra-fast build tool and dev server)
  - `tailwindcss`, `postcss`, `autoprefixer`
  - `lucide-react` (clean, lightweight iconography)
  - `@tanstack/react-query` (server state management, automatic cache invalidation on webhooks)
- **Dual-Surface Design:**
  - **Mobile HUD (**`/`**):** Clean, minimalist Tailwind cards for Bank foundation status, Daily Allowance with live Rollover badge, out-of-sight Vault/Bills strip, Freedom burn meter, and Quick Intent FAB.
  - **Desktop / Admin Toggle (**`/analytics/deep-ledger`**):** Seamless transition to the full **AG Grid** "Advanced Ledger & Audit Log".

---

### 2.7. Render (Foundational Cloud Hosting & Live URL)

- **Location:** `render.yaml` at repository root.
- **Role:** **Foundational cloud deployment platform**. Hosts the live production services for judges and user testing, providing the official live URL for the Devpost submission and targeting the Render Sponsor category.
- **Services Provisioned via** `render.yaml`**:**
  1. `firewallet-api`: Python Web Service running FastAPI via `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  2. `firewallet-web`: Static Site hosting the React + Tailwind web app (`npm run build`, publish directory `frontend/dist`).
  3. `firewallet-db`: Managed PostgreSQL database with automatic connection string injection.
  4. Stable Public HTTPS: Endpoints required for verified PayPal Sandbox webhook delivery (`/api/v1/webhooks/paypal`).

---

### 2.8. AG Grid (Foundational Desktop Deep Analytics & Ledger)

- **Location:** `frontend/src/features/analytics/DeepLedgerGrid.jsx`
- **Role:** **Foundational desktop ledger engine & deep analysis table**. Targets the AG Grid Sponsor category while serving as the visual front-end for deep financial auditing.
- **Capabilities & Features:**
  - **Enterprise Column Filtering & Multi-Sort:** Filter by bucket (`bank`, `daily`, `freedom`, `vault`, `bills`), state (`hold`, `posted`, `released`), date ranges, and amounts.
  - **Category & Payee Grouping:** Group transactions by merchant, category (`groceries`, `utilities`, `hedonism`), or necessity level.
  - **Audit Metadata:** Displays correlation IDs, PayPal Order IDs, Capture IDs, and webhook receipt timestamps.
  - **Direct "Ask Coach" Integration:** Users can select any transaction or grouped category in AG Grid and click "Analyze with Coach" to pass the filtered grid state directly to the reasoning agent.
  - **Exporting:** 1-click CSV and JSON ledger export.

---

### 2.9. Monolithic Financial Coach & Deep Analytics Layer

- **Location:** `backend/app/agents/insights/`, `backend/app/agents/shared/`, and `backend/app/analytics/deep_analytics.py`
- **Role:** Single-call inference engine powered by Groq `openai/gpt-oss-120b` (with OpenAI fallback `gpt-4o-mini` and offline heuristics) returning structured `CoachDecision` packets and 1-tap `ActionCard` actions, strictly backed by deterministic `LedgerEngine` Python guardrails and deep analytics.
- **Capabilities:**
  - Interrogates the PostgreSQL/SQLite ledger to perform:
    - Cross-bucket drift detection.
    - Anomaly detection (e.g., *"Why did my dining-out velocity surge between the 10th and 18th?"*).
    - Multi-period burn rate comparisons.
  - Answers complex natural-language questions grounded in exact transaction records, backed by the same dataset displayed in AG Grid.
  - Retains strict read-only security: outputs deep reasoning and pre-configured 1-tap actions, but never moves funds without explicit user confirmation.

---

### 2.10. PayPal Sandbox APIs

- **Location:** `backend/app/services/paypal_client.py`
- **Role:** Authoritative money-movement execution layer.
- **APIs Utilized:**
  1. **OAuth 2.0 Client Credentials:** `POST /v1/oauth2/token` with in-memory caching and 60-second refresh margin.
  2. **Orders v2:** `POST /v2/checkout/orders` with `intent=CAPTURE` for merchant checkout after intent approval; `POST /v2/checkout/orders/{id}/capture` upon buyer approval.
  3. **Payouts:** `POST /v1/payments/payouts` for automated payday Vault skims and scheduled bill disbursements.
  4. **Identity / Connect:** Login with PayPal for seamless sandbox buyer onboarding.
  5. **Webhooks:** Inbound webhook listener (`/api/v1/webhooks/paypal`) with cryptographic transmission signature verification against `PAYPAL_WEBHOOK_ID`.

---

### 2.11. Postman

- **Location:** `postman_collection.json` at repository root.
- **Role:** Contract smoke-testing and developer ergonomics.
- **Usage:** Pre-configured collection to verify intent classification, hold creation, cooldown conflict codes (HTTP 409), and deep analytics endpoints before frontend wiring. Instant testing for judges and evaluators.

---

### 2.12. APIMatic

- **Location:** `docs/openapi.json` and APIMatic Developer Portal.
- **Role:** Feeds clean, typed OpenAPI context and SDK definitions to Cursor to eliminate AI code generation hallucinations.

---

## 3. Cursor & AI Implementation Rules

When generating or editing code, Cursor and all AI agents must follow these library rules:

1. **Imports & ORM Patterns:**
   - Use `from sqlmodel import SQLModel, Field, select, col` for data models and queries.
   - Use `from sqlmodel.ext.asyncio.session import AsyncSession` for all database session typing.
   - Never use deprecated `.dict()` on SQLModel or Pydantic models; always use `.model_dump()` or `.model_dump_json()`.
   - Never use deprecated `datetime.utcnow()`; always use `datetime.now(timezone.utc)` (or `utc_now()`).
   - Use `from fastapi import FastAPI, Depends, HTTPException, status` for routes.
   - Use `from httpx import AsyncClient` for PayPal and LLM HTTP requests.
   - Use `ag-grid-react` and `ag-grid-community` for the desktop Deep Ledger component.
2. **Database & Analytics:**
   - All deep analytics aggregations must live in `backend/app/analytics/deep_analytics.py` and run against the SQLModel session.
   - Access database sessions via `from app.database import get_session`.
3. **PayPal Client:**
   - All PayPal interactions must go through `app.services.paypal_client.py`.
   - Never format currency as float; always convert minor units (cents) to two-decimal strings using integer arithmetic (`f"{cents // 100}.{cents % 100:02d}"`).
4. **Agents & Coach:**
   - Intent Agent (`agents/intent/`) and Financial Coach (`agents/insights/`) use `shared/llm_client.py`.
   - The Coach is strictly read-only and must **never** import or call `paypal_client.py`.
