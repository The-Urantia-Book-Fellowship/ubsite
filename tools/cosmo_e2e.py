"""The chart of the personalities, end to end, in Chrome (templates/
cosmology.html, static/cosmo.js; build/cosmo.py).

On a desktop in English and in Russian, with Whole paper off and on, since an
entry's sources are links of the book, which the Whole paper handler rewrites
(CLAUDE.md trap 44); on a phone, by touch; and with scripts off:

  what is drawn: every unit's title no wider than his page drew it, which is
  what his lines were kept clear of; each language's lines and not the
  other's; no sign of three circles about one centre;

  a card chosen: its address, its two cards and its lines lit, the rest stood
  back, its entry beside the chart, and the page itself not moved; the same
  card again, and Escape, let go; a name in the entry chooses that one and
  brings it into the window; a source goes to the text, in the reader's unit,
  and Back returns to the card;

  a unit's title, a chip of the legend, the search box in both alphabets, the
  scale by its buttons, Ctrl + wheel and Whole chart, and the far lines'
  switch;

  from a headword's page in the index to its card; and with scripts off, a
  card to its entry in the list under the chart, and back.

    .venv/bin/python tools/cosmo_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8135 with the visit counter off and no
offline copy to offer, and leaves the dev server alone.  Not a gate:
tests/test_cosmo.py holds the static facts.
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
PORT = "8135"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, expr: str, ms: int = 4000) -> bool:
    """Poll, since wait_for_function does not wait for a promise (trap 41) and
    a smooth scroll is not an event."""
    end = time.time() + ms / 1000
    while time.time() < end:
        if pg.evaluate(expr):
            return True
        pg.wait_for_timeout(60)
    return False


Z = "parseFloat(getComputedStyle(document.querySelector('.csize')).getPropertyValue('--cz'))"
# A card, and whether it is in the window on the chart, whole.
SEEN = """(id) => { const v = document.querySelector('.cview').getBoundingClientRect(),
    r = document.querySelector('.cp[data-id="' + id + '"]:not(.ghost)').getBoundingClientRect();
    return r.left >= v.left && r.right <= v.right && r.top >= v.top && r.bottom <= v.bottom; }"""
STATE = """() => ({
    hash: location.hash, y: Math.round(scrollY),
    on: [...document.querySelectorAll('.cp.on')].map(a => (a.classList.contains('ghost') ? '~' : '') + a.dataset.id).sort(),
    rel: document.querySelectorAll('.cp.rel').length, lines: document.querySelectorAll('.ce.on').length,
    focus: document.querySelector('.cworld').classList.contains('focus'),
    entry: (document.querySelector('.ci.on') || {dataset: {}}).dataset.id || null,
    units: [...document.querySelectorAll('.cut.on')].map(a => a.dataset.id) })"""
# What the data says a card is joined to: the lines with an end at it, or at
# its other card.
JOINED = """(id) => [...document.querySelectorAll('.ce')].filter(g =>
    [g.dataset.a, g.dataset.b].some(e => e === id || e === '~' + id)).length"""
TITLES = """() => { const z = %s, ru = document.documentElement.dataset.lang === 'ru';
    return [...document.querySelectorAll('.cut')].map(a => [a.dataset.id,
        Math.round(a.getBoundingClientRect().width / z) - 6, +(ru ? a.dataset.ru : a.dataset.en)])
      .filter(x => x[1] > x[2] + 2); }""" % Z
CUT = """() => [...document.querySelectorAll('.cp .cn')].filter(n => n.scrollHeight > n.clientHeight + 1)
    .map(n => n.parentNode.dataset.id)"""
LINES = """() => { const shown = c => [...document.querySelectorAll('.cedges .' + c)]
      .filter(g => getComputedStyle(g).display !== 'none' && getComputedStyle(g.parentNode).display !== 'none').length;
    return [shown('en'), shown('ru')]; }"""
# No sign is three circles about one centre.
CONCENTRIC = """() => [...document.querySelectorAll('svg.cg')].filter(s => {
    const c = [...s.querySelectorAll('circle')].filter(x => getComputedStyle(x).fill === 'none')
      .map(x => (x.getAttribute('cx') || 0) + ',' + (x.getAttribute('cy') || 0));
    return c.length >= 3 && new Set(c).size < c.length; }).length"""


def fresh(b, settings: dict, **more):
    ctx = b.new_context(viewport={"width": more.pop("w", 1400), "height": more.pop("h", 900)}, **more)
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); }"
                        " catch (e) {}" % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # But for the offline copy's manifest, which this server has none of.
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error"
          and not m.text.startswith("Failed to load resource") else None)
    pg.on("response", lambda r: errors.append(f"404 {r.url}") if r.status == 404
          and "/offline/manifest.json" not in r.url else None)
    return ctx, pg, errors


def desktop(b, lang: str, whole: bool) -> None:
    say = f"[{lang}, Whole paper {'on' if whole else 'off'}] "
    ctx, pg, errors = fresh(b, {"lang": lang, "whole": whole})
    pg.goto(BASE + "/cosmology", wait_until="load")
    pg.evaluate("document.fonts.ready.then(() => 1)")
    pg.wait_for_timeout(300)
    n = pg.evaluate("[document.querySelectorAll('.cp').length, document.querySelectorAll('.cut').length,"
                    " document.querySelectorAll('.ce').length, document.querySelectorAll('.ci').length]")
    ok(n[0] > 100 and n[1] > 20 and n[2] > 100 and n[3] == n[1] + pg.evaluate(
        "document.querySelectorAll('.cp:not(.ghost)').length"),
       say + f"the chart is drawn: {n[0]} cards, {n[1]} units, {n[2]} lines, {n[3]} entries")
    wide = pg.evaluate(TITLES)
    ok(not wide, say + f"every unit's title is within the width his lines were kept clear of: {wide}")
    cut = pg.evaluate(CUT)
    print(f"        (names too long for three lines of a card, cut with an ellipsis: {len(cut)}: {', '.join(cut)})")
    en, ru = pg.evaluate(LINES)
    ok((en > 50 and ru == 0) if lang == "en" else (ru > 50 and en == 0),
       say + f"the lines drawn are this language's: {en} English, {ru} Russian")
    ok(pg.evaluate(CONCENTRIC) == 0, say + "no sign is three circles about one centre")
    ok(not pg.evaluate("document.querySelector('.ctools').hidden")
       and pg.evaluate("!document.querySelector('main.cosmo [id]:not(marker)')"),
       say + "the tools are shown, and nothing on the chart keeps an id for the browser to scroll to")
    z0 = pg.evaluate(Z)
    ok(0.5 < z0 <= 1 and pg.evaluate("document.querySelector('.csize').offsetWidth <= document.querySelector('.cview').clientWidth + 1"),
       say + f"it opens with the chart's whole width in the window, at {z0:.2f}")

    # A card chosen.
    pg.click('.cp[data-id="michael"]:not(.ghost)')
    ok(until(pg, "!!document.querySelector('.ci.on')"), say + "a click on a card shows its entry")
    s = pg.evaluate(STATE)
    joined = pg.evaluate(JOINED, "michael")
    ok(s["hash"] == "#michael" and s["on"] == ["michael", "~michael"] and s["entry"] == "michael",
       say + f"its address names it, and both its cards are lit: {s['hash']} {s['on']}")
    ok(s["lines"] == joined and s["focus"] and s["rel"] >= 10,
       say + f"its {joined} lines are lit with what they join it to ({s['rel']} cards), the rest stood back")
    ok(s["y"] == 0, say + f"and the page has not moved ({s['y']})")
    pg.wait_for_timeout(350)        # a line's colour changes over a fifth of a second
    head = pg.evaluate("""(() => { const shown = [...document.querySelectorAll('.ce.origin.on .l')]
          .find(x => getComputedStyle(x.parentNode).display !== 'none');
        return [getComputedStyle(shown).markerEnd, getComputedStyle(shown).stroke,
                getComputedStyle(document.querySelector('#cm-on path')).fill]; })()""")
    ok("cm-on" in head[0] and head[1] == head[2], say + f"a lit line's arrowhead is lit with it ({head[2]})")
    far = pg.evaluate("[...document.querySelectorAll('.ce.far.on')].filter(g => getComputedStyle(g).display !== 'none').length")
    ok(far > 0, say + f"its far lines are shown with it ({far})")

    # A name in the entry chooses that one, wherever it is.
    pg.click('.ci.on a[href="#lifec"]')
    ok(until(pg, "(document.querySelector('.ci.on') || {dataset: {}}).dataset.id === 'lifec'"),
       say + "a name in the entry chooses that personality")
    ok(until(pg, "(%s)('lifec')" % SEEN), say + "and brings its card into the window")
    ok(pg.evaluate("Math.round(scrollY)") == 0, say + "the page still not moved")
    pg.go_back()
    ok(until(pg, "(document.querySelector('.ci.on') || {dataset: {}}).dataset.id === 'michael'"),
       say + "Back returns to the card before")

    # A source is a link of the book, in the reader's unit; Back returns.
    href = pg.evaluate("document.querySelector('.ci.on a.cref').getAttribute('href')")
    pg.click(".ci.on a.cref")
    pg.wait_for_load_state("load")
    want = href if whole else href + ":0"
    ok(until(pg, "location.pathname === %s" % json.dumps(want)),
       say + f"a source goes to the text, {href} as {want}: at {pg.evaluate('location.pathname + location.hash')}")
    pg.go_back()
    pg.wait_for_load_state("load")
    ok(until(pg, "location.pathname === '/cosmology' && (document.querySelector('.ci.on') || {dataset: {}}).dataset.id === 'michael'"),
       say + "and Back returns to the chart, the card chosen again")
    ok(until(pg, "Math.round(scrollY) === 0", 1500), say + "with the page at its top")

    # Letting go.
    pg.keyboard.press("Escape")
    s = pg.evaluate(STATE)
    ok(s["hash"] == "" and not s["on"] and not s["focus"] and s["entry"] is None, say + "Escape lets go")
    pg.click('.cp[data-id="seraph"]')
    until(pg, "!!document.querySelector('.ci.on')")
    pg.click('.cp[data-id="seraph"]')
    s = pg.evaluate(STATE)
    ok(s["hash"] == "" and not s["on"] and s["entry"] is None, say + "and so does the same card again")

    # A unit.
    pg.click('.cut[data-id="salv"]')
    until(pg, "!!document.querySelector('.ci.on')")
    s = pg.evaluate(STATE)
    inside = pg.evaluate("document.querySelectorAll('.cp[data-u=\"salv\"]').length")
    ok(s["units"] == ["salv"] and s["entry"] == "salv" and s["rel"] >= inside > 5,
       say + f"a unit's title chooses the unit: its {inside} cards lit, its entry shown")
    pg.keyboard.press("Escape")

    # The legend's chips.
    pg.click(".clegend > summary")
    pg.click('.clegend .cchip[data-k="group:angel"]')
    angels = pg.evaluate("[...document.querySelectorAll('.cp')].filter(a => (' ' + a.dataset.k + ' ').includes(' group:angel ')).length")
    s = pg.evaluate(STATE)
    ok(s["rel"] == angels > 3 and pg.evaluate("document.querySelector('.clegend .cchip.on').dataset.k") == "group:angel",
       say + f"a chip lights every card of its kind ({angels} angels)")
    pg.click('.clegend .cchip[data-k="group:angel"]')
    ok(pg.evaluate("document.querySelectorAll('.cp.rel, .cchip.on').length") == 0, say + "and again lets go")
    shown = "[...document.querySelectorAll('.ce.far')].filter(g => getComputedStyle(g).display !== 'none').length"
    before = pg.evaluate(shown)
    pg.check(".cfar input")
    after = pg.evaluate(shown)
    ok(before == 0 and after > 10, say + f"the far lines' switch shows them all ({before} to {after})")
    pg.uncheck(".cfar input")
    pg.click(".clegend > summary")

    # The search box, in either alphabet whatever the language.
    for word, want in (("мелхис", "melch"), ("Solitary", "solitary")):
        pg.fill(".cq", word)
        ok(until(pg, "document.querySelectorAll('.cres li[data-n]').length > 0"),
           say + f"the search box finds {word!r}")
        pg.keyboard.press("Enter")
        found = until(pg, "['%s', 'fmelch'].includes((document.querySelector('.ci.on') || {dataset: {}}).dataset.id)" % want)
        ok(found, say + f"and Enter chooses it: {pg.evaluate(STATE)['entry']}")
        pg.fill(".cq", "")
    pg.fill(".cq", "qqqq")
    ok(until(pg, "!!document.querySelector('.cres li.none')"), say + "and says when it finds nothing")
    pg.fill(".cq", "")
    # Escape in the box is the box's; the next lets go.
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    ok(pg.evaluate(STATE)["entry"] is None, say + "Escape leaves the box, and again lets go")

    # The scale.
    z1 = pg.evaluate(Z)
    pg.click(".zin")
    z2 = pg.evaluate(Z)
    ok(abs(z2 / z1 - 1.25) < 0.01, say + f"+ enlarges by a quarter ({z1:.2f} to {z2:.2f})")
    box = pg.evaluate("(() => { const r = document.querySelector('.cview').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    under = """(p) => { const s = document.querySelector('.csize').getBoundingClientRect(), z = %s;
        return [(p[0] - s.left) / z, (p[1] - s.top) / z]; }""" % Z
    at = [box[0] + box[2] * 0.3, box[1] + box[3] * 0.6]
    a = pg.evaluate(under, at)
    pg.mouse.move(*at)
    pg.keyboard.down("Control")
    pg.mouse.wheel(0, -240)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(150)
    z3, c = pg.evaluate(Z), pg.evaluate(under, at)
    ok(z3 > z2 and abs(a[0] - c[0]) < 3 and abs(a[1] - c[1]) < 3,
       say + f"Ctrl + wheel enlarges about the pointer ({z2:.2f} to {z3:.2f}, the place under it kept to {abs(a[0] - c[0]):.1f}, {abs(a[1] - c[1]):.1f})")
    # A mouse's drag moves the chart, and its end chooses nothing.
    l0 = pg.evaluate("[document.querySelector('.cview').scrollLeft, document.querySelector('.cview').scrollTop]")
    pg.mouse.move(box[0] + 500, box[1] + 400)
    pg.mouse.down()
    pg.mouse.move(box[0] + 380, box[1] + 310, steps=6)
    pg.mouse.up()
    l1 = pg.evaluate("[document.querySelector('.cview').scrollLeft, document.querySelector('.cview').scrollTop]")
    ok(abs(l1[0] - l0[0] - 120) < 3 and abs(l1[1] - l0[1] - 90) < 3 and pg.evaluate(STATE)["entry"] is None,
       say + f"a mouse's drag moves the chart with it, and chooses nothing ({l0} to {l1})")
    pg.click(".zfit")
    ok(until(pg, "Math.abs(%s - %r) < 0.001 && document.querySelector('.cview').scrollTop === 0" % (Z, z0)),
       say + "Whole chart returns to the whole width, at the top")

    # From the index.
    pg.goto(BASE + "/i/michael-sons", wait_until="load")
    pg.click('main a[href="/cosmology#michael"]')
    pg.wait_for_load_state("load")
    ok(until(pg, "location.pathname === '/cosmology' && (document.querySelector('.ci.on') || {dataset: {}}).dataset.id === 'michael'"),
       say + "a headword's page in the index goes to its card, chosen")
    ok(until(pg, "Math.round(scrollY) === 0", 1500) and pg.evaluate(SEEN, "michael"),
       say + "which is in the window, the page at its top")
    ok(not errors, say + "no script error: " + "; ".join(errors[:3]))
    ctx.close()


def phone(b) -> None:
    say = "[a phone, Russian] "
    ctx, pg, errors = fresh(b, {"lang": "ru"}, w=390, h=800, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg.goto(BASE + "/cosmology", wait_until="load")
    pg.wait_for_timeout(400)
    v = pg.evaluate("(() => { const r = document.querySelector('.cview').getBoundingClientRect(); return [r.top, r.height, innerHeight]; })()")
    ok(v[1] >= 0.5 * v[2] and v[0] + v[1] <= v[2] + 1, say + f"the chart has {v[1] / v[2]:.0%} of the screen, and ends at its foot")
    ok(abs(pg.evaluate(Z) - 0.75) < 0.01 and pg.evaluate("document.querySelector('.cview').scrollLeft") > 50,
       say + "it opens at three quarters of its size, on its first unit")
    pg.tap('.cp[data-id="son"]')
    ok(until(pg, "!!document.querySelector('.ci.on')"), say + "a tap on a card shows its entry")
    r = pg.evaluate("(() => { const r = document.querySelector('.ci.on').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, innerWidth, innerHeight]; })()")
    ok(r[0] >= 0 and r[2] <= r[4] and r[3] <= r[5] and r[1] > r[5] * 0.35,
       say + "along the foot of the screen, within it")
    ok(pg.evaluate("Math.round(scrollY)") == 0, say + "and the page has not moved")
    # A finger's drag on the chart is the window's own scrolling.
    cdp = ctx.new_cdp_session(pg)
    t0 = pg.evaluate("[document.querySelector('.cview').scrollLeft, document.querySelector('.cview').scrollTop]")
    x, y = 200.0, v[0] + 150
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for i in range(1, 13):
        # Aslant by half a right angle: nearer either axis, Chrome holds a
        # finger's scroll to that axis, here as in any window that scrolls.
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x - 8 * i, "y": y - 8 * i, "id": 1}]})
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(120)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(500)
    t1 = pg.evaluate("[document.querySelector('.cview').scrollLeft, document.querySelector('.cview').scrollTop]")
    ok(t1[0] > t0[0] + 30 and t1[1] > t0[1] + 50 and pg.evaluate("Math.round(scrollY)") == 0,
       say + f"a finger's drag moves the chart both ways, and not the page ({t0} to {t1})")
    # Two fingers spread: the chart larger, about the point between them, and
    # the page itself as it was.
    pg.keyboard.press("Escape")
    z0 = pg.evaluate(Z)
    vv0 = pg.evaluate("visualViewport.scale")
    cx, cy = 195.0, v[0] + 220
    pts = lambda d: [{"x": cx - d, "y": cy, "id": 1}, {"x": cx + d, "y": cy, "id": 2}]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pts(40)})
    for d in range(44, 121, 4):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pts(d)})
        pg.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(300)
    z1 = pg.evaluate(Z)
    ok(z1 > z0 * 1.5 and pg.evaluate("visualViewport.scale") == vv0,
       say + f"two fingers spread enlarge the chart ({z0:.2f} to {z1:.2f}), and not the page")
    ok(not errors, say + "no script error: " + "; ".join(errors[:3]))
    ctx.close()


def plain(b) -> None:
    say = "[scripts off] "
    ctx, pg, errors = fresh(b, {}, java_script_enabled=False)
    pg.goto(BASE + "/cosmology", wait_until="load")
    # With scripts off nothing can be asked of the page by script: its markup is read.
    html = pg.content()
    ok('<div class="ctools" hidden' in html, say + "the tools that need them are hidden")
    ok(pg.locator(".ci").count() > 100 and pg.locator(".ci").first.is_visible(),
       say + "the entries are a list under the chart")
    pg.click('#c-michael')
    ok(pg.url.endswith("#michael") and pg.locator("#michael").is_visible(), say + "a card goes to its entry")
    ok(pg.locator("#michael h2").bounding_box()["y"] < 300, say + "which the browser has brought to the top")
    pg.click('#michael .conchart a')
    ok(pg.url.endswith("#c-michael"), say + "and its entry back to the card")
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        for lang, whole in (("en", False), ("ru", True), ("en", True)):
            desktop(b, lang, whole)
        phone(b)
        plain(b)
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
