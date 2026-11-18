"""Accounts: who a reader is, so that what they keep can follow them from one
device to another (Tigran, 2026-11-18; DECISIONS.md, Accounts).

Signing in is Google's, by OpenID Connect's server flow, and the flow is the
server's: no page carries a script of Google's, which would tell Google of
every visit and be missing offline.  /account/login sends the reader to
Google with a state, a nonce and a PKCE challenge kept in a cookie for ten
minutes; /account/callback exchanges the code Google sends back for an ID
token at Google's token endpoint, over TLS and with the client's secret, which
is why its signature is not checked (Google's documentation says so of a token
fetched this way), and its claims are: issuer, audience, expiry, nonce, and
that the address is verified.

An account is Google's `sub`, never the address, which can change.  A first
sign-in makes none until the reader has agreed to the terms (/account/welcome):
what Google said waits ten minutes in `pending` meanwhile.  A session is 256
random bits in a cookie, kept here only as its SHA-256, as the quiz's board
keeps a browser's token.

Kept, in var/user.db: Google's id for the account, the address, the name, the
account's picture, when it was made and last used, which terms were agreed to
and when; each session's hash and times; and the features given to some
accounts and not to all (`allow`), set from the host's command line.  No IP
address, nothing about the device, and nothing joined to var/visits.db, whose
counter skips every address under /account (visits.py).  Deleting an account
removes all of it, the bytes too (secure_delete, and the journal emptied).

The picture (Tigran, 2026-11-18: "we will need the profile photo as well, of
course") is Google's `picture`, which the `profile` scope already gives.  The
server fetches a small copy of it as the reader signs in, keeps it with the
account, and hands it to the browser with who is signed in, as a data: URL: so
no page loads a picture from Google's servers, which would tell Google of the
visit, and the picture is there offline.  Not before the reader's tick: until
an account is made only the picture's address waits.  A picture that cannot be
fetched costs no sign-in.

Each site keeps its own (Tigran, 2026-11-18), as each keeps its own quiz
board.  The site's secrets are not in the repository nor in the unit: they are
var/account.toml on each host, mode 0600, as var/stats.passwd is, written by
`python -m ubsite.account setup`; with no such file a site has no accounts,
and every address under /account answers 404.  The file also names the site's
own origin, from which the callback's address, the Origin a POST must carry
and the cookies' names all come: never from the Host a request names.

`who()` is the one question everything else asks.  Google's session answers it
here; on the Fellowship's site the same question would go to Laravel's
endpoint (INTEGRATION.md, section 6).
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import pathlib
import re
import secrets
import sqlite3
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONF = pathlib.Path(os.environ.get("UB_ACCOUNT_CONF", ROOT / "var" / "account.toml"))
DB = pathlib.Path(os.environ.get("UB_USER_DB", ROOT / "var" / "user.db"))

# The terms a reader agrees to as an account is made, by the day they last
# changed: terms.html's, which tests/test_account.py holds this to.
TERMS = "2026-11-18"

STATE_S = 600                    # from /account/login to Google and back
PENDING_S = 600                  # from Google's answer to the reader's tick
SESSION_S = 180 * 86400          # about six months
RENEW_S = 86400                  # a session used a day after it was last renewed is renewed
TIMEOUT_S = 10                   # Google's token endpoint

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
SCOPE = "openid email profile"   # the least there is: who, and nothing of theirs
# Where Google keeps an account's picture: the only addresses the server will
# fetch one from, whatever a token says.
PICTURES = r"https://lh[0-9]\.googleusercontent\.com/[\w./=~-]+"
PHOTO_PX = 96                    # asked of Google: three times the size it is shown at
PHOTO_MAX = 64 * 1024            # a picture larger than this is not kept
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL                -- 'id': made with the file, so that a browser knows one database from another
);
CREATE TABLE IF NOT EXISTS user (
  id INTEGER PRIMARY KEY,
  provider TEXT NOT NULL,            -- 'google'
  subject TEXT NOT NULL,             -- Google's sub: the account, whatever its address becomes
  email TEXT NOT NULL,               -- as Google last gave it
  name TEXT NOT NULL,
  made TEXT NOT NULL,                -- the server's time, UTC
  seen TEXT NOT NULL,
  terms TEXT NOT NULL,               -- the terms agreed to, by their day (TERMS)
  agreed TEXT NOT NULL,              -- and when
  photo BLOB,                        -- the account's picture, a small copy fetched at sign-in; NULL for none
  photo_type TEXT,                   -- image/jpeg, ...
  UNIQUE (provider, subject)
);
CREATE TABLE IF NOT EXISTS session (
  token TEXT PRIMARY KEY,            -- SHA-256 of the cookie's value, hex
  user_id INTEGER NOT NULL REFERENCES user(id),
  made TEXT NOT NULL,
  renewed INTEGER NOT NULL,          -- unix seconds
  expires INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS session_user ON session(user_id);
-- What Google said of an account not made yet, until its reader has agreed to
-- the terms or ten minutes have passed.
CREATE TABLE IF NOT EXISTS pending (
  token TEXT PRIMARY KEY,            -- SHA-256 of the cookie's value, hex
  subject TEXT NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  expires INTEGER NOT NULL,
  picture TEXT NOT NULL DEFAULT ''   -- where the account's picture is, fetched once there is an account
);
-- What some accounts may use and others not: given by address from the host's
-- command line, and bound to the account itself the first time that address
-- signs in, so that it follows the account and not an address that changes hands.
CREATE TABLE IF NOT EXISTS allow (
  email TEXT NOT NULL,               -- lower case
  feature TEXT NOT NULL,
  user_id INTEGER REFERENCES user(id),
  at TEXT NOT NULL,
  PRIMARY KEY (email, feature)
);
"""
RE_ORIGIN = re.compile(r"https://[a-z0-9.-]+(?::\d+)?|http://localhost(?::\d+)?")
# Where a reader goes on to after signing in: a path of this site's.  One /,
# then neither / nor \, which a browser reads as another host; no backslash or
# control character anywhere.
RE_NEXT = re.compile(r"/(?![/\\])[^\\\x00-\x1f\x7f]{0,500}")
RE_FEATURE = re.compile(r"[a-z][a-z0-9-]{0,31}")


