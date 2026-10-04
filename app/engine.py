"""Conversation protocol + Sugar's scripted front-desk voice.

Used in two places:
  * training/gen_dataset.py builds the synthetic SFT targets with `reply_for_state`
    (driven by the simulator's ground-truth slots, so labels are always correct).
  * app/main.py uses `ScriptedEngine` as the always-available fallback when Tinker
    inference is slow or unavailable. It re-extracts slots from the user's messages.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from menu import (COLOURS, LENGTHS, SERVICES, SHAPES, STYLES, TIMES, compute_total, naira)

SLOTS = ["name", "phone", "services", "style", "colours", "length", "shape", "notes", "time"]

HAND_SERVICES = {"gel_hands", "acrylic_full", "gelx", "biab", "press_on", "refill", "manicure"}


def needs_length(state: dict) -> bool:
    return any(SERVICES[s][2] for s in state.get("services") or [])


def needs_shape(state: dict) -> bool:
    return any(s in HAND_SERVICES for s in state.get("services") or [])


def next_slot(state: dict) -> str | None:
    for s in SLOTS:
        if s == "length" and state.get("services") and not needs_length(state):
            state.setdefault("length", "natural")
        if s == "shape" and state.get("services") and not needs_shape(state):
            state.setdefault("shape", "n/a")
        if s == "style" and state.get("services") and set(state["services"]) <= {"removal", "manicure", "pedicure"}:
            state.setdefault("style", "plain")
        if s == "colours" and state.get("services") and set(state["services"]) <= {"removal"}:
            state.setdefault("colours", ["None"])
        if not state.get(s):
            return s
    return None


# ---------------------------------------------------------------- protocol parsing
CHIPS_RE = re.compile(r"\[(chips|multi):\s*([^\]]+)\]\s*$", re.M)
ORDER_RE = re.compile(r"<order>\s*(\{.*?\})\s*</order>", re.S)


def parse_reply(text: str) -> dict[str, Any]:
    """Split a model/scripted message into display text, chips and order JSON."""
    out: dict[str, Any] = {"text": text, "chips": [], "multi": False, "order": None, "order_error": None}
    m = ORDER_RE.search(text)
    if m:
        try:
            out["order"] = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            out["order_error"] = str(e)
        text = text[: m.start()] + text[m.end():]
    elif "<order>" in text:
        out["order_error"] = "unterminated order block"
        text = text.split("<order>")[0]
    c = CHIPS_RE.search(text)
    if c:
        out["chips"] = [x.strip() for x in c.group(2).split("|") if x.strip()]
        out["multi"] = c.group(1) == "multi"
        text = text[: c.start()] + text[c.end():]
    out["text"] = text.strip()
    return out


def normalise_order(order: dict) -> dict:
    """Validate the model's order against the menu and recompute the price server-side."""
    services = [s for s in order.get("services") or [] if s in SERVICES]
    style = order.get("style") if order.get("style") in STYLES else "plain"
    length = order.get("length") if order.get("length") in LENGTHS else "natural"
    colours = order.get("colours") or []
    if isinstance(colours, str):
        colours = [colours]
    clean = {
        "name": str(order.get("name") or "").strip()[:60],
        "phone": str(order.get("phone") or "").strip()[:20],
        "services": services,
        "style": style,
        "colours": [str(c)[:30] for c in colours][:4],
        "length": length,
        "shape": str(order.get("shape") or "n/a")[:20],
        "notes": str(order.get("notes") or "None")[:200],
        "time": str(order.get("time") or "Right now (walk-in)")[:60],
    }
    clean["total"] = compute_total(services, style, length)
    clean["model_total"] = order.get("total")
    return clean


# ---------------------------------------------------------------- voice
def _first(name: str | None) -> str:
    return (name or "").split()[0] if name else ""


SERVICE_CHIPS = [SERVICES[k][0] for k in ["gel_hands", "acrylic_full", "gelx", "biab", "press_on", "refill", "manicure", "pedicure", "gel_toes", "removal"]]
STYLE_CHIPS = [v[0] for v in STYLES.values()]
LENGTH_CHIPS = [LENGTHS[k][0] for k in ["short", "medium", "long", "xl"]]
NOTE_CHIPS = ["No allergies", "Sensitive skin", "Allergic to acrylic", "I have a broken nail"]


