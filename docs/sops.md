# Standard Operating Procedures (SOPs)

Operational runbooks for running, smoke-testing, and deploying **FireWallet** locally and on **Render**.

Related: **[problems.md](problems.md) (Core Build & Verification Gate)**, [SETUP_GUIDE.md](SETUP_GUIDE.md), [manual.md](manual.md), [architecture.md](architecture.md).

> [!IMPORTANT]
> **Pre-Submission Verification Gate ([problems.md](problems.md)):**
> Every build and release must pass the **End-to-End PayPal Smoke Check (Problem 1)** and the **Fresh-Clone Judge Dry Run (Problem 2)** documented in **[problems.md](problems.md)** before submission.

---

## 1. Prerequisites

| Tool | Purpose |
| :--- | :--- |
| **[uv](https://docs.astral.sh/uv/)** | Python 3.12+ package manager, lockfile (`uv.lock`), and script runner |
| **[fnm](https://github.com/Schniz/fnm) + npm** | Node 20+ version manager and frontend package manager |
| **SQLite / PostgreSQL 16+** | Dual-engine relational ledger: **SQLite** (`sqlite+aiosqlite`) for zero-config local dev; **PostgreSQL 16+** (`postgresql+asyncpg`) for Render production and row-lock concurrency testing |
| **PayPal Developer Sandbox** | Live sandbox money movement (`api-m.sandbox.paypal.com`): Orders v2, Captures, Payouts, Reporting Balances, Webhooks |
| **Public HTTPS Tunnel** | `ngrok` or Cloudflare Tunnel for receiving signed PayPal webhooks locally at `/api/v1/webhooks/paypal` |
| **Groq / OpenAI API Key** | Live LLM inference (`openai/gpt-oss-120b` primary on Groq, `gpt-4o-mini` fallback) |

---

## 2. One-Time Machine & PayPal Sandbox Setup

1. Create a Sandbox REST application at <https://developer.paypal.com/> (`Apps & Credentials → Sandbox`).
2. Copy the `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`.
3. Under `Sandbox → Accounts`, note the emails/credentials for:
   - **Personal Buyer Account:** Approves checkout Orders.
   - **Business Merchant Account:** App owner (`FireWallet`).
   - **Vault Receiver Account:** Destination for automated payday savings skims (`PAYPAL_VAULT_RECEIVER_EMAIL`).
   - **Bill Payee Account:** Destination for scheduled rent/utility disbursements (`PAYPAL_BILL_PAYEE_EMAIL`).
4. Register the webhook URL in the PayPal Developer Dashboard pointing to **`https://<your-host>/api/v1/webhooks/paypal`** and subscribe to `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, and `PAYMENT.PAYOUTSBATCH.SUCCESS`.

---

## 3. Environment Configuration (`backend/.env`)

Never commit `.env` to git. Copy `backend/.env.example` to `backend/.env`:

```ini
# Dual-Engine Database: Default zero-config SQLite locally, PostgreSQL in production
DATABASE_URL=sqlite+aiosqlite:///./firewallet.db
# DATABASE_URL=postgresql+asyncpg://firewallet:firewallet@localhost:5432/firewallet

# PayPal Sandbox Configuration
PAYPAL_ENV=sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret
PAYPAL_WEBHOOK_ID=your_paypal_sandbox_webhook_id
PAYPAL_VAULT_RECEIVER_EMAIL=vault-receiver@sandbox.paypal.com
PAYPAL_BILL_PAYEE_EMAIL=landlord@sandbox.paypal.com

# Primary LLM Configuration (Groq)
GROQ_API_KEY=your_groq_api_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-120b

# Secondary LLM Fallback Configuration (OpenAI-compatible)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_openai_or_gemini_api_key
LLM_MODEL=gpt-4o-mini

# Public URLs & CORS
APP_PUBLIC_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Frontend (`frontend/.env`):
```ini
VITE_API_BASE=http://localhost:8000
```

---

## 4. Local Run Sequence (Happy Path)

```bash
# Terminal 1 — Backend API (Port 8000)
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.jobs.seed
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend SPA (Port 5173)
cd frontend
npm install
npm run dev
```

- **Interactive Swagger UI:** `http://localhost:8000/docs`
- **Web App (Mobile HUD & Desktop AG Grid):** `http://localhost:5173`
- **Coach Connectivity Status:** `http://localhost:8000/api/v1/coach/status`

---

## 5. Automated & Manual Verification Matrix (Aligned with [problems.md](problems.md))

### A. Automated Pytest Suite (`Zero Warnings`)
```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest tests/ -W error
```
Covers:
- **Trinity Bucket Invariants:** Rollover top-up without reset, Bills priority over Vault skim on short income, Freedom hard stop, Bank Foundation lock, and Vault lock verification.
- **Double-Entry Zero-Sum Ledger:** Paired `transfer_id` legs summing to `0` in minor units (cents), running balances, and `HOLD → settle / release` transitions.
- **PayPal Balance Sync & Policy Re-allocation:** Live/simulated balance sync (`POST /api/v1/paypal/sync-balance`) and envelope updates (`PUT /api/v1/me/policy`).
- **Webhook Idempotency & Atomic Rollback:** Duplicate `event_id` handling (`200 OK` without double-posting) and status transitions (`pending → processed`).
- **Monolithic Agent & RAG Short-Tags:** Structured `CoachDecision` + 1-tap `ActionCard`, topic-specific diagnostic chips (`BUG-007`), and emergency detection.

### B. End-to-End PayPal Smoke Check ([problems.md](problems.md) Problem 1 Gate)
Run against both local tunnel and the live **Render** URL:
1. Obtain OAuth 2.0 client-credentials token (`POST /v1/oauth2/token`).
2. Create an allowed spend intent (`POST /api/v1/intents`) and execute checkout (`POST /api/v1/intents/{id}/execute`) with `PayPal-Request-Id`.
3. Approve Order as the sandbox buyer and capture (`POST /api/v1/intents/{id}/capture`).
4. Confirm signed webhook delivery at `POST /api/v1/webhooks/paypal` transitions `paypal_webhook_events.status` to `processed` and settles the ledger `HOLD`.
5. Trigger Payday (`POST /api/v1/paypal/payday`) to execute a PayPal Payout to `PAYPAL_VAULT_RECEIVER_EMAIL` and verify `SUCCESS` in the receiver's sandbox activity.
6. Replay the capture and payout events twice to confirm zero double-posting.

---

## 6. Webhook Local & Hosted SOP

1. Ensure the webhook endpoint is registered at **`https://<host>/api/v1/webhooks/paypal`** (always include the `/api/v1` prefix).
2. In production on Render, cryptographic signature verification against `PAYPAL_WEBHOOK_ID` must always be active; never enable dev signature-skip flags in hosted environments.
3. If the local `ngrok` / Cloudflare tunnel hostname changes, update the webhook URL in the PayPal Developer Dashboard immediately so captures do not remain in `executing`.

---

## 7. Incident Troubleshooting

| Symptom | Root Cause & Fix |
| :--- | :--- |
| **Captures stay in `executing`** | PayPal Dashboard webhook URL is missing `/api/v1` (must be `/api/v1/webhooks/paypal`) or `PAYPAL_WEBHOOK_ID` is mismatched. |
| **Coach badge shows `local_fallback`** | `GROQ_API_KEY` / `LLM_API_KEY` is unset or a placeholder in `backend/.env`. Check `GET /api/v1/coach/status`. |
| **PayPal 401 Unauthorized** | Mixing live credentials with `https://api-m.sandbox.paypal.com`. Use Sandbox app credentials only. |
| **Frontend cannot reach API on Render** | Verify `VITE_API_BASE` is set to the full public `https://` API URL and `CORS_ORIGINS` includes the static site origin. |
