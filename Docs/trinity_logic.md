# Trinity logic (business rules)

**FireWallet** implements this Trinity four-bucket architecture. All affordability answers and literacy advice provided by the reactive Insights coach must evaluate against the exact same deterministic `can_spend` rules and ledger numbers as the proactive intent firewall.

The product partitions money into user-visible buckets plus a locked Vault. All amounts are **integer minor units** (cents). All times are **user-local** (`users.timezone`).

The system enforces **policies the user already saved**. It does not invent a budget.

## The structure

| Bucket | Role | Liquidity |
| --- | --- | --- |
| **Bank** | Foundation. Income lands here. Pays Daily top-ups and bills. Majority of cash flow. | High, but **direct spend requires override** |
| **Daily Allowance** | Fluid engine for groceries and day-to-day living | High, intended spend path |
| **Freedom** | Pre-allocated hedonism / impulse for the month | High until empty, then **gone** |
| **Vault** | Long-term savings skimmed on income | Locked. Spend forbidden in v1 except explicit “unstash” policy (default: off) |
| **Bills** (internal) | Reserved for rent, water, utilities | Spend only via scheduled bill pay |

Bills may be modeled as a fifth bucket kind `bills` so reservations cannot be spent as Daily. User-facing copy can still say “the Bank handles necessities.”

## Policy object (user-set)

Stored on `budget_policies` (see [data_model.md](data_model.md)):

