"""The player's section buttons, end to end, in Chrome (Tigran, 2026-11-23):
⏮⏮ and ⏭⏭ around the paragraph's ⏮ and ⏭ (listen.js secBack, secNext,
secStep, carryOn), the same press with Whole paper off and on.

Held here: ⏮⏮ once goes to the start of the section being heard, its spoken
heading; twice in quick succession to the start of the section before, and
three times to the one before that, across a paper's edge (101:1 to 100:7),
a press made while the section before is fetched counted and taken once it
is in; ⏭⏭ to the start of the next.  With Whole paper off each step to
another section brings its page into this one, as "Next" does, at its
address; with it on a step within the paper fetches nothing, and one past
its ends brings in the paper before, whole, at its last section, brought
into view, or the paper after at its first.  The bar never says "End of the
section" or offers "Next" while a section is fetched, and plays on in the
new one.  ⏭⏭ is greyed at the book's end alone, and ⏮⏮ twice at 0:0 stays
there.  ⏮ pressed twice while a paper's title is read goes to the last
paragraph of the paper before, and with Whole paper off a section's title to
the section before's; ⏭ at a paper's last paragraph to the next paper's
title, and at the book's last nowhere.  Presses made while a page comes are
all taken once it is in: ⏮⏮ four times at 101:0 is 100:5.  On a phone, by taps.  In the browser's voice the steps ask for each
section's spoken text; in Григорий Войнер's reading of USGNY a step into
19:0, which his recording lacks, is the browser's voice, and a step out of it
his recording again.  With Follow along off and the reader on another page,
the reading moves and the page stays.  And × or a ▶ in the page while a
section is on its way leaves it behind.

    .venv/bin/python tools/secstep_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8146 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate, like
listen_tr_e2e.py: tests/test_whole.py holds the static facts.
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
PORT = "8146"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []

AT = "() => (document.querySelector('.player .at') || {}).textContent || null"
PLAYING = "document.querySelector('.player .toggle').getAttribute('aria-label') === 'Pause'"
# Watches the bar from now on for the end of a section said or "Next" offered.
WATCH = """() => { window.ubSawEnd = false; const b = document.querySelector('.player'),
    look = () => { if (/End of the/.test(b.querySelector('.who').textContent) || !b.querySelector('.onward').hidden) window.ubSawEnd = true; };
  new MutationObserver(look).observe(b, { subtree: true, childList: true, characterData: true, attributes: true }); }"""
# A browser that lists voices and never finishes speaking (listen_tr_e2e.py
# VOICES): what is read stays where a step put it.
VOICES = """
(() => {
  const V = [{ name: 'English (America)', lang: 'en-US', default: true, localService: true },
             { name: 'Russian', lang: 'ru-RU', default: false, localService: true }];
  const fake = { speaking: false, pending: false, paused: false, onvoiceschanged: null,
    getVoices: () => V, pause() {}, resume() {}, addEventListener() {}, removeEventListener() {}, cancel() {}, speak() {} };
  Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true });
  // Its voices are no SpeechSynthesisVoice, so neither is the utterance.
  window.SpeechSynthesisUtterance = function (t) { this.text = t; };
})();
"""


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, js: str, timeout: float = 10.0) -> bool:
    """Poll an expression until it is true (trap 41)."""
    end = time.time() + timeout
    while time.time() < end:
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(100)
    return False


def context(b, settings: dict, phone: bool = False, wide: bool = False):
    ctx = (b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
           if phone else b.new_context(viewport={"width": 1920 if wide else 1400, "height": 900}))
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    # What the player asks for: the recordings and spoken texts, and the pages
    # it fetches for listening (X-UB-Fetch), each by its path.
    asked: list[str] = []
    pages: list[str] = []

    def req(r):
        path = urllib.parse.urlparse(r.url).path
        if "/audio/" in r.url or "/speech/" in r.url:
            asked.append(path)
        elif r.headers.get("x-ub-fetch") == "next":
            pages.append(path)
    pg.on("request", req)
    # And each address given the <audio>: one had whole plays again from
    # Chrome's cache with no request (listen_tr_e2e.py context).
    ctx.expose_binding("ubHeard", lambda _src, path: asked.append(path))
    ctx.add_init_script("""(() => { const d = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
      Object.defineProperty(HTMLMediaElement.prototype, 'src', { configurable: true, get() { return d.get.call(this); },
        set(v) { if (v && window.ubHeard) window.ubHeard(new URL(v, location.href).pathname); d.set.call(this, v); } });
    })();""")
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, asked, pages, errors


def press(pg, sel: str, n: int = 1, phone: bool = False) -> None:
    """n presses in quick succession, by the mouse or by taps; then a pause
    longer than the 400 ms that makes the next one a press of its own."""
    if phone:
        for _ in range(n):
            pg.tap(sel)
    else:
        pg.click(sel, click_count=n)
    pg.wait_for_timeout(450)


def at(pg, ref: str, path: str | None = None, timeout: float = 10.0) -> bool:
    return until(pg, f"(({AT})() === {json.dumps(ref)})" + (f" && location.pathname === {json.dumps(path)}" if path else ""),
                 timeout)


def start(pg, ref: str) -> None:
    sel = f"[id='{ref}'] .stk > .playp"
    pg.wait_for_selector(sel, timeout=15000)
    pg.click(sel)
    until(pg, f"(({AT})() === {json.dumps(ref)})")


def steps(b, whole: bool, phone: bool = False) -> None:
    say = ("Whole paper on" if whole else "Whole paper off") + (", a phone" if phone else "") + ": "
    print("\n" + say.rstrip(": "))
    ctx, pg, asked, pages, errors = context(b, {"whole": True} if whole else {}, phone=phone)
    pg.goto(BASE + ("/101" if whole else "/101:2"))
    here = "/101" if whole else "/101:2"
    start(pg, "101:2.3")
    ok(pg.evaluate(AT) == "101:2.3" and until(pg, PLAYING), say + "101:2.3's ▶ plays it")
    bar = pg.evaluate("[...document.querySelector('.player').children].filter(e => e.matches('button')).map(e => e.className)")
    ok(bar[:5] == ["sprev", "prev", "toggle", "next", "snext"], say + f"⏮⏮ ⏮ ⏵ ⏭ ⏭⏭, the section's around the paragraph's ({bar[:5]})")
    tips = pg.evaluate("[...document.querySelectorAll('.player :is(.sprev, .snext)')].map(e => [e.title, e.getAttribute('aria-label')])")
    ok(tips == [["Back to the start of this section (twice: the one before)"] * 2, ["Next section"] * 2],
       say + f"each named ({tips})")

    # Once: the start of this section, its spoken heading, in this page.
    sel = ".player .sprev"
    press(pg, sel, phone=phone)
    ok(at(pg, "101:2", here) and until(pg, PLAYING), say + f"⏮⏮ once: 101:2 from its heading ({pg.evaluate(AT)})")
    # Twice: the section before.
    del pages[:]
    pg.evaluate(WATCH)
    press(pg, sel, 2, phone=phone)
    ok(at(pg, "101:1", "/101" if whole else "/101:1") and until(pg, PLAYING),
       say + f"⏮⏮ twice: 101:1 from its heading, playing ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
    ok(pages == ([] if whole else ["/101:1"]),
       say + ("within the paper, nothing fetched" if whole else "its page brought into this one") + f" ({pages})")
    ok(asks_file(asked, "/audio/mh/paper101/P101_01"), say + "in its own file")
    # Three times: the one before that, across the paper's edge, the third
    # press made while 101:0 is fetched where Whole paper is off.
    del pages[:]
    press(pg, sel, 3, phone=phone)
    ok(at(pg, "100:7", "/100" if whole else "/100:7") and until(pg, PLAYING),
       say + f"⏮⏮ three times: across the paper's edge to 100:7 ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
    ok(pages == (["/100"] if whole else ["/101:0", "/100:7"]), say + f"by way of 101:0 ({pages})")
    if whole:
        top = "document.querySelector(\"section[id='100:7'] .papertop h2\").getBoundingClientRect().top"
        # Where the smooth scroll stops: the same place twice, 300 ms apart.
        was = None
        for _ in range(20):
            pg.wait_for_timeout(300)
            now = pg.evaluate(top)
            if now == was:
                break
            was = now
        h = pg.evaluate("innerHeight")
        ok(0 <= now <= h * .6, say + f"the paper before, whole, at its last section, brought into view ({now:.0f} of {h} px)")
    # On: the next section, the next paper's first.
    del pages[:]
    press(pg, ".player .snext", phone=phone)
    ok(at(pg, "101:0", "/101" if whole else "/101:0") and until(pg, PLAYING),
       say + f"⏭⏭: 101:0, the next paper's first ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
    press(pg, ".player .snext", phone=phone)
    ok(at(pg, "101:1", "/101" if whole else "/101:1"), say + f"⏭⏭ again: 101:1 ({pg.evaluate(AT)})")
    ok(pages == (["/101"] if whole else ["/101:0", "/101:1"]), say + f"fetched only across a paper's edge where whole ({pages})")
    ok(not pg.evaluate("window.ubSawEnd"), say + "the bar never said the section had ended, nor offered Next, on the way")
    ok(not pg.evaluate("document.querySelector('.player .snext').disabled"), say + "⏭⏭ live")
    # The paragraph's buttons are as they were.
    press(pg, ".player .next", phone=phone)
    ok(at(pg, "101:1.1"), say + f"⏭ still the next paragraph ({pg.evaluate(AT)})")
    ok(not errors, say + "no script error: " + "; ".join(errors))
    ctx.close()


def asks_file(asked: list, stem: str) -> bool:
    return any(a.startswith(stem + ".") for a in asked)


# The refs of the voice heard, Merritt Horn's, in the page's own data.
SEGS = "() => JSON.parse(document.getElementById('ub-audio').textContent).voices.mh.segs.map(s => s[0])"


def heading(pg, ref: str) -> None:
    """The first paragraph's ▶, which starts from the section's heading."""
    sel = f"[id='{ref}.1'] .stk > .playp"
    pg.wait_for_selector(sel, timeout=15000)
    pg.click(sel)
    until(pg, f"(({AT})() === {json.dumps(ref)})")


def para_back(b) -> None:
    """⏮ twice while a paper's title is read goes to the last paragraph of
    the paper before (Tigran, 2026-11-23); three times to the one before
    that; with Whole paper off a section's title to the last paragraph of the
    section before; at 0:0 nowhere."""
    for whole in (False, True):
        say = "Whole paper on: " if whole else "Whole paper off: "
        print("\n⏮ twice at a title, " + say.rstrip(": "))
        ctx, pg, asked, pages, errors = context(b, {"whole": True} if whole else {})
        pg.goto(BASE + ("/101" if whole else "/101:0"))
        heading(pg, "101:0")
        ok(pg.evaluate(AT) == "101:0" and until(pg, PLAYING), say + "101:0's ▶ reads the paper's title first")
        press(pg, ".player .prev", 2)
        ok(until(pg, f"location.pathname === {json.dumps('/100' if whole else '/100:7')}"),
           say + f"⏮ twice: the paper before ({pg.evaluate('location.pathname')})")
        segs = pg.evaluate(SEGS)
        ok(at(pg, segs[-1]) and segs[-1].startswith("100:7.") and until(pg, PLAYING),
           say + f"from its last paragraph, playing ({pg.evaluate(AT)}, {segs[-1]})")
        para = f"document.getElementById({json.dumps(segs[-1])}).getBoundingClientRect()"
        ok(until(pg, f"(r => r.top >= 0 && r.bottom <= innerHeight)({para})", 5), say + "brought into view")
        # Back to the title, by ⏭⏭, and three times: one more.
        press(pg, ".player .snext")
        ok(at(pg, "101:0", "/101" if whole else "/101:0"), say + f"⏭⏭: 101:0 again ({pg.evaluate(AT)})")
        press(pg, ".player .prev", 3)
        segs = pg.evaluate(SEGS)
        ok(at(pg, segs[-2], "/100" if whole else "/100:7"),
           say + f"⏮ three times: the paragraph before the last ({pg.evaluate(AT)}, {segs[-2]})")
        # ⏭ likewise, from the paper's last paragraph into the next paper's
        # title (Tigran, the same day); three times quick, two paragraphs on.
        press(pg, ".player .next")
        ok(at(pg, segs[-1]), say + f"⏭: the last paragraph ({pg.evaluate(AT)})")
        press(pg, ".player .next")
        ok(at(pg, "101:0", "/101" if whole else "/101:0") and until(pg, PLAYING),
           say + f"⏭ at the paper's last paragraph: the next paper, from its title ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
        press(pg, ".player .prev", 2)
        ok(at(pg, segs[-1], "/100" if whole else "/100:7"), say + f"⏮ twice: back at the last paragraph ({pg.evaluate(AT)})")
        press(pg, ".player .next", 3)
        ok(at(pg, "101:0.2", "/101" if whole else "/101:0") and until(pg, PLAYING),
           say + f"⏭ three times quick there: 101:0.2, two on from the title ({pg.evaluate(AT)})")
        # ⏮⏮ four times from a paper's first section: across the edge and two
        # more, the presses counted while the paper before came all taken.
        press(pg, ".player .sprev", 4)
        ok(at(pg, "100:5", "/100" if whole else "/100:5") and until(pg, PLAYING),
           say + f"⏮⏮ four times at 101:0: 100:5 ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
        pg.wait_for_timeout(1500)
        ok(pg.evaluate(AT).startswith("100:5"), say + f"and nothing more taken after ({pg.evaluate(AT)})")
        if not whole:
            # A section's title, on a section's page: the section before's last.
            pg.goto(BASE + "/101:2")
            heading(pg, "101:2")
            press(pg, ".player .prev", 2)
            ok(until(pg, "location.pathname === '/101:1'"), f"{say}at 101:2's title, ⏮ twice: 101:1 ({pg.evaluate('location.pathname')})")
            segs = pg.evaluate(SEGS)
            ok(at(pg, segs[-1]) and segs[-1].startswith("101:1."), say + f"its last paragraph ({pg.evaluate(AT)})")
        del pages[:]
        pg.goto(BASE + ("/0" if whole else "/0:0"))
        heading(pg, "0:0")
        press(pg, ".player .prev", 2)
        ok(at(pg, "0:0", "/0" if whole else "/0:0") and pages == [], say + f"at 0:0's title, ⏮ twice stays there ({pg.evaluate(AT)}, {pages})")
        ok(not errors, say + "no script error: " + "; ".join(errors))
        ctx.close()


def ends(b) -> None:
    print("\nThe book's ends")
    for whole in (False, True):
        say = "Whole paper on: " if whole else "Whole paper off: "
        ctx, pg, asked, pages, errors = context(b, {"whole": True} if whole else {})
        pg.goto(BASE + ("/196" if whole else "/196:3"))
        start(pg, "196:3.1")
        ok(until(pg, "document.querySelector('.player .snext').disabled"), say + "⏭⏭ greyed in the book's last section")
        col = pg.evaluate("getComputedStyle(document.querySelector('.player .snext')).color")
        rule = pg.evaluate("(() => { const e = document.createElement('i'); e.style.color = 'var(--rule)'; document.body.appendChild(e);"
                           " const c = getComputedStyle(e).color; e.remove(); return c; })()")
        ok(col == rule, say + f"in the transport bar's grey ({col})")
        last = pg.evaluate(SEGS)[-1]
        start(pg, last)
        del pages[:]
        press(pg, ".player .next")
        ok(pg.evaluate(AT) == last and pages == [], say + f"⏭ at the book's last paragraph stays there ({pg.evaluate(AT)}, {pages})")
        if whole:
            start(pg, "196:2.1")
            ok(until(pg, "!document.querySelector('.player .snext').disabled"), say + "and live in the section before it")
        del pages[:]
        pg.goto(BASE + ("/0" if whole else "/0:0"))
        start(pg, "0:0.2")
        press(pg, ".player .sprev", 2)
        ok(at(pg, "0:0", "/0" if whole else "/0:0") and pages == [], say + f"⏮⏮ twice at 0:0 stays there ({pg.evaluate(AT)}, {pages})")
        ok(not errors, say + "no script error: " + "; ".join(errors))
        ctx.close()


def voices(b) -> None:
    print("\nThe browser's voice, and Григорий Войнер's reading of USGNY")
    ctx, pg, asked, pages, errors = context(b, {"voice": "browser"})
    ctx.add_init_script(VOICES)
    pg.goto(BASE + "/101:2")
    start(pg, "101:2.3")
    del asked[:]
    press(pg, ".player .sprev", 2)
    ok(at(pg, "101:1", "/101:1") and "/speech/101:1" in asked,
       f"the browser's voice: ⏮⏮ twice reads 101:1, its spoken text asked for ({pg.evaluate(AT)}, {asked})")
    press(pg, ".player .snext")
    ok(at(pg, "101:2", "/101:2"), f"and ⏭⏭ 101:2 ({pg.evaluate(AT)})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()

    ctx, pg, asked, pages, errors = context(b, {"translations": "urantia-ru"}, wide=True)
    ctx.add_init_script(VOICES)
    pg.goto(BASE + "/19:1")
    cell = ".rc[data-k='urantia-ru']:has(p.rt[data-ref='19:1.2']) .stk > .playp"
    pg.wait_for_selector(cell, timeout=15000)
    pg.click(cell)
    voice = "() => document.querySelector('.player .voice span').textContent"
    ok(until(pg, f"/Voyner/.test(({voice})())") and asks_file(asked, "/audio/voyner/19-01"), "USGNY's ▶ at 19:1.2: his recording")
    del asked[:]
    press(pg, ".player .sprev", 2)
    ok(at(pg, "19:0", "/19:0") and "/speech/urantia-ru/19:0" in asked and not until(pg, f"/Voyner/.test(({voice})())", 1),
       f"⏮⏮ twice: 19:0, which he does not read, in the browser's voice ({asked}, {pg.evaluate(voice)!r})")
    press(pg, ".player .next")
    ok(at(pg, "19:0.1") and until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.ref === '19:0.1'"),
       "⏭ there: the translation's line marked")
    del asked[:]
    press(pg, ".player .snext")
    ok(at(pg, "19:1", "/19:1") and until(pg, f"/Voyner/.test(({voice})())") and asks_file(asked, "/audio/voyner/19-01"),
       f"⏭⏭: 19:1 in his recording again ({pg.evaluate(voice)!r})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def roaming(b) -> None:
    print("\nFollow along off, the reader on another page")
    ctx, pg, asked, pages, errors = context(b, {"follow": False})
    pg.goto(BASE + "/101:2")
    start(pg, "101:2.3")
    # The transport bar's ⏭ under the text: followed in this page (listen.js visit).
    pg.click("nav.transport a.next")
    ok(until(pg, "location.pathname === '/101:3'") and until(pg, PLAYING), "a link while it plays shows 101:3, and it plays on")
    press(pg, ".player .sprev", 2)
    ok(at(pg, "101:1") and pg.evaluate("location.pathname") == "/101:3",
       f"⏮⏮ twice: 101:1 is heard, and the page stays at 101:3 ({pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
    ok(until(pg, PLAYING), "playing")
    press(pg, ".player .snext")
    ok(at(pg, "101:2") and pg.evaluate("location.pathname") == "/101:3", f"⏭⏭: 101:2, the page still 101:3 ({pg.evaluate(AT)})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


# The pages fetched for listening held back window.ubHold ms, in the page.
HOLD = """
(() => { const f = window.fetch;
  window.fetch = function (u, o) {
    if (o && o.headers && o.headers['X-UB-Fetch'] === 'next' && window.ubHold)
      return new Promise(r => setTimeout(r, window.ubHold)).then(() => f.call(this, u, o));
    return f.call(this, u, o); }; })();
