# Demo script (under 3 minutes)

Judges are **not required** to watch past three minutes. The video must show the app **working live** on both the mobile PWA view and the desktop AG Grid view, hosted live on **Render**. Public YouTube upload, no copyrighted music, no mock toasts.

Total target runtime: **2 minutes 50 seconds** (strictly under the 3:00 cutoff).

---

## Story in One Sentence

**FireWallet** is a proactive financial firewall and AI coach: AI parses *why* you are spending, PayPal only moves money if your Trinity bucket rules allow it, an Advanced Reasoning Coach explains complex patterns, and an AG Grid desktop workbench provides deep transaction intelligence.

---

## Pre-roll Setup (not in video)

- User seeded in database with Trinity policy: Daily $40 target + $12 rollover, Bank $800, Vault $200, Bills $1,200 (Rent), Freedom $25 remaining.
- Render live production app ready (`https://firewallet-web.onrender.com`).
- PayPal sandbox personal buyer logged in or credentials auto-filled.
- Webhooks live and verified green.
- Primary recording on phone screen (390×844); secondary browser window open to desktop AG Grid view (`/analytics/deep-ledger`).

---

## Storyboard & Timing Beats

| Timestamp | Visual (on screen) | Voiceover Script | Proof / Action |
| :--- | :--- | :--- | :--- |
| **0:00–0:20** *(20s)* | **Mobile HUD (`/`)**<br/>Show Bank locked card, Daily hero with `+$12` rollover badge, safe Vault/Bills strip, and Freedom meter. | "Most budget apps are autopsies—they tell you what happened after your money is already gone. FireWallet is a proactive firewall. It divides your cash into Bank, Daily living, a locked savings Vault, and a guilt-free Freedom envelope." | Mobile HUD UI in high-contrast Tailwind. |
| **0:20–0:40** *(20s)* | **Insights Coach & Chart Literacy**<br/>Tap `chart_pie_week` $\rightarrow$ "What does this pie mean?". Then ask: "Can I afford a $20 movie?" | "Beside the HUD, an AI Financial Coach turns charts into plain English. Tap any chart for an instant breakdown, or ask if you can afford a $20 movie ticket. The coach evaluates your envelope in real time and gives you a one-tap link to the intent firewall." | Coach drawer slides up; returns plain-English breakdown and 1-tap `[Log in Quick Intent]` chip. |
| **0:40–1:15** *(35s)* | **Allowed Spend: "Buying groceries" $24**<br/>Tap Quick Intent FAB. Enter $24.00, "Buying groceries at Safeway". | "Every transaction starts with why. The Intent Agent classifies groceries as daily living, checks our Daily Allowance, and gates PayPal. We tap Pay with PayPal, approve in the real sandbox, and our webhook settles the ledger immediately." | Intent Agent verdict $\rightarrow$ PayPal hosted sandbox approval $\rightarrow$ Webhook settles $\rightarrow$ Daily decrements on HUD. |
| **1:15–1:35** *(20s)* | **Desktop Admin: Foundational AG Grid**<br/>Cut to Desktop View (`/analytics/deep-ledger`). Filter by Daily bucket, group by Category. Tap "Analyze with Coach". | "For deep financial visibility, switch to desktop. Powered by AG Grid, our Advanced Ledger gives you enterprise filtering, grouping, and audit tracking down to PayPal Capture IDs. Our Advanced Reasoning Coach analyzes the filtered grid to diagnose spending velocity and anomalies." | Desktop AG Grid table filtering live transactions; Coach panel analyzes grid state. |
| **1:35–2:10** *(35s)* | **Blocked Impulse: "Late-night sushi" $35**<br/>Back to mobile. Tap Quick Intent FAB. Enter $35.00, "Late-night sushi delivery". | "Now watch what happens when impulse hits. It's 1 a.m. and we want $35 sushi, but our Freedom envelope only has $5 left. FireWallet refuses to silently raid rent money. The firewall blocks the checkout. There is no PayPal button." | Verdict card shows **BLOCKED**; category=freedom; explains bank protection; Escape Window button appears. |
| **2:10–2:35** *(25s)* | **Friction Override (Escape Window)**<br/>Open Escape Window. Enter 200-char confession. Show live cooldown timer. | "To bypass your own rules, you face the Escape Window: a written confession to your future self and a mandatory server-side cooldown timer. There is no one-click bypass. Friction is the feature that saves your rent." | Live countdown timer counting down; execute button returns HTTP 409 until `ready_at`. |
| **2:35–2:50** *(15s)* | **Wrap & Architecture Close**<br/>Show end card with live Render URL, GitHub repository, PayPal sandbox architecture, and AG Grid. | "Hosted live on Render with PayPal sandbox and dual AI agents. FireWallet turns financial discipline into code." | End title card: Live Render URL + GitHub repo + PayPal Sandbox + AG Grid. |

---

## Device & Filming Guidelines

- **Mobile View:** Film the phone screen for the primary mobile HUD, intent capture, and Escape Window beats.
- **Desktop Cut:** Smooth cut at 1:15 to a desktop browser showing the full AG Grid Advanced Ledger.
- **No mocks:** Keep real PayPal sandbox URLs and buyer approval visible in browser address bars.
- **Live URL:** Display the live Render production URL on screen during the closing seconds.
