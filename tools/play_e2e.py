"""A paragraph's ▶ and the time beside it, and the Contents' mark, in Chrome
(Tigran, 2026-11-17): the triangle a third larger, the whole second line of
the stack under the reference its button, and at the line's end the time the
paragraph takes to hear in the recording the page plays, at the speed chosen
(listen.js place(), clock(); ub.css .playp[data-t]); and the section being
read on a pale blue band in the Contents (ub.css .rail li.here > a).

Held here: every paragraph's time is the recording's, by the database, a
section's first with its spoken heading; it is drawn by the stylesheet and the
button has no text, so that a copy never takes it; the button is as wide as
the stack and a line tall, and what is under a finger at the time is the
button (CLAUDE.md trap 61), a tap there starting the reading; the time
follows the speed; none with the 1955 pages shown, with the references off,
in the browser's voice, or beside a translation's ▶; the text stands at one
indent under references of five characters; Help's example carries it; and
the band is the section's alone and gives the rail no sideways scroll.

    .venv/bin/python tools/play_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8138 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate, like
runhead_e2e.py: tests/test_play.py holds the static facts.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = "8138"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def clock(ms: float, rate: float = 1.0) -> str:
    """listen.js clock(): m:ss, to the nearest second, never 0:00."""
    n = max(1, int(ms / rate / 1000 + .5))
    return f"{n // 60}:{n % 60:02d}"


def recorded(paper: int, section: int | None = None, key: str = "mh") -> dict[str, int]:
    """Each paragraph's milliseconds in a recording, from the database: its own
    segment, and before a section's first the spoken heading's."""
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT p.ref, g.end_ms - g.start_ms FROM audio_segment g JOIN audio_source s ON s.id = g.source_id"
        " JOIN section sec ON sec.id = g.section_id LEFT JOIN paragraph p ON p.id = g.paragraph_id"
        " WHERE s.key = ? AND sec.paper_n = ? AND (? IS NULL OR sec.n = ?) ORDER BY sec.n, g.ord",
        (key, paper, section, section)).fetchall()
    out, head = {}, 0
    for ref, ms in rows:
        if ref is None:
            head = ms
        else:
            out[ref] = ms + head
            head = 0
    return out


# Every paragraph's time as its ▶ carries it, {ref: "m:ss"}.
TIMES = """() => Object.fromEntries([...document.querySelectorAll('p.t[id] > .stk > .playp')]
    .filter(b => b.dataset.t).map(b => [b.closest('p.t').id, b.dataset.t]))"""
# What the stylesheet draws after a paragraph's ▶: the time, or nothing.
DRAWN = """(id) => { const b = document.getElementById(id).querySelector('.stk > .playp');
    const c = getComputedStyle(b, '::after').content; return c === 'none' || c === 'normal' ? '' : c.replace(/"/g, ''); }"""
# A paragraph's stack, its reference and its ▶, as boxes [left, top, right, bottom].
BOXES = """(id) => { const p = document.getElementById(id), r = e => { const b = e.getBoundingClientRect();
      return [b.left, b.top, b.right, b.bottom]; }, b = p.querySelector('.stk > .playp');
    return { stk: r(p.querySelector('.stk')), num: r(p.querySelector('.num')), play: r(b), svg: r(b.querySelector('svg')),
             text: b.textContent, fits: b.scrollWidth <= b.clientWidth }; }"""


def settle(pg, ms: int = 200) -> None:
    pg.wait_for_timeout(ms)


def context(b, settings: dict | None = None, phone: bool = True, width: int = 1500):
    ctx = (b.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2)
           if phone else b.new_context(viewport={"width": width, "height": 900}))
    # A fresh context is a first visit, which the tour would meet (help.js).
    # The settings once, on the tab's first page: what a test sets after is
    # kept as it moves about.
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); if (!sessionStorage.getItem('seeded')) {"
                        " sessionStorage.setItem('seeded', '1'); localStorage.setItem('ub_settings', %s); } } catch (e) {}"
                        % json.dumps(json.dumps(settings or {})))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, errors


