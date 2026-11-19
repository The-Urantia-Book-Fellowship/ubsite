"""What follows a reader's account, end to end, in Chrome, two browsers side by
side as two devices (ubsite/account.py sync(), static/account.js; Tigran,
2026-11-18, built 2026-11-19): a reader who is not signed in runs none of it;
the first device to sign in gives the account what it has, its settings but
for the device's own, its bookmarks and its place; a second device takes the
account's settings in place of its own, keeps both devices' bookmarks and the
newer place, and shows them without a reload; a setting, a bookmark set and a
bookmark removed, each made on one device and seen on the other; the place,
which leaves a device as its page is left; the account's menu opened, which
asks at once; Whole paper, which moves the other
device's page; Restore the defaults, whose question says every device; a
change made with no network, sent when it returns; everything a script keeps
cleared, as Safari clears it, and all of it back; signing out of a computer
that is not one's own, with the box ticked; signing out and in again as the
same reader; and another reader on the same browser, asked first, declined
and then accepted.

    .venv/bin/python tools/follow_e2e.py        (after make data)

The site and the stand-in for Google are tools/account_e2e.py's, which starts
them: the app on localhost:8144 with a database of its own in a temporary
directory, and leaves the dev server alone.  Five minutes are not waited for:
a page is told that its last exchange was long ago and that it has come back
into view.  Not a gate: tests/test_account.py holds the exchange itself.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

from playwright.sync_api import Error as PlaywrightError, sync_playwright

import account_e2e as E

SITE, ok, until = E.SITE, E.ok, E.until
BOB = {"sub": "220169484474386276335", "email": "bob.reader@example.org", "name": "Bob Reader",
       "picture": E.GOOGLE + "/photo/bob"}
NOW = int(time.time() * 1000)
# What the browser keeps, as the page reads it.
KEPT = """() => { const j = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || 'null') || d; } catch (e) { return d; } };
  return {set: j('ub_settings', {}), marks: j('ub_marks', []).map(m => m.ref), place: j('ub_place', {}).ref || null,
          sync: j('ub_sync', null), who: j('ub_who', null)}; }"""
ROOT_DATA = "() => Object.assign({}, document.documentElement.dataset)"
# Five minutes on, and the page back in view: the occasion for asking what the other devices changed.
LATER = """() => { const s = JSON.parse(localStorage.getItem('ub_sync')); s.t = 0;
  localStorage.setItem('ub_sync', JSON.stringify(s)); document.dispatchEvent(new Event('visibilitychange')); }"""
BAR = """() => { const b = document.querySelector('.fbar'); return {ref: b.querySelector('.fref').textContent,
  count: b.querySelector('.fcount').textContent, has: b.classList.contains('fhas')}; }"""


class Device:
    """A browser of its own: what it keeps to begin with, what it asked of the
    site, and the questions it was put, each answered as `yes` then stands."""

    def __init__(self, b, store: dict, width: int = 1100, height: int = 900):
        self.ctx = b.new_context(viewport={"width": width, "height": height}, service_workers="block")
        seed = "".join("localStorage.setItem(%s, %s);" % (json.dumps(k), json.dumps(json.dumps(v))) for k, v in store.items())
        self.ctx.add_init_script("try { if (!sessionStorage.getItem('e2e')) { sessionStorage.setItem('e2e', '1');"
                                 " if (!localStorage.getItem('ub_tour')) { localStorage.setItem('ub_tour', 'seen');"
                                 " localStorage.setItem('ub_install', 'no'); %s } } } catch (e) {}" % seed)
        self.asked: list[str] = []
        self.heard: list[str] = []
        self.yes = True
        self.ctx.on("request", lambda r: self.asked.append(r.method + " " + r.url))
        self.said: list[str] = []                # what each exchange said
        self.ctx.on("request", lambda r: self.said.append(r.post_data or "") if r.url.endswith("/account/sync") else None)
        self.pg = self.ctx.new_page()
        self.pg.on("pageerror", lambda e: E.errors.append(str(e)))
        self.pg.on("dialog", self._dialog)

    def _dialog(self, d):
        self.heard.append(d.message)
        if self.yes:
            d.accept()
        else:
            d.dismiss()

    def kept(self) -> dict:
        return self.pg.evaluate(KEPT)

    def sign_in(self, new: bool = False):
        pg, here = self.pg, self.pg.url
        if not pg.evaluate("() => document.querySelector('.top .acctmenu').open"):
            pg.click(".top .acctmenu > summary")
        pg.click(".top .acctmenu .acct-go")
        if new:
            pg.wait_for_url(lambda u: "/account/welcome" in u)
            pg.check(".acct-agree")
            pg.click(".acct-make")
        pg.wait_for_url(here)

    def sign_out(self, clear: bool = False):
        pg = self.pg
        if not pg.evaluate("() => document.querySelector('.top .acctmenu').open"):
            pg.click(".top .acctmenu > summary")
        until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'in'")
        if clear:
            pg.check(".top .acctmenu .acct-clear")
        pg.click(".top .acctmenu .acct-bye")
        until(pg, "!localStorage.getItem('ub_who')")

    def later(self):
        self.pg.evaluate(LATER)

    def bookmark(self, ref: str):
        """The paragraph tapped, and the bar's button: set, or taken off."""
        pg = self.pg
        pg.click(f'main p.t[id="{ref}"]', position={"x": 60, "y": 8})
        pg.wait_for_selector(".fbar.fup .fmark:visible")
        pg.wait_for_timeout(500)                 # the bar's buttons take no tap in the moment it rises
        pg.click(".fbar .fmark")
        pg.keyboard.press("Escape")

    def sent(self, since: int = 0) -> list[str]:
        return [a for a in self.asked[since:] if a.endswith("/account/sync")]


