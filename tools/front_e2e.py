"""The home page's passage of the moment and the offer to install the site as
an app, in Chrome (templates/home.html .fpass, base.html .appban, ub.js;
DECISIONS.md, The home page).  The offline copy's state on the home page's
bar needs a worker and a copy, and is tried by tools/offline_e2e.py.

    .venv/bin/python tools/front_e2e.py

Not a gate: it needs Chrome.  It runs the app itself on 127.0.0.1:8141 with
the visit counter off and no offline copy to offer.

  the passage: one of the list at each load, never the one shown last, its
  reference and its paper under it; a click on that goes to the paragraph,
  with Whole paper off and on, and with Paragraph previews on too, where no
  card comes in its place; with scripts off, the list's first; within the
  window on a phone, in both languages;

  the banner: not there with nothing known; there when the browser makes its
  offer, on the home page and on no other; there before ub.js runs on the
  next visit, and gone again where the offer does not come; Install is the
  browser's offer, and taken it is gone for good; its cross is for good,
  whatever the browser offers after; never where the page is the installed
  app; and on an iPhone, which makes no offer, it stays and Install opens
  Settings at Offline;

  the Home key: from a section's page and the whole paper's it goes to the
  home page, on a phone too; not with Ctrl, nor in the search box, nor in
  Settings or the changelog's tabs, whose own key it is, nor on the home page
  itself, where it goes to the page's top.
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
PORT = 8141
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/usr/bin/google-chrome"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


SHOWN = """() => { const b = document.querySelector('.fpass'); if (!b) return null;
  const a = b.querySelector('.fpat a'), r = b.getBoundingClientRect();
  return {words: b.querySelector('.fpq').textContent, html: b.querySelector('.fpq').innerHTML, href: a.getAttribute('href'),
          ref: a.querySelector('.fpr').textContent, title: a.querySelector('.fpt').textContent, kept: localStorage.getItem('ub_passage'),
          left: r.left, right: r.right, vw: document.documentElement.clientWidth,
          over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
BAN = """() => { const a = document.querySelector('.appban'), r = a.getBoundingClientRect(), s = getComputedStyle(a);
  return {on: s.display !== 'none', h: Math.round(r.height), mark: document.documentElement.dataset.install || '',
          known: localStorage.getItem('ub_install'), top: Math.round(document.querySelector('header.top').getBoundingClientRect().top),
          words: [...a.querySelectorAll('.abt x-en, .abt x-ru')].filter(e => e.getClientRects().length).map(e => e.textContent).join(''),
          over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
# The browser's offer, as Chrome makes it: an event with prompt() and userChoice.
OFFER = """(outcome) => { const e = new Event('beforeinstallprompt', {cancelable: true}); window.prompted = 0;
  e.prompt = () => { window.prompted++; return Promise.resolve(); };
  e.userChoice = new Promise(res => { window.choose = () => res({outcome: outcome}); });
  window.dispatchEvent(e); return e.defaultPrevented; }"""
SEEN = "try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}"


def fresh(b, w=1280, h=900, settings=None, known=None, extra="", **more):
    ctx = b.new_context(viewport={"width": w, "height": h}, service_workers="block", **more)
    ctx.add_init_script(SEEN + (" try { if (!localStorage.getItem('ub_settings')) localStorage.setItem('ub_settings', %s); } catch (e) {}"
                                % json.dumps(json.dumps(settings)) if settings else "")
                        + (" try { if (!sessionStorage.getItem('e2e')) { sessionStorage.setItem('e2e', '1');"
                           " localStorage.setItem('ub_install', '%s'); } } catch (e) {}" % known if known else "") + extra)
    return ctx


def run() -> int:
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    listed = [dict(ref=r, title=t, words=w) for r, t, w in con.execute("SELECT ref, title, text FROM passage ORDER BY n")]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        errors: list[str] = []

        print(f"The passage of the moment ({len(listed)} in the list)")
        ctx = fresh(b)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        seen, twice = [], 0
        for _ in range(8):
            pg.goto(BASE + "/")
            s = pg.evaluate(SHOWN)
            seen.append(s)
            twice += len(seen) > 1 and seen[-2]["words"] == s["words"]
        mine = [x for s in seen for x in listed if x["words"] == s["words"] and x["ref"] == s["ref"] and x["title"] == s["title"]]
        ok(len(mine) == 8 and all(s["href"] == "/" + s["ref"] for s in seen), "each load shows a passage of the list, with its reference and its paper")
        ok(twice == 0 and len({s["words"] for s in seen}) > 1, f"never the one shown last ({len({s['words'] for s in seen})} different in 8 loads)")
        ok(all(s["kept"] and s["kept"].endswith(" " + s["ref"]) for s in seen), "and what was shown is kept, for the next load to pass over")
        ref = seen[-1]["ref"]
        pg.click(".fpass .fpat a")
        pg.wait_for_url("**/" + ref)
        ok(pg.url.endswith("/" + ref), f"its reference goes to the paragraph ({ref})")
        ctx.close()

        ctx = fresh(b, settings={"whole": True, "previews": True})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        ref = pg.evaluate(SHOWN)["ref"]
        pg.hover(".fpass .fpat a")
        pg.wait_for_timeout(700)
        card = pg.locator(".pop.pv").count()
        pg.click(".fpass .fpat a")
        pg.wait_for_url("**/%s#%s" % (ref.split(":")[0], ref))
        ok(card == 0 and pg.url.endswith("/%s#%s" % (ref.split(":")[0], ref)),
           "with Whole paper and Paragraph previews on, no card in its place, and it goes to the paragraph on the paper's page")
        ctx.close()

        for w, lang in ((390, "en"), (320, "ru")):
            ctx = fresh(b, w, 800, settings={"lang": lang}, device_scale_factor=2)
            pg = ctx.new_page()
            pg.goto(BASE + "/")
            s = pg.evaluate(SHOWN)
            head = pg.evaluate("[...document.querySelectorAll('.fpass h2 x-en, .fpass h2 x-ru')].filter(e => e.getClientRects().length).map(e => e.textContent).join('')")
            ok(s["left"] >= 0 and s["right"] <= s["vw"] and s["over"] <= 0
               and head == ("Passage of the moment" if lang == "en" else "Отрывок на эту минуту"),
               f"[{w} px, {lang}] the card within the window, headed in the interface's language ({head})")
            ctx.close()

        ctx = b.new_context(viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        first = pg.inner_text(".fpass .fpq")
        ok(first == listed[0]["words"] and pg.get_attribute(".fpass .fpat a", "href") == "/" + listed[0]["ref"],
           "scripts off: the list's first, with its way there")
        ctx.close()

        print("The offer to install the site as an app")
        ctx = fresh(b)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        pg.wait_for_timeout(300)
        s0 = pg.evaluate(BAN)
        ok(not s0["on"] and s0["known"] is None and s0["top"] == 0, "with nothing known, no banner, the header at the window's top")
        prevented = pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        s1 = pg.evaluate(BAN)
        ok(prevented and s1["on"] and s1["h"] > 30 and s1["known"] == "offered" and s1["top"] == s1["h"] and s1["over"] <= 0
           and s1["words"] == "Install as an app: it works fully offline and updates itself.",
           f"the browser's offer brings it, over the header ({s1['h']} px), and is kept as made")
        pg.goto(BASE + "/1:1")
        pg.wait_for_timeout(200)
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        s = pg.evaluate(BAN)
        ok(not s["on"] and s["top"] == 0, "on a page of the text there is none, offer or no offer")
        # The next visit: there before ub.js has run, and gone where the offer does not come.
        pg.goto(BASE + "/", wait_until="commit")
        pg.wait_for_selector("header.top", state="attached")
        early = pg.evaluate("document.documentElement.dataset.install || ''")
        pg.wait_for_load_state("load")
        pg.wait_for_timeout(300)
        s2 = pg.evaluate(BAN)
        ok(early == "1" and s2["on"], "on the next visit it is there as the page is first drawn, by what was kept")
        pg.wait_for_timeout(4300)
        s3 = pg.evaluate(BAN)
        ok(not s3["on"] and s3["known"] is None and s3["top"] == 0, "and taken away, with what was kept, where the offer has not come in four seconds")
        # Install: the browser's own offer, and taken, gone for good.
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        pg.click(".appban .abgo")
        pg.wait_for_timeout(100)
        prompted = pg.evaluate("window.prompted")
        pg.evaluate("window.choose()")
        pg.wait_for_timeout(200)
        s4 = pg.evaluate(BAN)
        ok(prompted == 1 and not s4["on"] and s4["known"] == "done", "Install asks the browser's own offer, and taken, the banner is gone")
        pg.reload()
        pg.wait_for_timeout(300)
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        ok(pg.evaluate(BAN)["known"] in ("done", "offered"), "what is known is kept across a load")
        ctx.close()

        ctx = fresh(b, 390, 800, settings={"lang": "ru"}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        pg.wait_for_timeout(300)
        pg.evaluate(OFFER, "dismissed")
        pg.wait_for_timeout(100)
        s = pg.evaluate(BAN)
        ok(s["on"] and s["over"] <= 0 and s["words"] == "Установите как приложение: работает полностью офлайн и обновляется само.",
           f"[390 px, ru] in Russian, within the window ({s['h']} px)")
        pg.click(".appban .abno")
        pg.wait_for_timeout(100)
        s = pg.evaluate(BAN)
        ok(not s["on"] and s["known"] == "no", "its cross takes it away, kept as no")
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        pg.reload()
        pg.wait_for_timeout(300)
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        s = pg.evaluate(BAN)
        ok(not s["on"] and s["known"] == "no", "for good: not at the browser's next offer, nor on the next visit")
        ctx.close()

        # The offer refused in the browser's own dialog: gone until it offers again.
        ctx = fresh(b)
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        pg.wait_for_timeout(300)
        pg.evaluate(OFFER, "dismissed")
        pg.wait_for_timeout(100)
        pg.click(".appban .abgo")
        pg.evaluate("window.choose()")
        pg.wait_for_timeout(200)
        s = pg.evaluate(BAN)
        ok(not s["on"] and s["known"] is None, "refused in the browser's dialog, it goes, and comes with the browser's next offer")
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        ok(pg.evaluate(BAN)["on"], "which brings it again")
        ctx.close()

        # In the installed app, never.
        app = ("const mm = window.matchMedia.bind(window); window.matchMedia = q => q.indexOf('display-mode: standalone') >= 0"
               " ? {matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}} : mm(q);")
        ctx = fresh(b, known="offered", extra=app)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        pg.wait_for_timeout(300)
        pg.evaluate(OFFER, "accepted")
        pg.wait_for_timeout(100)
        ok(not pg.evaluate(BAN)["on"], "in the installed app there is none, whatever is known or offered")
        ctx.close()

        # An iPhone: no offer to wait for; Install opens Settings at Offline.
        ctx = fresh(b, 390, 800, device_scale_factor=3, is_mobile=True, has_touch=True,
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
                               " Version/18.0 Mobile/15E148 Safari/604.1")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/")
        pg.wait_for_timeout(4600)
        s = pg.evaluate(BAN)
        ok(s["on"] and s["mark"] == "ios", "on an iPhone it is there with no offer made, and stays")
        pg.tap(".appban .abgo")
        pg.wait_for_timeout(300)
        opened = pg.evaluate("[document.querySelector('dialog.settings').open, (document.querySelector('dialog.settings [role=tab][aria-selected=true]') || {}).id]")
        ok(opened == [True, "set-t-offline"], f"and Install opens Settings at Offline, which says how ({opened})")
        ctx.close()

        print("The Home key")
        for whole, at in ((False, "/1:1"), (True, "/1")):
            ctx = fresh(b, settings={"whole": True} if whole else None)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(BASE + at)
            pg.mouse.wheel(0, 1500)
            pg.wait_for_timeout(300)
            pg.keyboard.press("Home")
            pg.wait_for_url(BASE + "/", timeout=5000)
            ok(pg.url == BASE + "/", f"Home on {at} goes to the home page" + (" (Whole paper on)" if whole else ""))
            ctx.close()
        ctx = fresh(b, 390, 800, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/101:4")
        pg.keyboard.press("Home")
        pg.wait_for_url(BASE + "/", timeout=5000)
        ok(pg.url == BASE + "/", "and on a phone with a keyboard")
        ctx.close()

        ctx = fresh(b)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/1:1")
        pg.mouse.wheel(0, 1500)
        pg.wait_for_timeout(300)
        pg.keyboard.press("Control+Home")
        pg.wait_for_timeout(500)
        ok(pg.url == BASE + "/1:1" and pg.evaluate("scrollY") == 0, "Ctrl+Home stays the browser's: the page's top")
        pg.fill(".find input", "Paradise")
        pg.focus(".find input")
        pg.keyboard.press("Home")
        pg.wait_for_timeout(500)
        ok(pg.url == BASE + "/1:1" and pg.evaluate("document.querySelector('.find input').selectionStart") == 0,
           "in the search box it moves the caret, and the page stays")
        pg.click("main p.t")
        pg.keyboard.press("Control+Comma")
        pg.wait_for_timeout(300)
        pg.keyboard.press("ArrowRight")
        pg.keyboard.press("Home")
        pg.wait_for_timeout(500)
        tab = pg.evaluate("[document.querySelector('dialog.settings').open, [...document.querySelectorAll('dialog.settings [role=tab]')]"
                          ".filter(t => !t.hidden).findIndex(t => t.getAttribute('aria-selected') === 'true')]")
        ok(pg.url == BASE + "/1:1" and tab == [True, 0], f"in Settings it goes to the first tab, and the page stays ({tab})")
        pg.keyboard.press("Escape")
        pg.goto(BASE + "/changelog")
        tabs = pg.locator("main [role=tablist]").first.locator("[role=tab]")
        tabs.nth(1).click()
        pg.keyboard.press("Home")
        pg.wait_for_timeout(500)
        ok(pg.url == BASE + "/changelog" and tabs.nth(0).get_attribute("aria-selected") == "true",
           "on the changelog's tabs it goes to the first, and the page stays")
        pg.goto(BASE + "/")
        pg.mouse.wheel(0, 600)
        pg.wait_for_timeout(300)
        before = pg.evaluate("scrollY")
        pg.keyboard.press("Home")
        pg.wait_for_timeout(500)
        ok(pg.url == BASE + "/" and before > 0 and pg.evaluate("scrollY") == 0,
           f"on the home page itself it is the browser's, to the top ({before} px up)")
        ctx.close()

        ok(not errors, "no script error: " + "; ".join(errors))
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
