"""The chart of the personalities, end to end, in Chrome (templates/
cosmology.html, static/cosmo.js; build/cosmo.py).

On a desktop in English and in Russian, with Whole paper off and on, since an
entry's sources are links of the book, which the Whole paper handler rewrites
(CLAUDE.md trap 44); on a phone, by touch, and its line at four widths in both
languages; and with scripts off:

  what is drawn: every unit's title no wider than his page drew it, which is
  what his lines were kept clear of; each language's lines and not the
  other's; no sign of three circles about one centre;

  a card chosen: its address, its two cards and its lines lit, the rest stood
  back, its entry under the line's end, and the page not moved for a card in
  view; what is chosen still lit with the mouse over another card; the same
  card again, and Escape, let go; a name in the entry chooses that one and
  brings it into the window; a source goes to the text, in the reader's unit,
  and Back returns to the chart at the scale and the place it was left at;

  a unit's title, a chip of the legend, the legend shut by a click elsewhere
  and by Escape, the search box in both alphabets, the far lines' switch;

  moving and scaling, the page itself scrolling: the wheel over the chart and
  over the entry's card, where it once did nothing (Tigran, 2026-11-14);
  Shift + wheel; the keys with nothing focused; the header gone up and the
  line left at the top, the header at the window's left however far right;
  the line's buttons, one held down, + - 0 and / on the keys, Ctrl + wheel
  over the chart and over the entry, a mouse's drag, the map;

  on a phone: the line one line from 320 px, the window's width the device's,
  a finger both ways, two fingers, the strip along the foot and its opening,
  the magnifier, the legend's sign, and a name chosen from the whole chart;

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
# The line's foot on the screen: under it the window is the chart's.
FOOT = "Math.max(0, document.querySelector('.cbar').getBoundingClientRect().bottom)"
# A card, and whether it is in the window, whole, under the line.
SEEN = """(id) => { const r = document.querySelector('.cp[data-id="' + id + '"]:not(.ghost)').getBoundingClientRect();
    return r.left >= 0 && r.right <= document.documentElement.clientWidth && r.top >= %s && r.bottom <= innerHeight; }""" % FOOT
# Where the page stands, and the chart's scale.
AT = "[Math.round(scrollX), Math.round(scrollY)]"
# What on the chart is under a point of the screen, in the chart's own px.
UNDER = """(p) => { const s = document.querySelector('.csize').getBoundingClientRect(), z = %s;
    return [(p[0] - s.left) / z, (p[1] - s.top) / z]; }""" % Z
# The middle of an element on the screen.
MID = """(sel) => { const r = document.querySelector(sel).getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2]; }"""
# The same, the element first brought into view by the least movement: within
# an entry that scrolls, and never the page for what the line holds.
# Its first line's middle: a link that wraps has no words at its box's.
NEAR = """(sel) => { const e = document.querySelector(sel); e.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    const r = e.getClientRects()[0]; return [r.left + r.width / 2, r.top + r.height / 2]; }"""
BOX = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom]; }"""
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


def bring(pg, sel: str, x: float = 320, y: float = 430) -> list[float]:
    """The page moved so that an element's corner stands at a point of the
    screen, and the point to click it at: Playwright's own bringing into view
    would move the page as it liked, and under the line."""
    pg.evaluate("""([sel, x, y]) => { const r = document.querySelector(sel).getBoundingClientRect();
        scrollBy({ left: r.left - x, top: r.top - y, behavior: 'instant' }); }""", [sel, x, y])
    pg.wait_for_timeout(80)
    r = pg.evaluate(BOX, sel)
    return [r[0] + min(20, (r[2] - r[0]) / 2), (r[1] + r[3]) / 2]


def rest(pg, ms: int = 3000) -> None:
    """Until the page stands still: a card chosen is brought into view by a
    smooth scroll, and a click aimed while it glides lands somewhere else
    (two checks of a phone's failed so, one run in three)."""
    end, last = time.time() + ms / 1000, None
    while time.time() < end:
        now = pg.evaluate(AT)
        if now == last:
            return
        last = now
        pg.wait_for_timeout(90)


def hit(pg, sel: str) -> None:
    """A click where the element stands, once the page is at rest.  Not
    Playwright's own click, which brings its element into view as it sees
    fit, and for a link that wraps aims between its lines."""
    rest(pg)
    pg.mouse.click(*pg.evaluate(NEAR, sel))