"""


def abandon(b) -> None:
    """A section on its way is left behind by × or by a ▶ in the page: what
    it brings is dropped, the page stays, and the ▶ plays at once."""
    print("\nA section on its way, left behind")
    for how in ("×", "▶"):
        ctx, pg, asked, pages, errors = context(b, {})
        ctx.add_init_script(HOLD)
        pg.goto(BASE + "/101:2")
        start(pg, "101:2.3")
        pg.evaluate("window.ubHold = 1500")
        pg.evaluate(WATCH)
        pg.click(".player .sprev", click_count=2)
        pg.wait_for_timeout(300)
        ok(pg.evaluate("location.pathname") == "/101:2" and pg.evaluate(AT) == "101:2" and not pg.evaluate("window.ubSawEnd"),
           f"{how}: while 101:1 comes the bar stays as it was ({pg.evaluate(AT)})")
        if how == "×":
            pg.click(".player .close")
            pg.wait_for_timeout(2000)
            ok(pg.evaluate("location.pathname") == "/101:2" and not pg.query_selector(".player"),
               f"×: the bar gone, and 101:1 never shown ({pg.evaluate('location.pathname')})")
        else:
            pg.click("[id='101:2.5'] .stk > .playp")
            ok(at(pg, "101:2.5", "/101:2", 1) and until(pg, PLAYING, 1), "▶ at 101:2.5: it plays at once")
            pg.wait_for_timeout(2000)
            ok(pages == ["/101:1"] and pg.evaluate(AT) == "101:2.5" and pg.evaluate("location.pathname") == "/101:2",
               f"▶: and 101:1, come, is dropped ({pages}, {pg.evaluate(AT)}, {pg.evaluate('location.pathname')})")
        ok(not errors, f"{how}: no script error: " + "; ".join(errors))
        ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        steps(b, False)
        steps(b, True)
        steps(b, False, phone=True)
        steps(b, True, phone=True)
        para_back(b)
        ends(b)
        voices(b)
        roaming(b)
        abandon(b)
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (listen_tr_e2e.py NO_COPY).
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
