import time
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core import config

from .fallback import RuleBasedProvider
from .groq_provider import GroqProvider

_fallback = RuleBasedProvider()


def _normalize(raw: dict[str, Any]) -> dict[str, str]:
    def s(key: str) -> str:
        v = raw.get(key)
        return "" if v is None else str(v).strip()

    amount = s("amount").replace(",", "").lstrip("$€£").strip()
    try:
        d = Decimal(amount)
        if d.is_finite() and d == d.quantize(Decimal("0.01")):
            amount = str(d.quantize(Decimal("0.01")))  # "45" -> "45.00"; "45.001" left as-is for policy to reject
    except InvalidOperation:
        pass  # left as-is; the policy engine rejects it
    confidence = s("confidence").lower()
    return {
        "amount": amount,
        "currency": s("currency").upper(),
        "recipient": s("recipient"),
        "recipient_email": s("recipient_email").lower(),
        "description": s("description"),
        "invoice_number": s("invoice_number").upper(),
        "confidence": confidence if confidence in {"high", "medium", "low"} else "low",
    }


async def extract(message: str) -> dict[str, Any]:
    """Returns {"fields": {...}, "source", "model", "latency_ms", "fallback_reason"}."""
    started = time.perf_counter()
    reason = None
    if config.GROQ_API_KEY:
        provider = GroqProvider()
        try:
            fields = _normalize(await provider.extract_payment(message))
            return {
                "fields": fields,
                "source": provider.name,
                "model": provider.model,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "fallback_reason": None,
            }
        except Exception as e:  # network, auth, deprecated model, bad JSON...
            reason = f"{type(e).__name__}: {str(e)[:200]}"
    else:
        reason = "GROQ_API_KEY is not set"

    fields = _normalize(await _fallback.extract_payment(message))
    fields["confidence"] = "low"
    return {
        "fields": fields,
        "source": _fallback.name,
        "model": _fallback.model,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "fallback_reason": reason,
    }
