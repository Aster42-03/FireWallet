# Product Specification

**FireWallet** is a **proactive, voluntary-commitment financial firewall and budgeting web application** powered by the **Trinity** bucket architecture. It restricts liquidity **before** impulsive spending occurs through an intent-first PayPal gateway (`propose → verify → confirm → execute`), while building long-term financial literacy through a minimalist mobile HUD, an enterprise AG Grid desktop ledger, and a reactive AI Financial Coach.

Related: **[problems.md](problems.md) (Core Build Gate)**, [hackathon_overview.md](hackathon_overview.md), [TRINITY_RULES.md](TRINITY_RULES.md), [insights.md](insights.md).

---

## 1. Core Philosophy: The Voluntary-Commitment Model

Most finance apps operate as “financial autopsies”: they report on money after it has already left the account. Envelope apps (YNAB-style), "pots" (Monzo-style), and AI budgeting chatbots (Cleo-style) analyze or label transactions after the fact. **FireWallet puts an LLM-parsed "why" and a deterministic policy engine in front of the payment itself.**

### Why Voluntary Commitment Works
*"Nobody can tie someone down if they are set on finding a loophole. FireWallet is built for people who **want** financial discipline and need structured friction to keep it. Once you commit to routing your spending through FireWallet, it enforces your own rules at the point of payment, and moves savings out of reach where it can."*

1. **Explicit User Commitment:** During onboarding and envelope setup, the user authors their own rules and confirms a personal commitment statement. FireWallet does not invent a budget; it enforces the contract the user chose when calm against the impulses they feel at 1 a.m.
2. **Real Money Separation Where Possible:** When income lands on payday, the Vault savings skim is dispatched via a real **PayPal Payout** to a separate sandbox account, physically removing those funds from the primary spendable balance.
3. **Deliberate Reflection Friction:** When a user attempts to raid their Bank Foundation for a non-essential impulse, they face the **Escape Window**—a mandatory 200-character reflection confession and a server-enforced cooldown timer.
4. **Reactive Literacy Loop:** The read-only **AI Financial Coach** explains the *why* behind blocked transactions, clarifies charts, and simulates affordability before money moves.

---

## 2. Target Audience & Concrete Persona

Impulse e-commerce and delivery apps are 1-tap, while budgets are static monthly spreadsheets. When checking out from a single blended PayPal balance, users inadvertently spend money earmarked for rent and utilities.

### Primary Persona (With Concrete Numbers)
- **Profile:** University student or irregular/gig earner managing a **$400/month discretionary allowance** alongside **$1,200/month rent & utilities**, struggling to stop late-night food delivery orders.
- **Configured Policy:**
  - **Bills Reserve:** $1,200 earmarked first on payday.
  - **Vault Skim:** 20% (`2000 bps`) moved out on payday for Emergency Reserves & pre-designated Sinking Goals (e.g., saving for a camera).
  - **Daily Living Allowance:** $40.00/day target (with unspent funds rolling over to reward restraint).
  - **Freedom Envelope:** $150.00/month hard cap for guilt-free dining out and entertainment.

| Persona | Primary Need | FireWallet Mechanism |
| --- | --- | --- |
| **Student** *(Main Focus)* | Fixed allowance, campus social pressure, 1 a.m. food delivery | Quick Intent check, Daily Rollover streak rewards, Coach affordability simulation |
| **Irregular / Gig Earner** | Variable income bursts; lean weeks following flush weeks | Payday skim to Vault; Daily top-up to target rather than reset; Bills priority queue |
| **Impulse Shopper** | Fun money that cannot eat rent | Freedom burn-down envelope; Escape Window 200-char confession + cooldown |
| **Bill-Anxious Renter** | Rent and utilities must never bounce | Automatic payday bill reservation; Protected HUD panel showing exact rent protected |

---

## 3. Product Principles

1. **Intent before money (`Propose → Verify → Confirm → Execute`):** Natural language *why* is parsed by the AI agent, verified by deterministic Python rules (`can_spend`), confirmed by the user, and executed via PayPal Sandbox APIs.
2. **User-authored commitment:** Policy sliders are the user's self-binding contract; deterministic code enforces this contract without LLM hallucination.
3. **Friction is a feature:** Dipping into Bank Foundation reserves requires an Escape Window (200-character confession + server-side cooldown).
4. **Real PayPal execution:** Every external money movement hits PayPal Sandbox REST APIs:
   - **Merchant Spend Approved:** Creates and captures a real PayPal **Order v2** (`POST /v2/checkout/orders`).
   - **Payday Vault Skim & Bill Pay:** Executes a real PayPal **Payout** (`POST /v1/payments/payouts`) to the separate Vault receiver or bill payee sandbox account.
   - **Settlement Truth:** Reconciled via cryptographically verified **PayPal Webhooks** (`POST /api/v1/webhooks/paypal`) with PayPal Order, Capture, and Payout IDs persisted in the double-entry ledger.

---

## 4. The 5 Trinity Buckets

| Bucket | Role & Liquidity Policy |
| --- | --- |
| **Bank Foundation (`bank`)** | Foundation cash-flow engine. Income lands here; funds Daily top-ups and Bills. Direct merchant spend is locked behind the Escape Window override. |
| **Daily Allowance (`daily`)** | Fluid everyday living engine (groceries, transit, coffee). Features the **Rollover Rule**—unspent daily funds carry forward on top of tomorrow's replenishment. |
| **Freedom (`freedom`)** | Monthly guilt-free impulse and hedonism envelope. High liquidity until empty, then **hard stop** for the remainder of the month. |
| **Savings Vault (`vault`)** | Houses the **Emergency Reserve** (locked until a verified emergency strikes) and **Pre-designated Sinking Goals** (e.g., saving for a camera). True long-term wealth & investments are swept to external accounts upon reasoning with the Coach. |
| **Reserved Bills (`bills`)** | Internal priority earmark for fixed obligations (rent, utilities). Funded before Vault skims on lean paydays; never spendable as daily cash. |

---

## 5. Dual-Surface Architecture

- **Mobile HUD Surface (`view='hud'`):** High-contrast, thumb-driven dashboard showing Bank Foundation status, Daily Allowance + rollover streak badge, Protected HUD panel (*Rent protected, Impulse blocked, Rollover streak*), Vault & Bills strip, Freedom progress bar, Quick Intent FAB, and slide-up Coach drawer.
- **Desktop Deep Analytics Surface (`view='deep-ledger'`):** High-density enterprise workbench powered by **AG Grid** (`/api/v1/analytics/deep-ledger`). Supports multi-column sorting, category grouping, double-entry `transfer_id` auditing, PayPal Order/Capture ID inspection, and 1-tap **"Analyze with Coach"** row interrogation.

---

## 6. Honest Boundaries, Limitations & Non-Goals (v1)

- **Voluntary Commitment Scope:** Bank, Daily, and Freedom are programmatic double-entry ledger buckets sitting atop the user's primary PayPal balance (while Vault skims are moved to a separate sandbox account via Payouts). Enforcement applies to spending routed through FireWallet; cross-account card locking (virtual cards, bank-level multi-sig) is documented on the v2.0 roadmap ([features.md](features.md)).
- **Not a Bank or Investment Advisor:** FireWallet does not hold FDIC deposits, issue credit, or recommend securities/crypto.
- **Single Currency (USD Sandbox):** All v1 calculations operate in integer USD minor units (cents) against `api-m.sandbox.paypal.com`.
