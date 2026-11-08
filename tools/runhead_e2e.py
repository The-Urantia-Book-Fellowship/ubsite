"""The running head on demand, end to end, in Chrome with a touch screen
(ub.js tapHead, 2026-10-31): a tap on a paragraph shows it with that
paragraph's reference and the paper's head, a tap or two lines of scrolling
hides it, its gear opens Settings, its reference opens the Contents with the
paper being read in view and its mark is a link home, a tap while words are
selected does nothing, with Tap to turn the page on the top band shows it and the rest
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
        # A fresh context is a first visit, which the tour would meet (help.js).
        ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
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
        ok(pg.inner_text(".runhead .ref") == "101:4.3" and pg.evaluate("document.querySelector('.runhead .ref').tagName") == "BUTTON",
           "with the paragraph's reference, a button")
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

        print("Home and the Contents from the head")
        SHOWN = "document.querySelector('.rail').classList.contains('shown')"
        pg.tap("[id='101:4.4']")
        settle(pg)
        top0 = pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top")
        ok(pg.evaluate("document.querySelector('.runhead .home').getAttribute('href')") == "/"
           and pg.evaluate("!!document.querySelector('.runhead .home svg.logo')"), "the home link is the site's mark, to /")
        ok(not pg.evaluate(SHOWN), "the Contents folded, as a phone's page starts")
        pg.tap(".runhead .ref")
        settle(pg)
        ok(not shown(pg) and named(pg) == [], "a tap on the reference hides the head")
        ok(pg.evaluate(SHOWN) and pg.evaluate("document.querySelector('.railfold').getAttribute('aria-expanded')") == "true",
           "and opens the Contents")
        top = pg.evaluate("document.querySelector('.rail li.here').getBoundingClientRect().top")
        ok(abs(top - 844 / 6) < 40, "with the paper being read a sixth of the way down the screen: %.0f px" % top)
        ok(pg.evaluate(EN + "(document.querySelector('.rail li.here > details > summary'))").strip().startswith("101.")
           and pg.evaluate("document.querySelector('.rail li.here li.here a').getAttribute('href')") == "/101:4",
           "its sections under it, section 4 marked")
        ok(pg.evaluate("getComputedStyle(document.querySelector('.runhead .home .logo .flame')).fill") !=
           pg.evaluate("getComputedStyle(document.querySelector('.runhead .home .logo .book')).fill"),
           "the mark in its own colours, the flame not the book's")
        pg.go_back()
        settle(pg)
        ok("/101:4" in pg.url and not pg.evaluate(SHOWN), "Back stays on the page and folds the Contents again")
        top1 = pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top")
        ok(abs(top1 - top0) < 3, "and puts the paragraph back where it stood: %.0f px for %.0f" % (top1, top0))
        pg.go_forward()
        settle(pg)
        ok(pg.evaluate(SHOWN) and abs(pg.evaluate("document.querySelector('.rail li.here').getBoundingClientRect().top") - 844 / 6) < 40,
           "Forward opens them again at the paper")
        pg.click(".rail li.here li a[href='/101:5']")
        pg.wait_for_selector("[id='101:5.1']")
        settle(pg)
        pg.go_back()
        pg.wait_for_selector("[id='101:4.4']")
        settle(pg)
        ok(pg.evaluate(SHOWN), "Back from a section opened from the Contents finds them open")
        pg.go_back()
        settle(pg)
        ok("/101:4" in pg.url and not pg.evaluate(SHOWN), "and Back again folds them")

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
        top0 = pg.evaluate("document.getElementById('101:4.2').getBoundingClientRect().top")
        pg.tap(".runhead .ref")
        settle(pg)
        ok(not shown(pg) and pg.evaluate(SHOWN), "the reference opens the Contents on the whole paper's page")
        ok(pg.evaluate("[...document.querySelectorAll('.rail li.here li.here a')].map(a => a.getAttribute('href'))") == ["/101:4"],
           "which still mark section 4, the one left, not the introduction")
        pg.go_back()
        settle(pg)
        top1 = pg.evaluate("document.getElementById('101:4.2').getBoundingClientRect().top")
        ok(not pg.evaluate(SHOWN) and abs(top1 - top0) < 3,
           "Back folds the Contents and puts the paragraph back where it stood: %.0f px for %.0f" % (top1, top0))
        pg.go_forward()
        settle(pg)
        pg.evaluate("document.querySelector(\".rail li.here li a[href='/101:7']\").click()")
        settle(pg)
        ok(pg.evaluate("location.hash") == "#101:7" and pg.evaluate("document.getElementById('101:7').getBoundingClientRect().top") < 80,
           "a section tapped in the Contents is a place on the whole paper's page, scrolled to")
        pg.go_back()
        settle(pg)
        ok(pg.evaluate(SHOWN) and abs(pg.evaluate("document.querySelector('.rail li.here').getBoundingClientRect().top") - 844 / 6) < 40,
           "Back from it is the Contents again, at the paper, not section 4's top")
        pg.go_back()
        settle(pg)
        ok(not pg.evaluate(SHOWN) and abs(pg.evaluate("document.getElementById('101:4.2').getBoundingClientRect().top") - top0) < 3,
           "and Back again the paragraph where it stood")
        pg.evaluate("ubSettings.set('whole', false)")

        print("A reading path")
        pg.goto(BASE + "/i/humor/read")
        pg.wait_for_selector("main p.t[id]")
        pg.tap("main p.t[id] >> nth=0")
        settle(pg)
        pn = pg.evaluate(EN + "(document.querySelector('.runhead .pn'))")
        ok(shown(pg) and pn.startswith("Paper ") and " · " in pn, "names the paragraph's paper from the running head before it: " + pn)
        ok(pg.evaluate("getComputedStyle(document.querySelector('.runhead .au')).display") == "none", "with no author")
        pg.tap(".runhead .ref")
        settle(pg)
        ok(not shown(pg) and not errors, "with no Contents on the page, the reference only hides the head")

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

        print("A wide screen, the Contents folded away")
        ctx2 = b.new_context(viewport={"width": 1280, "height": 900})
        ctx2.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        pg2 = ctx2.new_page()
        pg2.on("pageerror", lambda e: errors.append(str(e)))
        pg2.goto(BASE + "/101:4")
        pg2.evaluate("ubSettings.set('rail', 'folded')")
        settle(pg2)
        ok(pg2.evaluate("document.documentElement.dataset.rail") == "folded", "folded by its setting")
        # A mouse's click shows it after a moment (ub.js DBL), which a
        # double-click's second press cancels (Tigran, 2026-11-08).
        pg2.click("[id='101:4.3']")
        settle(pg2)
        ok(not shown(pg2), "a mouse's click waits a moment")
        pg2.wait_for_timeout(400)
        ok(shown(pg2), "and then shows the head")
        pg2.click("[id='101:4.3']")
        settle(pg2)
        ok(not shown(pg2), "a click while it shows hides it at once")
        pg2.dblclick("[id='101:4.3']")
        pg2.wait_for_timeout(550)
        ok(not shown(pg2) and not pg2.evaluate("getSelection().isCollapsed") and
           not pg2.evaluate("document.querySelector('main .named')"),
           "a double-click selects a word, with no head and nothing tinted")
        pg2.keyboard.press("Control+x")
        settle(pg2)
        ok(pg2.evaluate("document.activeElement === document.querySelector('.find input') && "
                        "document.querySelector('.find input').value !== ''"),
           "Ctrl+X puts it in the search box")
        pg2.keyboard.press("Escape")
        settle(pg2)
        pg2.evaluate("getSelection().removeAllRanges()")
        pg2.click("[id='101:4.3']")
        pg2.wait_for_timeout(550)
        ok(shown(pg2), "a click on a paragraph shows the head")
        pg2.click(".runhead .ref")
        settle(pg2)
        ok(not shown(pg2) and pg2.evaluate("document.documentElement.dataset.rail") != "folded",
           "the reference unfolds the Contents and hides the head")
        ok(pg2.evaluate("document.querySelector('.railfold').getAttribute('aria-expanded')") == "true", "the fold button says so")
        pg2.evaluate("ubSettings.set('rail', 'open')")
        ctx2.close()

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
