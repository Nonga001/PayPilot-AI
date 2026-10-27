"""Deterministic policy engine. The AI proposes; this decides.

`evaluate` is a pure function: everything it needs from the database (today's spend,
earlier payments) arrives in a PolicyContext, so it is easy to test and to re-run at
execution time.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# PayPal-supported currencies only (KES is not a PayPal transaction currency).
# (per-transaction limit, per-day limit) in that currency.
LIMITS: dict[str, tuple[Decimal, Decimal]] = {
    "USD": (Decimal("500"), Decimal("2000")),
    "EUR": (Decimal("460"), Decimal("1850")),
    "GBP": (Decimal("400"), Decimal("1600")),
    "CAD": (Decimal("680"), Decimal("2700")),
    "AUD": (Decimal("760"), Decimal("3000")),
}
MAX_RECIPIENT_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 127  # PayPal purchase_unit.description limit
DUPLICATE_WINDOW_DAYS = 7

INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts|messages)",
    r"\bdisregard\s+(all\s+)?(previous|prior|above|the\s+rules)",
    r"\bforget\s+(all\s+)?(previous|prior|your)\s+(instructions|rules)",
    r"\boverride\s+(the\s+)?(rules|limit|limits|security|policy)",
    r"\bbypass\s+(the\s+)?(rules|limit|limits|security|policy|approval|checks?)",
    r"\b(skip|without)\s+(the\s+)?(approval|confirmation|review|checks?)",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\s+(an?\s+)?(admin|administrator|system|developer)",
    r"\bnew\s+instructions\b",
    r"\b(system|admin|developer)\s*:",
    r"\bsudo\b",
    r"\b(send|transfer|pay)\s+(all|everything|the\s+entire|my\s+whole)",
    r"\bno\s+(need\s+(to|for)\s+)?(approval|confirmation)",
    r"\bjailbreak\b|\bDAN\b",
]
_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"
_EXPLICIT_AMOUNT = re.compile(
    rf"[$€£]\s?({_NUM})|({_NUM})\s?(?:USD|EUR|GBP|CAD|AUD|KES|dollars?|euros?|pounds?|bucks)\b|\b(?:USD|EUR|GBP|CAD|AUD|KES)\s?({_NUM})",
    re.IGNORECASE,
)
# Bare numbers that are not glued to letters, '#', '-' or '/' (so "INV-1042", "#12", "10/27" don't count).
_BARE_NUMBER = re.compile(rf"(?<![\w#/\-.])({_NUM})(?![\w/\-]|\.\d)")
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


@dataclass
class PolicyContext:
    spent_today: Decimal = Decimal("0")            # completed spend today in the proposal's currency
    paid_invoice: dict[str, Any] | None = None     # earlier completed payment with the same invoice number
    similar_recent: dict[str, Any] | None = None   # same recipient + amount within DUPLICATE_WINDOW_DAYS
    pending_invoice: dict[str, Any] | None = None  # another proposal for this invoice awaiting PayPal approval
    payee: dict[str, Any] | None = None            # saved payee this payment resolves to
    open_invoice: dict[str, Any] | None = None     # unpaid invoice already sent to this client for this amount
    extra: dict[str, Any] = field(default_factory=dict)


def _dec(s: str) -> Decimal | None:
    try:
        d = Decimal(s.replace(",", ""))
        return d if d.is_finite() else None
    except (InvalidOperation, AttributeError):
        return None


def mentioned_amounts(message: str) -> tuple[set[Decimal], set[Decimal]]:
    explicit = {d for m in _EXPLICIT_AMOUNT.finditer(message) if (d := _dec(next(g for g in m.groups() if g)))}
    bare = {d for m in _BARE_NUMBER.finditer(message) if (d := _dec(m.group(1)))}
    return explicit, bare


def scan_injection(message: str) -> str | None:
    for rx in _INJECTION:
        m = rx.search(message)
        if m:
            return m.group(0)
    return None


def evaluate(parsed: dict[str, Any], message: str, ctx: PolicyContext | None = None) -> dict[str, Any]:
    ctx = ctx or PolicyContext()
    checks: list[dict[str, Any]] = []

    def check(id_: str, label: str, passed: bool, severity: str, detail: str) -> None:
        checks.append({"id": id_, "label": label, "passed": passed, "severity": severity, "detail": detail})

    currency = str(parsed.get("currency") or "").upper()
    limits = LIMITS.get(currency)

    # 1. Prompt injection on the ORIGINAL text
    hit = scan_injection(message)
    check("injection_scan", "Prompt-injection scan", hit is None, "block",
          f'Suspicious instruction found: "{hit}"' if hit else "No manipulation attempts found")

    # 2. Amount format
    raw_amount = str(parsed.get("amount") or "")
    amount = _dec(raw_amount)
    if amount is None:
        check("amount_valid", "Amount is valid", False, "block", "No valid amount was found")
    elif amount <= 0:
        check("amount_valid", "Amount is valid", False, "block", "Amount must be greater than zero")
    elif amount != amount.quantize(Decimal("0.01")):
        check("amount_valid", "Amount is valid", False, "block", "Amount has more than 2 decimal places")
    else:
        check("amount_valid", "Amount is valid", True, "block", f"{amount:.2f} {currency or ''}".strip())

    # 3. Grounding: the AI's amount must be one the user actually wrote
    if amount is not None and amount > 0:
        explicit, bare = mentioned_amounts(message)
        pool = explicit or bare
        if not pool:
            check("amount_grounded", "Amount matches your message", False, "review",
                  "The amount wasn't written as a number. Please confirm it")
        elif amount not in pool:
            check("amount_grounded", "Amount matches your message", False, "block",
                  f"AI proposed {amount:.2f}, but your message says {', '.join(f'{a:.2f}' for a in sorted(pool))}")
        elif len(explicit) > 1:
            check("amount_grounded", "Amount matches your message", False, "review",
                  f"Your message mentions several amounts ({', '.join(f'{a:.2f}' for a in sorted(explicit))})")
        else:
            check("amount_grounded", "Amount matches your message", True, "block",
                  "The amount appears in your message, word for word")

    # 4. Currency
    if limits:
        check("currency_supported", "Currency supported", True, "block", f"{currency} is supported by PayPal and policy")
    else:
        note = " (PayPal can't process KES; use USD)" if currency == "KES" else ""
        check("currency_supported", "Currency supported", False, "block",
              f"'{currency or 'none'}' is not allowed{note}. Allowed: {', '.join(LIMITS)}")

    # 5/6. Limits
    if limits and amount is not None and amount > 0:
        per_tx, per_day = limits
        check("per_tx_limit", "Per-payment limit", amount <= per_tx, "block",
              f"{amount:.2f} of {per_tx:.2f} {currency} allowed per payment" if amount <= per_tx
              else f"{amount:.2f} {currency} exceeds the {per_tx:.2f} {currency} per-payment limit")
        projected = ctx.spent_today + amount
        remaining = per_day - projected
        check("daily_limit", "Daily limit", projected <= per_day, "block",
              f"{remaining:.2f} {currency} of today's {per_day:.2f} left after this payment" if projected <= per_day
              else f"Would exceed today's {per_day:.2f} {currency} limit (already spent {ctx.spent_today:.2f})")

    # 7. Recipient
    recipient = str(parsed.get("recipient") or "").strip()
    email = str(parsed.get("recipient_email") or "").strip()
    if not recipient and not email:
        check("recipient_valid", "Recipient identified", False, "block", "No recipient found")
    elif len(recipient) > MAX_RECIPIENT_LENGTH:
        check("recipient_valid", "Recipient identified", False, "block", f"Recipient exceeds {MAX_RECIPIENT_LENGTH} characters")
    elif email and not _EMAIL.match(email):
        check("recipient_valid", "Recipient identified", False, "block", f"'{email}' is not a valid email address")
    else:
        check("recipient_valid", "Recipient identified", True, "block",
              f"{recipient or email}" + (f" <{email}>" if email and recipient else ""))

    # 7b. Saved payee: first payments to someone new get a human look
    if recipient or email:
        if ctx.payee:
            check("payee_known", "Saved payee", True, "review",
                  f"{ctx.payee['name']} is in your payees" + (f" ({ctx.payee.get('country')})" if ctx.payee.get("country") else ""))
        else:
            check("payee_known", "Saved payee", False, "review",
                  f"{recipient or email} isn't in your saved payees. First payments to new people need a check")

    # 7c. Where the PayPal email came from: your message or your payee list, never the AI's imagination
    if email:
        in_message = email.lower() in message.lower()
        from_payee = bool(ctx.payee and (ctx.payee.get("paypal_email") or "").lower() == email.lower())
        check("recipient_grounded", "Recipient email verified", in_message or from_payee, "block",
              "Taken from your message" if in_message else "Taken from your saved payee" if from_payee
              else f"{email} isn't in your message or your saved payees")

    # 8. Description
    description = str(parsed.get("description") or "")
    check("description_valid", "Purpose recorded", len(description) <= MAX_DESCRIPTION_LENGTH, "block",
          (description or "No purpose given") if len(description) <= MAX_DESCRIPTION_LENGTH
          else f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters")

    # 9. Duplicate invoice
    invoice = str(parsed.get("invoice_number") or "").strip()
    if invoice:
        if ctx.paid_invoice:
            p = ctx.paid_invoice
            check("duplicate_invoice", "Invoice not already paid", False, "block",
                  f"Invoice {invoice} was already paid ({p.get('amount')} {p.get('currency')} on "
                  f"{str(p.get('created_at', ''))[:10]}, receipt {p.get('receipt_number')})")
        elif ctx.pending_invoice:
            check("duplicate_invoice", "Invoice not already paid", False, "review",
                  f"Another payment for invoice {invoice} is waiting for PayPal approval")
        else:
            check("duplicate_invoice", "Invoice not already paid", True, "block", f"No earlier payment for {invoice}")

    # 10. Similar recent payment
    if ctx.similar_recent:
        s = ctx.similar_recent
        check("duplicate_pattern", "No repeat payment", False, "review",
              f"You paid {s.get('recipient')} {s.get('amount')} {s.get('currency')} on {str(s.get('created_at', ''))[:10]}. Is this a repeat?")
    elif amount is not None and recipient:
        check("duplicate_pattern", "No repeat payment", True, "review",
              f"No matching payment in the last {DUPLICATE_WINDOW_DAYS} days")

    # 11. AI confidence
    confidence = str(parsed.get("confidence") or "low").lower()
    check("ai_confidence", "AI confidence", confidence in {"high", "medium"}, "review",
          f"AI confidence: {confidence}" if confidence in {"high", "medium"}
          else "The AI isn't sure it understood this request")

    return _decide(checks)


INVOICE_MAX = {cur: per_day * 5 for cur, (_, per_day) in LIMITS.items()}


def evaluate_invoice(parsed: dict[str, Any], message: str, ctx: PolicyContext | None = None) -> dict[str, Any]:
    """Rules for requesting money (sending a PayPal invoice). No spend limits: money comes in."""
    ctx = ctx or PolicyContext()
    checks: list[dict[str, Any]] = []

    def check(id_: str, label: str, passed: bool, severity: str, detail: str) -> None:
        checks.append({"id": id_, "label": label, "passed": passed, "severity": severity, "detail": detail})

    hit = scan_injection(message)
    check("injection_scan", "Prompt-injection scan", hit is None, "block",
          f'Suspicious instruction found: "{hit}"' if hit else "No manipulation attempts found")

    currency = str(parsed.get("currency") or "").upper()
    amount = _dec(str(parsed.get("amount") or ""))
    ok_amount = amount is not None and amount > 0 and amount == amount.quantize(Decimal("0.01"))
    check("amount_valid", "Amount is valid", ok_amount, "block",
          f"{amount:.2f} {currency}".strip() if ok_amount else "No valid amount was found")
    if ok_amount:
        explicit, bare = mentioned_amounts(message)
        pool = explicit or bare
        grounded = amount in pool if pool else False
        check("amount_grounded", "Amount matches your message", grounded, "block" if pool else "review",
              "The amount appears in your message, word for word" if grounded
              else "The amount wasn't written as a number. Please confirm it" if not pool
              else f"AI proposed {amount:.2f}, but your message says {', '.join(f'{a:.2f}' for a in sorted(pool))}")

    if currency in LIMITS:
        check("currency_supported", "Currency supported", True, "block", f"{currency} is supported by PayPal")
        if ok_amount:
            cap = INVOICE_MAX[currency]
            check("invoice_cap", "Invoice size", amount <= cap, "block",
                  f"Within the {cap:.2f} {currency} invoice cap" if amount <= cap
                  else f"{amount:.2f} {currency} is over the {cap:.2f} {currency} invoice cap")
    else:
        check("currency_supported", "Currency supported", False, "block",
              f"'{currency or 'none'}' is not allowed. Allowed: {', '.join(LIMITS)}")

    email = str(parsed.get("recipient_email") or "").strip()
    if not email:
        check("recipient_valid", "Client email", False, "block", "PayPal needs the client's email to send an invoice")
    elif not _EMAIL.match(email):
        check("recipient_valid", "Client email", False, "block", f"'{email}' is not a valid email address")
    else:
        in_message = email.lower() in message.lower()
        from_payee = bool(ctx.payee and (ctx.payee.get("paypal_email") or "").lower() == email.lower())
        check("recipient_valid", "Client email", in_message or from_payee, "block",
              f"{email} ({'from your message' if in_message else 'from your saved contacts'})" if in_message or from_payee
              else f"{email} isn't in your message or your saved contacts")

    if ctx.open_invoice:
        o = ctx.open_invoice
        check("duplicate_invoice", "No open invoice already", False, "review",
              f"Invoice {o.get('invoice_number') or ''} for {o.get('amount')} {o.get('currency')} to this client is still {str(o.get('status', '')).lower()}")
    elif email:
        check("duplicate_invoice", "No open invoice already", True, "review", "No unpaid invoice to this client for this amount")

    confidence = str(parsed.get("confidence") or "low").lower()
    check("ai_confidence", "AI confidence", confidence in {"high", "medium"}, "review",
          f"AI confidence: {confidence}" if confidence in {"high", "medium"} else "The AI isn't sure it understood this request")

    return _decide(checks)


def _decide(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed_block = [c for c in checks if not c["passed"] and c["severity"] == "block"]
    failed_review = [c for c in checks if not c["passed"] and c["severity"] == "review"]
    if failed_block:
        decision, risk_level = "blocked", "high"
    elif failed_review:
        decision, risk_level = "review", "medium"
    else:
        decision, risk_level = "approved", "low"
    return {
        "decision": decision,
        "risk_level": risk_level,
        "risk_score": min(100, 6 + 22 * len(failed_review) + 45 * len(failed_block)),
        "reasons": [c["detail"] for c in failed_block + failed_review],
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
    }


def evaluate_for(kind: str, parsed: dict[str, Any], message: str, ctx: PolicyContext | None = None) -> dict[str, Any]:
    return evaluate_invoice(parsed, message, ctx) if kind == "invoice" else evaluate(parsed, message, ctx)


def limits_view() -> dict[str, Any]:
    return {cur: {"per_transaction": f"{a:.2f}", "per_day": f"{b:.2f}"} for cur, (a, b) in LIMITS.items()}
