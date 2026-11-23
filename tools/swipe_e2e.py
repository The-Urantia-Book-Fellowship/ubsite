"""Gestures, end to end, in Chrome with a touch screen (ub.js gestOn; Tigran,
2026-11-23): with Settings' Gestures on, a finger drawn leftwards across the
text goes on as the page's transport bar does, and rightwards back, an arrow
coming in as the finger moves and filling in once the stroke counts.

Off by default, a swipe does nothing.  On: a section's page steps a section,
across a paper's edge too; the whole paper's page a paper; a part's page to
its first paper, by Foreword in Part I; a Bible chapter a chapter.  And
nothing for a vertical stroke, one at 45 degrees, a short one, one brought
back before the finger lifts, two fingers, one from the screen's edge, one on
a card, one with words selected, one with Settings open, a page zoomed in, or
where the book ends.  The arrow: none under 16 px, armed at the threshold,
the link's label in the interface's language, gone when the stroke is.  The
switch in Settings on a touch screen and not on a desk; a tap still brings
the running head; and while a recording plays the page is swapped, not
loaded, and the reading goes on.

    .venv/bin/python tools/swipe_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8150 with the visit counter off, and
leaves the dev server alone.  Not a gate, like preview_e2e.py.
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
PORT = "8150"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


AT = "location.pathname + location.hash"
ARROW = """() => { const a = document.querySelector('.swipe');
    if (!a || a.hidden) return null;
    const r = a.getBoundingClientRect();
    return { armed: a.classList.contains('armed'), back: a.classList.contains('back'),
             label: a.querySelector('.lbl').textContent, left: r.left, right: r.right }; }"""


def context(b, settings: dict | None = None, touch: bool = True):
    ctx = (b.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2)
           if touch else b.new_context(viewport={"width": 1280, "height": 900}))
    # A fresh context is a first visit, which the tour would meet (help.js).
    # The settings once, on the tab's first page: what a test sets after is
    # kept as it moves about.
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); if (!sessionStorage.getItem('seeded')) {"
                        " sessionStorage.setItem('seeded', '1'); localStorage.setItem('ub_settings', %s); } } catch (e) {}"
                        % json.dumps(json.dumps(settings or {})))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, (ctx.new_cdp_session(pg) if touch else None), errors


def go(pg, path: str) -> None:
    pg.goto(BASE + path)
    pg.wait_for_load_state("load")
    pg.wait_for_timeout(500)


def on_text(pg) -> tuple[float, float]:
    """A point in the middle of the window that is on the text, the page
    scrolled so that one is."""
    for _ in range(6):
        y = pg.evaluate("innerHeight / 2")
        if pg.evaluate("(y) => { const e = document.elementFromPoint(innerWidth / 2, y);"
                       " return !!e && !!e.closest('main article') && !e.closest('.pop, nav.transport'); }", y):
            return pg.evaluate("innerWidth / 2"), y
        pg.evaluate("scrollBy(0, 120)")
        pg.wait_for_timeout(100)
    return pg.evaluate("innerWidth / 2"), pg.evaluate("innerHeight / 2")


def touch(cdp, kind: str, pts: list[tuple[float, float]]) -> None:
    cdp.send("Input.dispatchTouchEvent",
             {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i + 1} for i, (x, y) in enumerate(pts)]})


def stroke(cdp, pg, x: float, y: float, dx: float, dy: float = 0, steps: int = 14,
           back_to: float | None = None, end: str = "touchEnd", fingers: int = 1) -> None:
    """A finger (or two, side by side) down at x, y, drawn by dx, dy in steps,
    and lifted; or brought back to back_to of the way first; or cancelled."""
    at = lambda f: [(x + dx * f + 40 * i, y + dy * f) for i in range(fingers)]
    touch(cdp, "touchStart", at(0))
    for i in range(1, steps + 1):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", at(i / steps))
    if back_to is not None:
        for i in range(1, 7):
            pg.wait_for_timeout(16)
            touch(cdp, "touchMove", at(1 - (1 - back_to) * i / 6))
    pg.wait_for_timeout(60)
    touch(cdp, end, [])


def settled(pg, want: str | None, was: str, ms: int = 4000) -> str:
    """Where the page is once a swipe has done what it does: at want, or,
    where nothing should happen, still at was after a while."""
    t = time.time()
    while time.time() - t < ms / 1000:
        pg.wait_for_timeout(150)
        try:
            pg.wait_for_load_state("load")
            here = pg.evaluate(AT)
        except Exception:
            continue
        if want is not None and here == want:
            return here
    return pg.evaluate(AT) if want is None else here


def swipe(cdp, pg, dx: float, want: str | None, say: str, **kw) -> None:
    was = pg.evaluate(AT)
    x, y = on_text(pg)
    stroke(cdp, pg, x + (110 if dx < 0 else -110), y, dx, **kw)
    here = settled(pg, want, was, 4000 if want else 1500)
    ok(here == (want or was), say + ": " + here)


def off_by_default(b) -> None:
    print("Off by default")
    ctx, pg, cdp, errors = context(b)
    go(pg, "/1:1")
    swipe(cdp, pg, -220, None, "a long leftward stroke on 1:1 leaves the page")
    ok(pg.evaluate(ARROW) is None, "and draws no arrow")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def sections(b) -> None:
    print("\nGestures on, a section to a page")
    ctx, pg, cdp, errors = context(b, {"gestures": True})
    go(pg, "/1:1")
    ok(pg.evaluate("getComputedStyle(document.documentElement).overscrollBehaviorX") == "none",
       "the browser's own swipe through the history held off")
    swipe(cdp, pg, -220, "/1:2", "1:1, a stroke to the left goes on a section")
    swipe(cdp, pg, 220, "/1:1", "and to the right back")
    swipe(cdp, pg, 220, "/1:0", "back again, to the paper's introduction")
    swipe(cdp, pg, 220, "/0:12", "and back across the paper's edge, to the Foreword's last section")
    go(pg, "/0:0")
    x, y = on_text(pg)
    touch(cdp, "touchStart", [(x - 110, y)])
    for i in range(1, 15):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x - 110 + 220 * i / 14, y)])
    pg.wait_for_timeout(80)
    ok(pg.evaluate(ARROW) is None, "at the book's start, no arrow back")
    touch(cdp, "touchEnd", [])
    ok(settled(pg, None, "/0:0", 1500) == "/0:0", "and nothing happens")

    print("\nThe arrow")
    go(pg, "/1:1")
    x, y = on_text(pg)
    x0 = x + 110
    touch(cdp, "touchStart", [(x0, y)])
    for d in (4, 8, 12, 15):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x0 - d, y)])
    pg.wait_for_timeout(80)
    ok(pg.evaluate(ARROW) is None, "none under 16 px")
    for d in (30, 50):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x0 - d, y)])
    pg.wait_for_timeout(80)
    a = pg.evaluate(ARROW)
    ok(a is not None and not a["armed"] and not a["back"] and a["right"] > 300,
       "at 50 px an arrow at the right, not yet armed: %s" % a)
    ok(a is not None and a["label"] == "Next section: 1:2", "labelled as the bar's ⏭ is: %s" % (a and a["label"]))
    for d in (70, 80, 90):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x0 - d, y)])
    pg.wait_for_timeout(80)
    a = pg.evaluate(ARROW)
    ok(a is not None and a["armed"], "armed at 78 px, a fifth of 390: %s" % a)
    for d in (60, 40):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x0 - d, y)])
    pg.wait_for_timeout(80)
    a = pg.evaluate(ARROW)
    ok(a is not None and not a["armed"], "brought back short of it, disarmed")
    touch(cdp, "touchEnd", [])
    ok(settled(pg, None, "/1:1", 1500) == "/1:1" and pg.evaluate(ARROW) is None,
       "lifted there, nothing happens and the arrow goes")
    touch(cdp, "touchStart", [(x - 110, y)])
    for i in range(1, 15):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x - 110 + 200 * i / 14, y)])
    pg.wait_for_timeout(80)
    a = pg.evaluate(ARROW)
    ok(a is not None and a["armed"] and a["back"] and a["left"] < 90 and a["label"] == "Previous section: 1:0",
       "to the right, armed at the left, labelled as ⏮: %s" % a)
    touch(cdp, "touchCancel", [])
    ok(settled(pg, None, "/1:1", 1500) == "/1:1" and pg.evaluate(ARROW) is None,
       "a touchcancel takes it away, and nothing happens")

    print("\nStrokes that are not swipes")
    swipe(cdp, pg, 0, None, "a vertical stroke", dy=-300)
    swipe(cdp, pg, -220, None, "one at 45 degrees", dy=-220)
    swipe(cdp, pg, -50, None, "a short one")
    swipe(cdp, pg, -220, None, "one brought back before the finger lifts", back_to=0.1)
    swipe(cdp, pg, -220, None, "two fingers", fingers=2)
    y = on_text(pg)[1]
    stroke(cdp, pg, 12, y, 220)
    ok(settled(pg, None, "/1:1", 1500) == "/1:1", "a stroke from the screen's left edge")
    stroke(cdp, pg, 378, y, -220)
    ok(settled(pg, None, "/1:1", 1500) == "/1:1", "and from its right edge")
    pg.evaluate("getSelection().selectAllChildren(document.querySelector('main article p.t[id]'))")
    swipe(cdp, pg, -220, None, "a stroke with words selected")
    pg.evaluate("getSelection().removeAllRanges()")
    pg.evaluate("document.querySelector('header .gear').click()")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("!!document.querySelector('dialog.settings[open]')"), "Settings open")
    swipe(cdp, pg, -220, None, "a stroke with Settings open")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
    pg.wait_for_timeout(300)
    if pg.evaluate("visualViewport.scale") > 1.01:
        swipe(cdp, pg, -220, None, "a stroke on a page zoomed in")
    else:
        print("  --   the page could not be zoomed here; not tried")
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 1})
    pg.wait_for_timeout(300)

    print("\nOn a card")
    go(pg, "/14:5")
    mark = pg.locator("[id='14:5.1'] a.fn[data-k='st']").first
    mark.scroll_into_view_if_needed()
    pg.evaluate("scrollBy(0, 200)")
    pg.wait_for_timeout(150)
    mark.tap()
    pg.wait_for_timeout(300)
    r = pg.evaluate("(() => { const r = document.querySelector('.pop .body').getBoundingClientRect();"
                    " return [r.left + r.width / 2, r.top + Math.min(r.height / 2, 60)]; })()")
    stroke(cdp, pg, r[0] + 110, r[1], -220)
    ok(settled(pg, None, "/14:5", 1500) == "/14:5", "a stroke on an open note's card is the card's")

    print("\nA tap is still a tap")
    go(pg, "/1:1")
    x, y = on_text(pg)
    pg.touchscreen.tap(x, y)
    pg.wait_for_timeout(400)
    ok(pg.evaluate("(() => { const h = document.querySelector('.runhead'); return !!h && !h.hidden; })()"),
       "a tap on a paragraph brings the running head")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def whole(b) -> None:
    print("\nWhole paper on")
    ctx, pg, cdp, errors = context(b, {"gestures": True, "whole": True})
    go(pg, "/1")
    swipe(cdp, pg, -220, "/2", "the whole of Paper 1, to the left the next paper")
    swipe(cdp, pg, 220, "/1", "to the right the one before")
    swipe(cdp, pg, 220, "/0", "and before that the Foreword")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def parts_and_bible(b) -> None:
    print("\nA part's page, and a Bible chapter")
    for fw, want in ((True, "/0:0"), (False, "/1:0")):
        ctx, pg, cdp, errors = context(b, {"gestures": True, "foreword": fw})
        go(pg, "/part/1")
        swipe(cdp, pg, 220, None, "Part I, Foreword in Part I %s: nothing to the right" % ("on" if fw else "off"))
        swipe(cdp, pg, -220, want, "and to the left its first paper")
        ok(not errors, "no script error: " + "; ".join(errors))
        ctx.close()
    ctx, pg, cdp, errors = context(b, {"gestures": True})
    go(pg, "/bible/Gen/2")
    swipe(cdp, pg, -220, "/bible/Gen/3", "Genesis 2, to the left chapter 3")
    swipe(cdp, pg, 220, "/bible/Gen/2", "to the right back")
    swipe(cdp, pg, 220, "/bible/Gen/1", "and back to chapter 1")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def russian(b) -> None:
    print("\nIn Russian")
    ctx, pg, cdp, errors = context(b, {"gestures": True, "lang": "ru"})
    go(pg, "/1:1")
    x, y = on_text(pg)
    touch(cdp, "touchStart", [(x + 110, y)])
    for i in range(1, 15):
        pg.wait_for_timeout(16)
        touch(cdp, "touchMove", [(x + 110 - 220 * i / 14, y)])
    pg.wait_for_timeout(80)
    a = pg.evaluate(ARROW)
    ok(a is not None and a["label"] == "Следующий раздел: 1:2", "the arrow's label: %s" % (a and a["label"]))
    touch(cdp, "touchCancel", [])
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def switch(b) -> None:
    print("\nThe switch in Settings")
    for touchy, say in ((True, "on a phone"), (False, "on a desk with no touch screen")):
        ctx, pg, cdp, errors = context(b, touch=touchy)
        go(pg, "/1:1")
        pg.evaluate("document.querySelector('header .gear').click()")
        pg.wait_for_timeout(300)
        shown = pg.evaluate("(() => { const i = document.querySelector('dialog.settings input[name=\"gestures\"]');"
                            " return !!i && i.closest('label').getClientRects().length > 0; })()")
        ok(shown == touchy, "Gestures %s %s" % ("shown" if touchy else "hidden", say))
        if touchy:
            ok(pg.evaluate("document.querySelector('dialog.settings input[name=\"gestures\"]').checked") is False,
               "and off")
        ctx.close()


def playing(b) -> None:
    print("\nWhile a recording plays, Follow along off")
    # With Follow along on, the default, a link followed while playing loads
    # its page, as the bar's own ⏭ does (listen.js roaming); off, the page is
    # swapped in and the reading goes on.  The swipe does as the bar does.
    ctx, pg, cdp, errors = context(b, {"gestures": True, "follow": False})
    go(pg, "/101:4")
    pg.wait_for_selector("p.t[id] > .stk > .playp", state="attached", timeout=15000)
    pg.evaluate("document.getElementById('101:4.2').scrollIntoView({block: 'center'})")
    pg.wait_for_timeout(200)
    at = pg.evaluate("(() => { const r = document.querySelector('[id=\"101:4.2\"] .playp').getBoundingClientRect();"
                     " return [r.right - 12, r.top + r.height / 2]; })()")
    pg.touchscreen.tap(*at)
    ok(pg.wait_for_function("() => { const p = document.querySelector('p.t.now'); return p && p.id === '101:4.2'; }",
                            timeout=8000) is not None, "the reading started at 101:4.2")
    pg.evaluate("window.__stay = 1")
    swipe(cdp, pg, -220, "/101:5", "a stroke to the left goes on to 101:5")
    ok(pg.evaluate("window.__stay === 1"), "the page swapped in, not loaded")
    ok(pg.evaluate("!!document.querySelector('.player')"), "and the player is still there, the reading going on")
    pg.evaluate("document.querySelector('.player .close') && document.querySelector('.player .close').click()")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        off_by_default(b)
        sections(b)
        whole(b)
        parts_and_bible(b)
        russian(b)
        switch(b)
        playing(b)
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
