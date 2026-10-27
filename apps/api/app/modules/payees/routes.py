from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core import audit, db
from app.modules.security.policy import LIMITS
from app.modules.transactions import store

router = APIRouter(tags=["payees"])

_EMAIL = r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$"


class PayeeIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    paypal_email: str | None = Field(None, max_length=254)
    country: str | None = Field(None, max_length=2)
    default_currency: str | None = Field(None, max_length=3)
    aliases: list[str] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(None, max_length=200)

    @field_validator("paypal_email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        import re
        v = (v or "").strip().lower() or None
        if v and not re.match(_EMAIL, v):
            raise ValueError("Not a valid email address")
        return v

    @field_validator("default_currency")
    @classmethod
    def _cur(cls, v: str | None) -> str | None:
        v = (v or "").strip().upper() or None
        if v and v not in LIMITS:
            raise ValueError(f"Currency must be one of {', '.join(LIMITS)}")
        return v


@router.get("/payees")
def list_payees():
    return {"payees": store.list_payees()}


@router.post("/payees")
def save_payee(p: PayeeIn):
    """Create or update (matched by name). Changes are audited: a swapped PayPal email is a classic fraud move."""
    before = store.resolve_payee({"recipient": p.name})
    saved = store.upsert_payee(p.name.strip(), p.paypal_email, (p.country or "").upper() or None,
                               p.default_currency, [a.strip() for a in p.aliases if a.strip()], p.notes)
    with db.write() as c:
        audit.append(c, "payee.updated" if before else "payee.added", None, {
            "payee_id": saved["id"], "name": saved["name"],
            "paypal_email": saved["paypal_email"], "previous_email": before.get("paypal_email") if before else None,
        })
    return {"payee": saved}


@router.delete("/payees/{payee_id}")
def remove_payee(payee_id: str):
    p = store.get_payee(payee_id)
    if not p or not store.delete_payee(payee_id):
        raise HTTPException(404, "Payee not found")
    with db.write() as c:
        audit.append(c, "payee.removed", None, {"payee_id": payee_id, "name": p["name"]})
    return {"deleted": True}


@router.get("/invoices")
def list_invoices(limit: int = 100):
    return {"invoices": store.list_invoices(min(max(limit, 1), 500))}
