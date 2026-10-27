import json
import time
from decimal import Decimal
from typing import Any

from app.core import audit, db
from app.modules.security.policy import LIMITS, evaluate_for
from app.modules.transactions import store

from . import brain, tools


def explain(fields: dict[str, str], policy: dict[str, Any], spent_today: Decimal, kind: str = "payment",
            rail: str | None = None) -> str:
    """Plain-language summary, built from the checked fields rather than by the AI."""
    amount, currency = fields.get("amount") or "?", fields.get("currency") or ""
    who = fields.get("recipient") or fields.get("recipient_email") or "an unknown recipient"
    decision = policy["decision"]

    if kind == "invoice":
        lead = "You asked to invoice" if decision == "blocked" else "PayPilot will send"
        first = (f"{lead} {who} for {amount} {currency}" if decision == "blocked"
                 else f"{lead} {who} a PayPal invoice for {amount} {currency}").replace("  ", " ")
        if fields.get("description"):
            first += f" for “{fields['description']}”"
        parts = [first + "."]
        if decision != "blocked" and fields.get("recipient_email"):
            parts.append(f"PayPal emails it to {fields['recipient_email']}, and they can pay by PayPal or card. Payment is due in 10 days.")
    else:
        lead = "You asked to pay" if decision == "blocked" else "You're about to pay"
        first = f"{lead} {amount} {currency} to {who}".replace("  ", " ")
        if fields.get("description"):
            first += f" for “{fields['description']}”"
        if fields.get("invoice_number"):
            first += f" (invoice {fields['invoice_number']})"
        parts = [first + "."]
        if decision != "blocked":
            if rail == "payout":
                parts.append(f"PayPal Payouts sends it straight from your business balance to {fields['recipient_email']}.")
            else:
                parts.append("There's no PayPal email for this recipient, so you'll pay through PayPal Checkout into the "
                             "PayPilot business account, logged against this recipient.")

    if decision == "approved":
        limits = LIMITS.get(currency)
        if kind == "payment" and limits:
            try:
                left = limits[1] - spent_today - Decimal(amount)
                parts.append(f"All {policy['total']} safety checks passed. You'll have {left:.2f} {currency} of today's limit left.")
            except Exception:
                parts.append(f"All {policy['total']} safety checks passed.")
        else:
            parts.append(f"All {policy['total']} safety checks passed.")
        parts.append("Nothing happens until you approve it.")
    elif decision == "review":
        parts.append("Some details need your attention: " + "; ".join(policy["reasons"]) + ".")
        parts.append("You can still go ahead, but you'll need to confirm you've checked them.")
    else:
        parts.append("PayPilot blocked this: " + "; ".join(policy["reasons"]) + ".")
        parts.append("Nothing can be sent for this request.")
    return " ".join(parts)


def _ensure_steps(plan: dict[str, Any], fields: dict[str, str], kind: str) -> None:
    """Server-side lookups the policy depends on are always run and shown, even if the model skipped them."""
    have = {s["tool"] for s in plan["steps"]}
    if "find_payee" not in have and (fields.get("recipient") or fields.get("recipient_email")):
        _, step = tools.run("find_payee", {"query": fields.get("recipient") or fields.get("recipient_email")}, auto=True)
        plan["steps"].insert(0, step)
    if kind == "payment" and "get_budget" not in have and fields.get("currency"):
        _, step = tools.run("get_budget", {"currency": fields["currency"]}, auto=True)
        plan["steps"].insert(-1, step)
    if kind == "payment" and "check_payment_history" not in have and (fields.get("recipient") or fields.get("invoice_number")):
        _, step = tools.run("check_payment_history",
                            {"recipient": fields.get("recipient"), "invoice_number": fields.get("invoice_number")}, auto=True)
        plan["steps"].insert(-1, step)


async def analyze(message: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    plan = await brain.plan(message)
    kind = plan["kind"]
    now = db.now_iso()
    pid = store.new_id("prop")
    base = {"id": pid, "created_at": now, "updated_at": now, "message": message,
            "ai_source": plan["source"], "ai_model": plan["model"], "ai_latency_ms": plan["latency_ms"]}

    if kind == "answer":
        agent_blob = {"steps": plan["steps"], "answer": plan["answer"], "fallback_reason": plan["fallback_reason"]}
        with db.write() as c:
            store.insert_proposal(c, {**base, **{k: "" for k in store.PROPOSAL_FIELDS}, "kind": "answer",
                                      "status": "answered", "agent_json": json.dumps(agent_blob), "explanation": plan["answer"]})
            audit.append(c, "request.received", pid, {"message": message})
            audit.append(c, "agent.answered", pid, {"source": plan["source"], "steps": [s["summary"] for s in plan["steps"]]})
        return _out(pid, plan, t0)

    fields = plan["fields"]
    payee = store.resolve_payee(fields, plan.get("payee_id"))
    if payee:
        fields["recipient"] = payee["name"]
        if not fields.get("recipient_email") and payee.get("paypal_email"):
            fields["recipient_email"] = payee["paypal_email"].lower()
        if not fields.get("currency") and payee.get("default_currency"):
            fields["currency"] = payee["default_currency"]
    _ensure_steps(plan, fields, kind)

    rail = "invoice" if kind == "invoice" else ("payout" if fields.get("recipient_email") else "checkout")
    ctx = store.policy_context(fields, kind=kind, payee_id=payee["id"] if payee else None)
    policy = evaluate_for(kind, fields, message, ctx)
    if plan["source"] != "groq":
        policy["reasons"].insert(0, "AI was unavailable, so a backup rule-based parser read this request")
    explanation = explain(fields, policy, ctx.spent_today, kind, rail)
    status = "blocked" if policy["decision"] == "blocked" else "proposed"
    agent_blob = {"steps": plan["steps"], "answer": None, "fallback_reason": plan["fallback_reason"]}

    with db.write() as c:
        store.insert_proposal(c, {
            **base, **{k: fields.get(k, "") for k in store.PROPOSAL_FIELDS},
            "kind": kind, "rail": rail, "payee_id": payee["id"] if payee else None,
            "decision": policy["decision"], "risk_level": policy["risk_level"], "risk_score": policy["risk_score"],
            "policy_json": json.dumps(policy), "explanation": explanation, "status": status,
            "agent_json": json.dumps(agent_blob),
        })
        audit.append(c, "request.received", pid, {"message": message})
        audit.append(c, "ai.extracted", pid, {
            "source": plan["source"], "model": plan["model"], "latency_ms": plan["latency_ms"],
            "fallback_reason": plan["fallback_reason"], "kind": kind, "rail": rail, "fields": fields,
            "steps": [f"{s['label']}: {s['summary']}" for s in plan["steps"]],
        })
        audit.append(c, f"policy.{policy['decision']}", pid, {
            "risk_score": policy["risk_score"], "reasons": policy["reasons"],
            "failed": [ch["id"] for ch in policy["checks"] if not ch["passed"]],
        })
    return _out(pid, plan, t0)


def _out(pid: str, plan: dict[str, Any], t0: float) -> dict[str, Any]:
    out = store.proposal_out(store.get_proposal(pid))
    out["ai"]["fallback_reason"] = plan["fallback_reason"]
    out["timing_ms"] = {"ai": plan["latency_ms"], "total": int((time.perf_counter() - t0) * 1000)}
    return out