- `currency` — sandbox USD first
- `vault_skim_bps` — basis points of each income credit moved to Vault (e.g. 2000 = 20%)
- `daily_amount` — target Daily balance after morning top-up (not a daily spend cap that resets to zero)
- `freedom_monthly_amount` — credited to Freedom at period start (typically payday #1 or calendar month — **decision: calendar month**, see below)
- `bank_spend_requires_override` — default true
- `vault_spend_allowed` — default false
- `override_min_chars` — confession length
- `override_cooldown_seconds`
- `partner_required_for_bank` — if a partner is linked
- `freedom_leftover_sweep_to_vault` — default false

## Income (payday)

When income **settles** (PayPal capture/payout completed **and** ledger credit to Bank):

```
gross = income_amount
skim  = floor(gross * vault_skim_bps / 10_000)
bill_reserve = sum of bills due before next expected payday (or policy window)
spendable = gross - skim - bill_reserve

Bank     += spendable          # remainder of cash flow
Vault    += skim               # locked
Bills    += bill_reserve       # earmarked
```

If `skim + bill_reserve > gross`, **bills win**: fill Bills first, Vault gets `max(0, gross - bills)`, Bank gets 0. Never overdraft Bank on skim.

Vault movement is both a ledger post **and** a PayPal Payout to the vault receiver (see [paypal_integration.md](paypal_integration.md)). If Payout fails, hold `pending_vault` and retry; do not silently skip the skim.

## Daily Allowance and the Rollover Rule

**Rollover:** unused Daily **stays** in Daily. Discipline increases tomorrow’s spending power.

**Morning job** (user-local midnight, or first app open after midnight if the job missed):

```
target = policy.daily_amount
current = balance(Daily)

if current >= target:
    # rollover already covers today; Bank pays nothing
    noop
else:
    shortfall = target - current
    transfer min(shortfall, balance(Bank)) from Bank → Daily
```

This is a **top-up to target**, not “reset Daily to daily_amount.” Resetting would destroy rollover.

If Bank cannot fund the shortfall, Daily stays at `current` and the user sees a **Bank starved** state. Bills and Vault are not raided to fund Daily.

### What Daily is for

Groceries, transit, ordinary living. Agent default-routes `necessity_daily` categories here.

Spending **directly from Bank** for these is allowed only via **override** (friction). That is the psychological firewall.

## Freedom bucket

At **calendar month start** (user-local):

```
if balance(Freedom) > 0:
    # leftover Freedom does NOT roll into Daily or Bank by default
    # decision: leftover stays in Freedom (hedonism surplus) unless user opts "sweep leftover to Vault"
Freedom += policy.freedom_monthly_amount   # funded from Bank if possible
```

Funding order: Bank only. If Bank is short, Freedom gets a partial fill; do not steal Bills or Vault.

When Freedom is **zero**, impulse / hedonism intents are **denied** unless the user completes override to spend from Daily or Bank (Daily override is still friction if the agent marks the spend as non-essential).

**Once burned, it's gone** for that category of chaos: no silent refill mid-month except the monthly credit.

## Priority routing (necessities)

Fixed bills (rent, water, utilities) are `bills` rows with `priority`, `due_date`, `amount`, `payee_paypal`.

Sweep job (daily, and on payday):

1. Sort due-or-overdue bills by `priority` ascending (1 = rent first).
2. Pay from **Bills** bucket; if Bills is short, pull from **Bank** (this is allowed without consumer override — the user already authorized the bill).
3. Never pull from Daily, Freedom, or Vault to pay bills.
4. Execute via PayPal Payout (or Orders if the payee is a merchant).

If still short: mark bill `blocked_insufficient` and notify. Do not bounce Daily.

## Spend path (intent-first)

No merchant PayPal call without an `intents` row.

1. User submits NL **why** + amount + optional merchant.
2. Agent returns `category`, `necessity`, `recommended_bucket`, `rationale`.
3. Router:

| Agent necessity | Default bucket | If that bucket empty |
| --- | --- | --- |
| `bill` | Bills / Bank | deny (do not use Daily) |
| `daily_living` | Daily | deny or suggest wait until top-up; Bank only with override |
| `freedom` | Freedom | deny; Daily/Bank only with override |
| `ambiguous` | ask user to pick Daily vs Freedom | no PayPal until pick |

4. User confirms. Ledger **HOLD**. PayPal execute. Webhook **POST**.

### Bank spend

If `bank_spend_requires_override` and the source is Bank (or agent wants to dip into Bank): **friction required** before HOLD.

### Vault

If `vault_spend_allowed` is false, any Vault source is hard-deny. No override in v1 (prevents “confession then raid rent-adjacent savings”). Change only via policy edit with a cooling-off (optional later).

## Friction-based override (Escape Window)

Used when the user tries to break their own rules (empty Daily, Freedom burned, or Bank dip for non-bill).

All of the following, **in order**, unless policy disables a step:

1. **Confession:** `overrides.body` length ≥ `override_min_chars`. Store verbatim for the user’s own review, not for public shaming.
2. **Cooldown:** `override_cooldown_seconds` must elapse after confession submit. UI shows a timer. Server rejects execute if `now < ready_at`.
3. **Partner 2FA** if `partner_required_for_bank` and source is Bank (or policy says always): partner approves via magic link / TOTP. `partner_approvals.status = approved`.

Only then may `intents.status` become `override_approved` and execution proceed.

There is **no one-click “anyway”**. That is the product.

## State machine (intent)

```
draft → parsed → allowed | denied | needs_override
needs_override → override_pending → override_approved | override_rejected | override_expired
allowed | override_approved → hold → executing → settled | failed
executing → (webhook) settled
failed → (retry eligible) executing
denied, override_rejected, override_expired are terminal for that intent
```

## Ledger invariants

Double-entry: every movement is at least two lines that sum to 0 in the user’s books (source bucket credit/debit pair), plus optional `paypal_clearing` while waiting on webhooks.

```
HOLD:   Daily reserved += amount; Daily available -= amount
SETTLE: Daily reserved -= amount; expense posted; paypal_clearing cleared
FAIL:   Daily reserved -= amount; Daily available += amount
```

Available balance for spend checks is `posted - holds`. Never spend reserved funds.

## Edge cases

| Case | Rule |
| --- | --- |
| Missed payday | No automatic Daily top-up from Vault/Bills. Daily may still have rollover. Bills may `blocked_insufficient`. |
| Two paydays in one month | Each income skims Vault. Freedom monthly credit is **once per calendar month**, not per payday. |
| User timezone change | Next job uses new zone; do not double-run midnight if the local date already processed (`daily_runs.local_date` unique). |
| Partial PayPal capture | Settle HOLD for captured amount; release remainder. |
| Failed Payout (vault/daily) | Keep `pending_*` ledger; retry with same PayPal idempotency key. UI shows pending, not inflated available. |
| Clock skew / job overlap | Unique `(user_id, job_kind, local_date)`. |
| Amount 0 or negative | Reject at API. |
| Currency mismatch | Reject. v1 single currency. |
| Agent down | Intent stays `draft`/`parsed` fail; **no PayPal**. Manual category pick can be a fallback (still not silent pay). |
| Duplicate submit | Idempotency key from client on `POST /intents`. |

## Pseudocode: can_spend

```
def can_spend(user, amount, source, necessity, override):
    if amount <= 0: return deny("invalid_amount")
    if source == VAULT and not policy.vault_spend_allowed: return deny("vault_locked")
    if source == BILLS and necessity != BILL: return deny("bills_are_not_spending_money")
    avail = available(source)
    if avail < amount: return deny("insufficient")
    if source == BANK and policy.bank_spend_requires_override and necessity != BILL:
        if not override.complete: return friction("bank_override")
    if necessity == FREEDOM and source != FREEDOM:
        if not override.complete: return friction("cross_bucket")
    if necessity == DAILY_LIVING and source == BANK:
        if not override.complete: return friction("use_daily_or_override")
    return allow
```

## What we will not do (v1)

- Overdraft
- Lending Daily from next week
- Auto-refill Freedom mid-month
- Spending Vault to save a bill without an explicit later policy
- Silent merchant charges without an intent row
