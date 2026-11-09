# Hackathon Overview & Strategic Evaluation

**Source of truth:** [PayPal AI Hackathon on Devpost](https://paypalaihackathon.devpost.com/) and [official rules](https://paypalaihackathon.devpost.com/rules).

Related: **[problems.md](problems.md) (Core Build Gate & Honest Review)**, [demo_script.md](demo_script.md), [product.md](product.md).

> [!IMPORTANT]
> **Authoritative Build Gate ([problems.md](problems.md)):**
> Every FireWallet product, architectural, and engineering choice must be evaluated against **[problems.md](problems.md)** (*Honest Review and Prioritized Action Plan*). All features not in the video or judge quick start are frozen on the **Cut List (Section 7)** until after submission.

## What the Challenge Actually Requires

PayPal is asking what happens when AI sits behind real money movement. There are no prescribed tracks. The core requirement:

> The project must **meaningfully use both PayPal and AI**, run as a functional prototype on target devices, and be submitted with a public GitHub repo, open-source license, and a video under 3 minutes.

Sandbox is the intended environment. Partner tools (Render, AG Grid, Postman, APIMatic) enable cloud reliability and data visibility:

- **PayPal is the execution layer** — Orders v2 (captures), Payouts (Vault skim), Reporting Balances, and Webhooks (`/api/v1/webhooks/paypal`) — not a logo on a mock ledger.
- **AI is the proposal and deep intelligence layer (`Propose → Verify → Confirm → Execute`)**:
  - *Propose:* Single-call Groq `openai/gpt-oss-120b` (with OpenAI fallback) parses spend intent *why*, distills RAG `short_tag` memory, and outputs `CoachDecision` + 1-tap `ActionCard`.
  - *Verify:* Deterministic Python `LedgerEngine.can_spend` checks policy invariants and enforces reflection friction. The LLM never moves money.
  - *Confirm:* User confirms 1-tap card or completes Escape Window reflection.
  - *Execute:* PayPal Orders/Payouts execute and settle via signed webhooks.
- **The product is dual-surface**:
  - *Mobile HUD Surface (`view='hud'`):* Clean, minimalist Tailwind cards with Quick Intent FAB and Protected panel.
  - *Desktop Admin Surface (`view='deep-ledger'`):* High-density audit workbench powered by **AG Grid**.
  - *Cloud:* Hosted live on **Render** (`https://firewallet-web.onrender.com`).

---

## Key Deadlines (November 2026)

| Milestone | Exact Date & Time | Notes |
| :--- | :--- | :--- |
| **Official Devpost Deadline** | **Thu Nov 12, 12:00 PM PST** *(Fri Nov 13, 1:30 AM IST)* | Hard cutoff. Devpost locks all edits. |
| **Recommended Internal Submission Deadline** | **Thu Nov 12, 6:00 PM IST** | Provides **7.5 hours of buffer** for video processing, clean-clone verification, and final sanity checks. |
| **Judging Period** | Tue Dec 1, 14:00 PST → Tue Dec 15, 08:00 PST | Judges test live URLs or clean-clone SOPs. |
| **Winners Announced** | On or around Mon Dec 21, 14:00 PST | Devpost / PayPal Developer Community. |

Internal implication: a judges-runnable prototype, a live Render production URL, and a sub-3-minute video must exist **before 12 Nov 2026**.

## Eligibility (summary)

Open to age-of-majority individuals, teams, and organizations, excluding standard OFAC / conflict-of-interest exceptions (including Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea, and other comprehensively sanctioned territories — check current rules).

Team or org entries need a single Representative on Devpost.

## What to build (Project Requirements)

Build or update an application that:

1. Integrates the **PayPal developer platform** using the **free sandbox**.
2. Incorporates an **AI tool, model, or platform** of our choice (dual agents: Intent Gateway and Advanced Reasoning Coach).
3. Is a **working prototype** (installable and consistent with the video).
4. Is **documented** enough for judges to evaluate.
5. Complies with Official Rules.

Existing projects are allowed if **significantly updated during the submission period**. FireWallet is new; still keep a short “what we built during the window” note in the public README later.

PayPal’s platform in the rules includes PayPal, Venmo, Braintree, Xoom, Honey, Zettle, Paidy, Hyperwallet, Simility, Swift Financial, and others. FireWallet’s first draft stays on **PayPal REST sandbox** (Orders, Payouts, Identity, Webhooks). Expanding to Venmo/Braintree is a later decision, not a requirement.

### Sponsor tools (Foundational Strategy)

FireWallet deeply integrates key sponsor technologies as foundational pillars of the architecture:

- **Render (Foundational Cloud Hosting):** Hosts our live production FastAPI web service, React static site, and PostgreSQL database via `render.yaml`. Provides the live production URL required for Devpost and directly targets the **Render Sponsor Prize**.
- **AG Grid (Foundational Desktop Deep Analytics):** Powers the desktop "Advanced Ledger & Audit Log" view (`/analytics/deep-ledger`). Features multi-column sorting, granular filtering, category grouping, and direct "Analyze with Coach" deep intelligence, directly targeting the **AG Grid Sponsor Prize**.
- **Postman:** Pre-configured collection for developer smoke-testing and automated endpoint contract verification.
- **APIMatic:** OpenAPI context generation ensuring typed, hallucination-free AI code generation in Cursor.

None of these replace PayPal API calls in the runtime path.

## What to submit (checklist)

Copy this into the public repo README before submission.

- [ ] Working project using PayPal sandbox **and** an AI model/service
- [ ] Text description of features (Devpost + README)
- [ ] Functional demo: **live Render production URL** and complete local setup in the repo (SOPs).
- [ ] Tools list: which AI model/service, how it is used, which PayPal APIs, Render, AG Grid
- [ ] Public GitHub/GitLab/Bitbucket repo with **all source**, assets, run instructions
- [ ] **Open source license file** visible at repo root (About section)
- [ ] Demo video **under 3 minutes**, YouTube public, shows the app **working on the target device**
- [ ] No unlicensed third-party trademarks or copyrighted music in the video

Judges are **not required** to watch past three minutes. See [demo_script.md](demo_script.md).

## Judging

### Stage one (pass/fail)

Does the project reasonably fit the theme and **reasonably apply the required PayPal APIs/SDKs**?

FireWallet fails stage one if:

- Spend is only a Postgres `UPDATE` with a “PayPal” comment.
- AI is a generic chatbot that never gates a payment.
- Demo is Figma or a recorded slideshow of mock balances.

### Stage two (equal weights)

| Criterion | FireWallet translation |
| --- | --- |
| **Technological Implementation** | Real sandbox Orders/Payouts/Webhooks + real LLM intent parse + read-only coach over deterministic analytics; SQLModel + asyncpg ledger; live Render deployment. |
| **Design** | Clean mobile HUD on phone (`/`) with Quick Intent FAB; enterprise desktop admin workbench powered by **AG Grid** with deep analysis capabilities. |
| **Potential Impact** | Impulse spend vs rent/utilities is a real crisis for students and irregular earners; firewall prevents disaster while coach builds long-term literacy. |
| **Innovation/Idea** | Proactive intent firewall + reactive financial literacy coach with deep ledger reasoning — not another after-the-fact pie chart. |
| **Presentation** | 3-minute video: HUD → intent → PayPal money move → blocked impulse → coach affordability & chart explanation → AG Grid desktop inspection → override cost. |

Tie-break order follows the criteria list above.

## Prize targets (how we aim)

Cash pool is on the order of **$67,500+** (Devpost listing; partner pages sometimes say $60k+).

**Primary:** Grand prizes (1st $12k / 2nd $8k / 3rd $5k) via a complete, working product.

**Aligned specials:**

- Best Use of PayPal + AI ($5k)
- Best Use of Agentic Commerce ($5k)
- Most Impactful / Best Demo Delivery if the firewall story is clear

**Foundational Sponsor Targets:**

- **Render Sponsor Prize** (Live production URL, multi-service `render.yaml` blueprint, managed PostgreSQL).
- **AG Grid Sponsor Prize** (Enterprise desktop ledger, multi-column sorting, grouping, direct reasoning integration).

A project can typically win **at most one grand prize and one sponsor prize** (confirm current rules before submission).

## Decision filter (use on every feature)

Ask, in order:

1. Does this **execute or observe money on PayPal sandbox**?
2. Does **AI change the payment path** (approve, route, or block), or deliver grounded **deep financial literacy** without touching execution keys?
3. Can a judge **see it in under 90 seconds** on a phone or laptop?
4. Does it **enforce a rule the user already set**, rather than inventing new financial products?
5. If we skip it, does the 3-minute demo still tell the FireWallet story?

If (1) or (2) is “no” for a week of work, drop or defer it.

## Official links

- Challenge: <https://paypalaihackathon.devpost.com/>
- Rules: <https://paypalaihackathon.devpost.com/rules>
- PayPal Developer: <https://developer.paypal.com/>
- Sandbox API base: `https://api-m.sandbox.paypal.com`
- PayPal AI Toolkit (dev-time): <https://github.com/paypal/AI-Toolkit>
- PayPal MCP: <https://github.com/paypal/paypal-mcp-server>
- Community post: <https://developer.paypal.com/community/blog/PayPal_AI_Hackathon/>
- Questions: janet@devpost.com
