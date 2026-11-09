# Frontend (React + Vite + Tailwind Web App + AG Grid)

FireWallet’s frontend is a **mobile-first responsive web app** built with **React**, **Vite**, and **Tailwind CSS**, featuring an enterprise **AG Grid** desktop deep analytics layer. Node.js environment is managed via **fnm**.

The UI is built on a **dual-surface architecture** implemented as a clean, responsive Single-Page Application (SPA) with dynamic in-app surface toggling:
1. **Mobile HUD Surface (`view='hud'`):** Minimalist, thumb-driven Heads-Up Display featuring Tailwind cards for the Trinity buckets, the **Protected HUD Panel** (rent protected, impulse blocked, rollover streak), a Quick Intent FAB, and an AI chat coach drawer.
2. **Desktop Admin & Deep Analytics Surface (`view='deep-ledger'`):** Enterprise-grade transaction ledger powered by **AG Grid**, offering rich multi-column filtering, sorting, grouping, and direct analytical queries with the Advanced Reasoning Coach.

Related: **[problems.md](problems.md) (Core Build & Frontend Gate)**, [TOOL_STACK.md](TOOL_STACK.md), [architecture.md](architecture.md), [insights.md](insights.md), [api_contracts.md](api_contracts.md).

> [!IMPORTANT]
> **Frontend Verification Gate ([problems.md](problems.md)):**
> Every UI change must satisfy the frontend requirements in **[problems.md](problems.md)**:
> - **Problem 2 (Judge-Proof Controls):** Clearly labeled demo simulation controls (`Reset Demo Data`, `Simulate Next Day` rollover, `Simulate Payday` Vault payout).
> - **Problem 3 (Voluntary Commitment):** Explicit onboarding commitment confirmation step and deterministic **Protected Panel** on the Mobile HUD.
> - **Problem 9 (AG Grid Depth):** Zero trial/license watermark, master/detail transfer inspection (`transfer_id`), and live Coach anomaly row highlighting.

---

## 1. Information Architecture (IA)

| Surface / State | Viewport Focus | Component / Modal | Purpose |
| :--- | :--- | :--- | :--- |
| `view='hud'` | Mobile First | `features/hud/MobileHUD.jsx` | **Mobile Home HUD:** Minimalist Tailwind cards for Bank, Daily + rollover streak, safe Vault (Emergency Reserve + Goals), Bills earmark, Freedom meter, embedded charts, Coach drawer, Quick Intent FAB |
| `view='deep-ledger'` | Desktop / Tablet | `features/analytics/DeepLedgerGrid.jsx` | **Foundational Desktop View:** "Advanced Ledger & Audit Log" powered by AG Grid with multi-sort, category grouping, telemetry chips, and "Analyze with Coach" |
| Intent Modal | Mobile First | `features/intent/QuickIntentModal.jsx` | Quick Intent modal: Amount, natural language *why*, merchant, agent verdict (`CoachDecision`), 1-tap `ActionCard`, and PayPal redirect |
| Config Modal | Mobile First | `features/hud/BucketConfigModal.jsx` | Envelope customization: Daily target, Freedom monthly cap, Vault skim %, and friction parameters |
| Override Modal | Mobile First | `features/override/EscapeWindowModal.jsx` | Escape Window: 200-char confession textarea, live countdown timer, and emergency zero-delay detection |
| Coach Drawer | Both | `features/coach/CoachDrawer.jsx` | Monolithic Coach chat drawer with live LLM generation, RAG short-tag memory, and 1-tap action cards |

---

## 2. Surface 1: The Mobile HUD Layout (`/`)

The mobile view is intentionally clean, calm, and uncluttered. It presents the Trinity buckets as clear, high-contrast Tailwind cards:

