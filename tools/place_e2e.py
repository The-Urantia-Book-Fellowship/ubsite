"""The reading place and the bar at the foot, end to end, in Chrome (ub.js
rpSave, base.html .fbar; Tigran, 2026-11-17): the bar stands at the window's
foot on every page but a page of the text, a reading path and the chart, and
covers the end of none; on a first visit it says Begin reading and goes to the
Foreword; a glance at a paragraph moves no place, five seconds on a page of
the text do, and so does the reader's own scroll, at once; the place is the
first paragraph with a line showing, with its paper's title, the time and the
text's version; Continue reading goes to it, in the reader's unit, with Whole
paper off and on (CLAUDE.md trap 44); Back to the home page says the place as
it now is, and so does another tab; while something is heard the place is
the paragraph being heard, and the player stands over the bar on a page that
has it; a reading path moves nothing; a phone has the
reference alone after the words, in both languages; and with scripts off it
is Begin reading.

    .venv/bin/python tools/place_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8139 with the visit counter off, and
leaves the dev server alone.  Not a gate: tests/test_place.py holds the
static facts.
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
PORT = 8139
BASE = f"http://127.0.0.1:{PORT}"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


# The bar as a reader of the language shown has it: whether it is drawn, where
# it stands, its words (those displayed), its address.
BAR = """() => { const b = document.querySelector('.fbar'); if (!b) return null;
  const r = b.getBoundingClientRect(), on = getComputedStyle(b).display !== 'none';
  const said = el => { if (!el || !el.getClientRects().length) return '';
    const kids = [...el.children].filter(c => /^X-(EN|RU)$/.test(c.tagName));
    return (kids.length ? kids.filter(c => c.getClientRects().length).map(c => c.textContent).join('') : el.textContent).trim(); };
  return {on, top: r.top, bottom: r.bottom, left: r.left, right: r.right, vh: innerHeight, vw: document.documentElement.clientWidth,
          has: b.classList.contains('fhas'), href: b.querySelector('.fgo').getAttribute('href'),
          label: [...b.querySelectorAll('.fl')].map(said).join(''), ref: said(b.querySelector('.fref')),
          title: said(b.querySelector('.fttl')), fits: b.scrollWidth <= b.clientWidth + 1,
          over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
PLACE = "() => JSON.parse(localStorage.getItem('ub_place') || 'null')"
# The first paragraph with a line of its own showing at the window's top, found
# apart from ub.js rpPara.
FIRST = """() => { for (const p of document.querySelectorAll('main p.t[id]')) {
  const r = p.getBoundingClientRect(); if (r.height && r.bottom > 24) return p.id; } return null; }"""


def bar(pg):
    return pg.evaluate(BAR)


def place(pg):
    return pg.evaluate(PLACE)


def until(pg, js: str, ms: int = 4000) -> bool:
    """Whether `js` comes true within `ms` (polled: CLAUDE.md trap 41)."""
    end = time.time() + ms / 1000
    while time.time() < end:
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(100)
    return bool(pg.evaluate(js))


def fresh(b, **kw):
    ctx = b.new_context(**kw)
    # A fresh context is a first visit, which the tour would meet (help.js).
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
    return ctx


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        ctx = fresh(b, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("A first visit")
        pg.goto(BASE + "/")
        x = bar(pg)
        ok(x["on"] and abs(x["bottom"] - x["vh"]) < 1 and x["left"] == 0 and abs(x["right"] - x["vw"]) < 1,
           "the bar stands along the window's foot on the home page")
        ok(not x["has"] and x["label"] == "Begin reading" and x["title"] == "Foreword" and x["ref"] == ""
           and x["href"] == "/0", f"it says Begin reading, Foreword, and goes to /0 ({x['label']!r}, {x['title']!r}, {x['href']})")
        ok(place(pg) is None, "and nothing is kept yet")
        tv = pg.get_attribute(".fbar", "data-tv")
        ok(bool(tv) and tv.isdigit(), f"the bar carries the text's version ({tv})")

        print("Where the bar is, and what it covers")
        for url in ("/", "/read", "/index", "/i/faith", "/lists", "/help", "/search?q=faith", "/part/1", "/quiz",
                    "/appendix/A", "/changelog", "/api", "/no-such-page"):
            pg.goto(BASE + url)
            pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
            pg.wait_for_timeout(120)
            x = bar(pg)
            # The last thing the page says, the footer's or the main's, ends above the bar.
            low = pg.evaluate("""() => { let low = 0;
                for (const el of document.querySelectorAll('main *, footer p')) {
                  // Not what a closed fold holds, nor the Contents at the left, a window of its own.
                  if (!el.checkVisibility() || el.closest('.rail') || !el.getClientRects().length
                      || el.children.length && el.tagName !== 'P' && el.tagName !== 'A') continue;
                  low = Math.max(low, el.getBoundingClientRect().bottom); }
                return low; }""")
            ok(x["on"] and abs(x["bottom"] - x["vh"]) < 1 and low <= x["top"] + 1 and x["over"] <= 0,
               f"{url}: the bar is at the foot, and the page ends above it ({low:.0f} <= {x['top']:.0f})")
            if url == "/part/1":
                rail = pg.evaluate("document.querySelector('.rail').getBoundingClientRect().bottom")
                ok(rail <= x["top"] + 1, f"{url}: and so do the Contents at the left ({rail:.0f} <= {x['top']:.0f})")
        for url in ("/101:4", "/101", "/0:0", "/cosmology", "/i/faith/read"):
            pg.goto(BASE + url)
            ok(not bar(pg)["on"], f"{url}: no bar")

        print("A glance moves nothing")
        pg.goto(BASE + "/101:4.2")
        pg.wait_for_timeout(2000)
        ok(place(pg) is None, "two seconds at a paragraph an address names, nothing touched: no place")
        pg.goto(BASE + "/")
        ok(bar(pg)["label"] == "Begin reading", "and the home page still says Begin reading")

        print("Staying is reading")
        pg.goto(BASE + "/101:4")
        t0 = time.time() * 1000
        pg.wait_for_timeout(3000)
        ok(place(pg) is None, "after three seconds, still none")
        ok(until(pg, "() => !!localStorage.getItem('ub_place')", 4000), "after five, the place is kept")
        got, first = place(pg), pg.evaluate(FIRST)
        ok(got and got["ref"] == first, f"it is the first paragraph showing ({got and got['ref']}, {first})")
        ok(got and got["title"] == "The Real Nature of Religion", f"with its paper's title ({got and got['title']!r})")
        ok(got and got["v"] == tv and t0 <= got["at"] <= time.time() * 1000 + 1000, "the text's version and the time")

        print("The place follows the page")
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 1400)
        ok(until(pg, f"() => (({PLACE})() || {{}}).ref === ({FIRST})() && scrollY > 1000"),
           f"a wheel on, and it is the paragraph now at the top ({place(pg)['ref']})")
        moved = place(pg)["ref"]
        ok(moved != got["ref"], "another than before")

        print("The reader's own scroll is reading at once")
        pg.goto(BASE + "/12:3")
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 900)
        ok(until(pg, "() => /^12:3\\./.test((JSON.parse(localStorage.getItem('ub_place')) || {}).ref || '')", 1500),
           f"a wheel within the first second, and the place is in 12:3 ({place(pg)['ref']})")
        here = place(pg)
        ok(here["ref"] == pg.evaluate(FIRST) and here["title"] == "The Universe of Universes", "the paragraph at the top, its paper's title")

        print("Continue reading")
        pg.goto(BASE + "/")
        x = bar(pg)
        ok(x["has"] and x["label"] == "Continue reading" and x["ref"] == here["ref"]
           and x["title"].endswith("The Universe of Universes") and x["href"] == "/" + here["ref"],
           f"the home page says Continue reading, {x['ref']}, {x['title']!r}")
        ok(x["fits"] and x["over"] <= 0, "within the bar")
        pg.click(".fbar .fgo")
        pg.wait_for_url("**/" + here["ref"])
        ok(until(pg, f"""() => {{ const p = document.getElementById('{here["ref"]}'), r = p && p.getBoundingClientRect();
                         return !!r && r.top >= 0 && r.top < innerHeight / 2 && p.classList.contains('hit'); }}"""),
           "it goes to the paragraph, which is marked and in the upper half of the window")
        for url in ("/index", "/lists", "/part/3"):
            pg.goto(BASE + url)
            x = bar(pg)
            ok(x["on"] and x["label"] == "Continue reading" and x["ref"] == here["ref"], f"{url}: the same bar")

        print("Whole paper on")
        pg.goto(BASE + "/")
        pg.evaluate("ubSettings.set('whole', true)")
        pg.click(".fbar .fgo")
        pg.wait_for_url("**/12#" + here["ref"])
        ok(until(pg, f"""() => {{ const p = document.getElementById('{here["ref"]}'), r = p && p.getBoundingClientRect();
                         return !!r && r.top >= 0 && r.top < innerHeight / 2; }}"""),
           "Continue reading goes to the paragraph on the whole paper's page")
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 2400)
        ok(until(pg, f"() => (({PLACE})() || {{}}).ref === ({FIRST})() && scrollY > 2000"),
           f"and the place follows the whole paper's page too ({place(pg)['ref']})")
        whole = place(pg)
        ok(whole["title"] == "The Universe of Universes", "the paper's title, not a section's")

        print("Back to the home page")
        pg.go_back()
        pg.wait_for_url(BASE + "/")
        ok(until(pg, f"""() => document.querySelector('.fbar .fref').textContent === '{whole["ref"]}'"""),
           f"the bar says the place as it now is ({bar(pg)['ref']}, {whole['ref']})")
        pg.evaluate("ubSettings.set('whole', false)")

        print("Another tab")
        pg2 = ctx.new_page()
        pg2.goto(BASE + "/3:1")
        pg2.mouse.move(700, 500)
        pg2.mouse.wheel(0, 700)
        ok(until(pg2, "() => /^3:1\\./.test((JSON.parse(localStorage.getItem('ub_place')) || {}).ref || '')", 1500),
           "a place kept in a second tab")
        ok(until(pg, "() => /^3:1\\./.test(document.querySelector('.fbar .fref').textContent)"),
           f"is in the first tab's bar without a reload ({bar(pg)['ref']})")
        pg2.close()

        print("Listening")
        pg.goto(BASE + "/101:4")
        pg.evaluate("""() => { document.body.classList.add('listening');
                               document.getElementById('101:4.6').classList.add('now'); }""")
        ok(until(pg, "() => (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.6'", 4500),
           "the place is the paragraph being heard, the page not having moved")
        pg.evaluate("""() => { document.getElementById('101:4.6').classList.remove('now');
                               document.getElementById('101:4.8').classList.add('now'); }""")
        ok(until(pg, "() => (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.8'", 4500),
           "and moves on with it")

        print("The player stands over the bar")
        # Something heard, and a page with the bar brought in by listen.js: the
        # player's pill above the bar, and the page's end above both.
        # With Follow along off, that is: with it on a link loads its page, and
        # the reading ends (listen.js roaming()).
        pg.goto(BASE + "/101:4")
        pg.evaluate("ubSettings.set('follow', false)")
        pg.click("[id='101:4.2'] .stk > .playp")
        ok(until(pg, "() => document.body.classList.contains('listening') && !!document.querySelector('.player')", 6000),
           "a paragraph's play button starts the player")
        ok(until(pg, "() => (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.2'", 2500),
           f"and the place is the paragraph heard, as it starts ({place(pg)['ref']})")
        pg.click(".top .brand")
        ok(until(pg, "() => location.pathname === '/' && !!document.querySelector('main.front')", 6000)
           and pg.evaluate("document.body.classList.contains('listening')"), "the home page is brought in, the reading going on")
        x = bar(pg)
        pill = pg.evaluate("(() => { const r = document.querySelector('.player').getBoundingClientRect(); return [r.top, r.bottom]; })()")
        ok(x["on"] and pill[1] <= x["top"] - 4, f"the player is above the bar ({pill[1]:.0f} < {x['top']:.0f})")
        ok(x["has"] and x["ref"] == "101:4.2", f"the bar says the place heard ({x['ref']})")
        pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
        pg.wait_for_timeout(150)
        low = pg.evaluate("Math.max(...[...document.querySelectorAll('footer p')].filter(e => e.getClientRects().length).map(e => e.getBoundingClientRect().bottom))")
        pill = pg.evaluate("(() => { const r = document.querySelector('.player').getBoundingClientRect(); return [r.top, r.bottom]; })()")
        ok(low <= pill[0] + 1, f"and the page ends above the player ({low:.0f} <= {pill[0]:.0f})")
        pg.evaluate("document.querySelector('.player .close') && document.querySelector('.player .close').click()")
        pg.evaluate("ubSettings.set('follow', true)")

        print("A reading path moves nothing")
        was = place(pg)
        pg.goto(BASE + "/i/faith/read")
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 900)
        pg.wait_for_timeout(5600)
        ok(place(pg)["ref"] == was["ref"], f"the place is as it was ({place(pg)['ref']})")
        ok(errors == [], "no script error: " + "; ".join(errors))
        ctx.close()

        print("A phone, in both languages")
        for lang, label, begin in (("en", "Continue reading", "Begin reading"), ("ru", "Продолжить чтение", "Начать чтение")):
            for w in (390, 320):
                ctx = fresh(b, has_touch=True, is_mobile=True, viewport={"width": w, "height": 700}, device_scale_factor=2)
                ctx.add_init_script("try { localStorage.setItem('ub_settings', JSON.stringify({lang: '%s'})); } catch (e) {}" % lang)
                pg = ctx.new_page()
                pg.goto(BASE + "/")
                x = bar(pg)
                ok(x["on"] and x["label"] == begin and x["title"] == "" and x["fits"] and x["over"] <= 0,
                   f"{lang} {w}px: {begin}, alone ({x['label']!r}, {x['title']!r})")
                pg.evaluate("""() => localStorage.setItem('ub_place', JSON.stringify(
                    {ref: '139:11.12', title: 'The Twelve Apostles', at: Date.now(), v: '9'}))""")
                pg.reload()
                x = bar(pg)
                ok(x["has"] and x["label"] == label and x["ref"] == "139:11.12" and x["title"] == "" and x["fits"]
                   and x["over"] <= 0, f"{lang} {w}px: {label} and the reference, on one line ({x['label']!r}, {x['ref']!r})")
                one = pg.evaluate("""() => { const a = document.querySelector('.fgo').getBoundingClientRect();
                    return [...document.querySelectorAll('.fgo .fl, .fgo .fref')].filter(e => e.getClientRects().length)
                      .every(e => { const r = e.getBoundingClientRect(); return r.left >= a.left && r.right <= a.right + .5 && r.height < 30; }); }""")
                ok(one, f"{lang} {w}px: nothing cut or wrapped")
                ctx.close()

        print("A kept place that is no reference")
        ctx = fresh(b, viewport={"width": 1280, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('ub_place', '{\"ref\": \"javascript:alert(1)\", \"title\": \"x\"}'); } catch (e) {}")
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        x = bar(pg)
        ok(not x["has"] and x["href"] == "/0" and x["label"] == "Begin reading", "is not followed: Begin reading")
        ctx.close()

        print("Scripts off")
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        on = pg.locator(".fbar").is_visible()
        ok(on and pg.get_attribute(".fbar .fgo", "href") == "/0" and pg.locator(".fbar .fbegin").is_visible()
           and not pg.locator(".fbar .fcont").is_visible(), "the bar is there, Begin reading, to the Foreword")
        ctx.close()
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