def tip(pg, sel: str) -> None:
    """A finger's tap where the element stands (hit, above)."""
    rest(pg)
    pg.touchscreen.tap(*pg.evaluate(NEAR, sel))


def chosen(pg, id_: str) -> bool:
    return until(pg, "(document.querySelector('.ci.on') || {dataset: {}}).dataset.id === %s" % json.dumps(id_))


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
    credit = pg.evaluate("document.querySelector('.cby').cloneNode(true)").__class__ and pg.evaluate(
        "(() => { const c = document.querySelector('.cby').cloneNode(true);"
        " c.querySelectorAll(document.documentElement.dataset.lang === 'ru' ? 'x-en' : 'x-ru').forEach(e => e.remove());"
        " return c.textContent.trim(); })()")
    ok(credit.startswith("Data source by Alexander Alyuev" if lang == "en" else "Источник данных — Александр Алюев")
       and "Автор" not in credit and not credit.startswith("By "), say + f"the credit is the data's: {credit!r}")
    ok(pg.evaluate("!document.querySelector('.ctools input[type=range]')")
       and pg.evaluate("document.querySelectorAll('.czoom .cbtn').length") == 3
       and pg.evaluate("document.querySelectorAll('.cpan .cbtn').length") == 4,
       say + "the line has - + Whole chart and four arrows, and no slider")
    z0 = pg.evaluate(Z)
    ok(0.5 < z0 <= 1 and pg.evaluate("document.querySelector('.csize').offsetWidth <= document.documentElement.clientWidth + 1"),
       say + f"it opens with the chart's whole width in the window, at {z0:.2f}")
    ok(pg.evaluate("document.documentElement.classList.contains('cchart')")
       and pg.evaluate("getComputedStyle(document.querySelector('.cview')).overflowY") == "visible"
       and pg.evaluate("document.documentElement.scrollHeight > 3 * innerHeight"),
       say + "the chart is the page's own, no window of its own")

    # The page scrolls, as a page of the text does: the header goes up and the
    # line stays; with nothing focused the keys move it.
    top0 = pg.evaluate(BOX, ".cbar")[1]
    pg.mouse.move(500, 600)
    pg.mouse.wheel(0, 600)
    ok(until(pg, "Math.round(scrollY) === 600"), say + "the wheel over the chart moves the page")
    ok(top0 > 60 and pg.evaluate(BOX, ".top")[3] < 0 and abs(pg.evaluate(BOX, ".cbar")[1]) < 1
       and pg.evaluate(BOX, ".chead")[3] <= 1,
       say + "the header and the chart's name have gone up, and the line is left at the window's top")
    a0 = pg.evaluate(AT)
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("PageDown")
    ok(until(pg, "Math.round(scrollY) > %d" % (a0[1] + 400)) and pg.evaluate("document.activeElement === document.body"),
       say + "the keys move it with nothing focused")

    # A card chosen: one in view, so the page stays where it is.
    at = bring(pg, '.cp[data-id="michael"]:not(.ghost)')
    a0 = pg.evaluate(AT)
    pg.mouse.click(*at)
    ok(chosen(pg, "michael"), say + "a click on a card shows its entry")
    s = pg.evaluate(STATE)
    joined = pg.evaluate(JOINED, "michael")
    ok(s["hash"] == "#michael" and s["on"] == ["michael", "~michael"] and s["entry"] == "michael",
       say + f"its address names it, and both its cards are lit: {s['hash']} {s['on']}")
    ok(s["lines"] == joined and s["focus"] and s["rel"] >= 10,
       say + f"its {joined} lines are lit with what they join it to ({s['rel']} cards), the rest stood back")
    pg.wait_for_timeout(350)        # a line's colour changes over a fifth of a second
    ok(pg.evaluate(AT) == a0, say + f"and the page has not moved, the card being in view ({a0})")
    head = pg.evaluate("""(() => { const shown = [...document.querySelectorAll('.ce.origin.on .l')]
          .find(x => getComputedStyle(x.parentNode).display !== 'none');
        return [getComputedStyle(shown).markerEnd, getComputedStyle(shown).stroke,
                getComputedStyle(document.querySelector('#cm-on path')).fill]; })()""")
    ok("cm-on" in head[0] and head[1] == head[2], say + f"a lit line's arrowhead is lit with it ({head[2]})")
    far = pg.evaluate("[...document.querySelectorAll('.ce.far.on')].filter(g => getComputedStyle(g).display !== 'none').length")
    ok(far > 0, say + f"its far lines are shown with it ({far})")
    e = pg.evaluate(BOX, ".ci.on")
    foot = pg.evaluate(FOOT)
    ok(e[1] >= foot and e[2] <= pg.evaluate("document.documentElement.clientWidth") and e[0] > 600 and e[3] <= 900,
       say + "its entry hangs from the line's end, within the window")

    # What is chosen stays lit with the mouse over another card.
    other = pg.evaluate("""(() => { const a = [...document.querySelectorAll('.cp:not(.on):not(.rel)')].find(a => {
          const r = a.getBoundingClientRect(); return r.top > 120 && r.bottom < innerHeight - 20 && r.left > 20 && r.right < 800; });
        const r = a.getBoundingClientRect(); return [r.left + 60, r.top + 25]; })()""")
    pg.mouse.move(*other)
    pg.wait_for_timeout(120)
    s2 = pg.evaluate(STATE)
    ok(s2["on"] == s["on"] and s2["lines"] == s["lines"] and s2["rel"] == s["rel"],
       say + "what is chosen stays lit with the mouse over another card")

    # The wheel over the entry's card, where it once did nothing: the entry
    # first, the page after, and Ctrl + wheel the chart's scale there too.
    mid = pg.evaluate(MID, ".ci.on")
    pg.mouse.move(*mid)
    a0, z1 = pg.evaluate(AT), pg.evaluate(Z)
    for _ in range(8):
        pg.mouse.wheel(0, 300)
        pg.wait_for_timeout(60)
    ok(until(pg, "Math.round(scrollY) > %d" % (a0[1] + 300)),
       say + f"the wheel over the entry's card goes on to the page ({a0[1]} to {pg.evaluate(AT)[1]})")
    pg.keyboard.down("Control")
    pg.mouse.wheel(0, -240)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(150)
    z2 = pg.evaluate(Z)
    ok(z2 > z1 * 1.3, say + f"and Ctrl + wheel there scales the chart ({z1:.2f} to {z2:.2f})")
    pg.mouse.move(400, 500)
    a0 = pg.evaluate(AT)
    pg.keyboard.down("Shift")
    pg.mouse.wheel(0, 300)
    pg.keyboard.up("Shift")
    ok(until(pg, "Math.round(scrollX) === %d" % (a0[0] + 300)) and pg.evaluate(AT)[1] == a0[1],
       say + "Shift + wheel moves it sideways")
    ok(abs(pg.evaluate(BOX, ".cbar")[0]) < 1 and abs(pg.evaluate(BOX, ".cbar")[2] - pg.evaluate("document.documentElement.clientWidth")) < 1,
       say + "the line as wide as the window, at its left, however far right the page")
    pg.evaluate("scrollTo({ top: 0, behavior: 'instant' })")
    pg.wait_for_timeout(80)
    t = pg.evaluate(BOX, ".top")
    ok(pg.evaluate(AT)[0] > 200 and abs(t[0]) < 1 and abs(t[2] - pg.evaluate("document.documentElement.clientWidth")) < 1
       and abs(pg.evaluate(BOX, ".chead")[0]) < 1,
       say + "and at the top the site's header and the chart's name are at the window's left too")

    # A name in the entry chooses that one, wherever it is.
    hit(pg, '.ci.on a[href="#lifec"]')
    ok(chosen(pg, "lifec"), say + "a name in the entry chooses that personality")
    ok(until(pg, "(%s)('lifec')" % SEEN), say + "and brings its card into the window, under the line")
    pg.go_back()
    ok(chosen(pg, "michael"), say + "Back returns to the card before")

    # A source is a link of the book, in the reader's unit; Back returns to
    # the chart as it was left, its scale and its place.
    until(pg, "(%s)('michael')" % SEEN)
    pg.wait_for_timeout(700)        # the page at rest, and this entry of the history told
    left = pg.evaluate("[%s, %s]" % (Z, AT))
    href = pg.evaluate("document.querySelector('.ci.on a.cref').getAttribute('href')")
    pg.click(".ci.on a.cref")       # Playwright's own, which waits for the page it goes to
    pg.wait_for_load_state("load")
    want = href if whole else href + ":0"
    ok(until(pg, "location.pathname === %s" % json.dumps(want)),
       say + f"a source goes to the text, {href} as {want}: at {pg.evaluate('location.pathname + location.hash')}")
    ok(not pg.evaluate("document.documentElement.classList.contains('cchart')"), say + "a page of the text again, as it was")
    pg.go_back()
    pg.wait_for_load_state("load")
    ok(until(pg, "location.pathname === '/cosmology'") and chosen(pg, "michael"),
       say + "and Back returns to the chart, the card chosen again")
    pg.wait_for_timeout(400)
    back = pg.evaluate("[%s, %s]" % (Z, AT))
    ok(abs(back[0] - left[0]) < 0.001 and abs(back[1][0] - left[1][0]) <= 2 and abs(back[1][1] - left[1][1]) <= 2,
       say + f"at the scale and the place it was left at ({left} and {back})")

    # Letting go.
    pg.keyboard.press("Escape")
    s = pg.evaluate(STATE)
    ok(s["hash"] == "" and not s["on"] and not s["focus"] and s["entry"] is None, say + "Escape lets go")
    at = bring(pg, '.cp[data-id="seraph"]')
    pg.mouse.move(*at)
    pg.wait_for_timeout(120)
    s = pg.evaluate(STATE)
    ok(s["focus"] and s["lines"] > 0 and s["entry"] is None, say + "with nothing chosen a mouse over a card lights its lines")
    pg.mouse.click(*at)
    chosen(pg, "seraph")
    pg.mouse.click(*at)
    s = pg.evaluate(STATE)
    ok(s["hash"] == "" and not s["on"] and s["entry"] is None, say + "and the same card again lets go")
    pg.mouse.move(5, 300)

    # A unit.
    pg.mouse.click(*bring(pg, '.cut[data-id="salv"]'))
    chosen(pg, "salv")
    s = pg.evaluate(STATE)
    inside = pg.evaluate("document.querySelectorAll('.cp[data-u=\"salv\"]').length")
    ok(s["units"] == ["salv"] and s["entry"] == "salv" and s["rel"] >= inside > 5,
       say + f"a unit's title chooses the unit: its {inside} cards lit, its entry shown")
    pg.keyboard.press("Escape")

    # The legend's chips; it shuts on a click elsewhere and on Escape.
    hit(pg, ".clegend > summary")
    lb = pg.evaluate(BOX, ".clbody")
    ok(lb[1] >= pg.evaluate(FOOT) - 1 and lb[3] <= 900 and lb[2] <= pg.evaluate("document.documentElement.clientWidth"),
       say + "the legend opens under the line, within the window")
    hit(pg, '.clegend .cchip[data-k="group:angel"]')
    angels = pg.evaluate("[...document.querySelectorAll('.cp')].filter(a => (' ' + a.dataset.k + ' ').includes(' group:angel ')).length")
    s = pg.evaluate(STATE)
    ok(s["rel"] == angels > 3 and pg.evaluate("document.querySelector('.clegend .cchip.on').dataset.k") == "group:angel",
       say + f"a chip lights every card of its kind ({angels} angels)")
    hit(pg, '.clegend .cchip[data-k="group:angel"]')
    ok(pg.evaluate("document.querySelectorAll('.cp.rel, .cchip.on').length") == 0, say + "and again lets go")
    shown = "[...document.querySelectorAll('.ce.far')].filter(g => getComputedStyle(g).display !== 'none').length"
    before = pg.evaluate(shown)
    hit(pg, ".cfar input")
    after = pg.evaluate(shown)
    ok(before == 0 and after > 10, say + f"the far lines' switch shows them all ({before} to {after})")
    hit(pg, ".cfar input")
    ok(pg.evaluate("document.querySelector('.clegend').open"), say + "the legend stays open while it is used")
    pg.mouse.click(300, 500)
    ok(not pg.evaluate("document.querySelector('.clegend').open"), say + "and shuts on a click elsewhere")
    hit(pg, ".clegend > summary")
    pg.keyboard.press("Escape")
    ok(not pg.evaluate("document.querySelector('.clegend').open"), say + "and on Escape")

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
    pg.keyboard.press("/")
    ok(pg.evaluate("document.activeElement === document.querySelector('.cq')"), say + "/ goes to the search box")
    pg.keyboard.press("Escape")

    # The scale: the line's buttons, the keys, Ctrl + wheel about the pointer.
    hit(pg, ".zfit")
    pg.wait_for_timeout(100)
    z1 = pg.evaluate(Z)
    hit(pg, ".zin")
    z2 = pg.evaluate(Z)
    ok(abs(z2 / z1 - 1.25) < 0.01, say + f"+ enlarges by a quarter ({z1:.2f} to {z2:.2f})")
    hit(pg, ".zout")
    ok(abs(pg.evaluate(Z) - z1) < 0.005, say + "and - puts it back")
    pg.keyboard.press("+")
    pg.keyboard.press("+")
    zk = pg.evaluate(Z)
    pg.keyboard.press("-")
    ok(abs(zk / z1 - 1.5625) < 0.02 and abs(pg.evaluate(Z) / zk - 0.8) < 0.01,
       say + f"+ and - on the keys scale it too ({z1:.2f}, {zk:.2f}, {pg.evaluate(Z):.2f})")
    z2 = pg.evaluate(Z)
    at = [420.0, 560.0]
    a = pg.evaluate(UNDER, at)
    pg.mouse.move(*at)
    pg.keyboard.down("Control")
    pg.mouse.wheel(0, -240)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(150)
    z3, c = pg.evaluate(Z), pg.evaluate(UNDER, at)
    ok(z3 > z2 and abs(a[0] - c[0]) < 3 and abs(a[1] - c[1]) < 3,
       say + f"Ctrl + wheel enlarges about the pointer ({z2:.2f} to {z3:.2f}, the place under it kept to {abs(a[0] - c[0]):.1f}, {abs(a[1] - c[1]):.1f})")
    # A mouse's drag moves the page with it, and its end chooses nothing.
    l0 = pg.evaluate(AT)
    pg.mouse.move(600, 500)
    pg.mouse.down()
    pg.mouse.move(480, 410, steps=6)
    pg.mouse.up()
    l1 = pg.evaluate(AT)
    ok(abs(l1[0] - l0[0] - 120) < 3 and abs(l1[1] - l0[1] - 90) < 3 and pg.evaluate(STATE)["entry"] is None,
       say + f"a mouse's drag moves the chart with it, and chooses nothing ({l0} to {l1})")
    pg.mouse.move(700, 600)
    ok(pg.evaluate(AT) == l1 and not pg.evaluate("document.querySelector('.cview').classList.contains('drag')"),
       say + "and the chart does not follow the mouse once the button is up")
    # The arrows: a third of the window a press, and on while held.
    for cls, axis, sign in ((".pr", 0, 1), (".pd", 1, 1), (".pl", 0, -1), (".pu", 1, -1)):
        l0 = pg.evaluate(AT)
        hit(pg, cls)
        pg.wait_for_timeout(200)
        rest(pg)
        l1 = pg.evaluate(AT)
        ok(sign * (l1[axis] - l0[axis]) > 200 and l1[1 - axis] == l0[1 - axis],
           say + f"the arrow {cls} moves the page ({l0} to {l1})")
    l0 = pg.evaluate(AT)
    pg.mouse.move(*pg.evaluate(MID, ".pd"))
    pg.mouse.down()
    pg.wait_for_timeout(1300)
    pg.mouse.up()
    pg.wait_for_timeout(100)
    l1 = pg.evaluate(AT)
    pg.wait_for_timeout(500)
    ok(l1[1] - l0[1] > 600 and pg.evaluate(AT) == l1,
       say + f"held down it goes on, and stops when let go ({l1[1] - l0[1]} px in 1.3 s)")
    # The map: where the window stands on the chart, and a click in it to go there.
    m = pg.evaluate(BOX, ".cmap")
    ok(m is not None and m[0] >= 0 and m[3] <= 900 and 60 < m[2] - m[0] < 100,
       say + "the small map stands at the window's lower left")
    win = pg.evaluate("""(() => { const w = document.querySelector('.cmap .cmw'), s = document.querySelector('.csize').getBoundingClientRect(), z = %s;
        return [Math.abs(+w.getAttribute('y') - (%s - s.top) / z), +w.getAttribute('height'), (innerHeight - %s) / z]; })()""" % (Z, FOOT, FOOT))
    ok(win[0] < 3 and abs(win[1] - win[2]) < 3, say + "with the window's place marked on it")
    pg.mouse.click((m[0] + m[2]) / 2, m[1] + (m[3] - m[1]) * 0.8)
    pg.wait_for_timeout(150)
    mid = pg.evaluate(UNDER, [pg.evaluate("document.documentElement.clientWidth / 2"), (pg.evaluate(FOOT) + 900) / 2])
    hgt = pg.evaluate("parseFloat(document.querySelector('.csize').style.getPropertyValue('--h'))")
    ok(abs(mid[1] / hgt - 0.8) < 0.03, say + f"a click in the map goes there ({mid[1] / hgt:.2f} of the chart's height)")
    pg.keyboard.press("0")
    ok(until(pg, "Math.abs(%s - %r) < 0.001" % (Z, z0)) and pg.evaluate(AT)[0] == 0,
       say + "0 on the keys, as Whole chart, returns to the whole width")

    # From the index.
    pg.goto(BASE + "/i/michael-sons", wait_until="load")
    pg.click('main a[href="/cosmology#michael"]')
    pg.wait_for_load_state("load")
    ok(until(pg, "location.pathname === '/cosmology'") and chosen(pg, "michael"),
       say + "a headword's page in the index goes to its card, chosen")
    ok(until(pg, "(%s)('michael')" % SEEN), say + "which is in the window, under the line")
    ok(not errors, say + "no script error: " + "; ".join(errors[:3]))
    ctx.close()


