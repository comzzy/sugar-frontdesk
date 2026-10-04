"""End-to-end test: chat -> order -> (test) payment -> queue -> Start/Done, with screenshots.

Usage: python tests/e2e.py [base_url]
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
import os
SHOTS = Path(os.environ.get("E2E_SHOTS") or Path(__file__).resolve().parent.parent / "screenshots")
SHOTS.mkdir(exist_ok=True)
PIN = "2580"


def bot_count(page):
    return page.locator(".bubble.bot").count()


def say(page, text):
    n = bot_count(page)
    page.fill("#msg", text)
    page.press("#msg", "Enter")
    page.wait_for_function(f"document.querySelectorAll('.bubble.bot').length > {n}", timeout=45000)
    page.wait_for_timeout(500)
    return page.locator(".bubble.bot").last.inner_text()


def chip(page, *labels):
    n = bot_count(page)
    for l in labels:
        page.locator(".chips .chip", has_text=l).first.click()
    if page.locator(".chips .send-multi").count():
        page.locator(".chips .send-multi").click()
    page.wait_for_function(f"document.querySelectorAll('.bubble.bot').length > {n}", timeout=45000)
    page.wait_for_timeout(600)
    return page.locator(".bubble.bot").last.inner_text()


def book(page, script, tag):
    page.goto(BASE + "/#book")
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_timeout(1200)
    page.locator("#chat").scroll_into_view_if_needed()
    for kind, *args in script:
        out = say(page, args[0]) if kind == "say" else chip(page, *args)
        print(f"[{tag}] {kind} {args} -> {out[:90]!r}")
        if page.locator(".order-card").count():
            break
    page.wait_for_selector(".order-card", timeout=45000)
    return page


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        results = {}
        for label, vp, mobile in [("desktop", {"width": 1440, "height": 900}, False), ("mobile", {"width": 390, "height": 844}, True)]:
            ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(SHOTS / f"{label}-01-hero.png"))
            page.locator("#menu").scroll_into_view_if_needed(); page.wait_for_timeout(1400)
            page.screenshot(path=str(SHOTS / f"{label}-02-menu.png"))
            page.locator("#styles").scroll_into_view_if_needed(); page.wait_for_timeout(1400)
            page.screenshot(path=str(SHOTS / f"{label}-03-styles.png"))
            if mobile:
                script = [("say", "Hello, I wan book"), ("say", "call me Blessing"), ("say", "0813 555 2041"),
                          ("say", "abeg I wan do gel x, long coffin, french tip"), ("say", "nude and milky white"),
                          ("say", "no allergies o"), ("say", "by 4pm today")]
                # free-typed Pidgin; fall back to chips if the model asks something else
                extra = [("say", "long"), ("say", "coffin"), ("say", "french tips"), ("say", "none"), ("say", "4pm today")]
                script += extra
            else:
                script = [("say", "Chioma Okafor"), ("say", "08031234567"), ("chip", "Acrylic Full Set", "Spa Pedicure"),
                          ("chip", "Chrome / glazed"), ("chip", "Baby pink", "Silver"), ("chip", "Long"), ("chip", "Almond"),
                          ("chip", "No allergies"), ("chip", "Today, evening")]
            book(page, script, label)
            page.locator(".order-card").scroll_into_view_if_needed(); page.wait_for_timeout(800)
            page.screenshot(path=str(SHOTS / f"{label}-04-chat-order.png"))
            page.locator(".order-card .pay").click()
            page.wait_for_selector(".sheet-back.open"); page.wait_for_timeout(900)
            page.screenshot(path=str(SHOTS / f"{label}-05-payment.png"))
            page.click("#payNow")
            page.wait_for_selector(".ticket", timeout=15000); page.wait_for_timeout(900)
            page.screenshot(path=str(SHOTS / f"{label}-06-paid-ticket.png"))
            pos = page.locator("#tPos").inner_text()
            print(label, "ticket position:", pos)
            results[label] = {"position": pos, "errors": errors}
            ctx.close()

        # Sugar's dashboard
        for label, vp, mobile in [("desktop", {"width": 1440, "height": 900}, False), ("mobile", {"width": 390, "height": 844}, True)]:
            ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)
            page = ctx.new_page()
            page.goto(BASE + "/queue"); page.wait_for_timeout(900)
            page.screenshot(path=str(SHOTS / f"{label}-07-queue-pin.png"))
            for d in PIN:
                page.locator("#pad button", has_text=d).first.click()
            page.wait_for_selector("#dash:not([hidden])"); page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / f"{label}-08-queue.png"), full_page=True)
            if not mobile:
                page.locator("#next .qcard [data-act=start]").first.click(); page.wait_for_timeout(1500)
                page.screenshot(path=str(SHOTS / f"{label}-09-queue-started.png"), full_page=True)
                assert page.locator("#chair .qcard").count() == 1
                page.locator("#chair .qcard [data-act=done]").first.click(); page.wait_for_timeout(1500)
                assert page.locator("#done .qcard").count() >= 1
                page.screenshot(path=str(SHOTS / f"{label}-10-queue-done.png"), full_page=True)
            ctx.close()
        b.close()
        print("RESULTS", results)


if __name__ == "__main__":
    main()