def greeting(rng: random.Random) -> str:
    return rng.choice([
        "Hi love, welcome to Sugar Nails! 💅 Sugar is on a client right now, so I'll get you booked. What's your name?",
        "Welcome to Sugar Nails o! Sugar dey work on a client, but I'm here to sort you out. What's your name, my dear?",
        "Hello and welcome! 💖 Sugar's hands are busy right now, so let me book you in. Please, what's your name?",
        "Hey gorgeous, you're welcome to Sugar Nails! I'll take your booking while Sugar finishes up. What should I call you?",
    ])


def ask(slot: str, state: dict, rng: random.Random, retry: bool = False) -> str:
    n = _first(state.get("name"))
    if slot == "name":
        return rng.choice(["Sorry, I didn't catch your name. What should I call you?", "Abeg, what's your name?"])
    if slot == "phone":
        if retry:
            return rng.choice([
                "Hmm, that number no complete o. Please send a Nigerian number like 0803 123 4567.",
                "I think that number is missing some digits. Can you type it again? e.g. 0812 345 6789",
            ])
        return rng.choice([
            f"Nice to meet you, {n}! 😊 What's your phone number? Sugar will text you when it's your turn.",
            f"Lovely name, {n}! Abeg drop your phone number so we can reach you when you're next.",
            f"Welcome {n}! What number can we reach you on?",
        ])
    if slot == "services":
        txt = rng.choice([
            "Got it! What are we doing today? You can pick more than one.",
            "Perfect. Which service do you want? Pick as many as you like.",
            f"Thank you {n}! What would you like done today?",
        ])
        if retry:
            txt = "Sorry, I no catch that one. Which of these services do you want?"
        return txt + "\n[multi: " + " | ".join(SERVICE_CHIPS) + "]"
    if slot == "style":
        txt = rng.choice([
            "Sweet! Which style or design are you feeling?",
            "Nice choice! How do you want them styled?",
            "E go fine well well! Any design, or plain colour?",
        ])
        if retry:
            txt = "Which of these styles do you want?"
        return txt + "\n[chips: " + " | ".join(STYLE_CHIPS) + "]"
    if slot == "colours":
        txt = rng.choice([
            "Love it. What colour(s)? You can pick up to two.",
            "Okay o! Which colours are we using?",
            "Beautiful. Pick your colour(s):",
        ])
        return txt + "\n[multi: " + " | ".join(COLOURS) + "]"
    if slot == "length":
        txt = rng.choice([
            "How long do you want them? Long adds ₦2,000 and extra long adds ₦4,000.",
            "What length? (Long is +₦2,000, extra long +₦4,000)",
        ])
        if retry:
            txt = "Please choose a length:"
        return txt + "\n[chips: " + " | ".join(LENGTH_CHIPS) + "]"
    if slot == "shape":
        txt = rng.choice(["And the shape?", "Which shape do you like?", "Nice! What shape should Sugar file them?"])
        if retry:
            txt = "Please pick a shape:"
        return txt + "\n[chips: " + " | ".join(SHAPES) + "]"
    if slot == "notes":
        return rng.choice([
            "Any allergies, sensitive skin or anything Sugar should know?",
            "Before I forget, any allergies or special notes for Sugar?",
            "Anything Sugar should know? Allergies, broken nail, anything at all.",
        ]) + "\n[chips: " + " | ".join(NOTE_CHIPS) + "]"
    if slot == "time":
        return rng.choice([
            "Almost done! When do you want to come in?",
            "Last one: what time works for you?",
            "When should we expect you?",
        ]) + "\n[chips: " + " | ".join(TIMES) + "]"
    raise ValueError(slot)


def order_dict(state: dict) -> dict:
    o = {k: state.get(k) for k in SLOTS}
    o["total"] = compute_total(state["services"], state["style"], state["length"])
    return o


