"""Checks your PayPal Sandbox app and Groq key support what PayPilot uses.

Run from apps/api with your venv active:
    python scripts/sandbox_check.py
    python scripts/sandbox_check.py --payout someone@example.com   # also sends a real $1.00 SANDBOX payout

Prints no secrets.
"""
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from app.core import config  # noqa: E402

OK, BAD, WARN = "\033[32mOK\033[0m", "\033[31mFAIL\033[0m", "\033[33mWARN\033[0m"


def line(status: str, msg: str) -> None:
    print(f"  [{status}] {msg}")


def paypal_checks(payout_to: str | None) -> None:
    print("\nPayPal Sandbox")
    if not config.PAYPAL_CLIENT_ID or not config.PAYPAL_CLIENT_SECRET:
        line(BAD, "PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET missing in apps/api/.env")
        return
    base = config.PAYPAL_API_BASE
    r = requests.post(f"{base}/v1/oauth2/token", auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
                      data={"grant_type": "client_credentials"}, timeout=20)
    if not r.ok:
        line(BAD, f"OAuth token failed: HTTP {r.status_code} {r.text[:200]}")
        return
    body = r.json()
    scopes = body.get("scope", "")
    line(OK, f"OAuth token ({base})")
    for name, scope in [("Checkout (orders)", "payments/payment"), ("Payouts", "payments/payouts"),
                        ("Invoicing", "invoicing")]:
        line(OK if scope in scopes else WARN, f"{name} scope {'present' if scope in scopes else 'NOT in token'}"
             + ("" if scope in scopes else f": enable {name.split(' ')[0]} under your app's Features at developer.paypal.com"))
    h = {"Authorization": f"Bearer {body['access_token']}", "Content-Type": "application/json"}

    r = requests.post(f"{base}/v2/invoicing/search-invoices?page_size=5", headers=h, json={}, timeout=20)
    line(OK if r.ok else BAD, f"Invoicing search: HTTP {r.status_code}"
         + (f", {r.json().get('total_items', 0)} invoices" if r.ok else f" {r.text[:200]}"))

    r = requests.post(f"{base}/v2/invoicing/generate-next-invoice-number", headers=h, timeout=20)
    line(OK if r.ok else BAD, f"Invoicing next number: HTTP {r.status_code} {r.json().get('invoice_number', '') if r.ok else r.text[:200]}")

    if payout_to:
        batch = f"check-{uuid.uuid4().hex[:12]}"
        r = requests.post(f"{base}/v1/payments/payouts", headers={**h, "PayPal-Request-Id": batch}, json={
            "sender_batch_header": {"sender_batch_id": batch, "email_subject": "PayPilot sandbox check"},
            "items": [{"recipient_type": "EMAIL", "receiver": payout_to, "note": "PayPilot sandbox check",
                       "sender_item_id": batch, "amount": {"value": "1.00", "currency": "USD"}}],
        }, timeout=30)
        if not r.ok:
            line(BAD, f"Payout create: HTTP {r.status_code} {r.text[:300]}")
        else:
            bid = r.json()["batch_header"]["payout_batch_id"]
            line(OK, f"Payout created: batch {bid}")
            time.sleep(4)
            g = requests.get(f"{base}/v1/payments/payouts/{bid}", headers=h, timeout=20).json()
            items = g.get("items") or [{}]
            line(OK, f"Payout status: batch {g.get('batch_header', {}).get('batch_status')}, "
                     f"item {items[0].get('transaction_status')}")
    else:
        line(WARN, "Payout not tested (add --payout <email> to send a $1.00 sandbox payout)")


def groq_checks() -> None:
    print("\nGroq")
    if not config.GROQ_API_KEY:
        line(BAD, "GROQ_API_KEY missing")
        return
    try:
        from groq import Groq
    except ImportError:
        line(BAD, "groq package not installed in this Python. Activate the venv (source .venv/Scripts/activate) "
                  "or run: pip install -r requirements.txt")
        return
    client = Groq(api_key=config.GROQ_API_KEY)
    try:
        ids = {m.id for m in client.models.list().data}
        line(OK if config.GROQ_MODEL in ids else BAD, f"Model {config.GROQ_MODEL} {'available' if config.GROQ_MODEL in ids else 'NOT available'}")
    except Exception as e:
        line(BAD, f"List models: {e}")
        return
    t = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[{"role": "user", "content": "Look up the payee named Acme Supplies."}],
            tools=[{"type": "function", "function": {
                "name": "find_payee", "description": "Find a saved payee by name",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}],
            tool_choice="required",
        )
        calls = resp.choices[0].message.tool_calls or []
        ms = int((time.perf_counter() - t) * 1000)
        line(OK if calls else BAD, f"Tool calling: {len(calls)} call(s) in {ms} ms "
             + (json.dumps(calls[0].function.arguments) if calls else ""))
    except Exception as e:
        line(BAD, f"Tool calling: {e}")


if __name__ == "__main__":
    to = sys.argv[sys.argv.index("--payout") + 1] if "--payout" in sys.argv else None
    paypal_checks(to)
    groq_checks()
    print()
