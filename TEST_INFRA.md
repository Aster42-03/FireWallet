# TEST_INFRA — FireWallet E2E Testing Infrastructure

**Document Version:** 1.0.0  
**Target Scope:** FireWallet Phase 5, The Trinity Batch Dispatcher, Configurable Bills Allocation, Quick Intent Bug Fix (R1, R2, R3, R4)  
**Author:** `test_writer_1` (`teamwork_test_writer`)  
**Test Framework:** Pytest 9.2.0 + `pytest-asyncio` (Mode AUTO) + HTTPX ASGI Client + SQLModel In-Memory SQLite StaticPool  

---

## 1. Testing Architecture & Philosophy

The FireWallet E2E testing infrastructure is designed as an opaque-box, requirement-driven verification suite protecting the system's core invariants:
1. **Zero-Float Integrity:** All currency calculations strictly operate in integer minor units (cents). Floating-point currency math is prohibited.
2. **Bank Foundation Inviolability & Blast Radius Containment:** Bank Foundation is structurally insulated from direct spend or agentic batch raiding. Disbursements and payouts are confined to isolated `vault` or `bills` buckets.
3. **Double-Entry Ledger Invariance:** Every balance reallocation (bills target synchronization, vault cascade draws, payday skims) executes as balanced, zero-sum paired entries (`-FromBucket / +ToBucket = $0.00`).
4. **Human-in-the-Loop Veto Power:** Autonomous batch dispatchers propose obligations and stage queues, but require explicit user authorization with per-item veto control before execution.
5. **Live PayPal Sandbox Enforcement:** Batch payouts require authenticated, live PayPal Sandbox credentials and fail cleanly (HTTP 503) if unconfigured or offline, rejecting silent mock fallback.
6. **Dual-Flow Friction Gates:** Emergency spends bypass friction with 0s cooldown, while non-emergency discretionary draws enforce accountability partner approval or a 200-character reflective confession plus a 180-second countdown timer.

---

## 2. 4-Tier Test Classification Framework

Every requirement (R1, R2, R3, R4) is covered across four distinct verification tiers:

| Tier | Category | Description | Minimum Target | FireWallet Implementation |
|---|---|---|---|---|
| **Tier 1** | **Feature Coverage** | Happy path execution for each core function, endpoint, and schema definition. | $\ge 5$ tests per feature | 26 tests across R1–R4 |
| **Tier 2** | **Boundary & Corner Cases** | Edge inputs, zero amounts, negative values, integer bounds, empty token strings, token replays, unconfigured credentials, and 400/404/409/422 error states. | $\ge 5$ tests per feature | 21 tests across R1–R4 |
| **Tier 3** | **Cross-Feature Combinations** | Multi-system interactions: Vault cascade + Partner approval; Bills rebalance + Batch Dispatcher blast radius; 5-bucket zero-sum ledger conservation. | $\ge 2$ tests per feature | 9 tests across R1–R4 |
| **Tier 4** | **Real-World Scenarios** | End-to-end user journeys: Acute medical ER hospitalization flow; seasonal winter heating bill rebalance; monthly batch payout dispatch with selective human veto. | $\ge 1$ test per feature | 5 tests across R1–R4 |

**Total Suite Size:** **61 comprehensive E2E tests** across 4 dedicated test files.

---

## 3. Test Suite Inventory & File Map

```
tests/
├── unit/
│   ├── test_quick_intent_e2e.py      # R4: Quick Intent Bug Fix & Core Categories (17 tests)
│   └── test_phase5_e2e.py           # R1: Emergency Vault, Cascade & Partner Dual-Flow (14 tests)
└── api/
    ├── test_bills_config_e2e.py     # R3: Configurable Bills Envelope & Rebalancing (15 tests)
    └── test_batch_dispatcher_e2e.py # R2: The Trinity Batch Dispatcher Payouts (15 tests)
```

### Detailed Breakdown by Feature File:

#### 1. `tests/unit/test_quick_intent_e2e.py` (Requirement R4 — 17 Tests)
- **Tier 1 (Feature Coverage):**
  - `test_tier1_classify_groceries_supermarket` — Supermarket items map to `groceries`.
  - `test_tier1_classify_transit_subway` — Commuter subway maps to `transit`.
  - `test_tier1_classify_utilities_electric_bill` — Electric bill maps to `utilities`.
  - `test_tier1_classify_entertainment_concert` — Concert tickets map to `entertainment`.
  - `test_tier1_classify_gifts_birthday` — Gifts map to `gifts`.
  - `test_tier1_classify_eating_out_restaurant` — Restaurant dining maps to `eating_out` / `dining_out`.
  - `test_tier1_classify_emergency_medical` — Acute hospital ER copay maps to `emergency`.
