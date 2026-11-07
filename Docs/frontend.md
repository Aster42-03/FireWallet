# Frontend (React + Vite + Tailwind PWA + AG Grid)

FireWallet’s frontend is a **mobile-first, installable Progressive Web App (PWA)** built with **React**, **Vite**, and **Tailwind CSS**, featuring an enterprise **AG Grid** desktop deep analytics layer. Node.js environment is managed via **fnm**.

The UI is built on a **dual-surface architecture**:
1. **Mobile-First HUD (`/`):** Minimalist, thumb-driven Heads-Up Display featuring Tailwind cards for the Trinity buckets, a Quick Intent FAB, and an AI chat coach drawer.
2. **Desktop Admin & Deep Analytics View (`/analytics/deep-ledger`):** Enterprise-grade transaction ledger powered by **AG Grid**, offering rich multi-column filtering, sorting, grouping, and direct analytical queries with the Advanced Reasoning Coach.

Related: [TOOL_STACK.md](TOOL_STACK.md), [ARCHITECTURE.md](ARCHITECTURE.md), [insights.md](insights.md), [api_contracts.md](api_contracts.md).

---

## 1. Information Architecture (IA)

| Route | Viewport Focus | Component / Surface | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | Mobile First | `features/hud/` | **Mobile Home HUD:** Minimalist Tailwind cards for Bank, Daily + rollover, safe Vault/Bills, Freedom meter, embedded charts, Coach drawer, Quick Intent FAB |
| `/analytics/deep-ledger` | Desktop / Tablet | `features/analytics/DeepLedgerGrid.jsx` | **Foundational Desktop View:** "Advanced Ledger & Audit Log" powered by AG Grid with multi-sort, category grouping, and "Analyze with Coach" |
| `/intent` | Mobile First | `features/intent/` | Quick Intent modal / screen: Amount, natural language *why*, merchant, agent verdict, PayPal redirect |
| `/intent/:id` | Mobile First | `features/intent/` | Detailed intent verdict, category breakdown, PayPal approval status, return redirect |
| `/override/:id` | Mobile First | `features/override/` | Escape Window: Confession textarea, live server cooldown countdown, partner status |
| `/coach` | Both | `features/coach/` | Full-screen Coach view with Advanced Reasoning Model (also accessible as a slide-up drawer on `/`) |
| `/bills` | Both | `features/bills/` | Priority bill schedule (rent first), pay-now manual trigger |
| `/settings` | Both | `features/settings/` | Policy sliders (skim %, daily target, freedom monthly, partner email, timezone) |
| `/pay/return`, `/pay/cancel` | Mobile First | `features/intent/` | PayPal sandbox OAuth and checkout return handlers |

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
