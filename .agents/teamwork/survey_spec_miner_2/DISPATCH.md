# Survey Task: The Trinity Batch Dispatcher Specification & Codebase Mapping (R2)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Features Specification: `/home/aster42/projects/full-stack/FireWallet/docs/features.md`
- Codebase: backend models, schemas, routers, services (bills, coach, PayPal payouts), and frontend bills components.

## Mission
Investigate and extract the complete specifications and technical requirements for:
1. Backend `BatchPaymentItem` SQLModel database model:
   - Fields, relationships, states (queued, executing, completed, failed, cancelled, etc.)
2. AI Coach `BatchDispatcherProposal` structured output schema:
   - Structure, risk assessment fields, blast radius containment (vault/bills isolation)
3. REST Endpoints:
   - `POST /api/v1/bills/batch-dispatcher/propose`
   - `POST /api/v1/bills/batch-dispatcher/execute`
   - `GET /api/v1/bills/batch-dispatcher/queue`
   - Sequential, idempotent PayPal Payouts execution
   - Clean failure handling when offline or missing live PayPal Sandbox credentials
4. Frontend Staging Area Interface:
   - User veto toggling for queued items before dispatch
   - Real-time execution status display
5. Identify existing bills/payouts code and tests in `tests/`.

## Required Outputs
Write your detailed report to:
`/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/report.md`
and write your standard `handoff.md` in your working directory.
Report back via `send_message` when complete.


## 2026-11-08T14:33:32Z
You are survey_spec_miner_2, an instance of teamwork_spec_miner.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/DISPATCH.md and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md.
Follow all instructions in DISPATCH.md.
Investigate The Trinity Batch Dispatcher (R2: BatchPaymentItem SQLModel, BatchDispatcherProposal schema, REST endpoints, live PayPal Sandbox requirement & failure handling, frontend staging area interface).
Produce your comprehensive investigation report at:
/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_spec_miner_2/report.md
and write handoff.md in your working directory.
When done, send a message to your parent orchestrator (conversation ID: 28249f08-094c-49f2-824d-ac8a44bcc29f) reporting completion.
