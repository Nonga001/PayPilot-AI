import json
import time
from decimal import Decimal
from typing import Any

from app.core import audit, db
from app.modules.ai.service import extract
from app.modules.security.policy import LIMITS, evaluate
from app.modules.transactions import store


def explain(fields: dict[str, str], policy: dict[str, Any], spent_today: Decimal) -> str:
    """Plain-language summary, built from the checked fields rather than by the AI."""
    amount, currency = fields.get("amount") or "?", fields.get("currency") or ""
    who = fields.get("recipient") or fields.get("recipient_email") or "an unknown recipient"
    lead = "You asked to pay" if policy["decision"] == "blocked" else "You're about to pay"
    parts = [f"{lead} {amount} {currency} to {who}".replace("  ", " ")]
    if fields.get("description"):
        parts[0] += f" for “{fields['description']}”"
    if fields.get("invoice_number"):
        parts[0] += f" (invoice {fields['invoice_number']})"
    parts[0] += "."

    if policy["decision"] != "blocked":
        if fields.get("recipient_email"):
            parts.append(f"PayPal will send the money to {fields['recipient_email']}.")
        else:
            parts.append("No PayPal email was given, so it's paid to the PayPilot business account and logged against this recipient.")

    decision = policy["decision"]
    if decision == "approved":
        limits = LIMITS.get(currency)
        if limits:
            try:
                left = limits[1] - spent_today - Decimal(amount)
                parts.append(f"All {policy['total']} safety checks passed. You'll have {left:.2f} {currency} of today's limit left.")
            except Exception:
                parts.append(f"All {policy['total']} safety checks passed.")
        parts.append("Nothing moves until you approve it, then confirm again on PayPal.")
    elif decision == "review":
        parts.append("Some details need your attention: " + "; ".join(policy["reasons"]) + ".")
        parts.append("You can still go ahead, but you'll need to confirm you've checked them.")
    else:
        parts.append("PayPilot blocked this payment: " + "; ".join(policy["reasons"]) + ".")
        parts.append("No money can move for this request.")
    return " ".join(parts)


async def analyze(message: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    ai = await extract(message)
    fields = ai["fields"]

    ctx = store.policy_context(fields)
    policy = evaluate(fields, message, ctx)
    if ai["source"] != "groq":
        policy["reasons"].insert(0, "AI was unavailable, so a backup rule-based parser read this request")
    explanation = explain(fields, policy, ctx.spent_today)

    now = db.now_iso()
    pid = store.new_id("prop")
    status = "blocked" if policy["decision"] == "blocked" else "proposed"
    with db.write() as c:
        store.insert_proposal(c, {
            "id": pid, "created_at": now, "updated_at": now, "message": message,
            **{k: fields.get(k, "") for k in store.PROPOSAL_FIELDS},
            "ai_source": ai["source"], "ai_model": ai["model"], "ai_latency_ms": ai["latency_ms"],
            "decision": policy["decision"], "risk_level": policy["risk_level"], "risk_score": policy["risk_score"],
            "policy_json": json.dumps(policy), "explanation": explanation, "status": status,
        })
        audit.append(c, "request.received", pid, {"message": message})
        audit.append(c, "ai.extracted", pid, {
            "source": ai["source"], "model": ai["model"], "latency_ms": ai["latency_ms"],
            "fallback_reason": ai["fallback_reason"], "fields": fields,
        })
        audit.append(c, f"policy.{policy['decision']}", pid, {
            "risk_score": policy["risk_score"], "reasons": policy["reasons"],
            "failed": [ch["id"] for ch in policy["checks"] if not ch["passed"]],
        })

    out = store.proposal_out(store.get_proposal(pid))
    out["ai"]["fallback_reason"] = ai["fallback_reason"]
    out["timing_ms"] = {"ai": ai["latency_ms"], "total": int((time.perf_counter() - t0) * 1000)}
    return out
