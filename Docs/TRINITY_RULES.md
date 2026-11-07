# Trinity Rules: Mathematical & Behavioral Logic

This document specifies the exact mathematical rules, balance invariants, and psychological behavioral constraints governing the **Trinity** bucket architecture in **FireWallet**.

Related: [TOOL_STACK.md](TOOL_STACK.md), [ARCHITECTURE.md](ARCHITECTURE.md), [insights.md](insights.md), [paypal_integration.md](paypal_integration.md).

---

## 1. The Core Bucket Structure

FireWallet partitions all user capital into four distinct psychological and programmatic buckets, plus an internal necessity reservation:

| Bucket               | Core Role                                                                           | Liquidity & Spend Policy                                                                                   | Mathematical Treatment                                                                    |
| :------------------- | :---------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------- |
| **Bank**             | Foundation & cash-flow engine. Income lands here; funds daily allowances and bills. | High liquidity, but **direct spend is locked**. Direct merchant charges require an Escape Window override. | $B_{\text{avail}} = B_{\text{posted}} - B_{\text{holds}}$                                 |
| **Daily Allowance**  | Fluid daily living engine (groceries, transit, coffee, lunch).                      | High liquidity. Intended spend path for everyday essentials.                                               | Features the **Rollover Rule** (unspent funds carry forward).                             |
| **Freedom**          | Pre-allocated monthly hedonism & guilt-free impulse envelope.                       | High liquidity until empty, then **hard stop**. Once burned, gone for the month.                           | $F_{\text{month}} = \text{policy.freedommonthlyamount}$                                   |
| **Vault**            | Long-term locked savings automatically skimmed from income.                         | **Locked**. Spend strictly forbidden in v1. Backed by PayPal Payouts to a vault receiver.                  | $V_{\text{skim}} = \lfloor \text{gross} \times \frac{\text{vaultskimbps}}{10000} \rfloor$ |
| **Bills** (Internal) | Reserved earmark for fixed contractual obligations (rent, utilities).               | Spendable **only** via scheduled bill payouts. Never spendable as daily cash.                              | $\sum \text{Bills}_{\text{due}}$ earmarked before Bank funds become free.                 |

---

## 2. Income & Payday Mathematics

When income settles into the system (via PayPal capture or payday credit):

```
gross = income_amount
vault_skim = floor(gross * policy.vault_skim_bps / 10000)
bills_due = sum(bill.amount for bill in upcoming_bills_in_window)

# Invariant: Bills always take priority over savings skim
if (vault_skim + bills_due) > gross:
    bills_reserved = min(gross, bills_due)
    vault_skim = max(0, gross - bills_reserved)
    bank_spendable = 0
else:
    bills_reserved = bills_due
    bank_spendable = gross - vault_skim - bills_reserved

Bank  += bank_spendable
Bills += bills_reserved
Vault += vault_skim (Dispatched via PayPal Payout to Vault Receiver)
```

**Key Invariant:** Never overdraft the Bank bucket to satisfy a Vault skim. If income is lean, essentials (rent/utilities) win first.

---

## 3. Daily Allowance & The Rollover Rule

Traditional budgets reset daily limits to zero or a fixed number, penalizing restraint. FireWallet uses a **Target Top-Up with Rollover**:

### The Rollover Law

Any unspent Daily balance from yesterday **remains in Daily**. Restraint yesterday compounds into increased spending power today.

### Morning Job Logic (User-Local Midnight)

At local midnight (or upon first app launch of the calendar day):

```python
target = policy.daily_amount
current_daily = balance(Daily)

if current_daily >= target:
    # Full rollover retained! Bank pays $0 today.
    rollover_surplus = current_daily - target
    shortfall = 0
else:
    shortfall = target - current_daily
    # Top up shortfall from Bank, up to available Bank balance
    top_up = min(shortfall, balance(Bank))
    transfer_ledger(from_bucket=Bank, to_bucket=Daily, amount=top_up)
```

**Bank Starved State:** If Bank available balance is zero, Daily remains at `current_daily` without crashing. Under no circumstances are Vault or Bills raided to fund Daily.

---

## 4. Freedom Envelope (Guilt-Free Hedonism)

- **Monthly Credit:** On the 1st of each calendar month, Freedom receives `policy.freedom_monthly_amount` funded from Bank.
- **Leftover Handling:** Any unspent Freedom remains in Freedom as a surplus, unless the user toggles `freedom_leftover_sweep_to_vault: true`.
- **Once Burned, It's Gone:** When Freedom reaches $0, any hedonistic or discretionary purchase (e.g. gaming, takeout, luxury shopping) is **denied by the firewall**.
- **No Silent Bank Raids:** An empty Freedom envelope blocks checkout. Dipping into Daily or Bank requires the user to face deliberate friction.

---

## 5. Friction-Based Override (The Escape Window)

When a user attempts to break their own rules (e.g. spending from an exhausted Freedom envelope, or raiding the Bank foundation for non-bills), FireWallet enforces the **Escape Window**.

There is **no one-click bypass**. The user must complete three sequential friction gates:

```
[Intent Denied] ──> [1. Confession] ──> [2. Cooldown Timer] ──> [3. Partner 2FA] ──> [Approved]
```