def touch(ctx, pg):
    cdp = ctx.new_cdp_session(pg)

    def send(kind, pts):
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})
    return send


def phone(b) -> None:
    say = "[a phone, Russian] "
    ctx, pg, errors = fresh(b, {"lang": "ru"}, w=390, h=800, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg.goto(BASE + "/cosmology", wait_until="load")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("innerWidth") == 390 and pg.evaluate("visualViewport.scale") == 1
       and pg.evaluate("document.documentElement.scrollWidth") > 1000,
       say + "the window is the device's width, the page as wide as the chart (the viewport's least scale)")
    ok(abs(pg.evaluate(Z) - 0.75) < 0.01 and pg.evaluate("Math.round(scrollX)") > 50,
       say + "it opens at three quarters of its size, on its first unit")
    ok(abs(pg.evaluate(BOX, ".top")[0]) < 1 and abs(pg.evaluate(BOX, ".cbar")[0]) < 1,
       say + "the header and the line at the window's left all the same")
    send = touch(ctx, pg)

    def stroke(x, y, dx, dy, n=14):
        send("touchStart", [{"x": x, "y": y, "id": 1}])
        for i in range(1, n + 1):
            send("touchMove", [{"x": x + dx * i / n, "y": y + dy * i / n, "id": 1}])
            pg.wait_for_timeout(16)
        pg.wait_for_timeout(120)
        send("touchEnd", [])
        pg.wait_for_timeout(600)

    # A finger moves the page, as on a page of the text: the header goes up,
    # the line stays.
    stroke(200, 650, 0, -420)
    ok(pg.evaluate("Math.round(scrollY)") > 300 and pg.evaluate(BOX, ".top")[3] < 0 and abs(pg.evaluate(BOX, ".cbar")[1]) < 1,
       say + "a finger up moves the page: the header gone, the line at the window's top")
    ok(pg.evaluate(BOX, ".cbar")[3] < 60, say + f"which is one line ({pg.evaluate(BOX, '.cbar')[3]:.0f} px of 800)")
    # Aslant by half a right angle: nearer either axis, Chrome holds a
    # finger's scroll to that axis, here as in any page that scrolls.
    t0 = pg.evaluate(AT)
    stroke(250, 600, -120, -120)
    t1 = pg.evaluate(AT)
    ok(t1[0] > t0[0] + 60 and t1[1] > t0[1] + 60, say + f"a finger aslant moves it both ways ({t0} to {t1})")
    # Two fingers spread: the chart larger, about the point between them, and
    # the page itself as it was.
    z0 = pg.evaluate(Z)
    cx, cy = 195.0, 420.0
    pts = lambda d: [{"x": cx - d, "y": cy, "id": 1}, {"x": cx + d, "y": cy, "id": 2}]
    a = pg.evaluate(UNDER, [cx, cy])
    send("touchStart", pts(40))
    for d in range(44, 81, 4):
        send("touchMove", pts(d))
        pg.wait_for_timeout(16)
    send("touchEnd", [])
    pg.wait_for_timeout(300)
    z1, c = pg.evaluate(Z), pg.evaluate(UNDER, [cx, cy])
    ok(z1 > z0 * 1.5 and pg.evaluate("visualViewport.scale") == 1 and pg.evaluate("innerWidth") == 390,
       say + f"two fingers spread enlarge the chart ({z0:.2f} to {z1:.2f}), and not the page")
    ok(abs(a[0] - c[0]) < 40 and abs(a[1] - c[1]) < 40, say + f"about the point between them (kept to {abs(a[0] - c[0]):.0f}, {abs(a[1] - c[1]):.0f})")
    tip(pg, ".zout")
    tip(pg, ".zout")

    # A card chosen: a strip along the foot, which a tap opens whole.
    at = bring(pg, '.cp[data-id="son"]', 60, 300)
    pg.touchscreen.tap(*at)
    ok(chosen(pg, "son"), say + "a tap on a card shows its entry")
    r = pg.evaluate(BOX, ".ci.on")
    ok(r[0] >= 0 and r[2] <= 390 and r[3] <= 800 and r[3] - r[1] <= 0.25 * 800 and r[1] > 0.6 * 800,
       say + f"a strip along the foot of the screen, {(r[3] - r[1]) / 800:.0%} of it")
    ok(pg.evaluate("getComputedStyle(document.querySelector('.ci.on dl')).display") == "none"
       and pg.evaluate("document.querySelector('.ci.on h2').getBoundingClientRect().height > 0"),
       say + "with its name and what it is, and no more")
    pg.touchscreen.tap((r[0] + r[2]) / 2 - 40, (r[1] + r[3]) / 2)
    pg.wait_for_timeout(150)
    r2 = pg.evaluate(BOX, ".ci.on")
    ok(r2[3] - r2[1] > (r[3] - r[1]) * 1.6 and r2[3] - r2[1] <= 0.7 * 800 + 1
       and pg.evaluate("getComputedStyle(document.querySelector('.ci.on dl')).display") != "none",
       say + f"a tap on it opens it whole ({(r2[3] - r2[1]) / 800:.0%} of the screen)")
    tip(pg, ".ci.on .cmore")
    pg.wait_for_timeout(100)
    r3 = pg.evaluate(BOX, ".ci.on")
    ok(abs((r3[3] - r3[1]) - (r[3] - r[1])) < 2, say + "and its sign folds it again")
    tip(pg, ".ci.on .x")
    ok(pg.evaluate(STATE)["entry"] is None, say + "its × lets go")

    # The magnifier opens the box across the line.
    tip(pg, ".cqb")
    ok(until(pg, "document.activeElement === document.querySelector('.cq')"), say + "the magnifier opens the search box")
    q, bar = pg.evaluate(BOX, ".cq"), pg.evaluate(BOX, ".cbar")
    ok(q[2] - q[0] > 340 and q[1] >= bar[1] and q[3] <= bar[3]
       and pg.evaluate("getComputedStyle(document.querySelector('.zin')).visibility") == "hidden",
       say + "across the line, in the buttons' place")
    pg.keyboard.type("михаил")
    ok(until(pg, "document.querySelectorAll('.cres li[data-n]').length > 0"), say + "it finds a name typed")
    li = pg.evaluate(MID, ".cres li[data-n]")
    pg.touchscreen.tap(*li)
    ok(until(pg, "!!document.querySelector('.ci.on')") and until(pg, "!document.querySelector('.cfind').classList.contains('open')")
       and pg.evaluate("getComputedStyle(document.querySelector('.zin')).visibility") == "visible",
       say + f"a tap on what it found chooses it ({pg.evaluate(STATE)['entry']}), and the line is the buttons' again")
    tip(pg, ".ci.on .x")
    tip(pg, ".cqb")
    tip(pg, ".cqx")
    ok(until(pg, "!document.querySelector('.cfind').classList.contains('open')"), say + "the box's × shuts it")

    # The legend's sign.
    tip(pg, ".clegend > summary")
    lb = pg.evaluate(BOX, ".clbody")
    ok(pg.evaluate("document.querySelector('.clegend').open") and lb[0] >= 0 and lb[2] <= 390 and lb[3] <= 800,
       say + f"the legend's sign opens it, within the screen ({lb})")
    tip(pg, '.clegend .cchip[data-k="group:angel"]')
    ok(not pg.evaluate("document.querySelector('.clegend').open") and pg.evaluate(STATE)["rel"] > 3,
       say + "a chip lights its cards and shuts the legend, which lay over them")
    pg.keyboard.press("Escape")

    # Whole chart: its whole width in the window, where no name can be read;
    # a name chosen from there comes back to a scale it can be read at.
    tip(pg, ".zfit")
    pg.wait_for_timeout(150)
    zf = pg.evaluate(Z)
    ok(abs(zf - 390 / pg.evaluate("parseFloat(document.querySelector('.csize').style.getPropertyValue('--w'))")) < 0.005
       and pg.evaluate("document.querySelector('.cview').classList.contains('far')"),
       say + f"Whole chart shows its whole width ({zf:.2f})")
    tip(pg, ".cqb")
    pg.keyboard.type("Gabriel")
    until(pg, "document.querySelectorAll('.cres li[data-n]').length > 0")
    pg.touchscreen.tap(*pg.evaluate(MID, ".cres li[data-n]"))
    ok(until(pg, "!!document.querySelector('.ci.on')") and until(pg, "%s >= 0.74" % Z),
       say + f"a name chosen from there brings the scale back ({pg.evaluate(Z):.2f})")
    ok(until(pg, "(() => { const r = document.querySelector('.cp.on').getBoundingClientRect();"
                 " return r.left >= 0 && r.right <= 390 && r.top >= %s && r.bottom <= document.querySelector('.ci.on').getBoundingClientRect().top; })()" % FOOT),
       say + "with its card in view, between the line and the strip")
    # The arrows, a phone having no keys.
    l0 = pg.evaluate(AT)
    tip(pg, ".pd")
    pg.wait_for_timeout(200)
    tip(pg, ".pr")
    pg.wait_for_timeout(200)
    rest(pg)
    l1 = pg.evaluate(AT)
    ok(l1[0] - l0[0] > 100 and l1[1] - l0[1] > 150, say + f"the arrows move the page ({l0} to {l1})")
    ok(not errors, say + "no script error: " + "; ".join(errors[:3]))
    ctx.close()


