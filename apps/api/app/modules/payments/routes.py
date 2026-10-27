"""Payment execution. The browser only ever sends a proposal id or an order id.

Amounts, currency and recipient always come from the stored, policy-checked proposal,
and the policy is re-run right before an order is created.
"""
import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit, config, db
from app.modules.security.policy import evaluate
from app.modules.transactions import store

from .paypal_client import PayPalError, approval_link, paypal

router = APIRouter(prefix="/payments", tags=["payments"])


class CreateOrderRequest(BaseModel):
    proposal_id: str = Field(..., min_length=5, max_length=64)
    acknowledge_risks: bool = False


class OrderRequest(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=64, pattern=r"^[A-Z0-9]+$")


def _paypal_http(e: PayPalError, action: str) -> HTTPException:
    hint = f" (issue: {e.issue})" if e.issue else ""
    code = 400 if 400 <= e.status < 500 else 502
    return HTTPException(code, f"PayPal {action} failed: {e}{hint}")


@router.post("/create-order")
def create_order(payload: CreateOrderRequest):
    p = store.get_proposal(payload.proposal_id)
    if not p:
        raise HTTPException(404, "Proposal not found")
    if p["status"] == "completed":
        raise HTTPException(409, "This proposal has already been paid")
    if p["status"] == "awaiting_payer" and p["approval_url"]:
        return {"order_id": p["order_id"], "approval_url": p["approval_url"], "reused": True}
    if p["status"] not in ("proposed", "cancelled"):
        raise HTTPException(403, f"This payment is {p['status']} and cannot be executed")

    # Re-run the policy against current state (daily spend and duplicates may have changed).
    fields = {k: p[k] or "" for k in store.PROPOSAL_FIELDS}
    policy = evaluate(fields, p["message"], store.policy_context(fields, exclude_proposal=p["id"]))

    if policy["decision"] == "blocked":
        with db.write() as c:
            store.update_proposal(c, p["id"], status="blocked", decision="blocked",
                                  risk_level=policy["risk_level"], risk_score=policy["risk_score"],
                                  policy_json=json.dumps(policy))
            audit.append(c, "execution.refused", p["id"], {"reasons": policy["reasons"]})
        raise HTTPException(403, "Blocked by policy: " + "; ".join(policy["reasons"]))

    if policy["decision"] == "review" and not payload.acknowledge_risks:
        raise HTTPException(409, "This payment needs review. Confirm you've checked: " + "; ".join(policy["reasons"]))

    try:
        order = paypal().create_order(
            amount=fields["amount"], currency=fields["currency"], description=fields["description"],
            custom_id=p["id"], payee_email=fields["recipient_email"] or None,
            return_url=f"{config.FRONTEND_URL}/payment/success",
            cancel_url=f"{config.FRONTEND_URL}/payment/cancel",
            request_id=f"order-{p['id']}-{p['updated_at']}",
        )
    except PayPalError as e:
        with db.write() as c:
            audit.append(c, "order.failed", p["id"], {"error": str(e), "issue": e.issue, "debug_id": e.debug_id})
        raise _paypal_http(e, "create order")

    url = approval_link(order)
    with db.write() as c:
        store.update_proposal(c, p["id"], status="awaiting_payer", order_id=order["id"], approval_url=url,
                              decision=policy["decision"], risk_level=policy["risk_level"],
                              risk_score=policy["risk_score"], policy_json=json.dumps(policy))
        audit.append(c, "human.approved", p["id"], {
            "decision": policy["decision"], "acknowledged_risks": payload.acknowledge_risks,
            "reasons": policy["reasons"],
        })
        audit.append(c, "order.created", p["id"], {
            "order_id": order["id"], "amount": fields["amount"], "currency": fields["currency"],
            "payee": fields["recipient_email"] or "merchant",
        })
    return {"order_id": order["id"], "approval_url": url, "reused": False}


