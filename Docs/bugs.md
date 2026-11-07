# FireWallet Bug Tracker

This document tracks known issues, edge cases, and architectural bugs across development phases.

---

## BUG-001: AI Coach Chat Messages and Responses Doubling

- **Bug ID**: `BUG-001`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/App.jsx`), AI Coach Integration
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
When sending a query to the AI Financial Coach in the UI (via either 1-tap analytical chips or direct text submission), the user's message appeared twice in the chat stream, and the coach returned two identical responses in parallel.

### 2. Root Cause
1. **`useEffect` Double Invocation in React 18 `<StrictMode>`**:
   `useEffect(() => { if (initialQuery) handleSend(initialQuery); }, [initialQuery])` fired twice on mount while `coachInitialQuery` in `App.jsx` remained populated.
2. **Asynchronous React State Race Condition**:
   `handleSend()` relied solely on React `loading` state rather than a synchronous `useRef` lock, allowing back-to-back calls to dispatch parallel `POST /api/v1/coach/messages` requests.

### 3. Resolution Implemented
1. Added synchronous `isSendingRef` lock and `lastProcessedInitialRef` guard inside `frontend/src/features/coach/CoachDrawer.jsx`.
2. Added `onClearInitialQuery` callback in `frontend/src/App.jsx` so `coachInitialQuery` is cleared immediately upon consumption.
3. Attached an `AbortController` (`signal`) to `sendCoachMessage` in `frontend/src/shared/api.js` and `CoachDrawer.jsx` to cancel stale in-flight requests cleanly on unmount.

---

## BUG-002: Quick Intent Bucket Not Found (Dual-Database Divergence)

- **Bug ID**: `BUG-002`
- **Component**: Backend (`app/core/config.py`, `app/api/v1/auth.py`, `app/api/v1/intents.py`)
- **Severity**: High
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
In the Quick Intent tab, users received an error stating `"Bucket 'freedom' not found"`, blocking all intent evaluations and prevent payments from passing through.

### 2. Root Cause
1. **SQLite Database Path Divergence**: When starting the FastAPI server from `backend/` working directory, SQLite relative path `sqlite+aiosqlite:///./firewallet.db` evaluated to `backend/firewallet.db`. Because previous Alembic migrations and seed scripts were executed from the root directory, root `firewallet.db` had seeded buckets while `backend/firewallet.db` was unseeded or had a user without buckets.
2. **Missing Auto-Provisioning Guard**: `get_current_user` assumed pre-existing buckets and threw a 404 instead of auto-provisioning the 5 core Trinity buckets (`bank`, `daily`, `freedom`, `vault`, `bills`).

### 3. Resolution Implemented
1. Added `resolve_database_url()` in `backend/app/core/config.py` that resolves relative SQLite database paths strictly against the canonical repository root path (`BASE_DIR.parent / "firewallet.db"`).
2. Added auto-provisioning in `backend/app/api/v1/auth.py` inside `get_current_user()`: if a user lacks the 5 Trinity buckets, they are automatically initialized and committed atomically.
3. Synced root `firewallet.db` to `backend/firewallet.db`.

---

## BUG-003: Coach Predetermined Robotic Response Missing Human Warmth

