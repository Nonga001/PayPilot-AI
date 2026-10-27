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

CREATE TABLE IF NOT EXISTS payees (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    name_norm        TEXT NOT NULL UNIQUE,
    aliases          TEXT NOT NULL DEFAULT '',
    paypal_email     TEXT,
    country          TEXT,
    default_currency TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id                TEXT PRIMARY KEY,
    proposal_id       TEXT NOT NULL REFERENCES proposals(id),
    paypal_invoice_id TEXT UNIQUE,
    invoice_number    TEXT,
    status            TEXT NOT NULL,
    amount            TEXT NOT NULL,
    currency          TEXT NOT NULL,
    recipient         TEXT,
    recipient_email   TEXT NOT NULL,
    description       TEXT,
    payer_view_url    TEXT,
    audit_hash        TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_invoices_email ON invoices(recipient_email);
"""

# Columns added after the first release. init() adds any that an older database is missing.
MIGRATIONS: dict[str, dict[str, str]] = {
    "proposals": {
        "kind": "TEXT NOT NULL DEFAULT 'payment'",  # payment | invoice | answer
        "rail": "TEXT",                              # payout | checkout | invoice
        "payee_id": "TEXT",
        "agent_json": "TEXT",
    },
    "transactions": {
        "rail": "TEXT NOT NULL DEFAULT 'checkout'",
        "payout_item_id": "TEXT",
    },
}

# Demo suppliers. Swap the emails for your own PayPal sandbox accounts on the Payees page.
SEED_PAYEES = [
    ("Acme Supplies", "acme, acme supplies ltd", "acme.supplies@example.com", "US", "USD", "Packaging supplier"),
    ("Bright Print Co", "bright print, brightprint", "orders@brightprint.example.com", "GB", "GBP", "Printing"),
    ("Kamau Logistics", "kamau, kamau logistics ltd", "pay@kamaulogistics.example.com", "KE", "USD", "Delivery partner, Nairobi"),
    ("Maria Lopez Design", "maria lopez, maria", "maria.lopez@example.com", "ES", "EUR", "Freelance designer"),
]


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
    c = conn()
    statements = [s.strip() for s in SCHEMA.split(";") if s.strip()]
    for stmt in statements:  # tables first
        if stmt.upper().startswith("CREATE TABLE"):
            c.execute(stmt)
    for table, cols in MIGRATIONS.items():  # then columns added since the first release
        have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        for col, ddl in cols.items():
            if col not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    for stmt in statements:  # indexes last, once every column exists
        if stmt.upper().startswith("CREATE INDEX"):
            c.execute(stmt)
    if c.execute("SELECT COUNT(*) AS n FROM payees").fetchone()["n"] == 0:
        import re
        import uuid
        for name, aliases, email, country, cur, notes in SEED_PAYEES:
            c.execute(
                "INSERT INTO payees (id, name, name_norm, aliases, paypal_email, country, default_currency, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"payee_{uuid.uuid4().hex[:16]}", name, re.sub(r"[^a-z0-9@.]+", " ", name.lower()).strip(),
                 aliases, email, country, cur, notes, now_iso()),
            )


def row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None