class Refused(Exception):
    """What a request asks that will not be done: status, and why."""

    def __init__(self, status: int, why: str):
        super().__init__(why)
        self.status, self.why = status, why


class Config:
    """var/account.toml: the site's own origin and Google's client."""

    def __init__(self, origin: str, client_id: str, client_secret: str,
                 auth_uri: str = AUTH_URI, token_uri: str = TOKEN_URI, issuers: tuple = ISSUERS,
                 pictures: str = PICTURES):
        if not RE_ORIGIN.fullmatch(origin):
            raise ValueError(f"account.toml: origin = {origin!r}: https://host, or http://localhost[:port]")
        if not client_id or not client_secret:
            raise ValueError("account.toml: [google] client_id and client_secret")
        self.origin, self.client_id, self.client_secret = origin, client_id, client_secret
        self.auth_uri, self.token_uri, self.issuers = auth_uri, token_uri, tuple(issuers)
        self.pictures = re.compile(pictures)

    @property
    def secure(self) -> bool:
        return self.origin.startswith("https://")

    @property
    def callback(self) -> str:
        return self.origin + "/account/callback"

    def cookie(self, name: str) -> str:
        """A cookie's name: __Host- on https, which a browser takes only from
        this host itself, over TLS, for the whole of it: neither a page of a
        neighbouring host nor anyone on the network can plant one."""
        return ("__Host-" if self.secure else "") + name


_conf: tuple[tuple, Config | None] | None = None