def summary(state: dict, rng: random.Random) -> str:
    o = order_dict(state)
    n = _first(o["name"])
    lines = [rng.choice([f"Perfect, {n}! Here's your booking:", f"Lovely! See your booking, {n}:", f"All set, {n}. Please check:"])]
    for s in o["services"]:
        lines.append(f"• {SERVICES[s][0]}: {naira(SERVICES[s][1])}")
    if STYLES[o["style"]][1]:
        lines.append(f"• {STYLES[o['style']][0]}: +{naira(STYLES[o['style']][1])}")
    if needs_length(o) and LENGTHS[o["length"]][1]:
        lines.append(f"• {LENGTHS[o['length']][0]} length: +{naira(LENGTHS[o['length']][1])}")
    det = []
    if o["colours"] and o["colours"] != ["None"]:
        det.append("Colours: " + ", ".join(o["colours"]))
    if o["shape"] != "n/a":
        det.append("Shape: " + o["shape"])
    if o["length"] != "natural":
        det.append("Length: " + LENGTHS[o["length"]][0])
    if det:
        lines.append(" · ".join(det))
    lines.append(f"Notes: {o['notes']} · Time: {o['time']}")
    lines.append(f"Total: {naira(o['total'])}")
    lines.append(rng.choice([
        "Tap Pay to lock your spot in Sugar's queue. 💅",
        "Once you pay, you're on Sugar's list sharp sharp!",
        "Pay below and I'll add you to the queue.",
    ]))
    return "\n".join(lines) + "\n<order>" + json.dumps(o, ensure_ascii=False) + "</order>"


def price_answer(services: list[str]) -> str:
    parts = [f"{SERVICES[s][0]} is {naira(SERVICES[s][1])}" for s in services]
    return "Good question! " + ", ".join(parts) + "."


def reply_for_state(state: dict, rng: random.Random, retry_slot: str | None = None, prefix: str = "") -> str:
    slot = next_slot(state)
    body = summary(state, rng) if slot is None else ask(slot, state, rng, retry=(retry_slot == slot))
    return (prefix + "\n" + body).strip() if prefix else body


# ---------------------------------------------------------------- rule-based extraction (fallback only)
SERVICE_KW = [
    (r"refill|infill|fill[- ]?in|re-?fill", "refill"),
    (r"gel[- ]?x|extension", "gelx"),
    (r"acrylic|acrylics|acrylik", "acrylic_full"),
    (r"biab|overlay|builder", "biab"),
    (r"press[- ]?on|presson", "press_on"),
    (r"pedicure|pedi\b|spa pedi", "pedicure"),
    (r"manicure|mani\b", "manicure"),
    (r"remov|soak[- ]?off|take off", "removal"),
    (r"gel.{0,20}(toe|leg|feet)|toe.{0,12}gel", "gel_toes"),
    (r"\bgel\b|gel polish", "gel_hands"),
]
STYLE_KW = [
    (r"french", "french"), (r"ombr|baby ?boomer", "ombre"), (r"chrome|glaz", "chrome"),
    (r"cat[- ]?eye", "cat_eye"), (r"marble", "marble"), (r"3d|flower", "flowers_3d"),
    (r"stone|charm|bling|crystal|diamond", "stones"), (r"art|design|paint|drawing", "nail_art"),
    (r"plain|simple|solid|no design|just colou?r", "plain"),
]
COLOUR_KW = [
    (r"nude|skin ?tone|beige", "Nude"), (r"milky|white", "Milky white"), (r"hot ?pink|fuchsia", "Hot pink"),
    (r"baby ?pink|light pink|\bpink\b", "Baby pink"), (r"\bred\b", "Red"), (r"wine|burgundy|maroon", "Wine"),
    (r"black", "Black"), (r"brown|chocolate|coffee", "Chocolate brown"), (r"gold", "Gold"), (r"silver", "Silver"),
    (r"green|emerald", "Emerald green"), (r"blue", "Sky blue"), (r"lilac|purple|lavender", "Lilac"), (r"coral|peach", "Coral"),
]
LENGTH_KW = [(r"extra[- ]?long|very long|xl|longest", "xl"), (r"\blong\b", "long"), (r"medium|mid", "medium"), (r"short", "short")]
PHONE_RE = re.compile(r"(\+?234|0)\s*[789][01]\d(?:[\s-]*\d){7}")


def _match(kws, text: str, multi=False):
    t = text.lower()
    found = []
    for pat, val in kws:
        if re.search(pat, t) and val not in found:
            found.append(val)
            if not multi:
                return val
            t = re.sub(pat, " ", t)
    return found if multi else None


