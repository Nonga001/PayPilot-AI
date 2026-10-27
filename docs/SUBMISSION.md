# PayPilot AI: Devpost write-up (draft)

Edit freely before pasting into the Devpost form.

## Tagline

A payments agent for small businesses: AI does the legwork, rules check every detail, you stay in charge.

## Inspiration

Small businesses run on trust and thin margins. In Kenya and across Africa, many pay overseas suppliers and
freelancers through PayPal. One wrong payment (paying an invoice twice, a typo in an amount, or a supplier's
email quietly swapped by a fraudster) can wipe out a week's profit. AI assistants that "just pay" make that
worse: a model can misread "$45" as "$450", or be talked into ignoring its rules by text hidden in an invoice.

We wanted the speed of an AI agent with the safety of a careful bookkeeper.

## What it does

Type what you need in plain words:

- **Pay a supplier**: "Pay my supplier Acme Supplies $45 for the packaging order, invoice INV-1042"
- **Get paid**: "Invoice Maria Lopez (maria@…) €250 for the logo design"
- **Ask**: "Have I already paid Kamau Logistics this week?"

PayPilot's agent looks things up before it proposes anything: your saved payees, your payment history, today's
budget, and your invoices on PayPal. You see each step it took. Then a deterministic policy engine checks the
proposal against up to 13 rules and explains the result in plain language. You approve, and PayPal carries it out:
**Payouts** for suppliers, **Invoicing** for clients, **Checkout** as a fallback. You get a printable receipt, and
every step is written to a hash-chained audit log that shows if anything was changed later.

## How we built it

- **Agent**: Groq (`openai/gpt-oss-20b`) with tool calling. Four read-only tools (`find_payee`,
  `check_payment_history`, `get_budget`, `search_paypal_invoices`) and three terminal tools (`propose_payment`,
  `propose_invoice`, `answer`). The agent can't move money; it can only propose.
- **Policy engine** (Python, pure functions): prompt-injection scan, amount grounding against the original
  message, recipient-email grounding (it must come from the message or a saved payee), per-currency limits,
  duplicate-invoice and repeat-payment detection, a new-payee review, and AI confidence. It runs when a proposal is
  made and again right before PayPal is called.
- **PayPal**: Payouts, Invoicing v2 and Orders v2, with OAuth token caching, connection pooling,
  PayPal-Request-Id idempotency keys and an atomic "executing" state against double payment.
- **Backend**: FastAPI and SQLite with automatic migrations, plus a SHA-256 hash-chained audit log.
- **Frontend**: Next.js 16, Tailwind 4, Lucide icons, and AG Grid for the ledger (sort, filter, search, CSV export).
- **Resilience**: if Groq is down or a model is deprecated, a rule-based planner runs the same tools and routes
  everything to human review.

## Challenges

- Making the AI useful without letting it hold the pen: amounts and emails are always re-derived and verified by
  code, never taken on the model's word.
- Payouts vs Checkout: Checkout is a customer paying a merchant, not a business paying a supplier. Switching the
  supplier flow to Payouts made the product honest.
- KES isn't a PayPal transaction currency, so the policy explains that instead of failing at PayPal.

## Accomplishments

- An agent whose reasoning you can watch, step by step, before you approve anything
- Prompt-injection, hallucinated amounts, invented emails and duplicate invoices are all caught by rules, with
  tests for each
- A tamper-evident audit trail with one-click verification

## What we learned

The most useful thing an AI can do in payments is the legwork: lookups, cross-checks and explanations. The
decision itself is better left to deterministic rules and a person.

## What's next

- Invoice upload (PDF or photo) to fill in the payment automatically
- Scheduled and recurring supplier payments
- Multi-user approvals (two people for large payments)
- Moving from SQLite to Postgres for production

## Built with

PayPal Payouts, PayPal Invoicing, PayPal Orders, Groq, gpt-oss-20b, Python, FastAPI, SQLite, Next.js, React,
Tailwind CSS, AG Grid, Lucide, Render

## AI tools used and how

- **Groq / gpt-oss-20b**: the in-product agent (tool calling for lookups, structured proposals)
- **Claude**: coding assistant for parts of the backend, UI and tests
- **DeepSeek**: coding assistant for early scaffolding
