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
the paragraph being heard, a translation's by the paragraph it translates,
and stays that paragraph once the player is shut, while it is on the screen;
the player stands over the bar on a page that has it; a reading path moves nothing; a phone has the
reference alone after the words, in both languages; and with scripts off it
is Begin reading.

And the bookmarks (ub.js bmPut, the same day), with a finger and with a mouse:
a tap on a paragraph brings the bar at the foot with the running head, and
the next takes both away; Bookmark this paragraph sets one, with its paper's
title and its opening words, and again removes it; the paragraph has its
ribbon in the margin, level with its reference, beside it and over nothing;
the list's button appears with the first, with their number, on the home
page too, before anything is drawn; the list is in the book's order, a sheet
across a phone and a card on a desk, over the bar and the player; a row goes
to its paragraph, with Whole paper off and on; its cross removes it, the row
staying with Undo, which puts it back as it was; Escape and a click outside
shut the list; a translation's paragraph, in its fold and in its column,
marks the paragraph it translates; a reading path's paragraph is marked with
its paper's title; another tab follows; what the browser keeps that is no
reference is not followed, and what it keeps is put in as text; the words
fit at 320 px in both languages; and with scripts off there is no control.

And a paragraph's link (ub.js copyLink, 2026-11-19): a click or a tap on its
reference copies its address, and Copy link in the bar, with the references
shown or not, in the paragraph's own address whatever the reader's unit; a
translation's paragraph gives the paragraph it translates; the copy command
does it where the clipboard's call is refused.

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


