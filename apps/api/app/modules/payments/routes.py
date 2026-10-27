"""Execution on PayPal: Payouts (suppliers), Checkout (fallback) and Invoicing (getting paid).

The browser only ever sends a proposal id or an order id.

Amounts, currency and recipient always come from the stored, policy-checked proposal,
and the policy is re-run right before an order is created.
"""
import json
import time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit, config, db
from app.modules.security.policy import evaluate_for
from app.modules.transactions import store

from .paypal_client import PayPalError, approval_link, paypal

router = APIRouter(prefix="/payments", tags=["payments"])


class CreateOrderRequest(BaseModel):
    proposal_id: str = Field(..., min_length=5, max_length=64)
    acknowledge_risks: bool = False


class OrderRequest(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=64, pattern=r"^[A-Z0-9]+$")


HINTS = {
    "invoice": "Turn on Invoicing for your app at developer.paypal.com > Apps & Credentials > your app > Features, then restart the API.",
    "payout": "Turn on Payouts for your app at developer.paypal.com > Apps & Credentials > your app > Features, then restart the API.",
}


def _paypal_http(e: PayPalError, action: str) -> HTTPException:
    if e.status == 403 or "NOT_AUTHORIZED" in (e.issue or e.name or ""):
        key = "invoice" if "invoice" in action else "payout" if "payout" in action else None
        if key:
            return HTTPException(400, f"PayPal {action} isn't enabled for this app. {HINTS[key]}")
    hint = f" (issue: {e.issue})" if e.issue else ""
    code = 400 if 400 <= e.status < 500 else 502
    return HTTPException(code, f"PayPal {action} failed: {e}{hint}")


def _precheck(p: dict[str, Any] | None, acknowledge: bool) -> dict[str, Any]:
    """Status checks, then the policy again against current state (spend and duplicates may have changed)."""
    if not p:
        raise HTTPException(404, "Proposal not found")
    if p.get("kind") == "answer":
        raise HTTPException(400, "This was a question, so there's nothing to execute")
    if p["status"] == "completed":
        raise HTTPException(409, "This proposal has already been carried out")
    if p["status"] == "executing":
        raise HTTPException(409, "This proposal is already being processed")
    if p["status"] not in ("proposed", "cancelled", "awaiting_payer"):
        raise HTTPException(403, f"This request is {p['status']} and cannot be executed")

    kind = p.get("kind") or "payment"
    fields = {k: p[k] or "" for k in store.PROPOSAL_FIELDS}
    ctx = store.policy_context(fields, exclude_proposal=p["id"], kind=kind, payee_id=p.get("payee_id"))
    policy = evaluate_for(kind, fields, p["message"], ctx)

    if policy["decision"] == "blocked":
        with db.write() as c:
            store.update_proposal(c, p["id"], status="blocked", decision="blocked",
                                  risk_level=policy["risk_level"], risk_score=policy["risk_score"],
                                  policy_json=json.dumps(policy))
            audit.append(c, "execution.refused", p["id"], {"reasons": policy["reasons"]})
        raise HTTPException(403, "Blocked by policy: " + "; ".join(policy["reasons"]))
    if policy["decision"] == "review" and not acknowledge:
        raise HTTPException(409, "This needs review. Confirm you've checked: " + "; ".join(policy["reasons"]))
    return policy


def _claim(p: dict[str, Any]) -> None:
    """Move proposed -> executing atomically so a double click can't pay twice."""
    with db.write() as c:
        n = c.execute("UPDATE proposals SET status='executing', updated_at=? WHERE id=? AND status IN ('proposed','cancelled')",
                      (db.now_iso(), p["id"])).rowcount
    if n == 0:
        raise HTTPException(409, "This proposal is already being processed")


def _release(p: dict[str, Any], event: str, data: dict[str, Any]) -> None:
    with db.write() as c:
        store.update_proposal(c, p["id"], status="proposed")
        audit.append(c, event, p["id"], data)


def _start_checkout(p: dict[str, Any], acknowledge: bool) -> dict[str, Any]:
    if p["status"] == "awaiting_payer" and p["approval_url"]:
        return {"order_id": p["order_id"], "approval_url": p["approval_url"], "reused": True}
    policy = _precheck(p, acknowledge)
    fields = {k: p[k] or "" for k in store.PROPOSAL_FIELDS}
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
            "decision": policy["decision"], "acknowledged_risks": acknowledge, "reasons": policy["reasons"],
        })
        audit.append(c, "order.created", p["id"], {
            "order_id": order["id"], "amount": fields["amount"], "currency": fields["currency"],
            "payee": fields["recipient_email"] or "merchant",
        })
    return {"order_id": order["id"], "approval_url": url, "reused": False}


PAYOUT_WAITING = {None, "", "PENDING", "PROCESSING", "NEW"}


