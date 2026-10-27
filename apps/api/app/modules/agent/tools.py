"""Tools the PayPilot agent can call.

Lookup tools are read-only. The three terminal tools (propose_payment, propose_invoice,
answer) only describe an intent: nothing executes until a person approves it and the
server-side policy passes it again.
"""
import time
from decimal import Decimal
from typing import Any, Callable

from app.modules.security.policy import LIMITS
from app.modules.transactions import store


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


_S = {"type": "string"}
_CONF = {"type": "string", "enum": ["high", "medium", "low"]}

TOOL_SCHEMAS = [
    _fn("find_payee", "Look up a saved payee or client by name or email. Returns their PayPal email, country and currency.",
        {"query": {**_S, "description": "Name or email as the user wrote it"}}, ["query"]),
    _fn("check_payment_history", "Recent payments to a recipient and whether an invoice number was already paid.",
        {"recipient": {**_S, "description": "Payee name or email, or empty"},
         "invoice_number": {**_S, "description": "Invoice/reference number, or empty"}}, []),
    _fn("get_budget", "Today's spend, daily limit and per-payment limit for a currency.",
        {"currency": {**_S, "description": "ISO code, e.g. USD"}}, ["currency"]),
    _fn("search_paypal_invoices", "Search invoices this business sent through PayPal, with live status (paid, unpaid...).",
        {"client_email": {**_S, "description": "Client email, or empty"},
         "invoice_number": {**_S, "description": "Invoice number, or empty"}}, []),
    _fn("propose_payment", "Final step for paying someone. Proposes ONE payment for human approval.",
        {"amount": {**_S, "description": "Decimal string exactly as written, e.g. 45.00"},
         "currency": {**_S, "description": "ISO code. $ means USD"},
         "recipient": {**_S, "description": "Who is paid"},
         "recipient_email": {**_S, "description": "From the message or find_payee only, else empty"},
         "payee_id": {**_S, "description": "id from find_payee, else empty"},
         "description": {**_S, "description": "Short purpose"},
         "invoice_number": {**_S, "description": "Invoice/reference number, else empty"},
         "confidence": _CONF},
        ["amount", "currency", "recipient", "confidence"]),
    _fn("propose_invoice", "Final step for requesting money from a client with a PayPal invoice. Proposes ONE invoice for approval.",
        {"amount": _S, "currency": _S,
         "client_name": _S,
         "client_email": {**_S, "description": "From the message or find_payee only, else empty"},
         "description": {**_S, "description": "What the invoice is for"},
         "confidence": _CONF},
        ["amount", "currency", "client_name", "confidence"]),
    _fn("answer", "Final step for questions or when no payment/invoice should be made. Reply in 1-3 short sentences based only on tool results.",
        {"text": _S}, ["text"]),
]

TERMINAL = {"propose_payment", "propose_invoice", "answer"}

LABELS = {
    "find_payee": "Looked up payee",
    "check_payment_history": "Checked payment history",
    "get_budget": "Checked today's budget",
    "search_paypal_invoices": "Searched PayPal invoices",
    "propose_payment": "Drafted the payment",
    "propose_invoice": "Drafted the invoice",
    "answer": "Answered",
}


def _s(args: dict[str, Any], key: str) -> str:
    v = args.get(key)
    return "" if v is None else str(v).strip()


# ----------------------------------------------------------------- executors
def find_payee(args: dict[str, Any]) -> tuple[Any, str]:
    q = _s(args, "query")
    found = store.find_payees(q)
    slim = [{k: p.get(k) for k in ("id", "name", "paypal_email", "country", "default_currency", "notes")} for p in found]
    if not slim:
        return {"payees": []}, f"No saved payee matches “{q}”"
    p = slim[0]
    extra = f" (+{len(slim) - 1} more)" if len(slim) > 1 else ""
    return {"payees": slim}, f"Found {p['name']}, {p['paypal_email'] or 'no PayPal email'}{extra}"


def check_payment_history(args: dict[str, Any]) -> tuple[Any, str]:
    recipient, invoice = _s(args, "recipient"), _s(args, "invoice_number")
    payee = store.resolve_payee({"recipient": recipient}) if recipient else None
    names = {recipient}
    if payee:
        names |= {payee["name"], payee.get("paypal_email") or ""}
    rows: dict[str, dict[str, Any]] = {}
    for n in filter(None, names):
        for t in store.recipient_history(recipient=n, limit=5):
            rows[t["id"]] = t
    if invoice:
        for t in store.recipient_history(invoice_number=invoice, limit=5):
            rows[t["id"]] = t
    hist = sorted(rows.values(), key=lambda t: t["created_at"], reverse=True)[:5]
    slim = [{k: t.get(k) for k in ("receipt_number", "amount", "currency", "recipient", "invoice_number", "status", "created_at")}
            for t in hist]
    paid = [t for t in slim if invoice and (t.get("invoice_number") or "").upper() == invoice.upper()
            and t.get("status") in store.COUNTED_STATUSES]
    result = {"payments": slim, "invoice_already_paid": bool(paid)}
    if paid:
        return result, f"Invoice {invoice} was already paid ({paid[0]['receipt_number']})"
    if slim:
        last = slim[0]
        return result, f"{len(slim)} earlier payment(s); last {last['amount']} {last['currency']} on {last['created_at'][:10]}"
    return result, "No earlier payments" + (f", invoice {invoice} unpaid" if invoice else "")


