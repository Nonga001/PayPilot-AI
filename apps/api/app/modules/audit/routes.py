from fastapi import APIRouter, Query

from app.core import audit, config
from app.modules.security.policy import LIMITS, limits_view
from app.modules.transactions import store

router = APIRouter(tags=["audit"])


@router.get("/audit")
def audit_log(limit: int = Query(50, ge=1, le=500)):
    return {"events": audit.recent(limit)}


@router.get("/audit/verify")
def audit_verify():
    return audit.verify()


@router.get("/dashboard")
def dashboard():
    """Everything the home screen needs in one request."""
    spend = store.spend_by_currency_today()
    budgets = []
    for cur, (per_tx, per_day) in LIMITS.items():
        spent = spend.get(cur)
        if spent is None and cur != "USD":
            continue  # only show currencies in use (USD always shown)
        spent = spent or 0
        budgets.append({
            "currency": cur, "spent": f"{spent:.2f}", "limit": f"{per_day:.2f}",
            "per_transaction": f"{per_tx:.2f}", "remaining": f"{per_day - spent:.2f}",
        })
    return {
        "budgets": budgets,
        "limits": limits_view(),
        "stats": store.stats_today(),
        "transactions": store.list_transactions(6),
        "invoices": store.list_invoices(4),
        "payees": len(store.list_payees()),
        "audit": {**audit.verify(), "events": audit.recent(8)},
        "environment": {
            "paypal": "sandbox" if "sandbox" in config.PAYPAL_API_BASE else "live",
            "ai_model": config.GROQ_MODEL if config.GROQ_API_KEY else "rules (no GROQ_API_KEY)",
        },
    }
