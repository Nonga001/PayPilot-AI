"""Keeps open PayPal invoices up to date, so "Sent, unpaid" turns into "Paid" once the client pays.

PayPal can push this with webhooks, but those need a public, verified endpoint. Polling is enough here: the ledger
and dashboard call sync_open_invoices() when they load, at most once every MIN_INTERVAL seconds.
"""
import logging
import threading
import time

from app.core import audit, db
from app.modules.payments import paypal_client
from app.modules.transactions import store

log = logging.getLogger(__name__)

OPEN = ("SENT", "UNPAID", "PARTIALLY_PAID", "SCHEDULED")
MIN_INTERVAL = 15  # seconds between PayPal checks
MAX_PER_SYNC = 10
_last = 0.0
_lock = threading.Lock()


def update_invoice(inv: dict, status: str | None) -> dict:
    """Store a new status from PayPal (audited). Returns the invoice as stored."""
    if status and status != inv["status"]:
        with db.write() as c:
            c.execute("UPDATE invoices SET status=?, updated_at=? WHERE id=?", (status, db.now_iso(), inv["id"]))
            audit.append(c, "invoice.status_changed", inv["proposal_id"], {"from": inv["status"], "to": status})
    return store.get_invoice(inv["id"]) or inv


def sync_open_invoices(force: bool = False) -> int:
    """Re-read open invoices from PayPal. Never raises: a PayPal hiccup must not break the page. Returns changes."""
    global _last
    with _lock:
        if not force and time.monotonic() - _last < MIN_INTERVAL:
            return 0
        _last = time.monotonic()
    rows = db.conn().execute(
        f"SELECT * FROM invoices WHERE paypal_invoice_id IS NOT NULL AND status IN ({','.join('?' * len(OPEN))}) "
        "ORDER BY created_at DESC LIMIT ?", (*OPEN, MAX_PER_SYNC),
    ).fetchall()
    changed = 0
    for r in rows:
        inv = dict(r)
        try:
            status = paypal_client.paypal().get_invoice(inv["paypal_invoice_id"]).get("status")
        except Exception as e:  # PayPalError, network: try again next time
            log.info("invoice sync skipped %s: %s", inv["id"], type(e).__name__)
            continue
        if status and status != inv["status"]:
            update_invoice(inv, status)
            changed += 1
    return changed
