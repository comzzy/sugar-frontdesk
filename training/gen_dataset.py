"""Generate a synthetic multi-turn SFT dataset in Sugar's front-desk voice.

A customer simulator samples a ground-truth booking (the "goal") and talks to the
front desk in varied Nigerian English / Pidgin, sometimes tapping quick-reply chips,
sometimes typing free text, volunteering several details at once, giving a bad phone
number, asking prices, or changing their mind. The assistant side is written from
the ground truth, so every target (including the final <order> JSON and total) is correct.

Output: training/data/train.jsonl and training/data/eval.jsonl, one conversation per line:
  {"id": ..., "goal": {...}, "messages": [{"role": ..., "content": ...}, ...]}
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from engine import (ask, greeting, needs_length, needs_shape, next_slot, price_answer,  # noqa: E402
                    reply_for_state, summary)
from menu import COLOURS, LENGTHS, SERVICES, SHAPES, STYLES, SYSTEM_PROMPT, TIMES  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"

FIRST = ["Chioma", "Tolu", "Adaeze", "Funke", "Blessing", "Amaka", "Zainab", "Kemi", "Ifeoma", "Bisola", "Nneka",
         "Halima", "Temi", "Ngozi", "Yetunde", "Precious", "Esther", "Damilola", "Hauwa", "Oluchi", "Simi", "Joy",
         "Favour", "Aisha", "Bukola", "Ebere", "Mercy", "Lola", "Uche", "Rukayat", "Teniola", "Gift", "Ada", "Jumoke",
         "Fatima", "Chinwe", "Busayo", "Ifeoluwa", "Ruth", "Somto", "Mariam", "Debby", "Kiki", "Tobi", "Jennifer"]
LAST = ["Okafor", "Adeyemi", "Bello", "Eze", "Okonkwo", "Balogun", "Nwosu", "Abubakar", "Ogunleye", "Obi",
        "Lawal", "Chukwu", "Afolabi", "Ibrahim", "Uzor", "Adebayo", "Musa", "Okeke", "Danjuma", "Oyelaran"]

SERVICE_WORDS = {
    "gel_hands": ["gel polish", "gel on my hands", "just gel", "gel", "gel polish for fingers"],
    "gel_toes": ["gel on my toes", "toe gel", "gel for my legs", "gel polish on toes"],
    "acrylic_full": ["acrylic", "full set acrylic", "acrylic nails", "fixing nails (acrylic)", "full acrylic set"],
    "gelx": ["gel-x", "gel x extensions", "gelx", "gel extensions"],
    "biab": ["BIAB", "builder gel overlay", "biab on my natural nails", "overlay"],
    "press_on": ["press-ons", "press on nails", "custom press ons", "presson set"],
    "refill": ["refill", "acrylic refill", "infill", "fill my acrylic"],
    "manicure": ["manicure", "normal manicure", "mani", "classic manicure"],
    "pedicure": ["pedicure", "spa pedicure", "pedi", "pedicure for my feet"],
    "removal": ["removal", "take off my old acrylic", "soak off", "remove my old gel"],
}
STYLE_WORDS = {
    "plain": ["plain", "just plain colour", "simple, no design", "solid colour"],
    "french": ["french tips", "french", "classic french", "french tip abeg"],
    "ombre": ["ombre", "baby boomer", "ombré fade"],
    "chrome": ["chrome", "glazed donut chrome", "glazed", "chrome finish"],
    "cat_eye": ["cat eye", "cat-eye", "that cat eye magnetic one"],
    "marble": ["marble", "marble design", "marble effect"],
    "nail_art": ["nail art", "hand painted design", "some design", "drawings on them"],
    "stones": ["stones", "rhinestones", "charms and stones", "bling bling"],
    "flowers_3d": ["3d flowers", "flower design 3D", "3d flower art"],
}
COLOUR_WORDS = {
    "Nude": ["nude", "skin tone"], "Milky white": ["milky white", "white"], "Baby pink": ["baby pink", "light pink"],
    "Hot pink": ["hot pink", "fuchsia"], "Red": ["red"], "Wine": ["wine", "burgundy"], "Black": ["black"],
    "Chocolate brown": ["chocolate brown", "brown"], "Gold": ["gold"], "Silver": ["silver"],
    "Emerald green": ["emerald green", "green"], "Sky blue": ["sky blue", "blue"], "Lilac": ["lilac", "lavender"],
    "Coral": ["coral", "peach"],
}
LENGTH_WORDS = {"short": ["short", "short abeg", "keep am short"], "medium": ["medium", "mid length", "not too long"],
                "long": ["long", "make them long", "long please"], "xl": ["extra long", "very long o", "XL"]}
NOTES = [("None", ["no", "none", "nothing o", "no allergies", "No allergies", "I'm good"])] * 6 + [
    ("Sensitive skin", ["Sensitive skin", "my skin is a bit sensitive", "sensitive skin pls"]),
    ("Allergic to acrylic", ["Allergic to acrylic", "acrylic dey scratch my skin"]),
    ("Broken nail on left thumb", ["I have a broken nail on my left thumb", "my left thumb nail broke"]),
    ("Prefers no cutting of cuticles", ["please don't cut my cuticles", "no cutting cuticle abeg"]),
    ("Coming with her daughter", ["I'm coming with my daughter", "my daughter go follow me come"]),
    ("Allergic to latex gloves", ["I'm allergic to latex", "latex gloves dey worry me"]),
]
FREE_TIMES = ["by 4pm today", "around 2 o'clock", "Saturday morning", "tomorrow by 10am", "after work, like 6pm",
              "now now", "this evening", "Friday afternoon", "any time tomorrow", "11am"]
OPENERS = ["Hi", "Hello", "Good afternoon", "Good morning ma", "Hey", "Hi, I want to do my nails",
           "Hello, I wan book", "Hi there", "Good evening", "Please I want to make my nails"]
FILLERS_PRE = ["", "", "", "I want ", "I'll do ", "Abeg ", "Let me do ", "I go do ", "Can I get "]
FILLERS_POST = ["", "", "", " please", " abeg", " o", " pls", " 🙏", " thanks"]


def maybe_typo(rng, s):
    if rng.random() < 0.12 and len(s) > 4:
        i = rng.randrange(1, len(s) - 1)
        return s[:i] + s[i + 1:]
    return s


def phone_str(rng, digits):
    f = rng.random()
    if f < 0.4:
        return digits
    if f < 0.7:
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    return "+234" + digits[1:]


def sample_goal(rng):
    svc_pool = list(SERVICES)
    weights = [10, 4, 10, 6, 6, 5, 4, 4, 6, 3]
    services = [rng.choices(svc_pool, weights)[0]]
    if rng.random() < 0.35:
        extra = rng.choice([s for s in ["pedicure", "gel_toes", "removal", "manicure"] if s not in services])
        if extra == "removal":
            services.insert(0, extra)
        else:
            services.append(extra)
    st = {"services": services}
    goal = {"name": rng.choice(FIRST) + (" " + rng.choice(LAST) if rng.random() < 0.5 else ""),
            "phone": "0" + rng.choice(["803", "806", "813", "816", "703", "706", "810", "814", "903", "905", "802", "808", "812", "701", "902", "907"]) + "".join(str(rng.randrange(10)) for _ in range(7)),
            "services": services}
    if set(services) <= {"removal", "manicure", "pedicure"}:
        goal["style"] = "plain"
    else:
        goal["style"] = rng.choice(list(STYLES))
    goal["colours"] = ["None"] if set(services) <= {"removal"} else rng.sample(COLOURS, rng.choice([1, 1, 2]))
    goal["length"] = rng.choice(["short", "medium", "long", "long", "xl"]) if needs_length(st) else "natural"
    goal["shape"] = rng.choice(SHAPES) if needs_shape(st) else "n/a"
    note = rng.choice(NOTES)
    goal["notes"] = note[0]
    goal["_notes_say"] = rng.choice(note[1])
    if rng.random() < 0.55:
        goal["time"] = rng.choice(TIMES)
        goal["_time_say"] = goal["time"] if rng.random() < 0.6 else goal["time"].lower().replace(",", "").replace("(walk-in)", "").strip()
    else:
        goal["time"] = rng.choice(FREE_TIMES)
        goal["_time_say"] = goal["time"]
    return goal


def say_slot(rng, slot, goal, chip_ok=True):
    """What the customer types to provide `slot`."""
    chip = chip_ok and rng.random() < 0.4
    if slot == "name":
        n = goal["name"] if rng.random() < 0.6 else goal["name"].split()[0]
        goal["name"] = n  # the name actually given is the ground truth
        return rng.choice([n, f"My name is {n}", f"I'm {n}", f"Na {n}", f"call me {n}", n.lower()])
    if slot == "phone":
        return rng.choice(["", "", "it's ", "my number na ", "", "this one: "]) + phone_str(rng, goal["phone"])
    if slot == "services":
        if chip:
            return ", ".join(SERVICES[s][0] for s in goal["services"])
        words = [rng.choice(SERVICE_WORDS[s]) for s in goal["services"]]
        return maybe_typo(rng, rng.choice(FILLERS_PRE) + " and ".join(words) + rng.choice(FILLERS_POST))
    if slot == "style":
        if chip:
            return STYLES[goal["style"]][0]
        return maybe_typo(rng, rng.choice(["", "", "I want ", "let's do ", "make it "]) + rng.choice(STYLE_WORDS[goal["style"]]) + rng.choice(FILLERS_POST))
    if slot == "colours":
        if chip:
            return ", ".join(goal["colours"])
        ws = [rng.choice(COLOUR_WORDS[c]) for c in goal["colours"]]
        return rng.choice(["", "", "", "I like ", "mix "]) + " and ".join(ws) + rng.choice(FILLERS_POST)
    if slot == "length":
        return LENGTHS[goal["length"]][0] if chip else rng.choice(LENGTH_WORDS[goal["length"]])
    if slot == "shape":
        s = goal["shape"]
        return s if chip else rng.choice([s.lower(), f"{s.lower()} shape", f"{s} pls", f"make am {s.lower()}"])
    if slot == "notes":
        return goal["_notes_say"]
    if slot == "time":
        return goal["_time_say"]
    raise ValueError(slot)


def volunteer_extra(rng, slot, goal, state):
    """Sometimes the customer packs more details into one message."""
    if slot == "services" and goal["style"] != "plain" and rng.random() < 0.3:
        extra = [("style", rng.choice(STYLE_WORDS[goal["style"]]))]
        if goal["length"] != "natural" and rng.random() < 0.6:
            extra.append(("length", rng.choice(LENGTH_WORDS[goal["length"]][:1])))
        if goal["shape"] != "n/a" and rng.random() < 0.6:
            extra.append(("shape", goal["shape"].lower()))
        return extra
    if slot == "length" and goal["shape"] != "n/a" and rng.random() < 0.3:
        return [("shape", goal["shape"].lower())]
    if slot == "colours" and goal["length"] != "natural" and rng.random() < 0.15:
        return [("length", rng.choice(LENGTH_WORDS[goal["length"]][:1]))]
    return []


def build_conversation(rng, idx):
    goal = sample_goal(rng)
    state: dict = {}
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "assistant", "content": greeting(rng)}]
    # opener
    op = rng.choice(OPENERS)
    if rng.random() < 0.25:
        op = f"{rng.choice(['Hi', 'Hello', 'Good afternoon'])}, I'm {goal['name']}"
        state["name"] = goal["name"]
        msgs.append({"role": "user", "content": op})
        msgs.append({"role": "assistant", "content": reply_for_state(state, rng)})
    else:
        msgs.append({"role": "user", "content": op})
        msgs.append({"role": "assistant", "content": rng.choice([
            "Hi! You're welcome 💖 What's your name, please?", "Hello dear! Before anything, what's your name?",
            "Welcome o! Wetin be your name?", "Hi love! What should I call you?"])})
    bad_phone = rng.random() < 0.1
    price_q = rng.random() < 0.1
    guard = 0
    while (slot := next_slot(state)) is not None and guard < 20:
        guard += 1
        if slot == "phone" and bad_phone:
            bad_phone = False
            msgs.append({"role": "user", "content": goal["phone"][:rng.randrange(5, 9)]})
            msgs.append({"role": "assistant", "content": ask("phone", state, rng, retry=True)})
            continue
        if price_q and slot in ("services", "style"):
            price_q = False
            qs = rng.sample(list(SERVICES), rng.choice([1, 2]))
            q = rng.choice(["how much is ", "how much be ", "what's the price for ", "abeg how much for "]) + " and ".join(rng.choice(SERVICE_WORDS[s]) for s in qs) + "?"
            msgs.append({"role": "user", "content": q})
            msgs.append({"role": "assistant", "content": reply_for_state(state, rng, prefix=price_answer(qs))})
            continue
        text = say_slot(rng, slot, goal)
        state[slot] = goal[slot]
        for s2, w in volunteer_extra(rng, slot, goal, state):
            text += rng.choice([", ", " ", ". "]) + w
            state[s2] = goal[s2]
        msgs.append({"role": "user", "content": text})
        msgs.append({"role": "assistant", "content": reply_for_state(state, rng)})
    # occasional change after summary
    if rng.random() < 0.1 and goal["colours"] != ["None"]:
        newc = rng.choice([c for c in COLOURS if c not in goal["colours"]])
        msgs.append({"role": "user", "content": rng.choice(["abeg change the colour to ", "actually make it ", "can I change colour to "]) + rng.choice(COLOUR_WORDS[newc])})
        state["colours"] = [newc]
        goal["colours"] = [newc]
        msgs.append({"role": "assistant", "content": "No wahala, I've updated it!\n" + summary(state, rng)})
    clean_goal = {k: v for k, v in goal.items() if not k.startswith("_")}
    return {"id": f"conv-{idx:04d}", "goal": clean_goal, "messages": msgs}


def main(n_train=360, n_eval=40):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2026)
    for name, n, off in [("train", n_train, 0), ("eval", n_eval, 10000)]:
        with open(OUT / f"{name}.jsonl", "w") as f:
            for i in range(n):
                f.write(json.dumps(build_conversation(rng, off + i), ensure_ascii=False) + "\n")
        print("wrote", name, n)


if __name__ == "__main__":
    main()
