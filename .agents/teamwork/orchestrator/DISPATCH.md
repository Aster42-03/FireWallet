## 2026-11-08T14:30:48Z

Implement Phase 5 (Emergency Vault allocation, autonomous payment execution, and accountability partner dual-flow escape window), The Trinity Batch Dispatcher, Bills configuration from the envelope settings modal, Quick Intent category identification bug fix, real-time PayPal account routing identification, and update all affected documentation.

Working directory: /home/aster42/projects/full-stack/FireWallet
Integrity mode: development

## Requirements

### R1. Phase 5 Implementation (Emergency Vault & Accountability Partner Dual-Flow)
Implement Phase 5 across the backend and frontend per the Phase 5 Implementation Plan:
1. Emergency Vault Allocation & Autonomous Payment Execution (`BUG-008`): verified genuine emergencies auto-route to `vault` with 0s cooldown bypass; cascade available vault + remainder from bank if vault funds are insufficient; empower the AI Coach to execute transactions autonomously once payment details are verified.
2. Accountability Partner Escalation & Dual-Flow Escape Window: when a partner is linked, dispatch an approval token (returned in the API response and displayed in the in-app UI / server logs for copy/testing); if the partner approves within the window, spend unlocks immediately with 0s cooldown and 0 confession characters; if the partner does not approve within the set time, enforce a 200-character reflective confession and a 180s countdown timer; dispatch a final outcome alert to the partner logging whether the payment was made or cancelled.
3. Model Branding Removal: ensure no model or vendor branding (e.g., Groq, Llama, OpenAI, Gemini) is displayed anywhere in the UI.

### R2. The Trinity Batch Dispatcher Implementation (`docs/features.md`)
Implement The Trinity Batch Dispatcher bridging AI Coach bill analysis with autonomous payout execution:
1. Backend: Implement `BatchPaymentItem` SQLModel database model, AI Coach `BatchDispatcherProposal` structured output schema, and REST endpoints (`POST /api/v1/bills/batch-dispatcher/propose`, `POST /api/v1/bills/batch-dispatcher/execute`, `GET /api/v1/bills/batch-dispatcher/queue`) enforcing vault/bills blast radius containment and idempotent sequential PayPal Payouts. Require live PayPal Sandbox credentials for batch payout execution and fail cleanly if offline or credentials are missing.
2. Frontend: Implement a Staging Area interface allowing human veto toggling of queued payment items before dispatch, and displaying real-time execution status.

### R3. Configurable Bills Allocation in Envelope Settings (`BucketConfigModal.jsx`)
Enable the Reserved Bills bucket to be configured from the "Configure Envelopes" modal:
1. Frontend: Add a field in `frontend/src/features/hud/BucketConfigModal.jsx` allowing the user to view and set the Reserved Bills target amount ($ USD) or allocate funds from Bank Foundation to Bills.
2. Backend: Update budget policy handling and double-entry rebalancing so that configuring the bills target executes paired double-entry transfers (`-Bank / +Bills = $0.00`), allowing users to move money from Bank Foundation to the Reserved Bills section cleanly.

### R4. Quick Intent Category Identification Bug (Log and Fix)
Log an entry in `/home/aster42/projects/full-stack/FireWallet/docs/bugs.md` detailing that quick intent payments misidentify categories due to lingering scaffolding artifacts. Resolve this bug in the codebase by cleaning up old scaffolding artifacts in backend parser/heuristics and frontend Quick Intent, ensuring spending intents are accurately classified into the core category set (`groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`/`dining_out`, `emergency`).

### R5. Real-Time PayPal Account Routing Identification & Documentation
Identify from the live codebase and test environment how PayPal determines which account to pay across buyer checkouts (Orders v2 payee defaults), internal bucket transfers, emergency disbursements, and Payouts. Update `/home/aster42/projects/full-stack/FireWallet/docs/paypal_integration.md` and cross-reference the findings in relevant documentation such as `docs/architecture.md` and `docs/agent_design.md`.

### R6. Roadmap Update and Renaming
Update `/home/aster42/projects/full-stack/FireWallet/docs/ROADMAP_PHASE4_PHASE5.md` to document the implementation of Phase 5, The Trinity Batch Dispatcher, and Bills envelope configuration, and rename the file to `/home/aster42/projects/full-stack/FireWallet/docs/ROADMAP_PHASE5.md`.

## Verification Resources
- Existing automated test suite: `pytest tests/`
- Documentation files in `/home/aster42/projects/full-stack/FireWallet/docs/`
- Phase 5 Implementation Plan: `/home/aster42/.gemini/antigravity/brain/110647b1-24c2-490f-aaff-6cd41f7efd42/phase5_implementation_plan.md`
- Features specification: `/home/aster42/projects/full-stack/FireWallet/docs/features.md`
