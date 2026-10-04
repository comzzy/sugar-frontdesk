"""Bookings + queue storage.

* Locally (and on any server with a disk): SQLite.
* On Vercel, where functions are stateless: a private Vercel Blob store
  (used automatically when BLOB_READ_WRITE_TOKEN is set). Each booking is its own
  JSON object, so updates never race on a shared file.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USE_BLOB = bool(os.environ.get("BLOB_READ_WRITE_TOKEN")) and os.environ.get("FORCE_SQLITE") != "1"
DB_PATH = os.environ.get("DB_PATH") or ("/tmp/sugar.db" if os.environ.get("VERCEL") else None) or str(Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data")) / "sugar.db")
_lock = threading.Lock()
WINDOW = 36 * 3600


def _new(order: dict, engine: str) -> dict:
    return {"id": uuid.uuid4().hex[:10], "created": time.time(), "order": order, "total": order["total"],
            "status": "draft", "paid": 0, "pay_ref": None, "pay_mode": None,
            "queued_at": None, "started_at": None, "done_at": None, "engine": engine}


def _with_positions(rows: list[dict]) -> list[dict]:
    rank = {"in_chair": 0, "paid": 1, "done": 2}
    rows = [r for r in rows if r.get("paid") and (r.get("queued_at") or 0) > time.time() - WINDOW]
    rows.sort(key=lambda b: (rank.get(b["status"], 3), -(b["done_at"] or 0) if b["status"] == "done" else b["queued_at"]))
    pos = 0
    for b in rows:
        if b["status"] == "paid":
            pos += 1
            b["position"] = pos
    return rows


# ---------------------------------------------------------------- Vercel Blob backend
if USE_BLOB:
    from vercel.blob import get as _bget, list_objects as _blist, put as _bput

    def _put(prefix: str, b: dict):
        _bput(f"{prefix}/{b['id']}.json", json.dumps(b).encode(), access="private",
              content_type="application/json", add_random_suffix=False, overwrite=True)

    def _load(path: str) -> dict | None:
        try:
            r = _bget(path, access="private", use_cache=False)
            return json.loads(r.content) if r.status_code == 200 else None
        except Exception:
            return None

    def create_draft(order: dict, engine: str) -> str:
        b = _new(order, engine)
        _put("drafts", b)
        return b["id"]

    def get(bid: str) -> dict | None:
        if not bid.isalnum():
            return None
        return _load(f"queue/{bid}.json") or _load(f"drafts/{bid}.json")

    def set_ref(bid: str, ref: str, mode: str):
        b = get(bid)
        if b:
            b["pay_ref"], b["pay_mode"] = ref, mode
            _put("queue" if b["paid"] else "drafts", b)

    def mark_paid(bid: str, ref: str, mode: str) -> dict | None:
        b = get(bid)
        if not b:
            return None
        if not b["paid"]:
            b.update(paid=1, status="paid", pay_ref=ref, pay_mode=mode, queued_at=time.time())
            _put("queue", b)
        return b

    def set_status(bid: str, status: str) -> dict | None:
        b = _load(f"queue/{bid}.json") if bid.isalnum() else None
        if not b:
            return None
        b["status"] = status
        b["started_at" if status == "in_chair" else "done_at"] = time.time()
        _put("queue", b)
        return b

    def queue() -> list[dict]:
        items = _blist(prefix="queue/", limit=200).blobs
        cutoff = time.time() - WINDOW
        paths = [i.pathname for i in items if i.uploaded_at.timestamp() > cutoff]
        with ThreadPoolExecutor(max_workers=12) as ex:
            rows = [r for r in ex.map(_load, paths) if r]
        return _with_positions(rows)

# ---------------------------------------------------------------- SQLite backend
else:
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

    def _row(r) -> dict:
        d = dict(r)
        d["order"] = json.loads(d.pop("order_json"))
        return d

    def create_draft(order: dict, engine: str) -> str:
        b = _new(order, engine)
        with _lock, _conn() as c:
            c.execute("INSERT INTO bookings (id, created, order_json, total, status, engine) VALUES (?,?,?,?,?,?)",
                      (b["id"], b["created"], json.dumps(order), order["total"], "draft", engine))
        return b["id"]

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
        with _conn() as c:
            rows = c.execute("SELECT * FROM bookings WHERE paid=1").fetchall()
        return _with_positions([_row(r) for r in rows])
