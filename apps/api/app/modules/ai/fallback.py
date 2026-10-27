"""Rule-based extractor used when the AI provider is unreachable.

Always reports confidence "low", so the policy engine routes its output to human review.
"""
import re
from typing import Any

_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
_CODES = r"USD|EUR|GBP|CAD|AUD|KES"

_AMOUNT = re.compile(
    rf"(?P<sym>[$€£])\s?(?P<a1>\d[\d,]*(?:\.\d{{1,2}})?)"
    rf"|(?P<a2>\d[\d,]*(?:\.\d{{1,2}})?)\s?(?P<code>{_CODES}|dollars?|euros?|pounds?)\b"
    rf"|\b(?P<code2>{_CODES})\s?(?P<a3>\d[\d,]*(?:\.\d{{1,2}})?)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_INVOICE = re.compile(r"\b(?:invoice|inv|bill|ref)\s*(?:no\.?|number|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{1,30})", re.IGNORECASE)
_RECIPIENT = re.compile(r"\bto\s+(?:my\s+)?([A-Za-z][\w&.' -]{0,60}?)(?=\s+(?:for|at|on|via|\(|<)|[,.;]|\s*$)", re.IGNORECASE)
_PAY_NAME = re.compile(r"\b(?i:pay)\s+(?i:my\s+)?(?i:(?:our\s+)?(?:supplier|vendor|contractor|landlord)\s+)?\s*([A-Z][\w&.' -]{0,60}?)\s+(?=[$€£]|\d|(?:USD|EUR|GBP)\b)")
_PURPOSE = re.compile(r"\bfor\s+(.{1,120}?)(?=[,.;]|\s+and\s|$)", re.IGNORECASE)

_WORD_CODES = {"dollar": "USD", "dollars": "USD", "euro": "EUR", "euros": "EUR", "pound": "GBP", "pounds": "GBP"}


class RuleBasedProvider:
    name = "rules"
    model = "deterministic-parser"

    async def extract_payment(self, message: str) -> dict[str, Any]:
        amount, currency = "", ""
        m = _AMOUNT.search(message)
        if m:
            amount = (m.group("a1") or m.group("a2") or m.group("a3") or "").replace(",", "")
            if m.group("sym"):
                currency = _SYMBOLS[m.group("sym")]
            else:
                code = (m.group("code") or m.group("code2") or "").lower()
                currency = _WORD_CODES.get(code, code.upper())
        email = _EMAIL.search(message)
        invoice = _INVOICE.search(message)
        recipient = _RECIPIENT.search(message) or _PAY_NAME.search(message)
        purpose = _PURPOSE.search(message)
        return {
            "amount": amount,
            "currency": currency,
            "recipient": recipient.group(1).strip() if recipient else "",
            "recipient_email": email.group(0) if email else "",
            "description": purpose.group(1).strip() if purpose else "",
            "invoice_number": invoice.group(1).upper() if invoice else "",
            "confidence": "low",
        }
