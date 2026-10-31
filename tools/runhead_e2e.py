"""The running head on demand, end to end, in Chrome with a touch screen
(ub.js tapHead, 2026-10-31): a tap on a paragraph shows it with that
paragraph's reference and the paper's head, a tap or two lines of scrolling
hides it, its gear opens Settings, a tap while words are selected does
nothing, with Tap to turn the page on the top band shows it and the rest
turns, the whole paper's page names the paper and not the section, a reading
path names the paper of the paragraph, and a 1955 card and the head are never
up together.

    .venv/bin/python tools/runhead_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8132 with the visit counter off, and
leaves the dev server alone.  Not a gate, like offline_e2e.py: tests/
test_runhead.py holds the static facts.
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
BASE = "http://127.0.0.1:8132"
# An element's words as a reader of English has them (tools/offline_e2e.py EN).
EN = "(el => { const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent; })"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


# A y where the finger lands on a paragraph's text and nothing else, scanning
# the window from `frm` to `to` at x: not a link, a fold's line or the index.
TEXT_Y = """([frm, to]) => { const step = frm < to ? 8 : -8;
    for (let y = frm; step > 0 ? y < to : y > to; y += step) {
      const el = document.elementFromPoint(195, y);
      if (el && el.closest('p.t[id]') && !el.closest('a, button, .pop')) return y; } }"""


def text_y(pg, frm: float, to: float):
    return pg.evaluate(TEXT_Y, [frm, to])


def shown(pg) -> bool:
    return pg.evaluate("() => { const h = document.querySelector('.runhead'); return !!h && !h.hidden; }")


def named(pg) -> list[str]:
    return pg.evaluate("() => [...document.querySelectorAll('p.t.named')].map(p => p.id)")


def settle(pg) -> None:
    pg.wait_for_timeout(150)


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        ctx = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844},
                            device_scale_factor=2)
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("A section's page, the references off")
        pg.goto(BASE + "/101:4")
        pg.evaluate("ubSettings.set('paranum', false)")
        ok(not shown(pg), "no head until a tap")
        pg.tap("[id='101:4.3']")
        settle(pg)
        ok(shown(pg), "a tap on a paragraph shows the head")
        ok(pg.inner_text(".runhead .ref") == "101:4.3" and pg.evaluate("document.querySelector('.runhead .ref').tagName") == "SPAN",
           "with the paragraph's reference, as text")
        ok(pg.evaluate(EN + "(document.querySelector('.runhead .pn'))") == "Paper 101The Real Nature of Religion",
           "and the paper's number and title")
        ok(pg.evaluate("getComputedStyle(document.querySelector('.runhead .tt'), '::before').content") == '" – "',
           "with the book's dash drawn between them")
        ok(pg.inner_text(".runhead .au") == "Melchizedek", "and its author")
        ok(named(pg) == ["101:4.3"], "the paragraph alone is tinted")
        pg.tap("[id='101:4.3']")
        settle(pg)
        ok(not shown(pg) and named(pg) == [], "a second tap hides it")

        pg.tap("[id='101:4.3']")
        settle(pg)
        pg.evaluate("scrollBy(0, 12)")
        settle(pg)
        ok(shown(pg), "a few pixels of scrolling keep it")
        pg.evaluate("scrollBy(0, 300)")
        settle(pg)
        ok(not shown(pg), "two lines of scrolling hide it")

        pg.tap("[id='101:4.4']")
        settle(pg)
        pg.keyboard.press("Escape")
        settle(pg)
        ok(not shown(pg), "Escape hides it")

        pg.tap("[id='101:4.4']")
        settle(pg)
        y = pg.evaluate("scrollY")
        pg.tap(".runhead .set")
        settle(pg)
        ok(pg.evaluate("document.querySelector('dialog.settings').open"), "its gear opens Settings")
        ok(not shown(pg), "and the head goes as it opens")
        pg.keyboard.press("Escape")
        settle(pg)
        ok(not pg.evaluate("document.querySelector('dialog.settings').open") and pg.evaluate("scrollY") == y,
           "Settings closes and the page has not moved")

        pg.evaluate("getSelection().selectAllChildren(document.getElementById('101:4.5'))")
        pg.tap("[id='101:4.4']")
        settle(pg)
        ok(not shown(pg), "a tap while words are selected does nothing")
        pg.evaluate("getSelection().removeAllRanges()")

        print("Tap to turn the page on")
        pg.evaluate("ubSettings.set('tappage', true)")
        # The top of the window on a paragraph's text, so that a tap in the
        # band lands on the text, not on a fold's line, which takes no tap.
        pg.evaluate("scrollTo(0, scrollY + document.getElementById('101:4.3').getBoundingClientRect().top + 10)")
        settle(pg)
        y = pg.evaluate("scrollY")
        low = text_y(pg, 824, 432)
        ok(low is not None, "a paragraph's text in the lower half of the screen")
        pg.touchscreen.tap(195, low or 700)
        settle(pg)
        ok(pg.evaluate("scrollY") > y + 200 and not shown(pg), "a tap low on the screen turns the page, with no head")
        pg.evaluate("scrollTo(0, scrollY + document.getElementById('101:4.3').getBoundingClientRect().top + 10)")
        settle(pg)
        pg.touchscreen.tap(195, 20)
        settle(pg)
        ok(shown(pg) and pg.inner_text(".runhead .ref") == "101:4.3",
           "a tap in the band at the top shows it, naming the first paragraph on the screen")
        pg.touchscreen.tap(195, 20)
        settle(pg)
        ok(not shown(pg), "and again hides it")
        pg.evaluate("ubSettings.set('tappage', false)")

        print("The paragraph an address arrived at")
        hit = "() => [...document.querySelectorAll('p.t.hit')].map(p => p.id)"
        pg.goto(BASE + "/0:1.2")
        ok(pg.evaluate(hit) == ["0:1.2"], "a section's page opens with it marked")
        pg.tap("[id='0:1.3']")
        settle(pg)
        ok(shown(pg) and named(pg) == ["0:1.3"] and pg.evaluate(hit) == [], "a tap on another lets go of it, and names that one")
        pg.tap("[id='0:1.3']")
        settle(pg)
        ok(not shown(pg) and named(pg) == [] and pg.evaluate(hit) == [], "and the second tap leaves nothing marked")

        print("The whole paper")
        pg.evaluate("ubSettings.set('whole', true)")
        pg.goto(BASE + "/0#0:1.2")
        pg.wait_for_selector("article.whole")
        settle(pg)
        ok(pg.evaluate(hit) == ["0:1.2"], "the whole paper's page marks the paragraph arrived at")
        pg.tap("[id='0:1.2']")
        settle(pg)
        ok(shown(pg) and named(pg) == ["0:1.2"] and pg.evaluate(hit) == [], "a tap on it lets go of the mark and names it")
        pg.tap("[id='0:1.2']")
        settle(pg)
        ok(not shown(pg) and named(pg) == [] and pg.evaluate(hit) == [], "and the second tap leaves it plain")
        pg.goto(BASE + "/101#101:4")
        pg.wait_for_selector("article.whole")
        pg.tap("[id='101:4.2']")
        settle(pg)
        ok(shown(pg) and pg.evaluate(EN + "(document.querySelector('.runhead .pn'))") == "Paper 101The Real Nature of Religion"
           and pg.inner_text(".runhead .ref") == "101:4.2", "names the paper, not the section")
        pg.evaluate("ubSettings.set('whole', false)")

        print("A reading path")
        pg.goto(BASE + "/i/humor/read")
        pg.wait_for_selector("main p.t[id]")
        pg.tap("main p.t[id] >> nth=0")
        settle(pg)
        pn = pg.evaluate(EN + "(document.querySelector('.runhead .pn'))")
        ok(shown(pg) and pn.startswith("Paper ") and " · " in pn, "names the paragraph's paper from the running head before it: " + pn)
        ok(pg.evaluate("getComputedStyle(document.querySelector('.runhead .au')).display") == "none", "with no author")

        print("A 1955 card")
        RING = "a.fn:not([data-k='st']):not([data-k='tn'])"
        pg.goto(BASE + "/0:1")
        pg.wait_for_selector(RING)
        pg.tap("[id='0:1.2']")
        settle(pg)
        ok(shown(pg), "the head up")
        pg.tap(RING + " >> nth=0")
        settle(pg)
        ok(pg.evaluate("!!document.querySelector('.pop')") and not shown(pg), "the card opens and the head goes")
        # A paragraph the card does not cover, tapped to close it.
        away = text_y(pg, 60, 824)
        ok(away is not None, "a paragraph clear of the card")
        pg.touchscreen.tap(195, away or 100)
        settle(pg)
        ok(not pg.evaluate("!!document.querySelector('.pop')") and not shown(pg),
           "the tap that closes the card does not bring the head")

        ok(not errors, "no script error: " + "; ".join(errors))
        b.close()
    return 1 if fails else 0


def main() -> int:
    env = dict(os.environ, UB_VISITS="off")
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-m", "uvicorn", "ubsite.app:app",
                            "--host", "127.0.0.1", "--port", "8132", "--log-level", "warning"],
                           cwd=ROOT, env=env)
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