def open_at(pg, path: str, sel: str = "p.t[id] > .stk > .playp") -> None:
    pg.goto(BASE + path)
    pg.wait_for_selector(sel, state="attached", timeout=15000)
    settle(pg, 400)


def phone(b) -> None:
    ctx, pg, errors = context(b)
    print("A section's page on a phone")
    open_at(pg, "/101:4")
    want = {ref: clock(ms) for ref, ms in recorded(101, 4).items()}
    got = pg.evaluate(TIMES)
    ok(len(want) == 10 and got == want, "every paragraph's ▶ carries the recording's time (%d of %d; 101:4.2 %s)"
       % (sum(got.get(k) == v for k, v in want.items()), len(want), got.get("101:4.2")))
    own = clock(dict(recorded(101, 4))["101:4.1"])
    ok(got.get("101:4.1") == own and own != clock(48941 - 4000), "the section's first with its spoken heading: " + own)
    ok(pg.evaluate(DRAWN, "101:4.2") == want["101:4.2"], "drawn by the stylesheet from the attribute")
    x = pg.evaluate(BOXES, "101:4.2")
    ok(x["text"] == "", "the button has no text of its own, for a copy to take")
    ok(abs(x["play"][2] - x["stk"][2]) < 1 and x["play"][2] - x["play"][0] > 55
       and abs((x["play"][3] - x["play"][1]) - (x["num"][3] - x["num"][1])) < 1,
       "the button is the stack's whole second line: %.0f x %.0f px" % (x["play"][2] - x["play"][0], x["play"][3] - x["play"][1]))
    ok(abs((x["svg"][2] - x["svg"][0]) - 17.6) < .5, "its triangle 1.1rem: %.1f px" % (x["svg"][2] - x["svg"][0]))
    ok(x["fits"], "the triangle and the time within it")
    pg.evaluate("document.getElementById('101:4.2').scrollIntoView({block: 'center'})")
    settle(pg)
    x = pg.evaluate(BOXES, "101:4.2")
    at = [x["play"][2] - 12, (x["play"][1] + x["play"][3]) / 2]
    ok(pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && !!e.closest('.playp') &&"
                   " e.closest('p.t').id === '101:4.2'; }", at), "what is under a finger at the time is the button")
    pg.touchscreen.tap(*at)
    ok(pg.wait_for_function("() => { const p = document.querySelector('p.t.now'); return p && p.id === '101:4.2'; }", timeout=8000)
       is not None and pg.evaluate("!!document.querySelector('.player')"), "and a tap there starts the reading at the paragraph")
    pg.evaluate("document.querySelector('.player .close') && document.querySelector('.player .close').click()")
    settle(pg)

    print("The speed")
    pg.evaluate("ubSettings.set('rate', 1.5)")
    settle(pg)
    fast = {ref: clock(ms, 1.5) for ref, ms in recorded(101, 4).items()}
    ok(pg.evaluate(TIMES) == fast and fast != want and pg.evaluate(DRAWN, "101:4.2") == fast["101:4.2"],
       "the time follows it: 101:4.2 %s at 1.5 for %s" % (fast["101:4.2"], want["101:4.2"]))
    pg.evaluate("ubSettings.set('rate', 1)")
    settle(pg)
    ok(pg.evaluate(TIMES) == want, "and back")

    print("Where it is not drawn")
    pg.evaluate("ubSettings.set('pages', true)")
    settle(pg)
    x = pg.evaluate(BOXES, "101:4.2")
    pgb = pg.evaluate("(() => { const b = document.getElementById('101:4.2').querySelector('.pg').getBoundingClientRect();"
                      " return [b.left, b.top, b.right, b.bottom]; })()")
    ok(pg.evaluate(DRAWN, "101:4.2") == "" and x["play"][2] - x["play"][0] < 30 and pgb[0] >= x["play"][2] - 1
       and abs(pgb[1] - (x["num"][3])) < 6, "with the 1955 pages shown the page has the room, beside a ▶ of its own width")
    pg.evaluate("ubSettings.set('pages', false); ubSettings.set('paranum', false)")
    settle(pg)
    ok(pg.evaluate(DRAWN, "101:4.2") == "", "nor with the references off")
    pg.evaluate("ubSettings.set('paranum', true)")
    settle(pg)
    ok(pg.evaluate(DRAWN, "101:4.2") == want["101:4.2"], "and back with them")
    if pg.evaluate("!!window.speechSynthesis"):
        pg.evaluate("ubSettings.set('voice', 'browser')")
        settle(pg, 400)
        ok(pg.evaluate("document.querySelectorAll('p.t[id] > .stk > .playp').length") == 10 and pg.evaluate(TIMES) == {},
           "the browser's voice has no times")
        pg.evaluate("ubSettings.set('voice', 'mh')")
        settle(pg, 400)
        ok(pg.evaluate(TIMES) == want, "the recording chosen again has them")

    print("References of five characters, and a paper's opening")
    open_at(pg, "/1:0")
    ids = pg.evaluate("[...document.querySelectorAll('p.t[id]:not(.opening)')].map(p => p.id)")
    xs = [pg.evaluate(BOXES, i) for i in ids]
    widths = {round(x["stk"][2] - x["stk"][0], 1) for x in xs}
    ok(max(len(i) for i in ids) == 5 and len(widths) == 1 and all(x["fits"] for x in xs),
       "every stack as wide as the next, the time within it: %s px" % sorted(widths))
    ok(pg.evaluate(DRAWN, "1:0.1") == clock(recorded(1, 0)["1:0.1"]),
       "the opening paragraph's, in the line above it: " + pg.evaluate(DRAWN, "1:0.1"))
    x = pg.evaluate(BOXES, "1:0.1")
    # The reference's box is a line of the text tall, its figures at its top:
    # the two overlap by most of the button's height.
    ok(x["play"][0] >= x["num"][2] and x["play"][1] < x["num"][1] + 3 and x["play"][3] > x["num"][1] + 14,
       "its ▶ after the reference, on its line")

    print("The whole paper")
    pg.evaluate("ubSettings.set('whole', true)")
    open_at(pg, "/101", "article.whole p.t[id] > .stk > .playp")
    want = {ref: clock(ms) for ref, ms in recorded(101).items()}
    got = pg.evaluate(TIMES)
    ok(len(want) > 60 and got == want, "every paragraph of the paper, each section's first with its heading (%d of %d)"
       % (sum(got.get(k) == v for k, v in want.items()), len(want)))
    pg.evaluate("ubSettings.set('whole', false)")

    print("The Contents' mark")
    open_at(pg, "/101:4")
    pg.tap("[id='101:4.3']")
    settle(pg)
    pg.tap(".runhead .ref")
    settle(pg, 400)
    band(pg, "a phone")

    print("Help")
    pg.goto(BASE + "/help")
    settle(pg, 400)
    eg = pg.evaluate("(() => { const b = document.querySelector('.helppage .eg .stk > .playp'), p = b.closest('p.t');"
                     " return [p.querySelector('.num').textContent, b.dataset.t || '', getComputedStyle(b, '::after').content.replace(/\"/g, '')]; })()")
    paper, rest = eg[0].split(":")
    ms = recorded(int(paper), int(rest.split(".")[0])).get(eg[0])
    ok(ms is not None and eg[1] == clock(ms) == eg[2], "its example paragraph, %s, carries its time, drawn: %s" % (eg[0], eg[1]))
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def band(pg, where: str) -> None:
    x = pg.evaluate("""() => { const rail = document.querySelector('.rail'), a = rail.querySelector('li.here > details > ol > li.here > a'),
        o = rail.querySelector('li.here > details > ol > li:not(.here) > a'), s = rail.querySelector('li.here > details > summary a'),
        bg = e => getComputedStyle(e).backgroundColor, clear = c => /rgba?\\(0, 0, 0, 0\\)|transparent/.test(c);
      return { href: a.getAttribute('href'), band: !clear(bg(a)), other: clear(bg(o)), paper: clear(bg(s)),
               ink: getComputedStyle(a).color === getComputedStyle(s).color && getComputedStyle(a).color !== getComputedStyle(o).color,
               within: a.getBoundingClientRect().right <= rail.getBoundingClientRect().right,
               still: rail.scrollWidth <= rail.clientWidth && document.documentElement.scrollWidth <= innerWidth,
               n: rail.querySelectorAll('li.here > a').length }; }""")
    ok(x["href"] == "/101:4" and x["band"] and x["other"] and x["paper"] and x["n"] == 1,
       "on %s the section being read is on a band, it alone, not the paper nor another section" % where)
    ok(x["ink"], "its title in ink, as the paper's")
    ok(x["within"] and x["still"], "the band within the Contents, which do not scroll sideways for it")