def _payout_item(result: dict[str, Any]) -> dict[str, Any]:
    item = (result.get("items") or [{}])[0]
    pi = item.get("payout_item") or {}
    return {
        "status": item.get("transaction_status") or (result.get("batch_header") or {}).get("batch_status") or "PENDING",
        "transaction_id": item.get("transaction_id"),
        "payout_item_id": item.get("payout_item_id"),
        "fee": (item.get("payout_item_fee") or {}).get("value"),
        "amount": (pi.get("amount") or {}).get("value"),
        "currency": (pi.get("amount") or {}).get("currency"),
        "error": (item.get("errors") or {}).get("message") if isinstance(item.get("errors"), dict) else None,
    }


def _send_payout(p: dict[str, Any], acknowledge: bool) -> dict[str, Any]:
    policy = _precheck(p, acknowledge)
    fields = {k: p[k] or "" for k in store.PROPOSAL_FIELDS}
    _claim(p)
    note = fields["description"] + (f" (invoice {fields['invoice_number']})" if fields["invoice_number"] else "")
    try:
        created = paypal().create_payout(batch_id=f"paypilot-{p['id']}", item_id=p["id"], amount=fields["amount"],
                                         currency=fields["currency"], receiver_email=fields["recipient_email"], note=note)
        batch_id = created["batch_header"]["payout_batch_id"]
        result = created
        for _ in range(5):  # sandbox payouts usually settle within a few seconds
            result = paypal().get_payout(batch_id)
            if _payout_item(result)["status"] not in PAYOUT_WAITING:
                break
            time.sleep(0.9)
    except PayPalError as e:
        _release(p, "payout.failed", {"error": str(e), "issue": e.issue, "debug_id": e.debug_id})
        raise _paypal_http(e, "payout")
    except Exception as e:
        _release(p, "payout.failed", {"error": f"{type(e).__name__}: {e}"})
        raise HTTPException(502, f"PayPal payout failed: {e}")

    d = _payout_item(result)
    amount = d["amount"] or fields["amount"]
    currency = d["currency"] or fields["currency"]
    verified = Decimal(amount) == Decimal(fields["amount"]) and currency == fields["currency"]
    counted = d["status"] in store.COUNTED_STATUSES
    with db.write() as c:
        tx_id = store.new_id("txn")
        receipt = store.next_receipt_number(c)
        audit.append(c, "human.approved", p["id"], {
            "decision": policy["decision"], "acknowledged_risks": acknowledge, "reasons": policy["reasons"],
        })
        if not verified:
            audit.append(c, "capture.amount_mismatch", p["id"], {
                "approved": f"{fields['amount']} {fields['currency']}", "sent": f"{amount} {currency}"})
        h = audit.append(c, "payout.sent", p["id"], {
            "transaction_id": tx_id, "receipt_number": receipt, "payout_batch_id": batch_id,
            "payout_item_id": d["payout_item_id"], "status": d["status"], "amount": amount, "currency": currency,
            "receiver": fields["recipient_email"],
        })
        store.insert_transaction(c, {
            "id": tx_id, "receipt_number": receipt, "proposal_id": p["id"], "order_id": batch_id,
            "capture_id": d["transaction_id"], "status": d["status"], "amount": amount,
            "amount_cents": store.to_cents(amount), "currency": currency,
            "recipient": fields["recipient"], "recipient_norm": store.norm(fields["recipient"]) or store.norm(fields["recipient_email"]),
            "recipient_email": fields["recipient_email"], "description": fields["description"],
            "invoice_number": fields["invoice_number"], "invoice_norm": store.norm(fields["invoice_number"]),
            "payer_email": None, "payer_name": config.BUSINESS_NAME, "paypal_fee": d["fee"], "net_amount": None,
            "decision": policy["decision"], "risk_level": policy["risk_level"], "amount_verified": int(verified),
            "audit_hash": h, "created_at": db.now_iso(), "day": db.today(), "rail": "payout",
            "payout_item_id": d["payout_item_id"],
        })
        store.update_proposal(c, p["id"], status="completed" if counted else "failed", order_id=batch_id,
                              decision=policy["decision"], risk_level=policy["risk_level"],
                              risk_score=policy["risk_score"], policy_json=json.dumps(policy))
    return {"transaction": store.get_transaction(tx_id)}


