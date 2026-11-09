# Survey Task: Bills Envelope Config, Quick Intent Scaffolding Fix, PayPal Routing & Roadmap (R3, R4, R5, R6)

## Context & Inputs
- Original Request: `/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md`
- Documentation: `docs/bugs.md`, `docs/paypal_integration.md`, `docs/architecture.md`, `docs/agent_design.md`, `docs/ROADMAP_PHASE4_PHASE5.md`
- Codebase: `frontend/src/features/hud/BucketConfigModal.jsx`, backend budget policy / ledger rebalancing, intent classification parser/heuristics, PayPal client and routing logic.

## Mission
Investigate and extract the specifications and implementation details for:
1. Configurable Bills Envelope in Envelope Settings (R3):
   - Examine `frontend/src/features/hud/BucketConfigModal.jsx` and HUD state/telemetry
   - Trace backend budget policy and double-entry rebalancing (`-Bank / +Bills = $0.00`)
   - How targets are stored, validated, and updated
2. Quick Intent Category Identification Bug & Scaffolding Cleanup (R4):
   - Identify old scaffolding artifacts in backend parser/heuristics and frontend Quick Intent causing category misidentification
   - Enumerate exact core categories: `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`/`dining_out`, `emergency`
   - Review format for logging in `docs/bugs.md`
3. Real-Time PayPal Account Routing Identification & Documentation (R5):
   - Trace live codebase: how PayPal determines payee/destination accounts across buyer checkouts (Orders v2 payee defaults), internal bucket transfers, emergency disbursements, and Payouts
   - Identify what needs to be added to `docs/paypal_integration.md`, `docs/architecture.md`, `docs/agent_design.md`
4. Roadmap update and rename (R6):
   - Review `docs/ROADMAP_PHASE4_PHASE5.md` and planned rename to `docs/ROADMAP_PHASE5.md`
5. Identify existing tests in `tests/` covering these areas.

## Required Outputs
Write your detailed report to:
`/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/report.md`
and write your standard `handoff.md` in your working directory.
Report back via `send_message` when complete.


## 2026-11-08T14:33:39Z
You are survey_explorer_3, an instance of teamwork_explorer.
Your working directory is: /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/
Read /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/DISPATCH.md and /home/aster42/projects/full-stack/FireWallet/.agents/teamwork/ORIGINAL_REQUEST.md.
Follow all instructions in DISPATCH.md.
Investigate R3 (Bills Envelope config in BucketConfigModal & double-entry rebalancing), R4 (Quick Intent category bug & scaffolding cleanup), R5 (Real-time PayPal account routing & doc updates), and R6 (Roadmap update and rename).
Produce your comprehensive investigation report at:
/home/aster42/projects/full-stack/FireWallet/.agents/teamwork/survey_explorer_3/report.md
and write handoff.md in your working directory.
When done, send a message to your parent orchestrator (conversation ID: 28249f08-094c-49f2-824d-ac8a44bcc29f) reporting completion.