def config(path: pathlib.Path | None = None) -> Config | None:
    """The site's accounts as set up, or None where they are not: read again
    when the file changes, so that a host need not be restarted for it."""
    global _conf
    path = pathlib.Path(path or CONF)
    try:
        stamp = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return None
    if _conf is None or _conf[0] != stamp:
        with open(path, "rb") as fh:
            d = tomllib.load(fh)
        g = d.get("google", {})
        # auth_uri, token_uri, issuers and pictures are Google's unless the
        # file says otherwise, which only a test's stand-in for Google does.
        _conf = (stamp, Config(d.get("origin", ""), g.get("client_id", ""), g.get("client_secret", ""),
                               g.get("auth_uri", AUTH_URI), g.get("token_uri", TOKEN_URI),
                               tuple(g.get("issuers", ISSUERS)), g.get("pictures", PICTURES)))
    return _conf[1]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def local(path) -> str:
    """`next` as it may be followed: a path of this site's, or the home page."""
    return path if isinstance(path, str) and RE_NEXT.fullmatch(path) else "/"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def fetch_token(conf: Config, code: str, verifier: str) -> dict:
    """Google's answer to the code, from its token endpoint: the one thing
    this server asks of another.  A test puts its own in this function's place."""
    body = urllib.parse.urlencode({
        "code": code, "client_id": conf.client_id, "client_secret": conf.client_secret,
        "redirect_uri": conf.callback, "grant_type": "authorization_code", "code_verifier": verifier,
    }).encode("ascii")
    req = urllib.request.Request(conf.token_uri, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            got = json.loads(resp.read(1 << 20))
    except (OSError, ValueError) as e:        # urllib's errors are OSErrors: refused, timed out, a 4xx
        raise Refused(502, "google") from e
    if not isinstance(got, dict):
        raise Refused(502, "google")
    return got


def fetch_photo(conf: Config, url: str) -> tuple[bytes, str] | None:
    """A small copy of an account's picture, (its bytes, its type), from
    where Google keeps it and nowhere else; None for none, or for any reason
    it cannot be had: a picture costs no sign-in.  A test puts its own in this
    function's place."""
    if not url or not conf.pictures.fullmatch(url):
        return None
    if "googleusercontent.com/" in url:
        # Google sizes a picture by the end of its address: =s96-c, a square of 96.
        url = re.sub(r"=s\d+(-c)?$", "", url) + f"=s{PHOTO_PX}-c"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "image/*"}), timeout=5) as resp:
            kind = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = resp.read(PHOTO_MAX + 1)
    except (OSError, ValueError):
        return None
    if kind not in PHOTO_TYPES or not data or len(data) > PHOTO_MAX:
        return None
    return data, kind


def claims_of(conf: Config, got: dict, nonce: str) -> tuple[str, str, str, str]:
    """(sub, email, name, where the picture is) from Google's answer, or
    Refused.  The token came straight from Google over TLS, so its signature
    is not checked; what it says is: who issued it, for whom, until when, in
    answer to which request, and whether the address is the account's own."""
    try:
        head, payload, _sig = got["id_token"].split(".")
        c = json.loads(_unb64(payload))
    except (KeyError, AttributeError, ValueError):
        raise Refused(502, "google")
    if not isinstance(c, dict):
        raise Refused(502, "google")
    exp = c.get("exp")
    if (c.get("iss") not in conf.issuers or c.get("aud") != conf.client_id
            or not isinstance(exp, (int, float)) or exp <= time.time()
            or not nonce or c.get("nonce") != nonce):
        raise Refused(400, "claims")
    sub, email, name = c.get("sub"), c.get("email"), c.get("name")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or "@" not in email:
        raise Refused(400, "claims")
    if c.get("email_verified") not in (True, "true"):
        raise Refused(403, "unverified")
    if not isinstance(name, str) or not name.strip():
        name = email.split("@")[0]
    picture = c.get("picture")
    if not isinstance(picture, str) or len(picture) > 2000 or not conf.pictures.fullmatch(picture):
        picture = ""
    return sub[:255], email[:320], " ".join(name.split())[:200], picture


