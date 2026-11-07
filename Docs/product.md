# Product

**FireWallet** is a **proactive financial firewall and budgeting PWA** powered by the **Trinity** four-bucket architecture. It restricts liquidity **before** impulsive spending occurs through an intent-first PayPal gateway, while building long-term financial literacy through a mobile HUD dashboard and a reactive AI Insights Coach.

Hackathon context: [hackathon_overview.md](hackathon_overview.md). Bucket rules: [trinity_logic.md](trinity_logic.md). Coach design: [insights.md](insights.md).

---

## Philosophy

Most finance apps operate as “financial autopsies”: they report on money after it has already left the account. FireWallet takes a **proactive** stance:

1. It separates cash into psychological and programmatic buckets so rent and bills cannot fund a 1 a.m. impulse purchase without deliberate, user-configured friction.
2. It pairs this proactive firewall with a **reactive Insights Coach** to explain the *why* behind budgets, clarify charts, and simulate affordability before spending.

FireWallet **only enforces what the user already decided to enforce**. It is not a bank, not a credit provider, not investment advice, and not a moralizing scold. It is a protective firewall with a daily living allowance, a guilt-free fun envelope, and a friendly financial coach.

---

## Problem

Impulse e-commerce and delivery apps are 1-tap. Budgets are monthly spreadsheets. When checking out, people spend from a single blended PayPal balance that inadvertently consumes money earmarked for rent and utilities.

**Audience:** Anyone seeking proactive financial discipline—with a dedicated focus on **students** and **irregular/gig earners** who face unpredictable cash flow and high impulse pressure.

---

## Personas

| Persona | Primary Need | FireWallet Feature |
| --- | --- | --- |
| **Student** *(Main Focus)* | Fixed allowance, campus social pressure, late-night food ordering | Quick Intent check, Daily Rollover rewards, Coach affordability check (*"Can I eat out tonight?"*) |
| **Irregular / Gig Earner** | Variable income bursts; lean weeks following flush weeks | Payday skim to Vault; Daily top-up to target rather than reset; Bills priority queue |
| **Impulse Shopper** | Fun money that cannot eat rent | Freedom burn-down envelope; Escape Window confession + cooldown |
| **Bill-Anxious Renter** | Rent and utilities must never bounce | Automatic payday bill reservation; Bills bucket isolated from Daily spend |
| **Discipline Builder** | Positive reinforcement for restraint | Daily Rollover streak: unspent cash carries forward to tomorrow |
| **Accountability Pair** | Partner visibility into emergency Bank withdrawals | Partner 2FA token required for Bank overrides |

---

## Product Principles

1. **Intent before money:** Natural language *why* must be parsed and verified before PayPal Orders or Payouts execute.
2. **User-authored rules:** Policy sliders are the contract; AI interprets spend against this contract without inventing arbitrary rules.
3. **Friction is a feature:** Dipping into foundation reserves requires an Escape Window (confession + cooldown + partner 2FA).
4. **Literacy completes the loop:** Proactive stops prevent disaster; reactive coaching builds habits and financial understanding.
5. **Mobile HUD first:** Daily interactions happen via a mobile Heads-Up Display (HUD) with a thumb-friendly Quick Intent floating action button.
6. **Real PayPal execution:** Sandbox money movements are real (Orders, Payouts, Webhooks, Identity).
   - Explicitly link every internal Trinity move to a PayPal Sandbox API endpoint:
     - **Normal Intent Approved:** Fires a PayPal Orders API or Checkout sandbox call.
     - **Emergency Override Triggered:** Fires a PayPal Invoicing API or Payouts API call to move funds instantly out of the Vault sandbox account.
     - **Log the Response:** Save the returned paypal_transaction_id directly inside your SQLite/PostgreSQL database alongside the transaction record. When judges inspect your audit log or code, they see real PayPal transaction IDs attached to every single intent.

---

## User-Facing Buckets (Trinity Architecture)

- **Bank:** Foundation cash flow. Income lands here; funds bills and Daily top-ups. Direct spend requires an override.
- **Daily Allowance:** Fluid grocery and everyday living engine. Features the Rollover Rule (leftover stays).
- **Freedom:** Monthly guilt-free fun envelope. Once depleted, it is gone for the month.
- **Vault:** Locked savings skimmed on income. Spend forbidden in v1.
- **Bills:** Priority reserve for rent and utilities. Earmarked on payday.

---

## Surfaces

- **Mobile HUD (**`/`**):** High-contrast dashboard showing Bank core, Daily + rollover banner, safe Vault & Bills badges, Freedom progress bar, embedded Tailwind charts, and a floating **Quick Intent** button.
- **Desktop Deep Analytics ('/analytics'):** An AG Grid dashboard linked to the **'/coach'** Powers a deep transaction ledger and audit log for advanced information queryable with natural language
- **Quick Intent Modal / Page (**`/intent`**):** Rapid capture of amount, *why*, and merchant $\rightarrow$ Intent Agent verdict card $\rightarrow$ PayPal sandbox approval redirect.
- **Insights Coach Drawer (**`/coach`**):** Conversational sheet docked beside charts; offers plain-English chart explanations (`chart_id`), affordability simulations, and deep links to `/intent`.
- **Escape Window (**`/override/:id`**):** Friction screen with mandatory confession textarea, server-enforced cooldown countdown timer, and partner approval indicator.
- **Settings & Bills:** Policy configuration (skim %, daily target, freedom budget, partner email) and bill priority manager.

---

## Non-Goals (v1 / Hackathon)

- Tax preparation, credit scoring, or investment advice
- Production PayPal live charges (strictly sandbox)
- Replacing the user's primary checking account
- Public social feeds of confessions
- Automated merchant price negotiation
- Multi-currency or cryptocurrency

---

## Success Criteria for the Hackathon

A judge or user can:

1. **Witness Payday Skim:** Seed income; see Vault automatically skimmed and bills reserved.
2. **Complete an Allowed Spend:** Submit "Buying groceries" $24 via Quick Intent; see Intent Agent route to Daily; approve and capture in PayPal sandbox.
3. **Trigger the Firewall:** Submit "Late-night sushi" with an empty Freedom envelope; see the firewall block the spend and require an Escape Window override.
4. **Experience the Friction:** Submit a confession and watch the server-enforced cooldown timer block immediate execution.
5. **Ask Affordability Question:** Open the Coach sheet and ask *"Can I afford a $20 movie ticket tonight?"*; receive an analysis grounded in current balances with a 1-tap deep link to `/intent`.
6. **Trigger Chart Literacy:** Tap "Ask Coach" on `chart_pie_week`; receive a plain-English breakdown of category percentages without financial jargon.

---

## Tone

Calm, supportive, transparent, and direct. The firewall is protective, not punitive. The Coach is an empowering mentor, not a schoolmaster.
