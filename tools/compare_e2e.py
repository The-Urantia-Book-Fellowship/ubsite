"""Translations in parallel columns, in Chrome: the line that names the
columns, one to the page, at the window's top, each by its short name; and
the box of what a whole paper or section cites, in the margin, level with
the section's title (Tigran, 2026-11-15, all three).

Until that day `ub.js cmpDraw` put the names first in every section's grid,
where a sticky row stays only while its own section is in view: on the whole
paper's page the next section's row came up the page under the one stuck at
the top, two of them in the window at every section's end.  Now the row is
the article's own child, a grid of its own with the text's tracks.

With Whole paper off and on (CLAUDE.md trap 44), Aivazian's translation
ticked and the columns on, on a desktop's screen: there is one row of names,
the article's child, before its first section and in none; the names are
Uversa Press and each translation's short name, Aivazian, USGNY, and no
title of the book; each name stands over its column, to the tenth of a
pixel, at each of the grid's four sets of tracks (Width measured and full,
the index shown and folded or off) and with three columns; scrolled to the
end of a section there is still one, at the window's top, and at the page's
end too; a section's title on the whole paper's page has the room it has
without columns, above and below; the box of what the whole paper cites, and
a section's, stands in the margin's column, clear of the text's, its top
level with the head's on the whole paper's page and its foot with the
section's title on a section's page, the section's first paragraph under
both, its entries links that the pointer meets and a click follows (the row
of the heads lay over them for an hour), and is not shown with the index
folded or off; a box of five lines or more is folded to its line, which
says how many entries it holds and opens and folds it, on the whole paper's
page and a section's, and not on a phone nor with the columns off; a click
on a section's title names that section's first paragraph, and on a
translation's title that translation's, with and without columns, never the
first on the screen; a paragraph named by
the address is put under the names, not behind them; a column's ×
takes the column and leaves one row, and the last one's takes the row; and
turning the columns off in Settings takes it too, on again brings one back.
On a phone's screen the names are not shown, as they never were, and the
page is no wider than the screen.

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
NAMED = """() => ({ en: [...document.querySelectorAll('main p.t.named')].map(p => p.id),
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


def context(b, settings: dict, size=(1440, 900), phone: bool = False):
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


def desktop(b, whole: bool) -> None:
    say = "Whole paper on: " if whole else "Whole paper off: "
    print("\nA desktop's screen, " + say.rstrip(": "))
    base = {"translations": "ud", "compare": True}
    if whole:
        base["whole"] = True

    # Over its column at each of the grid's sets of tracks (ub.css
    # article.cmp .grid, four rules), and with three columns.
    for label, st in (("Width measured, the index shown", {}),
                      ("Width full, the index shown", {"width": "full"}),
                      ("Width measured, the index folded", {"margin": False}),
                      ("Width full, the index off", {"width": "full", "index": False}),
                      ("three columns, Width full", {"width": "full", "translations": "ud urantia-ru"})):
        ctx, pg, errors = context(b, dict(base, **st))
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

    # A column's ×, with two translations and then with one; and the setting.
    ctx, pg, errors = context(b, dict(base, translations="ud urantia-ru"))
    pg.goto(BASE + ("/15" if whole else "/15:13"))
    drawn(pg)
    ok(pg.locator(".cmpnames > .cn").count() == 3, say + "two translations ticked, three names")
    pg.click(".cmpnames .cnx[data-k=ud]")
    ok(until(pg, "document.querySelectorAll('.cmpnames > .cn').length === 2"), say + "a column's × takes its name")
    n = pg.evaluate(NAMES)
    ok(n["n"] == 1 and n["child"] and pg.locator("article.cmp .rc[data-k=ud]").count() == 0,
       say + f"and its column, one row of names left ({n})")
    pg.evaluate("ubSettings.set('compare', false)")
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.locator(".cmpnames").count() == 0,
       say + "the columns turned off in Settings, no row of names is left")
    pg.evaluate("ubSettings.set('compare', true)")
    ok(until(pg, "!!document.querySelector('article.cmp .cmphd')") and pg.evaluate(NAMES)["n"] == 1,
       say + "turned on again, there is one")
    pg.click(".cmpnames .cnx[data-k=urantia-ru]")
    ok(until(pg, "!document.querySelector('article.cmp')") and pg.locator(".cmpnames").count() == 0,
       say + "the last column's × takes the row of names with the columns")
    ok(not errors, say + f"no error in the page ({errors})")
    ctx.close()


def folds(b) -> None:
    """A box of five lines or more, folded to its line (Tigran, 2026-11-15)."""
    print("\nA long box, folded: Paper 193 in columns, USGNY ticked")
    st = {"translations": "urantia-ru", "compare": True, "whole": True}
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
    pg.evaluate("ubSettings.set('compare', false)")
    until(pg, "!document.querySelector('article.cmp')")
    v = pg.evaluate(FOLD.replace("sec.querySelector('.cmphd > .ch')", "sec.querySelector(':scope > .blanket')"), "193:0")
    ok(pg.locator(".cmpfold").count() == 0 and v["lists"] and not v["line"],
       f"with the columns off no box is marked, and the paper's is whole across the text ({v['tall']} px tall)")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # On a section's own page, at the head's foot.
    ctx, pg, errors = context(b, {"translations": "urantia-ru", "compare": True})
    pg.goto(BASE + "/193:1")
    drawn(pg)
    x, at = pg.evaluate(FOLD, "193:1"), pg.evaluate(BOX, "193:1")
    ok(x["fold"] and not x["lists"] and x["line"] and abs(at["bottom"] - at["headBottom"]) < 1,
       f"on a section's page its box of {x['lines']} lines is folded, at the foot of the head ({x})")
    ok(not errors, f"no error in the page ({errors})")
    ctx.close()

    # A phone folds no box by its length: the index's own button folds them all.
    ctx, pg, errors = context(b, st, size=(390, 844), phone=True)
    pg.goto(BASE + "/193")
    drawn(pg)
    x = pg.evaluate(FOLD, "193:0")
    ok(x["lists"] and not x["line"] and x["says"] == "true", f"on a phone the paper's box is whole, as it was ({x})")
    ctx.close()


def titles(b) -> None:
    """A click on a section's title names that section's first paragraph,
    never the first on the screen, one of the section before (Tigran,
    2026-11-15); under a translation's title, that translation's."""
    print("\nA click on a section's title")
    for label, st in (("in columns", {"translations": "ud", "compare": True, "whole": True}), ("without columns", {"whole": True})):
        ctx, pg, errors = context(b, st)
        pg.goto(BASE + "/15")
        if st.get("compare"):
            drawn(pg)
        else:
            pg.wait_for_selector("article.whole p.t")
            pg.evaluate("document.fonts.ready")
        pg.evaluate(TO, "15:13")
        pg.wait_for_timeout(300)
        first = pg.evaluate("(() => { const ps = document.querySelectorAll('main p.t[id]');"
                            " for (const p of ps) { const r = p.getBoundingClientRect(); if (r.height && r.bottom > 0) return p.id; } })()")
        ok(first.startswith("15:12."), f"{label}: the first paragraph on the screen is one of the section before ({first})")
        pg.locator('[id="15:13"] .cmphd > .ch:not([data-k]) h2' if st.get("compare") else '[id="15:13"] > .papertop h2').click()
        ok(until(pg, "!!document.querySelector('.runhead:not([hidden])')", 4), f"{label}: a click on the title brings the running head")
        n = pg.evaluate(NAMED)
        ok(n == {"en": ["15:13.1"], "tr": [], "head": "15:13.1"}, f"{label}: naming the section's own first paragraph ({n})")
        if st.get("compare"):
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
    st = {"translations": "ud", "compare": True}
    if whole:
        st["whole"] = True
    ctx, pg, errors = context(b, st, size=(390, 844), phone=True)
    pg.goto(BASE + ("/15" if whole else "/15:13"))
    drawn(pg)
    n = pg.evaluate(NAMES)
    ok(n["n"] == 1 and n["shown"] == 0 and n["inwin"] == [], say + f"the names are not shown ({n})")
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), say + "and the page is no wider than the screen")
    ok(not errors, say + f"no error in the page ({errors})")
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
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
