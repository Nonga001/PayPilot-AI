"""Read/write helpers for proposals and transactions (SQLite)."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.core import db
from app.modules.security.policy import DUPLICATE_WINDOW_DAYS, PolicyContext


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9@.]+", " ", (s or "").lower()).strip()


def to_cents(amount: str | Decimal) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


# ---------------------------------------------------------------- proposals
PROPOSAL_FIELDS = (
    "amount", "currency", "recipient", "recipient_email", "description", "invoice_number", "confidence",
)


def proposal_out(p: dict[str, Any] | None) -> dict[str, Any] | None:
    if p is None:
        return None
    policy = json.loads(p.pop("policy_json") or "{}")
    return {
        "id": p["id"],
        "status": p["status"],
        "created_at": p["created_at"],
        "message": p["message"],
        "payment": {k: p[k] or "" for k in PROPOSAL_FIELDS},
        "ai": {"source": p["ai_source"], "model": p["ai_model"], "latency_ms": p["ai_latency_ms"]},
        "policy": policy,
        "explanation": p["explanation"],
        "order_id": p["order_id"],
        "approval_url": p["approval_url"],
    }


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    return db.row(db.conn().execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone())


def get_proposal_by_order(order_id: str) -> dict[str, Any] | None:
    return db.row(db.conn().execute("SELECT * FROM proposals WHERE order_id=?", (order_id,)).fetchone())


def insert_proposal(c: sqlite3.Connection, p: dict[str, Any]) -> None:
    cols = ", ".join(p)
    c.execute(f"INSERT INTO proposals ({cols}) VALUES ({', '.join('?' * len(p))})", tuple(p.values()))


def update_proposal(c: sqlite3.Connection, proposal_id: str, **fields: Any) -> None:
    fields["updated_at"] = db.now_iso()
    sets = ", ".join(f"{k}=?" for k in fields)
    c.execute(f"UPDATE proposals SET {sets} WHERE id=?", (*fields.values(), proposal_id))


# ------------------------------------------------------------- transactions
def spent_today(currency: str) -> Decimal:
    r = db.conn().execute(
        "SELECT COALESCE(SUM(amount_cents),0) AS c FROM transactions "
        "WHERE day=? AND currency=? AND status IN ('COMPLETED','PENDING')",
        (db.today(), currency),
    ).fetchone()
    return Decimal(r["c"]) / 100


def spend_by_currency_today() -> dict[str, Decimal]:
    rows = db.conn().execute(
        "SELECT currency, SUM(amount_cents) AS c, COUNT(*) AS n FROM transactions "
        "WHERE day=? AND status IN ('COMPLETED','PENDING') GROUP BY currency",
        (db.today(),),
    ).fetchall()
    return {r["currency"]: Decimal(r["c"]) / 100 for r in rows}


def policy_context(fields: dict[str, Any], exclude_proposal: str | None = None) -> PolicyContext:
    c = db.conn()
    currency = (fields.get("currency") or "").upper()
    ctx = PolicyContext(spent_today=spent_today(currency) if currency else Decimal("0"))

    invoice = norm(fields.get("invoice_number"))
    if invoice:
        ctx.paid_invoice = db.row(c.execute(
            "SELECT receipt_number, amount, currency, created_at FROM transactions "
            "WHERE invoice_norm=? AND status IN ('COMPLETED','PENDING') ORDER BY created_at DESC LIMIT 1",
            (invoice,),
        ).fetchone())
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
        ctx.pending_invoice = db.row(c.execute(
            "SELECT id FROM proposals WHERE upper(invoice_number)=upper(?) AND status='awaiting_payer' "
            "AND updated_at>=? AND id IS NOT ? LIMIT 1",
            (fields.get("invoice_number"), cutoff, exclude_proposal),
        ).fetchone())

    recipient = norm(fields.get("recipient")) or norm(fields.get("recipient_email"))
    amount = fields.get("amount")
    if recipient and amount and currency:
        try:
            cents = to_cents(amount)
        except Exception:
            cents = None
        if cents is not None:
            since = (datetime.now(timezone.utc) - timedelta(days=DUPLICATE_WINDOW_DAYS)).isoformat(timespec="seconds")
            ctx.similar_recent = db.row(c.execute(
                "SELECT recipient, amount, currency, created_at FROM transactions "
                "WHERE recipient_norm=? AND amount_cents=? AND currency=? AND created_at>=? "
                "AND status IN ('COMPLETED','PENDING') ORDER BY created_at DESC LIMIT 1",
                (recipient, cents, currency, since),
            ).fetchone())
    return ctx


def next_receipt_number(c: sqlite3.Connection) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    n = c.execute("SELECT COUNT(*) AS n FROM transactions WHERE day=?", (db.today(),)).fetchone()["n"] + 1
    return f"PP-{day}-{n:04d}"


def insert_transaction(c: sqlite3.Connection, tx: dict[str, Any]) -> None:
    cols = ", ".join(tx)
    c.execute(f"INSERT INTO transactions ({cols}) VALUES ({', '.join('?' * len(tx))})", tuple(tx.values()))


def tx_out(t: dict[str, Any] | None) -> dict[str, Any] | None:
    if t is None:
        return None
    t = dict(t)
    for k in ("amount_cents", "recipient_norm", "invoice_norm", "day"):
        t.pop(k, None)
    t["amount_verified"] = bool(t.get("amount_verified"))
    return t


def get_transaction(key: str) -> dict[str, Any] | None:
    r = db.conn().execute(
        "SELECT * FROM transactions WHERE id=? OR receipt_number=? OR order_id=? LIMIT 1", (key, key, key)
    ).fetchone()
    return tx_out(db.row(r))


def list_transactions(limit: int = 20) -> list[dict[str, Any]]:
    rows = db.conn().execute("SELECT * FROM transactions ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return [tx_out(dict(r)) for r in rows]


def stats_today() -> dict[str, int]:
    c = db.conn()
    day = db.today()
    p = c.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN decision='blocked' THEN 1 ELSE 0 END) AS blocked, "
        "SUM(CASE WHEN decision='review' THEN 1 ELSE 0 END) AS review "
        "FROM proposals WHERE substr(created_at,1,10)=?",
        (day,),
    ).fetchone()
    t = c.execute("SELECT COUNT(*) AS n FROM transactions WHERE day=?", (day,)).fetchone()
    return {
        "analyzed": p["total"] or 0,
        "blocked": p["blocked"] or 0,
        "review": p["review"] or 0,
        "paid": t["n"] or 0,
    }
