"""Tables for the Insights dashboard (AG Studio): every request PayPilot handled, the checks that
stopped or flagged them, the payments and invoices that went out.

A fresh demo database has almost nothing in it, so the dashboard can also add one labelled example
of each outcome. Every row carries `source` ("Live" or "Sample") and sample rows are generated, never
written to the ledger or the audit trail.
"""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core import db

OUTCOME = {
    "completed": "Paid", "blocked": "Blocked", "proposed": "Awaiting approval", "awaiting_payer": "Awaiting approval",
    "executing": "Awaiting approval", "cancelled": "Cancelled", "failed": "Failed", "answered": "Answered",
}


def _num(s: Any) -> float | None:
    try:
        return round(float(s), 2) if s not in (None, "") else None
    except (TypeError, ValueError):
        return None


def live() -> dict[str, list[dict[str, Any]]]:
    c = db.conn()
    requests, checks = [], []
    for p in c.execute("SELECT * FROM proposals ORDER BY created_at"):
        policy = json.loads(p["policy_json"] or "null") or {}
        failed = [ch for ch in policy.get("checks", []) if not ch.get("passed")]
        kind = p["kind"] or "payment"
        outcome = OUTCOME.get(p["status"], p["status"])
        if kind == "invoice" and p["status"] == "completed":
            outcome = "Invoiced"
        requests.append({
            "id": p["id"], "date": p["created_at"][:10], "created_at": p["created_at"], "kind": kind.title(),
            "rail": (p["rail"] or "").title() or None, "decision": (p["decision"] or "answered").title(),
            "risk_level": (p["risk_level"] or "").title() or None, "risk_score": p["risk_score"],
            "amount": _num(p["amount"]), "currency": p["currency"] or None, "recipient": p["recipient"] or None,
            "outcome": outcome, "ai_source": "Groq" if p["ai_source"] == "groq" else "Backup parser",
            "ai_latency_ms": p["ai_latency_ms"], "checks_failed": len(failed), "source": "Live",
        })
        for i, ch in enumerate(failed):
            checks.append({"id": f"{p['id']}-{i}", "request_id": p["id"], "check": ch.get("label"),
                           "check_id": ch.get("id"), "severity": "Blocks" if ch.get("severity") == "block" else "Needs review",
                           "date": p["created_at"][:10], "source": "Live"})
    payments = [{
        "id": t["id"], "request_id": t["proposal_id"], "date": t["day"], "recipient": t["recipient"],
        "rail": (t["rail"] or "checkout").title(), "status": t["status"].title(), "amount": _num(t["amount"]),
        "currency": t["currency"], "fee": _num(t["paypal_fee"]), "verified": bool(t["amount_verified"]),
        "invoice_number": t["invoice_number"], "source": "Live",
    } for t in c.execute("SELECT * FROM transactions ORDER BY created_at")]
    invoices = [{
        "id": i["id"], "request_id": i["proposal_id"], "date": i["created_at"][:10], "client": i["recipient"] or i["recipient_email"],
        "status": i["status"].replace("_", " ").title(), "amount": _num(i["amount"]), "currency": i["currency"], "source": "Live",
    } for i in c.execute("SELECT * FROM invoices ORDER BY created_at")]
    return {"requests": requests, "checks": checks, "payments": payments, "invoices": invoices}


# ------------------------------------------------------------------ sample examples
# One example per case, so an empty demo database still shows every kind of outcome without noise.
# (days ago, kind, payee, amount, currency, rail, decision, outcome, failed check or None, risk score)
EXAMPLES = [
    (6, "Payment", "Acme Supplies", 45.00, "USD", "Payout", "Approved", "Paid", None, 5),
    (5, "Payment", "John", 10.00, "USD", "Checkout", "Review", "Paid", ("Saved payee", "payee_known", "Needs review"), 30),
    (5, "Payment", "Acme Supplies", 128.50, "USD", "Payout", "Review", "Cancelled",
     ("Payment email matches payee", "payee_email_changed", "Needs review"), 45),
    (4, "Payment", "John", 5000.00, "USD", "Payout", "Blocked", "Blocked",
     ("Prompt-injection scan", "injection_scan", "Blocks"), 95),
    (3, "Payment", "Acme Supplies", 45.00, "USD", "Payout", "Blocked", "Blocked",
     ("Invoice not already paid", "invoice_not_paid", "Blocks"), 80),
    (3, "Payment", "Okafor Electrical", 4800.00, "USD", "Payout", "Blocked", "Blocked",
     ("Per-payment limit", "per_tx_limit", "Blocks"), 75),
    (2, "Invoice", "Maria Lopez Design", 250.00, "EUR", "Invoice", "Approved", "Invoiced", None, 5),
    (1, "Answer", None, None, None, None, "Answered", "Answered", None, None),
]
INVOICE_NUMBERS = {0: "INV-1042", 1: None, 2: "INV-2089", 4: "INV-1042"}


def sample(today: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """A handful of labelled examples, one per outcome. Never written to the ledger or audit trail."""
    today = today or datetime.now(timezone.utc).date()
    requests, checks, payments, invoices = [], [], [], []
    for n, (ago, kind, payee, amount, cur, rail, decision, outcome, failed, score) in enumerate(EXAMPLES):
        day = today - timedelta(days=ago)
        rid = f"sample_{n + 1:02d}"
        requests.append({
            "id": rid, "date": day.isoformat(), "created_at": f"{day.isoformat()}T10:{n:02d}:00+00:00", "kind": kind,
            "rail": rail, "decision": decision, "outcome": outcome, "amount": amount, "currency": cur, "recipient": payee,
            "risk_score": score, "risk_level": None if score is None else "High" if score >= 70 else "Medium" if score >= 25 else "Low",
            "ai_source": "Groq", "ai_latency_ms": 700 + 60 * n, "checks_failed": 1 if failed else 0, "source": "Sample",
        })
        if failed:
            checks.append({"id": f"{rid}-0", "request_id": rid, "check": failed[0], "check_id": failed[1],
                           "severity": failed[2], "date": day.isoformat(), "source": "Sample"})
        if outcome == "Paid":
            payments.append({"id": f"{rid}_tx", "request_id": rid, "date": day.isoformat(), "recipient": payee, "rail": rail,
                             "status": "Success" if rail == "Payout" else "Completed", "amount": amount, "currency": cur,
                             "fee": 0.25 if rail == "Payout" else round(amount * 0.0349 + 0.49, 2), "verified": True,
                             "invoice_number": INVOICE_NUMBERS.get(n), "source": "Sample"})
        if kind == "Invoice":
            invoices.append({"id": f"{rid}_inv", "request_id": rid, "date": day.isoformat(), "client": payee,
                             "status": "Sent", "amount": amount, "currency": cur, "source": "Sample"})
    return {"requests": requests, "checks": checks, "payments": payments, "invoices": invoices}


def build(include_sample: bool) -> dict[str, Any]:
    data = live()
    counts = {k: len(v) for k, v in data.items()}
    if include_sample:
        s = sample()
        for k in data:
            data[k] = s[k] + data[k]
    return {"as_of": db.now_iso(), "live_counts": counts, "includes_sample": include_sample, "tables": data}
