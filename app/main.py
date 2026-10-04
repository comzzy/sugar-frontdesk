"""Sugar Nails front desk: booking chat + payment + Sugar's live queue."""
from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import sys
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import llm  # noqa: E402
from engine import LOCATION_Q, ScriptedEngine, fix_location, location_answer, normalise_order, parse_reply  # noqa: E402

PUBLIC = Path(__file__).resolve().parent.parent / "public"
STATIC = PUBLIC / "static"
PAYSTACK_SECRET = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYMENT_MODE = "paystack" if PAYSTACK_SECRET else "mock"   # mock = simulated payment until Sugar connects Paystack
QUEUE_PIN = os.environ.get("QUEUE_PIN", "2580")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "")

app = FastAPI(title="Sugar Nails front desk")
fallback = ScriptedEngine()


class Msg(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[Msg]
    engine: str | None = None   # "fallback" once a session has fallen back


@app.get("/api/health")
def health():
    return {"ok": True, "tinker": llm.enabled(), "model": llm.model_path() if llm.enabled() else None,
            "payment_mode": PAYMENT_MODE}


@app.get("/api/config")
def config():
    return {"payment_mode": PAYMENT_MODE, "tinker": llm.enabled()}


@app.get("/api/menu")
def menu_api():
    from menu import COLOURS, LENGTHS, SERVICES, SHAPES, STYLES
    return {"services": [{"id": k, "label": v[0], "price": v[1], "extension": v[2]} for k, v in SERVICES.items()],
            "styles": [{"id": k, "label": v[0], "price": v[1]} for k, v in STYLES.items()],
            "colours": COLOURS, "shapes": SHAPES,
            "lengths": [{"id": k, "label": v[0], "price": v[1]} for k, v in LENGTHS.items()]}


@app.get("/api/queue/count")
def queue_count():
    q = db.queue()
    return {"waiting": sum(1 for b in q if b["status"] == "paid"), "in_chair": sum(1 for b in q if b["status"] == "in_chair")}


@app.post("/api/chat")
async def chat(body: ChatIn):
    history = [m.model_dump() for m in body.messages if m.role in ("user", "assistant")][-40:]
    for m in history:
        m["content"] = m["content"][:600]
    users = [m["content"] for m in history if m["role"] == "user"]
    engine, text, ms = "fallback", None, 0
    if llm.enabled() and body.engine != "fallback":
        t = time.time()
        try:
            text = await asyncio.wait_for(llm.complete(history), timeout=llm.TIMEOUT)
            engine = "tinker"
            parsed = parse_reply(text)
            if parsed["order_error"] or not parsed["text"]:
                text = None   # malformed: let the fallback answer this turn
        except Exception as e:  # timeout / network / quota
            print("tinker inference failed:", repr(e)[:200])
            text = None
        ms = int((time.time() - t) * 1000)
    if text is None:
        engine = "fallback"
        # a location question isn't a slot answer ("Where..." is not a name)
        text = fallback.respond([u for u in users if not LOCATION_Q.search(u)] or ["hi"])
    parsed = parse_reply(fix_location(text))
    parsed["text"] = location_answer(users, parsed["text"])
    out = {"text": parsed["text"], "chips": parsed["chips"], "multi": parsed["multi"], "engine": engine, "ms": ms}
    if parsed["order"]:
        order = normalise_order(parsed["order"])
        if order["services"] and order["name"]:
            order["booking_id"] = db.create_draft(order, engine)
            out["order"] = order
    return out


# ---------------------------------------------------------------- payments
class PayIn(BaseModel):
    booking_id: str
    email: str | None = None


@app.post("/api/pay/init")
async def pay_init(body: PayIn, request: Request):
    b = db.get(body.booking_id)
    if not b:
        raise HTTPException(404, "booking not found")
    if b["paid"]:
        return {"mode": b["pay_mode"], "paid": True}
    if PAYMENT_MODE == "mock":
        ref = "TEST-" + secrets.token_hex(4).upper()
        db.set_ref(b["id"], ref, "mock")
        return {"mode": "mock", "reference": ref, "amount": b["total"]}
    base = PUBLIC_URL or str(request.base_url).rstrip("/")
    email = body.email or f"guest-{b['id']}@sugarnails.ng"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://api.paystack.co/transaction/initialize",
                         headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
                         json={"email": email, "amount": b["total"] * 100, "currency": "NGN",
                               "callback_url": f"{base}/api/pay/callback?booking={b['id']}",
                               "metadata": {"booking_id": b["id"]}})
    data = r.json()
    if not data.get("status"):
        raise HTTPException(502, data.get("message", "paystack error"))
    db.set_ref(b["id"], data["data"]["reference"], "paystack")
    return {"mode": "paystack", "authorization_url": data["data"]["authorization_url"], "reference": data["data"]["reference"]}