def get_budget(args: dict[str, Any]) -> tuple[Any, str]:
    cur = _s(args, "currency").upper() or "USD"
    limits = LIMITS.get(cur)
    if not limits:
        return {"currency": cur, "supported": False, "supported_currencies": list(LIMITS)}, f"{cur} isn't supported by PayPal or policy"
    spent = store.spent_today(cur)
    left = limits[1] - spent
    return ({"currency": cur, "supported": True, "spent_today": f"{spent:.2f}", "daily_limit": f"{limits[1]:.2f}",
             "remaining_today": f"{left:.2f}", "per_payment_limit": f"{limits[0]:.2f}"},
            f"{left:.2f} {cur} left today, up to {limits[0]:.2f} per payment")


def search_paypal_invoices(args: dict[str, Any]) -> tuple[Any, str]:
    from app.modules.payments.paypal_client import PayPalError, paypal

    email, number = _s(args, "client_email").lower(), _s(args, "invoice_number")
    if not email and not number:
        local = store.list_invoices(10)
    else:
        local = [i for i in store.list_invoices(200)
                 if (email and i["recipient_email"].lower() == email) or (number and (i["invoice_number"] or "").upper() == number.upper())]
    live: list[dict[str, Any]] = []
    source = "paypal"
    try:
        res = paypal().search_invoices(recipient_email=email or None, invoice_number=number or None, page_size=10)
        for it in res.get("items", []):
            d = it.get("detail", {})
            amt = it.get("amount", {})
            live.append({"paypal_invoice_id": it.get("id"), "invoice_number": d.get("invoice_number"),
                         "status": it.get("status"), "amount": amt.get("value"), "currency": amt.get("currency_code"),
                         "date": d.get("invoice_date")})
        _sync_invoice_statuses(live)
    except (PayPalError, Exception) as e:  # PayPal unreachable or not configured: fall back to local records
        source = f"local only ({type(e).__name__})"
        live = [{k: i.get(k) for k in ("paypal_invoice_id", "invoice_number", "status", "amount", "currency", "created_at")} for i in local]
    result = {"source": source, "invoices": live[:10]}
    if not live:
        return result, "No matching PayPal invoices"
    unpaid = [i for i in live if i.get("status") in ("SENT", "UNPAID", "PARTIALLY_PAID", "SCHEDULED")]
    return result, f"{len(live)} invoice(s) on PayPal, {len(unpaid)} unpaid"


def _sync_invoice_statuses(live: list[dict[str, Any]]) -> None:
    from app.core import db
    ids = {i["paypal_invoice_id"]: i["status"] for i in live if i.get("paypal_invoice_id") and i.get("status")}
    if not ids:
        return
    with db.write() as c:
        for pid, status in ids.items():
            c.execute("UPDATE invoices SET status=?, updated_at=? WHERE paypal_invoice_id=? AND status<>?",
                      (status, db.now_iso(), pid, status))


EXECUTORS: dict[str, Callable[[dict[str, Any]], tuple[Any, str]]] = {
    "find_payee": find_payee,
    "check_payment_history": check_payment_history,
    "get_budget": get_budget,
    "search_paypal_invoices": search_paypal_invoices,
}


def run(name: str, args: dict[str, Any], auto: bool = False) -> tuple[Any, dict[str, Any]]:
    """Execute a lookup tool and return (result, trace step)."""
    t0 = time.perf_counter()
    try:
        result, summary = EXECUTORS[name](args)
        ok = True
    except Exception as e:  # a failing lookup must never crash the agent
        result, summary, ok = {"error": f"{type(e).__name__}: {str(e)[:200]}"}, f"Lookup failed: {type(e).__name__}", False
    step = {"tool": name, "label": LABELS.get(name, name), "args": {k: v for k, v in args.items() if v not in ("", None)},
            "summary": summary, "ms": int((time.perf_counter() - t0) * 1000), "ok": ok, "auto": auto}
    return result, step


def money_ok(amount: str) -> bool:
    try:
        return Decimal(amount) > 0
    except Exception:
        return False