def _send_invoice(p: dict[str, Any], acknowledge: bool) -> dict[str, Any]:
    policy = _precheck(p, acknowledge)
    fields = {k: p[k] or "" for k in store.PROPOSAL_FIELDS}
    _claim(p)
    try:
        created = paypal().create_invoice(amount=fields["amount"], currency=fields["currency"],
                                          recipient_name=fields["recipient"], recipient_email=fields["recipient_email"],
                                          description=fields["description"], reference=p["id"], request_id=f"inv-{p['id']}")
        inv_id = created.get("id") or str(created.get("href", "")).rstrip("/").split("/")[-1]
        sent = paypal().send_invoice(inv_id)
        full = paypal().get_invoice(inv_id)
    except PayPalError as e:
        _release(p, "invoice.failed", {"error": str(e), "issue": e.issue, "debug_id": e.debug_id})
        raise _paypal_http(e, "invoice")
    except Exception as e:
        _release(p, "invoice.failed", {"error": f"{type(e).__name__}: {e}"})
        raise HTTPException(502, f"PayPal invoice failed: {e}")

    detail = full.get("detail") or {}
    meta = detail.get("metadata") or {}
    view_url = meta.get("recipient_view_url") or (sent or {}).get("href")
    now = db.now_iso()
    row_id = store.new_id("inv")
    with db.write() as c:
        audit.append(c, "human.approved", p["id"], {
            "decision": policy["decision"], "acknowledged_risks": acknowledge, "reasons": policy["reasons"],
        })
        h = audit.append(c, "invoice.sent", p["id"], {
            "paypal_invoice_id": inv_id, "invoice_number": detail.get("invoice_number"),
            "status": full.get("status"), "amount": fields["amount"], "currency": fields["currency"],
            "recipient_email": fields["recipient_email"],
        })
        store.insert_invoice(c, {
            "id": row_id, "proposal_id": p["id"], "paypal_invoice_id": inv_id,
            "invoice_number": detail.get("invoice_number"), "status": full.get("status") or "SENT",
            "amount": fields["amount"], "currency": fields["currency"], "recipient": fields["recipient"],
            "recipient_email": fields["recipient_email"], "description": fields["description"],
            "payer_view_url": view_url, "audit_hash": h, "created_at": now, "updated_at": now,
        })
        store.update_proposal(c, p["id"], status="completed", decision=policy["decision"],
                              risk_level=policy["risk_level"], risk_score=policy["risk_score"],
                              policy_json=json.dumps(policy))
    return {"invoice": store.get_invoice(row_id)}


class ExecuteRequest(BaseModel):
    proposal_id: str = Field(..., min_length=5, max_length=64)
    acknowledge_risks: bool = False


@router.post("/execute")
def execute(payload: ExecuteRequest):
    """Carry out an approved proposal on the right PayPal rail.

    payout   -> PayPal Payouts, settles here, returns {"next": "receipt", transaction}
    checkout -> PayPal Checkout, returns {"next": "redirect", approval_url}
    invoice  -> PayPal Invoicing, returns {"next": "invoice", invoice}
    """
    p = store.get_proposal(payload.proposal_id)
    if p and p.get("kind") == "invoice":
        return {"next": "invoice", **_send_invoice(p, payload.acknowledge_risks)}
    if p and p.get("rail") == "payout":
        return {"next": "receipt", **_send_payout(p, payload.acknowledge_risks)}
    if not p:
        raise HTTPException(404, "Proposal not found")
    return {"next": "redirect", **_start_checkout(p, payload.acknowledge_risks)}


@router.post("/create-order")
def create_order(payload: CreateOrderRequest):
    """PayPal Checkout only (kept for compatibility). New clients use /payments/execute."""
    p = store.get_proposal(payload.proposal_id)
    if not p:
        raise HTTPException(404, "Proposal not found")
    if p.get("kind") == "invoice" or p.get("rail") == "payout":
        raise HTTPException(409, "This proposal uses a different PayPal rail. Use /payments/execute")
    return _start_checkout(p, payload.acknowledge_risks)


@router.post("/refresh/{key}")
def refresh(key: str):
    """Re-read a payout's or invoice's status from PayPal (e.g. UNCLAIMED -> SUCCESS, SENT -> PAID)."""
    tx = store.get_transaction(key)
    if tx and tx.get("rail") == "payout":
        try:
            d = _payout_item(paypal().get_payout(tx["order_id"]))
        except PayPalError as e:
            raise _paypal_http(e, "payout status")
        if d["status"] and d["status"] != tx["status"]:
            with db.write() as c:
                c.execute("UPDATE transactions SET status=? WHERE id=?", (d["status"], tx["id"]))
                audit.append(c, "payout.status_changed", tx["proposal_id"], {"from": tx["status"], "to": d["status"]})
        return {"transaction": store.get_transaction(tx["id"])}
    inv = store.get_invoice(key)
    if inv and inv.get("paypal_invoice_id"):
        try:
            full = paypal().get_invoice(inv["paypal_invoice_id"])
        except PayPalError as e:
            raise _paypal_http(e, "invoice status")
        status = full.get("status")
        if status and status != inv["status"]:
            with db.write() as c:
                c.execute("UPDATE invoices SET status=?, updated_at=? WHERE id=?", (status, db.now_iso(), inv["id"]))
                audit.append(c, "invoice.status_changed", inv["proposal_id"], {"from": inv["status"], "to": status})
        return {"invoice": store.get_invoice(inv["id"])}
    raise HTTPException(404, "Nothing to refresh for that id")


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
