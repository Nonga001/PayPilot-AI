"""Tables for the Insights dashboard (AG Studio): every request PayPilot handled, the checks that
stopped or flagged them, the payments and invoices that went out.

A fresh demo database has almost nothing in it, so the dashboard can also add a clearly labelled
sample history. Every row carries `source` ("Live" or "Sample") and sample rows are generated, never
written to the ledger or the audit trail.
"""
import json
import random
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


# ------------------------------------------------------------------ sample history
SUPPLIERS = [  # name, currency, typical amount, weight
    ("Acme Supplies", "USD", 120, 9), ("Kamau Logistics", "USD", 85, 8), ("Bright Print Co", "GBP", 60, 5),
    ("Nairobi Fresh Produce", "USD", 45, 7), ("CloudNest Hosting", "USD", 29, 4), ("Swift Courier", "USD", 18, 6),
    ("Okafor Electrical", "USD", 210, 3), ("Lumen Cleaning", "EUR", 75, 3),
]
CLIENTS = [("Maria Lopez Design", "EUR", 250), ("Harbor Cafe", "USD", 180), ("Zuri Events", "USD", 420)]
BLOCKS = [  # check label, check id, weight
    ("Prompt-injection scan", "injection_scan", 5), ("Amount matches your message", "amount_grounded", 4),
    ("Per-payment limit", "per_tx_limit", 4), ("Invoice not already paid", "invoice_not_paid", 6),
    ("Recipient email verified", "recipient_grounded", 2),
]
REVIEWS = [
    ("Saved payee", "payee_known", 6), ("AI confidence", "confidence", 4),
    ("Payment email matches payee", "payee_email_changed", 3), ("No repeat payment", "no_repeat", 3),
]


def _pick(rng: random.Random, items):
    return rng.choices(items, weights=[i[-1] for i in items])[0]


def sample(days: int = 60, today: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """A believable small-business history. Seeded by date, so it is stable for a day."""
    today = today or datetime.now(timezone.utc).date()
    rng = random.Random(today.toordinal())
    requests, checks, payments, invoices = [], [], [], []
    n = 0
    for back in range(days, 0, -1):
        day = today - timedelta(days=back)
        busy = 0.6 if day.weekday() >= 5 else 1.0
        for _ in range(rng.choices([1, 2, 3, 4, 5], [2, 4, 4, 2, 1])[0] if rng.random() < busy else 0):
            n += 1
            rid = f"sample_{n:04d}"
            ts = datetime(day.year, day.month, day.day, rng.randint(7, 19), rng.randint(0, 59), tzinfo=timezone.utc)
            roll = rng.random()
            kind = "Answer" if roll < 0.08 else "Invoice" if roll < 0.2 else "Payment"
            base = {"id": rid, "date": day.isoformat(), "created_at": ts.isoformat(timespec="seconds"), "kind": kind,
                    "ai_source": "Groq" if rng.random() < 0.95 else "Backup parser",
                    "ai_latency_ms": max(250, int(rng.gauss(900, 250))), "source": "Sample"}
            if kind == "Answer":
                requests.append({**base, "rail": None, "decision": "Answered", "risk_level": None, "risk_score": None,
                                 "amount": None, "currency": None, "recipient": None, "outcome": "Answered", "checks_failed": 0})
                continue
            if kind == "Invoice":
                client, cur, typical = rng.choice(CLIENTS)
                amount = round(max(20, rng.gauss(typical, typical * 0.3)), 2)
                status = rng.choices(["Paid", "Sent", "Draft"], [6, 3, 1])[0]
                requests.append({**base, "rail": "Invoice", "decision": "Approved", "risk_level": "Low", "risk_score": rng.randint(0, 10),
                                 "amount": amount, "currency": cur, "recipient": client, "outcome": "Invoiced", "checks_failed": 0})
                invoices.append({"id": f"{rid}_inv", "request_id": rid, "date": day.isoformat(), "client": client,
                                 "status": status, "amount": amount, "currency": cur, "source": "Sample"})
                continue

            name, cur, typical, _ = _pick(rng, SUPPLIERS)
            amount = round(max(5, rng.gauss(typical, typical * 0.35)), 2)
            d = rng.random()
            failed: list[tuple[str, str, str]] = []
            if d < 0.14:
                label, cid, _ = _pick(rng, BLOCKS)
                if cid == "per_tx_limit":
                    amount = round(rng.uniform(520, 4900), 2)
                failed.append((label, cid, "Blocks"))
                decision, outcome, score = "Blocked", "Blocked", rng.randint(70, 100)
            elif d < 0.36:
                label, cid, _ = _pick(rng, REVIEWS)
                failed.append((label, cid, "Needs review"))
                decision, score = "Review", rng.randint(25, 60)
                outcome = rng.choices(["Paid", "Cancelled"], [6, 4])[0]
            else:
                decision, score = "Approved", rng.randint(0, 20)
                outcome = rng.choices(["Paid", "Cancelled"], [93, 7])[0]
            rail = "Payout" if rng.random() < 0.85 else "Checkout"
            requests.append({**base, "rail": rail, "decision": decision, "risk_level": "High" if score >= 70 else "Medium" if score >= 25 else "Low",
                             "risk_score": score, "amount": amount, "currency": cur, "recipient": name, "outcome": outcome,
                             "checks_failed": len(failed)})
            for i, (label, cid, sev) in enumerate(failed):
                checks.append({"id": f"{rid}-{i}", "request_id": rid, "check": label, "check_id": cid, "severity": sev,
                               "date": day.isoformat(), "source": "Sample"})
            if outcome == "Paid":
                fee = 0.25 if rail == "Payout" else round(amount * 0.0349 + 0.49, 2)
                payments.append({"id": f"{rid}_tx", "request_id": rid, "date": day.isoformat(), "recipient": name, "rail": rail,
                                 "status": "Success" if rail == "Payout" else "Completed", "amount": amount, "currency": cur,
                                 "fee": fee, "verified": True, "invoice_number": f"INV-{1000 + n}", "source": "Sample"})
    return {"requests": requests, "checks": checks, "payments": payments, "invoices": invoices}


def build(include_sample: bool) -> dict[str, Any]:
    data = live()
    counts = {k: len(v) for k, v in data.items()}
    if include_sample:
        s = sample()
        for k in data:
            data[k] = s[k] + data[k]
    return {"as_of": db.now_iso(), "live_counts": counts, "includes_sample": include_sample, "tables": data}
