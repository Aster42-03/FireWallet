# Trinity Rules: Mathematical & Behavioral Logic

This document specifies the exact mathematical rules, balance invariants, and psychological behavioral constraints governing the **Trinity** bucket architecture in **FireWallet**.

Related: **[problems.md](problems.md) (Core Build Gate)**, [TOOL_STACK.md](TOOL_STACK.md), [architecture.md](architecture.md), [insights.md](insights.md), [paypal_integration.md](paypal_integration.md).

> [!IMPORTANT]
> **Core Build Gate & Verification ([problems.md](problems.md)):**
> Every code change affecting bucket balances, double-entry transfers, rollovers, or override friction must be validated against the **"Done when"** criteria in **[problems.md](problems.md)** (specifically Problem 1 for zero-sum accounting, Problem 3 for the voluntary-commitment model, and Problem 5 for deterministic emergency rules).

---

## 1. The Core Bucket Structure

FireWallet partitions all user capital into four distinct psychological and programmatic buckets, plus an internal necessity reservation:

| Bucket               | Core Role                                                                                                               | Liquidity & Spend Policy                                                                                                                                                                                            | Mathematical Treatment                                                                    |
| :------------------- | :---------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------- |
| **Bank**             | Foundation & cash-flow engine. Income lands here; funds daily allowances and bills.                                     | High liquidity, but **direct spend is locked**. Direct merchant charges require an Escape Window override.                                                                         | $B_{\text{avail}} = B_{\text{posted}} - B_{\text{holds}}$                                 |
| **Daily Allowance**  | Fluid daily living engine (groceries, transit, coffee, lunch).                                                          | High liquidity. Intended spend path for everyday essentials.                                                                                                                        | Features the **Rollover Rule** (unspent funds carry forward).                             |
| **Freedom**          | Pre-allocated monthly hedonism & guilt-free impulse envelope.                                                           | High liquidity until empty, then **hard stop**. Once burned, gone for the month.                                                                                                     | $F_{\text{month}} = \text{policy.freedommonthlyamount}$                                   |
| **Vault**            | **Emergency Reserve + Pre-designated Goal Savings** (e.g., camera, travel). Long-term investments are kept external.      | **Locked by default**. Emergency funds stay locked until an emergency strikes and is verified (0s bypass). Pre-designated goal funds spendable on target. External long-term savings swept separately upon Coach reasoning. | $V_{\text{skim}} = \lfloor \text{gross} \times \frac{\text{vaultskimbps}}{10000} \rfloor$ |
| **Bills** (Internal) | Reserved earmark for fixed contractual obligations (rent, utilities).                                                   | Spendable **only** via scheduled bill payouts. Never spendable as daily cash.                                                                                                      | $\sum \text{Bills}_{\text{due}}$ earmarked before Bank funds become free.                 |

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

### Emergency Override & Retrospective Trust Protocol (ADR-020)

Per **[problems.md](problems.md) Problem 5**:
1. **Core Principle:** The LLM may *classify* (`category`, `is_emergency`), but only deterministic Python code in `LedgerEngine` may *relax friction*. The LLM output schema does not set `cooldown_seconds`.
2. **Dual-Signal Deterministic Eligibility:** To qualify for emergency treatment, spend requires two independent signals:
   - A structured emergency category enum (`healthcare`, `transit`, `utilities`).
   - The LLM's verified `is_emergency = true` flag.
   - *Example:* "Emergency at a steakhouse" maps to `eating_out`, so deterministic code applies the full Escape Window friction regardless of text claims.
3. **Emergency Policy Invariant:**
   - Emergencies draw from the Vault Emergency Reserve (or Bank Foundation under emergency policy) with a deterministic 0-second or short cooldown verification.
   - Capped at `emergency_cap_minor` (e.g. $150.00) and frequency limits (e.g. max 1 emergency per 7 days). Exceeding these bounds requires standard Escape Window reflection friction.
4. **Informational Dispatch & Reflection Prompt:**
   - Asynchronous notification dispatched to the accountability partner if configured (informational log, non-blocking).
   - Post-transaction reflective logging prompt (*"What caused this unexpected expense?"*) recorded in `agent_runs` for the Coach to review.
5. **Roadmap Separation (Cut List per [problems.md](problems.md) Section 7):**
   - The complex dynamic Trust Score / MCC reputation engine is moved to the post-hackathon roadmap. The v1 live application maintains a simple counter of emergencies this month that the Coach references during cash-flow guidance.

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

---

## 8. Future Behavioral Extension: The Trinity Batch Dispatcher (Post-Hackathon v2.0)

*(Deferred to Post-Hackathon v2.0 on the Cut List per [problems.md](problems.md) Section 7 — detailed in [features.md](features.md#1-the-trinity-batch-dispatcher))*
- **Blast Radius Invariant:** Funds for the batch can *only* be drawn from isolated Vault/Bills earmarks. Core emergency funds and main bank buffers are structurally locked against agentic modifications.
- **Human-in-the-Loop Veto Power:** The agent never dispatches payouts autonomously without explicit user confirmation of the staged checklist.
- **Idempotent Payouts:** Each batch item tracks execution state (`pending_approval` $\rightarrow$ `approved` $\rightarrow$ `paid`), preventing duplicate transactions upon network retries.
