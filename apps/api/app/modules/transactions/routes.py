from fastapi import APIRouter, HTTPException, Query

from app.core import audit

from . import store

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Transactions are written only by /payments/execute (Payouts) and /payments/capture-order (Checkout),
# from PayPal's own responses. There is deliberately no POST here: the browser can't record payments.


@router.get("")
def list_recent(limit: int = Query(20, ge=1, le=500)):
    return {"transactions": store.list_transactions(limit)}


@router.get("/{key}")
def receipt(key: str):
    """Look up by transaction id, receipt number or PayPal order id. Includes the audit trail."""
    tx = store.get_transaction(key)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    proposal = store.proposal_out(store.get_proposal(tx["proposal_id"]))
    return {
        "transaction": tx,
        "proposal": proposal,
        "audit": audit.recent(proposal_id=tx["proposal_id"]),
    }
