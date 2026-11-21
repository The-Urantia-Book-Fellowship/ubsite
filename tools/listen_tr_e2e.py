"""A translation's own recording, end to end, in Chrome: Григорий Войнер's
reading of USGNY (urantia-ru), 2026-11-12.

With Whole paper off and on (CLAUDE.md trap 44), USGNY ticked, in a window
with room for it in a column beside the English (ub.js cmpFits; a setting
until 2026-11-16): the ▶ in the translation's cell plays the recording from that
paragraph, /audio/voyner/..., the bar names it "USGNY · Grigory Voyner", and
the line marked is the translation's, never the English paragraph; the
English paragraph's ▶ still plays Merritt Horn's and marks the English; the
bar's list of voices has the recording first under the translation, and a
pick there goes on in it from the same paragraph; and Settings' choice of the
browser's voice for the translation takes its ▶ from the recording, and its
default gives it back.  Settings' voices are a menu against each text, the
English first, its recording first in each and each of the browser's voices
once, in a browser that lists voices and in one that has listed none.  The bar's list has each text's recording and the browser's voices as one
list under it, the English first, and with no translation shown the English
text's alone.  Then on a phone's screen, which has no room for columns, Whole paper
off and on: the fold under a paragraph, opened, has the translation's ▶ at
the start of the line that names it, which plays the recording from there
and marks the translation's line; with three translations in tabs it is the
one shown's and no tab, and with All each has its own; and the recording
chosen in the bar marks the translation's line in the fold.  And where the recording lacks a section, 19:0: its ▶ there is
the browser's voice, and with Carry on into the next section on, a reading
that comes to it from 18:7 goes on in the browser's voice and is the
recording's again at 19:1 (the browser's speech a stand-in that is done at
once, headless Chrome's own never ending an utterance).  And the bar itself
(2026-11-21): on a phone two rows, the voice's name whole, at 320, 360 and 412
px, three text sizes, both languages, the index folded in Russian; Next at a
section's end; the time left before the speed, on a screen of seven-segment
digits read back from what is drawn, else plain figures, else none, an hour
and more as h:mm:ss; on a desk and a tablet one row, the screen never costing
the voice's name or the reference; and Follow along keeping the line being
read clear of the bar at 125%.

    .venv/bin/python tools/listen_tr_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8135 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate, like
preview_e2e.py: tests/test_readings.py holds the static facts.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = "8135"
BASE = "http://127.0.0.1:" + PORT
fails: list[str] = []

# The English of an element's words: the Russian, in <x-ru>, taken out
# (CLAUDE.md trap 33).
EN = """el => { if (!el) return ''; const c = el.cloneNode(true);
    c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent.trim(); }"""
# What is marked as being read: the translation's line, with whose it is, and
# the English paragraph.
# The English's paragraph is a p.t that is no translation's: a column's first
# line is a p.t too since 2026-11-20, its ▶ in its stack.
NOW = """() => { const l = document.querySelector('p.rt.now'), p = document.querySelector('p.t.now:not(.rt)');
    return { line: l ? l.dataset.ref : null, of: l ? l.dataset.k : null, para: p ? p.id : null }; }"""
VOICE = "() => (" + EN + ")(document.querySelector('.player .voicebox .voice'))"
# The bar's list of voices as it reads, a heading marked "# ".
BAR = """() => [...document.querySelectorAll('.player .voices > *, .player .voices [role=group] > *')]
    .map(e => (e.getAttribute('role') === 'group' ? null : (e.className === 'group' ? '# ' : '') + (%s)(e)))
    .filter(x => x !== null)""" % EN


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


def asks(pg, asked: list, path: str, timeout: float = 10.0) -> bool:
    """Wait for the page to have asked for path: a request is told of a
    moment after the tap that made it."""
    end = time.time() + timeout
    while time.time() < end:
        if path in asked:
            return True
        pg.wait_for_timeout(100)
    return False


def context(b, settings: dict, phone: bool = False, wide: bool = False):
    # The translations stand in columns where the window has room for them,
    # and in folds where it has not (ub.js cmpFits, since 2026-11-16; a
    # setting, `compare`, until then): `wide` is a desk's window with room
    # for two columns beside the Contents and the index, and the usual one,
    # 1400 px, has none, as a phone has none.
    ctx = (b.new_context(viewport={"width": 412, "height": 900}, has_touch=True, is_mobile=True)
           if phone else b.new_context(viewport={"width": 1920 if wide else 1400, "height": 900}))
    # A fresh context is a first visit, which the tour would meet (help.js).
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings)))
    pg = ctx.new_page()
    asked: list[str] = []
    pg.on("request", lambda r: asked.append(urllib.parse.urlparse(r.url).path)
          if "/audio/" in r.url or "/speech/" in r.url else None)
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, pg, asked, errors


def columns(b, whole: bool) -> None:
    settings = {"translations": "urantia-ru"}
    if whole:
        settings["whole"] = True
    ctx, pg, asked, errors = context(b, settings, wide=True)
    say = "Whole paper on: " if whole else "Whole paper off: "
    print("\nIn parallel columns, " + say.rstrip(": "))
    pg.goto(BASE + ("/1" if whole else "/1:1"))
    # In the paragraph's stack since 2026-11-20, as the first column's.
    cell = ".rc[data-k='urantia-ru']:has(p.rt[data-ref='1:1.2']) .stk > .playp"
    pg.wait_for_selector(cell, timeout=15000)
    ok(pg.get_attribute(cell, "aria-label") == "Listen to USGNY from 1:1.2", say + "the translation's cell has its ▶")

    pg.click(cell)
    ok(until(pg, "document.querySelector('p.rt.now') !== null"), say + "its ▶ starts a reading")
    ok(asks(pg, asked, "/audio/voyner/01-01.mp3") and not any(a.startswith("/speech/") for a in asked),
       say + f"which is the recording, not the browser's voice ({sorted(set(asked))})")
    ok(pg.evaluate(VOICE) == "USGNY · Grigory Voyner", say + f"the bar names it with its translation ({pg.evaluate(VOICE)!r})")
    now = pg.evaluate(NOW)
    ok(now == {"line": "1:1.2", "of": "urantia-ru", "para": None},
       say + f"and the translation's line is marked, not the English paragraph ({now})")

    # The next paragraph, by the bar: the mark follows in the translation.
    pg.click(".player .next")
    ok(until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.ref === '1:1.3'"),
       say + "the next paragraph is marked in the translation too")

    # The English paragraph's own ▶ is Merritt Horn's, and marks the English.
    del asked[:]
    pg.click("[id='1:1.4'] .playp")
    ok(until(pg, "(document.querySelector('p.t.now') || {}).id === '1:1.4'"), say + "the English ▶ marks the English paragraph")
    ok(asks(pg, asked, "/audio/mh/paper001/P001_01.mp3") and set(asked) == {"/audio/mh/paper001/P001_01.mp3"}
       and pg.evaluate(VOICE) == "Merritt Horn" and pg.evaluate(NOW)["line"] is None,
       say + f"in Merritt Horn's reading, and the translation's mark is gone ({asked}, {pg.evaluate(VOICE)!r})")

    # The bar's list: under each text its recording first, the English first.
    pg.click(".player .voicebox .voice")
    menu = pg.evaluate(BAR)
    ok(menu == ["# English text", "Merritt Horn", "Your browser’s voice",
                "# USGNY · Russian", "Grigory Voyner", "Your browser’s voice"],
       say + f"the voices list each text's recording first under it, and nowhere else ({menu})")
    del asked[:]
    pg.click(".player .voices [role=menuitemradio]:has-text('Grigory Voyner')")
    ok(until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.ref === '1:1.4'"),
       say + "picked there, it goes on from the same paragraph, marked in the translation")
    ok(asks(pg, asked, "/audio/voyner/01-01.mp3") and set(asked) == {"/audio/voyner/01-01.mp3"}
       and pg.evaluate(VOICE) == "USGNY · Grigory Voyner",
       say + f"in the recording ({asked})")

    # Settings: the browser's voice for this translation, and back.
    del asked[:]
    pg.evaluate("window.ubSettings.setTrVoice('urantia-ru', 'browser')")
    ok(until(pg, "!/Voyner/.test((%s)())" % VOICE), say + f"Settings' browser's voice takes over what is heard ({pg.evaluate(VOICE)!r})")
    ok(asks(pg, asked, "/speech/urantia-ru/1:1"), say + f"which asks for the translation's spoken text ({asked})")
    stored = json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))
    ok(json.loads(stored.get("trvoices", "{}")) == {"urantia-ru": "browser"}, say + f"and is what is stored ({stored.get('trvoices')!r})")
    del asked[:]
    pg.evaluate("window.ubSettings.setTrVoice('urantia-ru', '')")
    ok(until(pg, "/Voyner/.test((%s)())" % VOICE), say + "its default gives the recording back")
    stored = json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))
    ok("trvoices" not in stored, say + "and nothing is stored for the default")

    # Settings' menu: the recording first, chosen.
    pg.click(".gear")
    pg.click("dialog.settings [role=tab]:has-text('Listening')") if pg.locator("dialog.settings [role=tab]").count() else None
    sel = "dialog.settings label.set-bvoice[data-k='urantia-ru'] select"
    opts = pg.evaluate("[...document.querySelector(\"%s\").options].filter(o => !o.hidden).map(o => [o.value, o.text])" % sel)
    ok(pg.is_visible(sel) and opts[0] == ["", "Grigory Voyner"] and pg.input_value(sel) == "",
       say + f"Settings offers the recording first, and it is the one chosen ({opts[:3]})")
    en = pg.evaluate("[...document.querySelector(\"dialog.settings label.set-bvoice[data-k=''] select\").options]"
                     ".filter(o => !o.hidden).map(o => o.value)")
    ok(en[0] == "mh" and "voyner" not in en and "" not in en,
       say + f"and the English text's menu has Merritt Horn's first and not his ({en})")
    pg.keyboard.press("Escape")

    # Stop: the mark goes.
    pg.click(".player .close")
    ok(pg.evaluate(NOW) == {"line": None, "of": None, "para": None} and pg.locator(".player").count() == 0,
       say + "stopped, nothing is marked")
    ok(not errors, say + "no script error: " + "; ".join(errors))
    ctx.close()


def fold(b, whole: bool) -> None:
    """The translation in the fold under its paragraph, which is how a phone
    shows it (Tigran, 2026-11-13: "On the phone there is no play triangle at
    all, except against English text"): its ▶ at the start of the line that
    names it.  On a phone's screen, Whole paper off and on (trap 44)."""
    settings = {"translations": "urantia-ru"}
    if whole:
        settings["whole"] = True
    ctx, pg, asked, errors = context(b, settings, phone=True)
    say = "Whole paper on: " if whole else "Whole paper off: "
    print("\nIn the fold under the paragraph, with no room for columns, on a phone, " + say.rstrip(": "))
    pg.goto(BASE + ("/1" if whole else "/1:1"))
    pg.wait_for_selector("[id='1:1.2'] .playp", timeout=15000)
    ok(pg.locator(".rc .playp, .tf .playp").count() == 0, say + "a fold that is shut has no ▶")
    row = ".row:has([id='1:1.2']) "
    pg.click(row + ".trfold")
    play = row + ".tf.open .who[data-play='urantia-ru'] > .playp"
    pg.wait_for_selector(play, timeout=15000)
    box = pg.evaluate("(q => { const r = document.querySelector(q).getBoundingClientRect(); return [r.left >= 0, r.right <= innerWidth, r.width > 0]; })(%s)"
                      % json.dumps(play))
    ok(pg.get_attribute(play, "aria-label") == "Listen to USGNY from 1:1.2" and box == [True, True, True]
       and pg.evaluate("(q => document.querySelector(q).parentNode.firstChild === document.querySelector(q))(%s)" % json.dumps(play)),
       say + f"opened, the fold has the translation's ▶, before its name and on the screen ({box})")
    # With the time the paragraph takes to hear in the recording, beside the
    # triangle, as a column's ▶ has it (Tigran, 2026-11-21).
    t = pg.get_attribute(play, "data-t") or ""
    drawn = pg.evaluate("(q => getComputedStyle(document.querySelector(q), '::after').content)(%s)" % json.dumps(play))
    ok(re.fullmatch(r"\d+:\d\d", t) is not None and drawn == f'"{t}"',
       say + f"its ▶ has the paragraph's time beside it ({t!r}, drawn {drawn})")
    pg.click(play)
    ok(until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.ref === '1:1.2'"),
       say + "its ▶ starts a reading there, the translation's line marked")
    now = pg.evaluate(NOW)
    ok(now["of"] == "urantia-ru" and now["para"] is None and asks(pg, asked, "/audio/voyner/01-01.mp3")
       and not any(a.startswith("/speech/") for a in asked) and pg.evaluate(VOICE) == "USGNY · Grigory Voyner",
       say + f"in the recording, the English paragraph unmarked ({now}, {sorted(set(asked))}, {pg.evaluate(VOICE)!r})")
    pg.click(".player .close")
    del asked[:]
    pg.click("[id='1:1.2'] .playp")
    ok(until(pg, "(document.querySelector('p.t.now') || {}).id === '1:1.2'")
       and asks(pg, asked, "/audio/mh/paper001/P001_01.mp3"), say + "the English ▶ plays the English")
    pg.click(".player .voicebox .voice")
    pg.click(".player .voices [role=menuitemradio]:has-text('Grigory Voyner')")
    ok(until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.ref === '1:1.2'"),
       say + "the recording, picked in the bar, marks the translation's line in the fold")
    now = pg.evaluate(NOW)
    ok(now["of"] == "urantia-ru" and now["para"] is None and asks(pg, asked, "/audio/voyner/01-01.mp3"),
       say + f"and it is the recording that plays ({now}, {sorted(set(asked))})")
    ok(not errors, say + "no script error: " + "; ".join(errors))
    ctx.close()


def tabs(b) -> None:
    """Three translations in the fold: in tabs, the ▶ is the one shown's, at
    the start of the tabs' row, and no tab; with All, each has its own."""
    ctx, pg, asked, errors = context(b, {"translations": "ud urantia-ru uf-ru", "trtab": "urantia-ru"}, phone=True)
    print("\nIn the fold, three translations in tabs")
    pg.goto(BASE + "/1:1")
    row = ".row:has([id='1:1.2']) "
    pg.wait_for_selector(row + ".trfold", timeout=15000)
    pg.click(row + ".trfold")
    pg.wait_for_selector(row + ".tf.open .trtabs > .playp", timeout=15000)
    labels = "[...document.querySelectorAll(%s)].map(e => e.getAttribute('aria-label'))" % json.dumps(row + ".tf.open .playp")
    first = "(q => (document.querySelector(q).firstChild.className))(%s)" % json.dumps(row + ".tf.open .trtabs")
    ok(pg.evaluate(labels) == ["Listen to USGNY from 1:1.2"] and pg.evaluate(first) == "playp",
       f"the tabs' row begins with the ▶ of the translation shown ({pg.evaluate(labels)})")
    # Each ▶'s time, where a recording reads its translation: USGNY's alone.
    times = "[...document.querySelectorAll(%s)].map(e => e.dataset.t || null)" % json.dumps(row + ".tf.open .playp")
    ok(re.fullmatch(r"\d+:\d\d", pg.evaluate(times)[0] or "") is not None, f"with the paragraph's time ({pg.evaluate(times)})")
    pg.click(row + ".tf.open .trtabs > .playp")
    ok(until(pg, "(document.querySelector('p.rt.now') || {dataset: {}}).dataset.k === 'urantia-ru'")
       and asks(pg, asked, "/audio/voyner/01-01.mp3"), f"which plays it ({sorted(set(asked))})")
    stored = json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))
    ok(stored.get("trtab") == "urantia-ru" and pg.locator(row + ".tf.open .trtabs button[aria-pressed='true']").count() == 1,
       f"and is no tab: the tab chosen is as it was ({stored.get('trtab')!r})")
    pg.click(".player .close")
    pg.click(row + ".tf.open .trtabs button[data-tab='uf-ru']")
    ok(until(pg, labels + "[0] === 'Listen to UF-RUS from 1:1.2'") and len(pg.evaluate(labels)) == 1
       and pg.evaluate(times) == [None],
       f"another tab chosen, the ▶ is that translation's, with no time, none reading it but the browser ({pg.evaluate(labels)})")
    pg.click(row + ".tf.open .trtabs button[data-tab='all']")
    ok(until(pg, labels + ".length === 3")
       and pg.evaluate(labels) == [f"Listen to {n} from 1:1.2" for n in ("Aivazian", "USGNY", "UF-RUS")]
       and pg.locator(row + ".tf.open .trtabs > .playp").count() == 0
       and pg.locator(row + ".tf.open .who[data-play] > .playp").count() == 3
       and [x is not None for x in pg.evaluate(times)] == [False, True, False],
       f"with All, each translation has its own before its name, USGNY's with its time, and the tabs' row none ({pg.evaluate(labels)}, {pg.evaluate(times)})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


# A speech engine that says nothing and is done at once: headless Chrome's own
# never ends an utterance, and the way through a section read by the browser's
# voice is by each one's end.  No voices, so that none is set on an utterance.
QUICK_SPEECH = """
(() => {
  const fake = { speaking: false, pending: false, paused: false, onvoiceschanged: null, said: 0,
    getVoices: () => [], pause() {}, resume() {}, addEventListener() {}, removeEventListener() {},
    cancel() { this.now = null; },
    speak(u) {
      this.now = u; this.said++;
      setTimeout(() => { if (this.now !== u) return; u.dispatchEvent(new Event('start'));
        setTimeout(() => { if (this.now !== u) return; this.now = null; u.dispatchEvent(new Event('end')); }, 30); }, 10);
    } };
  Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true });
})();
"""


# A browser that lists voices, which headless Chrome does not: two English and
# two Russian, one of each this device's own, and nothing spoken.
VOICES = """
(() => {
  const V = [{ name: 'Google US English', lang: 'en-US', default: false, localService: false },
             { name: 'English (America)', lang: 'en-US', default: true, localService: true },
             { name: 'Google русский', lang: 'ru-RU', default: false, localService: false },
             { name: 'Russian', lang: 'ru-RU', default: false, localService: true }];
  const fake = { speaking: false, pending: false, paused: false, onvoiceschanged: null,
    getVoices: () => V, pause() {}, resume() {}, addEventListener() {}, removeEventListener() {}, cancel() {}, speak() {} };
  Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true });
})();
"""
# Settings' voices as a reader sees them: [the text's name, the menu's entries, the one chosen].
MENUS = """() => [...document.querySelectorAll('dialog.settings .setvoices label[data-k]')].filter(l => !l.hidden).map(l => {
  const c = l.cloneNode(true); c.querySelectorAll('x-ru, select').forEach(x => x.remove());
  const s = l.querySelector('select');
  return [c.textContent.trim(), [...s.options].filter(o => !o.hidden).map(o => o.text), s.options[s.selectedIndex].text]; })"""


def menus(b) -> None:
    """Settings' Listening tab (Tigran, 2026-11-13): a menu of voices against
    each text, the English first, then the translations in the reader's
    order; a text's recording first in its menu, then the browser's voices in
    its language by name, each once, with no "Automatic" and no "Your
    browser's voice" among them; and a pick kept as what it is."""
    ctx, pg, _asked, errors = context(b, {"translations": "urantia-ru ud"})
    ctx.add_init_script(VOICES)
    print("\nSettings' voices, in a browser that lists some")
    pg.goto(BASE + "/1:1")
    pg.click(".gear")
    pg.click("dialog.settings [role=tab]:has-text('Listening')")
    got = pg.evaluate(MENUS)
    # The translations by language and short name, whatever their order
    # shown (Tigran, 2026-11-20): Aivazian before USGNY, ticked after it.
    ok(got == [["English text", ["Merritt Horn", "Google US English", "English (America)"], "Merritt Horn"],
               ["Aivazian", ["Google русский", "Russian"], "Google русский"],
               ["USGNY", ["Grigory Voyner", "Google русский", "Russian"], "Grigory Voyner"]],
       f"a menu against each text, the English first, its recording first, each voice once ({got})")
    heads = pg.evaluate("[...document.querySelectorAll('dialog.settings .panel.on .sub')].map(e => (" + EN + ")(e))")
    ok(heads == ["Voices"], f"under one heading ({heads})")

    def stored() -> dict:
        return json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))

    def sel(k: str) -> str:
        return f"dialog.settings .setvoices label[data-k='{k}'] select"

    pg.select_option(sel(""), "English (America)")
    ok((stored().get("voice"), stored().get("bvoice")) == ("browser", "English (America)"),
       f"a browser's voice picked for the English is kept by its name ({stored()})")
    pg.select_option(sel(""), "mh")
    ok("voice" not in stored(), f"Merritt Horn picked again is the default, and nothing is kept for it ({stored()})")
    pg.select_option(sel("urantia-ru"), "Russian")
    ok(json.loads(stored()["trvoices"]) == {"urantia-ru": "Russian"}, "a browser's voice picked for USGNY is kept by its name")
    pg.select_option(sel("urantia-ru"), "")
    ok("trvoices" not in stored(), "and its recording picked again is the default")
    pg.select_option(sel("ud"), "Russian")
    pg.keyboard.press("Escape")
    pg.click(".gear")
    got = pg.evaluate(MENUS)
    ok([g[2] for g in got] == ["Merritt Horn", "Russian", "Grigory Voyner"], f"opened again, each menu shows what reads its text ({[g[2] for g in got]})")
    # What was kept before this day: the browser's own choice for a
    # translation with a recording, "browser", is its best voice by name.
    pg.evaluate("window.ubSettings.setTrVoice('urantia-ru', 'browser')")
    pg.keyboard.press("Escape")
    pg.click(".gear")
    ok(pg.evaluate(MENUS)[2][2] == "Google русский", "a choice of the browser's voice kept before is shown as its best, by name")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()

    ctx, pg, _asked, errors = context(b, {"translations": "urantia-ru ud"})
    print("\nSettings' voices, in a browser that has listed none")
    pg.goto(BASE + "/1:1")
    pg.click(".gear")
    pg.click("dialog.settings [role=tab]:has-text('Listening')")
    got = pg.evaluate(MENUS)
    ok(got == [["English text", ["Merritt Horn", "Your browser’s voice"], "Merritt Horn"],
               ["Aivazian", ["Your browser’s voice"], "Your browser’s voice"],
               ["USGNY", ["Grigory Voyner", "Your browser’s voice"], "Grigory Voyner"]],
       f"one entry stands for the browser's voices until it lists them ({got})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def bar(b) -> None:
    """The bar's list of voices (Tigran, 2026-11-13: "it separates Merritt
    Horn from the browser's voices"): under each text its recording and then
    the browser's voices by name, as Settings' menus have them; with no
    translation, the English text's alone, under no heading."""
    ctx, pg, _asked, errors = context(b, {"translations": "urantia-ru ud"})
    ctx.add_init_script(VOICES)
    # Chrome's own utterance takes none but a voice of its own making.
    ctx.add_init_script("window.SpeechSynthesisUtterance = class extends EventTarget { constructor(t) { super(); this.text = t; } };")
    print("\nThe bar's voices, in a browser that lists some")
    pg.goto(BASE + "/1:1")
    pg.wait_for_selector("[id='1:1.2'] .playp", timeout=15000)
    pg.click("[id='1:1.2'] .playp")
    pg.click(".player .voicebox .voice")
    menu = pg.evaluate(BAR)
    ok(menu == ["# English text", "Merritt Horn", "Google US English", "English (America)",
                "# Aivazian · Russian", "Google русский", "Russian",
                "# USGNY · Russian", "Grigory Voyner", "Google русский", "Russian"],
       f"each text's recording and the browser's voices are one list under it, the English first ({menu})")
    checked = "[...document.querySelectorAll('.player .voices [aria-checked=true]')].map(%s)" % EN
    ok(pg.evaluate(checked) == ["Merritt Horn"], f"the voice heard is the one checked ({pg.evaluate(checked)})")

    def stored() -> dict:
        return json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))

    pg.click(".player .voices [role=group]:first-child [role=menuitemradio]:has-text('English (America)')")
    ok((stored().get("voice"), stored().get("bvoice")) == ("browser", "English (America)")
       and until(pg, "(%s)() === 'English (America)'" % VOICE),
       f"a browser's voice picked for the English is kept by its name, and the bar names it ({stored()}, {pg.evaluate(VOICE)!r})")
    pg.click(".player .voicebox .voice")
    ok(pg.evaluate(checked) == ["English (America)"], f"and is the one checked ({pg.evaluate(checked)})")
    pg.click(".player .voices [role=menuitemradio]:has-text('Merritt Horn')")
    ok(until(pg, "(%s)() === 'Merritt Horn'" % VOICE) and stored().get("voice") in (None, "mh"),
       f"Merritt Horn picked again is heard again ({stored()})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()

    ctx, pg, _asked, errors = context(b, {})
    ctx.add_init_script(VOICES)
    print("\nThe bar's voices, with no translation shown")
    pg.goto(BASE + "/1:1")
    pg.wait_for_selector("[id='1:1.2'] .playp", timeout=15000)
    pg.click("[id='1:1.2'] .playp")
    pg.click(".player .voicebox .voice")
    menu = pg.evaluate(BAR)
    ok(menu == ["Merritt Horn", "Google US English", "English (America)"],
       f"the English text's voices are the list, under no heading ({menu})")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


def lacking(b) -> None:
    """A section the recording lacks: no file reads 19:0 (voyner-unread.tsv).
    Its ▶ there is the browser's voice; and with Carry on into the next
    section on, a reading that comes to it from 18:7 goes on in the browser's
    voice, and is the recording's again at 19:1."""
    ctx, pg, asked, errors = context(b, {"translations": "urantia-ru", "onward": True}, wide=True)
    ctx.add_init_script(QUICK_SPEECH)
    print("\nA section the recording lacks, 19:0, read a section at a time")
    pg.goto(BASE + "/19:0")
    cell = ".rc[data-k='urantia-ru']:has(p.rt[data-ref='19:0.9']) .stk > .playp"
    pg.wait_for_selector(cell, timeout=15000)
    pg.click(cell)
    ok(asks(pg, asked, "/speech/urantia-ru/19:0"), f"its own ▶ there is the browser's voice ({sorted(set(asked))})")
    # From its last paragraph the browser's voice is soon done, and carries on.
    ok(until(pg, "location.pathname === '/19:1'", 20), "which, done with 19:0, carries on into 19:1")
    ok(asks(pg, asked, "/audio/voyner/19-01.mp3") and until(pg, "/Voyner/.test((%s)())" % VOICE),
       f"in the recording, which 19:1 has ({sorted(set(asked))}, {pg.evaluate(VOICE)!r})")
    ok(until(pg, "document.querySelector('p.rt.now') !== null")
       and pg.evaluate(NOW)["of"] == "urantia-ru", f"marking the translation's line there ({pg.evaluate(NOW)})")
    pg.click(".player .close")

    # And from the section before: 18:7's last paragraph, five seconds of the
    # recording, played out.
    del asked[:]
    pg.goto(BASE + "/18:7")
    sel = ".rc[data-k='urantia-ru'] p.rt[data-ref]"
    pg.wait_for_selector(sel, timeout=15000)
    last = pg.evaluate("[...document.querySelectorAll(\"%s\")].pop().dataset.ref" % sel)
    pg.click(f".rc[data-k='urantia-ru']:has(p.rt[data-ref='{last}']) .stk > .playp")
    ok(asks(pg, asked, "/audio/voyner/18-07.mp3") and until(pg, "/Voyner/.test((%s)())" % VOICE),
       f"18:7's last paragraph, {last}, plays in the recording")
    ok(until(pg, "location.pathname !== '/18:7'", 25), "at its end the reading carries on")
    ok(asks(pg, asked, "/speech/urantia-ru/19:0"),
       f"through 19:0 in the browser's voice, the recording having none of it ({sorted(set(asked))})")
    ok("/audio/voyner/19-00.mp3" not in asked, "the file so named, which is 192:0 again, is never asked for")
    ok(until(pg, "location.pathname === '/19:1'", 25) and asks(pg, asked, "/audio/voyner/19-01.mp3")
       and until(pg, "/Voyner/.test((%s)())" % VOICE),
       f"and at 19:1 the recording is back ({pg.evaluate('location.pathname')}, {pg.evaluate(VOICE)!r})")
    stored = json.loads(pg.evaluate("localStorage.getItem('ub_settings')"))
    ok("trvoices" not in stored, "with no voice stored: the reader chose none, the recording lacked a section")
    ok(not errors, "no script error: " + "; ".join(errors))
    ctx.close()


# The bar on a phone's screen, each box [left, top, right, bottom], and the
# voice's name as shown and as wide as it needs.
GEO = """() => { const b = document.querySelector('.player'), q = s => { const e = s ? b.querySelector(s) : b;
      if (!e || !e.getClientRects().length) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; },
    n = b.querySelector('.voice span');
  return { bar: q(''), mid: q('.mid'), prev: q('.prev'), toggle: q('.toggle'), close: q('.close'), onward: q('.onward'),
           left: q('.tleft'), rate: q('.rate'), t: b.querySelector('.tleft').textContent, title: b.querySelector('.tleft').title,
           shown: n.clientWidth, need: n.scrollWidth, on: b.querySelector('.onward').scrollWidth > b.querySelector('.onward').clientWidth + 1,
           vw: innerWidth, vh: innerHeight, inner: (() => { const r = b.getBoundingClientRect(), cs = getComputedStyle(b);
             return [r.left + parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft),
                     r.right - parseFloat(cs.borderRightWidth) - parseFloat(cs.paddingRight)]; })() }; }"""


# What the bar's screen shows, read from its drawing: each digit by the
# segments lit, a digit all unlit a space, the colons by their upper dot.
DRAWN = """() => { const LIT = {abcdef: '0', bc: '1', abdeg: '2', abcdg: '3', bcfg: '4', acdfg: '5', acdefg: '6',
      abc: '7', abcdefg: '8', abcdfg: '9'}, g = document.querySelector('.player .tleft svg > g');
  if (!g) return null;
  let s = '';
  for (const c of g.children) {
    if (c.tagName === 'g') { const on = [...c.children].filter(p => p.classList.contains('on') && p.getBBox().height
        && getComputedStyle(p).display !== 'none' && getComputedStyle(p).visibility !== 'hidden').map(p => p.dataset.s).join('');
      s += on ? (LIT[on] || '?') : ' '; }
    else if (c.getAttribute('y') === '4.7') s += ':';
  }
  return s.trim(); }"""
FIT = "() => document.querySelector('.player .tleft').dataset.fit"


def one_line(g: dict) -> bool:
    """⏮, ⏵ and × centred on one line: under a short name the buttons once
    wrapped into a third row."""
    mid = lambda r: (r[1] + r[3]) / 2
    if g["prev"][0] < g["inner"][0] - 1 or g["close"][2] > g["inner"][1] + 1:
        return False                           # and inside the bar's padding
    return all(abs(mid(g[x]) - mid(g["toggle"])) <= 2 for x in ("prev", "close", "rate") + (("left",) if g["left"] else ()))


def secs(t: str) -> int:
    n = 0
    for x in t.split(":"):
        n = n * 60 + int(x)
    return n


def phone_bar(b) -> None:
    """On a phone the bar is two rows (Tigran, 2026-11-21): the reference and
    the voice on a line over the buttons, the voice's name whole, where at
    360 px "USGNY · Григорий Войнер" was "USG…"; at the end of a section
    "Next" and the next one's name on that line, where beside the buttons it
    ran past the bar and took the × with it; and Follow along keeps the line
    being read clear of the bar by its height, 100 px from the foot at 125%,
    where it kept 80 px whatever the bar."""
    print("\nThe bar on a phone")
    for lang in ("en", "ru"):
        for ui in ("100", "112.5", "125"):
            for w in (360, 412):
                say = f"{lang} {ui}% {w} px: "
                # In Russian with the index folded, as Tigran reads on his
                # phone: the screen's top segments, classes once, were hidden
                # with the index's entries (`.a`; trap 58).
                st = {"translations": "urantia-ru", "lang": lang, "uisize": ui}
                if lang == "ru":
                    st["margin"] = "off"
                ctx, pg, asked, errors = context(b, st, phone=True)
                pg.set_viewport_size({"width": w, "height": 800})
                pg.goto(BASE + "/1:1")
                pg.wait_for_selector("[id='1:1.2'] .playp", timeout=15000)
                row = ".row:has([id='1:1.2']) "
                pg.click(row + ".trfold")
                play = row + ".tf.open .who[data-play='urantia-ru'] > .playp"
                pg.wait_for_selector(play, timeout=15000)
                pg.click(play)
                pg.wait_for_selector(".player .voice span", timeout=15000)
                for voice in ("USGNY", "Merritt Horn"):
                    if voice == "Merritt Horn":
                        pg.click("[id='1:1.2'] .stk > .playp")
                        until(pg, "(document.querySelector('p.t.now') || {}).id === '1:1.2'")
                    pg.wait_for_timeout(150)
                    g = pg.evaluate(GEO)
                    name = pg.evaluate(VOICE)
                    ok(g["need"] <= g["shown"] + 1 and name.startswith(voice),
                       say + f"{name!r}, whole ({g['shown']} of {g['need']} px)")
                    ok(g["mid"][3] <= g["toggle"][1] + 1 and g["bar"][0] >= 0 and g["bar"][2] <= g["vw"]
                       and g["close"][2] <= g["bar"][2] and one_line(g),
                       say + f"on a line over the buttons, which are one line, the bar in the window ({g['bar']}, {g['mid']}, {g['toggle']})")
                    # The time left in the section, before the speed (Tigran,
                    # 2026-11-21), counting down as the reading goes on.
                    # As a watch's screen shows it, where the row has room,
                    # its digits reading as the time; at 125% on 360 px
                    # in plain figures (listen.js leftFit).
                    fit, drawn = pg.evaluate(FIT), pg.evaluate(DRAWN)
                    ok(g["left"] is not None and re.fullmatch(r"\d+:\d\d", g["t"] or "") is not None
                       and g["left"][2] <= g["rate"][0] + 1
                       and g["title"] == {"en": "Time left in this section", "ru": "Осталось до конца раздела"}[lang],
                       say + f"the time left in the section, {g['t']!r}, before the speed")
                    want = "plain" if (ui, w) == ("125", 360) else "lcd"
                    ok(fit == want and (fit != "lcd" or drawn == g["t"]),
                       say + f"on a screen of seven-segment digits where there is room, else plain ({fit}, drawn {drawn!r})")
                    if lang == "en" and ui == "100" and w == 360:
                        a = secs(pg.evaluate(GEO)["t"])
                        pg.wait_for_timeout(2500)
                        z = secs(pg.evaluate(GEO)["t"])
                        ok(a - 4 <= z <= a - 1, say + f"and it counts down as the reading goes on ({a} s, then {z} s)")
                if lang == "ru" and ui == "125" and w == 360:
                    # The voices' list opens above the whole bar, in the window.
                    pg.click(".player .voicebox .voice")
                    v = pg.evaluate("""() => { const r = document.querySelector('.player .voices').getBoundingClientRect(),
                        t = document.querySelector('.player').getBoundingClientRect(); return [r.left, r.right, r.bottom, t.top, innerWidth]; }""")
                    ok(v[0] >= 0 and v[1] <= v[4] and v[2] <= v[3], say + f"the voices' list above the bar, in the window ({v})")
                    pg.keyboard.press("Escape")
                ok(not errors, say + "no script error: " + "; ".join(errors))
                ctx.close()

    # The end of a section: 108:6.9 takes Merritt Horn 2.7 s, and Carry on
    # into the next section off, the bar says where to go on.
    for lang in ("en", "ru"):
        say = f"{lang} 125% 360 px: "
        ctx, pg, asked, errors = context(b, {"lang": lang, "uisize": "125", "onward": False}, phone=True)
        pg.set_viewport_size({"width": 360, "height": 800})
        pg.goto(BASE + "/108:6")
        pg.wait_for_selector("[id='108:6.9'] .stk > .playp", timeout=15000)
        pg.click("[id='108:6.9'] .stk > .playp")
        ok(until(pg, "!document.querySelector('.player .onward').hidden", 30), say + "the end of the section offers the next")
        g = pg.evaluate(GEO)
        ok(g["mid"] is None and g["onward"] and g["onward"][3] <= g["toggle"][1] + 1 and one_line(g) and g["left"] is None
           and g["bar"][0] >= 0 and g["bar"][2] <= g["vw"] and g["close"][2] <= g["bar"][2],
           say + f"\"Next\" on the line over the buttons, the × in the bar, no time left ({g['onward']}, {g['close']}, {g['bar']})")
        ok(not errors, say + "no script error: " + "; ".join(errors))
        ctx.close()

    # A phone of 320 px: the row in the bar at every size, the time on its
    # screen, or plain, or left out, as there is room.
    for ui in ("100", "112.5", "125"):
        ctx, pg, asked, errors = context(b, {"uisize": ui}, phone=True)
        pg.set_viewport_size({"width": 320, "height": 700})
        pg.goto(BASE + "/1:1")
        pg.wait_for_selector("[id='1:1.2'] .stk > .playp", timeout=15000)
        pg.click("[id='1:1.2'] .stk > .playp")
        pg.wait_for_selector(".player .voice span", timeout=15000)
        pg.wait_for_timeout(400)
        g = pg.evaluate(GEO)
        ok(g["bar"][0] >= 0 and g["bar"][2] <= g["vw"] and g["prev"][0] >= g["bar"][0] and g["close"][2] <= g["bar"][2]
           and one_line(g) and pg.evaluate("document.querySelector('.player').scrollWidth <= document.querySelector('.player').clientWidth + 1"),
           f"320 px at {ui}%: the buttons in the bar, the time {pg.evaluate(FIT)}")
        ok(not errors, f"320 px at {ui}%: no script error: " + "; ".join(errors))
        ctx.close()

    # The whole paper's page: the time left in the paper, an hour and more
    # of Paper 15 in h:mm:ss; and a desk's bar of one row has no time.
    ctx, pg, asked, errors = context(b, {"whole": True}, phone=True)
    pg.set_viewport_size({"width": 360, "height": 800})
    pg.goto(BASE + "/15")
    pg.wait_for_selector("[id='15:0.1'] .stk > .playp", timeout=15000)
    pg.click("[id='15:0.1'] .stk > .playp")
    ok(until(pg, "!document.querySelector('.player .tleft').hidden"), "whole paper: the time left shows")
    g = pg.evaluate(GEO)
    ok(re.fullmatch(r"1:0\d:\d\d", g["t"] or "") is not None and g["title"] == "Time left in this paper" and one_line(g)
       and pg.evaluate(FIT) == "lcd" and pg.evaluate(DRAWN) == g["t"],
       f"whole paper: the time left in the paper, over an hour as h:mm:ss, on the screen ({g['t']!r}, {g['title']!r}, drawn {pg.evaluate(DRAWN)!r})")
    ok(not errors, "whole paper: no script error: " + "; ".join(errors))
    ctx.close()
    # A desk's and a tablet's bar, one row: the screen too, since the same
    # day (Tigran: "I want it on all platforms: tablet, computer, etc."),
    # before the speed, and never at the cost of the voice's name or the
    # reference, which stand beside it there (listen.js leftFit).
    for lang in ("en", "ru"):
        for ui in ("100", "125"):
            for w in (1400, 768, 600):
                say = f"desk {lang} {ui}% {w} px: "
                ctx, pg, asked, errors = context(b, {"translations": "urantia-ru", "lang": lang, "uisize": ui})
                pg.set_viewport_size({"width": w, "height": 900})
                pg.goto(BASE + "/1:1")
                pg.wait_for_selector("[id='1:1.2'] .playp", timeout=15000)
                pg.wait_for_timeout(500)                   # the columns, where there is room
                cell = ".rc[data-k='urantia-ru']:has(p.rt[data-ref='1:1.2']) .stk > .playp"
                if pg.locator("article.cmp").count():
                    pg.wait_for_selector(cell, timeout=15000)
                    pg.click(cell)
                else:
                    row = ".row:has([id='1:1.2']) "
                    pg.click(row + ".trfold")
                    play = row + ".tf.open .who[data-play='urantia-ru'] > .playp"
                    pg.wait_for_selector(play, timeout=15000)
                    pg.click(play)
                pg.wait_for_selector(".player .voice span", timeout=15000)
                until(pg, "!document.querySelector('.player .tleft').hidden")
                pg.wait_for_timeout(300)
                g, fit, drawn = pg.evaluate(GEO), pg.evaluate(FIT), pg.evaluate(DRAWN)
                mid = lambda r: (r[1] + r[3]) / 2
                # What the name and the reference have, with the time as it is and with none.
                cost = pg.evaluate("""() => { const t = document.querySelector('.player .tleft'), f = t.dataset.fit,
                    n = document.querySelector('.player .voice span'), w = document.querySelector('.player .where'),
                    a = [n.clientWidth, w.clientWidth]; t.dataset.fit = 'none'; const z = [n.clientWidth, w.clientWidth];
                    t.dataset.fit = f; return [z[0] - a[0], z[1] - a[1]]; }""")
                ok(abs(mid(g["mid"]) - mid(g["toggle"])) <= 3 and g["bar"][0] >= 0 and g["bar"][2] <= g["vw"]
                   and g["close"][2] <= g["inner"][1] + 1 and g["prev"][0] >= g["inner"][0] - 1,
                   say + f"one row, in the window ({g['bar']})")
                ok(cost[0] <= 1 and cost[1] <= 1 and fit in ("lcd", "plain", "none")
                   and (fit != "lcd" or (drawn == g["t"] and g["left"][2] <= g["rate"][0] + 1)),
                   say + f"the time {fit}, before the speed, costing the name and the reference nothing ({cost}, drawn {drawn!r})")
                if w == 1400:
                    ok(fit == "lcd" and g["need"] <= g["shown"] + 1, say + f"a desk has the screen, and the name whole ({g['shown']} of {g['need']} px)")
                ok(not errors, say + "no script error: " + "; ".join(errors))
                ctx.close()

    # Follow along: at 125% the bar's top stands 100 px above the window's
    # foot.  A paragraph whose end is 90 px above it, started, is brought
    # clear of the bar; with the margin of 80 px it was left under it.
    for ui in ("100", "125"):
        say = f"{ui}%: "
        ctx, pg, asked, errors = context(b, {"uisize": ui, "follow": True}, phone=True)
        pg.set_viewport_size({"width": 390, "height": 800})
        pg.goto(BASE + "/1:1")
        pg.wait_for_selector("[id='1:1.1'] .stk > .playp", timeout=15000)
        pg.click("[id='1:1.1'] .stk > .playp")
        pg.wait_for_selector(".player .voice span", timeout=15000)
        target = "1:1.3"
        pg.evaluate("""id => { const p = document.getElementById(id), r = p.getBoundingClientRect();
            scrollTo(0, scrollY + r.bottom - (innerHeight - 90)); }""", target)
        pg.wait_for_timeout(300)
        before = pg.evaluate("id => innerHeight - document.getElementById(id).getBoundingClientRect().bottom", target)
        pg.click(f"[id='{target}'] .stk > .playp")
        until(pg, f"(document.querySelector('p.t.now') || {{}}).id === '{target}'")
        pg.wait_for_timeout(1200)                     # the smooth scroll
        g = pg.evaluate("""id => [document.getElementById(id).getBoundingClientRect().bottom,
            document.querySelector('.player').getBoundingClientRect().top, innerHeight]""", target)
        ok(abs(before - 90) <= 2 and g[0] <= g[1],
           say + f"a paragraph ending {before:.0f} px above the foot, started, ends above the bar ({g[0]:.0f} <= {g[1]:.0f})")
        ok(not errors, say + "no script error: " + "; ".join(errors))
        ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        columns(b, False)
        columns(b, True)
        fold(b, False)
        fold(b, True)
        tabs(b)
        menus(b)
        bar(b)
        lacking(b)
        phone_bar(b)
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