### Gate 1: Mandatory Confession

- The user must submit a written explanation to `POST /overrides`.
- Length requirement: `len(body) >= policy.override_min_chars` (default: 200 characters).
- Purpose: Psychological intervention—forces the user to articulate why their current impulse justifies compromising their rent or savings.

### Gate 2: Server-Enforced Cooldown Timer

- The server sets `ready_at = now() + policy.override_cooldown_seconds` (default: 180 seconds).
- The mobile HUD renders an active countdown timer.
- Any attempt to execute the payment (`POST /intents/{id}/execute`) before `now() >= ready_at` returns **HTTP 409 Conflict**.

### Gate 3: Accountability Partner 2FA (Optional)

- If `policy.partner_required_for_bank` is active, an approval magic token is dispatched to the partner's verified email.
- The partner reviews the confession, amount, and category, and submits approval via a secure token endpoint.

### Emergency Override & Retrospective Trust Protocol

1. **Immediate Execution (Zero-Cooldown):**
   * If the Intent Parser detects a high-urgency emergency classification, standard cooldown timers and friction locks are bypassed instantly to prevent transaction failure.
   * Funds are drawn from the dedicated **Vault Emergency Sub-Bucket**.
2. **Parallel Informational Dispatch:**
   * If an Accountability Partner is configured, an informational alert is dispatched asynchronously in parallel. This serves as a transparency log, not a gating mechanism.
   * Implement the accountability partner notification as an asynchronous Webhook (e.g. an in-app "Partner Drawer", and a telegram bot automated message).
3. **Post-Transaction Verification & Truth-Checking:**
   * Following payment completion, a non-blocking post-transaction prompt invites the user to categorize or verify the nature of the emergency.
4. **Behavioral Adaptation (The Trust/Reputation Engine):**
   * base the **Trust Score** on objective, non-deceptive behavioral telemetry:
     - **Frequency Decay:** Overrides cost trust points regardless of the reason. 1 emergency/month = high trust; 5 emergencies/week = degraded trust score.
     - **Merchant Category Logic (MCC):** If the user claims an emergency at a pharmacy or transit vendor, trust impact is minimal. If the emergency claim happens at a restaurant or gaming storefront, the trust score penalty increases automatically.
     - **The Prompt’s Role:** Use the post-transaction prompt for **Reflective Intention Logging** (*"What caused this unexpected expense?"*), feeding the response directly to the AI Financial Coach to recalculate next month's Vault buffer.
     ## Verification data feeds a dynamic user trust score. This score adjusts the sensitivity of the firewall for *subsequent non-critical* transactions (e.g., higher trust = lighter friction; lower trust = stricter guardrails).
5. **Coaching Integration:**
   * Discrepancies or frequent overrides are routed to the AI Financial Coach to gently adjust budget allocation or Vault buffers, preserving absolute user agency without punitive lockouts.

Only after all active gates are satisfied does `intents.status` transition to `override_approved`.

---

## 6. Deterministic Policy Invariant: `can_spend`

The core evaluation executed by the Policy Engine (`ledger/`) is strictly deterministic:

```python
def can_spend(user, amount_minor, source_bucket, necessity, override_status):
    # Rule 1: Validation
    if amount_minor <= 0:
        return Deny("invalid_amount")
    
    # Rule 2: Vault Lock
    if source_bucket == VAULT and not user.policy.vault_spend_allowed:
        return Deny("vault_locked_savings")
        
    # Rule 3: Bills Protection
    if source_bucket == BILLS and necessity != "bill":
        return Deny("bills_reserved_for_obligations")
        
    # Rule 4: Balance Check (posted minus active holds)
    if available_balance(source_bucket) < amount_minor:
        return Deny("insufficient_funds")
        
    # Rule 5: Bank Direct Spend Protection
    if source_bucket == BANK and user.policy.bank_spend_requires_override and necessity != "bill":
        if override_status != "approved":
            return NeedsOverride("bank_foundation_protection")
            
    # Rule 6: Discretionary / Hedonism Protection
    if necessity == "freedom" and source_bucket != FREEDOM:
        if override_status != "approved":
            return NeedsOverride("freedom_envelope_depleted")
            
    # Rule 7: Everyday Living Routing
    if necessity == "daily_living" and source_bucket == BANK:
        if override_status != "approved":
            return NeedsOverride("use_daily_allowance_or_override")
            
    return Allow(source_bucket)
```

---

## 7. Ledger Invariants & Double-Entry Accounting

1. **Zero-Sum Postings:** Every internal transfer or settlement is a balanced pair of debit (`-amount`) and credit (`+amount`) rows where $\sum \text{amount} = 0$.
2. **Hold-Before-Execute:**
   - On intent confirmation: Insert row with `state = 'hold'`, reducing available funds immediately.
   - On PayPal webhook capture: Transition hold to `state = 'posted'`.
   - On PayPal failure or cancel: Delete hold or transition to `state = 'released'`.
3. **Integer Minor Units:** All ledger values are signed 64-bit integers (`BIGINT` cents). Currency floats are prohibited throughout the entire codebase.
