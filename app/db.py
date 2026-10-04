"""Tiny SQLite store for bookings and the queue."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH") or ("/tmp/sugar.db" if os.environ.get("VERCEL") else None) or str(Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data")) / "sugar.db")
_lock = threading.Lock()


def _conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id TEXT PRIMARY KEY, created REAL, order_json TEXT, total INTEGER,
        status TEXT,            -- draft | paid | in_chair | done
        paid INTEGER DEFAULT 0, pay_ref TEXT, pay_mode TEXT,
        queued_at REAL, started_at REAL, done_at REAL, engine TEXT)""")
    return c


def create_draft(order: dict, engine: str) -> str:
    bid = uuid.uuid4().hex[:10]
    with _lock, _conn() as c:
        c.execute("INSERT INTO bookings (id, created, order_json, total, status, engine) VALUES (?,?,?,?,?,?)",
                  (bid, time.time(), json.dumps(order), order["total"], "draft", engine))
    return bid


def get(bid: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
    return _row(r) if r else None


def set_ref(bid: str, ref: str, mode: str):
    with _lock, _conn() as c:
        c.execute("UPDATE bookings SET pay_ref=?, pay_mode=? WHERE id=?", (ref, mode, bid))


def mark_paid(bid: str, ref: str, mode: str) -> dict | None:
    with _lock, _conn() as c:
        c.execute("UPDATE bookings SET paid=1, status=CASE WHEN status='draft' THEN 'paid' ELSE status END, "
                  "pay_ref=?, pay_mode=?, queued_at=COALESCE(queued_at, ?) WHERE id=?", (ref, mode, time.time(), bid))
    return get(bid)


def set_status(bid: str, status: str) -> dict | None:
    col = {"in_chair": "started_at", "done": "done_at"}[status]
    with _lock, _conn() as c:
        c.execute(f"UPDATE bookings SET status=?, {col}=? WHERE id=? AND paid=1", (status, time.time(), bid))
    return get(bid)


def queue() -> list[dict]:
    since = time.time() - 36 * 3600
    with _conn() as c:
        rows = c.execute("SELECT * FROM bookings WHERE paid=1 AND queued_at>? ORDER BY "
                         "CASE status WHEN 'in_chair' THEN 0 WHEN 'paid' THEN 1 ELSE 2 END, "
                         "CASE WHEN status='done' THEN -done_at ELSE queued_at END", (since,)).fetchall()
    out = [_row(r) for r in rows]
    pos = 0
    for b in out:
        if b["status"] == "paid":
            pos += 1
            b["position"] = pos
    return out


def _row(r) -> dict:
    d = dict(r)
    d["order"] = json.loads(d.pop("order_json"))
    return d
