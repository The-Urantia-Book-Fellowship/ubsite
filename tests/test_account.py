"""Accounts (ubsite/account.py, its routes in app.py; Tigran, 2026-11-18):
signing in with Google by the server's own flow, with Google's answer a
stand-in here; what is refused, each with a page or a reason and never a 500;
the cookies; a first sign-in making no account before its reader's tick; who
is signed in; signing out; an account deleted, its bytes gone from the file;
what only some accounts are given; what follows the account, the exchange
between a browser and the server, two browsers each a device (2026-11-19);
and a site with no var/account.toml, which has no accounts at all.  Each test has a database and a configuration of its
own in a temporary directory: nothing here writes var/user.db, and nothing
asks Google.
"""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import re
import sqlite3
import sys
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ubsite import account, l10n  # noqa: E402

DB = ROOT / "var" / "ub.db"
ORIGIN = "https://ubsite.example"
CLIENT = "1234-abc.apps.googleusercontent.example"
ADA = {"sub": "110169484474386276334", "email": "Ada.Reader@example.org", "name": "Ada Reader"}
PICTURE = "https://lh3.googleusercontent.com/a/ACg8ocK-ada_Reader0=s100-c"
# A picture's bytes: a JPEG's first, and enough after them to look for in a file.
JPEG = b"\xff\xd8\xff\xe0" + b"ada-reader-picture-bytes" * 8


class Browser:
    """A browser's side of it: its cookies, kept between requests as a browser
    keeps them, and each answer's status, headers (every Set-Cookie) and body."""

    def __init__(self, host: str = "ubsite.example", scheme: str = "https"):
        self.host, self.scheme, self.jar = host, scheme, {}
        self.set: list[str] = []

    def ask(self, method: str, url: str, body=None, origin: str | None = None,
            ctype: str = "application/json", cookies: bool = True):
        from ubsite.app import app
        path, _, query = url.partition("?")
        raw = b"" if body is None else body if isinstance(body, bytes) else json.dumps(body).encode()
        headers = [(b"host", self.host.encode())]
        if method != "GET":
            headers += [(b"content-type", ctype.encode()), (b"content-length", str(len(raw)).encode())]
        if origin:
            headers.append((b"origin", origin.encode()))
        if cookies and self.jar:
            headers.append((b"cookie", "; ".join(f"{k}={v}" for k, v in self.jar.items()).encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                 "scheme": self.scheme, "path": path, "raw_path": path.encode(), "query_string": query.encode(),
                 "root_path": "", "headers": headers, "client": ("127.0.0.1", 1), "server": (self.host, 443)}
        out = {"status": 0, "headers": [], "body": b""}

        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}

        async def send(m):
            if m["type"] == "http.response.start":
                out["status"] = m["status"]
                out["headers"] = [(k.decode().lower(), v.decode()) for k, v in m["headers"]]
            elif m["type"] == "http.response.body":
                out["body"] += m.get("body", b"")

        asyncio.run(app(scope, receive, send))
        self.set = [v for k, v in out["headers"] if k == "set-cookie"]
        for line in self.set:
            name, _, value = line.split(";")[0].partition("=")
            if re.search(r"max-age=0\b", line, re.I) or value in ('""', ""):
                self.jar.pop(name, None)
            else:
                self.jar[name] = value
        text = out["body"].decode()
        try:
            got = json.loads(text)
        except ValueError:
            got = text
        return out["status"], dict(out["headers"]), got

    def get(self, url, **kw):
        return self.ask("GET", url, **kw)

    def post(self, url, body=None, origin=ORIGIN, **kw):
        return self.ask("POST", url, {} if body is None else body, origin=origin, **kw)


