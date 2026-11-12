"""Paragraph previews at a tap, and a finger's drag on a card, end to end, in
Chrome with a touch screen (ub.js pvLink, popTouch; both mended 2026-11-12,
from what Tigran saw on his phone).

With Whole paper off and on: a tap on a reference in a note's card shows the
paragraphs in a card over it and the page stays, the same tap closes it, and
the reference at the preview's head goes there.  With Whole paper on the tap
went to the place, the Whole paper handler having rewritten the link first.

And on a note long enough to scroll: a drag scrolls its words; a stroke on
past either end leaves the page where it was, with the stylesheet's
containment and without it (a browser that did not honour it); a drag begun on
the strip above the words, the ×'s, leaves it; and a drag under the card moves
the page, which is the page's.

    .venv/bin/python tools/preview_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8134 with the visit counter off, and
leaves the dev server alone.  Not a gate, like runhead_e2e.py: tests/
test_previews.py holds the static facts.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = "8134"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


# Where the note's words stand, how far they have scrolled, and the page.
STATE = """() => { const b = document.querySelector('.pop .body');
    return { top: Math.round(b.scrollTop), max: Math.round(b.scrollHeight - b.clientHeight), win: Math.round(scrollY) }; }"""
BOX = """() => { const r = document.querySelector('.pop .body').getBoundingClientRect();
    return [r.left, r.top, r.width, r.height]; }"""
AT = "location.pathname + location.hash"


def drag(cdp, pg, x: float, y: float, dy: float, steps: int = 12) -> None:
    """A finger down at x, y, moved by dy in steps, rested and lifted: a drag
    and no fling.  Real touches, so that the browser makes the scroll of them
    as it does of a finger's, and the page's handlers see them."""
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for i in range(1, steps + 1):
        pg.wait_for_timeout(16)
        cdp.send("Input.dispatchTouchEvent",
                 {"type": "touchMove", "touchPoints": [{"x": x, "y": y + dy * i / steps, "id": 1}]})
    pg.wait_for_timeout(120)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(400)


def note(pg, section: str, para: str):
    """The page of the section, the study note at the paragraph open in its
    card, and the box of its words."""
    pg.goto(BASE + "/" + section)
    pg.wait_for_timeout(500)
    mark = pg.locator("[id='%s'] a.fn[data-k='st']" % para).first
    mark.scroll_into_view_if_needed()
    pg.evaluate("scrollBy(0, 200)")      # the mark in the window's upper half, its card on the screen
    pg.wait_for_timeout(150)
    mark.tap()
    pg.wait_for_timeout(300)
    return pg.evaluate(BOX)


def one(b, whole: bool) -> None:
    ctx = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844},
                        device_scale_factor=2)
    settings = {"preview": True}
    if whole:
        settings["whole"] = True
    # A fresh context is a first visit, which the tour would meet (help.js).
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    say = "Whole paper on: " if whole else "Whole paper off: "

    print("\nA reference in a note's card, " + say.rstrip(": "))
    note(pg, "14:5", "14:5.1")
    here = pg.evaluate(AT)
    ok(here == ("/14#14:5" if whole else "/14:5"), say + "the page is the reader's unit, " + here)
    ref = pg.locator(".pop.st a[href*='30:4.1-8']").first
    ref.tap()
    pg.wait_for_timeout(1200)
    ok(pg.evaluate(AT) == here, say + "a tap on 30:4.1-8 leaves the page where it is")
    ok(pg.evaluate("(() => { const e = document.querySelector('.pop.pv'); return !!e && e.querySelector('.pvref a').textContent === '30:4.1-8'"
                   " && e.querySelectorAll('.body p:not(.pvref)').length === 8 && e.querySelectorAll('sup.pvn').length === 8; })()"),
       say + "and shows its eight paragraphs in a card, each with its number")
    ok(pg.evaluate("!!document.querySelector('.pop.st')"), say + "the note's card stays under it")
    ref.tap()
    pg.wait_for_timeout(400)
    ok(pg.evaluate("!document.querySelector('.pop.pv') && !!document.querySelector('.pop.st')") and pg.evaluate(AT) == here,
       say + "the same tap again closes the preview alone")
    ref.tap()
    pg.wait_for_timeout(900)
    ok(pg.evaluate("!!document.querySelector('.pop.pv')"), say + "and a third shows it again, the link once tapped")
    pg.locator(".pop.pv .pvref a").tap()
    pg.wait_for_timeout(1500)
    ok(pg.evaluate(AT) == ("/30#30:4.1-8" if whole else "/30:4.1-8"), say + "the reference at its head goes there, " + pg.evaluate(AT))

    print("\nA drag on a long note's card, " + say.rstrip(": "))
    left, top, width, height = note(pg, "14:1", "14:1.9")
    x, y = left + width / 2, top + height / 2
    was = pg.evaluate(STATE)
    ok(was["max"] > 300 and was["top"] == 0, say + "the note scrolls, %d px of it" % was["max"])
    drag(cdp, pg, x, y + 60, -150)
    st = pg.evaluate(STATE)
    ok(st["top"] > 100 and st["win"] == was["win"], say + "a drag up scrolls its words and not the page")
    drag(cdp, pg, x, y + 100, -1500, steps=40)
    st = pg.evaluate(STATE)
    ok(st["max"] - st["top"] <= 1 and st["win"] == was["win"], say + "one stroke on past the end stops at the end, the page still")
    drag(cdp, pg, x, y + 60, -150)
    ok(pg.evaluate(STATE)["win"] == was["win"], say + "a new stroke at the end leaves the page")
    # A browser that did not honour the containment: the handler alone.
    pg.evaluate("document.querySelector('.pop .body').style.overscrollBehavior = 'auto'")
    drag(cdp, pg, x, y + 60, -150)
    ok(pg.evaluate(STATE)["win"] == was["win"], say + "and with the stylesheet's containment taken away")
    drag(cdp, pg, x, y - 60, 150)
    st = pg.evaluate(STATE)
    ok(st["max"] - st["top"] > 100 and st["win"] == was["win"], say + "a drag down scrolls the words back")
    drag(cdp, pg, x, y - 100, 1500, steps=40)
    drag(cdp, pg, x, y - 60, 150)
    st = pg.evaluate(STATE)
    ok(st["top"] == 0 and st["win"] == was["win"], say + "a stroke on past the top leaves the page, without the containment too")
    drag(cdp, pg, x, top - 12, 150)
    ok(pg.evaluate(STATE)["win"] == was["win"], say + "a drag begun on the strip above the words leaves the page")
    drag(cdp, pg, x, top + height + 40, -150)
    ok(pg.evaluate(STATE)["win"] > was["win"] + 100, say + "a drag begun under the card moves the page, as ever")
    ok(pg.evaluate("!!document.querySelector('.pop.st')"), say + "and the card is still open")

    ok(not errors, say + "no script error: " + "; ".join(errors))
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        one(b, False)
        one(b, True)
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (the manifest a 404), so that no page
# registers the worker and fetches the copy, 48 MB to each fresh context
# (tools/runhead_e2e.py NO_COPY).
NO_COPY = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main() -> int:
    env = dict(os.environ, UB_VISITS="off")
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", NO_COPY,
                            str(ROOT / "var" / "no-offline-copy"), PORT], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
