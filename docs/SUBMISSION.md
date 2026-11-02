# PayPilot AI: Devpost write-up

Copy each section into the matching Devpost field. Edit freely.

**Prize tracks:** the main prizes, plus the **Best Use of AG Grid** sponsor prize (AG Grid ledger, and AG Studio with
custom widgets and the Studio Agent Framework on the Insights page).

**Links**
- Live demo: https://paypilot-web-qxy9.onrender.com (no sign-up; PayPal sandbox buyer login is in the README)
- Code: https://github.com/Nonga001/PayPilot-AI
- Video: (paste your YouTube link)

## Tagline

Let AI handle the payments. Keep it from paying the wrong person.

## Inspiration

Small businesses run on trust and thin margins. Many pay overseas suppliers and freelancers through PayPal. One
wrong payment (an invoice paid twice, a mistyped amount, or a supplier's email quietly swapped by a fraudster) can
wipe out a week's profit. AI assistants that "just pay" make that worse: a model can misread "$45" as "$450", or be
talked into ignoring its rules by a line hidden in an invoice.

We wanted the speed of an AI agent with the caution of a careful bookkeeper.

## What it does

Type what you need in plain words, or upload a supplier's invoice:

- **Pay a supplier**: "Pay my supplier Acme Supplies $45 for the packaging order, invoice INV-1042"
- **Get paid**: "Invoice Maria Lopez (maria@…) €250 for the logo design"
- **Ask**: "Have I already paid Kamau Logistics this week?"
- **Upload an invoice** (PDF or photo): PayPilot reads the vendor, total and invoice number and drafts the payment

The agent looks things up before proposing anything: your saved payees, your payment history, today's budget and
your invoices on PayPal. You see each step. Then deterministic rules check the proposal and explain the result in
plain language. You approve, and PayPal carries it out: **Payouts** for suppliers, **Invoicing** for clients,
**Checkout** for someone new. You get a receipt, and every step goes into a hash-chained audit log.

What it stops:
- **Hidden instructions**, in a request or in invisible text inside a PDF
- **Invoice scams**: a known supplier asking to be paid at a new email is flagged for the owner to confirm
- **Paying twice**: the same invoice number, or the same amount to the same person this week
- **Made-up details**: every amount and email must appear in the owner's words, the invoice, or the saved payees

The **Insights** page, built with AG Studio, shows what the rules stopped, flagged and paid. Owners can filter it,
add their own widgets, or ask the assistant, which hands safety questions to PayPilot's own Risk analyst agent.

## How we built it

- **Agent**: Groq (`openai/gpt-oss-20b`) with tool calling. Read-only tools (`find_payee`,
  `check_payment_history`, `get_budget`, `search_paypal_invoices`) and terminal tools (`propose_payment`,
  `propose_invoice`, `answer`). The agent can only propose; it can't move money.
- **Policy engine** (Python, pure functions): prompt-injection scan, amount grounding against the original
  message, recipient-email grounding, a changed-payment-email check against the saved payee, per-currency limits,
  duplicate-invoice and repeat-payment detection, new-payee review, and AI confidence. It runs when a proposal is
  made and again right before PayPal is called.
- **Invoice reading**: `pypdf` extracts text and Groq reads the fields; photos go to a Groq vision model. Every figure
  must appear on the page, the whole text is scanned for injection, and a "pay us at a new email" line is always
  passed on to the rules.
- **PayPal**: Payouts, Invoicing v2 and Orders v2, with cached OAuth, connection pooling, PayPal-Request-Id
  idempotency keys and an atomic "executing" state against double payment.
- **AG Grid**: the ledger (sort, filter, search, CSV export).
- **AG Studio** (Insights): three pages on PayPilot's own data, a theme mapped to the app's design tokens, and two
  **custom widgets**: a safety funnel that reads Studio's data engine (so it follows every filter) and a live
  audit-chain check. With the **Studio Agent Framework**, Studio's built-in agents run on Groq through our API (the
  key never reaches the browser), plus a custom **Risk analyst** agent with three PayPilot tools. The lead agent
  delegates safety questions to it.
- **Backend**: FastAPI and SQLite with automatic migrations, and a SHA-256 hash-chained audit log.
- **Frontend**: Next.js 16, Tailwind 4, Lucide icons.
- **Resilience**: if Groq is down or rate-limited, a rule-based parser runs the same tools and routes everything to
  human review.

## Challenges

- Making the AI useful without letting it hold the pen: amounts and emails are always re-checked by code, never
  taken on the model's word.
- Payouts vs Checkout: Checkout is a customer paying a merchant, not a business paying a supplier. Moving the
  supplier flow to Payouts made the product honest.
- Testing invoice upload against the live AI showed it sometimes skipped the "new payment email" line, the exact
  scam we wanted to catch. A fixed rule now makes sure that line always reaches the policy engine.
- Running AG Studio's agents on Groq's free plan meant keeping requests small: the Risk analyst answers from compact
  tool results, and the API waits out short rate limits.

## Accomplishments

- An agent whose reasoning you can watch, step by step, before you approve anything
- Prompt injection (even hidden in a PDF), invoice scams, hallucinated amounts and duplicate invoices are all caught
  by rules, with tests for each (29 tests)
- A custom AG Studio agent and custom widgets working on live payment-safety data
- A tamper-evident audit trail with one-click verification

## What we learned

The most useful thing an AI can do in payments is the legwork: reading, looking things up, cross-checking and
explaining. The decision itself belongs to fixed rules and a person.

## What's next

- Scheduled and recurring supplier payments
- Two-person approval for large payments
- Postgres instead of SQLite for production
- Confirming changed payment details with the supplier automatically, through a known contact

## Built with

PayPal Payouts, PayPal Invoicing, PayPal Orders, Groq, gpt-oss-20b, gpt-oss-120b, Qwen (vision), Python, FastAPI,
SQLite, pypdf, Next.js, React, Tailwind CSS, AG Grid, AG Studio, Lucide, Render

## AI tools used and how

- **Groq (gpt-oss-20b)**: the in-product agent (tool calling for lookups, structured proposals) and invoice reading
- **Groq (gpt-oss-120b and gpt-oss-20b)**: the AG Studio assistant and the Risk analyst agent
- **Groq (Qwen vision model)**: reading photos of invoices
- **Claude**: coding assistant for parts of the backend, UI and tests
- **DeepSeek**: coding assistant for early scaffolding