def id_token(claims: dict) -> str:
    """A token as Google's token endpoint sends one: three parts, the middle
    its claims.  Its signature is not looked at (account.claims_of)."""
    def part(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{part({'alg': 'RS256'})}.{part(claims)}.c2lnbmF0dXJl"


class WithAccounts(unittest.TestCase):
    """A site with accounts set up, and Google's answer made here."""

    origin, host, scheme = ORIGIN, "ubsite.example", "https"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.saved = (account.CONF, account._conf, account._accounts, account.fetch_token, account.fetch_photo)
        account.CONF = d / "account.toml"
        account.CONF.write_text(f'origin = "{self.origin}"\n[google]\nclient_id = "{CLIENT}"\n'
                                f'client_secret = "s3cret"\n', encoding="utf-8")
        account._conf = None
        self.db = d / "user.db"
        account._accounts = account.Accounts(self.db)
        self.said = {}           # what Google's token endpoint was asked
        self.claims = {}         # what it says, over the defaults
        self.fails = None
        account.fetch_token = self.google
        self.fetched = []        # the pictures asked for, in order
        self.photo = (JPEG, "image/jpeg")
        account.fetch_photo = self.picture

    def tearDown(self):
        account.CONF, account._conf, account._accounts, account.fetch_token, account.fetch_photo = self.saved
        self.tmp.cleanup()

    def picture(self, conf, url):
        self.fetched.append(url)
        return self.photo if url else None

    def google(self, conf, code, verifier):
        self.said = {"code": code, "verifier": verifier, "redirect_uri": conf.callback}
        if self.fails:
            raise self.fails
        c = {"iss": "https://accounts.google.com", "aud": CLIENT, "exp": time.time() + 3600,
             "nonce": self.nonce, "email_verified": True, "picture": PICTURE, **ADA, **self.claims}
        return {"access_token": "ya29.x", "id_token": id_token({k: v for k, v in c.items() if v is not None})}

    def browser(self) -> Browser:
        return Browser(self.host, self.scheme)

    def to_google(self, b: Browser, nxt: str = "/101:4"):
        """/account/login: the address Google is asked at, as its parts."""
        st, h, _ = b.get("/account/login?next=" + nxt)
        self.assertEqual(st, 303)
        q = {k: v[0] for k, v in parse_qs(urlsplit(h["location"]).query).items()}
        self.nonce = q["nonce"]
        return h["location"], q

    def sign_in(self, b: Browser, nxt: str = "/101:4", agree: bool = True):
        """The whole of it, as a reader goes: to Google, back, the tick where
        the account is new, and the page that tells the browser.  The answer
        of the last request made."""
        _, q = self.to_google(b, nxt)
        st, h, body = b.get(f"/account/callback?code=the-code&state={q['state']}")
        if st == 303 and h["location"].startswith("/account/welcome") and agree:
            st, h, body = b.post("/account/agree", {"agree": True})
        return st, h, body

    def rows(self, sql, *args):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class SigningIn(WithAccounts):
    def test_to_google_with_what_openid_asks_and_nothing_more(self):
        b = self.browser()
        url, q = self.to_google(b, "/101:4")
        self.assertTrue(url.startswith(account.AUTH_URI + "?"))
        self.assertEqual(q["client_id"], CLIENT)
        self.assertEqual(q["redirect_uri"], ORIGIN + "/account/callback")
        self.assertEqual(q["response_type"], "code")
        self.assertEqual(q["scope"], "openid email profile")
        self.assertEqual(q["code_challenge_method"], "S256")
        # Google asks which account every time: no site can sign a reader in
        # by sending them here.
        self.assertEqual(q["prompt"], "select_account")
        self.assertGreaterEqual(len(q["state"]), 32)
        self.assertNotEqual(q["state"], q["nonce"])
        self.assertNotIn("s3cret", url)

    def test_a_first_sign_in_makes_no_account_before_the_tick(self):
        b = self.browser()
        st, h, _ = self.sign_in(b, agree=False)
        self.assertEqual((st, h["location"]), (303, "/account/welcome?next=%2F101%3A4"))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM user"), [(0,)])
        self.assertNotIn("__Host-ub_sid", b.jar)
        st, _, page = b.get(h["location"])
        self.assertEqual(st, 200)
        self.assertIn("<b>Ada Reader</b>, Ada.Reader@example.org", l10n_en(page))
        self.assertIn('<a href="/terms">Terms of use</a>', l10n_en(page))
        self.assertIn('<script type="application/json" class="acct-next">"/101:4"</script>', page)
        # Not ticked, nothing is made.
        st, _, j = b.post("/account/agree", {"agree": False})
        self.assertEqual((st, j), (400, {"error": "agree"}))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM user"), [(0,)])
        st, _, j = b.post("/account/agree", {"agree": True})
        self.assertEqual((st, j), (200, {"ok": True}))
        (sub, email, name, terms), = self.rows("SELECT subject, email, name, terms FROM user")
        self.assertEqual((sub, email, name, terms), (ADA["sub"], ADA["email"], ADA["name"], account.TERMS))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM pending"), [(0,)])
        self.assertIn("__Host-ub_sid", b.jar)
        self.assertNotIn("__Host-ub_oauth", b.jar)

    def test_who_is_signed_in_and_the_page_that_says_so(self):
        b = self.browser()
        self.sign_in(b)
        st, h, me = b.get("/account/me")
        self.assertEqual(st, 200)
        self.assertEqual({k: me[k] for k in ("name", "email", "features")},
                         {"name": "Ada Reader", "email": "Ada.Reader@example.org", "features": []})
        self.assertEqual(me["photo"], "data:image/jpeg;base64," + base64.b64encode(JPEG).decode())
        self.assertRegex(me["db"], r"^[0-9a-f]{16}$")
        self.assertEqual(h["cache-control"], "no-store")
        self.assertEqual(h["referrer-policy"], "no-referrer")
        self.assertEqual(h["x-robots-tag"], "noindex")
        st, _, page = b.get("/account/done?next=%2F30%2330%3A4.1-8")
        self.assertEqual(st, 200)
        self.assertIn('class="acct-next">"/30#30:4.1-8"</script>', page)
        # The page's own script: it writes who is signed in, and goes on to
        # what the server wrote, reading no address itself.
        own = page[page.index('class="acct-next"'):]
        own = own[:own.index("</script>", own.index("<script>"))]
        self.assertIn("localStorage.setItem('ub_who'", own)
        self.assertIn("location.replace(next)", own)
        self.assertNotRegex(own, r"location\.(search|href|hash)|document\.URL")

    def test_the_accounts_page_and_where_it_goes_back_to(self):
        b = self.browser()
        st, h, page = b.get("/account?next=%2F30%2330%3A4.1-8")
        self.assertEqual(st, 200)
        self.assertEqual(h["cache-control"], "no-store")
        self.assertIn('<main class="prose legal acctpage">', page)
        self.assertIn('<div class="acct" data-state="out" data-next="/30#30:4.1-8">', page)
        self.assertIn('<p class="acct-back"><a href="/30#30:4.1-8">Continue reading</a></p>', l10n_en(page))
        st, _, page = b.get("/account")
        self.assertIn('data-next="/account"', page)
        self.assertNotIn("acct-back", page)
        # The menu at the header's corner is in this page as in every other,
        # the same box with no word of where to go back to: the script takes
        # the page's own address.
        self.assertEqual(page.count('<div class="acct" data-state="out"'), 2)
        self.assertEqual(page.count('<div class="acct" data-state="out">'), 1)
        st, _, page = b.get("/account?next=//evil.example/")
        self.assertIn('data-next="/"', page)
        self.assertNotIn("evil", page)

    def test_a_second_sign_in_finds_the_account_and_asks_for_no_tick(self):
        self.sign_in(self.browser())
        b = self.browser()
        self.claims = {"name": "Ada R.", "email": "ada@example.net"}       # as Google now gives them
        st, h, _ = self.sign_in(b, "/1:1")
        self.assertEqual((st, h["location"]), (303, "/account/done?next=%2F1%3A1"))
        self.assertEqual(self.rows("SELECT subject, email, name FROM user"),
                         [(ADA["sub"], "ada@example.net", "Ada R.")])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM session"), [(2,)])
        self.assertEqual(b.get("/account/me")[2]["email"], "ada@example.net")

    def test_google_is_given_the_verifier_whose_hash_it_was_sent(self):
        import hashlib
        b = self.browser()
        _, q = self.to_google(b)
        b.get(f"/account/callback?code=the-code&state={q['state']}")
        want = base64.urlsafe_b64encode(hashlib.sha256(self.said["verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(q["code_challenge"], want)
        self.assertEqual(self.said["code"], "the-code")
        self.assertEqual(self.said["redirect_uri"], ORIGIN + "/account/callback")


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Picture(WithAccounts):
    """The account's picture (Tigran, 2026-11-18): a small copy fetched by the
    server as its reader signs in, kept with the account, and handed to the
    browser with who is signed in, so that no page asks Google for it."""

    def test_not_fetched_before_the_tick_and_kept_after(self):
        b = self.browser()
        self.sign_in(b, agree=False)
        self.assertEqual(self.fetched, [])                                 # only its address waits
        self.assertEqual(self.rows("SELECT picture FROM pending"), [(PICTURE,)])
        b.post("/account/agree", {"agree": True})
        self.assertEqual(self.fetched, [PICTURE])
        self.assertEqual(self.rows("SELECT photo, photo_type FROM user"), [(JPEG, "image/jpeg")])

    def test_as_google_has_it_at_each_sign_in(self):
        self.sign_in(self.browser())
        self.photo = (b"\x89PNG\r\n\x1a\n" + b"another", "image/png")
        b = self.browser()
        self.sign_in(b)
        self.assertEqual(self.fetched, [PICTURE, PICTURE])
        self.assertTrue(b.get("/account/me")[2]["photo"].startswith("data:image/png;base64,"))
        # None to be had this time: the one kept before stays.
        self.photo = None
        self.sign_in(self.browser())
        self.assertEqual(self.rows("SELECT photo_type FROM user"), [("image/png",)])

    def test_none_costs_no_sign_in(self):
        self.photo = None
        b = self.browser()
        st, _, j = self.sign_in(b)
        self.assertEqual((st, j), (200, {"ok": True}))
        self.assertEqual(b.get("/account/me")[2]["photo"], "")
        # And an account whose token names no picture.
        self.claims = {"sub": "222", "email": "bob@example.org", "name": "Bob", "picture": None}
        b = self.browser()
        self.sign_in(b)
        self.assertEqual(b.get("/account/me")[2]["photo"], "")

    def test_only_from_where_google_keeps_pictures(self):
        conf = account.config()
        for url in ("https://lh3.googleusercontent.com/a/ACg8ocK=s96-c", "https://lh5.googleusercontent.com/-x/photo.jpg"):
            self.assertTrue(conf.pictures.fullmatch(url), url)
        for url in ("http://lh3.googleusercontent.com/a/x", "https://evil.example/a.jpg", "https://lh3.googleusercontent.com.evil.example/a",
                    "https://lh3.googleusercontent.com/a/x?next=https://evil.example", "file:///etc/passwd", "http://127.0.0.1:8130/stats", ""):
            self.assertIsNone(conf.pictures.fullmatch(url), url)
            self.assertIsNone(self.saved[4](conf, url), url)               # the real fetch_photo: refused unasked
        self.claims = {"picture": "https://evil.example/a.jpg"}
        b = self.browser()
        self.sign_in(b)
        self.assertEqual(self.fetched, [""])                               # the token's word for it is not taken
        self.assertEqual(b.get("/account/me")[2]["photo"], "")

    def test_a_file_made_before_the_picture_gains_its_columns(self):
        con = sqlite3.connect(self.db)
        con.executescript("CREATE TABLE user (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,"
                          " email TEXT NOT NULL, name TEXT NOT NULL, made TEXT NOT NULL, seen TEXT NOT NULL,"
                          " terms TEXT NOT NULL, agreed TEXT NOT NULL, UNIQUE (provider, subject));"
                          "CREATE TABLE pending (token TEXT PRIMARY KEY, subject TEXT NOT NULL, email TEXT NOT NULL,"
                          " name TEXT NOT NULL, expires INTEGER NOT NULL);"
                          "INSERT INTO user VALUES (1, 'google', '%s', 'old@example.org', 'Ada', 't', 't', 'd', 't');" % ADA["sub"])
        con.close()
        b = self.browser()
        st, h, _ = self.sign_in(b)
        self.assertEqual(st, 303)                                          # the account that was there, and no tick
        self.assertEqual(self.rows("SELECT id, email, photo_type FROM user"), [(1, ADA["email"], "image/jpeg")])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Cookies(WithAccounts):
    def test_names_and_flags_on_https(self):
        b = self.browser()
        self.to_google(b)
        (state,) = b.set
        self.assertRegex(state, r"^__Host-ub_oauth=[\w-]+; ")
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=600"):
            self.assertIn(flag, state)
        self.assertNotIn("Domain", state)
        self.sign_in(b)
        by = {c.split("=")[0]: c for c in b.set}
        sid = by["__Host-ub_sid"]
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", f"Max-Age={account.SESSION_S}"):
            self.assertIn(flag, sid)
        self.assertNotIn("Domain", sid)
        # And one a script may read, which says only that there is a session.
        self.assertRegex(by["ub_in"], r"^ub_in=1; ")
        self.assertNotIn("HttpOnly", by["ub_in"])
        self.assertIn("Secure", by["ub_in"])

    def test_the_session_is_kept_only_as_its_hash(self):
        b = self.browser()
        self.sign_in(b)
        raw = b.jar["__Host-ub_sid"]
        self.assertGreaterEqual(len(raw), 43)                              # 256 bits
        self.assertEqual(self.rows("SELECT token FROM session"), [(account.digest(raw),)])
        blob = b"".join(p.read_bytes() for p in self.db.parent.iterdir() if p.name.startswith("user.db"))
        self.assertNotIn(raw.encode(), blob)

    def test_no_cookie_no_account(self):
        b = self.browser()
        self.sign_in(b)
        st, _, j = self.browser().get("/account/me")
        self.assertEqual((st, j), (401, {"error": "signed out"}))
        b.jar["__Host-ub_sid"] = "x" * 43
        self.assertEqual(b.get("/account/me")[0], 401)
        self.assertNotIn("ub_in", b.jar)                                   # and the hint is taken back

    def test_a_session_ends_and_is_renewed_as_it_is_used(self):
        b = self.browser()
        self.sign_in(b)
        con = sqlite3.connect(self.db)
        con.execute("UPDATE session SET renewed = renewed - ?, expires = expires - ?",
                    (account.RENEW_S + 5, account.RENEW_S + 5))
        con.commit()
        (before,), = self.rows("SELECT expires FROM session")
        st, _, _ = b.get("/account/me")
        self.assertEqual(st, 200)
        self.assertTrue(any(c.startswith("__Host-ub_sid=") for c in b.set))  # sent again, its six months anew
        (after,), = self.rows("SELECT expires FROM session")
        self.assertGreater(after, before)
        b.get("/account/me")
        self.assertEqual(b.set, [])                                         # not on every answer
        con.execute("UPDATE session SET expires = ?", (int(time.time()) - 1,))
        con.commit()
        con.close()
        self.assertEqual(b.get("/account/me")[0], 401)


class OnTheDevServer(WithAccounts):
    """http://localhost, where a browser takes no __Host- cookie: plain names."""

    origin, host, scheme = "http://localhost:8130", "localhost:8130", "http"

    @unittest.skipUnless(DB.exists(), "var/ub.db not built")
    def test_plain_names_and_no_secure(self):
        b = self.browser()
        _, q = self.to_google(b)
        self.assertEqual(q["redirect_uri"], "http://localhost:8130/account/callback")
        self.assertRegex(b.set[0], r"^ub_oauth=")
        self.assertNotIn("Secure", b.set[0])
        b.get(f"/account/callback?code=c&state={q['state']}")
        st, _, _ = b.post("/account/agree", {"agree": True}, origin=self.origin)
        self.assertEqual(st, 200)
        self.assertIn("ub_sid", b.jar)
        self.assertEqual(b.get("/account/me")[0], 200)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Refused(WithAccounts):
    def failed(self, b, url, why):
        """A page of the site's saying what went wrong, and no 500."""
        st, _, page = b.get(url)
        self.assertIn(st, (400, 403), url)
        self.assertIn('<main class="prose legal acctpage">', page)
        self.assertIn(str(l10n.tr(why)["en"]), l10n_en(page))
        self.assertNotIn("__Host-ub_sid", b.jar)
        self.assertNotIn("__Host-ub_oauth", b.jar)                          # and the attempt is over
        self.assertEqual(self.rows("SELECT COUNT(*) FROM user") if self.db.exists() else [(0,)], [(0,)])

    def test_an_answer_to_no_question(self):
        b = self.browser()
        self.failed(b, "/account/callback?code=c&state=whatever", "acct:fail:state")

    def test_another_state(self):
        b = self.browser()
        self.to_google(b)
        self.failed(b, "/account/callback?code=c&state=" + "A" * 43, "acct:fail:state")

    def test_a_stale_one(self):
        b = self.browser()
        _, q = self.to_google(b)
        k = json.loads(account._unb64(b.jar["__Host-ub_oauth"]))
        k["t"] -= account.STATE_S + 1
        b.jar["__Host-ub_oauth"] = account._b64(json.dumps(k).encode())
        self.failed(b, f"/account/callback?code=c&state={q['state']}", "acct:fail:state")

    def test_cancelled_at_google(self):
        b = self.browser()
        _, q = self.to_google(b)
        self.failed(b, f"/account/callback?error=access_denied&state={q['state']}", "acct:fail:cancelled")

    def test_google_not_answering(self):
        b = self.browser()
        _, q = self.to_google(b)
        self.fails = account.Refused(502, "google")
        self.failed(b, f"/account/callback?code=c&state={q['state']}", "acct:fail:google")

    def test_what_the_token_must_say(self):
        for claims, why in (({"nonce": "another"}, "acct:fail:google"),
                            ({"aud": "someone-elses-client"}, "acct:fail:google"),
                            ({"iss": "https://accounts.example"}, "acct:fail:google"),
                            ({"exp": time.time() - 1}, "acct:fail:google"),
                            ({"sub": None}, "acct:fail:google"),
                            ({"email": None}, "acct:fail:google"),
                            ({"email_verified": False}, "acct:fail:unverified"),
                            ({"email_verified": None}, "acct:fail:unverified")):
            with self.subTest(claims=claims):
                b = self.browser()
                _, q = self.to_google(b)
                self.claims = claims
                self.failed(b, f"/account/callback?code=c&state={q['state']}", why)

    def test_a_token_that_is_no_token(self):
        b = self.browser()
        _, q = self.to_google(b)
        account.fetch_token = lambda *a: {"error": "invalid_grant"}
        self.failed(b, f"/account/callback?code=c&state={q['state']}", "acct:fail:google")

    def test_next_is_a_path_of_this_site_or_the_home_page(self):
        for nxt, want in (("/101:4", "/101:4"), ("/30#30:4.1-8", "/30#30:4.1-8"), ("/search?q=faith", "/search?q=faith"),
                          ("//evil.example/x", "/"), ("/\\evil.example", "/"), ("https://evil.example", "/"),
                          ("javascript:alert(1)", "/"), ("evil", "/"), ("/a\\b", "/"), ("/a\nb", "/"), ("", "/"),
                          ("/" + "a" * 600, "/")):
            self.assertEqual(account.local(nxt), want, nxt)
        st, _, page = self.browser().get("/account/done?next=%2F%2Fevil.example%2Fx")
        self.assertEqual(st, 200)
        self.assertIn('class="acct-next">"/"</script>', page)

    def test_a_post_from_elsewhere_or_not_json(self):
        b = self.browser()
        self.sign_in(b)
        for kw in ({"origin": None}, {"origin": "https://evil.example"}, {"origin": "https://ubsite.example.evil.example"},
                   {"ctype": "text/plain"}, {"ctype": "application/x-www-form-urlencoded"}):
            for path in ("/account/logout", "/account/delete", "/account/agree"):
                with self.subTest(path=path, **kw):
                    st, _, j = b.post(path, {"email": ADA["email"], "agree": True}, **kw)
                    self.assertEqual((st, j), (403, {"error": "origin"}))
        self.assertEqual(b.get("/account/me")[0], 200)                     # still signed in, still there
        st, _, j = b.post("/account/logout", b"x" * 2000)
        self.assertEqual((st, j), (413, {"error": "too large"}))
        st, _, j = b.post("/account/logout", b"[1]")
        self.assertEqual((st, j), (400, {"error": "json"}))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Leaving(WithAccounts):
    def test_signed_out_here_and_not_there(self):
        b, other = self.browser(), self.browser()
        self.sign_in(b)
        self.sign_in(other)
        st, _, j = b.post("/account/logout")
        self.assertEqual((st, j), (200, {"ok": True}))
        self.assertNotIn("__Host-ub_sid", b.jar)
        self.assertNotIn("ub_in", b.jar)
        self.assertEqual(b.get("/account/me")[0], 401)
        self.assertEqual(other.get("/account/me")[0], 200)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM session"), [(1,)])

    def test_deleted_by_its_address_and_gone_from_the_file(self):
        b, other = self.browser(), self.browser()
        self.sign_in(b)
        self.sign_in(other)
        account.accounts().grant(ADA["email"], "ai")
        b.post("/account/sync", {"first": True, "n": 0, "ch": [
            ["set", "theme", "dark"], ["mark", "101:4.2", {"title": "The Real Nature of Religion",
                                                           "q": "kept-words-of-a-bookmark", "at": 5, "v": "8"}]]})
        self.assertEqual(self.rows("SELECT COUNT(*) FROM item"), [(2,)])
        st, _, j = b.post("/account/delete", {"email": "someone@else.example"})
        self.assertEqual((st, j), (400, {"error": "address"}))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM user"), [(1,)])
        st, _, j = b.post("/account/delete", {"email": " ada.reader@EXAMPLE.org "})
        self.assertEqual((st, j), (200, {"ok": True}))
        for table in ("user", "session", "allow", "pending", "item"):
            self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {table}"), [(0,)], table)
        self.assertEqual(other.get("/account/me")[0], 401)                 # every session of it
        # The bytes too: not in the database, nor in its journal.
        blob = b"".join(p.read_bytes() for p in self.db.parent.iterdir() if p.name.startswith("user.db"))
        for word in (ADA["sub"].encode(), b"Ada.Reader@example.org", b"ada.reader@example.org", b"Ada Reader", JPEG[4:40],
                     b"kept-words-of-a-bookmark"):
            self.assertNotIn(word, blob, word)
        st, _, j = b.post("/account/delete", {"email": ADA["email"]})
        self.assertEqual(st, 401)


THEME = ["set", "theme", "dark"]
# The translations open under every paragraph, and the tab chosen in them:
# they came to follow the account on 2026-11-20 (settings.LATE).
OPEN, TAB = ["set", "tropen", True], ["set", "trtab", "all"]
A_MARK = ["mark", "101:4.2", {"title": "The Real Nature of Religion", "q": "Revelation is a technique", "at": 1000, "v": "8"}]
B_MARK = ["mark", "2:0.1", {"title": "The Nature of God", "q": "Inasmuch as man\u2019s highest", "at": 2000, "v": "8"}]


def place(ref: str, at: int) -> list:
    return ["place", "", {"ref": ref, "title": "A paper", "at": at, "v": "8"}]


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Following(WithAccounts):
    """What follows the account (account.py sync()).  Each Browser is a
    device, signed in to the one account; `said` is what the exchange
    answered, and a device keeps the number and the database it was told."""

    def device(self) -> Browser:
        b = self.browser()
        self.sign_in(b)
        b.n, b.db = 0, None
        return b

    def exchange(self, b: Browser, ch=(), first: bool = False, **kw) -> dict:
        st, _, got = b.post("/account/sync", {"first": first, "db": b.db, "n": b.n, "ch": list(ch), **kw})
        self.assertEqual(st, 200, got)
        if not got.get("restart"):
            b.n, b.db = got["n"], got["db"]
        return got

    def kept(self) -> dict:
        return {(k, key): (None if v is None else json.loads(v))
                for k, key, v in self.rows("SELECT kind, key, value FROM item")}

    def test_a_new_account_takes_what_the_first_device_has(self):
        a = self.device()
        got = self.exchange(a, [THEME, ["set", "whole", True], ["set", "rate", 1.25], A_MARK, place("101:4.2", 500)], first=True)
        self.assertEqual((got["n"], got["had"], got["ch"], got["id"]), (1, False, [], 1))
        self.assertEqual(got["db"], self.rows("SELECT value FROM meta WHERE key = 'id'")[0][0])
        self.assertEqual(self.kept(), {
            ("set", "theme"): "dark", ("set", "whole"): True, ("set", "rate"): 1.25,
            ("mark", "101:4.2"): A_MARK[2],
            ("place", ""): {"ref": "101:4.2", "title": "A paper", "at": 500, "v": "8"}})
        # With nothing changed and nothing elsewhere, nothing comes, and the number stands.
        self.assertEqual(self.exchange(a)["ch"], [])
        self.assertEqual(a.n, 1)

    def test_a_first_exchange_that_brings_nothing_is_still_one(self):
        a, b = self.device(), self.device()
        self.assertEqual(self.exchange(a, first=True)["n"], 1)
        # So the second device's settings do not become the account's: it has
        # had an exchange, and its settings are every one its default.
        got = self.exchange(b, [THEME], first=True)
        self.assertEqual((got["had"], got["ch"], self.kept()), (True, [], {}))

    def test_a_second_device_takes_the_accounts_settings_and_keeps_every_bookmark(self):
        a, b = self.device(), self.device()
        self.exchange(a, [THEME, A_MARK, place("101:4.2", 5000)], first=True)
        got = self.exchange(b, [["set", "theme", "light"], ["set", "redletter", False], B_MARK, place("2:0.1", 4000)],
                            first=True)
        self.assertTrue(got["had"])
        # The account's settings, whole, and not this device's; its bookmark;
        # its place, the newer.  This device's bookmark is taken, and not sent back.
        self.assertCountEqual(got["ch"], [THEME, A_MARK, place("101:4.2", 5000)])
        k = self.kept()
        self.assertEqual(k[("set", "theme")], "dark")
        self.assertNotIn(("set", "redletter"), k)
        self.assertEqual((k[("mark", "2:0.1")], k[("mark", "101:4.2")]), (B_MARK[2], A_MARK[2]))
        self.assertEqual(k[("place", "")]["ref"], "101:4.2")
        # And the first device learns of the second's bookmark, and of nothing else.
        self.assertEqual(self.exchange(a)["ch"], [B_MARK])

    def test_a_newer_place_on_a_second_device_becomes_the_accounts(self):
        a, b = self.device(), self.device()
        self.exchange(a, [place("101:4.2", 5000)], first=True)
        self.assertEqual(self.exchange(b, [place("2:0.1", 6000)], first=True)["ch"], [])
        self.assertEqual(self.exchange(a)["ch"], [place("2:0.1", 6000)])

    def test_a_bookmark_here_is_kept_though_removed_elsewhere(self):
        a, b = self.device(), self.device()
        self.exchange(a, [A_MARK], first=True)
        self.exchange(a, [["mark", "101:4.2", None]])
        self.assertIsNone(self.kept()[("mark", "101:4.2")])                # a removal is a row
        got = self.exchange(b, [A_MARK], first=True)                      # signing in loses no bookmark
        self.assertEqual(got["ch"], [])
        self.assertEqual(self.kept()[("mark", "101:4.2")], A_MARK[2])
        self.assertEqual(self.exchange(a)["ch"], [A_MARK])

    def test_a_change_reaches_the_other_device_and_so_does_a_removal(self):
        a, b = self.device(), self.device()
        self.exchange(a, [THEME, A_MARK], first=True)
        self.exchange(b, first=True)
        got = self.exchange(a, [["set", "theme", None], ["set", "lang", "ru"], ["mark", "101:4.2", None], B_MARK])
        self.assertEqual((got["n"], got["ch"]), (2, []))
        self.assertCountEqual(self.exchange(b)["ch"],
                              [["set", "theme", None], ["set", "lang", "ru"], ["mark", "101:4.2", None], B_MARK])
        self.assertEqual(self.exchange(b)["ch"], [])                       # once

    def test_two_devices_unseen_by_each_other(self):
        """Only then is there anything to settle: a setting and a removal by
        which arrived first, the place and a bookmark added by when they were
        made, whatever order they arrived in."""
        a, b = self.device(), self.device()
        self.exchange(a, [A_MARK], first=True)
        self.exchange(b, first=True)
        # A setting: a's arrives first and stands; b is told so.
        self.exchange(a, [THEME])
        got = self.exchange(b, [["set", "theme", "light"]])
        self.assertEqual((got["ch"], self.kept()[("set", "theme")]), ([THEME], "dark"))
        # Seen, b's next change of it is taken.
        self.assertEqual(self.exchange(b, [["set", "theme", "light"]])["ch"], [])
        self.assertEqual(self.exchange(a)["ch"], [["set", "theme", "light"]])
        # The place: b's was made later, and arrives first; a's older one does not replace it.
        self.exchange(b, [place("2:0.1", 9000)])
        self.assertEqual(self.exchange(a, [place("101:4.2", 8000)])["ch"], [place("2:0.1", 9000)])
        # And the other way round: a's is the later made, though it arrives second.
        self.exchange(b, [place("2:0.2", 9500)])
        self.assertEqual(self.exchange(a, [place("101:4.3", 9900)])["ch"], [])
        self.assertEqual(self.exchange(b)["ch"], [place("101:4.3", 9900)])
        # A bookmark removed on one device and, unseen, set again on another
        # before that: the removal, which arrived first, stands.
        self.exchange(a, [["mark", "101:4.2", None]])
        again = ["mark", "101:4.2", dict(A_MARK[2], at=1500)]
        self.assertEqual(self.exchange(b, [again])["ch"], [["mark", "101:4.2", None]])
        self.assertIsNone(self.kept()[("mark", "101:4.2")])

    def test_a_time_is_never_later_than_the_servers_clock(self):
        a, b = self.device(), self.device()
        self.exchange(a, first=True)
        self.exchange(b, first=True)
        ahead = int(time.time() * 1000) + 10 * 86400 * 1000            # a's clock is ten days fast
        self.exchange(a, [place("101:4.2", ahead)])
        kept = self.kept()[("place", "")]["at"]
        self.assertLessEqual(kept, int(time.time() * 1000))
        time.sleep(0.01)
        # So b's place, made after it by the server's clock, is not held back for ten days.
        self.assertEqual(self.exchange(b, [place("2:0.1", int(time.time() * 1000))])["ch"], [])

    def test_an_answer_lost_and_the_same_sent_again(self):
        a, b = self.device(), self.device()
        self.exchange(a, first=True)
        self.exchange(b, first=True)
        n, db = a.n, a.db
        self.exchange(a, [THEME, A_MARK])
        a.n, a.db = n, db                                                  # as if the answer never came
        got = self.exchange(a, [THEME, A_MARK])
        self.assertEqual((got["ch"], got["n"]), ([], n + 1))                # taken as its own, and written once
        self.assertCountEqual(self.exchange(b)["ch"], [THEME, A_MARK])

    def test_what_is_not_taken_and_the_rest_that_is(self):
        a = self.device()
        got = self.exchange(a, [
            ["set", "size", "125"],                 # the device's own
            ["set", "tappage", True],               # a setting long gone
            ["set", "whole", "yes"],                # not its setting's type
            ["set", "rate", True],
            ["set", "face", "x" * 501],              # longer than any setting's words
            ["mark", "999:1.1", A_MARK[2]],         # no paragraph of the book
            ["mark", "1:1", A_MARK[2]],             # nor a paragraph's reference
            ["place", "", {"ref": "999:1.1", "at": 5}],
            ["place", "x", {"ref": "1:1.1", "at": 5}],
            ["set", "theme", "sepia"],              # of its type: a name is not held to today's choices
            ["set", "theme", "dark"],               # said twice: the first stands
            A_MARK], first=True)
        self.assertEqual(got["ch"], [])
        self.assertEqual(self.kept(), {("set", "theme"): "sepia", ("mark", "101:4.2"): A_MARK[2]})
        # Words are kept on one line, and bounded.
        self.exchange(a, [["mark", "2:0.1", {"title": "T\n" + "t" * 300, "q": "q" * 900, "at": "soon", "v": 8}]])
        kept = self.kept()[("mark", "2:0.1")]
        self.assertEqual((kept["title"][:3], len(kept["title"]), len(kept["q"]), kept["at"], kept["v"]),
                         ("T t", 200, 400, 0, ""))

    def test_a_script_from_before_a_setting_followed_is_told_nothing_of_it_and_takes_nothing_back(self):
        """settings.LATE.  The first script, which names no version, noted
        every setting it was sent, known to it or not, and said of one it did
        not keep that it was back at its default, which the server took: a
        page left open from before a deploy would have folded the translations
        on every other device each time it was left (found in review,
        2026-11-20).  So it is told nothing of such a setting, and nothing it
        says of one is heard."""
        new, old = self.device(), self.device()
        self.exchange(new, [OPEN, TAB, THEME], first=True, v=2, was=1)
        self.assertEqual((self.kept()[("set", "tropen")], self.kept()[("set", "trtab")]), (True, "all"))
        # A first exchange is answered with every setting of the account's: but for these.
        self.assertEqual(self.exchange(old, first=True)["ch"], [THEME])
        # And what the first script would then have said of them.
        got = self.exchange(old, [["set", "tropen", None], ["set", "trtab", None], ["set", "theme", "light"]])
        self.assertEqual(got["ch"], [])
        k = self.kept()
        self.assertEqual((k[("set", "tropen")], k[("set", "trtab")], k[("set", "theme")]), (True, "all", "light"))
        # Nor may it set one, having no such setting to set.
        self.exchange(old, [["set", "tropen", False], ["set", "trtab", "ud"]])
        self.assertEqual((self.kept()[("set", "tropen")], self.kept()[("set", "trtab")]), (True, "all"))
        # The device with today's script hears of the theme alone.
        self.assertEqual(self.exchange(new, v=2, was=2)["ch"], [["set", "theme", "light"]])
        # A later change of one of them is not told to the old script either.
        self.exchange(new, [["set", "tropen", None]], v=2, was=2)
        self.assertEqual(self.exchange(old)["ch"], [])

    def test_a_browser_whose_script_has_just_come_to_know_a_setting_is_sent_it_whatever_its_number(self):
        """`was`, the version of the script that made what the browser keeps
        of its last exchange.  Under the old script its number went on past
        the rows it was not told of, so the new one is sent them, once; and
        what it says of them is settled as unseen, the first to arrive
        standing, so that a tab chosen long ago on this device does not
        replace the account's."""
        a, b = self.device(), self.device()
        self.exchange(a, first=True, v=2, was=1)
        self.exchange(b, first=True)
        self.exchange(a, [OPEN, TAB, THEME], v=2, was=2)
        self.assertEqual(self.exchange(b)["ch"], [THEME])                  # the old script: its number is past them now
        n = b.n
        got = self.exchange(b, [["set", "trtab", "ud"]], v=2, was=1)       # the page loaded again, the new script
        self.assertCountEqual(got["ch"], [OPEN, TAB])
        self.assertEqual((self.kept()[("set", "trtab")], b.n), ("all", n))
        self.assertEqual(self.exchange(b, v=2, was=2)["ch"], [])           # once
        # Seen, its next change of the tab is taken, and the other device hears.
        self.assertEqual(self.exchange(b, [["set", "trtab", "ud"]], v=2, was=2)["ch"], [])
        self.assertEqual(self.exchange(a, v=2, was=2)["ch"], [["set", "trtab", "ud"]])

    def test_a_tab_kept_on_a_device_becomes_the_accounts_where_it_has_none(self):
        a, b = self.device(), self.device()
        self.exchange(a, first=True, v=2, was=1)
        self.exchange(b, first=True)
        self.assertEqual(self.exchange(b, [["set", "trtab", "ud"]], v=2, was=1)["ch"], [])
        self.assertEqual(self.kept()[("set", "trtab")], "ud")
        self.assertEqual(self.exchange(a, v=2, was=2)["ch"], [["set", "trtab", "ud"]])
        # A state said to be of a later script than the one speaking is of that one's.
        self.assertEqual(self.exchange(a, v=2, was=7)["ch"], [])

    def test_what_is_no_exchange_at_all(self):
        a = self.device()
        for bad in ({"ch": "x"}, {"ch": [["set", "theme"]]}, {"ch": [["note", "1:1.1", None]]}, {"ch": [["set", 5, None]]},
                    {"n": -1}, {"n": "1"}, {"n": True}, {"ch": [THEME] * (account.SYNC_MAX + 1)},
                    {"v": 0}, {"v": "2"}, {"v": True}, {"v": 2.0}, {"v": 2, "was": 0}, {"v": 2, "was": "1"}):
            st, _, j = a.post("/account/sync", {"first": True, "n": 0, "ch": [], **bad})
            self.assertEqual(st, 400, bad)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM item"), [(0,)])
        self.assertEqual(self.rows("SELECT n FROM user"), [(0,)])

    def test_another_database_or_a_number_ahead_starts_over(self):
        a = self.device()
        self.exchange(a, [THEME], first=True)
        for kw in ({"db": "another"}, {"n": a.n + 5}, {"db": None}):
            st, _, got = a.post("/account/sync", {"first": False, "db": a.db, "n": a.n, "ch": [["set", "theme", "light"]], **kw})
            self.assertEqual((st, got), (200, {"restart": True, "db": a.db}), kw)
        self.assertEqual(self.kept(), {("set", "theme"): "dark"})          # nothing was written
        # And the browser begins again, with everything it has: the account's settings come back.
        self.assertEqual(self.exchange(a, [["set", "theme", "light"]], first=True)["ch"], [THEME])

    def test_no_more_bookmarks_than_an_account_may_have(self):
        a = self.device()
        saved, account.MARKS_MAX = account.MARKS_MAX, 2
        try:
            marks = [["mark", f"1:1.{i}", {"title": "", "q": "", "at": i, "v": "8"}] for i in (1, 2, 3)]
            self.exchange(a, marks, first=True)
            self.assertEqual(sorted(k[1] for k in self.kept()), ["1:1.1", "1:1.2"])
            self.exchange(a, [["mark", "1:1.1", None], marks[2]])           # one removed makes room for one
            self.assertEqual(sorted(k[1] for k, v in self.kept().items() if v), ["1:1.2", "1:1.3"])
        finally:
            account.MARKS_MAX = saved

    def test_only_a_reader_signed_in_from_this_site(self):
        a, out = self.device(), self.browser()
        body = {"first": True, "n": 0, "ch": [THEME]}
        st, h, j = out.post("/account/sync", body)
        self.assertEqual((st, j), (401, {"error": "signed out"}))
        self.assertEqual(h["cache-control"], "no-store")
        self.assertEqual(a.post("/account/sync", body, origin="https://elsewhere.example")[0], 403)
        self.assertEqual(a.post("/account/sync", body, ctype="text/plain")[0], 403)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM item"), [(0,)])
        # A session ended: the cookie that says there is one is taken back.
        self.exchange(a, first=True)
        a.post("/account/logout")
        a.jar["__Host-ub_sid"], a.jar["ub_in"] = "stale", "1"
        st, _, _ = a.post("/account/sync", body)
        self.assertEqual(st, 401)
        self.assertNotIn("ub_in", a.jar)

    def test_larger_than_the_accounts_other_posts_and_no_larger_than_nginx_lets_through(self):
        from ubsite import app as A
        a = self.device()
        marks = [["mark", f"1:{s}.{p}", {"title": "The Universal Father", "q": "w" * 300, "at": p, "v": "8"}]
                 for s in range(1, 6) for p in range(1, 6)]
        self.assertGreater(len(json.dumps(marks)), 4 * A.ACCT_BODY)
        got = self.exchange(a, marks, first=True)
        self.assertEqual(len(self.kept()), sum(1 for (c,) in self.rows(
            "SELECT 1 FROM item")))                                         # those the book has, each a row
        self.assertGreater(len(self.kept()), 10)
        st, _, j = a.post("/account/sync", b'{"first": true, "n": 0, "ch": [], "pad": "' + b"x" * A.SYNC_BODY + b'"}')
        self.assertEqual((st, j), (413, {"error": "too large"}))
        # nginx's location for it lets through what the app takes, and no more.
        for name in ("ubsite.nginx", "ubsite-sigmaai.nginx"):
            conf = (ROOT / "deploy" / name).read_text(encoding="utf-8")
            block = conf[conf.index("location = /account/sync {"):]
            self.assertIn("client_max_body_size 1m;", block[:block.index("}")], name)
        self.assertEqual(A.SYNC_BODY, 1024 * 1024)

    def test_a_file_made_before_the_exchange_gains_what_it_needs(self):
        a = self.device()
        con = sqlite3.connect(self.db)
        con.execute("DROP TABLE item")
        con.execute("ALTER TABLE user DROP COLUMN n")
        con.commit()
        con.close()
        self.assertEqual(self.exchange(a, [THEME], first=True)["n"], 1)
        self.assertEqual(self.kept(), {("set", "theme"): "dark"})

    def test_a_backup_put_back_loses_no_one_and_the_browser_starts_over(self):
        """A copy made as the host makes it every night (backup()), put back
        in the file's place: who was signed in still is, the account keeps
        what it kept when the copy was made, and a browser that has exchanged
        with it since, its number ahead of the file's, begins again and brings
        what it has."""
        a = self.device()
        self.exchange(a, [THEME, A_MARK], first=True)
        made = account.accounts().backup()
        self.assertEqual((made["accounts"], made["kept"], made["deleted"]), (1, 2, []))
        self.exchange(a, [B_MARK, ["set", "theme", "light"]])
        self.assertEqual(a.n, 2)
        for p in self.db.parent.glob("user.db*"):                        # the file, and its journal
            p.unlink()
        made["copy"].rename(self.db)
        self.assertEqual(a.get("/account/me")[0], 200)                   # the session is in the copy
        self.assertEqual(self.kept(), {("set", "theme"): "dark", ("mark", "101:4.2"): A_MARK[2]})
        st, _, got = a.post("/account/sync", {"first": False, "db": a.db, "n": a.n, "ch": []})
        self.assertEqual((st, got), (200, {"restart": True, "db": a.db}))
        # Begun again: both bookmarks are the account's, and its settings the copy's.
        got = self.exchange(a, [A_MARK, B_MARK, ["set", "theme", "light"]], first=True)
        self.assertEqual(got["ch"], [THEME])
        self.assertEqual(set(self.kept()), {("set", "theme"), ("mark", "101:4.2"), ("mark", "2:0.1")})

    def test_the_nightly_copy_is_its_readers_alone_and_no_copy_is_kept_thirty_days(self):
        """backup(), which each host's crontab runs: nothing where there are
        no accounts; a copy beside them that only its owner can read, whole;
        and every copy 29 days old deleted, a day inside what Privacy says."""
        import io
        import os
        from contextlib import redirect_stdout
        acc = account.accounts()
        self.assertIsNone(acc.backup())
        self.assertFalse((self.db.parent / "accounts").exists())
        a = self.device()
        self.exchange(a, [THEME, A_MARK, B_MARK], first=True)
        self.exchange(a, [["mark", "2:0.1", None]])
        t = time.time()
        first = acc.backup(now=t - 30 * 86400)                           # thirty nights ago
        os.utime(first["copy"], (t - 30 * 86400,) * 2)
        mid = acc.backup(now=t - 28 * 86400)
        os.utime(mid["copy"], (t - 28 * 86400,) * 2)
        got = acc.backup(now=t - 60)                                     # tonight's, a minute before the next
        self.assertEqual((got["accounts"], got["kept"], got["deleted"]), (1, 2, [first["copy"].name]))
        self.assertEqual(sorted(p.name for p in got["copy"].parent.iterdir()), sorted([mid["copy"].name, got["copy"].name]))
        self.assertEqual(got["copy"].stat().st_mode & 0o777, 0o600)
        self.assertEqual(got["copy"].parent, self.db.parent / "accounts")
        self.assertRegex(got["copy"].name, r"^user-\d{4}-\d\d-\d\d-\d{6}\.db$")
        con = sqlite3.connect(got["copy"])
        self.assertEqual(con.execute("SELECT email FROM user").fetchall(), [(ADA["email"],)])
        con.close()
        self.assertEqual(account.KEEP_DAYS, 29)
        self.assertIn("deleted within 30 days", str(l10n.tr("privacy:account:5")["en"]))
        # The crontab's line: one line to its log each night.
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(account.main(["backup"]), 0)
        self.assertRegex(out.getvalue(), r"^\S+Z user-[\d-]+\.db, read back whole: 1 accounts, 2 things kept\n$")

    def test_a_deploy_takes_one_copy_off_the_host_and_says_how_the_nightly_ones_stand(self):
        """deploy.sh, on a machine that is on only while it is worked at: a
        copy made on the host by SQLite's own backup, whatever build the host
        runs, before anything is shipped; read back; that one alone kept here,
        and not for thirty days; and a warning where the host's crontab has
        made none of late.  No script runs nightly from here."""
        deploy = ROOT / "deploy"
        self.assertFalse((deploy / "backup-accounts.sh").exists())
        sh = (deploy / "deploy.sh").read_text(encoding="utf-8")
        take = sh.index("""sqlite3.connect(\\"var/user.db\\").backup(sqlite3.connect(\\"var/user-backup.db\\"))""")
        self.assertLess(take, sh.index('    ship "$HOST"\ndone'))
        self.assertIn("PRAGMA integrity_check", sh)
        self.assertIn("""find "$HERE/var/accounts" -name "user-$HOST-*.db*" ! -name "$(basename "$copy")" -type f -delete""", sh)
        self.assertIn("WARNING: $HOST has made no nightly copy of its accounts", sh)
        self.assertIn("make -s accounts-prune", sh)
        make = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("find var/accounts -name 'user-*.db*' -type f -mtime +28 -delete", make)
        self.assertIn("serve: stop accounts-prune", make)
        readme = (deploy / "README.md").read_text(encoding="utf-8")
        self.assertIn("17 3 * * * cd /home/tigran/ubsite && .venv/bin/python -m ubsite.account backup >> var/accounts/backup.log 2>&1",
                      readme)

    def test_the_hosts_list_says_what_an_account_keeps(self):
        a = self.device()
        self.exchange(a, [THEME, A_MARK, B_MARK, place("2:0.1", 5)], first=True)
        self.exchange(a, [["mark", "2:0.1", None]])
        self.assertEqual(account.accounts().kept(1), {"set": 1, "mark": 1, "place": 1})


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Given(WithAccounts):
    def test_what_an_address_is_given_follows_the_account(self):
        a = account.accounts()
        a.grant("ADA.reader@example.org", "ai")                            # before she has ever signed in
        self.assertEqual(a.grants(), [("ada.reader@example.org", "ai", None)])
        b = self.browser()
        self.sign_in(b)
        self.assertEqual(b.get("/account/me")[2]["features"], ["ai"])
        (user,), = self.rows("SELECT user_id FROM allow")
        self.assertIsNotNone(user)
        # Her address changes at Google: the account's is still hers.
        self.claims = {"email": "ada@example.net"}
        b2 = self.browser()
        self.sign_in(b2)
        self.assertEqual(b2.get("/account/me")[2]["features"], ["ai"])
        # Given to an account there already is, it is bound at once.
        a.grant("ada@example.net", "beta")
        self.assertEqual(b.get("/account/me")[2]["features"], ["ai", "beta"])
        self.assertTrue(a.revoke("ada@example.net", "beta"))
        self.assertEqual(b.get("/account/me")[2]["features"], ["ai"])
        self.assertFalse(a.revoke("ada@example.net", "beta"))
        with self.assertRaises(ValueError):
            a.grant("ada@example.net", "Not A Feature")

    def test_the_hosts_command_line(self):
        self.sign_in(self.browser())
        a = account.accounts()
        (u,) = a.users()
        self.assertEqual((u["email"], u["name"], u["features"]), (ADA["email"], ADA["name"], []))
        self.assertFalse(a.remove("nobody@example.org"))
        self.assertTrue(a.remove(ADA["email"].upper()))
        self.assertEqual(a.users(), [])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class WithoutAccounts(unittest.TestCase):
    """No var/account.toml: the site has no accounts, and says so by a 404."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.saved = (account.CONF, account._conf, account._accounts)
        account.CONF, account._conf = d / "account.toml", None
        account._accounts = account.Accounts(d / "user.db")
        self.db = d / "user.db"

    def tearDown(self):
        account.CONF, account._conf, account._accounts = self.saved
        self.tmp.cleanup()

    def test_every_address_is_404_and_nothing_is_made(self):
        b = Browser()
        for url in ("/account", "/account/login", "/account/callback?code=c&state=s", "/account/welcome",
                    "/account/done", "/account/me"):
            self.assertEqual(b.get(url)[0], 404, url)
        for url in ("/account/agree", "/account/logout", "/account/delete"):
            self.assertEqual(b.post(url)[0], 404, url)
        self.assertEqual(b.set, [])
        self.assertFalse(self.db.exists())


class Words(unittest.TestCase):
    def test_the_terms_agreed_to_are_the_terms_page_s(self):
        """An account records which terms its reader agreed to, by the day
        terms.html says they last changed."""
        self.assertIn(str(l10n.date(account.TERMS)["en"]), str(l10n.tr("terms:lead")["en"]))

    def test_the_configuration(self):
        for origin in ("https://ubsite.example", "https://ubsite.example:8443", "http://localhost", "http://localhost:8130"):
            account.Config(origin, "id", "secret")
        for origin in ("http://ubsite.example", "https://ubsite.example/", "https://ubsite.example/x", "ubsite.example",
                       "http://127.0.0.1:8130", "", "https://UBSITE.example"):
            with self.assertRaises(ValueError, msg=origin):
                account.Config(origin, "id", "secret")
        with self.assertRaises(ValueError):
            account.Config("https://ubsite.example", "id", "")
        c = account.Config("https://ubsite.example", "id", "secret")
        self.assertEqual((c.cookie("ub_sid"), c.secure, c.callback),
                         ("__Host-ub_sid", True, "https://ubsite.example/account/callback"))

    def test_the_worker_and_the_copy_leave_accounts_to_the_server(self):
        static = ROOT / "ubsite" / "static"
        self.assertIn(r"quiz\/board\/|account\/)/.test(url.pathname)) return;", (static / "sw.js").read_text(encoding="utf-8"))
        core = (static / "offline-core.js").read_text(encoding="utf-8")
        self.assertIn(r"quiz\/board\/|account\/)/.test(path)", core)
        self.assertIn("if (path === '/account') return { res: away(sh, T('This page is read online.')) };", core)

    def test_settings_foot_leads_to_the_account_and_no_tab_does(self):
        """Where the dialog says where the settings are kept, on every page:
        the words as they were, and beside them what a host with accounts
        shows, signed out and signed in, each with the one link, to /account.
        The offline copy's gate follows every link of a stored page: /account
        it answers as a page read online, and nothing under it."""
        from ubsite import settings
        tpl = ROOT / "ubsite" / "templates"
        base = (tpl / "base.html").read_text(encoding="utf-8")
        self.assertIn("""<p class="kept"><span class="kept-only">{{ t('Kept in this browser only.') }}</span>
      <span class="kept-out">{{ t('kept:out') }}</span><span class="kept-in">{{ t('kept:in') }}</span></p>""", base)
        for key in ("kept:out", "kept:in"):
            for lang in l10n.LANGS:
                self.assertEqual(re.findall(r'href="([^"]+)"', str(l10n.tr(key)[lang])), ["/account"], key)
        self.assertNotRegex(base, r'href="/account/')
        self.assertNotIn("account", [g["key"] for g in settings.groups([])])
        # The dev server and the main site; pi5's has none for now (Tigran, 2026-11-19).
        self.assertEqual(settings.ACCOUNT_HOSTS, ["localhost", "ubsite.sigmaai.au"])
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertIn('dialog.settings .kept:not([data-acct="out"]) .kept-out, dialog.settings .kept:not([data-acct="in"]) '
                      '.kept-in,\ndialog.settings .kept[data-acct="in"] .kept-only { display: none; }', css)

    def test_the_accounts_box_is_buttons_and_no_dialog(self):
        """In the header of every page: nothing in it may be a link under
        /account, nor a dialog, at whose end the offline copy cuts the shell,
        nor carry a name, which Settings' form would take for a setting."""
        acct = (ROOT / "ubsite" / "templates" / "_account.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<button\b", acct)), len(re.findall(r'<button type="button"', acct)))
        self.assertNotIn("<dialog", acct)
        self.assertNotRegex(acct, r'href="/account')
        self.assertNotIn(" name=", acct)

    def test_the_menu_at_the_corner_is_every_page_s_and_hidden(self):
        """A <details>, as the ?'s menu is, after it: hidden in the page as
        stored, which is the page of a host with no accounts and of a reader
        with scripts off; the head script shows it where the host has
        accounts, with whoever is signed in, from the browser's own note."""
        base = (ROOT / "ubsite" / "templates" / "base.html").read_text(encoding="utf-8")
        header = base[base.index('<header class="top">'):base.index("</header>")]
        self.assertLess(header.index('<details class="help"'),
                        header.index("""<details class="acctmenu" data-src="{{ asset('account.js') }}" hidden>"""))
        self.assertIn("{{ chrome.person_svg() }}", header)
        head = base[:base.index("</head>")]
        self.assertIn("window.ubMe = function () {", head)
        self.assertIn("on = window.ubAcct.indexOf(location.hostname) >= 0;", head)
        self.assertIn("menu.hidden = !on;", head)
        # Google's words about the reader go in as text, never as markup.
        self.assertNotRegex(head[head.index("window.ubMe"):], r"innerHTML")

    def test_the_script_of_what_follows_is_run_for_a_reader_signed_in(self):
        """static/account.js: named on the menu, and run by ub.js where the
        browser's note says someone is signed in, so a reader with no account
        runs none of it.  Its words are in the scripts' catalog, without which
        its first T() throws, and it is in the offline copy with the rest."""
        from ubsite.app import L10N_SCRIPTS
        from offline import pack
        static = ROOT / "ubsite" / "static"
        self.assertIn("account.js", L10N_SCRIPTS)
        self.assertIn("account.js", pack.ASSETS)
        ub = (static / "ub.js").read_text(encoding="utf-8")
        self.assertIn("if (acctRun || !acctMenu || !acctMenu.dataset.src || !acctWho() || "
                      "/^\\/account\\//.test(location.pathname)) return;", ub)
        self.assertEqual(ub.count("acctMenu.dataset.src"), 2)
        js = (static / "account.js").read_text(encoding="utf-8")
        self.assertIn("fetch('/account/sync'", js)
        # The one address it asks, and nothing of anyone else.
        self.assertEqual(re.findall(r"fetch\('([^']+)'", js), ["/account/sync"])
        self.assertNotRegex(js, r"https?://")

    def test_the_devices_own_settings_are_settings_and_the_page_is_told(self):
        from ubsite import settings
        every = settings.defaults()
        self.assertEqual(settings.DEVICE, ["uisize", "size", "lead", "width", "bvoice", "trvoices",
                                           "rail", "margin", "toc"])
        self.assertTrue(set(settings.DEVICE) < set(every))
        self.assertEqual(set(settings.followed()), set(every) - set(settings.DEVICE))
        for k in ("whole", "lang", "theme", "translations", "voice"):      # Whole paper follows (Tigran, 2026-11-18)
            self.assertIn(k, settings.followed())
        # And the translations' folds, open or shut, with the tab chosen in
        # them, which was the device's own until then (Tigran, 2026-11-20).
        self.assertEqual((every["tropen"], every["trtab"]), (False, ""))
        for k in ("tropen", "trtab"):
            self.assertIn(k, settings.followed())
        base = (ROOT / "ubsite" / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("window.ubOwn = {{ settings_device|tojson }};", base[:base.index("</head>")])


    def test_a_setting_that_comes_to_follow_later_is_named_with_its_version(self):
        """settings.LATE, and account.js's V.  FIRST is what the first script
        of the exchange followed, 2026-11-19, for ever: whatever follows
        beyond it must be in LATE, with the version of the exchange that
        first knew it, or a page from before it would take it back from the
        account (the test above, of a script from before).  V is the latest."""
        from ubsite import settings
        FIRST = {"align", "face", "follow", "foreword", "index", "indexsearch", "lang", "listen", "notes",
                 "notesearch", "onward", "pages", "paranum", "pilcrow", "preview", "quiz", "rate", "redletter",
                 "studynotes", "studysearch", "theme", "tips", "translations", "trsearch", "voice", "whole"}
        self.assertEqual(set(settings.followed()) - FIRST, set(settings.LATE))
        self.assertEqual(settings.LATE, {"tropen": 2, "trtab": 2, "english": 3})
        self.assertTrue(all(isinstance(v, int) and v >= 2 for v in settings.LATE.values()))
        js = (ROOT / "ubsite" / "static" / "account.js").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"\n      V = (\d+);\n", js), [str(max(settings.LATE.values()))])
        self.assertIn("v: V, was: (sy.v | 0) >= 1 ? sy.v | 0 : 1, ch: send });", js)
        self.assertIn("t: Date.now(), v: V, base: base,", js)
        # It notes no setting it does not keep, and calls none back to its default.
        self.assertIn("if (!follows(c[1])) return;", js)
        self.assertIn("for (k in base.set) if (follows(k) && !(k in now.set)) ch.push(['set', k, null]);", js)


def l10n_en(body: str) -> str:
    return re.sub(r'<x-ru lang="ru">.*?</x-ru>', "", body, flags=re.S).replace("<x-en>", "").replace("</x-en>", "")


if __name__ == "__main__":
    unittest.main()
