# Dispatch: Milestone 3 - Phase 5 Emergency Vault & Partner Dual-Flow & Branding (worker_m3)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md` (R1)
- Project Architecture & Contracts: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Survey Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_1/report.md`
- Tests: `tests/unit/test_phase5_e2e.py`, `tests/unit/test_agent_and_rag.py`

## Role & Mission
You are `worker_m3`, an instance of `teamwork_worker`.
Your mission is to implement M3:
1. Emergency Vault Allocation & Autonomous Payment Execution (BUG-008):
   - In `backend/app/ledger/engine.py`, update `can_spend` to accept `is_emergency: bool = False`. If `source_kind == "vault"` and `is_emergency == True`, approve spend (0s cooldown bypass).
   - In `backend/app/api/v1/intents.py`, pass `is_emergency=intent.is_emergency` into `can_spend`. If emergency, route `recommended_bucket = "vault"`.
   - In `execute_intent`, when spending from `vault`: draw available funds from `vault`; if vault available < amount, cascade remainder from `bank` via balanced double-entry transfer `emergency_vault_draw` (`-Bank / +Vault = $0.00`).
   - In `backend/app/agents/insights/coach.py` and `backend/app/api/v1/coach.py`, allow `"vault"` as a valid target bucket and empower the AI Coach to execute verified emergency transactions autonomously.
2. Accountability Partner Dual-Flow Escape Window:
   - In `backend/app/api/v1/overrides.py`, when an override is created and a partner is linked (`partner_links` table exists), generate a 256-bit URL-safe token (`secrets.token_urlsafe(32)`), store its SHA-256 hash in `partner_approvals`, log the token to server console/stdout, and return it in `OverrideResponse.partner_token`.
   - Implement partner decision endpoints (`GET /api/v1/partner/approve/{token}` and `POST /api/v1/partner/approve/{token}/decision`).
   - If partner approves within the escape window: unlock transaction immediately with 0s cooldown and 0 confession characters required (`status = "approved"`).
   - If partner times out or does not approve: enforce a 200-character reflective confession and a 180s countdown timer.
   - Dispatch/log a final outcome alert (`[PARTNER OUTCOME ALERT] Override {id} resolved: {outcome}`) logging whether the payment was made or cancelled.
3. Model Branding Removal:
   - Ensure zero vendor or model branding (Groq, Llama, OpenAI, Gemini) appears anywhere in the UI or user-facing strings.
4. Existing Test Updates:
   - In `tests/unit/test_agent_and_rag.py`, update `test_emergency_override_grants_zero_cooldown_and_settles_from_bank` to reflect Vault settlement instead of Bank settlement.

## Exclusive Write Ownership
You exclusively own and may edit:
- `backend/app/ledger/engine.py`
- `backend/app/api/v1/intents.py`
- `backend/app/api/v1/coach.py`
- `backend/app/agents/insights/coach.py`
- `backend/app/api/v1/overrides.py`
- `backend/app/api/v1/partner.py`
- `backend/app/main.py` (only to include partner router if needed)
- `frontend/src/features/intent/QuickIntentModal.jsx`
- `frontend/src/features/coach/CoachDrawer.jsx`
- `frontend/src/features/escape/EscapeWindowModal.jsx`
- `tests/unit/test_agent_and_rag.py`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Completion Criteria
1. Full Phase 5 implementation completed.
2. All tests in `tests/unit/test_phase5_e2e.py` pass 100%.
3. Existing test suite `backend/.venv/bin/pytest tests/` passes.
4. Write `handoff.md` in `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m3/handoff.md`.
5. Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).

## 2026-11-08T15:13:33Z
[Message] sender=28249f08-094c-49f2-824d-ac8a44bcc29f priority=MESSAGE_PRIORITY_HIGH
**Context**: Milestone 3 Status Check
**Content**: Heartbeat check: inspecting progress on Phase 5 Emergency Vault & Partner Dual-Flow. We observed backend/app/api/v1/partner.py has been created.
**Action**: Please update progress.md with your current step and let us know your status.