- **Tier 2 (Boundary & Corner Cases):**
  - `test_tier2_food_token_disambiguation_dining_not_groceries` — Generic `"food"` token does not intercept dining takeout as groceries.
  - `test_tier2_food_token_fast_food` — Fast food burgers classify as dining, not groceries.
  - `test_tier2_medical_emergency_scaffolding_removed` — Eliminates `medical_emergency` scaffolding artifact; returns canonical `emergency`.
  - `test_tier2_savings_violation_scaffolding_removed` — Eliminates `savings_violation` scaffolding artifact; maps to canonical taxonomy.
  - `test_tier2_case_insensitivity_and_punctuation` — Extreme capitalization and symbols do not corrupt parsing.
  - `test_tier2_minimal_and_ambiguous_utterance` — Ambiguous single-word inputs fall back to recognized canonical categories.
- **Tier 3 (Cross-Feature Combinations):**
  - `test_tier3_emergency_classification_triggers_zero_cooldown_metadata` — Attaches `valid_emergency` and `zero_cooldown` flags.
  - `test_tier3_luxury_splurge_with_emergency_phrase_rejected` — Luxury celebration mentioning "emergency reserves" is stripped of emergency status.
  - `test_tier3_utility_shutoff_classified_as_emergency` — Acute utility disconnection notice maps to `emergency`.
- **Tier 4 (Real-World Scenarios):**
  - `test_tier4_full_day_spending_journey_canonical_taxonomy` — Simulates 7 distinct daily financial transactions; enforces 100% adherence to canonical category set with zero scaffolding artifacts.

#### 2. `tests/api/test_bills_config_e2e.py` (Requirement R3 — 15 Tests)
- **Tier 1 (Feature Coverage):**
  - `test_tier1_get_policy_returns_bills_monthly_amount` — GET `/api/v1/me/policy` returns default 120,000 cents ($1,200.00).
  - `test_tier1_update_bills_target_inflow_from_bank` — PUT `/api/v1/me/policy` increases Bills from Bank.
  - `test_tier1_update_bills_target_outflow_return_to_bank` — Decreasing Bills returns excess to Bank.
  - `test_tier1_patch_policy_preserves_bills_amount` — PATCH partial updates leave Bills target intact.
  - `test_tier1_double_entry_ledger_records_verified` — Verifies paired `bill_reserve` ledger entries sum to exactly $0.00.
  - `test_tier1_hud_buckets_endpoint_reflects_rebalanced_bills` — GET `/api/v1/buckets` reports updated available funds.
- **Tier 2 (Boundary & Corner Cases):**
  - `test_tier2_bills_target_zero_cents_deallocates_to_bank` — Target of 0 cents is valid; sweeps reserve back to Bank.
  - `test_tier2_negative_bills_target_rejected_422` — Negative amount rejected with HTTP 422.
  - `test_tier2_bills_target_unchanged_idempotent_no_spurious_entries` — Idempotent update creates zero spurious ledger records.
  - `test_tier2_bills_target_exceeding_bank_funds_capped` — Over-allocation capped safely at available Bank funds.
  - `test_tier2_string_or_float_minor_units_handled_strictly` — Non-integer types rejected with HTTP 422.
- **Tier 3 (Cross-Feature Combinations):**
  - `test_tier3_bills_rebalancing_preserves_zero_sum_across_all_five_buckets` — Total system net worth conserved before and after rebalance.
  - `test_tier3_deep_ledger_aggregates_remain_balanced_after_bills_rebalance` — AG Grid telemetry validates `double_entry_balanced == True`.
  - `test_tier3_multiple_consecutive_reallocations_stable` — Rapid sequential reallocations remain accurate.
- **Tier 4 (Real-World Scenarios):**
  - `test_tier4_winter_heating_envelope_expansion_and_spring_reduction` — Full seasonal utility expansion ($1,200 -> $1,450) and spring de-allocation back to Bank Foundation ($1,450 -> $1,200).

#### 3. `tests/unit/test_phase5_e2e.py` (Requirement R1 — 14 Tests)
- **Tier 1 (Feature Coverage):**
  - `test_tier1_can_spend_vault_with_is_emergency_flag` — Rule 1 permits Vault spend when `is_emergency=True`, denies when `False`.
  - `test_tier1_emergency_vault_routing_and_zero_cooldown` — Emergency intents auto-route to Vault with 0s cooldown bypass.
  - `test_tier1_vault_to_bank_cascade_when_vault_insufficient` — Available Vault drawn first; remainder cascaded from Bank via `emergency_vault_draw`.
  - `test_tier1_partner_token_generation_when_partner_linked` — Cryptographic 256-bit token returned in API response and hash saved in DB.
  - `test_tier1_partner_decision_public_endpoints_happy_path` — Partner inspects via GET `/partner/approve/{token}` and unlocks via POST decision.
  - `test_tier1_model_branding_neutrality` — Strict AST/regex audit across `frontend/src/` verifying 0 vendor/model branding occurrences.
