"""Capture a desktop walkthrough of the live site as timestamped CDP screencast frames.

Writes /tmp/sugar-desk/frames/*.jpg, frames.json and marks.json for tests/edit_desktop.py.
The queue page gets the PIN via sessionStorage (never typed on screen) and hides every
order card except the example customer's, so no other customer data is captured.
"""
import base64, json, os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://sugar-nails-nine.vercel.app"
PIN = os.environ.get("QUEUE_PIN", "2580")
NAME = "Ada"
OUT = Path("/tmp/sugar-desk"); FR = OUT / "frames"
FR.mkdir(parents=True, exist_ok=True)
for f in FR.glob("*.jpg"): f.unlink()
frames, marks = [], {}


def mark(k): marks[k] = time.time()


def screencast(page):
    s = page.context.new_cdp_session(page)
    def on_frame(ev):
        i = len(frames); p = FR / f"{i:06d}.jpg"
        p.write_bytes(base64.b64decode(ev["data"]))
        frames.append((ev["metadata"]["timestamp"], str(p)))
        try: s.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception: pass
    s.on("Page.screencastFrame", on_frame)
    s.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 1})
    return s


HIDE_OTHERS = """
(() => {
  // every order card is hidden by default; only the example customer's card is let through
  const css = () => { if (document.documentElement && !document.getElementById('keep-css')) { const st = document.createElement('style'); st.id = 'keep-css'; st.textContent = '.qcard:not([data-keep]) { display: none !important; }'; document.documentElement.appendChild(st); } };
  const keep = () => document.querySelectorAll('.qcard:not([data-keep])').forEach(c => {
    if ((c.querySelector('.qname') || {}).textContent === 'ADA_NAME') c.dataset.keep = '1'; });
  new MutationObserver(() => { css(); keep(); }).observe(document, { subtree: true, childList: true }); css();
})();
""".replace("ADA_NAME", NAME)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-device-scale-factor=1"])
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(BASE + "/"); page.evaluate("localStorage.clear()")
        sc = screencast(page)
        page.reload(wait_until="domcontentloaded"); mark("hero")
        page.wait_for_timeout(11000)
        page.locator("#menu").scroll_into_view_if_needed(); mark("menu"); page.wait_for_timeout(4500)
        page.locator("#styles").scroll_into_view_if_needed(); mark("styles"); page.wait_for_timeout(4500)
        page.locator("#chat").scroll_into_view_if_needed(); mark("chat"); page.wait_for_timeout(2500)

        turn = [0]
        def say(text):
            n = page.locator(".bubble.bot").count(); k = turn[0]; turn[0] += 1
            mark(f"t{k}_type"); page.locator("#msg").press_sequentially(text, delay=55)
            page.press("#msg", "Enter"); mark(f"t{k}_sent")
            page.wait_for_function(f"document.querySelectorAll('.bubble.bot').length > {n}", timeout=45000)
            mark(f"t{k}_reply"); page.wait_for_timeout(1800); mark(f"t{k}_end")
            print(k, text, "->", page.locator(".bubble.bot").last.inner_text()[:100].replace("\n", " / "))

        script = ["Hi, I'm Ada", "08000000000", "abeg I wan do gel x, long coffin, french tip",
                  "nude and milky white", "no allergies", "4pm today"]
        extra = ["long", "coffin", "french tips", "none", "4pm today"]
        for t in script + extra:
            if page.locator(".order-card").count(): break
            say(t)
        page.wait_for_selector(".order-card", timeout=45000)
        page.locator(".order-card").scroll_into_view_if_needed(); mark("summary"); page.wait_for_timeout(5000)
        marks["total"] = page.locator(".order-card").inner_text()
        page.locator(".order-card .pay").click(); page.wait_for_selector(".sheet-back.open"); mark("sheet"); page.wait_for_timeout(4000)
        page.click("#payNow"); mark("paynow"); page.wait_for_selector(".ticket", timeout=15000); mark("ticket"); page.wait_for_timeout(5000)
        marks["position"] = page.locator("#tPos").inner_text()
        mark("ticket_end"); sc.send("Page.stopScreencast")

        q = ctx.new_page()
        q.add_init_script(f"sessionStorage.setItem('sugar-pin', {json.dumps(PIN)});" + HIDE_OTHERS)
        q.bring_to_front()
        sc2 = screencast(q)
        q.goto(BASE + "/queue"); q.wait_for_selector("#dash:not([hidden])"); q.wait_for_timeout(700); mark("dash")
        q.wait_for_timeout(5500)
        q.locator("#next .qcard [data-act=start]").first.click(); mark("start"); q.wait_for_timeout(4500)
        q.locator("#chair .qcard [data-act=done]").first.click(); mark("done"); q.wait_for_timeout(6000)
        mark("end"); sc2.send("Page.stopScreencast")
        ctx.close(); b.close()
    (OUT / "frames.json").write_text(json.dumps(frames)); (OUT / "marks.json").write_text(json.dumps(marks, indent=1))
    print("frames", len(frames), "span", round(frames[-1][0] - frames[0][0], 1), "position", marks.get("position"))


if __name__ == "__main__":
    main()
