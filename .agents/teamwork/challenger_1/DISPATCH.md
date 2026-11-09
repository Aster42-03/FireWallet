# Dispatch: Adversarial Empirical Verification (challenger_1)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Project Document: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Codebase: `backend/` and `frontend/`

## Role & Mission
You are `challenger_1`, an instance of `teamwork_challenger`.
Your mission is to empirically stress-test and adversarially challenge the FireWallet system:
1. Write and execute test scripts/harnesses testing:
   - Zero-sum double-entry ledger invariants: verify that across arbitrary series of reallocations, emergency draws, and batch payouts, total net worth is conserved to the exact cent (`-Bank / +Bucket = $0.00`).
   - Vault-to-Bank cascade: verify partial draws ($100 Vault + $50 Bank = $150 draw) and complete exhaustion ($0 Vault + $100 Bank = $100 draw).
   - Partner approval replay attacks: verify replaying approved or rejected tokens yields HTTP 409 Conflict.
   - Batch Dispatcher blast radius: verify attempts to specify `source_bucket="bank"` fail immediately with HTTP 400.
2. Run pytest suite and any custom empirical test scripts.

## Required Output
Write your adversarial evaluation report to:
`/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/challenger_1/report.md`
Write `handoff.md` in your working directory stating your explicit verdict: `APPROVE` or `REQUEST_CHANGES`.
Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).

## 2026-11-08T15:19:20Z
Received dispatch from parent orchestrator (28249f08-094c-49f2-824d-ac8a44bcc29f):
"You are challenger_1, an instance of teamwork_challenger.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/challenger_1/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/challenger_1/DISPATCH.md, /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md, and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md.
Follow all instructions in DISPATCH.md.
Empirically stress-test double-entry invariants, Vault-to-Bank cascade, partner token replay attacks, and blast radius containment.
Write report.md and handoff.md in your working directory stating your verdict (APPROVE or REQUEST_CHANGES).
Notify parent orchestrator (28249f08-094c-49f2-824d-ac8a44bcc29f)."
