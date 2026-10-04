"""Record a short mobile demo of a full booking + Sugar's queue, then build screenshots/demo.gif.

Usage: python tests/record_demo.py [base_url]
Needs ffmpeg. Long model waits are sped up so the GIF stays ~20s. It creates one test booking;
remove it afterwards with DELETE /api/queue/<id> (X-Pin). --encode-only re-encodes the last take.
"""
import json, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://localhost:8090")
OUT = Path(__file__).resolve().parent.parent / "screenshots" / "demo.gif"
TMP = Path("/tmp/sugar-demo"); TMP.mkdir(exist_ok=True)
W, H = 390, 844
marks = []          # (start, end) of model-wait periods, seconds since recording start


def main():
    if "--encode-only" in sys.argv:
        m = json.loads((TMP / "marks.json").read_text())
        return encode(m["marks"], m["total"], None)
    for f in TMP.glob("*.webm"): f.unlink()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, is_mobile=True, has_touch=True,
                            record_video_dir=str(TMP), record_video_size={"width": W, "height": H})
        page = ctx.new_page(); t0 = time.time()
        page.goto(BASE + "/"); page.evaluate("localStorage.clear()"); page.reload()
        page.wait_for_timeout(2600)                                     # landing
        page.locator("#chat").scroll_into_view_if_needed(); page.wait_for_timeout(900)

        def wait_reply(n):
            s = time.time() - t0
            page.wait_for_function(f"document.querySelectorAll('.bubble.bot').length > {n}", timeout=45000)
            marks.append((s + 0.6, time.time() - t0 - 0.2))
            page.wait_for_timeout(700)

        def say(text):
            n = page.locator(".bubble.bot").count()
            page.locator("#msg").press_sequentially(text, delay=28); page.press("#msg", "Enter"); wait_reply(n)

        def chip(*labels):
            n = page.locator(".bubble.bot").count()
            for l in labels:
                page.locator(".chips .chip", has_text=l).first.click(); page.wait_for_timeout(250)
            if page.locator(".chips .send-multi").count(): page.locator(".chips .send-multi").click()
            wait_reply(n)

        steps = [lambda: say("Hi, I be Tolu"), lambda: say("0805 123 4567"),
                 lambda: say("gel x, long almond, chrome"), lambda: say("baby pink"),
                 lambda: say("no allergies"), lambda: say("today evening")]
        extra = [lambda: say("long"), lambda: say("almond"), lambda: say("chrome"), lambda: say("none"), lambda: say("today evening")]
        for s in steps + extra:
            if page.locator(".order-card").count(): break
            s()
        page.wait_for_selector(".order-card", timeout=45000)
        page.locator(".order-card").scroll_into_view_if_needed(); page.wait_for_timeout(1800)   # summary
        page.locator(".order-card .pay").click(); page.wait_for_selector(".sheet-back.open"); page.wait_for_timeout(1400)
        page.click("#payNow"); page.wait_for_selector(".ticket", timeout=15000); page.wait_for_timeout(2600)  # success + ticket
        bid = None  # find it by diffing GET /api/queue before/after
        page.goto(BASE + "/queue"); page.wait_for_timeout(700)
        for d in "2580":
            page.locator("#pad button", has_text=d).first.click(); page.wait_for_timeout(150)
        page.wait_for_selector("#dash:not([hidden])"); page.wait_for_timeout(1800)
        page.locator("#next .qcard [data-act=start]").first.click(); page.wait_for_timeout(2200)
        total = time.time() - t0
        ctx.close(); b.close()
    (TMP / "marks.json").write_text(json.dumps({"marks": marks, "total": total}))
    print("raw seconds", round(total, 1), "waits", [(round(a, 1), round(b_, 1)) for a, b_ in marks], "booking", bid)

    encode(marks, total, bid)


def encode(marks, total, bid):
    video = next(TMP.glob("*.webm"))
    # piecewise speed: model waits at 10x, everything else at 1.6x
    segs, cur = [], 0.0
    for a, b_ in marks:
        if b_ - a < 0.5: continue
        segs.append((cur, a, 1.6)); segs.append((a, b_, 10.0)); cur = b_
    segs.append((cur, total + 1, 1.6))
    parts = [f"[0:v]trim={a:.2f}:{b_:.2f},setpts=(PTS-STARTPTS)/{sp}[v{i}]" for i, (a, b_, sp) in enumerate(segs)]
    concat = "".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[c]"
    fc = ";".join(parts + [concat, "[c]fps=12,scale=300:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-filter_complex", fc, str(OUT)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT)], capture_output=True, text=True).stdout.strip() or 0)
    print(json.dumps({"gif": str(OUT), "mb": round(OUT.stat().st_size / 1e6, 2), "seconds": round(dur, 1), "booking_id": bid}))


if __name__ == "__main__":
    main()
