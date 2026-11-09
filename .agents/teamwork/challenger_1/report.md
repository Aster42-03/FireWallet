# Adversarial Empirical Challenge Report: FireWallet Phase 5 & Trinity Batch Dispatcher

**Agent**: `challenger_1` (teamwork_challenger)  
**Date**: 2026-11-08  
**Verdict**: **`APPROVE`**  
**Overall Risk Assessment**: **`LOW`**

---

## 1. Executive Summary

As the empirical challenger, `challenger_1` designed and executed rigorous adversarial test harnesses against the FireWallet codebase. We did not accept declarative assertions; all invariants were subjected to empirical stress testing via automated test executions against the deterministic ledger engine, the REST API endpoints, and the database state machine.

Across all empirical challenges:
1. **Double-Entry Invariants**: Maintained exact zero-sum ledger conservation (`-Bank / +Bucket = $0.00`) across intensive arbitrary sequences of upward/downward bills reallocations, vault skim modifications, emergency draws, and batch payouts. Zero float arithmetic was verified.
2. **Vault-to-Bank Cascade**: Verified both partial draws ($100 Vault + $50 Bank = $150 draw) and complete exhaustion ($0 Vault + $100 Bank = $100 draw). Overdraw boundaries strictly halted with HTTP 409 without leaking funds or leaving orphan holds.
3. **Partner Replay Attacks**: Single-use cryptographic tokens reliably rejected duplicate decisions (both approval and rejection replays) with HTTP 409 Conflict. State inversion attempts (e.g., approving an already rejected token or vice versa) were completely blocked.
4. **Batch Dispatcher Blast Radius Containment**: Attempts to spend from `bank` or unauthorized buckets (`daily`, `freedom`, `payroll`, `root`, `""`) failed immediately with HTTP 400. Overdraw requests exceeding isolated reserves failed with HTTP 400, leaving Bank Foundation 100% untouched down to the exact cent. Live PayPal Sandbox credential checks cleanly returned HTTP 503 when mock or offline.

The regression test suite passed with **116 passed, 1 skipped** (1 skipped is the Testcontainers Docker requirement, which is expected in sandbox environments).

---

## 2. Adversarial Challenges & Hypotheses

### Challenge 1: Zero-Sum Ledger Conservation Across Arbitrary Sequences
- **Assumption Challenged**: Complex state mutations (e.g. policy adjustments, emergency cascade draws, batch payouts) might lead to rounding drift, float inaccuracies, or un-paired ledger legs.
- **Attack Scenario**: Subject the ledger to a consecutive chain of rapid mutations:
  1. Rebalance Reserved Bills upwards (from $1,200 to $1,600).
  2. Rebalance Reserved Bills downwards (from $1,600 to $900).
  3. Change Vault skim rate (from 20% to 35%) and re-sync allocations.
  4. Perform an emergency draw cascading from Bank to Vault.
  5. Perform an isolated batch payout from Bills.
- **Empirical Result**: **PASS**.
  - All internal transfer legs shared `transfer_id` and summed to exactly `0` cents.
  - Across all operations, total posted net worth across the 5 Trinity buckets equaled `initial_pool - external_disbursements` to the exact integer cent.
  - No floating point numbers were introduced in the ledger.

### Challenge 2: Vault-to-Bank Cascade Allocation & Boundary Failures
- **Assumption Challenged**: If Vault funds are insufficient or empty, the cascade transfer might under-fund, over-fund, double-debit Bank Foundation, or permit overdrawing past combined Vault + Bank reserves.
- **Attack Scenarios**:
  - **Scenario 2A (Partial Draw)**: Seed Vault = $100.00 (10,000 cents), Bank = $50.00 (5,000 cents). Request emergency draw of $150.00 (15,000 cents).
    - *Result*: Cascade transfer of exactly -$50.00 from Bank to +$50.00 Vault was recorded. Post-settlement: Vault = $0.00, Bank = $0.00. Total draw = $150.00. Zero funds lost.
  - **Scenario 2B (Complete Exhaustion)**: Seed Vault = $0.00, Bank = $100.00 (10,000 cents). Request emergency draw of $100.00.
    - *Result*: 100% of the $100.00 cascaded from Bank to Vault via paired double-entry transfer. Post-settlement: Vault = $0.00, Bank = $0.00.
  - **Scenario 2C (Overdraw Boundary)**: Seed Vault = $100.00, Bank = $50.00 (Total available: $150.00). Attempt emergency draw of $150.01 (15,001 cents).
    - *Result*: Execution cleanly failed with HTTP 409 Conflict. Ledger inspection confirmed zero funds moved, zero cascade entries recorded, and zero holds placed.