```
┌──────────────────────────────────────────────────┐
│  FIREWALLET                          [Profile ⚙] │
├──────────────────────────────────────────────────┤
│  BANK FOUNDATION                                 │
│  $800.00  🔒 Locked (Direct spend needs override)│
├──────────────────────────────────────────────────┤
│  DAILY ALLOWANCE                                 │
│  $52.00   Available                              │
│  [✦ Target: $40.00  |  +$12.00 Rollover from Sun]│
├──────────────────────────────────────────────────┤
│  OUT-OF-SIGHT RESERVES                           │
│  🛡️ Vault: $200.00 (Locked)  |  🏠 Rent: $1,200  │
├──────────────────────────────────────────────────┤
│  FREEDOM ENVELOPE (HEDONISM)                     │
│  $90.00 / $150.00 remaining this month           │
│  ████████████████░░░░░░░░░░░░░░░░  60% Left      │
├──────────────────────────────────────────────────┤
│  7-DAY SPENDING ANALYTICS                        │
│  [ Pie Chart: Groceries 66% / Takeout 34% ]      │
│  [💬 Ask Coach about this chart]                 │
├──────────────────────────────────────────────────┤
│  INSIGHTS COACH DOCK                             │
│  "You're on track! Tap below to ask anything."   │
│  [ Quick Pill: "Can I afford dinner tonight?" ]  │
└──────────────────────────────────────────────────┘
                            ┌──────────────────────┐
                            │ (⚡ Quick Intent) FAB│
                            └──────────────────────┘
```

### Key Mobile HUD Highlights:
- **Bank Foundation Card:** Displays core liquidity with a lock icon, reminding the user that foundation money is protected.
- **Daily Living Hero:** Prominent typography with an encouraging green badge highlighting accumulated rollover (`+$12.00 Rollover`).
- **Out-of-Sight Strip:** Displays locked Vault savings and earmarked Bills in a muted strip, preventing impulse mental accounting.
- **Freedom Meter:** Visual burn bar that tracks discretionary spending without shame.
- **Quick Intent Floating Action Button (FAB):** Pinned in the natural bottom-right thumb zone for 1-tap spend logging.
- **Coach Drawer:** Slides up on demand without navigating away from the HUD.

---

## 3. Surface 2: Foundational Desktop Admin & Deep Analytics View (`/analytics/deep-ledger`)

When viewed on desktop (or accessed via the **"Advanced Ledger & Audit Log"** tab), FireWallet expands into a high-density, professional financial workbench powered by **AG Grid**:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FIREWALLET DESKTOP ADMIN       [Mobile HUD]  [★ Advanced Ledger & Audit Log]  [Settings ⚙]             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  DEEP ANALYTICS & AUDIT WORKBENCH                                         [Export CSV] [Analyze 🤖]    │
│  Filters: [Bucket: All ▼] [State: All ▼] [Date: Last 90 Days ▼] [Category: All ▼]  [Search: _______]   │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Date       | Category    | Bucket   | Amount    | State    | Utterance         | PayPal Order ID │  │
│  │────────────|─────────────|──────────|───────────|──────────|───────────────────|─────────────────│  │
│  │ 2026-10-28 | groceries   | daily    | -$24.50   | posted   | Trader Joe's run  | 5O190127TN...   │  │
│  │ 2026-10-27 | bills       | bills    | -$1,200.0 | posted   | November Rent     | P-8XY987654...  │  │
│  │ 2026-10-26 | eating_out  | freedom  | -$35.00   | posted   | Late-night ramen  | 3K281920PQ...   │  │
│  │ 2026-10-25 | savings     | vault    | +$200.00  | posted   | Payday 20% skim   | P-1AB234567...  │  │
│  │ 2026-10-24 | eating_out  | bank     | -$48.00   | posted   | Override Confess. | 9L482019MN...   │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  DEEP COACH INTELLIGENCE PANEL                                                                         │
│  Selection: 14 transactions in "eating_out" (Total: $248.00)                                           │
│  Coach Analysis: "Dining out increased 42% over the last 14 days, primarily driven by three weekend   │
│  orders. Your Daily rollover cushion absorbed 60% of this, but Freedom is now within $12 of empty."  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### AG Grid Enterprise Features:
1. **Multi-Column Sorting & Pinning:** Sort simultaneously by Date, Category, and Amount. Pin Bucket and State columns.
2. **Category & Bucket Grouping:** Group transactions by Trinity bucket (`bank`, `daily`, `freedom`, `vault`, `bills`) with automatic subtotal aggregations.
3. **Transaction State Segmentation:** Differentiates between `hold` (active PayPal intent checkout), `posted` (settled debit), and `released` (canceled/expired holds).
4. **Audit Metadata Transparency:** Directly inspects `transfer_id`, `paypal_order_id`, `paypal_capture_id`, and webhook event hashes for full compliance.
5. **Interactive "Analyze with Coach" Action:** Selecting one or more rows and clicking the "Analyze" button instantly sends the filtered dataset to the Advanced Reasoning Coach for deep diagnostic review.