def line(b) -> None:
    """The line is one line on a phone, from 320 px, in both languages (Tigran,
    2026-11-14: "Can we fit all that on a single line?")."""
    for lang in ("en", "ru"):
        for w in (320, 360, 390, 412):
            ctx, pg, errors = fresh(b, {"lang": lang}, w=w, h=780, has_touch=True, is_mobile=True, device_scale_factor=2)
            pg.goto(BASE + "/cosmology", wait_until="load")
            pg.wait_for_timeout(250)
            m = pg.evaluate("""(() => { const bar = document.querySelector('.cbar').getBoundingClientRect(),
                  b = [...document.querySelectorAll('.cbar .cbtn:not(.cqx), .clegend > summary')].map(e => e.getBoundingClientRect());
                return { h: bar.height, n: b.length, tops: Math.max(...b.map(r => r.top)) - Math.min(...b.map(r => r.top)),
                         left: Math.min(...b.map(r => r.left)), right: Math.max(...b.map(r => r.right)),
                         size: [Math.min(...b.map(r => r.width)), Math.max(...b.map(r => r.width))],
                         over: b.some((r, i) => i && r.left < b[i - 1].right - 0.5),
                         sw: document.querySelector('.cbar').scrollWidth }; })()""")
            ok(m["n"] == 9 and m["tops"] < 1.5 and m["h"] < 56 and m["left"] >= 0 and m["right"] <= w and not m["over"]
               and m["size"][0] >= 26 and m["sw"] <= w,
               f"[a phone {w} px, {lang}] the line is one line of nine buttons, {m['size'][0]:.0f} px each, {m['h']:.0f} px tall")
            ok(not errors, f"[a phone {w} px, {lang}] no script error: " + "; ".join(errors[:3]))
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
        line(b)
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