def extract_name(text: str) -> str:
    t = re.sub(r"(?i)\b(hi|hello|hey|good (morning|afternoon|evening))\b[,!.]?", " ", text)
    t = re.sub(r"(?i)\b(my name is|my name na|i am|i'm|im|na|call me|it's|its|name is|this is)\b", " ", t)
    words = [w.strip(".,!?").capitalize() for w in t.split() if re.match(r"^[A-Za-z'-]+[.,!?]*$", w)]
    return " ".join(words[:3])


class ScriptedEngine:
    """Deterministic fallback. Replays the user messages to rebuild booking state."""

    def __init__(self, seed: int = 7):
        self.seed = seed

    def respond(self, user_msgs: list[str]) -> str:
        rng = random.Random(self.seed + len(user_msgs))
        if not user_msgs:
            return greeting(rng)
        state: dict = {}
        retry = None
        prefix = ""
        for i, msg in enumerate(user_msgs):
            prefix = ""
            retry = None
            low = msg.lower()
            slot = next_slot(state)
            if slot is None and re.search(r"change|edit|wrong|instead", low):
                prefix = "No wahala! Tell me what to change."
            if re.search(r"how much|price|cost", low):
                sv = _match(SERVICE_KW, msg, multi=True)
                if sv:
                    prefix = price_answer(sv)
                    continue
            # opportunistic slots
            sv = _match(SERVICE_KW, msg, multi=True)
            if sv and (slot == "services" or slot is None or len(sv) >= 1 and slot not in ("name", "notes", "time")):
                state["services"] = sv
            st = _match(STYLE_KW, msg)
            if st and slot not in ("name", "notes", "time"):
                state["style"] = st
            cl = _match(COLOUR_KW, msg, multi=True)
            if cl and slot not in ("name", "notes", "time"):
                state["colours"] = cl[:2]
            ln = _match(LENGTH_KW, msg)
            if ln and slot not in ("name", "notes", "time") and (slot in ("length", None) or state.get("services")):
                state["length"] = ln
            sh = next((s for s in SHAPES if s.lower() in low or (s == "Coffin" and "ballerina" in low)), None)
            if sh and slot not in ("name", "notes", "time"):
                state["shape"] = sh
            ph = PHONE_RE.search(msg)
            if ph:
                state["phone"] = re.sub(r"[\s-]", "", ph.group(0))
            # the slot we actually asked for
            if slot == "name":
                if re.fullmatch(r"(?i)\W*(hi|hello|hey|good (morning|afternoon|evening)( ma| sir)?|hi there)\W*|.*\b(want|wan|book|make my nails|do my nails)\b.*", msg) and not re.search(r"(?i)\b(i'm|i am|my name|call me)\b", msg):
                    continue  # greeting / intent only; still waiting for the name
                state["name"] = extract_name(msg) or msg.strip()[:30]
            elif slot == "phone" and not state.get("phone"):
                retry = "phone"
            elif slot == "services" and not state.get("services"):
                retry = "services"
            elif slot == "style" and not state.get("style"):
                retry = "style"
            elif slot == "colours" and not state.get("colours"):
                state["colours"] = [msg.strip()[:30]]
            elif slot == "length" and not state.get("length"):
                retry = "length"
            elif slot == "shape" and not state.get("shape"):
                retry = "shape"
            elif slot == "notes":
                state["notes"] = "None" if re.fullmatch(r"(?i)\s*(no|none|nope|nothing|no allergies|nothing o|i'm good|no o)\W*", msg) else msg.strip()[:200]
            elif slot == "time":
                key = re.sub(r"[^a-z ]", "", msg.lower()).split()
                state["time"] = next((t for t in TIMES if re.sub(r"[^a-z ]", "", t.lower().replace("(walk-in)", "")).split() == key), msg.strip()[:60])
        if next_slot(state) is None and not prefix and len(user_msgs) and re.search(r"\b(yes|ok|okay|sure|confirm|alright)\b", user_msgs[-1].lower()) and state.get("time") != user_msgs[-1].strip()[:60]:
            return "Great! Just tap the Pay button under your booking and you're in Sugar's queue. 💅"
        return reply_for_state(state, rng, retry_slot=retry, prefix=prefix)