def _capture_details(result: dict[str, Any]) -> dict[str, Any]:
    unit = (result.get("purchase_units") or [{}])[0]
    cap = ((unit.get("payments") or {}).get("captures") or [{}])[0]
    breakdown = cap.get("seller_receivable_breakdown") or {}
    payer = result.get("payer") or {}
    name = payer.get("name") or {}
    return {
        "capture_id": cap.get("id"),
        "status": cap.get("status") or result.get("status"),
        "amount": (cap.get("amount") or {}).get("value"),
        "currency": (cap.get("amount") or {}).get("currency_code"),
        "paypal_fee": (breakdown.get("paypal_fee") or {}).get("value"),
        "net_amount": (breakdown.get("net_amount") or {}).get("value"),
        "payer_email": payer.get("email_address"),
        "payer_name": " ".join(x for x in (name.get("given_name"), name.get("surname")) if x) or None,
    }


@router.post("/capture-order")
def capture_order(payload: OrderRequest):
    p = store.get_proposal_by_order(payload.order_id)
    if not p:
        raise HTTPException(404, "Unknown order: it was not created by PayPilot")

    existing = store.get_transaction(payload.order_id)
    if existing:  # page reload / double click: idempotent
        return {"transaction": existing, "already_captured": True}

    if p["status"] != "awaiting_payer":
        raise HTTPException(409, f"Order cannot be captured (proposal is {p['status']})")

    try:
        result = paypal().capture_order(payload.order_id)
    except PayPalError as e:
        if e.issue == "ORDER_ALREADY_CAPTURED":
            result = paypal().get_order(payload.order_id)
        else:
            with db.write() as c:
                audit.append(c, "capture.failed", p["id"], {"error": str(e), "issue": e.issue, "debug_id": e.debug_id})
            raise _paypal_http(e, "capture")

    d = _capture_details(result)
    if not d["amount"] or not d["currency"]:
        raise HTTPException(502, "PayPal returned no capture details")

    # Record what PayPal says actually moved, and flag any mismatch with what was approved.
    verified = Decimal(d["amount"]) == Decimal(p["amount"]) and d["currency"] == p["currency"]

    with db.write() as c:
        again = c.execute("SELECT id FROM transactions WHERE order_id=?", (payload.order_id,)).fetchone()
        if again:
            return {"transaction": store.get_transaction(payload.order_id), "already_captured": True}
        tx_id = store.new_id("txn")
        receipt = store.next_receipt_number(c)
        if not verified:
            audit.append(c, "capture.amount_mismatch", p["id"], {
                "approved": f"{p['amount']} {p['currency']}", "captured": f"{d['amount']} {d['currency']}",
            })
        h = audit.append(c, "payment.captured", p["id"], {
            "transaction_id": tx_id, "receipt_number": receipt, "order_id": payload.order_id,
            "capture_id": d["capture_id"], "status": d["status"], "amount": d["amount"], "currency": d["currency"],
        })
        store.insert_transaction(c, {
            "id": tx_id, "receipt_number": receipt, "proposal_id": p["id"], "order_id": payload.order_id,
            "capture_id": d["capture_id"], "status": d["status"], "amount": d["amount"],
            "amount_cents": store.to_cents(d["amount"]), "currency": d["currency"],
            "recipient": p["recipient"], "recipient_norm": store.norm(p["recipient"]) or store.norm(p["recipient_email"]),
            "recipient_email": p["recipient_email"], "description": p["description"],
            "invoice_number": p["invoice_number"], "invoice_norm": store.norm(p["invoice_number"]),
            "payer_email": d["payer_email"], "payer_name": d["payer_name"],
            "paypal_fee": d["paypal_fee"], "net_amount": d["net_amount"],
            "decision": p["decision"], "risk_level": p["risk_level"], "amount_verified": int(verified),
            "audit_hash": h, "created_at": db.now_iso(), "day": db.today(),
        })
        store.update_proposal(c, p["id"], status="completed" if d["status"] in ("COMPLETED", "PENDING") else "failed")

    return {"transaction": store.get_transaction(tx_id), "already_captured": False}


@router.post("/cancel")
def cancel(payload: OrderRequest):
    p = store.get_proposal_by_order(payload.order_id)
    if not p:
        raise HTTPException(404, "Unknown order")
    if p["status"] == "awaiting_payer":
        with db.write() as c:
            store.update_proposal(c, p["id"], status="cancelled")
            audit.append(c, "payer.cancelled", p["id"], {"order_id": payload.order_id})
    return {"proposal_id": p["id"], "status": "cancelled" if p["status"] == "awaiting_payer" else p["status"]}
