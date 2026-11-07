# Setup & Deployment Guide

This guide provides end-to-end instructions for running **FireWallet** locally (with zero-config SQLite or PostgreSQL), smoke-testing APIs with Postman, configuring PayPal Sandbox credentials, and deploying the foundational cloud architecture on **Render** (qualifying for the Render Sponsor Prize).

Related: [TOOL_STACK.md](TOOL_STACK.md), [ARCHITECTURE.md](ARCHITECTURE.md), [TRINITY_RULES.md](TRINITY_RULES.md).

---

## 1. Prerequisites & Core Tooling

FireWallet uses the latest modern package and runtime managers at its core:
- **`uv` (Python 3.12+):** The blazing-fast Rust-based package manager that handles virtual environments, lockfiles (`uv.lock`), and isolated script execution.
- **`npm` (Node.js 20+):** Managed via `fnm` (Fast Node Manager) or `nvm` for reproducible frontend toolchains.

Ensure the following tools are installed on your workstation:

| Tool | Recommended Version | Purpose |
| :--- | :--- | :--- |
| **uv** | Latest (0.5+) | **Foundational Python package and virtual environment manager** |
| **Python** | 3.12+ | Backend runtime |
| **fnm / npm** | Node 20+, npm 10+ | **Foundational frontend runtime and package manager** |
| **Git** | Latest | Version control |
| **PayPal Sandbox** | Free Developer Account | API credentials & mock money movement |
| **Tunnel Tool** | `ngrok` or Cloudflare Tunnel | Public HTTPS webhook endpoint for local development |

---

## 2. Environment Configuration

Create a `.env` file in `backend/` (do not commit this file to git). Use `backend/.env.example` as a template:

```ini
# Database: Default to SQLite for zero-config local dev, or PostgreSQL for production
DATABASE_URL=sqlite+aiosqlite:///./firewallet.db
# DATABASE_URL=postgresql+asyncpg://firewallet:firewallet@localhost:5432/firewallet

# PayPal Sandbox Credentials (from developer.paypal.com)
PAYPAL_ENV=sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=your_sandbox_client_id_here
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret_here
PAYPAL_WEBHOOK_ID=your_sandbox_webhook_id_here

# PayPal Receiver Accounts (Sandbox emails)
PAYPAL_VAULT_RECEIVER_EMAIL=vault-receiver@sandbox.paypal.com
PAYPAL_BILL_PAYEE_EMAIL=landlord@sandbox.paypal.com

# LLM Configuration (OpenAI-compatible: OpenAI, Gemini, Groq, Ollama)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_llm_api_key_here
LLM_MODEL=gpt-4o-mini

# Application Endpoints
APP_PUBLIC_URL=https://your-ngrok-or-render-tunnel.ngrok-free.app
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Frontend `.env` in `frontend/`:
```ini
VITE_API_BASE=http://localhost:8000
```

---

## 3. Local Backend Setup

### Option A: Using `uv` (Recommended - Core Package Manager)

```powershell
# Navigate to backend directory
cd backend

# Install dependencies and sync virtual environment directly from uv.lock
uv sync

# Seed the database with demo user Aster, 5 Trinity buckets, and initial balances
uv run python -m app.jobs.seed

# Run database schema migrations (if using Alembic)
uv run alembic upgrade head

# Start FastAPI with auto-reload
uv run uvicorn app.main:app --reload --port 8000
```

### Option B: Using standard `pip` and `venv`

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies in editable mode
pip install -e .

# Run migrations and launch
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 4. Local Frontend Setup

```powershell
# Open a new terminal and navigate to frontend directory
cd frontend

# Ensure correct Node version is active
fnm use 20   # or nvm use 20

# Install npm dependencies (React, Vite, Tailwind CSS, AG Grid)
npm install

# Start Vite development server
npm run dev
```

The Mobile HUD will be live at `http://localhost:5173`. Open Developer Tools (F12) and toggle **Device Mode** (e.g. iPhone 14 Pro, 390×844) to experience the mobile HUD. To explore the desktop admin interface, navigate to `/analytics/deep-ledger` to inspect the full AG Grid transaction table.

---

## 5. PayPal Sandbox Webhook Setup (Local)

To receive real-time webhook events (`PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.PAYOUTSBATCH.SUCCESS`) locally:

1. Launch a public tunnel pointing to your FastAPI port:
   ```powershell
   ngrok http 8000
   ```
2. Copy the HTTPS forwarding URL (e.g. `https://a1b2-c3d4.ngrok-free.app`).
3. Log in to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications/sandbox).
4. Select your Sandbox App $\rightarrow$ Scroll to **Webhooks** $\rightarrow$ Click **Add Webhook**.
5. Set Webhook URL: `https://<your-ngrok-url>/webhooks/paypal`.
6. Check event triggers:
   - `Checkout order approved`
   - `Payment capture completed`
   - `Payment capture denied`
   - `Payment payouts-item succeeded`
   - `Payment payouts-batch success`
7. Copy the generated **Webhook ID** into `backend/.env` under `PAYPAL_WEBHOOK_ID`.

