"""Search by meaning, in Chrome (templates/meaning.html, _meaning.html,
static/meaning.js, ub.js meanDraw; ARCHITECTURE.md, Search by meaning).

    .venv/bin/python tools/meaning_e2e.py

Not a gate: it needs Chrome, and the model (var/embed/bge-m3/, var/embed.db).
It runs the app itself on 127.0.0.1:8144, with the model, the visit counter
off and no offline copy to offer.

  a question: an example tapped is asked, its words in the box and in the
  address after the #; the answer has the index's entries, passages set as
  the text is, and the King James Version's list; what the page is and its
  examples make way; typed and entered, asked again by the button, and the
  one before come back to by Back;

  no question in any address asked of the server, only in a POST's body;

  a link followed and Back: the answer again, at the line left; a passage's
  link with Whole paper off and on (CLAUDE.md trap 44);

  the reader's texts: with a translation ticked each passage's fold says how
  many it holds, a tap opens them all, and with a translation first its words
  stand where the English stood, under the paragraph's address; the entries
  that brought a passage beside it, each a link under the pointer (trap 61);

  the switches: Index and appendices off takes the index's row and the
  margin, The Bible in search results off the King James Version's list;

  in Russian, a Russian question and the interface's words;

  the network taken away: the page says so, and answers again when it is back;
  a question too long is refused in words;

  the lists: each heading says how many it holds; the index's entries one to
  a line; with Width at Full the lists as wide as the passages, with Measured
  the measure;

  the ways in: the header's tick, By meaning, at 320, 390, 836 and 1280 px,
  in both languages, at the four Interface text sizes: inside the box, under
  the pointer, the header no wider than the window (traps 65, 68); ticked,
  Enter asks the box's words by meaning, on any page and on the page itself,
  the tick kept from page to page and the box's placeholder saying which
  search it is; not ticked, Enter is the ordinary search; the home page's
  tile; the line on the ordinary search's results.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8144
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/usr/bin/google-chrome"
fails: list[str] = []

SEEN = "try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no'); } catch (e) {}"
Q1 = "Why does God allow suffering?"
Q2 = "How do prayer and worship differ?"
QRU = "Чем молитва отличается от поклонения?"


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def fresh(b, w=1280, h=900, settings=None):
    ctx = b.new_context(viewport={"width": w, "height": h}, service_workers="block")
    ctx.add_init_script(SEEN + (" try { localStorage.setItem('ub_settings', %s); } catch (e) {}"
                                % json.dumps(json.dumps(settings)) if settings else ""))
    pg = ctx.new_page()
    pg.errors, pg.asked = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("request", lambda r: pg.asked.append((r.method, r.url, r.post_data)))
    return ctx, pg


def at(q: str) -> str:
    return BASE + "/meaning#q=" + urllib.parse.quote(q, safe="")


def answered(pg, timeout=20000):
    pg.wait_for_selector(".mnout:not([hidden]) .mnp", timeout=timeout)
    pg.wait_for_timeout(250)


STATE = """() => ({
  box: document.querySelector('.mnq').value,
  hash: decodeURIComponent(location.hash),
  entries: document.querySelectorAll('.mnix .mnentries a').length,
  passages: document.querySelectorAll('.mnp').length,
  paras: document.querySelectorAll('.mnlist p.t[id]').length,
  ids: [...document.querySelectorAll('.mnlist p.t[id]')].map(p => p.id),
  kjv: [...document.querySelectorAll('.mnbible li')].filter(x => x.getClientRects().length).length,
  ix: !!document.querySelector('.mnix') && document.querySelector('.mnix').getClientRects().length > 0,
  lead: document.querySelector('.mnlead').getClientRects().length > 0,
  tries: document.querySelector('.mntry').getClientRects().length > 0,
  say: document.querySelector('.mnsay').hidden ? '' : document.querySelector('.mnsay').textContent,
  wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  words: (document.querySelector('.mnanswer') || {dataset: {}}).dataset.words || '',
  first: (document.querySelector('.mnlist p.t[id]') || {id: ''}).id,
})"""


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)

        print("a question")
        ctx, pg = fresh(b)
        pg.goto(BASE + "/meaning")
        pg.wait_for_function("() => window.ubMeaning")
        s = pg.evaluate(STATE)
        ok(s["lead"] and s["tries"] and not s["passages"] and not s["say"],
           "the page opens with what it is and its examples, and nothing asked")
        ok(pg.evaluate("() => document.activeElement === document.querySelector('.mnq')"), "the box has the keys on a desk")
        ok(pg.locator("a.mnex").count() == 6, "six examples")
        pg.locator("a.mnex").nth(1).click()
        answered(pg)
        s = pg.evaluate(STATE)
        ok(s["box"] == Q1 and s["hash"] == "#q=" + Q1, f"an example tapped is asked: the box and the address have it ({s['hash']})")
        ok(s["entries"] >= 3 and s["passages"] == 20 and s["paras"] >= s["passages"] and s["kjv"] >= 3,
           f"the answer: {s['entries']} index entries, {s['passages']} passages of {s['paras']} paragraphs, {s['kjv']} of the KJV")
        heads = pg.evaluate("""() => [...document.querySelectorAll('.mnanswer > section')].filter(x => x.getClientRects().length).map(x => {
            const c = x.querySelector('h2').cloneNode(true); c.querySelectorAll('x-ru').forEach(y => y.remove());
            return c.textContent.replace(/\\s+/g, ' ').trim(); })""")
        notes = pg.evaluate("() => document.querySelectorAll('.mnnotes li').length")
        want = ([f"In the index ({s['entries']})", "In the text (20)"] + ([f"In the study notes ({notes})"] if notes else [])
                + [f"In the King James Version ({s['kjv']})"])
        ok(heads == want, f"each list says how many it holds: {heads}")
        rows = pg.evaluate("""() => { const ls = [...document.querySelectorAll('.mnentries li')];
            return {n: ls.length, tops: new Set(ls.map(l => Math.round(l.getBoundingClientRect().top))).size,
                    lines: ls.map(l => Math.round(l.getBoundingClientRect().height / parseFloat(getComputedStyle(l).lineHeight)))}; }""")
        ok(rows["n"] == rows["tops"] and all(n == 1 for n in rows["lines"]),
           f"the index's entries one to a line, none wrapped on a desk ({rows['lines']})")
        ok(len(set(s["ids"])) == len(s["ids"]), "no paragraph twice")
        ok(not s["lead"] and not s["tries"] and not s["say"], "what the page is and its examples make way for the answer")
        ok(pg.evaluate("() => !!document.querySelector('.mnlist p.t .jesus, .mnlist p.t .num')"),
           "a passage is set as the text is: its reference, the red letter")
        first1 = s["first"]
        pg.locator(".mnq").fill(Q2)
        pg.keyboard.press("Enter")
        pg.wait_for_function("(q) => decodeURIComponent(location.hash) === '#q=' + q", arg=Q2)
        pg.wait_for_function("(f) => { const p = document.querySelector('.mnlist p.t[id]'); return p && p.id !== f; }", arg=first1)
        s2 = pg.evaluate(STATE)
        ok(s2["box"] == Q2 and s2["first"] != first1, f"typed and entered: another answer ({s2['first']})")
        n = len([a for a in pg.asked if a[0] == "POST"])
        pg.locator(".mngo").click()
        pg.wait_for_timeout(600)
        ok(len([a for a in pg.asked if a[0] == "POST"]) == n + 1, "the button asks the same question again")
        pg.go_back()
        pg.wait_for_function("(f) => { const p = document.querySelector('.mnlist p.t[id]'); return p && p.id === f; }", arg=first1)
        ok(pg.evaluate(STATE)["box"] == Q1, "Back: the question before, asked again, in the box")
        posts = [a for a in pg.asked if a[0] == "POST"]
        ok(all(a[1] == BASE + "/meaning/find" for a in posts) and all(json.loads(a[2])["q"] in (Q1, Q2) for a in posts),
           f"{len(posts)} questions, each in a POST's body to /meaning/find")
        leaked = [a[1] for a in pg.asked if "suffering" in urllib.parse.unquote(a[1]) or "prayer" in urllib.parse.unquote(a[1])]
        ok(not leaked, "no question in any address asked of the server" + (f": {leaked[:2]}" if leaked else ""))
        ok(not pg.errors, "no error in the page" + (f": {pg.errors[:2]}" if pg.errors else ""))

        print("a link followed, and Back")
        pg.evaluate("() => document.querySelectorAll('.mnp')[5].scrollIntoView()")
        pg.wait_for_timeout(200)
        y = pg.evaluate("() => Math.round(scrollY)")
        href = pg.evaluate("() => document.querySelectorAll('.mnp')[5].querySelector('a.mnwhere').getAttribute('href')")
        pg.locator(".mnp").nth(5).locator("a.mnwhere").click()
        pg.wait_for_url(lambda u: "/meaning" not in u)
        ok(urllib.parse.urlparse(pg.url).path == href.split("-")[0].rsplit(".", 1)[0] or href in pg.url,
           f"a passage's link goes to its place ({pg.url.replace(BASE, '')})")
        pg.go_back()
        answered(pg)
        pg.wait_for_timeout(500)
        y2 = pg.evaluate("() => Math.round(scrollY)")
        ok(abs(y2 - y) <= 4, f"Back: the answer again, at the line left ({y} px, {y2} px)")
        ctx.close()

        ctx, pg = fresh(b, settings={"whole": True})
        pg.goto(at(Q1))
        answered(pg)
        href = pg.evaluate("() => document.querySelector('.mnp a.mnwhere').getAttribute('href')")
        pg.locator(".mnp a.mnwhere").first.click()
        pg.wait_for_url(lambda u: "/meaning" not in u)
        paper = href.split(":")[0]
        ok(urllib.parse.urlparse(pg.url).path == paper and urllib.parse.urlparse(pg.url).fragment == href[1:],
           f"with Whole paper on the link goes to the paper's page, at the passage ({pg.url.replace(BASE, '')})")
        ctx.close()

        print("the reader's texts")
        ctx, pg = fresh(b, settings={"translations": "uf-ru"})
        pg.goto(at(Q1))
        answered(pg)
        pg.wait_for_function("() => [...document.querySelectorAll('.mnlist .trfold')].some(b => b.textContent)")
        folds = pg.evaluate("() => [...document.querySelectorAll('.mnlist .tf[data-has~=\"uf-ru\"] .trfold')].map(b => b.textContent)")
        ok(folds and all("1" in f for f in folds), f"each of {len(folds)} folds says how many it holds")
        ok(pg.evaluate("() => document.querySelectorAll('.mnlist .tf.open').length") == 0, "folded, as the reader keeps them")
        tr_asked = len([a for a in pg.asked if "/tr/" in a[1]])
        ok(tr_asked == 0, "and nothing asked of the translations until one is opened")
        pg.locator(".mnlist .trfold").nth(2).click()
        pg.wait_for_function("() => document.querySelectorAll('.mnlist .tf.open .tr p.rt').length >= document.querySelectorAll('.mnlist .tf[data-has]').length")
        o = pg.evaluate("() => ({open: document.querySelectorAll('.mnlist .tf.open').length, all: document.querySelectorAll('.mnlist .tf[data-has]').length,"
                        " ru: [...document.querySelectorAll('.mnlist .tf.open .tr p.rt')].every(p => p.lang === 'ru' && /[а-я]/.test(p.textContent))})")
        ok(o["open"] == o["all"] and o["ru"], f"a tap on one opens them all, each the translation's words ({o['open']} of {o['all']})")
        chip = pg.evaluate("""() => { const a = document.querySelector('.mnlist .row > .a .chips a'); if (!a) return null;
            a.scrollIntoView({block: 'center'}); const r = a.getBoundingClientRect();
            const e = document.elementFromPoint(r.left + Math.min(r.width, 40) / 2, r.top + r.height / 2);
            return {href: a.getAttribute('href'), under: e === a || a.contains(e)}; }""")
        ok(chip and chip["href"].startswith(("/i/", "/appendix/")) and chip["under"],
           f"the entries that brought a passage stand beside it, each a link under the pointer ({chip})")
        ctx.close()

        ctx, pg = fresh(b, 390, 844, settings={"translations": "uf-ru", "english": "1"})
        pg.goto(at(Q1))
        answered(pg)
        pg.wait_for_function("() => document.querySelectorAll('.mnlist .row[data-ftx]').length > 0")
        o = pg.evaluate("() => { const ps = [...document.querySelectorAll('.mnlist p.t[id]')];"
                        " return {n: ps.length, ru: ps.filter(p => p.lang === 'ru').length, en: [...document.querySelectorAll('.mnlist p.t.enoff, .mnlist .enoff')].length,"
                        " wide: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }")
        ok(o["n"] and o["ru"] == o["n"] and o["wide"] <= 0,
           f"with a translation first its words stand where the English stood, under the paragraph's address ({o['ru']} of {o['n']})")
        ok(not pg.errors, "no error in the page" + (f": {pg.errors[:2]}" if pg.errors else ""))
        ctx.close()

        print("the lists' width")
        for width, want in (("full", "the whole page"), ("measure", "the measure")):
            for mw in (1280, 1920):
                ctx, pg = fresh(b, mw, 900, settings={"width": width})
                pg.goto(at(Q1))
                answered(pg)
                o = pg.evaluate("""() => { const w = s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().width) : 0; };
                    return {main: w('main.meaning') - 2 * parseFloat(getComputedStyle(document.querySelector('main.meaning')).paddingLeft),
                            grid: w('.mnp .grid'), text: w('.mnp p.t'), kjv: w('.mnbible .hits'), ix: w('.mnentries'),
                            measure: Math.round(document.querySelector('.mnform').getBoundingClientRect().width),
                            wide: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""")
                same = abs(o["kjv"] - o["text"]) <= 2 and abs(o["ix"] - o["text"]) <= 2 and o["wide"] <= 0
                if width == "full":
                    ok(same and o["kjv"] > o["measure"] + 50, f"Width Full, {mw} px: the lists as wide as the passages' text, past the measure ({o})")
                else:
                    ok(same and abs(o["kjv"] - o["measure"]) <= 2, f"Width Measured, {mw} px: the lists at {want}, as the text is ({o})")
                ctx.close()
        ctx, pg = fresh(b, 1920, 900, settings={"width": "full", "margin": "off"})
        pg.goto(at(Q1))
        answered(pg)
        o = pg.evaluate("""() => { const w = s => Math.round(document.querySelector(s).getBoundingClientRect().width);
            return {main: Math.round(w('main.meaning') - 2 * parseFloat(getComputedStyle(document.querySelector('main.meaning')).paddingLeft)),
                    text: w('.mnp p.t'), kjv: w('.mnbible .hits'), ix: w('.mnentries')}; }""")
        ok(abs(o["kjv"] - o["text"]) <= 2 and abs(o["ix"] - o["text"]) <= 2 and abs(o["text"] - o["main"]) <= 2,
           f"Width Full with the index folded: the passages and the lists the whole page ({o})")
        ctx.close()
        ctx, pg = fresh(b, 390, 844, settings={"width": "full"})
        pg.goto(at(Q1))
        answered(pg)
        o = pg.evaluate("""() => { const w = s => Math.round(document.querySelector(s).getBoundingClientRect().width);
            return {text: w('.mnp p.t'), kjv: w('.mnbible .hits'), ix: w('.mnentries'), wide: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""")
        ok(abs(o["kjv"] - o["text"]) <= 2 and abs(o["ix"] - o["text"]) <= 2 and o["wide"] <= 0, f"and on a phone ({o})")
        ctx.close()

        print("the switches")
        ctx, pg = fresh(b, settings={"index": False, "biblesearch": False})
        pg.goto(at(Q1))
        answered(pg)
        s = pg.evaluate(STATE)
        margin = pg.evaluate("() => [...document.querySelectorAll('.mnlist .row > .a')].filter(a => a.getClientRects().length).length")
        ok(not s["ix"] and margin == 0, "Index and appendices off: no row of entries, no margin")
        ok(s["kjv"] == 0, "The Bible in search results off: no list of the King James Version")
        ok(s["passages"] >= 10, "the passages stand")
        ctx.close()

        print("in Russian")
        ctx, pg = fresh(b, 390, 844, settings={"lang": "ru"})
        pg.goto(at(QRU))
        answered(pg)
        s = pg.evaluate(STATE)
        h1 = pg.evaluate("() => [...document.querySelectorAll('main.meaning h1 *')].filter(x => x.getClientRects().length).map(x => x.textContent).join('')")
        ok(h1 == "Поиск по смыслу" and s["words"] == "ru" and s["passages"] >= 10 and s["wide"] <= 0,
           f"a Russian question, the interface in Russian, a phone's width ({s['passages']} passages, first {s['first']})")
        ok("5:3.3" in s["ids"] or "143:7.7" in s["ids"], "and the passage that says how prayer and worship differ among them")
        ctx.close()

        print("the network taken away, and a question too long")
        ctx, pg = fresh(b)
        pg.goto(BASE + "/meaning")
        pg.wait_for_function("() => window.ubMeaning")
        ctx.set_offline(True)
        pg.locator(".mnq").fill(Q1)
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => !document.querySelector('.mnsay').hidden && !/Looking/.test(document.querySelector('.mnsay').textContent)")
        s = pg.evaluate(STATE)
        ok("needs the network" in s["say"] and not s["passages"], "offline the page says Search by meaning needs the network")
        ctx.set_offline(False)
        pg.locator(".mngo").click()
        answered(pg)
        ok(pg.evaluate(STATE)["passages"] >= 10, "and answers when the network is back")
        pg.goto(at("x" * 301))
        pg.wait_for_function("() => !document.querySelector('.mnsay').hidden")
        ok("300" in pg.evaluate(STATE)["say"], "a question over 300 characters is refused in words, and not sent")
        ctx.close()

        print("the ways in")
        for lang in ("en", "ru"):
            for w in (320, 390, 836, 1280):
                for size in ("90", "100", "112.5", "125"):
                    ctx, pg = fresh(b, w, 800, {"lang": lang, "uisize": size})
                    pg.goto(BASE + "/1:0")
                    pg.wait_for_selector(".find .bym:not([hidden])")
                    pg.wait_for_timeout(150)
                    o = pg.evaluate("""() => { const f = document.querySelector('.find input[name="q"]').getBoundingClientRect(),
                        a = document.querySelector('.find .bym'), r = a.getBoundingClientRect(), t = a.querySelector('input').getBoundingClientRect(),
                        e = document.elementFromPoint(t.left + t.width / 2, t.top + t.height / 2);
                        return {in: r.left >= f.left && r.right <= f.right + .5 && r.top >= f.top - .5 && r.bottom <= f.bottom + .5,
                                under: e === a.querySelector('input'), room: Math.round(r.left - f.left - parseFloat(getComputedStyle(document.querySelector('.find input[name="q"]')).paddingLeft)),
                                wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                                words: [...a.querySelectorAll('span *')].filter(x => x.getClientRects().length).map(x => x.textContent).join('')}; }""")
                    ok(o["in"] and o["under"] and o["wide"] <= 0 and o["room"] >= 70 and o["words"],
                       f"{lang} {w} px, {size}%: the tick inside the box and under the pointer, {o['room']} px to type in"
                       + ("" if o["in"] and o["under"] and o["wide"] <= 0 and o["room"] >= 70 else f" ({o})"))
                    ctx.close()
        ctx, pg = fresh(b, 390, 844)
        pg.goto(BASE + "/1:0")
        pg.wait_for_selector(".find .bym:not([hidden])")
        box, tick = pg.locator('.find input[name="q"]'), pg.locator(".find .bym input")
        ok(not tick.is_checked() and "citation" in box.get_attribute("placeholder"), "the tick is off at first, the box the ordinary search's")
        box.fill("prayer")
        pg.keyboard.press("Enter")
        pg.wait_for_url(lambda u: "/search?q=prayer" in u)
        ok(True, "not ticked, Enter is the ordinary search")
        pg.goto(BASE + "/1:0")
        pg.wait_for_selector(".find .bym:not([hidden])")
        pg.locator(".find .bym").click()
        ok(tick.is_checked() and "question" in box.get_attribute("placeholder")
           and pg.evaluate("() => document.activeElement === document.querySelector('.find input[name=\"q\"]')"),
           "ticked: the box says it takes a question, and has the keys")
        pg.keyboard.type("  life after   death ")
        pg.keyboard.press("Enter")
        pg.wait_for_url(lambda u: "/meaning#q=" in u)
        answered(pg)
        s = pg.evaluate(STATE)
        ok(s["box"] == "life after death" and s["hash"] == "#q=life after death", "ticked, Enter asks the box's words by meaning")
        ok(pg.locator(".find .bym input").is_checked() and pg.locator('.find input[name="q"]').input_value() == "life after death",
           "the tick is kept on the next page, and the header's box holds the question")
        first = s["first"]
        pg.locator('.find input[name="q"]').fill("mercy")
        pg.keyboard.press("Enter")
        pg.wait_for_function("(f) => { const p = document.querySelector('.mnlist p.t[id]'); return p && p.id !== f; }", arg=first)
        ok(pg.evaluate(STATE)["hash"] == "#q=mercy", "on the page itself the header's box asks again")
        n = len([a for a in pg.asked if a[0] == "POST"])
        pg.locator('.find input[name="q"]').press("Enter")
        pg.wait_for_timeout(600)
        ok(len([a for a in pg.asked if a[0] == "POST"]) == n + 1, "and the same words again are asked again")
        leaked = [a[1] for a in pg.asked if "mercy" in a[1] or "death" in urllib.parse.unquote(a[1])]
        ok(not leaked, "no question from the header's box in any address asked of the server" + (f": {leaked[:2]}" if leaked else ""))
        pg.goto(BASE + "/101:4")
        pg.wait_for_selector(".find .bym:not([hidden])")
        ok(pg.locator(".find .bym input").is_checked(), "the tick is the same on a page of the text")
        pg.locator('.find input[name="q"]').fill("")
        pg.keyboard.press("Enter")
        pg.wait_for_url(BASE + "/meaning")
        ok(True, "ticked with the box empty, Enter goes to the page")
        pg.locator(".find .bym").click()
        ok(not pg.locator(".find .bym input").is_checked(), "unticked")
        pg.goto(BASE + "/1:0")
        pg.wait_for_selector(".find .bym:not([hidden])")
        ok(not pg.locator(".find .bym input").is_checked() and "citation" in pg.locator('.find input[name="q"]').get_attribute("placeholder"),
           "and it stays unticked, the box the ordinary search's again")
        ctx.close()
        ctx, pg = fresh(b, 390, 844, {"lang": "ru"})
        pg.goto(BASE + "/1:0")
        pg.wait_for_selector(".find .bym:not([hidden])")
        pg.locator(".find .bym").click()
        ok("вопрос" in pg.locator('.find input[name="q"]').get_attribute("placeholder"), "in Russian the box says so in Russian")
        ctx.close()
        ctx, pg = fresh(b, 390, 844)
        pg.goto(BASE + "/")
        tile = pg.locator('.ftiles a[href="/meaning"]')
        ok(tile.count() == 1 and tile.locator("svg").count() == 1, "the home page has its tile, with its drawing")
        tile.click()
        pg.wait_for_url(BASE + "/meaning")
        pg.goto(BASE + "/search?q=life%20after%20death")
        ok(pg.locator(".results .bymeaning a").get_attribute("href") == "/meaning#q=life%20after%20death",
           "the ordinary search's results have the line, with the same words")
        pg.locator(".results .bymeaning a").click()
        pg.wait_for_url(lambda u: "/meaning#q=" in u)
        answered(pg)
        ok(pg.evaluate(STATE)["box"] == "life after death", "which asks them")
        ok(not pg.errors, "no error in the page" + (f": {pg.errors[:2]}" if pg.errors else ""))
        ctx.close()
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
    env.pop("UB_MEANING", None)
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", NO_COPY,
                            str(ROOT / "var" / "no-offline-copy"), str(PORT)], cwd=ROOT, env=env)
    try:
        for _ in range(300):
            try:
                with urllib.request.urlopen(BASE + "/healthz", timeout=1) as r:
                    if json.load(r).get("meaning") is True:
                        break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            print("the server did not load the model (var/embed/bge-m3/, var/embed.db)")
            return 1
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