class Accounts:
    def __init__(self, path: pathlib.Path | None = None):
        self.path = pathlib.Path(path or DB)

    def _con(self, write: bool) -> sqlite3.Connection | None:
        """A connection; None if nothing was ever written and this is only a
        read.  The file is made by the first sign-in."""
        if not write and not self.path.exists():
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(f"file:{self.path}", uri=True, timeout=5, isolation_level=None)
        # A deleted row's bytes overwritten, not left in a free page (as
        # visits.py does for the day's salt): an account deleted is gone.
        con.execute("PRAGMA secure_delete = ON")
        con.executescript(SCHEMA)
        # A file made before a column was: the column added, its rows as they were.
        for table, col, kind in (("user", "photo", "BLOB"), ("user", "photo_type", "TEXT"),
                                 ("pending", "picture", "TEXT NOT NULL DEFAULT ''")):
            if col not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
        con.execute("INSERT OR IGNORE INTO meta VALUES ('id', ?)", (secrets.token_hex(8),))
        return con

    # ---- signing in -------------------------------------------------------------
    def begin(self, conf: Config, nxt: str) -> tuple[str, str]:
        """(Google's address to send the reader to, the cookie that remembers
        what was asked): a state against a forged answer, a nonce against a
        token replayed, and PKCE's verifier, whose hash Google is given and
        which it wants back with the code."""
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        kept = _b64(json.dumps({"s": state, "n": nonce, "v": verifier, "x": local(nxt),
                                "t": int(time.time())}).encode("utf-8"))
        url = conf.auth_uri + "?" + urllib.parse.urlencode({
            "client_id": conf.client_id, "redirect_uri": conf.callback, "response_type": "code",
            "scope": SCOPE, "state": state, "nonce": nonce,
            "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
            "code_challenge_method": "S256",
            # Google asks which account every time, so that no other site can
            # sign a reader in by sending them to /account/login.
            "prompt": "select_account",
        })
        return url, kept

    def finish(self, conf: Config, kept: str, state: str, code: str) -> tuple[str, str, str]:
        """Google's answer taken: ('in', a session's token, next) for an
        account there is, ('new', a pending token, next) for one to be made
        once its reader agrees to the terms; or Refused."""
        try:
            k = json.loads(_unb64(kept))
            want, nonce, verifier, nxt, at = k["s"], k["n"], k["v"], k["x"], k["t"]
        except (ValueError, KeyError, TypeError):
            raise Refused(400, "state")
        if (not state or not isinstance(want, str) or not secrets.compare_digest(state, want)
                or not isinstance(at, int) or time.time() - at > STATE_S):
            raise Refused(400, "state")
        sub, email, name, picture = claims_of(conf, fetch_token(conf, code, verifier), nonce)
        # The picture of an account there is, fetched before the database is
        # held: Google may be slow.  Of one not made yet, only its address is
        # kept, until its reader has agreed (agree()).
        photo = fetch_photo(conf, picture) if self._known(sub) else None
        con = self._con(True)
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM pending WHERE expires <= ?", (int(time.time()),))
            con.execute("DELETE FROM session WHERE expires <= ?", (int(time.time()),))
            row = con.execute("SELECT id FROM user WHERE provider = 'google' AND subject = ?", (sub,)).fetchone()
            if row:
                con.execute("UPDATE user SET email = ?, name = ?, seen = ? WHERE id = ?", (email, name, now(), row[0]))
                # As Google now has it; with none there, or none to be had now,
                # the one kept before stays.
                if photo:
                    con.execute("UPDATE user SET photo = ?, photo_type = ? WHERE id = ?", (photo[0], photo[1], row[0]))
                token = self._session(con, row[0], email)
                kind = "in"
            else:
                token = secrets.token_urlsafe(32)
                con.execute("INSERT INTO pending (token, subject, email, name, expires, picture) VALUES (?,?,?,?,?,?)",
                            (digest(token), sub, email, name, int(time.time()) + PENDING_S, picture))
                kind = "new"
            con.execute("COMMIT")
        finally:
            con.close()
        return kind, token, local(nxt)

    def _known(self, sub: str) -> bool:
        con = self._con(False)
        if con is None:
            return False
        try:
            return con.execute("SELECT 1 FROM user WHERE provider = 'google' AND subject = ?", (sub,)).fetchone() is not None
        finally:
            con.close()

    def _session(self, con, user_id: int, email: str) -> str:
        """A session for this account, and whatever was given to its address
        bound to it."""
        token, t = secrets.token_urlsafe(32), int(time.time())
        con.execute("INSERT INTO session VALUES (?,?,?,?,?)", (digest(token), user_id, now(), t, t + SESSION_S))
        con.execute("UPDATE allow SET user_id = ? WHERE email = ? AND user_id IS NULL", (user_id, email.lower()))
        return token

    def pending(self, token: str) -> dict | None:
        """Whose account is waiting for its reader's tick: {name, email}."""
        con = self._con(False) if token else None
        if con is None:
            return None
        try:
            row = con.execute("SELECT name, email FROM pending WHERE token = ? AND expires > ?",
                              (digest(token), int(time.time()))).fetchone()
        finally:
            con.close()
        return {"name": row[0], "email": row[1]} if row else None

    def agree(self, conf: Config, token: str) -> str:
        """The account made, its reader having agreed to the terms: a session's
        token.  Its picture is fetched now, and not before."""
        con = self._con(False) if token else None
        if con is None:
            raise Refused(404, "unknown")
        try:
            row = con.execute("SELECT picture FROM pending WHERE token = ? AND expires > ?",
                              (digest(token), int(time.time()))).fetchone()
        finally:
            con.close()
        if row is None:
            raise Refused(404, "unknown")
        photo = fetch_photo(conf, row[0]) or (None, None)
        con = self._con(True)
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT subject, email, name FROM pending WHERE token = ? AND expires > ?",
                              (digest(token), int(time.time()))).fetchone()
            if row is None:
                con.execute("ROLLBACK")
                raise Refused(404, "unknown")
            sub, email, name = row
            con.execute("DELETE FROM pending WHERE token = ? OR subject = ?", (digest(token), sub))
            # Two tabs may both have come back from Google: the second finds the account made.
            got = con.execute("SELECT id FROM user WHERE provider = 'google' AND subject = ?", (sub,)).fetchone()
            user = got[0] if got else con.execute(
                "INSERT INTO user (provider, subject, email, name, made, seen, terms, agreed, photo, photo_type)"
                " VALUES ('google',?,?,?,?,?,?,?,?,?)",
                (sub, email, name, now(), now(), TERMS, now(), photo[0], photo[1])).lastrowid
            session = self._session(con, user, email)
            con.execute("COMMIT")
        finally:
            con.close()
        return session

    # ---- who is asking ----------------------------------------------------------
    def who(self, token: str, renew: bool = False) -> dict | None:
        """The account a session's cookie names: {id, email, name, photo,
        features, db}, and `renewed` where the session was given its six
        months again, which /account/me asks for, the cookie then being sent
        again.  The picture is a data: URL, or '' for none: the browser keeps
        it with who is signed in, and no page asks anyone for it."""
        con = self._con(False) if token else None
        if con is None:
            return None
        try:
            t, h = int(time.time()), digest(token)
            row = con.execute("SELECT u.id, u.email, u.name, s.renewed, u.photo, u.photo_type FROM session s"
                              " JOIN user u ON u.id = s.user_id WHERE s.token = ? AND s.expires > ?", (h, t)).fetchone()
            if row is None:
                return None
            photo = (f"data:{row[5]};base64,{base64.b64encode(row[4]).decode('ascii')}"
                     if row[4] and row[5] in PHOTO_TYPES else "")
            me = {"id": row[0], "email": row[1], "name": row[2], "photo": photo, "renewed": False,
                  "features": [f for (f,) in con.execute("SELECT feature FROM allow WHERE user_id = ? ORDER BY feature",
                                                         (row[0],))],
                  "db": con.execute("SELECT value FROM meta WHERE key = 'id'").fetchone()[0]}
            if renew and t - row[3] >= RENEW_S:
                con.execute("UPDATE session SET renewed = ?, expires = ? WHERE token = ?", (t, t + SESSION_S, h))
                con.execute("UPDATE user SET seen = ? WHERE id = ?", (now(), row[0]))
                me["renewed"] = True
            return me
        finally:
            con.close()

    def sign_out(self, token: str) -> None:
        con = self._con(False) if token else None
        if con is None:
            return
        try:
            con.execute("DELETE FROM session WHERE token = ?", (digest(token),))
        finally:
            con.close()

    def delete(self, token: str, email) -> None:
        """The account a session names, and everything kept for it, gone: its
        reader says which by its address, so that it is not done by a slip."""
        me = self.who(token)
        if me is None:
            raise Refused(401, "signed out")
        if not isinstance(email, str) or email.strip().lower() != me["email"].lower():
            raise Refused(400, "address")
        self._remove(me["id"])

    def _remove(self, user_id: int) -> None:
        con = self._con(True)
        try:
            con.execute("BEGIN IMMEDIATE")
            for table, col in (("session", "user_id"), ("allow", "user_id"), ("user", "id")):
                con.execute(f"DELETE FROM {table} WHERE {col} = ?", (user_id,))
            con.execute("COMMIT")
            # And from the journal, where the rows written before still stand.
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()

    # ---- the host's command line --------------------------------------------------
    def users(self) -> list[dict]:
        con = self._con(False)
        if con is None:
            return []
        try:
            return [{"id": r[0], "email": r[1], "name": r[2], "made": r[3], "seen": r[4],
                     "features": [f for (f,) in con.execute("SELECT feature FROM allow WHERE user_id = ? ORDER BY feature",
                                                            (r[0],))]}
                    for r in con.execute("SELECT id, email, name, made, seen FROM user ORDER BY id").fetchall()]
        finally:
            con.close()

    def grants(self) -> list[tuple[str, str, int | None]]:
        con = self._con(False)
        if con is None:
            return []
        try:
            return con.execute("SELECT email, feature, user_id FROM allow ORDER BY email, feature").fetchall()
        finally:
            con.close()

    def grant(self, email: str, feature: str) -> None:
        email = email.strip().lower()
        if "@" not in email or not RE_FEATURE.fullmatch(feature):
            raise ValueError("an address, and a feature in small letters")
        con = self._con(True)
        try:
            con.execute("BEGIN IMMEDIATE")
            user = con.execute("SELECT id FROM user WHERE LOWER(email) = ?", (email,)).fetchone()
            con.execute("INSERT OR REPLACE INTO allow VALUES (?,?,?,?)",
                        (email, feature, user[0] if user else None, now()))
            con.execute("COMMIT")
        finally:
            con.close()

    def revoke(self, email: str, feature: str) -> bool:
        con = self._con(False)
        if con is None:
            return False
        try:
            return con.execute("DELETE FROM allow WHERE email = ? AND feature = ?",
                               (email.strip().lower(), feature)).rowcount == 1
        finally:
            con.close()

    def remove(self, email: str) -> bool:
        con = self._con(False)
        if con is None:
            return False
        try:
            row = con.execute("SELECT id FROM user WHERE LOWER(email) = ?", (email.strip().lower(),)).fetchone()
        finally:
            con.close()
        if row is None:
            return False
        self._remove(row[0])
        return True