def desk(b) -> None:
    print("A desk: the columns and the rail")
    ctx, pg, errors = context(b, {"translations": "urantia-ru"}, phone=False, width=1920)
    # A translation's ▶ in the stack at its paragraph's start, as the first
    # column's, with its time where a recording reads it, USGNY's Григорий
    # Войнер's (Tigran, 2026-11-20); in the gap before the column, with no
    # time, until then.
    open_at(pg, "/1:1", ".rc p.rt > .stk > .playp")
    ok(pg.evaluate("document.querySelectorAll('.rc p.rt > .stk > .playp').length") > 5
       and pg.evaluate("document.querySelectorAll('.rc > .playp, .tf .playp[data-t]').length") == 0,
       "a translation's ▶ stands in its paragraph, none in the gap")
    t12 = pg.evaluate("(document.querySelector(\".rc[data-k='urantia-ru'] p.rt[data-ref='1:1.2'] > .stk > .playp\") || {dataset: {}}).dataset.t")
    ok(bool(t12) and ":" in t12, f"with the time its recording takes ({t12})")
    want = {ref: clock(ms) for ref, ms in recorded(1, 1).items()}
    ok(pg.evaluate(TIMES) == want and pg.evaluate(DRAWN, "1:1.2") == want["1:1.2"], "the English beside it has its own")
    x = pg.evaluate("""() => { const p = document.querySelector(".rc[data-k='urantia-ru'] p.rt[data-ref='1:1.2']"),
        b = p.querySelector('.stk > .playp').getBoundingClientRect(), c = p.closest('.rc').getBoundingClientRect(),
        r = document.createRange(); r.setStart(p.querySelector('.stk').nextSibling, 0); r.setEnd(p.querySelector('.stk').nextSibling, 1);
        const t = r.getBoundingClientRect(); return [b.left, c.left, b.right, t.left, Math.abs(b.top - p.getBoundingClientRect().top)]; }""")
    ok(x[0] >= x[1] - 7 and x[2] <= x[3] + 1 and x[4] < 12,
       "inside its column, the text set after it on the first line: %.0f px after it" % (x[3] - x[2]))
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()
    ctx, pg, errors = context(b, phone=False)
    open_at(pg, "/101:4")
    band(pg, "a desk")
    pg.hover("[id='101:4.2'] .stk > .playp")
    settle(pg)
    ok(pg.evaluate("getComputedStyle(document.querySelector(\"[id='101:4.2'] .stk > .playp svg\")).opacity") == "1"
       and pg.evaluate("getComputedStyle(document.querySelector(\"[id='101:4.5'] .stk > .playp svg\")).opacity") == "0.45",
       "the triangle is faint, and full under the pointer")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        phone(b)
        desk(b)
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (tools/runhead_e2e.py NO_COPY).
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