### Challenge 3: Partner Approval Token Replay Attacks & Tampering
- **Assumption Challenged**: An accountability partner token might be replayed to unlock transactions multiple times, or manipulated to flip a rejected transaction into an approved state.
- **Attack Scenarios**:
  - **Scenario 3A (Replay on Approved Token)**: Approve token once (HTTP 200). Submit duplicate approval decision.
    - *Result*: Returns HTTP 409 Conflict ("Partner approval has already been decided.").
  - **Scenario 3B (Decision Flip Attack)**: Submit rejection on an already approved token.
    - *Result*: Returns HTTP 409 Conflict.
  - **Scenario 3C (Replay on Rejected Token)**: Reject token once (HTTP 200). Submit duplicate rejection decision.
    - *Result*: Returns HTTP 409 Conflict.
  - **Scenario 3D (Decision Inversion Attack)**: Submit approval on an already rejected token.
    - *Result*: Returns HTTP 409 Conflict.
  - **Scenario 3E (Tampering / Injection Payloads)**: Submit malformed tokens, trailing spaces, SQL injection strings (`'; DROP TABLE users; --`).
    - *Result*: Cleanly handled with HTTP 404 or 422. Database remained intact with zero unhandled 500 exceptions.

### Challenge 4: Batch Dispatcher Blast Radius Containment & Sandbox Guard
- **Assumption Challenged**: An automated bill batch execution could attempt to raid Bank Foundation, bypass isolated reserve limits, or execute payouts without live PayPal Sandbox credentials.
- **Attack Scenarios**:
  - **Scenario 4A (Bank Blast Radius Direct Spend)**: Call `POST /api/v1/bills/batch-dispatcher/execute` with `source_bucket="bank"`.
    - *Result*: Request rejected immediately with HTTP 400 Bad Request ("Batch Dispatcher is strictly restricted to isolated 'bills' or 'vault' reserves. Direct spend from 'bank' is forbidden.").
  - **Scenario 4B (Unauthorized Buckets)**: Test `source_bucket` values `daily`, `freedom`, `payroll`, `root`, `unknown`, `""`.
    - *Result*: All failed immediately with HTTP 400 Bad Request.
  - **Scenario 4C (Reserve Overdraw Protection)**: Stage a batch obligation of $5,000.00 exceeding isolated reserves.
    - *Result*: Rejected with HTTP 400 Bad Request. Post-call audit verified Bank Foundation balance was 100% unaltered.
  - **Scenario 4D (Live PayPal Sandbox Guard)**: Attempt batch execution when PayPal client returns mock tokens or offline status.
    - *Result*: Rejected cleanly with HTTP 503 Service Unavailable ("Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured."). Zero ledger debits recorded.

---

## 3. Empirical Test Execution Matrix

| Test Suite / Test Name | Category | Objective | Result | Execution Time |
|---|---|---|---|---|
| `test_adversarial_zero_sum_double_entry_arbitrary_sequence` | Invariant | Verify zero-sum conservation across arbitrary operation sequences | **PASSED** | 0.22s |
| `test_adversarial_vault_cascade_partial_draw` | Cascade | Verify $100 Vault + $50 Bank = $150 draw | **PASSED** | 0.18s |
| `test_adversarial_vault_cascade_complete_exhaustion` | Cascade | Verify $0 Vault + $100 Bank = $100 draw | **PASSED** | 0.17s |
| `test_adversarial_vault_cascade_overdraw_strictly_rejected` | Boundary | Verify overdraw exceeding combined reserves fails with 409 | **PASSED** | 0.14s |
| `test_adversarial_partner_token_replay_approved` | Security | Verify replay of approved token yields HTTP 409 Conflict | **PASSED** | 0.19s |
| `test_adversarial_partner_token_replay_rejected` | Security | Verify replay of rejected token yields HTTP 409 Conflict | **PASSED** | 0.18s |
| `test_adversarial_partner_token_tampering_and_sql_injection` | Security | Verify tampered tokens and SQL injection fail with 404/422 | **PASSED** | 0.12s |
| `test_adversarial_batch_dispatcher_bank_blast_radius_strictly_denied` | Blast Radius | Verify source_bucket='bank' fails with HTTP 400 | **PASSED** | 0.16s |
| `test_adversarial_batch_dispatcher_unauthorized_buckets_strictly_denied` | Blast Radius | Verify non-isolated buckets fail with HTTP 400 | **PASSED** | 0.18s |
| `test_adversarial_batch_dispatcher_overdraw_preserves_bank` | Blast Radius | Verify over-limit batch fails and leaves Bank untouched | **PASSED** | 0.15s |
| `test_adversarial_batch_dispatcher_live_paypal_sandbox_guard` | Integration | Verify mock/offline PayPal returns HTTP 503 | **PASSED** | 0.13s |
| **Full Regression Suite (`pytest tests/`)** | Full System | 117 tests covering unit, API, integration, and E2E | **116 PASSED, 1 SKIPPED** | 11.74s |

---

## 4. Unchallenged Areas

- **Live PayPal Production Environment**: Payouts and Orders were verified using the PayPal Sandbox API client specifications and mock/sandbox token filters; production credentials were not used as this is an isolated test environment.
- **PostgreSQL Testcontainers in CI**: Skipped `test_testcontainers_postgres.py` due to absent Docker daemon in the current execution container. Full SQLite in-memory async engine was used for all API, ledger, and model tests.

---

## 5. Final Challenger Verdict

The implementation adheres strictly to the mathematical and architectural invariants specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`. The financial firewall and blast radius containment guarantees hold under adversarial pressure.

**Verdict: `APPROVE`**