_accounts: Accounts | None = None


def accounts() -> Accounts:
    global _accounts
    if _accounts is None:
        _accounts = Accounts()
    return _accounts


def setup(path: pathlib.Path) -> None:
    """Ask for the site's origin and Google's client, and write them where
    only this user can read them: var/, which no deploy touches."""
    print("Signing in with Google, for this host.  From Google Cloud's console, Google Auth Platform, Clients:")
    origin = input("  this site's own origin (https://ubsite.example.org, or http://localhost:8130): ").strip().rstrip("/")
    client_id = input("  client ID: ").strip()
    client_secret = getpass.getpass("  client secret (not shown): ").strip()
    conf = Config(origin, client_id, client_secret)        # or ValueError, nothing written
    text = (f"# Written by `python -m ubsite.account setup`, {now()}.  Not in the repository:\n"
            f"# the client's secret is this host's alone.\n"
            f"origin = {json.dumps(conf.origin)}\n\n[google]\n"
            f"client_id = {json.dumps(conf.client_id)}\nclient_secret = {json.dumps(conf.client_secret)}\n")
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(target, 0o600)
    print(f"written: {target}\nIn Google's console the client's redirect address must be exactly {conf.callback}")


def main(argv: list[str]) -> int:
    a = accounts()
    if argv[:1] == ["setup"] and len(argv) == 1:
        setup(CONF)
    elif argv[:1] == ["list"] and len(argv) == 1:
        conf = config()
        print(f"{CONF}: " + (f"{conf.origin}, callback {conf.callback}" if conf else "none, so this site has no accounts"))
        for u in a.users():
            print(f"{u['id']:5}  {u['email']:40} {u['name']:30} made {u['made']}  seen {u['seen']}  {' '.join(u['features'])}")
        for email, feature, user in a.grants():
            if user is None:
                print(f"       {email:40} {feature}  (has not signed in)")
    elif argv[:1] == ["grant"] and len(argv) == 3:
        a.grant(argv[1], argv[2])
    elif argv[:1] == ["revoke"] and len(argv) == 3:
        if not a.revoke(argv[1], argv[2]):
            print("no such grant", file=sys.stderr)
            return 1
    elif argv[:1] == ["remove"] and len(argv) == 2:
        if not a.remove(argv[1]):
            print("no such account", file=sys.stderr)
            return 1
    else:
        print("usage: python -m ubsite.account setup | list | grant ADDRESS FEATURE | revoke ADDRESS FEATURE"
              " | remove ADDRESS", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
