# PayPilot AI

A secure AI payment agent for the PayPal + AI Hackathon. Type a payment the way you'd say it;
PayPilot reads it, checks it, explains it, waits for your approval, pays through PayPal, and
records a tamper-evident receipt.

**AI proposes. Rules decide. You approve. PayPal processes. Everything is recorded.**

## How a payment flows

1. **Understand**: `POST /agent/analyze` sends the message to Groq (strict JSON schema) to extract
   amount, currency, recipient, PayPal email, purpose and invoice number. If Groq is down, a
   rule-based parser takes over and the request is sent to review.
2. **Check**: a deterministic policy engine (`security/policy.py`) runs on the server:
   prompt-injection scan, amount grounding (the AI's amount must appear in your message),
   per-currency per-payment and daily limits, currency support, duplicate invoice detection,
   repeat-payment detection and AI confidence. Result: approved, review, or blocked.
3. **Explain**: a plain-language summary built from the checked fields.
4. **Approve**: you click approve (review items need an explicit acknowledgement). The server
   re-runs the policy, then creates the PayPal order from the stored proposal. The browser
   never sends an amount.
5. **Pay**: you confirm on PayPal; `POST /payments/capture-order` captures it.
6. **Record**: the server writes the transaction from PayPal's own capture response and issues a
   receipt. Every step is appended to a SHA-256 hash-chained audit log (`GET /audit/verify`).

## Run it

```bash
# API
cd apps/api
python -m venv .venv && source .venv/Scripts/activate   # Git Bash on Windows
pip install -r requirements.txt
cp ../../.env.example .env   # then fill in keys
uvicorn app.main:app --reload --port 8000

# Web (second terminal)
cd apps/web
npm install
npm run dev   # http://localhost:3000
```

Storage is SQLite (`apps/api/data/paypilot.db`, created automatically). No database server needed.

## Tests

```bash
cd apps/api && pip install pytest httpx && python -m pytest -q
```

## Structure

- `apps/api`: FastAPI backend (`agent`, `ai`, `security`, `payments`, `transactions`, `audit`)
- `apps/web`: Next.js 16 frontend
- `infra`: Docker Compose (Postgres, for a later move off SQLite)
