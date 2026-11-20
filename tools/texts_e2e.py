"""The texts in the reader's order, the English one of them, end to end, in
Chrome (settings.py `english`, ub.js ftxPut; Tigran, 2026-11-20: "treat all
texts in a uniform and symmetric manner, not singling out English as special,
even though it is the original").

With the English first, as every reader has it until they move it, nothing is
drawn.  With a translation first, on a phone: the English is never painted
before the translation stands in its place; the translation's lines carry
the paragraph's address and its reference, and its ▶; the English is in the
fold with the others, as a tab, with its own ▶; no address stands twice.  An
address arrives at the translation's line, the running head names its paper
in it, a bookmark's ribbon and Continue reading are its.  Where the first has
no paragraph the next stands in, named; where none has, the English, hidden
or not.  In columns each text in its column, the English movable and with a
× of its own.  Settings' Texts moves and hides the English, and keeps the
last one shown.  Search and a part's page follow the order.  A reload comes
back at the line.  Where a section's translations cannot be had, the English.

    .venv/bin/python tools/texts_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8149 with the visit counter off and no
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
PORT = 8149
BASE = f"http://127.0.0.1:{PORT}"
fails: list[str] = []
RU_FIRST = {"translations": "urantia-ru ud", "english": "1"}


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


def fresh(b, settings: dict, phone: bool = True, w: int = 390, h: int = 844):
    """A browser of its own with `settings` stored once and the tour seen; on
    DOMContentLoaded it notes how the English of 1:1.1 was painted, before
    ub.js has had the translations."""
    ctx = (b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2)
           if phone else b.new_context(viewport={"width": w, "height": h}))
    ctx.add_init_script(
        "try { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');"
        " localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } } catch (e) {}"
        " document.addEventListener('DOMContentLoaded', function () {"
        "  var p = document.querySelector('p.t[id=\"1:1.1\"]');"
        "  window.enAtFirst = p ? getComputedStyle(p).visibility : null; });" % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, errors


DUPS = """() => { const s = {}, d = []; document.querySelectorAll('[id]').forEach(e => { if (s[e.id]) d.push(e.id); s[e.id] = 1; }); return d; }"""
READY = "document.documentElement.classList.contains('ftxready')"


def default(b):
    print("The English first, as every reader has it")
    ctx, pg, errors = fresh(b, {"translations": "urantia-ru ud"})
    pg.goto(BASE + "/1:1")
    ok(until(pg, READY), "drawn")
    ok(pg.evaluate("document.querySelectorAll('.ftx, .enoff, .ftxwho, .ftxhd').length") == 0, "nothing of another first text")
    ok(pg.evaluate("document.getElementById('1:1.1').matches('p.t:not(.rt)')"), "the English carries the address")
    ok(pg.evaluate("window.enAtFirst") == "visible", "and is painted at once")
    ok(pg.evaluate("document.querySelector('main .tf[data-has] .trfold').textContent").startswith("2 translations"),
       "its fold holds the two translations")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def phone(b):
    print("A phone, USGNY first, then the English, then Aivazian")
    ctx, pg, errors = fresh(b, RU_FIRST)
    pg.goto(BASE + "/1:1")
    ok(until(pg, READY), "drawn")
    ok(pg.evaluate("window.enAtFirst") == "hidden", "the English held back before first paint")
    first = pg.evaluate("""() => { const p = document.getElementById('1:1.1');
        return { cls: p.className, k: p.dataset.k, lang: p.lang, num: p.querySelector(':scope > .stk > .num').textContent,
                 play: (p.querySelector('.stk .playp') || {}).ariaLabel || '' }; }""")
    ok(first["k"] == "urantia-ru" and "ftx" in first["cls"] and first["lang"] == "ru", f"1:1.1 is USGNY's line ({first['cls']})")
    ok(first["num"] == "1:1.1", "with its reference")
    ok("USGNY" in first["play"], f"and its ▶, in its own voice ({first['play']!r})")
    en = pg.evaluate("""() => { const e = document.querySelector('p.t:not(.rt)[data-ref="1:1.1"]');
        return e && { off: e.classList.contains('enoff'), shown: e.getClientRects().length > 0, id: e.id }; }""")
    ok(en and en["off"] and not en["shown"] and not en["id"], "the English gives up the address and stands aside")
    head = pg.evaluate("document.querySelector('main .ftxhd').textContent")
    ok("ТЕКСТ 1" in head and "Отец Всего Сущего" in head, f"the paper's head is USGNY's ({head[:40]!r})")
    ok(pg.evaluate("[...document.querySelectorAll('main > article > .papertop:not(.ftxhd)')].every(h => !h.getClientRects().length)"),
       "and the English's head is not shown")
    fold = pg.evaluate("document.querySelector('.row:has(> [id=\"1:1.1\"]) .trfold').textContent")
    ok(fold.startswith("2 texts"), f"the fold holds the two others ({fold!r})")
    pg.locator('.row:has(> [id="1:1.1"]) .trfold').click()
    ok(until(pg, "!!document.querySelector('.tf.open .trtabs')"), "opened")
    tabs = pg.evaluate("[...document.querySelectorAll('.tf.open .trtabs button[data-tab]')].map(b => b.textContent)")
    ok(tabs[:2] == ["Uversa Press", "Aivazian"], f"its tabs in the reader's order ({tabs})")
    pg.locator('.tf.open .trtabs button[data-tab="up"]').first.click()
    ok(until(pg, "!!document.querySelector('.tf.open p.rt[data-k=\"up\"][data-ref=\"1:1.1\"]')"), "the English's tab shows the English")
    ok(until(pg, "!!document.querySelector('.tf.open .trtabs > .playp')"), "with its ▶")
    ok(pg.evaluate(DUPS) == [], "no address stands twice")
    ok(not errors, "no script error: " + "; ".join(errors))
    pg.goto(BASE + "/1:1.3")
    ok(until(pg, READY) and until(pg, "(() => { const h = document.querySelector('.hit'); return h && h.id === '1:1.3' && h.dataset.k === 'urantia-ru'; })()"),
       "an address arrives at USGNY's line, marked")
    ok(until(pg, "(() => { const r = document.getElementById('1:1.3').getBoundingClientRect(); return r.top >= 0 && r.top < 200; })()"),
       "brought to the window's top")
    pg.evaluate("localStorage.setItem('ub_marks', JSON.stringify([{ref: '1:1.4', title: 'x', words: 'y', at: Date.now()}]))")
    pg.reload()
    ok(until(pg, READY) and until(pg, "document.getElementById('1:1.4').classList.contains('bmk')"), "a bookmark's ribbon is on USGNY's line")
    p = pg.evaluate("(() => { const r = document.getElementById('1:1.5').getBoundingClientRect(); return [r.left + 60, r.top + 10]; })()")
    pg.evaluate("document.getElementById('1:1.5').scrollIntoView({block: 'center'})")
    pg.wait_for_timeout(200)
    p = pg.evaluate("(() => { const r = document.getElementById('1:1.5').getBoundingClientRect(); return [r.left + 80, r.top + 20]; })()")
    pg.touchscreen.tap(p[0], p[1])
    ok(until(pg, "!!document.querySelector('.runhead:not([hidden])')"), "a tap brings the running head")
    rh = pg.evaluate("document.querySelector('.runhead .mid').textContent")
    ok(until(pg, "document.querySelector('.runhead .mid').textContent.includes('Отец Всего Сущего')"),
       f"naming the paper in USGNY ({rh[:40]!r})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def stand_in(b):
    print("Where the first text has no paragraph")
    ctx, pg, errors = fresh(b, {"translations": "ud urantia-ru", "english": "off"})
    pg.goto(BASE + "/50:1")
    ok(until(pg, READY), "drawn")
    who = pg.evaluate("[...document.querySelectorAll('main .ftxwho')].map(e => e.closest('p').id + ' ' + e.dataset.who)")
    ok(who == ["50:1.1 USGNY"], f"Paper 50, which Aivazian has not: USGNY stands in, named once ({who})")
    ok(pg.evaluate("document.getElementById('50:1.2').dataset.k") == "urantia-ru", "every paragraph USGNY's")
    pg.goto(BASE + "/41:3")
    ok(until(pg, READY), "41:3, which Aivazian has")
    ok(pg.evaluate("document.querySelectorAll('main .ftxwho').length") == 0 and
       pg.evaluate("document.getElementById('41:3.1').dataset.k") == "ud", "Aivazian's, unnamed")
    ctx.close()
    ctx, pg, errors = fresh(b, {"translations": "ud", "english": "off"})
    pg.goto(BASE + "/195:0")
    ok(until(pg, READY), "195:0, Aivazian alone, the English hidden")
    who = pg.evaluate("[...document.querySelectorAll('main .ftxwho')].map(e => e.closest('p').id + ' ' + e.dataset.who)")
    ok(who == ["195:0.4 Uversa Press"], f"where Aivazian stops, the English stands in, named ({who})")
    ok(pg.evaluate("document.getElementById('195:0.4').matches('p.t:not(.rt)') && document.getElementById('195:0.4').getClientRects().length > 0"),
       "shown, with its address")
    ok(pg.evaluate("document.querySelectorAll('main .tf[data-has] .trfold:not(:empty)').length") == 0, "and no fold: there is no other text")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def columns(b):
    print("Columns, USGNY first and the English second")
    ctx, pg, errors = fresh(b, {"translations": "urantia-ru", "english": "1", "rail": "folded"}, phone=False, w=1440, h=900)
    pg.goto(BASE + "/1:2")
    ok(until(pg, "!!document.querySelector('article.cmp') && " + READY), "in columns")
    names = pg.evaluate("[...document.querySelectorAll('.cmpnames .cn')].map(c => c.querySelector('b').textContent + (c.querySelector('.cnx') ? '×' : ''))")
    ok(names == ["USGNY×", "Uversa Press×"], f"named in order, each with its × ({names})")
    xs = pg.evaluate("""() => { const a = document.getElementById('1:2.1').getBoundingClientRect(), e = document.querySelector('p.t:not(.rt)[data-ref="1:2.1"]').getBoundingClientRect();
        return [a.left, e.left, Math.abs(a.top - e.top)]; }""")
    ok(xs[0] < xs[1] and xs[2] < 30, f"USGNY's line left of the English's, level with it ({xs})")
    ok(pg.evaluate("getComputedStyle(document.querySelector('p.t:not(.rt)[data-ref=\"1:2.1\"] > .stk > .num')).display") == "none",
       "the reference with the first text alone")
    ok(pg.evaluate(DUPS) == [], "no address stands twice")
    pg.click('.cmpnames .cnx[data-k="up"]')
    ok(until(pg, "!document.querySelector('article.cmp')"), "the English's × hides it, and with one text left there are no columns")
    ok(pg.evaluate("JSON.parse(localStorage.getItem('ub_settings')).english") == "off", "kept as hidden")
    ok(pg.evaluate("document.querySelectorAll('main p.t:not(.rt):not(.enoff)').length") == 0, "no English anywhere")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def dialog(b):
    print("Settings' Texts")
    ctx, pg, errors = fresh(b, {"translations": "urantia-ru"}, phone=False, w=1000, h=900)
    pg.goto(BASE + "/1:1")
    pg.click(".top .gear")
    pg.click("#set-t-translations")
    tab = pg.evaluate("document.querySelector('#set-t-translations x-en').textContent.trim()")   # trap 33
    ok(tab == "Texts", f"the tab is Texts ({tab!r})")
    order = "[...document.querySelectorAll('.trshown li')].map(l => l.dataset.k + (l.querySelector('.drop').disabled ? '!' : ''))"
    ok(pg.evaluate(order) == ["up", "urantia-ru"], "the English first among those shown")
    pg.click('.trshown li[data-k="up"] .down')
    ok(pg.evaluate(order) == ["urantia-ru", "up"] and pg.evaluate("JSON.parse(localStorage.getItem('ub_settings')).english") == "1",
       "moved down, its place kept")
    ok(until(pg, "document.getElementById('1:1.1') && document.getElementById('1:1.1').dataset.k === 'urantia-ru'"),
       "and the page has USGNY first behind the dialog")
    pg.click('.trshown li[data-k="up"] .drop')
    ok(pg.evaluate(order) == ["urantia-ru!"], "hidden, the last one shown cannot be")
    ok(pg.evaluate("!!document.querySelector('.trother[data-lang=\"en\"] li[data-k=\"up\"]')"), "the English among the others, to be ticked again")
    pg.click('.trother li[data-k="up"] input')
    ok(pg.evaluate(order) == ["urantia-ru", "up"], "ticked, at the end")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def search_and_part(b):
    print("Search and a part's page follow the order")
    vis = "[...document.querySelectorAll('main.results h2')].filter(h => h.offsetParent).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(h => (h.closest('[data-tr]') || {dataset: {}}).dataset.tr || '-')"
    # The English first: as it always was, its study notes before the translations'.
    for st, want in [({"translations": "urantia-ru"}, ["-", "up", "-", "urantia-ru"]),
                     ({"translations": "urantia-ru ud", "english": "1"}, ["-", "urantia-ru", "up", "ud", "-"]),
                     ({"translations": "urantia-ru", "english": "off"}, ["-", "urantia-ru", "-"])]:
        ctx, pg, errors = fresh(b, st, phone=False, w=1000, h=900)
        pg.goto(BASE + "/search?q=1934")
        got = pg.evaluate(vis)
        ok(got == want, f"{st}: {got}")
        ctx.close()
    ctx, pg, errors = fresh(b, {"translations": "urantia-ru ud", "english": "1"})
    pg.goto(BASE + "/part/1")
    got = pg.evaluate("[...document.querySelectorAll('.partpage .divider')].filter(d => d.offsetParent).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).map(d => d.dataset.k || 'up')")
    ok(got == ["urantia-ru", "up", "ud"], f"a part's dividers in the order ({got})")
    ctx.close()


def reload_and_unreachable(b):
    print("Loaded again, and the translations not to be had")
    ctx, pg, errors = fresh(b, RU_FIRST)
    pg.goto(BASE + "/1:2")
    ok(until(pg, READY), "drawn")
    pg.evaluate("window.dispatchEvent(new WheelEvent('wheel')); const p = document.getElementById('1:2.6'); scrollTo(0, scrollY + p.getBoundingClientRect().top - 120)")
    pg.wait_for_timeout(700)
    before = pg.evaluate("document.getElementById('1:2.6').getBoundingClientRect().top")
    pg.reload()
    ok(until(pg, READY), "reloaded")
    pg.wait_for_timeout(1200)
    after = pg.evaluate("document.getElementById('1:2.6').getBoundingClientRect().top")
    ok(abs(after - before) < 8, f"the same line at the same height ({before:.0f}, {after:.0f})")
    ctx.close()
    ctx, pg, errors = fresh(b, RU_FIRST)
    pg.route("**/tr/**", lambda r: r.abort())
    pg.goto(BASE + "/1:1")
    ok(until(pg, READY), "drawn without them")
    ok(pg.evaluate("document.getElementById('1:1.1').matches('p.t:not(.rt)') && getComputedStyle(document.getElementById('1:1.1')).visibility === 'visible'"),
       "the English stands, shown")
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        only = set(sys.argv[1:])
        for name, step in [("default", default), ("phone", phone), ("stand", stand_in), ("columns", columns),
                           ("dialog", dialog), ("search", search_and_part), ("reload", reload_and_unreachable)]:
            if not only or name in only:
                step(b)
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