def settings(pg, tab: str = "reading"):
    """Settings, at a tab: it opens again where it was last shut."""
    E.settings(pg)
    pg.click("#set-t-" + tab)


def items(db: pathlib.Path, user: int = 1) -> dict:
    if not db.exists():
        return {}
    con = sqlite3.connect(db)
    try:
        return {(k, key): (None if v is None else json.loads(v))
                for k, key, v in con.execute("SELECT kind, key, value FROM item WHERE user_id = ?", (user,))}
    finally:
        con.close()


def wait(f, ms: int = 9000) -> bool:
    end = time.time() + ms / 1000
    while time.time() < end:
        if f():
            return True
        time.sleep(0.15)
    return bool(f())


def run(tmp: pathlib.Path) -> int:
    db = tmp / "user.db"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

        print("A reader who is not signed in")
        a = Device(b, {
            "ub_settings": {"theme": "dark", "size": "125", "redletter": False},
            "ub_marks": [{"ref": "101:4.2", "title": "The Real Nature of Religion", "q": "Revelation is a technique", "at": NOW - 5000, "v": "8"}],
            "ub_place": {"ref": "101:4.3", "title": "The Real Nature of Religion", "at": NOW - 1000, "v": "8"}})
        a.pg.goto(SITE + "/101:4")
        a.pg.wait_for_load_state("networkidle")
        ok(not [x for x in a.asked if "account" in x], "asks the server nothing of an account, nor for its script")
        ok(a.pg.evaluate("() => typeof window.ubFollow") == "undefined" and a.kept()["sync"] is None, "and runs none of it")

        print("The first device signs in: the account takes what it has")
        a.sign_in(new=True)
        ok(wait(lambda: ("set", "theme") in items(db)), "an exchange, by itself, as the page it came back to loads")
        got = items(db)
        ok(got.get(("set", "theme")) == "dark" and got.get(("set", "redletter")) is False, "its settings are the account's")
        ok(("set", "size") not in got, "but for the device's own: the text's size stays the device's")
        ok(got.get(("mark", "101:4.2"), {}).get("q") == "Revelation is a technique", "its bookmark")
        ok(("place", "") in got, "and its place: " + repr(got.get(("place", ""), {}).get("ref")))
        ok(until(a.pg, "!!localStorage.getItem('ub_sync')"), "the browser notes the exchange")
        sy = a.kept()["sync"]
        ok(sy["id"] == 1 and sy["n"] == 1 and sy["base"]["set"] == {"theme": "dark", "redletter": False}
           and list(sy["base"]["marks"]) == ["101:4.2"], "whose account, the server's number, and the things as they stood")
        ok(a.kept()["set"] == {"theme": "dark", "size": "125", "redletter": False}, "and keeps what it kept")
        ok([x for x in a.asked if "/static/account.js" in x] != [], "the script of it was fetched, now that someone is signed in")

        print("A second device signs in: the account's settings, both devices' bookmarks, the newer place")
        d = Device(b, {
            "ub_settings": {"align": "ragged", "size": "90", "pages": True},
            "ub_marks": [{"ref": "2:0.1", "title": "The Nature of God", "q": "Inasmuch as man", "at": NOW - 9000, "v": "8"}],
            "ub_place": {"ref": "2:0.1", "title": "The Nature of God", "at": NOW - 60000, "v": "8"}})
        d.pg.goto(SITE + "/")
        d.pg.wait_for_load_state("networkidle")
        was = d.pg.evaluate(ROOT_DATA)
        ok(was.get("align") == "ragged" and was.get("pages") == "true" and "theme" not in was, "before: its own settings")
        ok(d.pg.evaluate(BAR) == {"ref": "2:0.1", "count": "1", "has": True}, "its own place and one bookmark in the bar")
        d.sign_in()
        ok(until(d.pg, "document.documentElement.dataset.theme === 'dark'"), "signed in, the page turns dark without a reload")
        now = d.pg.evaluate(ROOT_DATA)
        ok(now.get("redletter") == "off" and "align" not in now and "pages" not in now,
           "the account's settings in place of the device's, one it had chosen and the account had not being its default again")
        ok(now.get("size") == "90" and d.kept()["set"] == {"theme": "dark", "redletter": False, "size": "90"},
           "the text's size its own still: " + repr(d.kept()["set"]))
        ok(d.kept()["marks"] == ["2:0.1", "101:4.2"], "both devices' bookmarks, in the book's order: " + repr(d.kept()["marks"]))
        ok(until(d.pg, "document.querySelector('.fbar .fcount').textContent === '2'"), "two in the bar")
        ok(d.pg.evaluate(BAR)["ref"] == "101:4.3", "and Continue reading at the other device's place, the newer: "
           + repr(d.pg.evaluate(BAR)["ref"]))
        got = items(db)
        ok(("mark", "2:0.1") in got and ("set", "align") not in got and ("set", "pages") not in got and got[("set", "theme")] == "dark",
           "the account has the second device's bookmark, and none of its settings")
        ok(d.heard == [], "nothing was asked of the reader")

        print("The first device learns of it")
        a.later()
        ok(until(a.pg, "JSON.parse(localStorage.getItem('ub_marks')).length === 2"), "the second device's bookmark is on the first")
        ok(a.kept()["set"] == {"theme": "dark", "size": "125", "redletter": False}, "its settings as they were")

        print("The place leaves a device as its page is left")
        ok(until(a.pg, "(JSON.parse(localStorage.getItem('ub_place')) || {}).at > %d" % NOW, 9000),
           "the first device has been reading: " + repr(a.kept()["place"]))
        place = a.kept()["place"]
        before = len(a.asked)
        a.pg.goto(SITE + "/101:5")
        ok(wait(lambda: items(db).get(("place", ""), {}).get("ref") == place), "left, its page sends the place: " + repr(place))
        a.pg.wait_for_load_state("networkidle")
        # The request that outlives its page is not always reported here; the page come to makes none.
        ok(len(a.sent(before)) <= 1, "in one exchange, and the page come to asks nothing: " + repr(a.sent(before)))
        d.later()
        ok(until(d.pg, "document.querySelector('.fbar .fref').textContent === %s" % json.dumps(place)),
           "and Continue reading on the second device goes there")

        print("A setting changed on one device")
        settings(a.pg)
        a.pg.check('dialog.settings input[name="theme"][value="light"]', force=True)
        a.pg.keyboard.press("Escape")
        ok(wait(lambda: items(db).get(("set", "theme")) == "light"), "reaches the account three seconds after")
        d.later()
        ok(until(d.pg, "document.documentElement.dataset.theme === 'light'"), "and the other device, whose page turns light")
        ok(d.kept()["set"].get("theme") == "light", "which keeps it")

        print("Opening the account's menu brings it at once")
        settings(a.pg)
        a.pg.check('dialog.settings input[name="align"][value="ragged"]', force=True)
        a.pg.keyboard.press("Escape")
        ok(wait(lambda: items(db).get(("set", "align")) == "ragged"), "another setting changed on the first device")
        ok("align" not in d.pg.evaluate(ROOT_DATA), "is not on the second, which asked less than five minutes ago")
        d.pg.click(".top .acctmenu > summary")
        ok(until(d.pg, "document.documentElement.dataset.align === 'ragged'"), "until its reader opens the menu at the corner")
        d.pg.keyboard.press("Escape")

        print("A bookmark set on one device, and one taken off on the other")
        d.pg.goto(SITE + "/101:4")
        d.pg.wait_for_load_state("networkidle")
        a.pg.goto(SITE + "/101:4")
        a.pg.wait_for_load_state("networkidle")
        a.bookmark("101:4.5")
        ok(a.kept()["marks"] == ["2:0.1", "101:4.2", "101:4.5"], "set, by the bar's button")
        ok(wait(lambda: ("mark", "101:4.5") in items(db)), "it reaches the account")
        d.later()
        ok(until(d.pg, """document.querySelector('main p.t[id="101:4.5"]').classList.contains('bmk')"""),
           "and the other device's page has its ribbon, without a reload")
        d.bookmark("101:4.2")
        ok(d.kept()["marks"] == ["2:0.1", "101:4.5"], "one taken off there")
        ok(wait(lambda: ("mark", "101:4.2") in items(db) and items(db)[("mark", "101:4.2")] is None), "is a row of the account's, removed")
        a.later()
        ok(until(a.pg, """!document.querySelector('main p.t[id="101:4.2"]').classList.contains('bmk')"""),
           "and its ribbon goes from the first device's page")
        ok(a.kept()["marks"] == ["2:0.1", "101:4.5"], "which keeps the two that are left")

        print("Whole paper follows the account, and moves the other device's page")
        settings(a.pg)
        a.pg.check('dialog.settings input[name="whole"]', force=True)
        a.pg.keyboard.press("Escape")
        a.pg.wait_for_url(SITE + "/101#101:4")
        ok(wait(lambda: items(db).get(("set", "whole")) is True), "turned on here, it reaches the account")
        d.later()
        d.pg.wait_for_url(SITE + "/101#101:4")
        ok(True, "and the other device's page is the whole paper, at its section")
        ok(d.pg.evaluate("() => document.documentElement.dataset.whole") == "true", "its setting on")

        print("Restore the defaults, signed in")
        settings(a.pg)
        a.heard.clear()
        a.pg.click("dialog.settings .reset")
        ok(len(a.heard) == 1 and "every device" in a.heard[0], "asks, and says every device: " + repr(a.heard))
        a.pg.keyboard.press("Escape")
        ok(wait(lambda: items(db).get(("set", "theme"), 0) is None and items(db).get(("set", "whole"), 0) is None),
           "each setting that follows the account is a row of it, back at its default")
        d.later()
        d.pg.wait_for_url(SITE + "/101:4")
        d.pg.wait_for_load_state("networkidle")
        now = d.pg.evaluate(ROOT_DATA)
        ok("redletter" not in now and "whole" not in now and "theme" not in now,
           "and is its default on the other device, whose page is the section's again")
        ok(d.kept()["set"] == {"size": "90"}, "whose own text size is as it was: " + repr(d.kept()["set"]))
        ok(d.kept()["marks"] == ["2:0.1", "101:4.5"], "and the bookmarks are no settings")

        print("A change made with no network, sent when it returns")
        a.pg.goto(SITE + "/101:4")
        a.pg.wait_for_load_state("networkidle")
        a.ctx.set_offline(True)
        settings(a.pg, "show")
        a.pg.uncheck('dialog.settings input[name="pilcrow"]', force=True)
        a.pg.keyboard.press("Escape")
        a.pg.wait_for_timeout(4500)
        ok(("set", "pilcrow") not in items(db), "offline, nothing reaches the account")
        ok(a.kept()["set"].get("pilcrow") is False, "and the browser has it")
        a.ctx.set_offline(False)
        ok(wait(lambda: items(db).get(("set", "pilcrow")) is False), "online again, it goes by itself")

        print("Everything a script keeps cleared, the cookies left (Safari, after seven days)")
        d.pg.goto(SITE + "/")
        d.pg.wait_for_load_state("networkidle")
        d.pg.evaluate("() => { localStorage.clear(); localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no'); }")
        d.pg.reload()
        ok(until(d.pg, "!!localStorage.getItem('ub_who') && !!localStorage.getItem('ub_sync')"), "the page finds who is signed in, and asks what they keep")
        k = d.kept()
        ok(k["marks"] == ["2:0.1", "101:4.5"], "the bookmarks are back: " + repr(k["marks"]))
        ok(k["set"] == {"pilcrow": False}, "the settings that follow the account: " + repr(k["set"]))
        ok(k["place"] == items(db)[("place", "")]["ref"] and d.pg.evaluate(BAR)["has"], "and the place, in the bar")
        ok(until(d.pg, "document.documentElement.dataset.pilcrow === 'off'"), "on the page too")

        print("Signing out of a computer that is not one's own")
        rows = len(items(db))
        d.sign_out(clear=True)
        d.pg.wait_for_load_state("networkidle")
        k = d.kept()
        ok(k["who"] is None and k["sync"] is None and k["marks"] == [] and k["place"] is None and k["set"] == {},
           "the box ticked: nothing of the account is left in the browser: " + repr(k))
        ok(not d.pg.evaluate(BAR)["has"] and "pilcrow" not in d.pg.evaluate(ROOT_DATA), "the page is as a first visit's")
        ok(len(items(db)) == rows, "and the account keeps everything")
        ok(not [c for c in d.ctx.cookies() if c["name"] in ("ub_sid", "ub_in")], "signed out")
        d.ctx.close()

        print("Signed out with the box not ticked, and in again: the exchange goes on")
        a.sign_out()
        k = a.kept()
        ok(k["marks"] == ["2:0.1", "101:4.5"] and k["sync"] is not None and k["sync"]["id"] == 1, "the browser is left as it was")
        before = len(a.asked)
        settings(a.pg)
        a.pg.check('dialog.settings input[name="theme"][value="dark"]', force=True)
        a.pg.check('dialog.settings input[name="size"][value="125"]', force=True)
        a.pg.keyboard.press("Escape")
        a.pg.wait_for_timeout(4000)
        ok(a.sent(before) == [], "signed out, a change asks the server nothing")
        a.heard.clear()
        a.sign_in()
        ok(wait(lambda: items(db).get(("set", "theme")) == "dark"), "signed in again, what changed meanwhile goes to the account")
        ok(("set", "size") not in items(db) and a.kept()["set"].get("size") == "125", "but for the text's size, the device's own")
        ok(a.heard == [], "with no question asked")

        print("Another reader signs in on the same browser, and will not have it replaced")
        a.sign_out()
        E.Google.who = dict(BOB)
        a.yes = False
        a.heard.clear()
        ada = items(db)
        a.sign_in(new=True)
        ok(until(a.pg, "!localStorage.getItem('ub_who')", 9000), "asked, and answering no, he is signed out again")
        ok(len(a.heard) == 1 and "another account" in a.heard[0] and "Bob Reader" in a.heard[0], "the question names him: " + repr(a.heard))
        k = a.kept()
        ok(k["marks"] == ["2:0.1", "101:4.5"] and k["sync"]["id"] == 1 and k["set"].get("theme") == "dark", "the browser is as the first reader left it")
        ok(items(db) == ada and items(db, 2) == {}, "her account is untouched, and his keeps nothing of hers")

        print("And then will")
        a.yes = True
        a.heard.clear()
        try:
            a.sign_in()
        except PlaywrightError:                  # the page is read again as soon as he has answered
            pass
        ok(until(a.pg, "(JSON.parse(localStorage.getItem('ub_sync')) || {}).id === 2", 9000), "answering yes, the browser is his")
        a.pg.wait_for_timeout(500)
        a.pg.wait_for_load_state("networkidle")
        k = a.kept()
        ok(len(a.heard) == 1 and k["who"]["name"] == "Bob Reader", "asked once")
        ok(k["marks"] == [] and k["place"] is None and k["set"] == {"size": "125"},
           "her bookmarks, place and settings are out of it, the device's own staying: " + repr({x: k[x] for x in ("set", "marks", "place")}))
        ok("theme" not in a.pg.evaluate(ROOT_DATA) and not a.pg.evaluate(BAR)["has"], "and off the page")
        ok(items(db) == ada, "hers are safe with her account")
        ok(items(db, 2) == {}, "and none of them became his")

        ok(not E.errors, f"no script errors ({E.errors})")
        b.close()
    return 1 if E.fails else 0


if __name__ == "__main__":
    rc = E.main(run)
    print("FAILED: " + "; ".join(E.fails) if E.fails else "all good")
    sys.exit(rc)
