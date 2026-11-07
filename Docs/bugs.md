# FireWallet Bug Tracker

This document tracks known issues, edge cases, and architectural bugs deferred for resolution in upcoming development phases.

---

## BUG-001: AI Coach Chat Messages and Responses Doubling

- **Bug ID**: `BUG-001`
- **Component**: Frontend (`frontend/src/features/coach/CoachDrawer.jsx`, `frontend/src/App.jsx`), AI Coach Integration
- **Severity**: Medium
- **Status**: **Logged (Deferred to Phase 3 - Coach Agent Implementation)**
- **Reported**: 2026-11-07
- **Target Fix Milestone**: Phase 3 (AI Coach Full Agent Architecture & Autonomous Workflows)

### 1. Description
When sending a query to the AI Financial Coach in the UI (via either 1-tap analytical chips or direct text submission), the user's message appears twice in the chat stream, and the coach returns two identical responses in parallel.

### 2. Steps to Reproduce
1. Navigate to the **Deep Ledger / AG Grid Analytics** workbench (`/analytics/deep-ledger`) or open the Coach drawer from the top HUD.
2. Click any analytical prompt chip (e.g. *"Explain Bank Flows"*, *"Diagnose Velocity"*) or type a message in the input box and hit Send.
3. Observe the chat feed in `CoachDrawer`:
   - Two duplicate user chat bubbles appear in immediate succession.
   - Two duplicate assistant responses are generated and appended.

### 3. Root Cause Analysis
Preliminary analysis indicates several contributing factors:

1. **`useEffect` Re-execution on `initialQuery` Prop**:
   In `CoachDrawer.jsx`:
   ```javascript
   React.useEffect(() => {
     if (initialQuery) {
       handleSend(initialQuery);
     }
   }, [initialQuery]);
   ```
   - In React 18+ (especially with `<React.StrictMode>` during local development), `useEffect` runs twice on component mount.
   - When `initialQuery` is populated by `App.jsx`, both effect passes invoke `handleSend()`.
   - Furthermore, `initialQuery` in `App.jsx` state is not reset to `''` after `CoachDrawer` consumes it, causing re-triggers on parent re-renders.

2. **Concurrent State Dispatch & Race Condition**:
   - `handleSend()` immediately appends a new user message to `messages` via `setMessages(prev => [...prev, userMsg])` before awaiting the network response.
   - If two invocations run nearly simultaneously before `loading` state locks the input, two separate network requests are dispatched to `/api/v1/coach/messages`.
   - When both HTTP responses resolve, both assistant responses are appended to the message array.

### 4. Proposed Solution (To Be Executed in Phase 3)
1. **Ref-based Deduplication in `CoachDrawer.jsx`**:
   - Use an `executedQueryRef = useRef(null)` or `hasFiredRef = useRef(false)` to ensure each specific `initialQuery` executes at most once per lifecycle.
   - Reset the ref only when `initialQuery` changes to a distinct new string or when the drawer closes.
2. **Clear Initial Query in Parent (`App.jsx`)**:
   - Add a callback `onClearInitialQuery={() => setCoachInitialQuery('')}` so the parent state is cleared immediately after the query is accepted by the coach component.
3. **In-Flight Request Guard & AbortController**:
   - Guard `handleSend` with a ref check `if (isSendingRef.current) return;` in addition to React state `loading`.
   - Attach an `AbortController` to cancel any redundant in-flight request if a new one is explicitly triggered.
4. **Backend Message Deduplication (Optional)**:
   - Pass an `idempotency_key` or `client_message_id` from the frontend to `/api/v1/coach/messages` to guarantee at-most-once processing on the server.
