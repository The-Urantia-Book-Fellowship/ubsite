"""The tour, end to end, in Chrome (static/help.js; Tigran, 2026-11-06): a
first visit to the home page is met by the welcome, whose "Open the book"
opens 1:1 with the tour going on from the entries beside the text, through
every step the page has, to Done, after which nothing comes again; a first
visit deep in the book is met by it too, and Skip ends it for good; the keys
move it; a control the page lacks is stepped over; Help's "Take the tour"
and "Show me" start it; the lit gear opens Settings over the dim; a note's
card opens clear of it; on a phone the folded index's line and the
contents' line are lit, and a tap on the lit contents keeps the tour; and in
Russian the cards are Russian.

    .venv/bin/python tools/help_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8133 with the visit counter off, and
leaves the dev server alone.  Not a gate, like runhead_e2e.py: tests/
test_help.py holds the static facts.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8133"
EN = "(el => { const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent; })"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def step(pg):
    return pg.evaluate("sessionStorage.getItem('ub_tour')")


def seen(pg):
    return pg.evaluate("localStorage.getItem('ub_tour')")


def card(pg):
    try:
        pg.wait_for_selector(".tour-card", timeout=10000)
    except Exception:
        # Say what the page holds, so that a timeout explains itself.
        print("  no card:", pg.evaluate("""() => ({ url: location.href, step: sessionStorage.getItem('ub_tour'),
            seen: localStorage.getItem('ub_tour'), tour: typeof window.ubTour,
            cards: [...document.querySelectorAll('.tour-card')].map(c => { const r = c.getBoundingClientRect();
              return [c.className, r.left, r.top, r.width, r.height]; }),
            dialog: !!document.querySelector('dialog[open]'), listening: document.body.classList.contains('listening') })"""))
        raise
    pg.wait_for_timeout(250)
    return pg.query_selector(".tour-card")


def title(pg):
    return pg.evaluate(EN, pg.query_selector(".tour-card h2")).strip()


def walk(pg):
    """Next through every step; the keys of the steps shown.  A button that
    navigates is clicked by the DOM (see the welcome): Playwright's own click is
    retried on the new page when a navigation detaches the button."""
    out = []
    for _ in range(14):
        pg.wait_for_timeout(300)
        k = step(pg)
        if not k:                      # Done or Skip let the step go: the tour is over
            break
        card(pg)
        out.append(k)
        go = pg.query_selector(".tour-card .go")
        if not go:
            break
        go.click()
    return out


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        errors: list[str] = []

        print("A first visit to the home page")
        ctx = b.new_context(viewport={"width": 1380, "height": 860})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        card(pg)
        ok(title(pg) == "Welcome", "the welcome")
        ok(pg.evaluate(EN, pg.query_selector(".tour-card .go")).strip() == "Open the book", "offers to open the book")
        ok(seen(pg) is None, "not yet seen")
        pg.evaluate("document.querySelector('.tour-card .go').click()")
        pg.wait_for_url(BASE + "/1:1", timeout=5000)
        ok(seen(pg) == "seen", "seen once the welcome is answered")
        steps = walk(pg)
        ok(steps[0] == "chips", f"the tour goes on at the entries: {steps}")
        # 127.0.0.1 is a secure context, so the worker can run and the cloud is shown.
        ok("cloud" in steps and "listen" in steps and "notes" in steps, f"the cloud, the ▶ and a note among them: {steps}")
        ok(steps[-1] == "help", "and ends at the ?")
        ok(step(pg) is None and not pg.query_selector(".tour-card"), "Done ends it and lets the step go")
        pg.reload()
        pg.wait_for_timeout(1200)
        ok(not pg.query_selector(".tour-card"), "nothing comes again")
        ok(not errors, f"no script errors: {errors[:3]}")
        pg.close()

        print("A first visit deep in the book, Skip, and the keys")
        pg = b.new_context(viewport={"width": 1380, "height": 860}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/101:4")
        card(pg)
        ok(title(pg) == "Welcome", "the welcome on a deep link")
        ok(pg.evaluate(EN, pg.query_selector(".tour-card .go")).strip() == "Begin", "Begin, on a page of the book")
        pg.keyboard.press("ArrowRight")
        card(pg)
        ok(step(pg) == "chips", "→ begins")
        pg.keyboard.press("ArrowRight")
        card(pg)
        ok(step(pg) == "cited", "→ goes on")
        pg.keyboard.press("ArrowLeft")
        card(pg)
        ok(step(pg) == "chips", "← goes back")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)
        ok(step(pg) is None and not pg.query_selector(".tour-card") and seen(pg) == "seen", "Escape ends it for good")
        pg.close()

        print("Controls the page lacks")
        pg = b.new_context(viewport={"width": 1380, "height": 860}).new_page()
        pg.goto(BASE + "/1:1")
        pg.evaluate("ubSettings.set('listen', false); ubSettings.set('index', false)")
        pg.reload()
        card(pg)
        pg.click(".tour-card .go")
        steps = walk(pg)
        ok("listen" not in steps and "chips" not in steps and "cited" not in steps, f"Listening and the index off: {steps}")
        pg.close()

        print("Help's buttons")
        pg = b.new_context(viewport={"width": 1380, "height": 860}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.evaluate("1")
        pg.goto(BASE + "/help")
        pg.wait_for_timeout(900)
        ok(not pg.query_selector(".tour-card"), "no tour on the Help page itself")
        for ch in ("text", "index", "moving", "listening", "notes", "keys"):
            ok(pg.query_selector(f"#{ch}") is not None, f"chapter {ch}")
        pg.evaluate("document.querySelector('.showme[data-tour=\"listen\"]').click()")
        pg.wait_for_url(BASE + "/1:1", timeout=5000)
        card(pg)
        ok(step(pg) == "listen", "Show me on Listening lights the ▶")
        ok(pg.query_selector(".tour-card .prev") is not None, "with Back alive")
        pg.goto(BASE + "/101:4")
        pg.wait_for_timeout(300)
        pg.click(".top a.help")             # by the link, as a reader comes: the referrer is the page
        pg.wait_for_url(BASE + "/help", timeout=5000)
        pg.wait_for_timeout(300)
        pg.evaluate("document.querySelector('.tourstart').click()")
        pg.wait_for_url(BASE + "/101:4", timeout=5000)
        card(pg)
        ok(title(pg) == "Welcome", "Take the tour goes back to the page the reader came from")
        pg.keyboard.press("Escape")
        pg.close()

        print("The lit gear, and a note's card")
        pg = b.new_context(viewport={"width": 1380, "height": 860}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/1:1")
        pg.evaluate("sessionStorage.setItem('ub_tour', 'gear'); localStorage.setItem('ub_tour', 'seen')")
        pg.reload()
        card(pg)
        ok(step(pg) == "gear", "at the gear")
        pg.click(".top .gear")
        pg.wait_for_timeout(300)
        ok(pg.evaluate("document.querySelector('dialog.settings').open"), "the lit gear opens Settings")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        ok(not pg.evaluate("document.querySelector('dialog.settings').open") and step(pg) == "gear", "Settings closes, the tour stays")
        pg.evaluate("ubTour.start('notes')")
        card(pg)
        mark = pg.query_selector("main a.fn")
        mark.click()
        pg.wait_for_timeout(300)
        ok(pg.query_selector(".pop") is not None, "the note's card opens under the lit mark")
        clear = pg.evaluate("""() => { const p = document.querySelector('.pop').getBoundingClientRect();
            const el = document.elementFromPoint(p.left + p.width / 2, p.top + 12);
            return !!el && !!el.closest('.pop'); }""")
        ok(clear, "and stands clear of the dimming")
        pg.close()

        print("A phone")
        ctx = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/1:1")
        card(pg)
        pg.tap(".tour-card .go")
        card(pg)
        ok(step(pg) == "chips", "the entries' step")
        lit = pg.evaluate("""() => { const r = document.querySelector('.tour-ring').getBoundingClientRect();
            const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return el ? (el.closest('.afold') ? 'afold' : el.closest('.a') ? 'a' : el.className) : ''; }""")
        ok(lit in ("afold", "a"), f"the folded line or the box is lit: {lit}")
        inside = pg.evaluate("""() => { const r = document.querySelector('.tour-card').getBoundingClientRect();
            return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight; }""")
        ok(inside, "the card is inside the window")
        pg.evaluate("ubTour.start('contents')")
        card(pg)
        pg.tap(".rail .railfold")
        pg.wait_for_timeout(300)
        ok(step(pg) == "contents" and pg.query_selector(".tour-card") is not None, "a tap on the lit contents keeps the tour")
        pg.close()

        print("In Russian")
        pg = b.new_context(viewport={"width": 1380, "height": 860}).new_page()
        pg.goto(BASE + "/1:1")
        pg.evaluate("ubSettings.set('lang', 'ru')")
        pg.reload()
        card(pg)
        ru = pg.evaluate("() => { const h = document.querySelector('.tour-card h2'); return getComputedStyle(h.querySelector('x-ru')).display !== 'none' && getComputedStyle(h.querySelector('x-en')).display === 'none'; }")
        ok(ru, "the card is Russian")
        ok(title(pg) == "Welcome", "and carries the English too")
        pg.close()

        ok(not errors, f"no script errors: {errors[:3]}")
        b.close()
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


def main() -> int:
    env = dict(os.environ, UB_VISITS="off")
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "ubsite.app:app", "--host", "127.0.0.1", "--port", "8133",
                            "--log-level", "warning"], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    sys.exit(main())
