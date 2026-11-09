# Dispatch: Remediation of Batch Dispatcher Sandbox Guard & Partner Expiration (fix_worker)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Project Document: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/PROJECT.md`
- Gate Status: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/orchestrator/GATE_STATUS.md`
- Reviewer Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/reviewer_1/report.md`
- Challenger Findings: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/challenger_2/handoff.md`

## Role & Mission
You are `fix_worker`, an instance of `teamwork_worker`.
Your mission is to remediate the critical defects discovered during the verification gate:
1. Critical Defect in `backend/app/api/v1/bills.py` (`execute_batch`):
   - Currently, step 5 checks `paypal_client.has_live_credentials()` but fails to verify `token = await paypal_client.get_access_token()`.
   - Update step 5 so that it obtains the access token and checks:
     ```python
     if is_live:
         try:
             token = await paypal_client.get_access_token()
             if not token or token == "mock_sandbox_access_token":
                 is_live = False
         except Exception:
             is_live = False
     ```
     If `not is_live`, raise `HTTPException(status_code=503, detail="Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured.")`.
   - Also ensure that when `req.source_bucket == "bills"`, `available_isolated` does not allow `bills` bucket to dip negative without cascading from `vault`:
     ```python
     if req.source_bucket == "bills":
         available_isolated = bills_avail
     elif req.source_bucket == "vault":
         available_isolated = vault_avail
     ```
     (Or cascade from vault to bills with paired double-entry transfers if approved sum > bills_avail).
2. Partner Expiration in `backend/app/api/v1/partner.py`:
   - In `submit_partner_decision`, verify that token is not older than 24 hours:
     ```python
     if override.created_at and now > override.created_at + timedelta(hours=24):
         raise HTTPException(status_code=status.HTTP_410_GONE, detail="Partner approval token has expired.")
     ```
3. Verification:
   - Run `backend/.venv/bin/pytest tests/api/test_adversarial_empirical_challenger.py -v`.
   - Run the complete automated test suite: `backend/.venv/bin/pytest tests/ -v`.
   - Ensure all tests pass (0 failures).

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Required Output
Write `handoff.md` in `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/fix_worker/handoff.md`.
Notify parent orchestrator (`28249f08-094c-49f2-824d-ac8a44bcc29f`).

## 2026-11-08T15:43:41Z
**Context**: Remediation Progress Check
**Content**: We observed that the fixes in backend/app/api/v1/bills.py (lines 318-361) and backend/app/api/v1/partner.py (lines 124-133) have been successfully written to disk. Are the test suite runs complete?
**Action**: Please complete testing, write handoff.md, and report back.