- **Bug ID**: `BUG-003`
- **Component**: Backend LLM Orchestration (`backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
When sending conversational greetings like `"hello"`, `"hey coach"`, or general inquiries, the coach responded with a cold, canned robotic boilerplate (`"Trinity Coach Evaluation: You have requested..."`) lacking personal financial context, warmth, and natural conversation.

### 2. Root Cause
The fallback cascade in `call_unified_coach` used a rigid template assuming every prompt was a strict spend inquiry, ignoring greetings, conversational inquiries, and dynamic ledger context (user name, daily balance, rollover streak).

### 3. Resolution Implemented
1. Replaced static template with dynamic context-aware conversational generation in `backend/app/agents/shared/llm_client.py`.
2. Incorporated user's name (`Aster`), daily balance, freedom balance, and rollover streak directly into conversational greetings and check-ins.
3. Errors now log full tracebacks to `logger.error` while communicating clear, warm, natural language explanations to the user without robotic jargon.

---

## BUG-004: Missing 1-Tap Action Cards for Words & Dollar Inquiries

- **Bug ID**: `BUG-004`
- **Component**: Backend RAG & Coach Engine (`backend/app/agents/rag.py`, `backend/app/agents/insights/coach.py`, `backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
The 1-tap action button was missing when users asked about common spending activities without typing an explicit `$` symbol (e.g. `"fifteen dollars"`, `"twenty bucks"`, `"50 cents"`, or `"Can I buy a coffee?"`).

### 2. Root Cause
1. Regex only recognized `\$\d+` syntax, ignoring word numbers (`twenty dollars`, `fifty cents`) and currency terms (`bucks`, `usd`).
2. Spend prompts without explicit amounts were assigned `action_type: "none"` without inferring common standard defaults.

### 3. Resolution Implemented
1. Built `parse_amount_cents_from_text()` in `backend/app/agents/rag.py` supporting `$XX`, numbers + words (`15 dollars`, `50 cents`), and full word numbers (`twenty dollars`, `fifteen bucks`, `fifty cents`).
2. Added default amount inference in `call_unified_coach` for common spend queries (`coffee`: $5.00, `takeout`: $18.00, `groceries`: $35.00, `vault sweep`: $25.00), automatically presenting ready-to-pay 1-tap action cards.

---

## BUG-005: Raw Markdown Unrendered in Coach Chat Bubbles

- **Bug ID**: `BUG-005`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/features/coach/MarkdownRenderer.jsx`)
- **Severity**: Low
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
Coach messages containing markdown syntax (`**bold**`, `*italics*`, `### headers`, `- bullets`, `` `code` ``) rendered as raw text characters instead of formatted rich typography.

### 2. Root Cause
`CoachDrawer.jsx` was rendering `msg.content` directly inside a text `<div>`.

### 3. Resolution Implemented
1. Created lightweight zero-dependency `MarkdownRenderer.jsx` parsing bold, italics, inline code, headers, bullet lists, and numbered lists.
2. Integrated `MarkdownRenderer` into `CoachDrawer.jsx`.

---

## BUG-006: Quick Chat Buttons Failing to Output Messages & Missing Insight Actions

- **Bug ID**: `BUG-006`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/features/hud/MobileHUD.jsx`, `frontend/src/App.jsx`), Backend Insights (`backend/app/agents/shared/llm_client.py`)
- **Severity**: Medium
- **Status**: **Resolved (Fixed in Phase 3)**
- **Reported**: 2026-11-07
- **Resolved**: 2026-11-07

### 1. Description
1. When clicking the quick chat buttons in Mobile HUD (e.g. "Can I afford the $20 movie ticket?"), the Coach drawer opened but no user message or coach reply was outputted to the chat stream.
2. The quick chat buttons were hardcoded to sample spending questions rather than informative financial insights (such as explaining rollover streak, why Bank is locked, vault sweep mechanics, and velocity diagnostics).

### 2. Root Cause
1. **StrictMode Mount-Abort Race Condition**:
   - In `CoachDrawer.jsx`, `useEffect` had an unmount cleanup function: `return () => { abortControllerRef.current?.abort(); }`.
   - In React 18 development mode (`<StrictMode>`), opening the drawer mounted the component, dispatched `handleSend`, and simultaneously called `onClearInitialQuery?.()` which set `coachInitialQuery = ""` in `App.jsx`.
   - React StrictMode immediately ran cleanup (invoking `abort()`, dropping the in-flight request) and remounted the component.
   - On remount, `initialQuery` was already `""` (cleared by the first mount), leaving `messages` reset to the initial welcome state with no message ever sent or received.
2. **Re-render Dependency Churn**: `handleSend` had `input` in its dependency array, recreating the function on every keystroke and causing effect dependency churn.
3. **Missing First-Class Insight Handlers**: In `llm_client.py`, questions regarding rollover streak, Bank locking, or Escape Window friction lacked structured mock and fallback handlers.

### 3. Resolution Implemented
1. **Structured Query ID Tracking**:
   - In `App.jsx`, `handleOpenCoachWithQuery` passes a unique query object: `{ id: timestamp, text: query }`.
   - In `CoachDrawer.jsx`, `lastProcessedIdRef` tracks dispatched query IDs, executing `handleSend` exactly once per unique button tap even under StrictMode.
   - Decoupled `input` from `handleSend` via `inputRef` so keystrokes do not recreate callback references.
   - Scoped `abortController` cleanup strictly to drawer close events (`!isOpen`), preventing initial mount unmounts from killing in-flight queries.
2. **Dedicated Insight Quick Chips in HUD and Coach**:
   - Replaced sample spending buttons in `MobileHUD.jsx` with actual financial insights:
     - `✦ Explain rollover streak`
     - `🔒 Why is Bank locked?`
     - `⚡ How Vault sweep works`
     - `📊 Diagnose spend velocity`
     - `🔥 Escape Window friction`
   - Added an interactive Quick Insight Suggestion Chips bar inside `CoachDrawer.jsx` directly above the chat input form for one-tap insight exploration.
3. **Structured Backend Insight Handlers**:
   - Added explicit handlers in `backend/app/agents/shared/llm_client.py` and `rag.py` delivering rich Markdown explanations for rollover streaks, Rule 4 locked Bank Foundation, and Escape Window friction.
   - Verified via unit and API integration tests in `tests/unit/test_phase3_agent_and_rag.py`.