---

## 6. Postman Smoke-Testing Workflow

1. Open Postman and import `postman/firewallet_collection.json`.
2. Configure the environment variable `baseUrl` to `http://localhost:8000`.
3. Run the collection to verify the full flow:
   - **Health Check:** `GET /health` $\rightarrow$ Expect `200 OK`.
   - **Buckets Snapshot:** `GET /buckets` $\rightarrow$ Verifies Trinity balances.
   - **Intent Submission:** `POST /intents` with `{"utterance": "Groceries", "amount": 2500}` $\rightarrow$ Expect status `allowed`.
   - **Escape Window Test:** `POST /intents` with high-cost takeout when Freedom is $0 $\rightarrow$ Expect status `needs_override`.
   - **Coach Literacy Test:** `POST /coach/messages` with `{"utterance": "Can I afford dinner tonight?"}` $\rightarrow$ Expect grounded response with `suggest_intent`.
   - **Deep Analytics Test:** `GET /analytics/deep-ledger` $\rightarrow$ Expect AG Grid compatible transaction rows.

---

## 7. APIMatic Integration for Cursor

To maintain perfect context synchronization in Cursor:
1. Export the OpenAPI schema:
   ```powershell
   curl http://localhost:8000/openapi.json -o docs/openapi.json
   ```
2. Upload `docs/openapi.json` to [APIMatic](https://www.apimatic.io/).
3. Generate typed client libraries or Markdown API context docs.
4. Reference the generated context in Cursor prompts to ensure that route handlers, payload shapes, and status codes match exactly without hallucinations.

---

## 8. Foundational Render Cloud Hosting (Sponsor Prize Guide)

Deploying FireWallet on **Render** is our foundational cloud hosting solution. It satisfies the hackathon live hosted demo requirement and strongly positions FireWallet for the **Render Sponsor Prize**.

> [!IMPORTANT]
> **Live Production Submission URL:** Include the live production URL generated by Render (`https://firewallet-web.onrender.com`) in your Devpost submission form under the *Live Demo / Website* field. Judges can immediately experience the live PWA and desktop AG Grid view without installing local dependencies.

### 8.1. How the Project is Hosted & Containerized on Render

FireWallet is configured for zero-friction cloud deployment on Render using two interchangeable approaches:
1. **Native Render Blueprint (Default):** Defined in `render.yaml`, leveraging Render's managed Python 3 environment for the API and static web server for React.
2. **Containerized Docker Deployment (Optional):** A multi-stage `Dockerfile` in `backend/` allows deployment as an isolated container web service if custom C extensions or Alpine runtimes are needed.

### 8.2. Blueprint Specification: `render.yaml`

The `render.yaml` blueprint at the repository root orchestrates all three production components:

```yaml
services:
  # 1. Backend Web Service (FastAPI)
  - type: web
    name: firewallet-api
    env: python
    region: oregon
    plan: starter
    buildCommand: "cd backend && pip install -e ."
    startCommand: "cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: firewallet-db
          property: connectionString
      - key: PAYPAL_ENV
        value: sandbox
      - key: PAYPAL_BASE_URL
        value: https://api-m.sandbox.paypal.com
      - key: PAYPAL_CLIENT_ID
        sync: false
      - key: PAYPAL_CLIENT_SECRET
        sync: false
      - key: PAYPAL_WEBHOOK_ID
        sync: false
      - key: LLM_API_KEY
        sync: false
      - key: LLM_BASE_URL
        value: https://api.openai.com/v1
      - key: LLM_MODEL
        value: gpt-4o-mini

  # 2. Frontend Static Site (React + Tailwind + AG Grid)
  - type: static
    name: firewallet-web
    buildCommand: "cd frontend && npm install && npm run build"
    staticPublishPath: "frontend/dist"
    envVars:
      - key: VITE_API_BASE
        fromService:
          type: web
          name: firewallet-api
          property: host

databases:
  # 3. Managed PostgreSQL Database
  - name: firewallet-db
    plan: starter
    region: oregon
```

### 8.3. Step-by-Step Render Deployment Instructions:
1. Push your repository to GitHub.
2. Log in to your [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** $\rightarrow$ Select **Blueprint**.
4. Select your GitHub repository. Render automatically reads `render.yaml` and sets up:
   - `firewallet-db`: Managed PostgreSQL database.
   - `firewallet-api`: FastAPI Web Service.
   - `firewallet-web`: React Static Site.
5. In the Render Dashboard under `firewallet-api` $\rightarrow$ **Environment**, supply your secret values:
   - `PAYPAL_CLIENT_ID`
   - `PAYPAL_CLIENT_SECRET`
   - `LLM_API_KEY`
6. Once deployed, copy your API URL: `https://firewallet-api.onrender.com`.
7. Go to your [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications/sandbox) and update your Webhook URL to:
   ```
   https://firewallet-api.onrender.com/webhooks/paypal
   ```
8. Verify that the static site at `https://firewallet-web.onrender.com` loads the mobile HUD, connects to the live API, and allows toggling to the desktop AG Grid view.
