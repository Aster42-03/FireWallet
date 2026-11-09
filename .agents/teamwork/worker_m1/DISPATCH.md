# Dispatch: Milestone 1 - Quick Intent Category Classification Bug Fix & Scaffolding Cleanup (worker_m1)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Project Architecture & Contracts: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Investigation Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/report.md` (Section 2: R4)

## Role & Mission
You are `worker_m1`, an instance of `teamwork_worker`.
Your mission is to implement M1: Quick Intent Category Classification Bug Fix and Scaffolding Cleanup, and log BUG-009 in `docs/bugs.md`.

## Exclusive Write Ownership
You exclusively own and may edit:
- `backend/app/agents/shared/llm_client.py`
- `backend/app/agents/intent/parser.py`
- `docs/bugs.md`

You MUST NOT edit files owned by other milestones.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Technical Specifications
1. In `backend/app/agents/shared/llm_client.py`:
   - Remove `"food"` from the `groceries` token list (around line 199) to stop dining utterances (e.g., "Thai food", "fast food") from incorrectly categorizing as `groceries` before `eating_out` can be checked.
   - Clean up lines 178 and 190: normalize `medical_emergency` and `savings_violation` to `emergency`.
   - Ensure the category output is strictly drawn from the canonical core category set: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out` (or `dining_out`), `emergency`.
2. In `backend/app/agents/intent/parser.py`:
   - Clean up any fallback scaffolding artifacts so valid categories are returned.
3. In `docs/bugs.md`:
   - Log `BUG-009: Quick Intent Category Classification Collision from Lingering Scaffolding Artifacts` following the established format in `docs/bugs.md`. Detail Symptom, Root Cause, Fix, and Verification.
4. Run verification tests:
   - Run `backend/.venv/bin/pytest tests/` to confirm all 44 existing tests continue to pass and no regressions were introduced.
   - Add/run unit tests checking intent categorization across all 7 core categories.

## Completion Criteria
1. Changes implemented cleanly in target files.
2. `BUG-009` logged in `docs/bugs.md`.
3. All tests pass (`backend/.venv/bin/pytest tests/`).
4. Write `handoff.md` in `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m1/handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
5. Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).


## 2026-11-08T14:45:34Z
You are worker_m1, an instance of teamwork_worker.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m1/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/worker_m1/DISPATCH.md, /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md, and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md.
Follow all instructions in DISPATCH.md.
Implement M1: Quick Intent Category Classification Bug Fix & Scaffolding Cleanup, and log BUG-009 in docs/bugs.md.
Run tests and verify.
Write handoff.md in your working directory and notify parent orchestrator (28249f08-094c-49f2-824d-ac8a44bcc29f).
