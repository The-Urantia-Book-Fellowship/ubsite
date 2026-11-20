"""The translations in parallel columns, in Chrome: where the columns come and
where the folds, and what the columns look like.

No setting since 2026-11-16 (Tigran): the page is in columns wherever each
column would be at least --mincol wide, 35 of the measure's 70 characters,
and in folds where it would not (ub.js cmpFits, ub.css .cprobe).  So first,
`room`: at a desk's windows from 1280 to 2560 px, with the Contents and the
index open and folded, one, two and three translations ticked, and under
62rem a phone, a tablet and a phone lying down, the page is in columns or in
folds as the rule says; in columns no column is under the least, and the
page is no wider than its window; in Measured, where the window has room,
each column is the measure; a fold of the Contents or of the index turns
the page into columns and back in place, the letter at the window's top
kept at its height, brought out from under the columns' names; so does the
window made wider and narrower, and the text's size; a paper one of the
translations has not has a column fewer, and room where the paper before
had none; a part's page is in columns by the same rule; the head script's
guess, that a page will be as the last was, is put right where it is wrong;
and a browser that kept the setting, and a size by its old name, reads as
it did.

Then what the columns are (Tigran, 2026-11-15): the line that names them,
one to the page, at the window's top, each by its short name; and the box
of what a whole paper or section cites, in the margin, level with the
section's title.  Until that day `ub.js cmpDraw` put the names first in
every section's grid, where a sticky row stays only while its own section is
in view: on the whole paper's page the next section's row came up the page
under the one stuck at the top, two of them in the window at every
section's end.  Now the row is the article's own child, a grid of its own
with the text's tracks.

With Whole paper off and on (CLAUDE.md trap 44), Aivazian's translation
ticked, in a window 1920 px wide, which has room for two columns with the
Contents and the index open: there is one row of names, the article's
child, before its first section and in none; the names are Uversa Press and
each translation's short name, Aivazian, USGNY, and no title of the book;
each name stands over its column, to the tenth of a pixel, at each of the
grid's four sets of tracks (Width measured and full, the index shown and
folded or off) and with three columns; scrolled to the end of a section
there is still one, at the window's top, and at the page's end too; a
section's title on the whole paper's page has the room it has without
columns, above and below; the box of what the whole paper cites, and a
section's, stands in the margin's column, clear of the text's, its top
level with the head's on the whole paper's page and its foot with the
section's title on a section's page, the section's first paragraph under
both, its entries links that the pointer meets and a click follows (the row
of the heads lay over them for an hour), and is not shown with the index
folded or off; a box of five lines or more is folded to its line, which
says how many entries it holds and opens and folds it, on the whole paper's
page and a section's, and not under 62rem nor out of columns; a click on a
section's title names that section's first paragraph, and on a
translation's title that translation's, with and without columns, never the
first on the screen; a paragraph named by the address is put under the
names, not behind them; a column's × takes the column and leaves one row,
and the last one's takes the row; and a window too narrow takes it too,
wide again brings one back.  On a phone's screen there are no columns, and
the page is no wider than the screen.

    .venv/bin/python tools/compare_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8137 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate, like
preview_e2e.py: tests/test_compare.py holds the static facts.
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
PORT = "8137"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []

# The English of an element's words: the Russian, in <x-ru>, taken out
# (CLAUDE.md trap 33).
EN = """el => { if (!el) return ''; const c = el.cloneNode(true);
    c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent.trim(); }"""

# The rows of names: how many, where each hangs, and those in the window.
NAMES = """() => {
  const all = [...document.querySelectorAll('.cmpnames')];
  const art = document.querySelector('main.reader > article');
  return {
    n: all.length,
    child: all.length === 1 && all[0].parentElement === art,
    before: all.length === 1 && all[0].nextElementSibling === art.querySelector(':scope > section'),
    insec: document.querySelectorAll('section .cmpnames').length,
    shown: all.filter(e => getComputedStyle(e).display !== 'none').length,
    inwin: all.map(e => e.getBoundingClientRect()).filter(b => b.height && b.bottom > 0 && b.top < innerHeight)
              .map(b => [Math.round(b.top * 10) / 10, Math.round(b.bottom * 10) / 10]),
  };
}"""
# Each name's left edge and width, and each column's, by a section's heads.
EDGES = """() => {
  const r = e => { const b = e.getBoundingClientRect(); return [Math.round(b.left * 10) / 10, Math.round(b.width * 10) / 10]; };
  return { cn: [...document.querySelectorAll('.cmpnames > .cn')].map(r),
           ch: [...document.querySelector('article.cmp .cmphd').querySelectorAll(':scope > .ch')].map(r),
           last: [...[...document.querySelectorAll('article.cmp .cmphd')].pop().querySelectorAll(':scope > .ch')].map(r) };
}"""
# The names as they read.
WORDS = "() => [...document.querySelectorAll('.cmpnames > .cn')].map(c => c.querySelector('b').textContent)"
LABEL = {"ud": "Aivazian", "urantia-ru": "USGNY", "uf-ru": "UF-RUS"}
# A section's box of what the whole paper or section cites, and what it
# stands beside: the head's first cell, the margin's entries, the last of
# the text's columns, the section's first paragraph.
BOX = """(id) => {
  const sec = document.getElementById(id), box = sec.querySelector(':scope > .blanket');
  const r = e => e.getBoundingClientRect(), t = x => Math.round(x * 10) / 10;
  const b = r(box), c = r(sec.querySelector('.cmphd > .ch')), a = sec.querySelector('.grid > .row > .a');
  const last = r([...sec.querySelectorAll('.cmphd > .ch')].pop());
  return { shown: getComputedStyle(box).display !== 'none', left: t(b.left), top: t(b.top), bottom: t(b.bottom),
           headTop: t(c.top), headBottom: t(c.bottom), margin: a ? t(r(a).left) : null, cols: t(last.right),
           text: t(r(sec.querySelector('.grid > .row p.t')).top) };
}"""
# A link in a section's box: is it what the pointer meets?  The row of the
# heads spans the margin's track too, and lay over the box (2026-11-15).
LINK = """(id) => { const a = document.getElementById(id).querySelector(':scope > .blanket a');
  a.scrollIntoView({block: 'center'});
  const r = a.getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { href: a.getAttribute('href'), met: e.closest('a') === a, under: e.tagName + '.' + e.className }; }"""
# A section's box as a fold: marked to fold, opened, its line shown and what
# the line says of itself, its lists shown, its lines, and how far under the
# head's foot the section's text begins.
FOLD = """(id) => { const sec = document.getElementById(id), box = sec.querySelector(':scope > .blanket'), b = box.querySelector(':scope > .afold');
  const r = e => e.getBoundingClientRect(), on = e => getComputedStyle(e).display !== 'none';
  return { fold: box.classList.contains('cmpfold'), open: box.classList.contains('shown'), line: on(b),
           says: b.getAttribute('aria-expanded'), lists: [...box.querySelectorAll(':scope > ul')].every(on),
           lines: box.querySelectorAll(':scope > ul > li').length, tall: Math.round(r(box).height),
           under: Math.round(r(sec.querySelector('.grid > .row p.t')).top - r(sec.querySelector('.cmphd > .ch')).bottom) }; }"""
# Every box on the page is marked to fold if and only if it has five lines.
MARKS = """() => { const bs = [...document.querySelectorAll('main article > section > .blanket')];
  const n = b => b.querySelectorAll(':scope > ul > li').length;
  return { boxes: bs.length, long: bs.filter(b => n(b) >= 5).length, marked: bs.filter(b => b.classList.contains('cmpfold')).length,
           wrong: bs.filter(b => b.classList.contains('cmpfold') !== (n(b) >= 5)).length }; }"""
# What a tap has named: the English paragraph, or a translation's line with whose it is; and the running head.
# The English's (or a first text's) line, not a column's first line, which is
# a p.t too since 2026-11-20 (ub.js trLines, its ▶ in its stack).
NAMED = """() => ({ en: [...document.querySelectorAll('main p.t.named')].filter(p => !p.closest('.rc')).map(p => p.id),
  tr: [...document.querySelectorAll('main .rc p.rt.named')].map(p => p.closest('.rc').dataset.k + ' ' + p.dataset.ref),
  head: (h => h && !h.hidden ? h.querySelector('.ref').textContent : null)(document.querySelector('.runhead')) })"""
# The room round a section's title: from the last paragraph of the section
# before to the title, and from the title to the section's first paragraph.
ROOM = """(id) => {
  const sec = document.getElementById(id), cmp = !!document.querySelector('article.cmp');
  const h2 = sec.querySelector(cmp ? '.cmphd .ch:first-child h2' : ':scope > .papertop h2');
  const prev = sec.previousElementSibling.querySelector('.grid > .row:last-child p.t');
  const first = sec.querySelector('.grid > .row p.t'), a = h2.getBoundingClientRect();
  return [Math.round((a.top - prev.getBoundingClientRect().bottom) * 10) / 10,
          Math.round((first.getBoundingClientRect().top - a.bottom) * 10) / 10];
}"""
# Whether the page is in columns, and what shows it: the article's class and
# the root's, the names, the folds shown, each column's width against the
# least a column may be and the measure, and how far the page runs past its
# window.
STATE = """() => {
  const art = document.querySelector('main.reader > article'), root = document.documentElement, t = x => Math.round(x * 10) / 10;
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden;height:0;width:var(--mincol)';
  art.appendChild(probe);
  const min = probe.getBoundingClientRect().width;
  probe.style.width = 'var(--measure)';
  const measure = probe.getBoundingClientRect().width;
  probe.remove();
  const head = art.querySelector('.cmphd');
  return { cmp: art.classList.contains('cmp'), cls: root.classList.contains('compare'),
           names: art.querySelectorAll('.cmpnames > .cn').length,
           folds: [...art.querySelectorAll('.tf')].filter(e => getComputedStyle(e).display !== 'none').length,
           cols: head ? [...head.querySelectorAll(':scope > .ch')].map(c => t(c.getBoundingClientRect().width)) : [],
           min: t(min), measure: t(measure), over: root.scrollWidth - innerWidth,
           kept: localStorage.getItem('ub_cols'), frame: art.parentNode.style.getPropertyValue('--cols') };
}"""
# The letter in the middle of the line at the window's top, under the
# columns' names where they stand there, as ub.js placeNow takes it: kept on
# the window, to be found again (WHERE).
MARK = """() => {
  const nm = document.querySelector('article.cmp .cmpnames'), f = nm ? nm.getBoundingClientRect().bottom : 0;
  const p = [...document.querySelectorAll('main p.t[id]')].find(q => q.getBoundingClientRect().bottom > f + 40), r = p.getBoundingClientRect();
  for (let dy = 6; dy < 60; dy += 4) {
    const c = document.caretPositionFromPoint(r.left + r.width / 2, f + dy);
    if (!c || c.offsetNode.nodeType !== 3 || !p.contains(c.offsetNode) || !c.offsetNode.length) continue;
    window.__n = c.offsetNode; window.__at = Math.min(c.offset, c.offsetNode.length - 1);
    const q = document.createRange(); q.setStart(window.__n, window.__at); q.setEnd(window.__n, window.__at + 1);
    const rs = q.getClientRects();
    if (rs.length) return { para: p.id, y: Math.round(rs[0].top), floor: Math.round(f) };
  }
  return null;
}"""
WHERE = """() => {
  const q = document.createRange(); q.setStart(window.__n, window.__at); q.setEnd(window.__n, window.__at + 1);
  const nm = document.querySelector('article.cmp .cmpnames');
  return { y: Math.round(q.getClientRects()[0].top), floor: nm ? Math.round(nm.getBoundingClientRect().bottom) : 0,
           cmp: !!document.querySelector('article.cmp') };
}"""
# A part's page: the dividers shown, and where each stands.
PART = """() => {
  const d = [...document.querySelectorAll('.partpage .divider')].filter(e => getComputedStyle(e).display !== 'none');
  return { cls: document.documentElement.classList.contains('compare'), shown: d.length,
           lefts: d.map(e => Math.round(e.getBoundingClientRect().left)), widths: d.map(e => Math.round(e.getBoundingClientRect().width)),
           over: document.documentElement.scrollWidth - innerWidth };
}"""
TR = {1: "urantia-ru", 2: "urantia-ru uf-ru", 3: "ud urantia-ru uf-ru"}
# A section's end in the middle of the window.
TO = """(id) => { const s = document.getElementById(id); scrollTo(0, 0);
    scrollTo(0, s.getBoundingClientRect().top - innerHeight / 3); }"""


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, js: str, timeout: float = 10.0) -> bool:
    """Poll an expression until it is true (trap 41: evaluate waits for a
    promise, wait_for_function does not)."""
    end = time.time() + timeout
    while time.time() < end:
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(100)
    return False


# A desk's window with room for two columns beside the Contents and the
# index; three want the widest.
WIDE = (1920, 1000)
WIDEST = (2560, 1000)


def context(b, settings: dict, size=WIDE, phone: bool = False):
    view = {"width": size[0], "height": size[1]}
    ctx = (b.new_context(viewport=view, has_touch=True, is_mobile=True, service_workers="block")
           if phone else b.new_context(viewport=view, service_workers="block"))
    # A fresh context is a first visit, which the tour would meet (help.js).
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, errors


def drawn(pg) -> None:
    pg.wait_for_selector("article.cmp .cmphd", timeout=20000)
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(300)


def settled(pg) -> dict:
    """The page once ub.js has decided and drawn: the typefaces in, and the
    class and the article agreed."""
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(500)
    return pg.evaluate(STATE)


def room(b) -> None:
    """Where the columns come, and where the folds (Tigran, 2026-11-16)."""
    print("\nRoom for the columns: 15:1, by the window, the folds and the translations ticked")
    both, rail, index, none = {}, {"rail": "folded"}, {"margin": False}, {"rail": "folded", "margin": False}
    # (window, what is folded, translations ticked, in columns?).  Each is
    # clear of the edge by a character or more on this machine's Chrome; the
    # nearest, left out, are three columns at 1920 px with both open and two
    # on a phone 740 px wide lying down, each with room by less than one.
    cases = [((1280, 900), "the Contents and the index open", both, 1, False),
             ((1280, 900), "the Contents folded", rail, 1, True),
             ((1440, 900), "the Contents and the index open", both, 1, False),
             ((1440, 900), "the index folded", index, 1, True),
             ((1440, 900), "the Contents folded", rail, 2, False),
             ((1440, 900), "both folded", none, 2, True),
             ((1440, 900), "both folded", none, 3, False),
             ((1920, 1000), "the Contents and the index open", both, 1, True),
             ((1920, 1000), "the Contents folded", rail, 2, True),
             ((1920, 1000), "the Contents folded", rail, 3, False),
             ((1920, 1000), "both folded", none, 3, True),
             ((2560, 1000), "the Contents and the index open", both, 3, True)]
    for size, label, folded, n, want in cases:
        ctx, pg, errors = context(b, dict(folded, translations=TR[n]), size=size)
        pg.goto(BASE + "/15:1")
        x = settled(pg)
        what = f"{size[0]} px, {label}, {n} ticked: "
        if want:
            ok(x["cmp"] and x["cls"] and x["names"] == n + 1 and x["folds"] == 0 and x["frame"] == str(n + 1),
               what + f"{n + 1} columns, their names over them, and no fold ({x['cols']})")
            ok(len(x["cols"]) == n + 1 and min(x["cols"]) >= x["min"] - 0.5 and max(x["cols"]) <= x["measure"] + 0.5,
               what + f"none under the least, {x['min']} px, nor over the measure, {x['measure']} px")
            ok(x["kept"] == str(size[0]), what + f"and the next page's first paint is told ({x['kept']})")
        else:
            ok(not x["cmp"] and not x["cls"] and x["names"] == 0 and x["folds"] > 0 and x["frame"] == "",
               what + f"no columns: a fold under each paragraph ({x['folds']} on the page)")
            ok(x["kept"] is None, what + "and the next page's first paint is told nothing")
        ok(x["over"] <= 0, what + "the page is no wider than its window")
        ok(not errors, what + f"no error in the page ({errors})")
        ctx.close()

    # Measured, the frame grows to hold a measure to a column where the
    # window has room: until 2026-11-16 two columns shared the frame made
    # for one, 28ch each in a window of any width.
    ctx, pg, errors = context(b, {"translations": TR[1]}, size=WIDEST)
    pg.goto(BASE + "/15:1")
    x = settled(pg)
    ok(len(x["cols"]) == 2 and all(abs(c - x["measure"]) <= 0.5 for c in x["cols"]),
       f"Measured, at 2560 px each of two columns is the measure ({x['cols']}, {x['measure']} px)")
    ctx.close()

    print("\nUnder 62rem, where there is no Contents beside the text and no margin")
    for size, label, extra, want in (((390, 844), "a phone", {}, False), ((667, 375), "a small phone lying down", {}, False),
                                     ((667, 375), "the same at Smaller text", {"size": "90"}, True),
                                     # Tigran's, 2026-11-16: two columns at Larger too, 35.2 characters
                                     # each, which is why the least is 35 and not the 36 it was that morning.
                                     ((836, 300), "a Galaxy Note 10+ lying down, at Larger text", {"size": "112.5"}, True),
                                     ((836, 300), "the same at Largest", {"size": "125"}, False),
                                     ((800, 1280), "a tablet upright", {}, True), ((800, 1280), "the same with the index folded", {"margin": False}, True),
                                     ((844, 390), "a phone lying down", {}, True)):
        ctx, pg, errors = context(b, dict(extra, translations=TR[1]), size=size, phone=True)
        pg.goto(BASE + "/15:1")
        x = settled(pg)
        what = f"{size[0]} px, {label}: "
        if want:
            ok(x["cmp"] and x["names"] == 2 and x["folds"] == 0 and len(x["cols"]) == 2 and min(x["cols"]) >= x["min"] - 0.5,
               what + f"two columns, none under the least ({x['cols']}, {x['min']} px)")
            # Side by side: with the index folded the text's one track
            # outranked the columns', and they lay one over another.
            lefts = pg.evaluate("[...document.querySelector('article.cmp .grid > .row:has(> .rc)').querySelectorAll(':scope > p.t, :scope > .rc')]"
                                ".map(e => Math.round(e.getBoundingClientRect().left))")
            ok(len(lefts) == 2 and lefts[1] > lefts[0] + x["min"], what + f"side by side ({lefts})")
            # A row's entries under it, across the columns, links the pointer meets.
            met = pg.evaluate("""() => { const seen = e => e && e.getClientRects().length ? e : null;
                const a = seen(document.querySelector('article.cmp .grid > .row > .a a')) || seen(document.querySelector('article.cmp .grid > .row > .a .afold'));
                a.scrollIntoView({block: 'center'}); const r = a.getBoundingClientRect(), row = a.closest('.row'), t = row.querySelector('p.t').getBoundingClientRect();
                const e = document.elementFromPoint(r.left + Math.min(r.width / 2, 20), r.top + r.height / 2);
                return { met: !!e && (e === a || a.contains(e)), under: r.top >= t.bottom - 12, tag: e && e.tagName }; }""")
            ok(met["met"] and met["under"], what + f"a row's entries stand under it, and the pointer meets them ({met})")
        else:
            ok(not x["cmp"] and not x["cls"] and x["names"] == 0 and x["folds"] > 0, what + f"no columns: folds ({x['folds']})")
        ok(x["over"] <= 0, what + "the page is no wider than its window")
        ok(not errors, what + f"no error in the page ({errors})")
        ctx.close()

    # Full is the window's width under 62rem whatever the index: folded or
    # off, the text's one track was the measure there, and Full left a wide
    # margin at the right of a phone lying down (Tigran, 2026-11-16).
    for label, extra in (("the index shown", {}), ("the index folded", {"margin": False}), ("the index off", {"index": False})):
        ctx, pg, errors = context(b, dict(extra, width="full", size="112.5"), size=(836, 300), phone=True)
        pg.goto(BASE + "/0:0")
        settled(pg)
        m = pg.evaluate("(r => [Math.round(r.left * 10) / 10, Math.round((innerWidth - r.right) * 10) / 10])"
                        "(document.querySelector('main .grid > .row > p.t[id]').getBoundingClientRect())")
        ok(abs(m[0] - m[1]) < 1, f"836 px, Width Full, {label}: the text has the window's width, as much at its right as at its left ({m})")
        ctx.close()

    # In place: a fold of the Contents, and of the index, turns the page into
    # columns and back, the letter at the window's top kept at its height,
    # and one that stood where the names now stand brought out from under
    # them.  With Whole paper off and on (trap 44).
    for whole in (False, True):
        say = "Whole paper on: " if whole else "Whole paper off: "
        print("\nIn place, " + say.rstrip(": ") + ", 1440 px")
        ctx, pg, errors = context(b, {"translations": TR[1], "whole": whole}, size=(1440, 900))
        pg.goto(BASE + "/15:3.4")
        settled(pg)
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 900)
        pg.wait_for_timeout(500)
        for what, sel, cols in (("the Contents folded", ".railfold", True), ("the Contents shown", ".railfold", False),
                                ("the index folded", ".indexfold", True), ("the index shown", ".indexfold", False),
                                ("the Contents folded", ".railfold", True), ("the index folded too", ".indexfold", True),
                                ("the index shown", ".indexfold", True), ("the Contents shown", ".railfold", False)):
            m = pg.evaluate(MARK)
            pg.locator(sel).click()
            pg.wait_for_timeout(700)
            w = pg.evaluate(WHERE)
            ok(w["cmp"] is cols, say + f"{what}: " + ("columns" if cols else "folds"))
            want = max(m["y"], w["floor"] + 2) if m["y"] < w["floor"] + 2 else m["y"]
            ok(abs(w["y"] - want) <= 3, say + f"{what}: the letter at the window's top keeps its height ({m['y']} to {w['y']}, the names to {w['floor']})")
        ok(not errors, say + f"no error in the page ({errors})")
        ctx.close()

    print("\nThe window, the text's size, a paper a translation has not, a part's page")
    ctx, pg, errors = context(b, {"translations": TR[1]}, size=(1440, 900))
    pg.goto(BASE + "/15:1")
    ok(not settled(pg)["cmp"], "1440 px, the Contents and the index open: folds")
    pg.set_viewport_size({"width": 1920, "height": 900})
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')"), "the window made 1920 px wide: columns")
    pg.set_viewport_size({"width": 1300, "height": 900})
    ok(until(pg, "!document.querySelector('article.cmp')"), "made 1300 px: folds again")
    pg.set_viewport_size({"width": 1440, "height": 600})
    pg.wait_for_timeout(400)
    ok(not pg.evaluate(STATE)["cmp"], "made 1440 px, and shorter: folds still")
    pg.evaluate("ubSettings.set('size', '90')")
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')"), "Text size Smaller: columns, each column's least being counted in characters")
    pg.evaluate("ubSettings.set('size', '125')")
    ok(until(pg, "!document.querySelector('article.cmp')"), "Text size Largest: folds")
    pg.evaluate("ubSettings.set('size', '100'); ubSettings.set('index', false)")
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')"), "Text size Standard and the index turned off: columns")
    pg.evaluate("ubSettings.set('translations', 'urantia-ru uf-ru')")
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.evaluate(STATE)["folds"] > 0, "a second translation ticked, three columns: no room, folds")
    pg.evaluate("ubSettings.set('translations', '')")
    pg.wait_for_timeout(400)
    x = pg.evaluate(STATE)
    ok(not x["cmp"] and not x["cls"] and x["folds"] == 0, f"none ticked: neither columns nor folds ({x})")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # A fold a reader opens opens every fold, and they go as the columns
    # come, none of them drawn under the columns; and come back as the reader
    # left them, open, or shut (Tigran, 2026-11-20; until then a fold opened
    # came back shut).
    ALL = ("(() => { const f = [...document.querySelectorAll('main .tf[data-has]')].filter(e => getComputedStyle(e).display !== 'none');"
           " return f.length > 0 && f.every(e => e.classList.contains('open') && e.querySelector('.tr p.rt')); })()")
    ctx, pg, errors = context(b, {"translations": TR[1]}, size=(1440, 900))
    pg.goto(BASE + "/15:1")
    settled(pg)
    pg.locator(".trfold").first.click()
    ok(until(pg, ALL), "a fold opened opens them all, each showing its translation")
    pg.locator(".railfold").click()
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')") and pg.locator(".tf.open").count() == 0
       and pg.locator("main .tf .tr").count() == 0, "the Contents folded: columns, and no fold open or drawn")
    pg.locator(".railfold").click()
    ok(until(pg, "!document.querySelector('article.cmp')") and until(pg, ALL), "shown again: the folds, all open, as the reader left them")
    pg.locator(".trfold").first.click()
    ok(until(pg, "document.querySelectorAll('.tf.open').length === 0"), "a tap on one folds them all")
    pg.locator(".railfold").click()
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')"), "the Contents folded again: columns")
    pg.locator(".railfold").click()
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.locator(".tf.open").count() == 0 and pg.evaluate(STATE)["folds"] > 0,
       "shown again: the folds, shut, as left")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # Aivazian's translation has Paper 15 and not Paper 50.
    for path, n, want in (("/50:1", 2, True), ("/15:1", 3, False)):
        ctx, pg, errors = context(b, {"translations": "ud urantia-ru", "rail": "folded"}, size=(1440, 900))
        pg.goto(BASE + path)
        x = settled(pg)
        ok(x["cmp"] is want and (x["names"] == n if want else x["folds"] > 0),
           f"two ticked, 1440 px, the Contents folded, {path}: " + (f"{n} columns, one of them having no such paper" if want else f"{n} columns have no room, folds"))
        ctx.close()

    for size, n, want in (((1440, 900), 1, True), ((1440, 900), 3, False), ((2560, 1000), 3, True), ((390, 844), 1, False)):
        ctx, pg, errors = context(b, {"translations": TR[n]}, size=size, phone=size[0] < 500)
        pg.goto(BASE + "/part/1")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(500)
        x = pg.evaluate(PART)
        side = len(set(x["lefts"])) == n + 1
        ok(x["shown"] == n + 1 and x["cls"] is want and side is want and x["over"] <= 0,
           f"a part's page, {size[0]} px, {n} ticked: " + ("a column each" if want else "each under the English") + f" ({x['lefts']})")
        ok(pg.evaluate("localStorage.getItem('ub_cols')") is None, "and it says nothing of the next page's first paint")
        ok(not errors, f"no error in the page ({errors})")
        ctx.close()

    print("\nThe first paint's guess, and a browser from before")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); if (!sessionStorage.getItem('once')) { sessionStorage.setItem('once', '1');"
                        " localStorage.setItem('ub_cols', '1000'); } localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps({"translations": TR[1]})))
    pg = ctx.new_page()
    pg.goto(BASE + "/15:1", wait_until="commit")
    pg.wait_for_selector("main .tf", state="attached")
    x = settled(pg)
    ok(not x["cmp"] and not x["cls"] and x["folds"] > 0 and x["kept"] is None,
       f"told the last page was in columns in a window as wide, with no room now: the class is taken away, and the folds shown ({x})")
    ctx.close()
    ctx, pg, errors = context(b, {"translations": TR[1], "rail": "folded"}, size=(1440, 900))
    pg.goto(BASE + "/15:1")
    settled(pg)
    pg.goto(BASE + "/15:2", wait_until="commit")
    pg.wait_for_selector("main .tf", state="attached")
    early = pg.evaluate("document.documentElement.classList.contains('compare')")
    ok(early, "a page in columns, and the next has the class before ub.js has drawn anything")
    drawn(pg)
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()
    # The setting kept, which is read by no one, and the sizes by their old
    # names: Larger was 125%, and Smaller 100%, which is Standard.
    ctx, pg, errors = context(b, {"translations": TR[1], "compare": True, "size": "larger", "uisize": "smaller"}, size=(1440, 900))
    pg.goto(BASE + "/15:1")
    x = settled(pg)
    px = pg.evaluate("[getComputedStyle(document.documentElement).fontSize, getComputedStyle(document.querySelector('main p.t')).fontSize]")
    ok(not x["cmp"] and x["folds"] > 0, "a `compare` kept from before turns no page into columns that has no room")
    ok(px == ["16px", "31px"], f"`uisize: smaller` is 100%, and `size: larger` 125% ({px})")
    pg.locator("button.gear").click()
    ticks = pg.evaluate("['uisize', 'size'].map(k => document.querySelector('dialog.settings input[name=' + k + ']:checked').value)")
    ok(ticks == ["100", "125"], f"and Settings ticks Standard and Largest ({ticks})")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()


def desktop(b, whole: bool) -> None:
    say = "Whole paper on: " if whole else "Whole paper off: "
    print("\nA desktop's screen, " + say.rstrip(": "))
    base = {"translations": "ud"}
    if whole:
        base["whole"] = True

    # Over its column at each of the grid's sets of tracks (ub.css
    # article.cmp .grid, four rules), and with three columns.
    for label, st in (("Width measured, the index shown", {}),
                      ("Width full, the index shown", {"width": "full"}),
                      ("Width measured, the index folded", {"margin": False}),
                      ("Width full, the index off", {"width": "full", "index": False}),
                      ("three columns, Width full", {"width": "full", "translations": "ud urantia-ru"})):
        ctx, pg, errors = context(b, dict(base, **st), size=WIDEST if "three" in label else WIDE)
        pg.goto(BASE + ("/15" if whole else "/15:13"))
        drawn(pg)
        n, e = pg.evaluate(NAMES), pg.evaluate(EDGES)
        ok(n["n"] == 1 and n["child"] and n["before"] and n["insec"] == 0,
           say + f"{label}: one row of names, the article's child, before its first section and in none ({n})")
        ok(len(e["cn"]) == len(st.get("translations", "ud").split()) + 1 and e["cn"] == e["ch"] == e["last"],
           say + f"{label}: each name stands over its column, in the first section and the last ({e['cn']} {e['last']})")
        words = pg.evaluate(WORDS)
        ok(words == ["Uversa Press"] + [LABEL[k] for k in st.get("translations", "ud").split()]
           and "Urantia" not in pg.inner_text(".cmpnames") and "Урантии" not in pg.inner_text(".cmpnames"),
           say + f"{label}: the names are the press's and each translation's short name, and no title ({words})")
        if st.get("margin") is False or st.get("index") is False:
            # Section 1 has a box: on the whole paper's page as it stands, or
            # on its own page.
            if not whole:
                pg.goto(BASE + "/15:1")
                drawn(pg)
            ok(pg.evaluate(BOX, "15:1")["shown"] is False, say + f"{label}: a section's box is not shown")
        ok(not errors, say + f"{label}: no error in the page ({errors})")
        ctx.close()

    ctx, pg, errors = context(b, base)
    if whole:
        pg.goto(BASE + "/15")
        drawn(pg)
        ok(pg.locator("article.cmp .cmphd").count() == 15, say + "every one of Paper 15's fifteen sections has its heads")
        # The end of a section, a box over the next one's titles (15:1) and
        # none (15:7, 15:13): what Tigran's picture showed twice.
        for sec in ("15:1", "15:7", "15:13"):
            pg.evaluate(TO, sec)
            pg.wait_for_timeout(200)
            n = pg.evaluate(NAMES)
            ok(n["n"] == 1 and len(n["inwin"]) == 1 and n["inwin"][0][0] == 0,
               say + f"at the end of the section before {sec} one row of names is in the window, at its top ({n['inwin']})")
        # A section's title has the room the page gives it without columns.
        room = pg.evaluate(ROOM, "15:13")
        plain_ctx, plain, _ = context(b, {"whole": True})
        plain.goto(BASE + "/15")
        plain.wait_for_selector("article.whole p.t")
        plain.evaluate("document.fonts.ready")
        plain.wait_for_timeout(300)
        want = plain.evaluate(ROOM, "15:13")
        plain_ctx.close()
        ok(room == want, say + f"a section's title in columns has the room it has without them, above and below ({room}, {want})")
        # The boxes, in the margin: what the whole paper cites, level with
        # the paper's head, and a section's, level with its title.
        for sec, what in (("15:0", "what the whole paper cites"), ("15:1", "what a whole section cites")):
            x = pg.evaluate(BOX, sec)
            ok(x["shown"] and x["left"] == x["margin"] and x["left"] > x["cols"],
               say + f"the box of {what} is in the margin's column, clear of the text's ({x})")
            ok(abs(x["top"] - x["headTop"]) < 1 and x["text"] >= x["bottom"] and x["text"] >= x["headBottom"],
               say + f"its top level with the head's, and the first paragraph under both ({sec})")
            link = pg.evaluate(LINK, sec)
            ok(link["met"], say + f"an entry in it is a link the pointer meets ({link})")
            # A click in the box, on no link, is the box's and marks nothing:
            # while the heads' row lay over it the click was the row's, which
            # has no paragraph, and the running head came down naming the
            # first paragraph on the screen (Tigran, 2026-11-15: "clicking on
            # that box highlights some strange text paragraph").
            pg.locator(f'[id="{sec}"] > .blanket h3').first.click()
            pg.wait_for_timeout(900)
            marked = pg.evaluate("[document.querySelectorAll('main :is(p.t.named, p.rt.named)').length,"
                                 " !!document.querySelector('.runhead:not([hidden])')]")
            ok(marked == [0, False], say + f"a click in the box on no link marks no paragraph and brings no running head ({marked})")
    else:
        pg.goto(BASE + "/15:0")
        drawn(pg)
        x = pg.evaluate(BOX, "15:0")
        ok(x["shown"] and x["left"] == x["margin"] and x["left"] > x["cols"] and abs(x["top"] - x["headTop"]) < 1
           and x["text"] >= x["bottom"],
           say + f"the box of what the whole paper cites is in the margin, its top level with the paper's head ({x})")
        link = pg.evaluate(LINK, "15:0")
        ok(link["met"], say + f"an entry in it is a link the pointer meets ({link})")
        pg.goto(BASE + "/15:1")
        drawn(pg)
        x = pg.evaluate(BOX, "15:1")
        ok(x["shown"] and x["left"] == x["margin"] and x["left"] > x["cols"],
           say + f"a section's box is in the margin's column, clear of the text's ({x})")
        ok(abs(x["bottom"] - x["headBottom"]) < 1 and x["top"] > x["headTop"] and x["text"] >= x["bottom"],
           say + "its foot level with the section's title, the last line of the head, and the first paragraph under both")
        link = pg.evaluate(LINK, "15:1")
        ok(link["met"], say + f"an entry in it is a link the pointer meets ({link})")
        # And a click on it goes to its headword's page.
        pg.locator("article.cmp > section > .blanket a").first.click()
        pg.wait_for_url("**/i/**")
        ok("/i/" in pg.url, say + f"and a click on it opens its headword ({pg.url})")
        pg.goto(BASE + "/15:13")
        drawn(pg)
    pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    pg.wait_for_timeout(200)
    n = pg.evaluate(NAMES)
    ok(len(n["inwin"]) == 1 and n["inwin"][0][0] == 0, say + f"at the page's end the names are still at the window's top ({n['inwin']})")

    # A paragraph the address names is put under the names (ub.js arrive()).
    pg.goto(BASE + "/15:13.2")
    drawn(pg)
    ok(pg.url.endswith("/15#15:13.2" if whole else "/15:13.2"), say + f"/15:13.2 opens ({pg.url})")
    under = """() => { const p = document.getElementById('15:13.2').getBoundingClientRect(),
        n = document.querySelector('.cmpnames').getBoundingClientRect();
        return n.top === 0 && p.top >= n.bottom && p.top <= n.bottom + 40; }"""
    ok(until(pg, under), say + "the paragraph named stands under the names, not behind them")
    ok(not errors, say + f"no error in the page ({errors})")
    ctx.close()

    # A column's ×, with two translations and then with one; and the window.
    ctx, pg, errors = context(b, dict(base, translations="ud urantia-ru"), size=WIDEST)
    pg.goto(BASE + ("/15" if whole else "/15:13"))
    drawn(pg)
    ok(pg.locator(".cmpnames > .cn").count() == 3, say + "two translations ticked, three names")
    pg.click(".cmpnames .cnx[data-k=ud]")
    ok(until(pg, "document.querySelectorAll('.cmpnames > .cn').length === 2"), say + "a column's × takes its name")
    n = pg.evaluate(NAMES)
    ok(n["n"] == 1 and n["child"] and pg.locator("article.cmp .rc[data-k=ud]").count() == 0,
       say + f"and its column, one row of names left ({n})")
    pg.set_viewport_size({"width": 1200, "height": 1000})
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.locator(".cmpnames").count() == 0,
       say + "the window made too narrow for the columns, no row of names is left")
    pg.set_viewport_size({"width": WIDEST[0], "height": WIDEST[1]})
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')") and pg.evaluate(NAMES)["n"] == 1,
       say + "made wide again, there is one")
    pg.click(".cmpnames .cnx[data-k=urantia-ru]")
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.locator(".cmpnames").count() == 0,
       say + "the last column's × takes the row of names with the columns")
    ok(not errors, say + f"no error in the page ({errors})")
    ctx.close()


def folds(b) -> None:
    """A box of five lines or more, folded to its line (Tigran, 2026-11-15)."""
    print("\nA long box, folded: Paper 193 in columns, USGNY ticked")
    st = {"translations": "urantia-ru", "whole": True}
    ctx, pg, errors = context(b, st)
    pg.goto(BASE + "/193")
    drawn(pg)
    m = pg.evaluate(MARKS)
    ok(m["wrong"] == 0 and 0 < m["long"] == m["marked"] < m["boxes"],
       f"every box of five lines or more is marked to fold, and no other ({m})")
    x = pg.evaluate(FOLD, "193:0")
    ok(x["lines"] == 27 and x["fold"] and not x["open"] and x["line"] and x["says"] == "false" and not x["lists"],
       f"the paper's box, 27 lines, is folded to its line, which says it is shut ({x})")
    ok(x["tall"] < 90 and x["under"] < 70, f"and the text begins under the paper's head, not a screen below it ({x['under']} px)")
    words = pg.evaluate("(%s)(document.getElementById('193:0').querySelector(':scope > .blanket > .afold'))" % EN)
    ok(words == "27 index entries across the whole paper and this section", f"the line says how many entries it holds ({words!r})")
    pg.locator('[id="193:0"] > .blanket > .afold').click()
    y = pg.evaluate(FOLD, "193:0")
    ok(y["open"] and y["says"] == "true" and y["lists"] and y["tall"] > 400, f"a click on the line opens the box ({y})")
    link = pg.evaluate(LINK, "193:0")
    ok(link["met"], f"an entry in the opened box is a link the pointer meets ({link})")
    pg.locator('[id="193:0"] > .blanket > .afold').click()
    z = pg.evaluate(FOLD, "193:0")
    ok(not z["open"] and z["says"] == "false" and not z["lists"], f"and a second click folds it again ({z})")
    short = pg.evaluate("[...document.querySelectorAll('main article > section > .blanket:not(.cmpfold)')].map(b => b.closest('section').id)[0]")
    w = pg.evaluate(FOLD, short)
    ok(w["lines"] < 5 and not w["line"] and w["lists"] and w["says"] == "true",
       f"a box of fewer lines, {short}'s, is whole, with no line to fold it ({w})")
    pg.set_viewport_size({"width": 1200, "height": 1000})
    until(pg, "!document.querySelector('article.cmp')")
    v = pg.evaluate(FOLD.replace("sec.querySelector('.cmphd > .ch')", "sec.querySelector(':scope > .blanket')"), "193:0")
    ok(pg.locator(".cmpfold").count() == 0 and v["lists"] and not v["line"],
       f"out of columns, the window too narrow, no box is marked, and the paper's is whole across the text ({v['tall']} px tall)")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # On a section's own page, at the head's foot.
    ctx, pg, errors = context(b, {"translations": "urantia-ru"})
    pg.goto(BASE + "/193:1")
    drawn(pg)
    x, at = pg.evaluate(FOLD, "193:1"), pg.evaluate(BOX, "193:1")
    ok(x["fold"] and not x["lists"] and x["line"] and abs(at["bottom"] - at["headBottom"]) < 1,
       f"on a section's page its box of {x['lines']} lines is folded, at the foot of the head ({x})")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # Under 62rem no box is folded by its length, the index's own button
    # folding them all: in columns, on a tablet, the paper's is whole.
    ctx, pg, errors = context(b, st, size=(800, 1100), phone=True)
    pg.goto(BASE + "/193")
    drawn(pg)
    x = pg.evaluate(FOLD, "193:0")
    ok(x["lists"] and not x["line"] and x["says"] == "true", f"on a tablet, in columns, the paper's box is whole ({x})")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()


def titles(b) -> None:
    """A click on a section's title names that section's first paragraph,
    never the first on the screen, one of the section before (Tigran,
    2026-11-15); under a translation's title, that translation's."""
    print("\nA click on a section's title")
    for label, st in (("in columns", {"translations": "ud", "whole": True}), ("without columns", {"whole": True})):
        ctx, pg, errors = context(b, st)
        pg.goto(BASE + "/15")
        if st.get("translations"):
            drawn(pg)
        else:
            pg.wait_for_selector("article.whole p.t")
            pg.evaluate("document.fonts.ready")
        pg.evaluate(TO, "15:13")
        pg.wait_for_timeout(300)
        first = pg.evaluate("(() => { const ps = document.querySelectorAll('main p.t[id]');"
                            " for (const p of ps) { const r = p.getBoundingClientRect(); if (r.height && r.bottom > 0) return p.id; } })()")
        ok(first.startswith("15:12."), f"{label}: the first paragraph on the screen is one of the section before ({first})")
        pg.locator('[id="15:13"] .cmphd > .ch[data-k="up"] h2' if st.get("translations") else '[id="15:13"] > .papertop h2').click()
        ok(until(pg, "!!document.querySelector('.runhead:not([hidden])')", 4), f"{label}: a click on the title brings the running head")
        n = pg.evaluate(NAMED)
        ok(n == {"en": ["15:13.1"], "tr": [], "head": "15:13.1"}, f"{label}: naming the section's own first paragraph ({n})")
        if st.get("translations"):
            pg.keyboard.press("Escape")
            ok(until(pg, "!document.querySelector('.runhead:not([hidden])')", 4), f"{label}: Escape takes the head away")
            pg.locator('[id="15:13"] .cmphd > .ch[data-k=ud] h2').click()
            ok(until(pg, "!!document.querySelector('.runhead:not([hidden])')", 4), f"{label}: a click on the translation's title brings it")
            n = pg.evaluate(NAMED)
            ok(n == {"en": [], "tr": ["ud 15:13.1"], "head": "15:13.1"},
               f"{label}: naming the translation's own first paragraph of the section ({n})")
        ok(not errors, f"{label}: no error in the page ({errors})")
        ctx.close()


def phone(b, whole: bool) -> None:
    say = "Whole paper on: " if whole else "Whole paper off: "
    print("\nA phone's screen, " + say.rstrip(": "))
    st = {"translations": "ud"}
    if whole:
        st["whole"] = True
    ctx, pg, errors = context(b, st, size=(390, 844), phone=True)
    pg.goto(BASE + ("/15" if whole else "/15:13"))
    pg.wait_for_selector("main .tf .trfold")
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(400)
    x = pg.evaluate(STATE)
    ok(not x["cmp"] and not x["cls"] and x["names"] == 0 and x["folds"] > 0,
       say + f"no columns and no names: each paragraph's translations in a fold under it ({x})")
    ok(x["over"] <= 0, say + "and the page is no wider than the screen")
    ok(not errors, say + f"no error in the page ({errors})")
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        room(b)
        for whole in (False, True):
            desktop(b, whole)
            phone(b, whole)
        folds(b)
        titles(b)
        b.close()
    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


# The app with no offline copy: nothing here is about the copy, and a fresh
# browser would spend the test fetching 48 MB of it (tools/runhead_e2e.py
# NO_COPY).
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
    sys.exit(main())