@app.post("/api/pay/confirm")
@app.post("/api/pay/mock-confirm")  # older clients
def pay_mock(body: PayIn):
    if PAYMENT_MODE != "mock":
        raise HTTPException(400, "mock payments are disabled")
    b = db.get(body.booking_id)
    if not b:
        raise HTTPException(404, "booking not found")
    b = db.mark_paid(b["id"], b["pay_ref"] or "TEST", "mock")
    return {"paid": True, "booking": _public(b)}


@app.get("/api/pay/callback")
async def pay_callback(booking: str, reference: str = "", trxref: str = ""):
    ref = reference or trxref
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"https://api.paystack.co/transaction/verify/{ref}",
                        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"})
    d = r.json().get("data") or {}
    b = db.get(booking)
    if b and d.get("status") == "success" and d.get("amount") == b["total"] * 100:
        db.mark_paid(booking, ref, "paystack")
    return RedirectResponse(f"/?booking={booking}#book")


@app.get("/api/booking/{bid}")
def booking_status(bid: str):
    b = db.get(bid)
    if not b:
        raise HTTPException(404, "not found")
    pos = next((q.get("position") for q in db.queue() if q["id"] == bid), None)
    return {**_public(b), "position": pos}


def _public(b):
    o = b["order"]
    return {"id": b["id"], "status": b["status"], "paid": bool(b["paid"]), "total": b["total"],
            "name": o.get("name"), "services": o.get("services"), "pay_mode": b["pay_mode"], "reference": b["pay_ref"]}


# ---------------------------------------------------------------- Sugar's queue
def _check_pin(pin: str | None):
    if not pin or not hmac.compare_digest(pin, QUEUE_PIN):
        raise HTTPException(401, "wrong PIN")


@app.post("/api/queue/login")
def queue_login(x_pin: str | None = Header(default=None)):
    _check_pin(x_pin)
    return {"ok": True}


@app.get("/api/queue")
def get_queue(x_pin: str | None = Header(default=None)):
    _check_pin(x_pin)
    return {"queue": db.queue(), "now": time.time()}


@app.post("/api/queue/clear")
def queue_clear(x_pin: str | None = Header(default=None)):
    """Sugar's 'clear test bookings' action: empties the queue and unpaid drafts."""
    _check_pin(x_pin)
    return {"ok": True, "removed": db.clear_all()}


@app.delete("/api/queue/{bid}")
def queue_remove(bid: str, x_pin: str | None = Header(default=None)):
    """Remove a single booking (e.g. a test booking or a duplicate)."""
    _check_pin(x_pin)
    if not db.remove(bid):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.post("/api/queue/{bid}/{action}")
def queue_action(bid: str, action: str, x_pin: str | None = Header(default=None)):
    _check_pin(x_pin)
    if action not in ("start", "done"):
        raise HTTPException(400, "bad action")
    b = db.set_status(bid, "in_chair" if action == "start" else "done")
    if not b:
        raise HTTPException(404, "not found")
    return {"ok": True, "booking": b}


# ---------------------------------------------------------------- pages
@app.get("/")
def index():
    return FileResponse(PUBLIC / "index.html")


@app.get("/queue")
def queue_page():
    return FileResponse(PUBLIC / "queue.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(500)
async def err(_, exc):
    return JSONResponse({"detail": "Something went wrong"}, status_code=500)