---

## 4. Deep Analysis Layer & Advanced Reasoning Integration

The desktop AG Grid and the Financial Coach work synchronously:
- When a user filters AG Grid (e.g. showing only `category='groceries'` over the last 60 days), the grid emits the current active filter state.
- Clicking **"Analyze with Coach"** dispatches the grid query parameters to `POST /coach/messages`.
- The Coach runs an **Advanced Reasoning Model** over `backend/app/analytics/deep_analytics.py`, computing:
  - **Spending Velocity:** Burn rate per day compared to the prior period.
  - **Category Drift:** Unplanned increases relative to target allocations.
  - **Outlier Anomalies:** Flagged transactions exceeding $2\sigma$ above normal frequency.
- The Coach returns structured analytical insights directly below the AG Grid table, complete with citations and actionable guidance.

---

## 5. Tailwind Design System & Responsive Tokens

- **Responsive Breakpoints:**
  - `<768px` (Mobile): Defaults strictly to the minimalist Mobile HUD (`/`).
  - `≥768px` (Tablet/Desktop): Unlocks top navigation with direct access to the **"Advanced Ledger & Audit Log"** AG Grid workbench.
- **Palette Tokens:**
  - Bank: `bg-slate-900 border-slate-700 text-slate-100` (Foundation, locked security).
  - Daily: `bg-emerald-950/40 border-emerald-800 text-emerald-300` (Fluid, healthy living).
  - Freedom: `bg-purple-950/40 border-purple-800 text-purple-300` (Guilt-free hedonism).
  - Vault: `bg-amber-950/40 border-amber-800 text-amber-300` (Locked savings).
  - Bills: `bg-sky-950/40 border-sky-800 text-sky-300` (Fixed obligations).
  - Firewall Alert: `bg-rose-950/50 border-rose-800 text-rose-300` (Friction required).

---

## 6. Coach Drawer Animations & Progressive Auto-Scroll Architecture

The Financial Coach drawer (`CoachDrawer.jsx`) provides a polished, responsive conversational experience:

1. **Hardware-Accelerated Sliding Animation**:
   - Replaced abrupt modal cut-ins with smooth keyframe animations defined in `frontend/src/index.css`:
     - `@keyframes drawerSlideIn`: Slides the drawer panel from `translateX(100%)` to `translateX(0)` over 300ms using the cubic-bezier easing `cubic-bezier(0.16, 1, 0.3, 1)`.
     - `@keyframes backdropFadeIn`: Gently fades in the dark backdrop (`opacity: 0` to `opacity: 1` over 250ms).
     - Clicking the backdrop safely triggers `onClose()`.
   - Each chat bubble transitions smoothly into the conversation using `animate-message-appear` (`translateY(6px)` to `translateY(0)`).
2. **Progressive Typewriter Streaming Reveal**:
   - Rather than popping a full markdown block into the view at once, newly arrived assistant responses stream smoothly chunk-by-chunk via an interval ticker (`stepTimeMs = 20`, dynamic chunk size scaled to total message length).
   - A pulsating cursor (`animate-pulse`) indicates live writing.
   - 1-Tap Action Cards and RAG citation tags are gracefully withheld until streaming concludes, fading in cleanly once generation is complete.
3. **Continuous Auto-Scrolling**:
   - Coupled with `messagesEndRef` and `scroll-smooth`, the drawer continuously scrolls downward at every streaming tick.
   - The user never has to manually drag the scrollbar to keep up with the response; the text reveals itself and scrolls into view naturally.
4. **Live LLM Connection Status Pill**:
   - The drawer header queries `GET /api/v1/coach/status` via `fetchCoachStatus()` and presents a real-time status pill (e.g. `Live: gpt-oss-120b` with a pulsating green beacon).
   - If offline or unconfigured, the pill cleanly indicates `Deterministic Engine Heuristic`.
   - Each generated response tags the generating model (`msg.model`), ensuring full visibility into real AI reasoning.
