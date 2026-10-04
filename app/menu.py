"""Sugar Nails menu, prices (NGN) and the shared system prompt.

Single source of truth used by the web app, the scripted fallback engine,
the synthetic dataset generator and the evaluator.
"""
from __future__ import annotations

SALON = "Sugar Nails"

# id -> (label, price, is_extension)
SERVICES: dict[str, tuple[str, int, bool]] = {
    "gel_hands": ("Gel Polish (hands)", 8000, False),
    "gel_toes": ("Gel Polish (toes)", 7000, False),
    "acrylic_full": ("Acrylic Full Set", 18000, True),
    "gelx": ("Gel-X Extensions", 20000, True),
    "biab": ("BIAB Overlay", 14000, False),
    "press_on": ("Custom Press-Ons", 12000, True),
    "refill": ("Acrylic Refill", 12000, True),
    "manicure": ("Classic Manicure", 5000, False),
    "pedicure": ("Spa Pedicure", 9000, False),
    "removal": ("Removal (gel/acrylic)", 3000, False),
}

# id -> (label, add-on price)
STYLES: dict[str, tuple[str, int]] = {
    "plain": ("Plain / solid colour", 0),
    "french": ("Classic French tips", 3000),
    "ombre": ("Ombre / baby boomer", 4000),
    "chrome": ("Chrome / glazed", 3500),
    "cat_eye": ("Cat-eye", 3500),
    "marble": ("Marble", 4000),
    "nail_art": ("Hand-painted nail art", 5000),
    "stones": ("Rhinestones & charms", 3000),
    "flowers_3d": ("3D flowers", 5000),
}

COLOURS = [
    "Nude", "Milky white", "Baby pink", "Hot pink", "Red", "Wine",
    "Black", "Chocolate brown", "Gold", "Silver", "Emerald green", "Sky blue",
    "Lilac", "Coral",
]

# id -> (label, surcharge on extension services)
LENGTHS: dict[str, tuple[str, int]] = {
    "natural": ("Natural length", 0),
    "short": ("Short", 0),
    "medium": ("Medium", 0),
    "long": ("Long", 2000),
    "xl": ("Extra long", 4000),
}

SHAPES = ["Square", "Squoval", "Round", "Oval", "Almond", "Coffin", "Stiletto"]

TIMES = ["Right now (walk-in)", "Today, afternoon", "Today, evening", "Tomorrow, morning", "Tomorrow, afternoon"]

PHONE = "+234 803 000 0000"  # placeholder salon line
ADDRESS = "Lekki Phase 1, Lagos"


def compute_total(services: list[str], style: str | None, length: str | None) -> int:
    total = sum(SERVICES[s][1] for s in services if s in SERVICES)
    if style in STYLES:
        total += STYLES[style][1]
    if length in LENGTHS and any(SERVICES[s][2] for s in services if s in SERVICES):
        total += LENGTHS[length][1]
    return total


def naira(n: int) -> str:
    return f"\u20a6{n:,}"


def _menu_text() -> str:
    lines = ["SERVICES (id: name, price):"]
    for k, (lbl, p, ext) in SERVICES.items():
        lines.append(f"- {k}: {lbl}, {naira(p)}{' (extension)' if ext else ''}")
    lines.append("STYLES (id: name, add-on):")
    for k, (lbl, p) in STYLES.items():
        lines.append(f"- {k}: {lbl}, +{naira(p)}")
    lines.append("LENGTHS (id: name, surcharge only if an extension service is booked):")
    for k, (lbl, p) in LENGTHS.items():
        lines.append(f"- {k}: {lbl}, +{naira(p)}")
    lines.append("SHAPES: " + ", ".join(SHAPES))
    lines.append("COLOURS: " + ", ".join(COLOURS))
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You are the front desk of {SALON}, Sugar's nail studio in Lagos. Sugar is busy doing nails, so you book customers for her.
Speak warmly like a Lagos front desk: friendly English with light Pidgin, short messages, one question at a time.
Collect in order: name, phone number, service(s), style, colour(s), length, shape, allergies or notes, preferred time.
When it helps, end a message with quick-reply options on their own line like: [chips: A | B | C]
When you have everything, summarise the booking with the total and end with the order on its own line as:
<order>{{"name": str, "phone": str, "services": [service ids], "style": style id, "colours": [str], "length": length id, "shape": str, "notes": str, "time": str, "total": int}}</order>
Total = sum of services + style add-on + length surcharge (only when an extension service is booked).
{_menu_text()}"""
