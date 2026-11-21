"""The running head on demand, end to end, in Chrome with a touch screen
(ub.js tapHead, 2026-10-31): a tap on a paragraph shows it with that
paragraph's reference and the paper's head, a tap or two lines of scrolling
hides it, its gear opens Settings, its reference opens the Contents with the
paper being read in view and its mark is a link home, a tap while words are
selected does nothing, a tap low on the screen names its paragraph and turns
no page, though the browser kept Tap to turn the page on (gone 2026-11-17),
the whole paper's page names the paper and not the section, a reading
path names the paper of the paragraph, and a 1955 card and the head are never
up together.  And the header's controls on a phone, where they fit; the list
of languages; and full screen, kept from page to page by the first tap.

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


# Whether the list of languages, the half-disc and full screen are drawn, and
# whether the controls stand on the name's line.
FLAGS = """(() => { const b = document.querySelector('.top .brand').getBoundingClientRect(),
  c = document.querySelector('.top .ctl').getBoundingClientRect(),
  vis = s => document.querySelector(s).getClientRects().length > 0;
  return {lang: vis('.top .langmenu'), line: c.top < b.bottom, theme: vis('.top .theme'),
          full: vis('.top .fscreen')}; })()"""
# Full screen as the page has it: in it, the button pressed, the choice kept.
FULL = "() => [!!document.fullscreenElement, document.querySelector('.top .fscreen').getAttribute('aria-pressed'), localStorage.getItem('ub_full')]"


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

        # The section being read, tapped in the Contents (Tigran, 2026-11-17:
        # "I stay where I was, but I expected to jump to the start of this
        # section, as it would if I tap on some other section").  Its link is
        # the address the page has, which the browser loaded again in place of
        # the Contents' entry, with the entry's state, and the page opened the
        # Contents again.
        print("The section being read, from the Contents")
        HERE = ".rail li.here li.here a"
        AT_PAPER = "Math.abs(document.querySelector('.rail li.here').getBoundingClientRect().top - 844 / 6) < 40"
        pg.tap("[id='101:4.4']")
        settle(pg)
        top0 = pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top")
        pg.tap(".runhead .ref")
        settle(pg)
        pg.evaluate("window.ubSame = 1")
        pg.tap(HERE)
        settle(pg)
        ok(pg.url.endswith("/101:4") and pg.evaluate("scrollY") == 0 and not pg.evaluate(SHOWN),
           "a tap on it is its page from the top, the Contents folded as a page opens")
        ok(pg.evaluate("window.ubSame") == 1, "with no page loaded")
        pg.go_back()
        settle(pg)
        ok(pg.evaluate(SHOWN) and pg.evaluate(AT_PAPER), "Back from it is the Contents again, at the paper, as from another section")
        pg.go_back()
        settle(pg)
        top1 = pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top")
        ok(not pg.evaluate(SHOWN) and abs(top1 - top0) < 3,
           "and Back again the paragraph where it stood: %.0f px for %.0f" % (top1, top0))
        pg.go_forward()
        settle(pg)
        pg.go_forward()
        settle(pg)
        ok(pg.evaluate("scrollY") == 0 and not pg.evaluate(SHOWN), "Forward twice is the section's top again, not the paragraph")
        pg.go_back()
        settle(pg)
        pg.go_back()
        settle(pg)
        ok(not pg.evaluate(SHOWN) and abs(pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top") - top0) < 3,
           "and back at the paragraph")

        # The Contents' own line is the way back from them (Tigran, 2026-11-17:
        # "simply tapping on the CONTENTS line should bring me back"), and
        # stays at the window's top while they are open.
        print("The Contents' line, the way back")
        LINE = "document.querySelector('.rail .railhead').getBoundingClientRect().top"
        pg.tap("[id='101:4.4']")
        settle(pg)
        pg.tap(".runhead .ref")
        settle(pg)
        ok(pg.evaluate(SHOWN) and abs(pg.evaluate(LINE)) < 1 and pg.evaluate("scrollY") > 500,
           "open from the reference, their line stands at the window's top, the list under it")
        ok(pg.evaluate("(() => { const e = document.elementFromPoint(60, 14); return !!e && !!e.closest('.railfold'); })()"),
           "and is what a finger finds there")
        pg.touchscreen.tap(60, 14)
        settle(pg)
        top1 = pg.evaluate("document.getElementById('101:4.4').getBoundingClientRect().top")
        ok(not pg.evaluate(SHOWN) and abs(top1 - top0) < 3 and pg.evaluate("(history.state || {}).ub || ''") == "",
           "a tap on it is Back: the Contents folded, the paragraph where it stood: %.0f px for %.0f" % (top1, top0))
        pg.evaluate("scrollTo(0, 0)")
        settle(pg)
        pg.tap(".railfold")
        settle(pg)
        pg.evaluate("scrollBy(0, 1000)")
        settle(pg)
        ok(pg.evaluate(SHOWN) and abs(pg.evaluate(LINE)) < 1, "opened by the line itself, it stays at the top as they scroll")
        pg.touchscreen.tap(60, 14)
        settle(pg)
        ok(not pg.evaluate(SHOWN) and abs(pg.evaluate(LINE)) < 1, "and a tap folds them, the line still at the top, the text under it")
        pg.evaluate("document.getElementById('101:4.4').scrollIntoView({block: 'center'})")
        settle(pg)

        pg.evaluate("getSelection().selectAllChildren(document.getElementById('101:4.5'))")
        pg.tap("[id='101:4.4']")
        settle(pg)
        ok(not shown(pg), "a tap while words are selected does nothing")
        pg.evaluate("getSelection().removeAllRanges()")

        print("A tap never turns the page")
        # Settings' Tap to turn the page is gone (Tigran, 2026-11-17), and a
        # browser that kept it on reads as if it never had: a tap low on the
        # screen names the paragraph under it, and the page stays.
        pg.evaluate("""() => { var s = JSON.parse(localStorage.getItem('ub_settings') || '{}');
                               s.tappage = true; localStorage.setItem('ub_settings', JSON.stringify(s)); }""")
        pg.reload()
        pg.wait_for_selector("[id='101:4.3']")
        ok(pg.evaluate("document.documentElement.dataset.tappage") is None, "a kept tappage sets nothing on the page")
        pg.evaluate("scrollTo(0, scrollY + document.getElementById('101:4.3').getBoundingClientRect().top + 10)")
        settle(pg)
        y = pg.evaluate("scrollY")
        low = text_y(pg, 824, 432)
        ok(low is not None, "a paragraph's text in the lower half of the screen")
        want = pg.evaluate("(y) => { var p = document.elementFromPoint(195, y).closest('p.t[id]'); return p && p.id; }", low or 700)
        pg.touchscreen.tap(195, low or 700)
        settle(pg)
        ok(abs(pg.evaluate("scrollY") - y) < 2 and shown(pg) and pg.inner_text(".runhead .ref") == want,
           "a tap low on the screen names its paragraph, and the page stays")
        pg.touchscreen.tap(195, low or 700)
        settle(pg)
        ok(not shown(pg), "and again hides it")
        pg.evaluate("""() => { var s = JSON.parse(localStorage.getItem('ub_settings') || '{}');
                               delete s.tappage; localStorage.setItem('ub_settings', JSON.stringify(s)); }""")

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

        # Tigran, 2026-11-19: the mark goes by itself after seven seconds,
        # fading for most of one more; a paragraph tapped stays named.
        print("The mark let go of by itself")
        gone = "() => !document.querySelector('p.t.hit, .rc p.rt.hit, .hitgo')"
        fading = "() => [...document.querySelectorAll('p.t.hit.hitgo')].map(p => p.id)"

        def at(t0: float, ms: int) -> None:
            pg.wait_for_timeout(max(0, ms - (time.monotonic() - t0) * 1000))

        pg.goto(BASE + "/0:1.2")
        t0 = time.monotonic()
        ok(pg.evaluate(hit) == ["0:1.2"], "a section's page opens with it marked")
        at(t0, 5000)
        ok(pg.evaluate(hit) == ["0:1.2"] and pg.evaluate(fading) == [], "still marked, and not fading, five seconds on")
        at(t0, 7400)
        ok(pg.evaluate(fading) == ["0:1.2"], "fading at seven and a half")
        at(t0, 8600)
        ok(pg.evaluate(gone), "and let go of by eight and a half, nothing left marked")
        pg.goto(BASE + "/0:1.2")
        pg.tap("[id='0:1.3']")
        settle(pg)
        t0 = time.monotonic()
        ok(shown(pg) and named(pg) == ["0:1.3"] and pg.evaluate(hit) == [], "a tap lets go of it at once, and names another")
        at(t0, 8600)
        ok(shown(pg) and named(pg) == ["0:1.3"] and pg.evaluate(gone), "which stays named eight and a half seconds on")
        pg.tap("[id='0:1.3']")
        settle(pg)

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
        # Loaded afresh: the page is at /0#0:1.2 already, and a step to its
        # own address loads nothing (trap 64).
        pg.goto(BASE + "/1#1:2.9")
        pg.wait_for_selector("article.whole")
        t0 = time.monotonic()
        ok(pg.evaluate(hit) == ["1:2.9"], "the whole paper's page marks the paragraph a load arrives at")
        at(t0, 8600)
        ok(pg.evaluate(gone), "and lets go of it by itself")
        pg.evaluate("location.hash = '1:3.2'")
        settle(pg)
        t0 = time.monotonic()
        ok(pg.evaluate(hit) == ["1:3.2"], "a place on the page arrived at is marked again")
        at(t0, 5000)
        ok(pg.evaluate(hit) == ["1:3.2"] and pg.evaluate(fading) == [], "its count started again from that arrival")
        at(t0, 8600)
        ok(pg.evaluate(gone), "and it goes by itself too")
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
        # The section being read, from the Contents, on the whole paper's
        # page: its link is the place the address already names, so the
        # browser fired popstate with no hashchange, at the same address,
        # which the page took for Back and put the paragraph back.
        pg.evaluate("document.getElementById('101:4.5').scrollIntoView({block: 'center'})")
        settle(pg)
        ok(pg.evaluate("document.getElementById('101:4').getBoundingClientRect().top") < -500, "(deep in section 4, its start far above)")
        pg.tap("[id='101:4.5']")
        settle(pg)
        top5 = pg.evaluate("document.getElementById('101:4.5').getBoundingClientRect().top")
        pg.tap(".runhead .ref")
        settle(pg)
        ok(pg.evaluate("[...document.querySelectorAll('.rail li.here li.here a')].map(a => a.getAttribute('href'))") == ["/101:4"],
           "the Contents mark section 4, the one being read")
        pg.evaluate("window.ubSame = 1")
        pg.tap(HERE)
        settle(pg)
        sec = pg.evaluate("document.getElementById('101:4').getBoundingClientRect().top")
        ok(pg.evaluate("location.hash") == "#101:4" and -5 < sec < 80 and pg.evaluate("window.ubSame") == 1,
           "a tap on it goes to the section's start, as a tap on another does: %.0f px" % sec)
        pg.go_back()
        settle(pg)
        ok(pg.evaluate(SHOWN) and pg.evaluate(AT_PAPER), "Back from it is the Contents again, at the paper")
        pg.go_back()
        settle(pg)
        top6 = pg.evaluate("document.getElementById('101:4.5').getBoundingClientRect().top")
        ok(not pg.evaluate(SHOWN) and abs(top6 - top5) < 3,
           "and Back again the paragraph where it stood: %.0f px for %.0f" % (top6, top5))
        pg.go_forward()
        settle(pg)
        pg.go_forward()
        settle(pg)
        sec = pg.evaluate("document.getElementById('101:4').getBoundingClientRect().top")
        ok(-5 < sec < 80, "Forward twice is the section's start again, not the paragraph: %.0f px" % sec)
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

        # A translation's paragraph in the fold under the English, which is
        # how a phone shows one (Tigran, 2026-11-17: "on the phone tapping a
        # translation's paragraph does nothing"; and of the head it had in
        # columns, "the page header is from English even on the Russian
        # text"): named alone, the head the translation's own.
        print("A translation's paragraph in the fold")
        HEAD = """() => { const h = document.querySelector('.runhead');
            return { ref: h.querySelector('.ref').textContent, pn: h.querySelector('.pn').textContent,
                     dash: getComputedStyle(h.querySelector('.tt'), '::before').content, au: h.querySelector('.au').textContent,
                     lang: h.querySelector('.mid').lang, ctl: [...h.querySelector('.ctl').children].map(e => e.className),
                     named: [...document.querySelectorAll('main .named')].map(p => (p.dataset.k || 'en') + ' ' + (p.id || p.dataset.ref)) }; }"""
        FOLD = "[id='101:4.3'] ~ .tf"
        pg.evaluate("ubSettings.set('translations', 'urantia-ru uf-ru'); ubSettings.set('trtab', 'urantia-ru')")
        pg.goto(BASE + "/101:4")
        pg.wait_for_selector(FOLD + " .trfold")
        pg.tap(FOLD + " .trfold")
        pg.wait_for_selector(FOLD + ".open p.rt")
        # Every fold opening, the head's among them (2026-11-21), the line
        # tapped is held where it stood while a typeface comes in (ub.js
        # placeHold), here the Cyrillic italic of the head's author: a
        # reader's touch lets go of it, Playwright's scroll to the element
        # before its tap does not, and the tap fell on the tabs above.
        pg.evaluate("document.fonts.ready.then(() => new Promise(r => setTimeout(r, 400)))")
        pg.tap(FOLD + " p.rt")
        settle(pg)
        h = pg.evaluate(HEAD) if shown(pg) else {}
        ok(h.get("named") == ["urantia-ru 101:4.3"] and h.get("ref") == "101:4.3", "a tap on it names it alone: %s" % h.get("named"))
        ok(h.get("pn") == "ТЕКСТ 101Подлинная сущность религии" and h.get("dash") == '" – "' and h.get("au") == "Мелхиседек"
           and h.get("lang") == "ru", "the head is the translation's own, its paper's number, title and author: %s, %s" % (h.get("pn"), h.get("au")))
        ok(h.get("ctl") == ["set", "home"], "the gear first, then the site's mark")
        pg.tap(FOLD + " .trtabs button[data-tab='uf-ru']")
        pg.wait_for_selector(FOLD + " p.rt[data-k='uf-ru']")
        settle(pg)
        ok(not shown(pg) and named(pg) == [], "another translation chosen in the fold takes the head with the paragraph")
        pg.tap(FOLD + " p.rt")
        settle(pg)
        h = pg.evaluate(HEAD) if shown(pg) else {}
        ok(h.get("named") == ["uf-ru 101:4.3"] and h.get("pn") == "Документ 101Действительная природа религии" and h.get("au") == "",
           "the Foundation's has its own, and no author, its text giving none: %s" % h.get("pn"))
        # Its reference opens the Contents as that translation gives them
        # (Tigran, 2026-11-17: "it would be nice to switch automatically to
        # that translation's variant of Contents.  Currently it goes to the
        # English (UVERSA PRESS) always"), for that opening.
        TOC = """() => { const r = document.querySelector('.rail'), a = r.querySelector('li.here > details > summary a');
            return { list: r.querySelector('.railtr select').value, paper: a.textContent.trim(),
                     kept: JSON.parse(localStorage.getItem('ub_settings') || '{}').toc || '' }; }"""
        pg.tap(".runhead .ref")
        pg.wait_for_timeout(600)
        c = pg.evaluate(TOC)
        ok(pg.evaluate(SHOWN) and c["list"] == "uf-ru" and c["paper"] == "101. Действительная природа религии" and pg.evaluate(AT_PAPER),
           "its reference opens the Contents in that translation, at the paper: %s, %s" % (c["list"], c["paper"]))
        ok(c["kept"] == "", "the reader's own choice of Contents is not changed by it")
        pg.go_back()
        settle(pg)
        c = pg.evaluate(TOC)
        # The book's own is "up" in the list since 2026-11-20, '' there being
        # the first text's, whichever it is.
        ok(not pg.evaluate(SHOWN) and c["list"] == "up" and c["paper"] == "101. The Real Nature of Religion", "Back folds them, the book's own again")
        pg.go_forward()
        pg.wait_for_timeout(600)
        c = pg.evaluate(TOC)
        ok(pg.evaluate(SHOWN) and c["list"] == "uf-ru" and c["paper"] == "101. Действительная природа религии", "Forward opens them in the translation again")
        pg.go_back()
        settle(pg)
        pg.tap("[id='101:4.3']")
        settle(pg)
        pg.tap(".runhead .ref")
        pg.wait_for_timeout(600)
        c = pg.evaluate(TOC)
        ok(pg.evaluate(SHOWN) and c["list"] == "up" and c["paper"] == "101. The Real Nature of Religion",
           "from the English paragraph they open as the reader chose, the book's")
        pg.go_back()
        settle(pg)
        pg.tap(FOLD + " p.rt")
        settle(pg)
        pg.tap(FOLD + " p.rt")
        settle(pg)
        ok(not shown(pg) and named(pg) == [], "a second tap hides it")
        pg.tap("[id='101:4.3']")
        settle(pg)
        h = pg.evaluate(HEAD) if shown(pg) else {}
        ok(h.get("named") == ["en 101:4.3"] and h.get("au") == "Melchizedek" and h.get("lang") == "",
           "the English paragraph above it has the English head again")
        pg.tap("[id='101:4.3']")
        settle(pg)
        pg.evaluate("ubSettings.set('trtab', 'all')")
        pg.wait_for_selector(FOLD + " p.who")
        settle(pg)
        pg.tap(FOLD + " p.who >> nth=0")
        settle(pg)
        ok(not shown(pg) and named(pg) == [], "a tap on a translation's name in the fold is no tap on the text")
        # The tap on the fold opened every fold, and they stay so (ub.js
        # trAll, 2026-11-20): folded again for what follows.
        pg.evaluate("ubSettings.set('translations', ''); ubSettings.set('trtab', ''); ubSettings.set('tropen', false)")

        # The whole paper's Contents from a translation's paragraph (Tigran,
        # 2026-11-18, of the Foreword in his own translation: on a desk, the
        # reference 0:6.2 followed, "I see section '5. ЛИЧНОСТНЫЕ РЕАЛЬНОСТИ'
        # highlighted", and on his phone section 6 marked, "but shows it in
        # English for some reason").  Two faults.  The mark was the section at
        # the window's top, whatever paragraph was named; and a section's link
        # once followed from the Contents is in the reader's unit, /0#0:6,
        # which the Contents drawn in a translation did not know for a
        # section's.
        print("The whole paper's Contents from a translation's paragraph")
        FW = ".rail li.here.fwin > details > ol > li"
        SECS = "[...document.querySelectorAll(%r)].map(li => li.querySelector('a'))" % FW
        MARK = "[...document.querySelectorAll(%r)].filter(li => li.classList.contains('here')).map(li => li.textContent.trim())" % FW
        FOLD6 = "[id='0:6.1'] ~ .tf"
        # The index off, so that the fold's line stands under its paragraph,
        # on the screen with section 6's title: a phone's entries, a screen
        # of them at 0:6.1, come between.
        pg.evaluate("ubSettings.set('whole', true); ubSettings.set('translations', 'ud'); ubSettings.set('trtab', 'ud'); ubSettings.set('index', false)")
        pg.goto(BASE + "/0")
        pg.wait_for_selector("article.whole")
        settle(pg)
        pg.tap(".railfold")
        settle(pg)
        pg.tap(FW + " a[href='/0:6']")
        settle(pg)
        ok(pg.evaluate("location.hash") == "#0:6" and pg.evaluate(SECS + "[6].getAttribute('href')") == "/0#0:6",
           "a section followed from the Contents is a place on the page, its link now in the reader's unit")
        # 200 px down: the folds about to open under the heads too (2026-11-21),
        # section 6's titles in the translation come between its title and the
        # line tapped, which stays, and the title goes up by them.
        pg.evaluate("scrollBy(0, document.getElementById('0:6').getBoundingClientRect().top - 200)")
        settle(pg)
        TOP6 = "document.getElementById('0:6').getBoundingClientRect().top"
        ok(pg.evaluate(MARK) == ["5. Personality Realities"] and pg.evaluate(TOP6) > 60,
           "(scrolled back a little, section 5 at the window's top and marked, section 6's title under it)")
        # By the finger's place, never Playwright's tap on the element, which
        # brings it into view first: the page moved, section 6 came to the
        # window's top, and the mark was the window's own.
        at = pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.left + 30, y: r.top + r.height / 2 }; }", FOLD6 + " .trfold")
        ok(at["y"] < 780, "(the fold's line under 0:6.1 on the screen: %.0f px)" % at["y"])
        pg.touchscreen.tap(at["x"], at["y"])
        pg.wait_for_selector(FOLD6 + ".open p.rt")
        settle(pg)
        at = pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.left + 80, y: r.top + 14 }; }", FOLD6 + " p.rt")
        ok(at["y"] < 780 and pg.evaluate(TOP6) > 60, "(the translation's paragraph on the screen, section 5 still at its top: %.0f px, %.0f)" % (at["y"], pg.evaluate(TOP6)))
        pg.touchscreen.tap(at["x"], at["y"])
        settle(pg)
        ok(shown(pg) and pg.inner_text(".runhead .ref") == "0:6.1" and pg.evaluate(TOP6) > 60 and pg.evaluate(MARK) == ["6. Energy and Pattern"],
           "a paragraph of section 6 named, the page not moved, the Contents mark section 6: %s" % pg.evaluate(MARK))
        pg.tap(".runhead .ref")
        pg.wait_for_timeout(600)
        drawn = pg.evaluate(SECS + ".map(a => [a.textContent.trim(), a.lang, a.classList.contains('untr')])")
        ok(len(drawn) == 13 and all(d[1] == "ru" and not d[2] for d in drawn) and drawn[6][0] == "6. ЭНЕРГИЯ И ОБРАЗЕЦ",
           "its reference opens them in the translation, the link followed among them: %s" % drawn[6][0])
        ok(pg.evaluate(MARK) == ["6. ЭНЕРГИЯ И ОБРАЗЕЦ"], "section 6 marked, the paragraph's, not the one at the window's top: %s" % pg.evaluate(MARK))
        pg.select_option(".railtr select", "up")
        settle(pg)
        ok(pg.evaluate(SECS + "[6].textContent.trim()") == "6. Energy and Pattern" and pg.evaluate(SECS + "[5].textContent.trim()") == "5. Personality Realities",
           "and the book's own chosen in their list puts the English back, that link's too")
        pg.evaluate("ubSettings.set('whole', false); ubSettings.set('translations', ''); ubSettings.set('trtab', ''); ubSettings.set('index', true);"
                    " ubSettings.set('tropen', false)")

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

        print("A translation's paragraph in its column")
        ctx3 = b.new_context(viewport={"width": 1920, "height": 900})
        ctx3.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        pg3 = ctx3.new_page()
        pg3.on("pageerror", lambda e: errors.append(str(e)))
        pg3.goto(BASE + "/0:1")
        pg3.evaluate("ubSettings.set('translations', 'ud')")
        pg3.goto(BASE + "/0:1")
        pg3.wait_for_selector(".rc p.rt[data-ref='0:1.2']")
        pg3.click(".rc p.rt[data-ref='0:1.2']", position={"x": 150, "y": 12})
        pg3.wait_for_timeout(550)
        h = pg3.evaluate(HEAD) if shown(pg3) else {}
        ok(h.get("named") == ["ud 0:1.2"] and h.get("pn") == "Предисловие" and h.get("au") == "Божественный Советник",
           "the head is the translation's there too, the Foreword's with no number: %s, %s" % (h.get("pn"), h.get("au")))
        # A click in a column's empty room: between two sections, above a
        # translation's title, and beside a cell in the room between the
        # columns (Tigran, 2026-11-18: "click outside the area of the text,
        # e.g. in the space between the section or above the first section
        # title selects the following English paragraph, even when clicked
        # above Russian section title").  The paragraph named is the next
        # down the page in the column the click fell in.
        print("A click in a column's empty room")
        # The middle of each column, the room between them, and the heights
        # of what stands about section 2's title.
        GEO = """() => { const r = id => document.querySelector(id).getBoundingClientRect(),
            en = r("[id='0:2.1']"), ru = r(".rc[data-k='ud']:has(p.rt[data-ref='0:2.1'])"),
            hd = r("[id='0:2'] .cmphd > .ch[data-k='ud']"),
            last = [...document.querySelectorAll("[id='0:1'] .grid > .row")].pop().getBoundingClientRect().bottom;
            return { en: en.left + en.width / 2, ru: ru.left + ru.width / 2, gap: (en.right + ru.left) / 2,
                     above: (last + hd.top) / 2, hd: hd.top, row: en.bottom - 8 }; }"""
        AT = "([x, y]) => { const e = document.elementFromPoint(x, y); return e.tagName + '.' + e.className; }"
        pg3.evaluate("ubSettings.set('whole', true)")
        pg3.goto(BASE + "/0")
        pg3.wait_for_selector(".rc p.rt[data-ref='0:2.1']")
        pg3.wait_for_timeout(400)
        pg3.evaluate("scrollBy(0, document.getElementById('0:2').getBoundingClientRect().top - 400)")
        settle(pg3)
        g = pg3.evaluate(GEO)

        def click3(x, y):
            if shown(pg3):
                pg3.mouse.click(g["en"], g["row"])
                pg3.wait_for_timeout(450)
            pg3.mouse.click(x, y)
            pg3.wait_for_timeout(550)
            return pg3.evaluate(HEAD)["named"] if shown(pg3) else []

        ok(g["hd"] - g["above"] > 4 and not pg3.evaluate("([x, y]) => !!document.elementFromPoint(x, y).closest('p.t, .rc, .ch')", [g["ru"], g["above"]]),
           "(room between sections 1 and 2, on no paragraph and no title: %s)" % pg3.evaluate(AT, [g["ru"], g["above"]]))
        n = click3(g["ru"], g["above"])
        ok(n == ["ud 0:2.1"], "in the translation's column it names the translation's next paragraph: %s" % n)
        n = click3(g["en"], g["above"])
        ok(n == ["en 0:2.1"], "and in the English column the English one: %s" % n)
        ok(pg3.evaluate(AT, [g["gap"] + 3, g["row"]]) == "DIV.row", "(room between the columns, beside 0:2.1, on the row alone)")
        n = click3(g["gap"] + 3, g["row"])
        ok(n == ["ud 0:2.1"], "in the room between the columns, beside the paragraph, the nearer column's: %s" % n)
        n = click3(g["gap"] - 3, g["row"])
        ok(n == ["en 0:2.1"], "and a little to the left of its middle the English: %s" % n)
        past = pg3.evaluate("document.querySelector(\".rc[data-k='ud']:has(p.rt[data-ref='0:2.1'])\").getBoundingClientRect().right") + 30
        ok(not pg3.evaluate("([x, y]) => !!document.elementFromPoint(x, y).closest('p.t, .rc, .ch, a, button, .a, .cites, .blanket')", [past, g["above"]]),
           "(the margin past the last column, between the sections: %s)" % pg3.evaluate(AT, [past, g["above"]]))
        n = click3(past, g["above"])
        ok(n == ["en 0:2.1"], "past the last column, in the margin, the English as before: %s" % n)
        pg3.evaluate("scrollTo(0, 0)")
        settle(pg3)
        top = pg3.evaluate("""() => { const h = document.querySelector("[id='0:0'] .cmphd > .ch[data-k='ud']").getBoundingClientRect();
            return { x: h.left + h.width / 2, y: h.top - 6 }; }""")
        ok(not pg3.evaluate("([x, y]) => !!document.elementFromPoint(x, y).closest('p.t, .rc, .ch, a, button')", [top["x"], top["y"]]),
           "(above the paper's head in the translation's column: %s)" % pg3.evaluate(AT, [top["x"], top["y"]]))
        if shown(pg3):
            pg3.mouse.click(g["en"], 500)
            settle(pg3)
        pg3.mouse.click(top["x"], top["y"])
        pg3.wait_for_timeout(550)
        n = pg3.evaluate(HEAD)["named"] if shown(pg3) else []
        ok(n == ["ud 0:0.1"], "above the paper's head there, the translation's first paragraph: %s" % n)
        pg3.mouse.click(top["x"], top["y"])
        settle(pg3)

        # The whole paper on a wide screen, where the end of one section is
        # at the window's top and the next under it: a paragraph named there
        # has the Contents' mark for its section while it is on the screen,
        # and once it has scrolled off the mark is the window's again
        # (Tigran, 2026-11-18).
        print("The whole paper on a wide screen, the Contents' mark")
        MARK3 = "[...document.querySelectorAll('.rail li.here li.here')].filter(li => li.offsetParent).map(li => li.textContent.trim())"
        pg3.evaluate("ubSettings.set('whole', true)")
        pg3.goto(BASE + "/0")
        pg3.wait_for_selector(".rc p.rt[data-ref='0:6.2']")
        pg3.wait_for_timeout(400)
        pg3.evaluate("scrollBy(0, document.getElementById('0:6').getBoundingClientRect().top - 200)")
        settle(pg3)
        ok(pg3.evaluate(MARK3) == ["5. Personality Realities"],
           "(section 6's title 200 px down the window, section 5 at its top and marked)")
        pg3.click("[id='0:6.2']", position={"x": 150, "y": 12})
        pg3.wait_for_timeout(550)
        ok(shown(pg3) and pg3.inner_text(".runhead .ref") == "0:6.2" and pg3.evaluate(MARK3) == ["6. Energy and Pattern"],
           "0:6.2 named, the Contents beside it mark section 6: %s" % pg3.evaluate(MARK3))
        pg3.click("[id='0:6.2']", position={"x": 150, "y": 12})
        settle(pg3)
        pg3.evaluate("scrollBy(0, 40)")
        settle(pg3)
        ok(not shown(pg3) and pg3.evaluate(MARK3) == ["6. Energy and Pattern"], "which holds with the head gone, while the paragraph is on the screen")
        pg3.evaluate("scrollBy(0, -1200)")
        settle(pg3)
        ok(pg3.evaluate(MARK3) == ["5. Personality Realities"], "and scrolled off, the mark is the section at the window's top again")
        pg3.evaluate("scrollBy(0, 1160)")
        settle(pg3)
        pg3.click(".rc p.rt[data-ref='0:6.2']", position={"x": 150, "y": 12})
        pg3.wait_for_timeout(550)
        pg3.click(".runhead .ref")
        pg3.wait_for_timeout(600)
        ok(pg3.evaluate(MARK3) == ["6. ЭНЕРГИЯ И ОБРАЗЕЦ"],
           "the translation's 0:6.2 and its reference: the Contents in the translation, section 6 marked: %s" % pg3.evaluate(MARK3))
        pg3.evaluate("ubSettings.set('whole', false)")
        pg3.evaluate("ubSettings.set('translations', '')")
        ctx3.close()

        print("The controls on a phone, where they fit")
        # Beside the name where the controls then stay on its line (Tigran,
        # 2026-11-17, of the flags; never on a phone from 2026-11-10): where
        # they would not, the line is first drawn closer (.tight), then the
        # account's mark is left out (tools/account_e2e.py; none here), then
        # the language (.nolang), the half-disc (.notheme) and last full
        # screen (.nofull); where the gear and the ? alone do not fit, the
        # controls have a line of their own and everything is on it.
        # Measured on 2026-11-21, with the list of languages for the flags
        # and full screen beside the half-disc (two pixels at a time): the
        # language fits from 354px at Standard in English, 398 at Larger and
        # 442 at Largest, in Russian 332, 374 and 416, both flags 3:2 and one
        # width (the Union Jack 2:1 at first, 360, 404 and 448 in English);
        # the half-disc from 324,
        # 364 and 404, in Russian 302, 340 and 378; full screen at Standard
        # down to 300 and less, from 338 at Larger and 374 at Largest, in
        # Russian 314 and 348; and the controls go to a line of their own
        # under 312px at Larger in English and 346 at Largest, 320 at Largest
        # in Russian.  With the flags and
        # no full screen, until that day, the flags fitted from 354, 398 and
        # 442, in Russian 334, 374 and 416.
        for lang, size, w, want, half, full in (
                ("en", "100", 400, True, True, True), ("en", "100", 372, True, True, True),
                ("en", "100", 360, True, True, True),
                ("en", "100", 350, False, True, True), ("en", "100", 330, False, True, True),
                ("en", "100", 316, False, False, True),
                ("en", "112.5", 420, True, True, True), ("en", "112.5", 392, False, True, True),
                ("en", "112.5", 356, False, False, True), ("en", "112.5", 330, False, False, False),
                ("en", "112.5", 304, True, True, True),
                ("en", "125", 470, True, True, True), ("en", "125", 430, False, True, True),
                ("en", "125", 390, False, False, True), ("en", "125", 360, False, False, False),
                ("en", "125", 330, True, True, True),
                ("ru", "100", 350, True, True, True), ("ru", "100", 320, False, True, True),
                ("ru", "100", 300, False, False, True),
                ("ru", "112.5", 392, True, True, True), ("ru", "112.5", 360, False, True, True),
                ("ru", "112.5", 330, False, False, True), ("ru", "112.5", 306, False, False, False),
                ("ru", "125", 440, True, True, True), ("ru", "125", 400, False, True, True),
                ("ru", "125", 364, False, False, True), ("ru", "125", 336, False, False, False),
                ("ru", "125", 312, True, True, True)):
            c = b.new_context(has_touch=True, is_mobile=True, viewport={"width": w, "height": 700})
            c.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', '%s'); }"
                              " catch (e) {}" % ('{"lang":"%s","uisize":"%s"}' % (lang, size)))
            q = c.new_page()
            q.on("pageerror", lambda e: errors.append(str(e)))
            q.goto(BASE + "/1:1")
            q.wait_for_timeout(300)
            f = q.evaluate(FLAGS)
            ok(f["lang"] == want and f["theme"] == half and f["full"] == full
               and (f["line"] or (f["lang"] and f["theme"] and f["full"])),
               f"{lang}, {size}%, {w}px: the language {'shown' if f['lang'] else 'left out'},"
               f" the half-disc {'shown' if f['theme'] else 'left out'},"
               f" full screen {'shown' if f['full'] else 'left out'},"
               f" the controls {'beside the name' if f['line'] else 'on a line of their own'}")
            c.close()
        c = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 600, "height": 700})
        c.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings',"
                          " '{\"uisize\":\"125\"}'); } catch (e) {}")
        q = c.new_page()
        q.on("pageerror", lambda e: errors.append(str(e)))
        q.goto(BASE + "/1:1")
        q.wait_for_timeout(300)
        seen = []
        for w in (600, 430, 600):
            q.set_viewport_size({"width": w, "height": 700})
            q.wait_for_timeout(150)
            seen.append(q.evaluate(FLAGS)["lang"])
        ok(seen == [True, False, True], f"a resize leaves the language out and brings it back ({seen})")
        # At 430px and Largest the language fits from 442px in English and
        # from 416 in Russian.
        q.set_viewport_size({"width": 430, "height": 700})
        q.wait_for_timeout(150)
        en430 = q.evaluate(FLAGS)
        q.evaluate("ubSettings.set('lang', 'ru')")
        q.wait_for_timeout(200)
        ok(en430 == {"lang": False, "line": True, "theme": True, "full": True}
           and q.evaluate(FLAGS) == {"lang": True, "line": True, "theme": True, "full": True},
           f"and a shorter name in Russian brings it back, the half-disc and full screen there in both ({en430}, {q.evaluate(FLAGS)})")
        q.evaluate("ubSettings.set('lang', 'en')")
        q.wait_for_timeout(200)
        # The half-disc flips the theme in effect, and the choice is kept.
        was = q.evaluate("document.documentElement.dataset.theme || ''")
        q.locator(".top .theme").tap()
        q.wait_for_timeout(200)
        one = q.evaluate("[document.documentElement.dataset.theme, JSON.parse(localStorage.getItem('ub_settings')).theme]")
        q.locator(".top .theme").tap()
        q.wait_for_timeout(200)
        two = q.evaluate("[document.documentElement.dataset.theme, JSON.parse(localStorage.getItem('ub_settings')).theme]")
        ok(was == "" and one == ["dark", "dark"] and two == ["light", "light"],
           f"a tap on the half-disc goes dark from the device's light, and the next light ({was!r}, {one}, {two})")
        c.close()

        print("The list of languages")
        # Tigran, 2026-11-21, where two flags stood: closed, the flag of the
        # language in effect and a chevron; open, each language, the one in
        # effect pressed; an item chosen shuts it.
        c = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 412, "height": 800})
        c.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        q = c.new_page()
        q.on("pageerror", lambda e: errors.append(str(e)))
        q.goto(BASE + "/1:1")
        q.wait_for_timeout(300)
        lshown = "() => [...document.querySelectorAll('.top .langmenu > summary .fl')].filter(f => f.getClientRects().length).map(f => f.dataset.to)"
        lpressed = "() => [...document.querySelectorAll('.top .langitems button')].map(b => b.dataset.to + ':' + b.getAttribute('aria-pressed'))"
        ok(q.evaluate(lshown) == ["en"] and not q.evaluate("document.querySelector('.top .langmenu').open"),
           "closed, it shows the Union Jack alone")
        q.tap(".top .langmenu > summary")
        q.wait_for_timeout(150)
        box = q.evaluate("(() => { const r = document.querySelector('.top .langitems').getBoundingClientRect(); return [r.left, r.right, innerWidth]; })()")
        ok(q.evaluate(lpressed) == ["en:true", "ru:false"] and box[0] >= 0 and box[1] <= box[2],
           f"open, English is pressed, and the list is within the window ({box})")
        q.tap(".top .langitems button[data-to=ru]")
        q.wait_for_timeout(250)
        ok(q.evaluate("[document.documentElement.dataset.lang, document.querySelector('.top .langmenu').open, JSON.parse(localStorage.getItem('ub_settings')).lang]") == ["ru", False, "ru"]
           and q.evaluate(lshown) == ["ru"] and q.evaluate(lpressed) == ["en:false", "ru:true"],
           "Русский chosen: the page in Russian, the list shut, the tricolour shown, Русский pressed")
        q.tap(".top .langmenu > summary")
        q.wait_for_timeout(150)
        q.tap("main p.t >> nth=1")
        q.wait_for_timeout(150)
        away = q.evaluate("document.querySelector('.top .langmenu').open")
        q.tap(".top .langmenu > summary")
        q.wait_for_timeout(150)
        q.keyboard.press("Escape")
        q.wait_for_timeout(150)
        ok(not away and q.evaluate("[document.querySelector('.top .langmenu').open, document.activeElement.matches('.top .langmenu > summary')]") == [False, True],
           "a tap elsewhere shuts it, and Escape, giving its mark the focus")
        q.reload()
        q.wait_for_timeout(300)
        ok(q.evaluate(lshown) == ["ru"], "a page loaded in Russian shows the tricolour from the first")
        c.close()

        print("Full screen")
        # Tigran, 2026-11-21: a tap on the corners; the browser leaves full
        # screen as a new page loads, and the first tap on the next page,
        # not on a link, brings it back; the button, Back or Esc (an end the
        # page did not ask for) ends it for good; a mouse never brings it
        # back.  The old page hears no end of it as it is left (checked in
        # Chrome: only pagehide).
        c = b.new_context(has_touch=True, is_mobile=True, viewport={"width": 412, "height": 800})
        c.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        q = c.new_page()
        q.on("pageerror", lambda e: errors.append(str(e)))
        q.goto(BASE + "/1:1")
        q.wait_for_timeout(300)
        if not q.evaluate("document.fullscreenEnabled"):
            ok(False, "this Chrome cannot put a page in full screen")
        else:
            fstart = q.evaluate(FULL)
            q.tap(".top .fscreen")
            q.wait_for_timeout(500)
            ok(fstart == [False, "false", None] and q.evaluate(FULL) == [True, "true", "1"],
               f"a tap on the corners: full screen, the button pressed, the choice kept ({q.evaluate(FULL)})")
            q.evaluate("location.href = '/1:2'")
            q.wait_for_url("**/1:2")
            q.wait_for_timeout(500)
            ok(q.evaluate(FULL) == [False, "false", "1"], "a new page is not in full screen, and the choice is still kept")
            link = q.locator("main a[href^='/']:visible").first
            link.evaluate("a => a.addEventListener('click', ev => ev.preventDefault())")
            link.tap()
            q.wait_for_timeout(500)
            ok(q.evaluate("!!document.fullscreenElement") is False, "a tap on a link does not bring it back")
            q.tap("main p.t >> nth=2")
            q.wait_for_timeout(600)
            ok(q.evaluate(FULL) == [True, "true", "1"] and not q.evaluate("!!document.querySelector('.runhead:not([hidden])')"),
               "a tap on the text brings it back, and does only that, with no running head")
            q.evaluate("document.exitFullscreen()")
            q.wait_for_timeout(400)
            soon = q.evaluate(FULL)
            q.wait_for_timeout(1500)
            ok(soon == [False, "false", "1"] and q.evaluate(FULL) == [False, "false", None],
               "ended from outside (Back, Esc), it is forgotten a moment later")
            q.tap("main p.t >> nth=3")
            q.wait_for_timeout(500)
            ok(q.evaluate("!!document.fullscreenElement") is False, "and the next tap does nothing")
            q.tap(".top .fscreen")
            q.wait_for_timeout(500)
            q.tap(".top .fscreen")
            q.wait_for_timeout(500)
            ok(q.evaluate(FULL) == [False, "false", None], "the corners again end it, and forget it")
        c.close()
        c = b.new_context(viewport={"width": 1200, "height": 800})
        c.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_full', '1'); } catch (e) {}")
        q = c.new_page()
        q.on("pageerror", lambda e: errors.append(str(e)))
        q.goto(BASE + "/1:2")
        q.wait_for_timeout(300)
        q.click("main p.t >> nth=2")
        q.wait_for_timeout(600)
        ok(q.evaluate(FULL) == [False, "false", "1"], "a mouse's click does not bring it back")
        c.close()

        ok(not errors, "no script error: " + "; ".join(errors))
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (the manifest a 404), so that no page
# registers the worker and fetches the copy, 48 MB to each fresh context: since
# 2026-11-10 every page does where the site has one (static/offline.js).
# Settings' Offline tab is shown all the same.  tools/offline_e2e.py is the
# test of the copy.
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
                            str(ROOT / "var" / "no-offline-copy"), "8132"], cwd=ROOT, env=env)
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
