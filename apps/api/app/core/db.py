"""Tiny SQLite layer: one connection per thread, WAL mode, serialized writes."""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.core import config

_local = threading.local()
_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    message         TEXT NOT NULL,
    amount          TEXT,
    currency        TEXT,
    recipient       TEXT,
    recipient_email TEXT,
    description     TEXT,
    invoice_number  TEXT,
    confidence      TEXT,
    ai_source       TEXT,
    ai_model        TEXT,
    ai_latency_ms   INTEGER,
    decision        TEXT,
    risk_level      TEXT,
    risk_score      INTEGER,
    policy_json     TEXT,
    explanation     TEXT,
    status          TEXT NOT NULL,
    order_id        TEXT UNIQUE,
    approval_url    TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id              TEXT PRIMARY KEY,
    receipt_number  TEXT UNIQUE NOT NULL,
    proposal_id     TEXT NOT NULL REFERENCES proposals(id),
    order_id        TEXT UNIQUE NOT NULL,
    capture_id      TEXT UNIQUE,
    status          TEXT NOT NULL,
    amount          TEXT NOT NULL,
    amount_cents    INTEGER NOT NULL,
    currency        TEXT NOT NULL,
    recipient       TEXT,
    recipient_norm  TEXT,
    recipient_email TEXT,
    description     TEXT,
    invoice_number  TEXT,
    invoice_norm    TEXT,
    payer_email     TEXT,
    payer_name      TEXT,
    paypal_fee      TEXT,
    net_amount      TEXT,
    decision        TEXT,
    risk_level      TEXT,
    amount_verified INTEGER NOT NULL DEFAULT 1,
    audit_hash      TEXT,
    created_at      TEXT NOT NULL,
    day             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tx_day_currency ON transactions(day, currency);
CREATE INDEX IF NOT EXISTS ix_tx_invoice ON transactions(invoice_norm);
CREATE INDEX IF NOT EXISTS ix_tx_recipient ON transactions(recipient_norm, currency);

CREATE TABLE IF NOT EXISTS audit_events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    event       TEXT NOT NULL,
    proposal_id TEXT,
    data        TEXT NOT NULL,
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_proposal ON audit_events(proposal_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.conn = c
    return c


@contextmanager
def write() -> Iterator[sqlite3.Connection]:
    """Serialized write transaction (keeps the audit hash chain strictly ordered)."""
    c = conn()
    with _write_lock:
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def init() -> None:
    conn().executescript(SCHEMA)


def row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None