- **Tier 2 (Boundary & Corner Cases):**
  - `test_tier2_emergency_exceeds_combined_vault_and_bank_pool` — Emergency exceeding combined pool rejected with HTTP 409.
  - `test_tier2_emergency_when_vault_is_empty_100pct_cascade` — 100% cascade from Bank when Vault is empty.
  - `test_tier2_partner_decision_invalid_token_404` — Unknown token returns HTTP 404.
  - `test_tier2_partner_decision_replay_conflict_409` — Replay of decided token returns HTTP 409 Conflict.
  - `test_tier2_partner_timeout_or_unresponsive_friction_enforced` — Unapproved partner falls back to 200 chars and 180s cooldown timer.
- **Tier 3 (Cross-Feature Combinations):**
  - `test_tier3_vault_cascade_with_partner_dual_flow_approval` — Combined Bank-Vault cascade authorized via partner token link.
  - `test_tier3_partner_outcome_alert_dispatched_on_user_cancellation` — Cancellation alert logged if user abandons approved override.
- **Tier 4 (Real-World Scenarios):**
  - `test_tier4_complete_er_medical_emergency_lifecycle` — End-to-end ER visit flow ($180 copay, Vault drawn to $20, Bank untouched at $800).

#### 4. `tests/api/test_batch_dispatcher_e2e.py` (Requirement R2 — 15 Tests)
- **Tier 1 (Feature Coverage):**
  - `test_tier1_batch_payment_item_sqlmodel_model_attributes` — Verifies `batch_payment_items` table, defaults, and attributes.
  - `test_tier1_batch_dispatcher_proposal_schema_validation` — Validates Pydantic `BatchDispatcherProposal` schema.
  - `test_tier1_batch_dispatcher_propose_endpoint` — POST `/propose` stages scheduled bills and returns risk assessment.
  - `test_tier1_batch_dispatcher_queue_endpoint` — GET `/queue` returns staged queue items and isolated balances.
  - `test_tier1_batch_dispatcher_execute_sequential_success` — Sequential PayPal Payouts execution with double-entry debits.
  - `test_tier1_human_veto_dispatches_only_approved_items` — Dispatches approved items; leaves vetoed items un-debited.
- **Tier 2 (Boundary & Corner Cases):**
  - `test_tier2_blast_radius_bank_foundation_strictly_forbidden` — Reject `source_bucket='bank'` with HTTP 400.
  - `test_tier2_blast_radius_insufficient_isolated_funds` — Reject payouts exceeding isolated Bills/Vault reserve with HTTP 400.
  - `test_tier2_live_paypal_sandbox_offline_or_mock_returns_503` — Offline or mock token returns HTTP 503 cleanly without fake payouts.
  - `test_tier2_empty_approved_items_rejected_400` — Empty approved list returns HTTP 400.
  - `test_tier2_idempotent_reexecution_skips_already_paid` — Re-submitting paid item avoids duplicate payouts and double debits.
  - `test_tier2_negative_or_zero_amount_item_rejected` — Non-positive batch item amounts raise validation errors.
- **Tier 3 (Cross-Feature Combinations):**
  - `test_tier3_bills_envelope_rebalance_combined_with_batch_dispatcher_cap` — R3 envelope expansion integrates with R2 batch dispatch limit.
  - `test_tier3_partial_failure_first_item_succeeds_second_fails` — First item commits as `paid`, second marks as `failed` with error message.
- **Tier 4 (Real-World Scenarios):**
  - `test_tier4_monthly_batch_dispatch_lifecycle_with_human_veto` — Full month-end run: Rent approved, Gym vetoed, Bills debited, Bank Foundation untouched.

---

## 4. Test Execution & Verification Commands

### Execute Full Test Suite:
```bash
backend/.venv/bin/pytest tests/ -v
```

### Execute by Requirement:
```bash
# R1: Phase 5 Emergency Vault & Partner Dual-Flow
backend/.venv/bin/pytest tests/unit/test_phase5_e2e.py -v

# R2: The Trinity Batch Dispatcher
backend/.venv/bin/pytest tests/api/test_batch_dispatcher_e2e.py -v

# R3: Configurable Bills Envelope
backend/.venv/bin/pytest tests/api/test_bills_config_e2e.py -v

# R4: Quick Intent Bug Fix & Scaffolding Cleanup
backend/.venv/bin/pytest tests/unit/test_quick_intent_e2e.py -v
```

---

## 5. Coverage & Quality Thresholds

- **Total Unit & API Tests:** 106 tests (45 baseline + 61 new E2E tests).
- **Milestone 1 (R4):** 17 / 17 Passing (100%).
- **Milestone 2 (R3):** 15 / 15 Passing (100%).
- **Milestones 3 & 4 (R1 & R2):** Comprehensive contract tests staged and ready for worker milestone implementation.
