"""A reader's account, end to end, in Chrome (ubsite/account.py, ub.js,
base.html ubMe; Tigran, 2026-11-18): a reader who never signs in asks the
server nothing of it; the menu at the header's corner, which is there signed
out too, with its button to Google; a first sign-in stopping at the tick, and
making the account only then; the browser told who is signed in, the
account's picture at the corner, fetched by the server and never by a page,
and who in the menu; Settings' foot saying the same and opening the menu;
signing out, the sign staying at the corner; signing in again from Settings'
foot on a whole paper's page, back to the very paragraph; everything a script
keeps cleared, as Safari clears it, and who is signed in found again by the
cookie; the account deleted; a phone, at 412 and 390 px in both languages, signed in
and out, with everything on the name's line, the language and full screen
among it; the narrowest,
where the sign gives way and Settings' foot leads to the page at /account; cancelling
at Google; and in Russian, nothing wider than the window and five tabs as
before.

    .venv/bin/python tools/account_e2e.py        (after make data)

Google is a stand-in on this machine: its two endpoints, which var/account.toml
may name for this (account.py config), the first sending the browser straight
back with a code and the second answering the code with a token, after
checking PKCE's verifier against the challenge it was sent.  Playwright is in
.venv as a dev requirement and drives the system's Chrome.  The app runs on
localhost:8144 with a database and a configuration of its own in a temporary
directory, the visit counter off, and leaves the dev server alone.  Not a
gate: tests/test_account.py holds the flow and what is refused.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE, GOOGLE = "http://localhost:8144", "http://127.0.0.1:8145"
CLIENT = "e2e-client"
ADA = {"sub": "110169484474386276334", "email": "ada.reader@example.org", "name": "Ada Reader",
       "picture": GOOGLE + "/photo/ada"}
# The smallest picture there is: one pixel, a PNG.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
fails: list[str] = []
errors: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, js: str, ms: int = 6000) -> bool:
    """Whether `js` comes true within `ms` (polled: CLAUDE.md trap 41)."""
    end = time.time() + ms / 1000
    while time.time() < end:
        try:
            if pg.evaluate(js):
                return True
        except Exception:                      # the page is on its way to another
            pass
        pg.wait_for_timeout(100)
    return bool(pg.evaluate(js))


class Google(http.server.BaseHTTPRequestHandler):
    """Google's two endpoints, as far as this site uses them."""

    who = dict(ADA)
    cancel = False
    codes: dict[str, dict] = {}
    asked: list[dict] = []
    photos: list[str] = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path.startswith("/photo/"):
            # An account's picture, which the site's server fetches, never a page.
            Google.photos.append(self.headers.get("User-Agent", ""))
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG)))
            self.end_headers()
            self.wfile.write(PNG)
            return
        if url.path != "/auth":
            self.send_error(404)
            return
        Google.asked.append(q)
        back = {"state": q.get("state", "")}
        if Google.cancel:
            back["error"] = "access_denied"
        else:
            code = "code-%d" % (len(Google.codes) + 1)
            Google.codes[code] = {"nonce": q.get("nonce"), "challenge": q.get("code_challenge"), "who": dict(Google.who)}
            back["code"] = code
        self.send_response(302)
        self.send_header("Location", q["redirect_uri"] + "?" + urllib.parse.urlencode(back))
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0)).decode()
        f = {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}
        kept = Google.codes.pop(f.get("code", ""), None)
        made = base64.urlsafe_b64encode(hashlib.sha256(f.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
        if (self.path != "/token" or kept is None or made != kept["challenge"] or f.get("client_id") != CLIENT
                or f.get("client_secret") != "e2e-secret" or f.get("redirect_uri") != SITE + "/account/callback"):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "invalid_grant"}')
            return
        claims = {"iss": GOOGLE, "aud": CLIENT, "exp": int(time.time()) + 3600, "nonce": kept["nonce"],
                  "email_verified": True, **kept["who"]}

        def part(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        out = json.dumps({"access_token": "x", "id_token": f"{part({'alg': 'RS256'})}.{part(claims)}.c2ln"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


SAID = """(sel) => { const el = document.querySelector(sel); if (!el || !el.getClientRects().length) return null;
  const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove());
  [...c.querySelectorAll('*')].forEach(x => { if (x.hasAttribute('hidden')) x.remove(); });
  return c.textContent.replace(/\\s+/g, ' ').trim(); }"""
# The words of Settings' foot as shown: what the stylesheet hides left out.
FOOT = """() => { const k = document.querySelector('dialog.settings .kept');
  return [...k.children].filter(s => getComputedStyle(s).display !== 'none').map(s => {
    const c = s.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent.trim(); }).join(' '); }"""
WHO = "() => JSON.parse(localStorage.getItem('ub_who') || 'null')"


def fresh(b, seed: str = "", width: int = 1100, height: int = 900):
    """A first visit, with the tour seen (help.js) and no worker, so that every
    page is the server's; `seed` is run before each page's own scripts."""
    ctx = b.new_context(viewport={"width": width, "height": height}, service_workers="block")
    ctx.add_init_script("try { if (!sessionStorage.getItem('e2e')) { sessionStorage.setItem('e2e', '1');"
                        " localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no'); %s } }"
                        " catch (e) {}" % seed)
    asked: list[str] = []
    ctx.on("request", lambda r: asked.append(r.method + " " + r.url))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    return ctx, pg, asked


def settings(pg):
    if not pg.evaluate("() => document.querySelector('dialog.settings').open"):
        pg.click("button.gear")
    pg.wait_for_selector("dialog.settings[open]")


def users(db: pathlib.Path) -> list[tuple]:
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT email, name, terms FROM user").fetchall()
    finally:
        con.close()


def run(tmp: pathlib.Path) -> int:
    db = tmp / "user.db"
    corner = """() => { const m = document.querySelector('.top .acctmenu'), s = m.querySelector('summary'),
        sign = s.querySelector('.acctsign'), img = s.querySelector('.acctphoto'), ini = s.querySelector('.acctinit'),
        r = s.getBoundingClientRect(), h = document.querySelector('.top .help').getBoundingClientRect(),
        shown = (e) => e.getClientRects().length > 0;
      return {there: shown(s), who: m.dataset.who || '', sign: shown(sign), photo: shown(img), letter: shown(ini) ? ini.textContent : '',
              src: (img.getAttribute('src') || '').slice(0, 22), width: Math.round(r.width), afterHelp: r.left >= h.right,
              inWindow: r.right <= innerWidth, open: m.open, no: [...document.querySelector('.top').classList].filter(c => c.startsWith('no')).join(' ')}; }"""
    tall = "() => Math.round(document.querySelector('.top').getBoundingClientRect().height)"
    box = "() => document.querySelector('.top .acctmenu .acct').dataset.state"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

        print("A reader who does not sign in")
        ctx, pg, asked = fresh(b)
        pg.goto(SITE + "/101:4")
        pg.wait_for_load_state("networkidle")
        c = pg.evaluate(corner)
        ok(c["there"] and c["sign"] and not c["photo"] and not c["letter"] and c["who"] == "",
           "the header's corner has the account's sign, with no one's picture")
        ok(c["afterHelp"] and c["inWindow"], "after the ?: the corner")
        high = pg.evaluate(tall)
        ok(not [a for a in asked if "/account" in a], "nothing was asked of the server about an account")
        ok(not db.exists(), "and the site has made no database of accounts")
        settings(pg)
        ok(pg.evaluate("() => document.querySelector('dialog.settings .kept').dataset.acct") == "out",
           "Settings' foot is marked signed out")
        ok(pg.evaluate(FOOT) == "Kept in this browser only. Sign in to keep them with an account.",
           "and says so: " + repr(pg.evaluate(FOOT)))
        ok(pg.evaluate("() => document.querySelectorAll('dialog.settings [role=tab]:not([hidden])').length") == 5,
           "five tabs, as before")
        pg.keyboard.press("Escape")

        print("The menu at the corner, to Google and back")
        pg.click(".top .acctmenu > summary")
        ok(pg.evaluate(corner)["open"] and pg.evaluate(box) == "out", "the sign opens a menu, signed out")
        ok(pg.evaluate(SAID, ".top .acctmenu .acct-go") == "Sign in with Google", "with Google's button")
        fit = pg.evaluate("() => { const r = document.querySelector('.top .acctitems').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }")
        ok(fit, "within the window")
        pg.keyboard.press("Escape")
        ok(not pg.evaluate(corner)["open"], "Escape shuts it")
        pg.click(".top .acctmenu > summary")
        pg.click("main p.t")
        ok(not pg.evaluate(corner)["open"], "and so does a click anywhere else")
        pg.click(".top .acctmenu > summary")
        pg.click(".top .acctmenu .acct-go")
        pg.wait_for_url(SITE + "/account/welcome?next=%2F101%3A4")
        q = Google.asked[-1]
        ok(q.get("scope") == "openid email profile" and q.get("prompt") == "select_account"
           and q.get("code_challenge_method") == "S256" and q.get("redirect_uri") == SITE + "/account/callback",
           "Google was asked for who the reader is and nothing more, with PKCE, and to ask which account")
        ok("Ada Reader" in (pg.evaluate(SAID, "main") or ""), "a first sign-in stops at a page that names her")
        ok(users(db) == [] and Google.photos == [], "no account is made yet, and no picture fetched")
        ok(pg.evaluate("() => document.querySelector('.acct-make').disabled"), "Create my account waits for the tick")
        pg.check(".acct-agree")
        pg.click(".acct-make")
        pg.wait_for_url(SITE + "/101:4")
        ok(True, "ticked, the account is made and the reader is back at the page being read")
        ok(users(db) == [(ADA["email"], ADA["name"], "2026-11-18")], "the account, with the terms agreed to: " + repr(users(db)))
        who = pg.evaluate(WHO)
        ok(bool(who) and who.get("name") == "Ada Reader" and who.get("email") == ADA["email"] and who.get("features") == [],
           "the browser keeps who is signed in")
        seen = pg.evaluate("() => document.cookie")
        ok("ub_in=1" in seen and "ub_sid" not in seen and "ub_oauth" not in seen,
           "a script sees that there is a session, and not the session")
        sid = [k for k in ctx.cookies() if k["name"] == "ub_sid"]
        ok(len(sid) == 1 and sid[0]["httpOnly"] and sid[0]["sameSite"] == "Lax", "the session's cookie is the server's alone")

        print("Signed in")
        ok(len(Google.photos) == 1 and "Mozilla" not in Google.photos[0],
           "the picture was fetched once, by the site's server and not by the browser")
        ok(not [a for a in asked if "/photo/" in a], "no page asked Google for it")
        c = pg.evaluate(corner)
        ok(c["who"] == "photo" and c["photo"] and not c["sign"] and c["src"] == "data:image/png;base64,",
           "her picture is at the header's corner, from what the browser keeps")
        ok(c["width"] == 24 and c["afterHelp"], "24 px, after the ?")
        ok(abs(pg.evaluate(tall) - high) <= 1, "and the header is as tall as it was")
        before = len(asked)
        pg.click(".top .acctmenu > summary")
        ok(until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'in'"), "the menu shows her signed in")
        ok(pg.evaluate(SAID, ".top .acctmenu .acct-who") == "Ada Readerada.reader@example.org", "by name and address: "
           + repr(pg.evaluate(SAID, ".top .acctmenu .acct-who")))
        ok(pg.evaluate("() => { const i = document.querySelector('.top .acctitems .acctphoto'); return i.getClientRects().length > 0 && i.src.startsWith('data:image/png'); }"),
           "with her picture")
        ok([pg.evaluate(SAID, ".top .acctmenu .acct-bye"), pg.evaluate(SAID, ".top .acctmenu .acct-del")] == ["Sign out", "Delete my account"],
           "and Sign out and Delete my account")
        pg.wait_for_timeout(600)                     # the menu's opening is told to the script a moment after
        ok([a for a in asked[before:] if "/account" in a] == [f"GET {SITE}/account/me", f"POST {SITE}/account/sync"],
           "opened, it asked the server who is signed in and what the account keeps, once each: "
           + repr([a for a in asked[before:] if "/account" in a]))
        pg.keyboard.press("Escape")
        settings(pg)
        ok(pg.evaluate(FOOT) == "Kept in this browser and with your account, Ada Reader. Account", "Settings' foot says whose: " + repr(pg.evaluate(FOOT)))
        pg.click("dialog.settings .kept a.acctlink:visible")
        ok(until(pg, "!document.querySelector('dialog.settings').open && document.querySelector('.top .acctmenu').open"),
           "and its link shuts Settings and opens the menu")
        pg.keyboard.press("Escape")
        before = len(asked)
        pg.goto(SITE + "/101:5")
        pg.wait_for_load_state("networkidle")
        ok(not [a for a in asked[before:] if a.endswith("/account/me")], "another page does not ask the server who is signed in")
        ok(not [a for a in asked[before:] if "/account/" in a and not a.endswith("/account/sync")],
           "and asks of the account only what it keeps, if anything (tools/follow_e2e.py): "
           + repr([a for a in asked[before:] if "/account" in a]))
        ok(pg.evaluate(corner)["who"] == "photo", "and has her picture at its corner")

        print("Signing out")
        pg.click(".top .acctmenu > summary")
        pg.click(".top .acctmenu .acct-bye")
        ok(until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'out'"), "Sign out, and the menu shows it")
        c = pg.evaluate(corner)
        ok(c["there"] and c["sign"] and not c["photo"] and c["who"] == "", "the sign stays at the corner, without the picture")
        ok(pg.evaluate(SAID, ".top .acctmenu .acct-go") == "Sign in with Google", "and offers to sign in again, there")
        ok(pg.evaluate(WHO) is None and "ub_in" not in pg.evaluate("() => document.cookie")
           and not [k for k in ctx.cookies() if k["name"] == "ub_sid"], "the browser keeps nothing of the session")
        ok(len(users(db)) == 1, "the account is still there")
        pg.keyboard.press("Escape")

        print("Signing in again from Settings' foot, on a whole paper, back to the paragraph")
        pg.evaluate("() => localStorage.setItem('ub_settings', JSON.stringify({whole: true}))")
        pg.goto(SITE + "/101#101:4.2")
        pg.wait_for_load_state("networkidle")
        settings(pg)
        pg.click("dialog.settings .kept a.acctlink:visible")
        pg.wait_for_url(SITE + "/101#101:4.2")
        ok(True, "straight to Google and back: an account there is asks for no tick, and the address keeps its #")
        ok(until(pg, "!!localStorage.getItem('ub_who')") and pg.evaluate(WHO)["name"] == "Ada Reader" and len(users(db)) == 1, "the same account")
        ok(pg.evaluate(corner)["who"] == "photo", "her picture at the corner again")

        print("Everything a script keeps cleared, the cookies left (Safari, after seven days)")
        pg.evaluate("() => { localStorage.clear(); localStorage.setItem('ub_tour', 'seen'); }")
        before = len(asked)
        pg.goto(SITE + "/101:4")
        ok(until(pg, "!!localStorage.getItem('ub_who')"), "the page finds the session's sign and asks who it is")
        ok(len([a for a in asked[before:] if a == f"GET {SITE}/account/me"]) == 1, "once")
        ok(until(pg, "document.querySelector('.top .acctmenu').dataset.who === 'photo'"), "and her picture is at the corner again")
        before = len(asked)
        pg.reload()
        pg.wait_for_load_state("networkidle")
        ok(not [a for a in asked[before:] if a.endswith("/account/me")], "after which no page asks who")

        print("The account deleted")
        pg.click(".top .acctmenu > summary")
        ok(until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'in'"), "in the menu, signed in")
        pg.click(".top .acctmenu .acct-del")
        ok(until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'out'"), "Delete my account, asked and answered yes")
        ok(users(db) == [] and pg.evaluate(WHO) is None, "the account is gone from the server, and its note from the browser")
        blob = b"".join(f.read_bytes() for f in tmp.iterdir() if f.name.startswith("user.db"))
        ok(ADA["email"].encode() not in blob and b"Ada Reader" not in blob and PNG[16:] not in blob, "its bytes too, the picture's among them")
        ctx.close()

        print("A phone: everything on the name's line, the language always")
        # The list of languages and full screen, beside the half-disc, since
        # 2026-11-21, where two flags stood: everything from 384px in English
        # and 356 in Russian at Standard, signed out (from 380 and 360 with
        # the flags); signed in, the letter or the picture 1.6px wider.
        flags = "() => ['.top .langmenu', '.top .fscreen', '.top .theme'].filter(s => document.querySelector(s).getClientRects().length > 0).length"
        for lang in ("en", "ru"):
            for width in (412, 390):
                ctx, pg, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({lang: '%s'}));" % lang, width, 700)
                pg.goto(SITE + "/101:4")
                pg.wait_for_load_state("networkidle")
                c, before = pg.evaluate(corner), pg.evaluate(tall)
                ok(c["there"] and c["sign"] and c["inWindow"] and c["no"] == "" and pg.evaluate(flags) == 3,
                   f"{width} px, {lang}, no one signed in: the gear, the half-disc, full screen, the language, the ? and the account's sign ({c['no'] or 'nothing left out'})")
                Google.who = {"sub": "222", "email": "bob@example.org", "name": "bob the reader"}
                pg.click(".top .acctmenu > summary")
                pg.click(".top .acctmenu .acct-go")
                pg.wait_for_url(lambda u: "/account/welcome" in u or u == SITE + "/101:4")
                if "/account/welcome" in pg.url:
                    pg.check(".acct-agree")
                    pg.click(".acct-make")
                pg.wait_for_url(SITE + "/101:4")
                pg.wait_for_load_state("networkidle")
                Google.who = dict(ADA)
                c = pg.evaluate(corner)
                ok(c["there"] and c["letter"] == "B" and c["who"] == "letter" and c["inWindow"] and c["no"] == "" and pg.evaluate(flags) == 3,
                   f"{width} px, {lang}, signed in: the same, with the first letter of his name for the sign ({c['no'] or 'nothing left out'})")
                ok(pg.evaluate(tall) <= before + 1, f"{width} px, {lang}: the header has no more lines than it had ({before} px, {pg.evaluate(tall)} px)")
                ok(pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"),
                   f"{width} px, {lang}: nothing is wider than the window")
                pg.click(".top .acctmenu > summary")
                fit = pg.evaluate("() => { const r = document.querySelector('.top .acctitems').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }")
                ok(fit and until(pg, "document.querySelector('.top .acctmenu .acct').dataset.state === 'in'"), f"{width} px, {lang}: the menu is within the window")
                ctx.close()

        print("The narrowest phone: the account's sign gives way, and then the language")
        ctx, pg, asked = fresh(b, "", 320, 700)
        pg.goto(SITE + "/101:4")
        pg.wait_for_load_state("networkidle")
        c, before = pg.evaluate(corner), pg.evaluate(tall)
        ok(not c["there"] and c["no"].startswith("noacct"), f"320 px, no one signed in: the sign is left out first ({c['no']})")
        Google.who = {"sub": "222", "email": "bob@example.org", "name": "bob the reader"}
        settings(pg)
        pg.click("dialog.settings .kept a.acctlink:visible")                  # Settings' foot is the way in here
        pg.wait_for_url(lambda u: "/account/welcome" in u or u == SITE + "/101:4")
        if "/account/welcome" in pg.url:
            pg.check(".acct-agree")
            pg.click(".acct-make")
        pg.wait_for_url(SITE + "/101:4")
        pg.wait_for_load_state("networkidle")
        Google.who = dict(ADA)
        c = pg.evaluate(corner)
        ok(not c["there"] and pg.evaluate(tall) <= before + 1, f"320 px, signed in: too narrow for the menu, and the header as it was ({c['no']})")
        settings(pg)
        ok(pg.evaluate(FOOT) == "Kept in this browser and with your account, bob the reader. Account", "Settings' foot says who is signed in")
        pg.click("dialog.settings .kept a.acctlink:visible")
        pg.wait_for_url(SITE + "/account?next=%2F101%3A4")
        ok(until(pg, "document.querySelector('main .acct').dataset.state === 'in'"), "and leads to the account's page")
        ok(pg.evaluate(SAID, "main .acct-bye") == "Sign out", "which has Sign out")
        ctx.close()

        print("Cancelled at Google")
        had = users(db)
        ctx, pg, asked = fresh(b)
        Google.cancel = True
        pg.goto(SITE + "/101:4")
        pg.click(".top .acctmenu > summary")
        pg.click(".top .acctmenu .acct-go")
        pg.wait_for_selector("main .acct-failed")
        Google.cancel = False
        ok(pg.evaluate(SAID, "main .acct-failed") == "Signing in was cancelled.", "a page says so")
        ok(pg.evaluate(SAID, "main .acct-go") == "Sign in with Google", "and offers again")
        ok(users(db) == had, "nothing is made")
        ctx.close()

        print("A phone, in Russian")
        for width in (390, 320):
            ctx, pg, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({lang: 'ru'}));", width, 700)
            pg.goto(SITE + "/101:4")
            pg.wait_for_load_state("networkidle")
            settings(pg)
            fit = pg.evaluate("""() => { const d = document.querySelector('dialog.settings'), t = d.querySelector('.tabs'),
                k = d.querySelector('.kept'), r = d.getBoundingClientRect(), kr = k.getBoundingClientRect();
                return [t.scrollWidth <= t.clientWidth, kr.left >= r.left && kr.right <= r.right + 1, k.scrollWidth <= k.clientWidth + 1,
                        Math.round(kr.height)]; }""")
            ok(fit[0], f"{width} px: the five tabs fit the dialog")
            ok(fit[1] and fit[2], f"{width} px: the foot's line is within it, {fit[3]} px tall")
            said = pg.evaluate("""() => [...document.querySelector('dialog.settings .kept').children]
                .filter(s => getComputedStyle(s).display !== 'none').map(s => { const c = s.cloneNode(true);
                c.querySelectorAll('x-en').forEach(x => x.remove()); return c.textContent.trim(); }).join(' ')""")
            ok(said == "Хранятся только в этом браузере. Войдите, чтобы хранить их вместе с учётной записью.", f"{width} px: in Russian")
            ok(pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"),
               f"{width} px: the page is no wider than the window")
            ctx.close()

        ok(not errors, f"no script errors ({errors})")
        b.close()
    return 1 if fails else 0


SERVE = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main(what=None) -> int:
    """The site and the stand-in for Google, started, and `what` run against
    them (run(), above; tools/follow_e2e.py brings its own)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        conf = tmp / "account.toml"
        conf.write_text(f'origin = "{SITE}"\n[google]\nclient_id = "{CLIENT}"\nclient_secret = "e2e-secret"\n'
                        f'auth_uri = "{GOOGLE}/auth"\ntoken_uri = "{GOOGLE}/token"\nissuers = ["{GOOGLE}"]\n'
                        f'pictures = "{GOOGLE}/photo/[a-z]+"\n', encoding="utf-8")
        google = http.server.ThreadingHTTPServer(("127.0.0.1", int(GOOGLE.rsplit(":", 1)[1])), Google)
        threading.Thread(target=google.serve_forever, daemon=True).start()
        env = dict(os.environ, UB_VISITS="off", UB_ACCOUNT_CONF=str(conf), UB_USER_DB=str(tmp / "user.db"))
        server = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", SERVE, str(ROOT / "var" / "no-offline-copy"),
                                   SITE.rsplit(":", 1)[1]], cwd=ROOT, env=env)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(SITE + "/healthz", timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            return (what or run)(tmp)
        finally:
            server.terminate()
            server.wait()
            google.shutdown()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
