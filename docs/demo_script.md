# Demo Video Script (Target: 2:30–2:45, Strictly < 3:00)

Judges are **not required** to watch past three minutes. The video must show **FireWallet** working live on both the mobile HUD surface (`view='hud'`) and the desktop **AG Grid** surface (`view='deep-ledger'`). Public YouTube upload, captions enabled, no copyrighted music, and **no third-party brand trademarks** (use generic merchant names only).

Related: **[problems.md](problems.md) (Problem 6 — Demo Video & Presentation Gate)**, [hackathon_overview.md](hackathon_overview.md), [product.md](product.md).

---

## Story & Voluntary-Commitment Thesis (One Sentence Each)

- **What FireWallet Is:** Envelope apps and AI chatbots analyze money *after* it is gone; **FireWallet** puts an LLM-parsed *why* and a deterministic policy engine (`propose → verify → confirm → execute`) directly in front of PayPal checkout.
- **The Voluntary-Commitment Model:** Nobody can tie someone down if they are set on finding a loophole—FireWallet is built for people who *want* financial discipline and need structured friction to keep it, enforcing the rules you set when calm at the exact moment of payment.

---

## Pre-Roll Setup (Before Recording)

- **Seeded Policy & Balances (Consistent Across Setup & Voiceover):**
  - **Bank Foundation:** `$800.00` (locked; protects upcoming bills)
  - **Reserved Bills:** `$1,200.00` (Rent earmarked)
  - **Daily Living Allowance:** `$52.00` available (`$40.00` daily target + `$12.00` rollover streak from yesterday)
  - **Freedom Envelope:** **`$5.00` remaining** out of `$150.00` monthly cap (matches the voiceover when testing the `$35.00` late-night impulse order)
  - **Savings Vault:** `$200.00` (Emergency Reserve + Camera Sinking Goal)
- **Escape Window Cooldown:** Set to **15 seconds** via `BucketConfigModal` during the demo so the server countdown completes live on camera without cutting.
- **Environment:** Local development environment open (`http://localhost:5173`); PayPal Sandbox buyer credentials ready; `/api/v1/webhooks/paypal` verified green; generic merchant names only (`Local Fresh Market`, `Late-Night Sushi Delivery`).

---

## 6-Beat Storyboard (2:40 Total Runtime)

| Timestamp | Beat & Surface | On-Screen Action | Voiceover Script | Proof Shown to Judges |
| :--- | :--- | :--- | :--- | :--- |
| **0:00–0:12** *(12s)* | **1. The Hook & Commitment**<br/>*(Mobile HUD `view='hud'`)* | Show Mobile HUD with Protected panel (*Rent Protected: $1,200 · Rollover Streak: 4 days*), Daily `$52`, and Freedom `$5 left`. | "It's 1 a.m., you want $35 sushi, and rent is due Monday. Traditional budget apps only hold an autopsy after your money is gone. FireWallet is a voluntary-commitment firewall: you set your rules when calm, and it enforces them in front of PayPal before you spend." | High-contrast Mobile HUD, Protected panel, and explicit commitment rule banner. |
| **0:12–0:55** *(43s)* | **2. Real Payment (`Propose → Verify → Confirm → Execute`)**<br/>*(Mobile HUD → PayPal Sandbox)* | Open Quick Intent. Enter `$24.00`, *"Buying dinner groceries"*, merchant *"Local Fresh Market"*. Show AI verdict card with rationale & confidence. Tap 1-tap PayPal button, approve in real PayPal Sandbox, return as webhook settles. | "Every payment starts with why. For $24 of groceries at Local Fresh Market, the AI proposes `daily_living` with 96% confidence, and deterministic Python verifies our $52 Daily balance. We confirm with one tap, approve in PayPal Sandbox, and a signed webhook settles the double-entry hold." | Live AI verdict rationale, visible `sandbox.paypal.com` URL, Order ID & Capture ID, Daily balance updates `$52 → $28`. |
| **0:55–1:30** *(35s)* | **3. Blocked Impulse & Escape Window**<br/>*(Mobile HUD)* | Open Quick Intent. Enter `$35.00`, *"Bored at 1 a.m., ordering sushi"*, merchant *"Late-Night Sushi Delivery"*. Show **BLOCKED** verdict (`Freedom has $5 left`). Open Escape Window, type 200-char reflection confession, watch 15s server timer finish. | "Now watch 1 a.m. impulse. We try $35 for late-night sushi, but Freedom only has $5 left. FireWallet blocks the checkout so we don't raid rent. To override our own rule, we face the Escape Window: a 200-character reflection confession and a server-enforced cooldown timer." | Blocked state (no PayPal button), 200-char counter, live 15s countdown completing to unlock override. |
| **1:30–1:50** *(20s)* | **4. Real Enforcement Proof: Vault Payout & Protected Panel**<br/>*(Mobile HUD + PayPal Sandbox Activity)* | Trigger Payday / Vault skim (`Simulate Payday`). Show PayPal Payout batch `SUCCESS` arriving in the separate Vault receiver sandbox account and the Protected HUD panel updating. | "Where possible, FireWallet moves money physically out of reach. On payday, our 20% Vault skim executes a real PayPal Payout to a separate sandbox account—while the Protected panel tracks every dollar of rent shielded and impulse blocked." | PayPal Payout Batch ID (`SUCCESS`), separate receiver balance rising, Protected HUD metrics. |
| **1:50–2:25** *(35s)* | **5. AI Coach & AG Grid Workbench**<br/>*(Desktop `view='deep-ledger'`)* | Switch to `Deep Ledger` (AG Grid). Expand master/detail transfer legs (`transfer_id`), click *"Analyze with Coach"*, ask *"Which dining transactions caused my Freedom burn?"* Show tool citations and AG Grid highlighting flagged rows. | "On desktop, AG Grid powers our double-entry audit workbench with zero-sum transfer inspection and category grouping. When we ask the Financial Coach why Freedom burned early, it cites live ledger tools and highlights the exact anomalous rows right inside AG Grid." | AG Grid grouping/filtering, Order/Capture IDs, Coach tool citations, flagged rows highlighted in grid, zero watermark. |
| **2:25–2:45** *(20s)* | **6. Architecture Close**<br/>*(End Card)* | Show clean architecture summary (`Propose → Verify → Confirm → Execute`), public GitHub repo, and MIT License. | "Propose with AI, verify with deterministic code, confirm by human commitment, and execute on PayPal Sandbox. FireWallet turns financial discipline into code." | GitHub repo link, MIT License, and PayPal Sandbox + AG Grid stack summary. |

---

## Production & Filming Checklist (Per [problems.md](problems.md) Problem 6)

- [ ] **Consistent Numbers:** Setup and voiceover both show **$5.00 remaining** in Freedom before the $35.00 sushi attempt.
- [ ] **Zero Third-Party Trademarks:** Only generic merchant names (`Local Fresh Market`, `Late-Night Sushi Delivery`, `Metro Transit`) appear on screen and in voiceover.
- [ ] **Captions Included:** Burned-in or YouTube SRT captions so a viewer watching muted understands the entire flow.
- [ ] **No Unlicensed Music or Watermarks:** Voiceover recorded cleanly; AG Grid renders with zero trial/license watermark.
- [ ] **Public YouTube Link Tested:** Verified in an incognito window before Devpost submission.