MARKS = "() => JSON.parse(localStorage.getItem('ub_marks') || '[]')"
# The bar's bookmark controls, as shown.
CTL = """() => { const b = document.querySelector('.fbar'), m = b.querySelector('.fmark'), l = b.querySelector('.flist'),
    sh = b.querySelector('.fsheet'), vis = e => !!e && e.getClientRects().length > 0,
    said = el => [...el.querySelectorAll('x-en, x-ru')].filter(vis).map(c => c.textContent).join('').trim(),
    r = b.getBoundingClientRect();
  return {on: vis(b), up: b.classList.contains('fup'), bottom: r.bottom, top: r.top, vh: innerHeight,
          mark: vis(m), pressed: m.getAttribute('aria-pressed'), label: vis(m) ? said(m) : '', go: vis(b.querySelector('.fgo')),
          list: vis(l), count: l.querySelector('.fcount').textContent, open: !sh.hidden, expanded: l.getAttribute('aria-expanded'),
          head: (() => { const h = document.querySelector('.runhead'); return !!h && !h.hidden; })(),
          ref: (() => { const h = document.querySelector('.runhead .ref'); return h ? h.textContent : ''; })(),
          fits: m.scrollWidth <= m.clientWidth + 1 && b.scrollWidth <= b.clientWidth + 1,
          over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
# The list's rows, as shown: reference, title, the second line, gone or not.
ROWS = """() => [...document.querySelectorAll('.fsheet li')].map(li => { const q = li.querySelector('.fq'),
    en = [...q.querySelectorAll('x-en')].map(x => x.textContent).join('');
  return {ref: li.querySelector('.fr').textContent, title: li.querySelector('.ft').textContent, q: en || q.textContent,
          gone: li.classList.contains('fgone'), btn: li.querySelector('button').className,
          kids: li.querySelector('.ft').children.length + (en ? 0 : q.children.length)}; })"""
# A bookmarked paragraph's ribbon, where the stylesheet draws it, beside its reference and its play button.
RIBBON = """(id) => { const p = document.getElementById(id), a = getComputedStyle(p, '::after'), pr = p.getBoundingClientRect(),
    box = e => { if (!e || !e.getClientRects().length) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  if (!p.classList.contains('bmk') || a.content === 'none') return null;
  const l = pr.left + parseFloat(a.left), t = pr.top + parseFloat(a.top);
  return {rib: [l, t, l + parseFloat(a.width), t + parseFloat(a.height)], p: [pr.left, pr.top, pr.right, pr.bottom],
          num: box(p.querySelector('.num')), play: box(p.querySelector('.stk > .playp')), bg: a.backgroundColor}; }"""
SEEN = "localStorage.setItem('ub_tour', 'seen');"


def ctl(pg):
    return pg.evaluate(CTL)


def tap_para(pg, ref: str, touch: bool = True) -> None:
    """A tap, or a mouse's click, on the paragraph's text, brought to the
    upper part of the window first; then the moment a click's head takes,
    and the moment after the bar has risen in which a tap on it is taken
    for the text's (ub.js BAR_SOON)."""
    pg.evaluate("(id) => { const p = document.getElementById(id); scrollTo(0, scrollY + p.getBoundingClientRect().top - 150); }", ref)
    pg.wait_for_timeout(200)
    box = pg.evaluate("(id) => { const r = document.getElementById(id).getBoundingClientRect(); return [r.left, r.top, r.width]; }", ref)
    x, y = box[0] + box[2] * 0.6, box[1] + 14
    if touch:
        pg.touchscreen.tap(x, y)
        pg.wait_for_timeout(550)
    else:
        pg.mouse.click(x, y)
        pg.wait_for_timeout(900)


def marks(b, errors: list) -> None:
    print("Bookmarks: a tap brings the bar with the running head")
    ctx = fresh(b, has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/101:4")
    x = ctl(pg)
    ok(not x["on"] and not x["mark"], "no bar while the page is read")
    tap_para(pg, "101:4.2")
    x = ctl(pg)
    ok(x["head"] and x["ref"] == "101:4.2" and x["on"] and x["up"] and abs(x["bottom"] - x["vh"]) < 1,
       "a tap on a paragraph: the running head, and the bar at the window's foot")
    ok(x["mark"] and x["label"] == "Bookmark this paragraph" and x["pressed"] == "false" and not x["go"],
       f"it says Bookmark this paragraph, in Continue reading's place ({x['label']!r})")
    ok(not x["list"], "and no list's button, there being no bookmark")

    print("Setting one")
    pg.tap(".fbar .fmark")
    pg.wait_for_timeout(150)
    got, x = pg.evaluate(MARKS), ctl(pg)
    ok(len(got) == 1 and got[0]["ref"] == "101:4.2" and got[0]["title"] == "The Real Nature of Religion"
       and got[0]["v"] == pg.get_attribute(".fbar", "data-tv") and got[0]["at"] > 1.7e12,
       f"the bookmark is kept, with its paper's title, the time and the text's version ({got and got[0]['ref']})")
    ok(len(got) == 1 and got[0]["q"].startswith("Mankind should understand that we who participate")
       and got[0]["q"].endswith("…") and len(got[0]["q"].split()) == 12 and "\u00ad" not in got[0]["q"]
       and "101:4.2" not in got[0]["q"], f"and its opening words, twelve, no reference or soft hyphen among them ({got and got[0]['q']!r})")
    ok(x["pressed"] == "true" and x["label"] == "Bookmarked" and x["head"] and x["up"], "the button reads Bookmarked, and both bars stay")
    ok(x["list"] and x["count"] == "1", f"the list's button comes, with their number ({x['count']})")

    print("The ribbon")
    r = pg.evaluate(RIBBON, "101:4.2")
    ok(r is not None, "the paragraph has its ribbon")
    if r:
        rib, par, num, play = r["rib"], r["p"], r["num"], r["play"]
        ok(rib[0] >= 2 and rib[2] <= par[0] - 2, f"in the margin, inside the window and clear of the text ({rib[0]:.1f} to {rib[2]:.1f}, text from {par[0]:.1f})")
        # The reference is small type at the top of its box: its line is the box's first 0.78rem * the leading.
        line = num and (num[1], num[1] + 0.78 * 16 * 1.45)
        mid = (rib[1] + rib[3]) / 2
        ok(bool(line) and line[0] <= mid <= line[1], f"level with the reference ({mid:.1f} in {line and [round(v, 1) for v in line]})")
        ok(bool(num) and rib[2] <= num[0] and (not play or rib[2] <= play[0]), "left of the reference and of the play button, over neither")
        ok(r["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), "drawn in the link's colour")
    under = pg.evaluate("""(id) => { const p = document.getElementById(id), n = p.querySelector('.num').getBoundingClientRect(),
        e = document.elementFromPoint(n.left + n.width / 2, n.top + 8); return !!e && (e.closest('.num') !== null || e.closest('.stk') !== null); }""", "101:4.2")
    ok(under, "what is under the pointer at the reference is the reference (trap 61)")

    print("The next tap takes both away, and the ribbon stays")
    tap_para(pg, "101:4.2")
    x = ctl(pg)
    ok(not x["head"] and not x["on"] and not x["up"] and not x["mark"], "the head and the bar are gone")
    ok(pg.evaluate(RIBBON, "101:4.2") is not None and pg.evaluate("document.querySelectorAll('p.t.named').length") == 0,
       "the ribbon is there with the paragraph untinted: a bookmark is no highlight")

    print("A tap that lands on the bar by chance sets nothing")
    # A paragraph tapped low on the screen: the bar rises under the finger,
    # and the next tap there, meant for the text, takes the bars away.
    pg.evaluate("(() => { const p = document.getElementById('101:4.5'); scrollTo(0, scrollY + p.getBoundingClientRect().top - (innerHeight - 40)); })()")
    pg.wait_for_timeout(200)
    low = pg.evaluate("innerHeight - 22")
    hit = pg.evaluate("(y) => { const e = document.elementFromPoint(195, y), p = e && e.closest('p.t[id]'); return p && p.id; }", low)
    pg.touchscreen.tap(195, low)
    pg.wait_for_timeout(120)
    x = ctl(pg)
    ok(bool(hit) and x["head"] and x["ref"] == hit and x["on"], f"a tap 22 px from the window's foot names {hit}, and the bar rises there")
    pg.touchscreen.tap(195, low)
    pg.wait_for_timeout(200)
    x = ctl(pg)
    ok(not x["head"] and not x["on"] and [m["ref"] for m in pg.evaluate(MARKS)] == ["101:4.2"],
       "the next tap at the same place, at once, takes both away and sets no bookmark")
    tap_para(pg, "101:4.5")
    side = pg.evaluate("(() => { const m = document.querySelector('.fmark').getBoundingClientRect(); return [m.left, m.right, innerHeight - 22]; })()")
    ok(side[0] > 24, f"the button is as wide as its words, the bar's ground beside it ({side[0]:.0f} to {side[1]:.0f})")
    pg.touchscreen.tap(10, side[2])
    pg.wait_for_timeout(200)
    x = ctl(pg)
    ok(not x["head"] and not x["on"] and [m["ref"] for m in pg.evaluate(MARKS)] == ["101:4.2"],
       "a tap on the bar's ground takes both away, as one on the running head's does")

    print("Another paragraph, set and taken off")
    tap_para(pg, "101:4.5")
    x = ctl(pg)
    ok(x["mark"] and x["pressed"] == "false" and x["label"] == "Bookmark this paragraph" and x["list"] and x["count"] == "1",
       "a paragraph without one: Bookmark this paragraph, and the list's button with 1")
    pg.tap(".fbar .fmark")
    pg.wait_for_timeout(150)
    ok(ctl(pg)["count"] == "2" and pg.evaluate(RIBBON, "101:4.5") is not None, "set: 2, and its ribbon")
    pg.tap(".fbar .fmark")
    pg.wait_for_timeout(150)
    x = ctl(pg)
    ok(x["count"] == "1" and x["pressed"] == "false" and pg.evaluate(RIBBON, "101:4.5") is None
       and [m["ref"] for m in pg.evaluate(MARKS)] == ["101:4.2"], "the button again takes it off: 1, and no ribbon")
    tap_para(pg, "101:4.2")
    ok(ctl(pg)["pressed"] == "true" and ctl(pg)["label"] == "Bookmarked", "the paragraph that has one reads Bookmarked as it is named")

    print("Scrolling takes both away")
    pg.evaluate("scrollBy(0, 200)")
    pg.wait_for_timeout(250)
    x = ctl(pg)
    ok(not x["head"] and not x["on"], "two lines of scrolling: the head and the bar go")

    print("The list, on a phone")
    pg.evaluate("""() => { const m = JSON.parse(localStorage.getItem('ub_marks'));
        m.push({ref: '140:5.6', title: 'The Ordination of the Twelve', q: 'From the Sermon on the Mount to the discourse…', at: 5, v: '9'});
        m.push({ref: '3:1.2', title: 'The Attributes of God', q: 'The Universal Father is all the time and without fail…', at: 7, v: '9'});
        m.push({ref: '101:4.10', title: 'The Real Nature of Religion', q: 'Tenth.', at: 9, v: '9'});
        localStorage.setItem('ub_marks', JSON.stringify(m)); }""")
    pg.reload()
    tap_para(pg, "101:4.3")
    x = ctl(pg)
    ok(x["list"] and x["count"] == "4", f"four kept: the button says 4 ({x['count']})")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(200)
    x, rows = ctl(pg), pg.evaluate(ROWS)
    ok(x["open"] and x["expanded"] == "true", "the button opens the list")
    ok([r["ref"] for r in rows] == ["3:1.2", "101:4.2", "101:4.10", "140:5.6"],
       f"in the book's order, 101:4.2 before 101:4.10 ({[r['ref'] for r in rows]})")
    ok(rows[1]["title"] == "The Real Nature of Religion" and rows[1]["q"].startswith("Mankind should understand")
       and all(not r["gone"] and r["btn"] == "fx" for r in rows), "a row is the reference, the paper's title and the opening words, with a cross")
    geo = pg.evaluate("""() => { const s = document.querySelector('.fsheet').getBoundingClientRect(), b = document.querySelector('.fbar').getBoundingClientRect(),
        h = document.querySelector('.runhead').getBoundingClientRect();
        return {l: s.left, r: s.right, t: s.top, b: s.bottom, bar: b.top, vw: document.documentElement.clientWidth, head: h.bottom,
                rows: [...document.querySelectorAll('.fsheet li')].every(li => { const a = li.getBoundingClientRect(); return a.left >= s.left && a.right <= s.right + .5; }),
                lines: [...document.querySelectorAll('.fsheet .fgoto')].every(a => { const r1 = a.querySelector('.frow').getBoundingClientRect(),
                    r2 = a.querySelector('.fq').getBoundingClientRect(); return r2.top >= r1.bottom - 2; })}; }""")
    ok(geo["l"] <= 0.5 and abs(geo["r"] - geo["vw"]) < 1 and abs(geo["b"] - geo["bar"]) < 2 and geo["t"] > geo["head"],
       f"a sheet across the window, on the bar and under the running head ({geo['l']:.0f} to {geo['r']:.0f}, {geo['t']:.0f} to {geo['b']:.0f})")
    ok(geo["rows"] and geo["lines"] and ctl(pg)["over"] <= 0, "its rows within it, each on two lines, and the page no wider")

    print("Removing, and Undo")
    was = [m for m in pg.evaluate(MARKS) if m["ref"] == "101:4.2"][0]
    pg.tap(".fsheet li:nth-child(2) .fx")
    pg.wait_for_timeout(150)
    rows, x = pg.evaluate(ROWS), ctl(pg)
    ok([m["ref"] for m in pg.evaluate(MARKS)] == ["3:1.2", "101:4.10", "140:5.6"] and x["count"] == "3",
       "the cross removes it at once: three kept, the button says 3")
    ok(x["open"] and len(rows) == 4 and rows[1]["ref"] == "101:4.2" and rows[1]["gone"] and rows[1]["q"] == "Removed"
       and rows[1]["btn"] == "fundo", f"its row stays, pale, saying Removed, with Undo ({rows[1]})")
    ok(pg.evaluate(RIBBON, "101:4.2") is None, "and its ribbon is gone from the page")
    ok(pg.evaluate("document.activeElement && document.activeElement.className") == "fundo", "the focus is on Undo, where the cross was")
    pg.tap(".fsheet li:nth-child(2) .fundo")
    pg.wait_for_timeout(150)
    rows, back = pg.evaluate(ROWS), [m for m in pg.evaluate(MARKS) if m["ref"] == "101:4.2"]
    ok(len(back) == 1 and back[0] == was and not rows[1]["gone"] and rows[1]["btn"] == "fx" and ctl(pg)["count"] == "4"
       and pg.evaluate(RIBBON, "101:4.2") is not None, "Undo puts it back as it was, its time too, and the ribbon")
    # The last one removed: the button stays while the list is open, and goes with it.
    for _ in range(4):
        pg.tap(".fsheet li:not(.fgone) .fx")
        pg.wait_for_timeout(100)
    x = ctl(pg)
    ok(pg.evaluate(MARKS) == [] and x["open"] and x["list"] and len(pg.evaluate(ROWS)) == 4, "all four removed: the list stays open with four Undos")
    pg.tap(".fsheet li:nth-child(1) .fundo")
    pg.tap(".fsheet li:nth-child(4) .fundo")
    pg.wait_for_timeout(150)
    ok([m["ref"] for m in pg.evaluate(MARKS)] == ["3:1.2", "140:5.6"], "two put back")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(150)
    x = ctl(pg)
    ok(not x["open"] and x["expanded"] == "false" and x["head"] and x["count"] == "2", "the button again shuts the list, the bars staying")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(150)
    ok(len(pg.evaluate(ROWS)) == 2, "opened again, those removed are forgotten: two rows")

    print("A row goes to its paragraph")
    pg.tap(".fsheet li:nth-child(2) .fgoto")
    pg.wait_for_url("**/140:5.6")
    ok(until(pg, """() => { const p = document.getElementById('140:5.6'), r = p && p.getBoundingClientRect();
                    return !!r && r.top >= 0 && r.top < innerHeight / 2 && p.classList.contains('hit') && p.classList.contains('bmk'); }"""),
       "to the paragraph, marked as the page's place and with its ribbon")
    x = ctl(pg)
    ok(not x["on"] and not x["open"], "and no bar there until a tap")
    pg.evaluate("ubSettings.set('whole', true)")
    tap_para(pg, "140:5.7")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(150)
    pg.tap(".fsheet li:nth-child(1) .fgoto")
    pg.wait_for_url("**/3#3:1.2")
    ok(until(pg, """() => { const p = document.getElementById('3:1.2'), r = p && p.getBoundingClientRect();
                    return !!r && r.top >= 0 && r.top < innerHeight / 2 && p.classList.contains('bmk'); }"""),
       "with Whole paper on, to the paragraph on the whole paper's page (trap 44)")
    # A row for a place on the page being read: there, and the list, the head and the bar gone.
    pg.evaluate("""() => { const m = JSON.parse(localStorage.getItem('ub_marks'));
        m.push({ref: '3:6.3', title: 'The Attributes of God', q: 'x', at: 1, v: '9'}); localStorage.setItem('ub_marks', JSON.stringify(m)); }""")
    pg.reload()
    tap_para(pg, "3:0.1")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(150)
    pg.tap(".fsheet li:nth-child(2) .fgoto")
    ok(until(pg, """() => { const p = document.getElementById('3:6.3'), r = p.getBoundingClientRect();
                    return location.hash === '#3:6.3' && r.top >= 0 && r.top < innerHeight / 2; }"""), "a place on this page: the page goes to it")
    x = ctl(pg)
    ok(not x["open"] and not x["on"] and not x["head"], "and the list, the head and the bar are gone")
    pg.evaluate("ubSettings.set('whole', false)")

    print("A translation's paragraph in its fold")
    pg.evaluate("localStorage.removeItem('ub_marks'); ubSettings.set('translations', 'urantia-ru'); ubSettings.set('trtab', 'urantia-ru')")
    pg.goto(BASE + "/101:4")
    fold = "[id='101:4.3'] ~ .tf"
    pg.wait_for_selector(fold + " .trfold")
    pg.tap(fold + " .trfold")
    pg.wait_for_selector(fold + ".open p.rt")
    pg.wait_for_timeout(200)
    pg.tap(fold + " p.rt")
    pg.wait_for_timeout(550)
    x = ctl(pg)
    ok(x["head"] and x["ref"] == "101:4.3" and x["mark"] and x["pressed"] == "false", "named, it has the bar")
    pg.tap(".fbar .fmark")
    pg.wait_for_timeout(150)
    got = pg.evaluate(MARKS)
    ok(len(got) == 1 and got[0]["ref"] == "101:4.3" and got[0]["title"] == "The Real Nature of Religion"
       and any("\u0400" <= c <= "\u04ff" for c in got[0]["q"]), f"the bookmark is the paragraph's, with the words as read ({got and got[0]['q']!r})")
    ok(pg.evaluate(RIBBON, "101:4.3") is not None and ctl(pg)["pressed"] == "true", "the ribbon is on the paragraph of the text")
    pg.evaluate("ubSettings.set('translations', ''); ubSettings.set('trtab', ''); localStorage.removeItem('ub_marks')")

    print("A reading path")
    pg.goto(BASE + "/i/faith/read")
    ref = pg.evaluate("document.querySelector('main p.t[id]').id")
    tap_para(pg, ref)
    x = ctl(pg)
    ok(x["head"] and x["on"] and x["mark"] and x["label"] == "Bookmark this paragraph", f"a tap on {ref} there brings both bars")
    pg.tap(".fbar .fmark")
    pg.wait_for_timeout(150)
    got = pg.evaluate(MARKS)
    paper = int(ref.split(":")[0])
    ok(len(got) == 1 and got[0]["ref"] == ref and len(got[0]["title"]) > 3 and "Paper" not in got[0]["title"] and "·" not in got[0]["title"],
       f"kept with its paper's title, read from the path's line for Paper {paper} ({got and got[0]['title']!r})")
    ok(pg.evaluate(RIBBON, ref) is not None, "and its ribbon")
    ctx.close()

    print("320 and 390 px, in both languages, with Copy link beside it")
    for lang, label, done, w in [(*t, w) for t in (("en", "Bookmark this paragraph", "Bookmarked"), ("ru", "Поставить закладку", "В закладках"))
                                 for w in (320, 390)]:
        ctx = fresh(b, has_touch=True, is_mobile=True, viewport={"width": w, "height": 640}, device_scale_factor=2)
        ctx.add_init_script("""try { localStorage.setItem('ub_settings', JSON.stringify({lang: '%s'}));
            if (!localStorage.getItem('ub_marks')) localStorage.setItem('ub_marks', JSON.stringify(
              [{ref: '139:11.12', title: 'The Twelve Apostles', q: 'One, two, three.', at: 1, v: '9'}])); } catch (e) {}""" % lang)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/101:4")
        tap_para(pg, "101:4.2")
        x = ctl(pg)
        one = pg.evaluate("""() => { const m = document.querySelector('.fmark').getBoundingClientRect(), l = document.querySelector('.flist').getBoundingClientRect(),
            c = document.querySelector('.fcopy'), cr = c.getBoundingClientRect();
            return m.height < 60 && cr.left >= m.right - .5 && l.left >= cr.right - .5 && cr.width >= 44 && c.scrollWidth <= c.clientWidth + 1
              && !c.querySelector('.fcl').getClientRects().length && l.right <= document.documentElement.clientWidth + .5; }""")
        ok(x["label"] == label and x["fits"] and x["over"] <= 0 and one and x["count"] == "1",
           f"{lang} {w}px: {label}, Copy link's drawing, the list's button, nothing cut")
        pg.tap(".fbar .fmark")
        pg.wait_for_timeout(150)
        ok(ctl(pg)["label"] == done and ctl(pg)["fits"], f"{lang} {w}px: {done}")
        ctx.close()

    print("A desk, with a mouse")
    ctx = fresh(b, viewport={"width": 1280, "height": 900})
    ctx.add_init_script("""try { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
        localStorage.setItem('ub_marks', JSON.stringify([
          {ref: '48:7.24', title: 'The Morontia Life', q: 'Few mortals ever dare to draw anything like the sum…', at: 3, v: '9'},
          {ref: '101:4.2', title: 'The Real Nature of Religion', q: 'Mankind should understand…', at: 4, v: '9'}])); } } catch (e) {}""")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/")
    x = ctl(pg)
    ok(x["on"] and x["go"] and not x["mark"] and x["list"] and x["count"] == "2", "the home page: Continue reading's bar with the list's button, 2")
    pg.click(".fbar .flist")
    pg.wait_for_timeout(150)
    geo = pg.evaluate("""() => { const s = document.querySelector('.fsheet').getBoundingClientRect(), b = document.querySelector('.fbar').getBoundingClientRect();
        return {l: s.left, r: s.right, b: s.bottom, w: s.width, bar: b.top, vw: document.documentElement.clientWidth}; }""")
    ok(ctl(pg)["open"] and 300 < geo["w"] < 480 and geo["r"] <= geo["vw"] and geo["r"] > geo["vw"] - 40 and geo["b"] <= geo["bar"],
       f"the list is a card over the bar's right end ({geo['l']:.0f} to {geo['r']:.0f}, {geo['w']:.0f} wide)")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    ok(not ctl(pg)["open"], "Escape shuts it")
    pg.click(".fbar .flist")
    pg.wait_for_timeout(100)
    pg.mouse.click(40, 300)                 # the page's own margin, no link there
    pg.wait_for_timeout(100)
    ok(not ctl(pg)["open"] and pg.evaluate("location.pathname") == "/", "a click elsewhere shuts it")
    pg.click(".fbar .flist")
    pg.click(".fsheet li:nth-child(1) .fgoto")
    pg.wait_for_url("**/48:7.24")
    ok(until(pg, "() => document.getElementById('48:7.24').classList.contains('bmk')"), "a row on the home page goes to its paragraph")
    tap_para(pg, "48:7.24", touch=False)
    x = ctl(pg)
    ok(x["head"] and x["on"] and x["mark"] and x["pressed"] == "true" and x["label"] == "Bookmarked", "a click on it: both bars, and Bookmarked")
    pg.click(".fbar .flist")
    pg.wait_for_timeout(100)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    x = ctl(pg)
    ok(not x["open"] and x["head"] and x["on"], "Escape shuts the list first, the bars staying")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    x = ctl(pg)
    ok(not x["head"] and not x["on"], "and again, the head and the bar")

    print("Another tab")
    pg2 = ctx.new_page()
    pg2.goto(BASE + "/48:7")
    tap_para(pg2, "48:7.3", touch=False)
    pg2.click(".fbar .fmark")
    ok(until(pg, "() => document.getElementById('48:7.3').classList.contains('bmk')"), "a bookmark set in a second tab has its ribbon in the first")
    tap_para(pg, "48:7.3", touch=False)
    ok(ctl(pg)["count"] == "3" and ctl(pg)["pressed"] == "true", "and is counted there, and Bookmarked")
    pg2.close()

    print("The player, the bar and the list")
    pg.evaluate("ubSettings.set('follow', false)")
    pg.goto(BASE + "/101:4")
    pg.click("[id='101:4.2'] .stk > .playp")
    ok(until(pg, "() => document.body.classList.contains('listening') && !!document.querySelector('.player')", 6000), "the player open on a page of the text")
    tap_para(pg, "101:4.3", touch=False)
    geo = pg.evaluate("""() => { const p = document.querySelector('.player').getBoundingClientRect(), b = document.querySelector('.fbar').getBoundingClientRect();
        return [p.bottom, b.top]; }""")
    ok(ctl(pg)["on"] and geo[0] <= geo[1] - 4, f"the bar up, the player stands over it ({geo[0]:.0f} < {geo[1]:.0f})")
    pg.click(".fbar .flist")
    pg.wait_for_timeout(150)
    top = pg.evaluate("""() => { const p = document.querySelector('.player').getBoundingClientRect(), s = document.querySelector('.fsheet').getBoundingClientRect(),
        x = (Math.max(p.left, s.left) + Math.min(p.right, s.right)) / 2, y = (Math.max(p.top, s.top) + Math.min(p.bottom, s.bottom)) / 2,
        meet = p.right > s.left && p.left < s.right && p.bottom > s.top && p.top < s.bottom, e = meet && document.elementFromPoint(x, y);
        return !meet || (!!e && !!e.closest('.fsheet')); }""")
    ok(top, "the list open, it is over the player where they meet")
    pg.evaluate("document.querySelector('.player .close') && document.querySelector('.player .close').click(); ubSettings.set('follow', true)")
    ctx.close()

    print("A translation's paragraph in its column")
    ctx = fresh(b, viewport={"width": 1920, "height": 900})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/0:1")
    pg.evaluate("ubSettings.set('translations', 'ud')")
    pg.goto(BASE + "/0:1")
    pg.wait_for_selector(".rc p.rt[data-ref='0:1.2']")
    pg.click(".rc p.rt[data-ref='0:1.2']", position={"x": 150, "y": 12})
    pg.wait_for_timeout(900)
    pg.click(".fbar .fmark")
    pg.wait_for_timeout(150)
    got = pg.evaluate(MARKS)
    ok(len(got) == 1 and got[0]["ref"] == "0:1.2" and got[0]["title"] == "Foreword" and pg.evaluate(RIBBON, "0:1.2") is not None,
       f"marks the paragraph it translates, the ribbon on the text's own ({got and got[0]['ref']}, {got and got[0]['title']!r})")
    ctx.close()

    print("What the browser keeps is trusted for nothing")
    ctx = fresh(b, viewport={"width": 1280, "height": 900})
    ctx.add_init_script("""try { localStorage.setItem('ub_marks', JSON.stringify([
        {ref: 'javascript:alert(1)', title: 'x', q: 'y'}, null, 7, {ref: '1:1'},
        {ref: '1:1.2', title: '<img src=x onerror=window.pwned=1>', q: '<b>bold</b>', at: 1, v: '9'}])); } catch (e) {}""")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/")
    ok(ctl(pg)["count"] == "1", "of five things kept, the one with a paragraph's reference is counted")
    pg.click(".fbar .flist")
    pg.wait_for_timeout(150)
    rows = pg.evaluate(ROWS)
    ok(len(rows) == 1 and rows[0]["ref"] == "1:1.2" and rows[0]["title"] == "<img src=x onerror=window.pwned=1>" and rows[0]["q"] == "<b>bold</b>"
       and rows[0]["kids"] == 0 and pg.evaluate("window.pwned") is None
       and pg.get_attribute(".fsheet .fgoto", "href") == "/1:1.2", "and its words are put in as text, its address its reference")
    ctx.close()

    print("Paragraph previews on: the bar's links are no references")
    # A card for Continue reading's link, drawn in the page under the window's
    # foot, made the page taller: a scrollbar came as the pointer rested on
    # the bar and went as it left, the page jumping sideways (Tigran,
    # 2026-11-17); and a tap there on a phone would have shown the card.
    seed = """try { localStorage.setItem('ub_settings', JSON.stringify({preview: true}));
        if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
          localStorage.setItem('ub_place', JSON.stringify({ref: '0:3.19', title: 'Foreword', at: 1, v: '9'}));
          localStorage.setItem('ub_marks', JSON.stringify([{ref: '0:3.1', title: 'Foreword', q: 'Total, infinite reality…', at: 1, v: '9'}])); } } catch (e) {}"""
    ctx = fresh(b, viewport={"width": 1273, "height": 900})
    ctx.add_init_script(seed)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/")
    size = "() => [document.documentElement.scrollHeight, document.documentElement.clientWidth, document.querySelectorAll('.pop.pv').length]"
    was = pg.evaluate(size)
    ok(pg.evaluate("document.documentElement.dataset.preview") == "true" and bar(pg)["href"] == "/0:3.19", "previews on, and Continue reading a paragraph's address")
    pg.hover(".fbar .fgo")
    pg.wait_for_timeout(1200)
    now = pg.evaluate(size)
    ok(now == was and now[2] == 0, f"the pointer resting on Continue reading: no card, and the page as tall and as wide as it was ({was} -> {now})")
    pg.click(".fbar .flist")
    pg.hover(".fsheet .fgoto")
    pg.wait_for_timeout(1200)
    now = pg.evaluate(size)
    ok(now == was and now[2] == 0, f"nor on a bookmark's row ({now})")
    pg.hover(".fbar .flist")
    pg.wait_for_timeout(300)
    ok(pg.evaluate(size) == was, "and nothing moves as the pointer goes on to the list's button")
    ctx.close()
    ctx = fresh(b, has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.add_init_script(seed)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/")
    pg.tap(".fbar .fgo")
    pg.wait_for_url("**/0:3.19")
    ok(pg.evaluate("document.querySelectorAll('.pop.pv').length") == 0, "on a phone a tap on Continue reading goes there, and shows no card")
    pg.goto(BASE + "/")
    pg.tap(".fbar .flist")
    pg.wait_for_timeout(150)
    pg.tap(".fsheet .fgoto")
    pg.wait_for_url("**/0:3.1")
    ok(pg.evaluate("document.querySelectorAll('.pop.pv').length") == 0, "and a tap on a bookmark's row goes to its paragraph")
    ctx.close()

    print("Scripts off: no control")
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, java_script_enabled=False)
    pg = ctx.new_page()
    pg.goto(BASE + "/")
    ok(not pg.locator(".fbar .fmark").is_visible() and not pg.locator(".fbar .flist").is_visible()
       and not pg.locator(".fbar .fsheet").is_visible() and pg.locator(".fbar .fgo").is_visible(), "the bar is Begin reading alone")
    pg.goto(BASE + "/101:4")
    ok(not pg.locator(".fbar").is_visible(), "and a page of the text has none")
    ctx.close()


CLIP = "() => navigator.clipboard.readText()"
# The note that says the link was copied, as shown, and where.
NOTE = """() => { const n = document.querySelector('.lnote'); if (!n || !n.classList.contains('lon')) return null;
  const r = n.getBoundingClientRect(), xs = [...n.querySelectorAll('x-en, x-ru')].filter(e => e.getClientRects().length);
  return {said: xs.length ? xs.map(e => e.textContent).join('') : n.textContent, l: r.left, r: r.right, t: r.top, b: r.bottom,
          vw: document.documentElement.clientWidth, vh: innerHeight}; }"""
# A box, [left, top, right, bottom].
BOX = "(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"


def clip(pg, what: str = "nothing yet") -> None:
    pg.evaluate("(w) => navigator.clipboard.writeText(w)", what)


def said_over(pg, sel: str) -> bool:
    """Whether the note says Link copied, inside the window, over or under `sel`."""
    n, r = pg.evaluate(NOTE), pg.evaluate(BOX, sel)
    return (n is not None and n["said"] in ("Link copied", "Ссылка скопирована") and n["l"] >= 0 and n["r"] <= n["vw"] + .5
            and (abs(n["b"] + 6 - r[1]) < 1.5 or abs(n["t"] - 6 - r[3]) < 1.5))


def links(b, errors: list) -> None:
    """A paragraph's link (Tigran, 2026-11-19): a click or a tap on its
    reference copies its address, /101:4.2, and names nothing in the running
    head; Copy link in the bar does, with the references shown or not; with
    Whole paper on the address is still the paragraph's own; a translation's
    paragraph gives the paragraph it translates; Help's example copies
    nothing; and where the clipboard's own call is refused, the copy command
    does it."""
    print("A paragraph's link, with a mouse")
    ctx = fresh(b, viewport={"width": 1280, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/101:4")
    clip(pg)
    num = "[id='101:4.2'] .num"
    pg.hover(num)
    ok(pg.get_attribute(num, "title") == "Copy link to this paragraph", "the reference says what a click does")
    ok(pg.evaluate("(s) => getComputedStyle(document.querySelector(s)).cursor", num) == "pointer", "with a pointer")
    pg.click(num)
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.2", f"a click on it copies {BASE}/101:4.2 ({pg.evaluate(CLIP)!r})")
    ok(said_over(pg, num), f"and says Link copied over it ({pg.evaluate(NOTE)})")
    pg.wait_for_timeout(800)
    ok(not ctl(pg)["head"] and not ctl(pg)["on"], "the running head and the bar stay away")
    pg.wait_for_timeout(1000)
    ok(pg.evaluate(NOTE) is None and pg.evaluate("document.querySelector('.lnote').textContent") == "", "the note goes, its words with it")
    clip(pg)
    pg.dblclick(num)
    pg.wait_for_timeout(900)
    sel = pg.evaluate("getSelection().toString().trim()")
    ok(sel and sel in "101:4.2" and not ctl(pg)["head"], f"a double-click selects in the reference, for Ctrl+X, and names nothing ({sel!r})")
    pg.evaluate("getSelection().removeAllRanges()")

    tap_para(pg, "101:4.5", touch=False)
    x = ctl(pg)
    words = pg.evaluate("() => [...document.querySelectorAll('.fcopy .fcl x-en, .fcopy .fcl x-ru')].filter(e => e.getClientRects().length).map(e => e.textContent).join('')")
    ok(x["head"] and x["ref"] == "101:4.5" and words == "Copy link", f"a click on the text: the bar has Copy link, in words ({words!r})")
    pg.wait_for_timeout(450)
    pg.click(".fbar .fcopy")
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.5" and said_over(pg, ".fbar .fcopy"), "Copy link copies the paragraph named, and says so over the button")
    ok(ctl(pg)["head"], "and the bar stays up")
    pg.keyboard.press("Escape")

    print("  references off")
    pg.evaluate("ubSettings.set('paranum', false)")
    ok(not pg.is_visible(num), "no reference shown")
    clip(pg)
    tap_para(pg, "101:4.6", touch=False)
    pg.wait_for_timeout(450)
    pg.click(".fbar .fcopy")
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.6", f"Copy link copies it all the same ({pg.evaluate(CLIP)!r})")
    pg.keyboard.press("Escape")
    pg.evaluate("ubSettings.set('paranum', true)")

    print("  Whole paper on")
    pg.evaluate("ubSettings.set('whole', true)")
    pg.goto(BASE + "/101:4")
    pg.wait_for_timeout(300)
    clip(pg)
    pg.click(num)
    pg.wait_for_timeout(150)
    ok(pg.evaluate("location.pathname") == "/101" and pg.evaluate(CLIP) == BASE + "/101:4.2",
       f"on the whole paper's page the address is still the paragraph's own ({pg.evaluate(CLIP)!r})")
    pg.evaluate("ubSettings.set('whole', false)")

    print("  Help's example, and the copy command")
    pg.goto(BASE + "/help")
    clip(pg)
    eg = "main.helppage p.t .num"
    pg.click(eg)
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == "nothing yet" and pg.evaluate(NOTE) is None and not pg.get_attribute(eg, "title"),
       "a click on Help's example copies nothing")
    ctx.close()
    ctx = fresh(b, viewport={"width": 1280, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    ctx.add_init_script("navigator.clipboard.writeText = () => Promise.reject(new DOMException('refused', 'NotAllowedError'));")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/101:4")
    pg.click(num)
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.2" and said_over(pg, num),
       f"the clipboard's call refused, the copy command copies the address alone ({pg.evaluate(CLIP)!r})")
    ctx.close()

    print("A paragraph's link, with a finger")
    ctx = fresh(b, has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844}, device_scale_factor=2,
                permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/101:4")
    clip(pg)
    pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); scrollTo(0, scrollY + r.top - 200); }", num)
    pg.wait_for_timeout(150)
    pg.tap(num)
    pg.wait_for_timeout(550)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.2" and not ctl(pg)["head"], "a tap on the reference copies it, and names nothing")
    tap_para(pg, "101:4.5")
    c = pg.evaluate(BOX, ".fbar .fcopy")
    ok(ctl(pg)["head"] and c[2] - c[0] >= 44 and not pg.evaluate("document.querySelector('.fcopy .fcl').getClientRects().length"),
       f"a tap on the text: Copy link, its drawing alone, {c[2] - c[0]:.0f} px wide")
    pg.tap(".fbar .fcopy")
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.5" and said_over(pg, ".fbar .fcopy"), "a tap on it copies, and the note says so over it")
    pg.evaluate("localStorage.removeItem('ub_marks'); ubSettings.set('translations', 'urantia-ru'); ubSettings.set('trtab', 'urantia-ru')")
    pg.goto(BASE + "/101:4")
    fold = "[id='101:4.3'] ~ .tf"
    pg.wait_for_selector(fold + " .trfold")
    pg.tap(fold + " .trfold")
    pg.wait_for_selector(fold + ".open p.rt")
    pg.wait_for_timeout(200)
    pg.tap(fold + " p.rt")
    pg.wait_for_timeout(550)
    clip(pg)
    pg.tap(".fbar .fcopy")
    pg.wait_for_timeout(150)
    ok(pg.evaluate(CLIP) == BASE + "/101:4.3", f"a translation's paragraph gives the paragraph it translates ({pg.evaluate(CLIP)!r})")
    ctx.close()


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
        ok(until(pg, "() => (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.8'", 1000),
           "and moves on with it, at once")
        # A translation's line being read is marked in its fold or its column: the place is the paragraph it translates.
        pg.evaluate("""() => { document.getElementById('101:4.8').classList.remove('now');
            const rt = document.createElement('p'); rt.className = 'rt now'; rt.dataset.k = 'urantia-ru'; rt.dataset.ref = '101:4.5';
            rt.id = ''; rt.removeAttribute('id'); rt.setAttribute('data-e2e', 'line');
            document.getElementById('101:4.5').closest('.row').appendChild(rt); }""")
        ok(until(pg, "() => (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.5'", 1000),
           "a translation's line being read: the paragraph it translates")
        pg.evaluate("document.querySelector('[data-e2e=line]').remove(); document.body.classList.remove('listening')")

        print("The player shut: the paragraph last heard stays the place")
        # Tigran, 2026-11-17: "if I was listening and paused (but also got rid of
        # the audio player at the bottom for some reason), then I would want to
        # resume from that paragraph and not from the one that happens to be at
        # the top of the view".
        pg.goto(BASE + "/101:4")
        pg.click("[id='101:4.3'] .stk > .playp")
        ok(until(pg, "() => document.body.classList.contains('listening') && (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.3'", 6000),
           "heard from 101:4.3, the place is 101:4.3")
        pg.evaluate("document.querySelector('.player .toggle').click()")          # paused
        pg.evaluate("(() => { const p = document.getElementById('101:4.3'); scrollTo(0, scrollY + p.getBoundingClientRect().top - 360); })()")
        pg.wait_for_timeout(700)
        top = pg.evaluate(FIRST)
        ok(top != "101:4.3" and place(pg)["ref"] == "101:4.3", f"paused, with {top} at the window's top and 101:4.3 lower on the screen: still 101:4.3")
        pg.evaluate("document.querySelector('.player .close').click()")
        ok(until(pg, "() => !document.body.classList.contains('listening') && !document.querySelector('.player')", 3000), "the player shut")
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 120)
        pg.wait_for_timeout(700)
        ok(place(pg)["ref"] == "101:4.3" and pg.evaluate(FIRST) != "101:4.3", "a little scrolling, 101:4.3 still on the screen: still 101:4.3")
        pg.evaluate("dispatchEvent(new Event('pagehide'))")
        ok(place(pg)["ref"] == "101:4.3", "and as the page is left")
        pg.goto(BASE + "/")
        x = bar(pg)
        ok(x["ref"] == "101:4.3" and x["href"] == "/101:4.3", f"Continue reading goes to the paragraph last heard ({x['ref']})")
        pg.go_back()
        pg.wait_for_url("**/101:4")
        pg.click("[id='101:4.3'] .stk > .playp")
        ok(until(pg, "() => document.body.classList.contains('listening') && (JSON.parse(localStorage.getItem('ub_place')) || {}).ref === '101:4.3'", 6000), "heard again")
        pg.evaluate("document.querySelector('.player .close').click()")
        pg.wait_for_timeout(300)
        pg.mouse.move(700, 500)
        pg.mouse.wheel(0, 3000)
        ok(until(pg, f"() => (({PLACE})() || {{}}).ref === ({FIRST})() && (({PLACE})() || {{}}).ref !== '101:4.3'", 3000),
           f"scrolled off the screen by the reader, the place follows the page again ({place(pg)['ref']})")

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

        marks(b, errors)
        ok(errors == [], "bookmarks: no script error: " + "; ".join(errors))

        links(b, errors)
        ok(errors == [], "a paragraph's link: no script error: " + "; ".join(errors))

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
    env = dict(os.environ, UB_VISITS="off", UB_MEANING="off")
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
