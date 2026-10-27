"""Append-only, hash-chained audit log.

Each event stores sha256(prev_hash | ts | event | proposal_id | data). Editing or deleting
any past row breaks every hash after it, which /audit/verify detects.
"""
import hashlib
import json
import sqlite3
from typing import Any

from app.core import db

GENESIS = "0" * 64


def _digest(prev: str, ts: str, event: str, proposal_id: str | None, data: str) -> str:
    return hashlib.sha256(f"{prev}|{ts}|{event}|{proposal_id or ''}|{data}".encode()).hexdigest()


def append(c: sqlite3.Connection, event: str, proposal_id: str | None, data: dict[str, Any]) -> str:
    """Must be called inside db.write()."""
    last = c.execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
    prev = last["hash"] if last else GENESIS
    ts = db.now_iso()
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    h = _digest(prev, ts, event, proposal_id, payload)
    c.execute(
        "INSERT INTO audit_events (ts, event, proposal_id, data, prev_hash, hash) VALUES (?,?,?,?,?,?)",
        (ts, event, proposal_id, payload, prev, h),
    )
    return h


def _out(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["data"] = json.loads(d["data"])
    return d


def recent(limit: int = 20, proposal_id: str | None = None) -> list[dict[str, Any]]:
    c = db.conn()
    if proposal_id:
        rows = c.execute(
            "SELECT * FROM audit_events WHERE proposal_id=? ORDER BY seq ASC", (proposal_id,)
        ).fetchall()
    else:
        rows = c.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    return [_out(r) for r in rows]


def verify() -> dict[str, Any]:
    prev = GENESIS
    count = 0
    for r in db.conn().execute("SELECT * FROM audit_events ORDER BY seq ASC"):
        count += 1
        if r["prev_hash"] != prev or _digest(prev, r["ts"], r["event"], r["proposal_id"], r["data"]) != r["hash"]:
            return {"valid": False, "count": count, "broken_at": r["seq"], "head": prev}
        prev = r["hash"]
    return {"valid": True, "count": count, "broken_at": None, "head": prev}
