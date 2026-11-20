"""The translations' folds as one state, end to end, in Chrome (ub.js trAll,
settings.py KEPT `tropen`; Tigran, 2026-11-20: "Folding or unfolding a single
paragraph's translations should affect all paragraphs and this state should
be preserved globally").

Where the window has no room for the translations in columns, a tap on any
paragraph's fold opens them under every paragraph, and a tap again folds them
all; the line tapped stays where it stood on the screen, the index shown or
folded (on a phone with the index folded a fold has no box of its own); and
every page of the text then loads as the reader left them: Continue reading,
his report of the bug as he gave it, with Whole paper off and on; a paragraph
come to from the index; a tab chosen in one fold is every fold's.  Columns
come with the folds open and draw none of them, and the folds come back open.
With the folds shut a search's hit in a translation opens its one paragraph's,
and the reading its; with them open the hit's is at its own translation and
the reading shuts none.  The window's top inside a fold: Continue reading
names that paragraph, and not the next.  A browser that keeps nothing still
opens them all; where the translations cannot be had the folds stay shut, and
the one tapped says why.  Help's example of a fold is on its page, and no
control.  The longest paper, 30, whole, timed.  And a page loaded again by
Back or a reload comes back at the line it was left at, the folds open or in
columns, where the browser alone would put it paragraphs on.

    .venv/bin/python tools/trfold_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8148 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate.
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
PORT = 8148
BASE = f"http://127.0.0.1:{PORT}"
fails: list[str] = []
TICKED = "urantia-ru uf-ru"


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, js: str, ms: int = 8000) -> bool:
    """Whether `js` comes true within `ms` (polled: CLAUDE.md trap 41)."""
    end = time.time() + ms / 1000
    while time.time() < end:
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(50)
    return bool(pg.evaluate(js))


# The page's folds: those that show a translation the reader ticked, how many
# are open and drawn, whether the page is in columns, and any fold's words
# drawn under columns.
FOLDS = """() => {
  const all = [...document.querySelectorAll('main .tf[data-has]')].filter(tf => tf.querySelector('.trfold').textContent.trim());
  return {n: all.length, open: all.filter(tf => tf.classList.contains('open')).length,
          drawn: all.filter(tf => tf.querySelector('.tr:not([hidden]) :is(p.rt, .gap)')).length,
          shown: all.filter(tf => tf.querySelector('.tr:not([hidden]) p.rt')).length,
          cols: !!document.querySelector('main article.cmp'),
          under: document.querySelectorAll('main article.cmp .tf .tr').length}; }"""
ALL_OPEN = "(() => { const f = (%s)(); return f.n > 0 && f.open === f.n && f.shown === f.n; })()" % FOLDS
ALL_SHUT = "(() => { const f = (%s)(); return f.n > 0 && f.open === 0; })()" % FOLDS
STORED = "() => JSON.parse(localStorage.getItem('ub_settings') || '{}')"
# Where an element's top stands in the window.
TOP = "(q) => { const e = document.querySelector(q); return e ? e.getBoundingClientRect().top : null; }"
# The paragraph whose fold, open, stands across height y of the window,
# found apart from ub.js foldOver.
ACROSS = """(y) => { for (const row of document.querySelectorAll('main .grid > .row')) {
  const tr = row.querySelector(':scope > .tf.open > .tr'); if (!tr) continue;
  const r = tr.getBoundingClientRect(); if (r.height && r.top <= y && r.bottom > y) return row.querySelector('p.t[id]').id; }
  return null; }"""


def fresh(b, settings: dict | None = None, phone: bool = True, w: int = 390, h: int = 844, block: bool = False):
    """A browser of its own, a phone's by default, with `settings` stored once
    (not at every page, which would undo a tap) and the tour seen."""
    ctx = (b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2)
           if phone else b.new_context(viewport={"width": w, "height": h}))
    seed = json.dumps(dict({"translations": TICKED}, **(settings or {})))
    ctx.add_init_script(
        "try { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');"
        " localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } } catch (e) {}" % json.dumps(seed)
        # A browser that keeps nothing: what it is told to keep is refused.
        + (" Storage.prototype.setItem = function () { throw new DOMException('no', 'SecurityError'); };" if block else ""))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, errors


def tap_fold(pg, q: str) -> tuple[float, float]:
    """A finger on the fold's line `q`, where it stands, the page not moved
    to it first (Playwright's own tap would; trap 57): its top before.  The
    page brought to it as a reader's finger would, which lets go of a place
    still held (ub.js placeHold, arriveTouched)."""
    pg.evaluate("(q) => { const b = document.querySelector(q); const r = b.getBoundingClientRect();"
                " if (r.top < 80 || r.bottom > innerHeight - 120) { window.dispatchEvent(new WheelEvent('wheel'));"
                " scrollBy({top: r.top - innerHeight / 2, behavior: 'instant'}); } }", q)
    pg.wait_for_timeout(150)
    r = pg.evaluate("(q) => { const r = document.querySelector(q).getBoundingClientRect();"
                    " return [r.left + Math.min(r.width / 2, 40), r.top + r.height / 2, r.top]; }", q)
    t = time.time()
    pg.touchscreen.tap(r[0], r[1])
    return r[2], t


def fold_of(ref: str) -> str:
    return f".grid > .row:has(> p.t[id='{ref}']) .trfold"


def continue_reading(b, whole: bool, margin: bool) -> None:
    """His report: Continue reading, the translations unfolded, Home, and
    Continue reading again came back with them folded."""
    s = {"whole": True} if whole else {}
    if not margin:
        s["margin"] = False
    say = ("Whole paper on" if whole else "Whole paper off") + (", the index folded" if not margin else "") + ": "
    print("\nContinue reading, " + say.rstrip(": "))
    ctx, pg, errors = fresh(b, s)
    pg.goto(BASE + "/")
    pg.evaluate("localStorage.setItem('ub_place', JSON.stringify({ref: '101:4.3', title: 'The Real Nature of Religion', at: Date.now(), v: ''}))")
    pg.reload()
    pg.click(".fbar .fgo")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    ok(until(pg, ALL_SHUT) and pg.evaluate(TOP, "[id='101:4.3']") is not None, say + "come to 101:4.3, the folds shut")
    # A fold under the paragraph come to, tapped: every fold opens.
    q = fold_of("101:4.3")
    y0, t = tap_fold(pg, q)
    ok(until(pg, ALL_OPEN), say + f"a tap on one fold opens them all ({pg.evaluate(FOLDS)})")
    dt = time.time() - t
    pg.wait_for_timeout(1200)
    y1 = pg.evaluate(TOP, q)
    ok(abs(y1 - y0) <= 1, say + f"and the line tapped stays where it stood ({y0:.1f} → {y1:.1f}, {dt:.2f} s)")
    ok(pg.evaluate(STORED).get("tropen") is True, say + "kept (tropen)")
    ok(pg.locator(".runhead:not([hidden])").count() == 0, say + "the tap is no tap on the text: no running head")
    # Home, and Continue reading again.
    pg.goto(BASE + "/")
    ok(pg.evaluate("document.querySelector('.fbar').classList.contains('fhas')"), say + "the bar on the home page has the place")
    ref = pg.evaluate("JSON.parse(localStorage.getItem('ub_place')).ref")
    pg.click(".fbar .fgo")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    ok(until(pg, ALL_OPEN), say + f"Continue reading again: every fold open ({pg.evaluate(FOLDS)})")
    pg.wait_for_timeout(1500)
    top = pg.evaluate(TOP, f"[id='{ref}']")
    ok(top is not None and -2 <= top <= 60, say + f"and the place, {ref}, at the window's top under the folds above it ({top})")
    # Folded again, from another paragraph's fold.
    q = fold_of("101:4.5")
    y0, _ = tap_fold(pg, q)
    ok(until(pg, ALL_SHUT), say + "a tap on another fold folds them all")
    pg.wait_for_timeout(600)
    y1 = pg.evaluate(TOP, q)
    ok(abs(y1 - y0) <= 1, say + f"the line tapped where it stood ({y0:.1f} → {y1:.1f})")
    pg.goto(BASE + "/")
    pg.click(".fbar .fgo")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    pg.wait_for_timeout(800)
    ok(pg.evaluate(ALL_SHUT) and pg.evaluate(STORED).get("tropen") is None, say + "and Continue reading then comes back with them folded")
    ok(not errors, say + "no script error: " + "; ".join(errors))
    ctx.close()


def tabs_and_index(b) -> None:
    print("\nA tab chosen in one fold is every fold's; a paragraph come to from the index")
    ctx, pg, errors = fresh(b, {"tropen": True})
    pg.goto(BASE + "/101:4")
    ok(until(pg, ALL_OPEN), "opened with the setting on, every fold is open")
    ok(pg.locator(".tf.open .trtabs button[data-tab='urantia-ru'][aria-pressed='true']").count() == pg.evaluate(FOLDS)["n"],
       "each at the first translation ticked")
    q = ".grid > .row:has(> p.t[id='101:4.4']) .trtabs button[data-tab='all']"
    pg.evaluate("(q) => document.querySelector(q).scrollIntoView({block: 'center'})", q)
    pg.wait_for_timeout(200)
    anchor = ".grid > .row:has(> p.t[id='101:4.4']) .trfold"
    y0 = pg.evaluate(TOP, anchor)
    r = pg.evaluate("(q) => { const r = document.querySelector(q).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", q)
    pg.touchscreen.tap(r[0], r[1])
    ok(until(pg, "document.querySelectorAll('.tf.open .trtabs button[data-tab=all][aria-pressed=true]').length === (%s)().n" % FOLDS),
       "All tapped in one fold: every fold shows All")
    pg.wait_for_timeout(1200)
    y1 = pg.evaluate(TOP, anchor)
    ok(abs(y1 - y0) <= 1, f"the fold tapped stays where it stood ({y0:.1f} → {y1:.1f})")
    ok(pg.evaluate(STORED).get("trtab") == "all", "kept (trtab)")
    # From an index entry to its paragraph.
    pg.goto(BASE + "/i/humor")
    link = pg.locator("main a[href^='/'][href*=':'][href*='.']").first
    href = link.get_attribute("href")
    link.click()
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    ok(until(pg, ALL_OPEN), f"a reference followed from /i/humor ({href}): every fold open, at All")
    ok(pg.locator(".tf.open .trtabs button[data-tab='all'][aria-pressed='true']").count() == pg.evaluate(FOLDS)["n"], "at All")
    pg.wait_for_timeout(1200)
    hit = pg.evaluate("(document.querySelector('p.t.hit') || {}).id || null")
    top = pg.evaluate(TOP, f"[id='{hit}']") if hit else None
    ok(hit and top is not None and -2 <= top <= 60, f"the paragraph come to, {hit}, at the window's top ({top})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def hits_and_reading(b) -> None:
    print("\nA search's hit in a translation, and the reading, with the folds shut and open")
    ctx, pg, errors = fresh(b)
    pg.goto(BASE + "/101:4.3#tr-uf-ru")
    ok(until(pg, "document.querySelectorAll('.tf.open').length === 1"), "shut: the hit's paragraph alone has its fold open")
    ok(pg.locator(".row:has(> p.t[id='101:4.3']) .tf.open .trtabs button[data-tab='uf-ru'][aria-pressed='true']").count() == 1,
       "at the translation hit")
    ok(pg.evaluate(STORED).get("tropen") is None, "and the setting is not changed")
    # The reading opens its paragraph's fold, and shuts it as it goes on.
    pg.evaluate("ubTrRead('101:4.5', 'urantia-ru', true)")
    ok(until(pg, "!!document.querySelector('.row:has(> p.t[id=\"101:4.5\"]) .tf.open')"), "the reading opens the fold of the paragraph read")
    pg.evaluate("ubTrRead('101:4.6', 'urantia-ru', true)")
    ok(until(pg, "!document.querySelector('.row:has(> p.t[id=\"101:4.5\"]) .tf.open')"
                 " && !!document.querySelector('.row:has(> p.t[id=\"101:4.6\"]) .tf.open')"), "and shuts it for the next")
    pg.evaluate("ubTrRead(null)")
    # Opened, every fold; the hit's at its own translation.
    ctx.close()
    ctx, pg, errors = fresh(b, {"tropen": True})
    pg.goto(BASE + "/101:4.3#tr-uf-ru")
    ok(until(pg, ALL_OPEN), "open: every fold open")
    ok(pg.locator(".row:has(> p.t[id='101:4.3']) .tf.open .trtabs button[data-tab='uf-ru'][aria-pressed='true']").count() == 1
       and pg.locator(".row:has(> p.t[id='101:4.4']) .tf.open .trtabs button[data-tab='urantia-ru'][aria-pressed='true']").count() == 1,
       "the hit's at the translation hit, the others at the first ticked")
    n = pg.evaluate(FOLDS)["open"]
    for ref in ("101:4.5", "101:4.6", "101:4.7"):
        pg.evaluate(f"ubTrRead('{ref}', 'urantia-ru', true)")
        pg.wait_for_timeout(150)
    pg.evaluate("ubTrRead(null)")
    pg.wait_for_timeout(150)
    ok(pg.evaluate(FOLDS)["open"] == n, "the reading shuts none of them")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def columns(b) -> None:
    print("\nColumns come with the folds open, and go")
    ctx, pg, errors = fresh(b, {"tropen": True, "rail": "folded", "margin": False}, phone=False, w=1000, h=900)
    pg.goto(BASE + "/101:4")
    ok(until(pg, ALL_OPEN), "at 1000 px with no room for three columns: every fold open")
    pg.set_viewport_size({"width": 1700, "height": 900})
    ok(until(pg, "(%s)().cols" % FOLDS), "made wider: columns")
    pg.wait_for_timeout(800)
    f = pg.evaluate(FOLDS)
    ok(f["under"] == 0 and pg.locator("main .tf .tr").count() == 0, f"and no fold's words under them ({f})")
    pg.set_viewport_size({"width": 1000, "height": 900})
    ok(until(pg, "!(%s)().cols" % FOLDS) and until(pg, ALL_OPEN), f"narrowed again: the folds, all open ({pg.evaluate(FOLDS)})")
    ok(pg.locator("[id^='fnref']").evaluate_all("els => els.length === new Set(els.map(e => e.id)).size"), "no note's number twice")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def place_in_fold(b) -> None:
    print("\nThe window's top inside a fold: the place is that paragraph")
    ctx, pg, errors = fresh(b, {"tropen": True})
    pg.goto(BASE + "/101:4")
    ok(until(pg, ALL_OPEN), "every fold open")
    pg.wait_for_timeout(800)
    # The window's top half-way down 101:4.4's translations.
    pg.evaluate("""() => { const tr = document.querySelector('.grid > .row:has(> p.t[id="101:4.4"]) .tf .tr');
      const r = tr.getBoundingClientRect(); window.dispatchEvent(new WheelEvent('wheel'));
      scrollBy({top: r.top + r.height / 2, behavior: 'instant'}); }""")
    pg.wait_for_timeout(900)
    across = pg.evaluate(ACROSS, 24)
    got = pg.evaluate("(JSON.parse(localStorage.getItem('ub_place')) || {}).ref")
    ok(across == "101:4.4" and got == "101:4.4", f"kept as 101:4.4, whose translations stand there ({got}, {across})")
    pg.goto(BASE + "/")
    pg.click(".fbar .fgo")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    ok(until(pg, ALL_OPEN), "and Continue reading comes back to it, the folds open")
    pg.wait_for_timeout(1200)
    top = pg.evaluate(TOP, "[id='101:4.4']")
    ok(top is not None and -2 <= top <= 60, f"101:4.4 at the window's top ({top})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def nothing_kept(b) -> None:
    print("\nA browser that keeps nothing; and the translations not to be had")
    ctx, pg, errors = fresh(b, block=True)
    pg.goto(BASE + "/101:4")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    tap_fold(pg, fold_of("101:4.3"))
    ok(until(pg, ALL_OPEN), "storage refused: a tap still opens them all")
    tap_fold(pg, fold_of("101:4.4"))
    ok(until(pg, ALL_SHUT), "and folds them all")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()
    ctx, pg, errors = fresh(b, {"tropen": True})
    pg.route("**/tr/**", lambda r: r.abort())
    pg.goto(BASE + "/101:4")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    pg.wait_for_timeout(1500)
    ok(pg.evaluate(FOLDS)["open"] == 0, "their section's translations not to be had: the folds stay shut")
    tap_fold(pg, fold_of("101:4.3"))
    ok(until(pg, "!!document.querySelector('.tf.open .gap')"), "the one tapped opens, and says why")
    ok(pg.evaluate(FOLDS)["open"] == 1, "alone")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def longest(b) -> None:
    print("\nThe longest paper, 30, whole: 321 paragraphs")
    ctx, pg, errors = fresh(b, {"whole": True})
    pg.goto(BASE + "/30")
    pg.wait_for_selector("main .tf[data-has] .trfold:not(:empty)")
    pg.evaluate("document.getElementById('30:2.80').scrollIntoView({block: 'start'})")
    pg.wait_for_timeout(500)
    q = fold_of("30:2.81")
    y0, t = tap_fold(pg, q)
    ok(until(pg, ALL_OPEN, 20000), f"a tap opens all {pg.evaluate(FOLDS)['n']} folds in {time.time() - t:.2f} s")
    pg.wait_for_timeout(1500)
    y1 = pg.evaluate(TOP, q)
    ok(abs(y1 - y0) <= 1, f"the line tapped where it stood ({y0:.1f} → {y1:.1f})")
    y0, t = tap_fold(pg, q)
    ok(until(pg, ALL_SHUT, 20000), f"and folds them all in {time.time() - t:.2f} s")
    pg.wait_for_timeout(600)
    y1 = pg.evaluate(TOP, q)
    ok(abs(y1 - y0) <= 1, f"the line tapped where it stood ({y0:.1f} → {y1:.1f})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


# The line at the window's top: a paragraph's or a translation's line in an
# open fold, and where it stands.
LINE = """() => { for (const e of document.querySelectorAll('main :is(p.t[id], .tf.open p.rt[data-ref])')) {
  const r = e.getBoundingClientRect(); if (r.height && r.bottom > 4) return [e.id || e.dataset.k + ' ' + e.dataset.ref, Math.round(r.top)]; } }"""


def back(b) -> None:
    """A page loaded again from its entry in the history, where the browser
    puts it back by its height as first drawn, before the folds or the
    columns (ub.js atBack): Playwright's Chrome keeps no page in its cache,
    so every Back here is such a load, as a reload is."""
    print("\nBack and a reload, the page loaded again from its entry")
    for label, s, path, w, at in (("folds open, a section", {"tropen": True}, "/101:4", 390, 0.45),
                                  ("folds open, the whole paper", {"tropen": True, "whole": True}, "/101", 390, 0.45),
                                  ("folds open, come to a paragraph", {"tropen": True}, "/101:4.3", 390, 0.7),
                                  ("folds open, the top in a fold", {"tropen": True}, "/101:4", 390, None),
                                  ("in columns", {"rail": "folded", "margin": False}, "/101:4", 1700, 0.45)):
        ctx, pg, errors = fresh(b, s, phone=w < 1000, w=w, h=900)
        pg.goto(BASE + path)
        pg.wait_for_selector("main .tf[data-has]", state="attached")
        until(pg, ALL_OPEN if s.get("tropen") else "!!document.querySelector('main article.cmp .rc')")
        pg.wait_for_timeout(1200)
        if at is None:
            pg.evaluate("""() => { const tr = document.querySelector('.grid > .row:has(> p.t[id="101:4.5"]) .tf .tr');
              window.dispatchEvent(new WheelEvent('wheel')); scrollBy({top: tr.getBoundingClientRect().top + 40, behavior: 'instant'}); }""")
        else:
            pg.evaluate("(f) => { window.dispatchEvent(new WheelEvent('wheel'));"
                        " scrollTo({top: document.documentElement.scrollHeight * f, behavior: 'instant'}); }", at)
        pg.wait_for_timeout(700)
        was = pg.evaluate(LINE)
        pg.goto(BASE + "/1:1")
        pg.wait_for_timeout(500)
        pg.go_back(wait_until="commit")
        pg.wait_for_timeout(2500)
        came = pg.evaluate(LINE)
        ok(came == was, f"{label}: Back puts it back at the same line ({was} → {came})")
        pg.reload()
        pg.wait_for_timeout(2500)
        came = pg.evaluate(LINE)
        ok(came == was, f"{label}: and so does a reload ({was} → {came})")
        ok(not errors, label + ": no script error: " + "; ".join(errors))
        ctx.close()


def help_example(b) -> None:
    print("\nHelp's example of a fold")
    ctx, pg, errors = fresh(b)
    pg.goto(BASE + "/help#translations")
    eg = "#translations .eg .trfold"
    ok(pg.locator(eg).is_visible() and pg.locator(eg).inner_text().strip() == "3 translations",
       f"on the page, with its words ({pg.locator(eg).inner_text()!r})")
    pg.locator(eg).tap()
    pg.wait_for_timeout(300)
    ok(pg.evaluate(STORED).get("tropen") is None and pg.locator("#translations .eg .tf.open").count() == 0, "and a tap on it changes nothing")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        only = sys.argv[1:]
        steps = [("bug", lambda: [continue_reading(b, w, m) for w, m in ((False, True), (True, True), (False, False), (True, False))]),
                 ("tabs", lambda: tabs_and_index(b)), ("hits", lambda: hits_and_reading(b)), ("columns", lambda: columns(b)),
                 ("place", lambda: place_in_fold(b)), ("nothing", lambda: nothing_kept(b)), ("longest", lambda: longest(b)),
                 ("back", lambda: back(b)),
                 ("help", lambda: help_example(b))]
        for name, step in steps:
            if not only or name in only:
                step()
        b.close()
    return 1 if fails else 0


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
                            str(ROOT / "var" / "no-offline-copy"), str(PORT)], cwd=ROOT, env=env)
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
