# Phase 5 Specification & Codebase Investigation Handoff Report

**Agent**: `survey_spec_miner_1`  
**Role**: Specification Miner & Codebase Surveyor  
**Milestone**: Phase 5 Specification & Codebase Mapping (R1)  
**Date**: 2026-11-08  
**Report Artifact**: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_1/report.md`

---

## 1. Observation

1. **`backend/app/ledger/engine.py` (lines 118-120)**:
   ```python
   # Rule 1: Vault is locked long-term savings
   if source_kind == "vault":
       return False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden."
   ```
   `LedgerEngine.can_spend` unconditionally denies any spend where `source_kind == "vault"`. The method signature (`can_spend(session, user_id, amount_minor, source_kind, necessity, has_approved_override=False)`) has no parameter for `is_emergency`.

2. **`backend/app/api/v1/intents.py` (lines 87-106, 273-286)**:
   - Line 87-94: Maps target kind to `intent.recommended_bucket`.
   - Line 96-102: Calls `can_spend` without passing emergency status.
   - Line 136-143: If `policy_status == "needs_override"`, sets `action_card` to `action_type="open_override"`, forcing the user into the Escape Window even if emergency.
   - Lines 277-286 in `execute_intent`:
     ```python
     if intent.status == "override_approved":
         ...
         if current_b_avail < intent.amount and "bank" in balances:
             hold_bucket_id = balances["bank"]["bucket_id"]
             intent.source_bucket_id = hold_bucket_id
     ```
     When an override is approved, it falls back exclusively to Bank Foundation (`"bank"`), never attempting to draw or cascade from `vault`.

3. **`backend/app/agents/insights/coach.py` (lines 294-309)**:
   ```python
   # Check explicit attempt to spend from Vault
   if target_bucket == "vault" or "from vault" in lower_utt or "raid vault" in lower_utt:
       decision_status = "rejected"
       action_type = "none"
       reply_text = ("Your **Locked Savings Vault** cannot be spent directly under Trinity firewall rules. "...)
   elif det_emerg:
       # Valid emergency -> ZERO cooldown delay! Pre-approve Intent + Override immediately.
       daily_avail = balances.get("daily", {}).get("available", 0)
       bank_avail = balances.get("bank", {}).get("available", 0)
       chosen_kind = "daily" if daily_avail >= amount_cents else "bank"
   ```
   When emergency is detected, Coach selects `daily` or `bank`, explicitly bypassing `vault`.

4. **`backend/app/api/v1/coach.py` (line 154)**:
   ```python
   target_kind = body.target_bucket if body.target_bucket in ("daily", "freedom", "bills", "bank") else "freedom"
   ```
   `"vault"` is excluded from the list of valid target buckets in `execute_coach_action`.

5. **`backend/app/models/user.py` (lines 63-95)** and **`backend/alembic/versions/0001_initial_schema_initial_schema.py` (lines 143-155, 253-260)**:
   The database tables `partner_links` and `partner_approvals` already exist in the database schema and Alembic migration 0001:
   - `partner_links`: `id`, `user_id`, `partner_email`, `active`, `created_at`.
   - `partner_approvals`: `id`, `override_id`, `partner_link_id`, `status` ("pending", "approved", "rejected"), `token_hash`, `decided_at`.

6. **`backend/app/api/v1/overrides.py` (lines 34-182)**:
   Currently only checks `policy.partner_required_for_bank` and returns it as a boolean. It does NOT generate any approval token, create `PartnerApproval` records, expose public decision routes (`/partner/approve/{token}`), or handle partner instant bypass.

7. **`tests/unit/test_agent_and_rag.py` (lines 138-194)**:
   ```python
   async def test_emergency_override_grants_zero_cooldown_and_settles_from_bank(client: httpx.AsyncClient):
       ...
       # 4. Verify Bank Foundation funded the $180.00 emergency ($800.00 -> $620.00)
       buckets_resp = await client.get("/api/v1/buckets")
       buckets = {b["kind"]: b["available"] for b in buckets_resp.json()["buckets"]}
       assert buckets["bank"] == 62000
   ```
   This existing test explicitly asserts that the emergency funds came from Bank Foundation (`buckets["bank"] == 62000`), codifying the BUG-008 behavior.

8. **Frontend Model Branding Audit (`frontend/src/`)**:
   Ripgrep search `grep -riE "(groq|llama|openai|gemini|claude|chatgpt)" frontend/src/` returned **0 matches**.
   `CoachDrawer.jsx` (lines 330-349) renders clean generic status indicators: `"AI Engine Active"` / `"Deterministic Mode"`.

---

## 2. Logic Chain

1. **Root Cause of BUG-008**:
   - Observations 1, 2, 3, and 4 establish that three layers (`LedgerEngine.can_spend`, `intents.py`, and `coach.py`) enforce that `vault` is strictly inaccessible for spending under all conditions.
   - Consequently, when emergency detection (`is_genuine_emergency() = True`) was added in Phase 3, developers routed emergencies to `daily` or `bank` to avoid trigger-blocking on Rule 1.
   - This directly caused BUG-008: verified life/medical emergencies raided rent protection and daily living allowance rather than drawing from the dedicated Vault Emergency reserve.

2. **Required Resolution for Emergency Vault Allocation**:
   - Modifying `LedgerEngine.can_spend()` to accept `is_emergency: bool = False` and exempting genuine emergencies from Rule 1 allows emergency spending from `vault` (Observation 1).
   - In `submit_intent` and `coach.py`, setting `recommended_bucket = "vault"` and `target_bucket = "vault"` routes the purchase to the Vault (Observations 2, 3).
   - When Vault balance is less than the emergency amount, the remainder must cascade from Bank Foundation via a balanced double-entry transfer (`emergency_vault_draw`). This maintains zero-sum ledger invariants without modifying external transaction semantics.
   - In `coach.py` and `execute_coach_action`, adding `"vault"` to permissible buckets and providing autonomous execution (Observation 4) satisfies the requirement for AI Coach autonomous payment execution once details are verified.

3. **Required Implementation for Accountability Partner Dual-Flow**:
   - Database tables `partner_links` and `partner_approvals` already exist in the schema (Observation 5), meaning no new database migration is required for basic partner approval persistence.
   - When `create_override` is called and a partner is linked, generating a cryptographic token (`secrets.token_urlsafe(32)`), storing its hash in `partner_approvals`, logging the token to server logs, and returning it in `OverrideResponse` fulfills the token generation and log/UI display requirements (Observation 6).
   - Implementing public endpoints `GET /api/v1/partner/approve/{token}` and `POST /api/v1/partner/approve/{token}/decision` enables the partner to inspect and approve/reject the override.
   - When the partner approves, immediately transitioning `Override.status = "approved"`, `Override.ready_at = utc_now()`, and `Intent.status = "override_approved"` unlocks the transaction with 0s cooldown and 0 confession characters required.
   - If the partner times out or rejects, standard friction gates apply (200-char confession and 180s timer).
   - When the transaction executes or is cancelled, logging a structured alert (`[PARTNER OUTCOME ALERT] Override {id} resolved: PAYMENT SETTLED/CANCELLED`) fulfills the outcome alert requirement.

4. **Test Suite Adaptation**:
   - Because `test_emergency_override_grants_zero_cooldown_and_settles_from_bank` asserts `buckets["bank"] == 62000` (Observation 7), fixing BUG-008 will break this test unless it is updated to assert Vault depletion (`assert buckets["vault"] == 2000` and `assert buckets["bank"] == 80000`).
   - New tests must be added to cover the Vault cascade ($250 draw from $200 Vault + $50 Bank), partner token generation, partner approval bypass, and partner timeout fallback.

---

## 3. Caveats

1. **Partner Authentication**: The `/partner/approve/{token}` endpoints are intentionally unauthenticated by user session to allow an external partner (or testing persona) to open the link directly in an incognito window or separate browser. Security relies entirely on the high-entropy 256-bit cryptographic token (`secrets.token_urlsafe(32)`).
2. **Postgres vs SQLite**: SQLite in-memory test suite does not enforce foreign key cascading unless PRAGMA foreign_keys is on. Tests must explicitly wire `partner_link_id` to a valid `PartnerLink`.
3. **Model Branding Scope**: While frontend UI text is completely devoid of vendor names, `GET /api/v1/coach/status` still returns `provider: "groq"` and `model: "openai/gpt-oss-120b"`. The frontend deliberately suppresses these fields and renders only `"AI Engine Active"`. If strict backend decoupling is desired, `/coach/status` can also be sanitized to return generic strings.

---

## 4. Conclusion

The specification and codebase mapping for Phase 5 is complete:
1. **Emergency Vault Allocation (BUG-008)** requires synchronized updates across `LedgerEngine.can_spend()`, `intents.py`, `coach.py`, and `QuickIntentModal.jsx` to route verified emergencies to `vault`, cascade remainder from `bank`, and execute autonomously.
2. **Accountability Partner Dual-Flow** leverages existing SQLModel tables `partner_links` and `partner_approvals`, requiring token generation, two public endpoints (`/partner/approve/{token}` and `/partner/approve/{token}/decision`), outcome alert logging, and an updated dual-branch UI in `EscapeWindowModal.jsx`.
3. **Model Branding Removal** is confirmed clean across the frontend UI; all references are brand-neutral.
4. **Existing Tests**: One existing test (`test_emergency_override_grants_zero_cooldown_and_settles_from_bank`) will need its assertion updated from Bank to Vault, and 5 new unit/API tests are identified.

All findings, feature tables, edge case matrices, and implementation plans have been written to:
`/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_1/report.md`.

---

## 5. Verification Method

1. **Run Current Automated Test Suite**:
   ```bash
   backend/.venv/bin/pytest tests/
   ```
   *Baseline*: 44 passed, 1 skipped in ~5.4 seconds.

2. **Verify Frontend Branding Neutrality**:
   ```bash
   grep -riE "(groq|llama|openai|gemini|claude|chatgpt)" frontend/src/
   ```
   *Expected*: Exit code 1 (0 matches found).

3. **Inspect Phase 5 Report**:
   ```bash
   head -n 50 /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_1/report.md
   ```
