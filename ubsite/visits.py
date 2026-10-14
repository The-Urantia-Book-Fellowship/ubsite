"""The visit counter: who reads the site, from where, and what they read.

Server-side, so a page carries nothing for it: no script, no cookie, no consent
banner.  `Counter` is a pure ASGI middleware.  After each response it puts one
tuple on a queue, which costs a few microseconds and does no I/O.  A thread in
each worker (`Recorder`) drains the queue into var/visits.db every couple of
seconds, and that is where the work is done:

  - the address is looked up in DB-IP's City Lite (`make geoip`) for country,
    region and city;
  - it is hashed with the day's salt into a visitor number, which counts people
    within a day and cannot follow them from one day to the next;
  - and then it is dropped.  No IP address is written anywhere (visits.sql).

ubsite/stats.py reads what this writes, for the private /stats page.  Analytics
must never cost a reader a page, so every failure here is logged once and
otherwise ignored.  UB_VISITS=off turns the counter off.
"""

from __future__ import annotations

import atexit
import datetime
import hashlib
import logging
import os
import pathlib
import queue
import re
import sqlite3
import threading
import time
from urllib.parse import urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
VISITS = ROOT / "var" / "visits.db"
GEOIP = ROOT / "var" / "geoip" / "dbip-city-lite.mmdb"
SCHEMA = pathlib.Path(__file__).with_name("visits.sql")

OFF = os.environ.get("UB_VISITS", "").lower() in ("off", "0", "no")
# Pages that are not reading: what deploy.sh polls, the icons, the report itself,
# and what Work offline asks for (the worker, the app manifest; /offline/ below).
SKIP = frozenset({"/healthz", "/favicon.ico", "/apple-touch-icon.png", "/stats",
                  "/sw.js", "/manifest.webmanifest"})
# Set by /stats on the owner's browser, so that their own reading is not counted.
OWNER = re.compile(rb"(?:^|;\s*)ub_me=1(?:;|$)")
VIA = frozenset({"swap", "next"})              # listen.js's X-UB-Fetch

log = logging.getLogger("ubsite.visits")


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def visitor(salt: bytes, ip: str, ua: str) -> int:
    """The day's number for one address and browser: 8 bytes of a salted hash."""
    h = hashlib.sha256(salt + ip.encode() + b"\0" + ua.encode()).digest()
    return int.from_bytes(h[:8], "big", signed=True)


def referrer(ref: str, host: str) -> str | None:
    """Where a page was reached from, without its query string or fragment.

    Those carry tracking tokens (fbclid, gclid) and, from some sites, what the
    reader searched for there.  A link inside this site keeps only its path.
    """
    if not ref:
        return None
    u = urlsplit(ref)
    if u.netloc == host:
        return (u.path or "/")[:300]
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))[:300]


def language(accept: str) -> str | None:
    """Accept-Language's first tag: "en-GB,en;q=0.9" is en-GB."""
    tag = accept.split(",")[0].split(";")[0].strip()
    return tag[:20] or None


class Recorder:
    """The queue, and the thread that drains it into visits.db.

    One per worker process.  The thread starts on the first request noted, so
    importing the app (a test, a script) starts nothing.
    """

    def __init__(self, path: pathlib.Path = VISITS, geoip: pathlib.Path = GEOIP,
                 interval: float = 2.0):
        self.path, self.geoip, self.interval = path, geoip, interval
        self.q: queue.SimpleQueue = queue.SimpleQueue()
        self.lock = threading.Lock()               # one drain at a time
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.con: sqlite3.Connection | None = None
        self.reader = None
        self.reader_mtime = None
        self.day: str | None = None
        self.salt = b""
        self.agents: dict[str, int] = {}
        self.places: dict[tuple, int] = {}
        self.warned: set[str] = set()

    def put(self, item: tuple) -> None:
        self.q.put(item)
        if self.thread is None:
            with self.lock:
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, name="visits", daemon=True)
                    self.thread.start()
                    atexit.register(self.close)

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            self.flush()

    def close(self) -> None:
        """Write what is queued.  Run at exit, so a restart loses nothing."""
        self.stop.set()
        self.flush()

    def flush(self) -> None:
        with self.lock:
            batch = []
            while True:
                try:
                    batch.append(self.q.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            try:
                self._write(batch)
            except Exception as exc:               # noqa: BLE001
                self.warn("write", f"visits not recorded: {exc!r}")
                self.con = None                    # reconnect next time

    def warn(self, key: str, msg: str) -> None:
        if key not in self.warned:
            self.warned.add(key)
            log.warning(msg)

    # ---- the writing ---------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self.con is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
            con.execute("PRAGMA journal_mode = WAL")
            con.execute("PRAGMA synchronous = NORMAL")
            con.executescript(SCHEMA.read_text())
            self.con, self.day, self.agents, self.places = con, None, {}, {}
        return self.con

    def _salt(self, con: sqlite3.Connection, day: str) -> bytes:
        """The day's salt, shared by both workers: whichever comes first makes it.

        Every other day's is deleted, so yesterday's numbers cannot be made
        again from an address and a browser.
        """
        if day != self.day:
            con.execute("INSERT OR IGNORE INTO salt VALUES (?, ?)", (day, os.urandom(16)))
            self.salt = con.execute("SELECT value FROM salt WHERE day=?", (day,)).fetchone()[0]
            self.day = day
        con.execute("DELETE FROM salt WHERE day < ?", (day,))
        return self.salt

    def _geo(self):
        try:
            mtime = self.geoip.stat().st_mtime_ns
        except OSError:
            self.warn("geoip", f"no {self.geoip}: places not recorded (make geoip)")
            self.reader = None
            return None
        if self.reader is None or mtime != self.reader_mtime:
            import maxminddb                       # only where a database is
            self.reader = maxminddb.open_database(str(self.geoip), maxminddb.MODE_AUTO)
            self.reader_mtime = mtime
        return self.reader

    def _place(self, con: sqlite3.Connection, ip: str) -> int | None:
        reader = self._geo()
        if reader is None or not ip:
            return None
        try:
            rec = reader.get(ip)
        except ValueError:                         # not an address
            return None
        country = (rec or {}).get("country") or {}
        if not country.get("iso_code"):
            return None
        subs = rec.get("subdivisions") or [{}]
        key = (country["iso_code"],
               subs[0].get("names", {}).get("en", ""),
               rec.get("city", {}).get("names", {}).get("en", ""))
        pid = self.places.get(key)
        if pid is None:
            con.execute("INSERT OR IGNORE INTO place(country, country_name, region, city)"
                        " VALUES (?, ?, ?, ?)",
                        (key[0], country.get("names", {}).get("en", key[0]), key[1], key[2]))
            pid = con.execute("SELECT id FROM place WHERE country=? AND region=? AND city=?",
                              key).fetchone()[0]
            if len(self.places) > 20000:
                self.places.clear()
            self.places[key] = pid
        return pid

    def _agent(self, con: sqlite3.Connection, ua: str) -> int:
        aid = self.agents.get(ua)
        if aid is None:
            con.execute("INSERT OR IGNORE INTO agent(ua) VALUES (?)", (ua,))
            aid = con.execute("SELECT id FROM agent WHERE ua=?", (ua,)).fetchone()[0]
            if len(self.agents) > 5000:
                self.agents.clear()
            self.agents[ua] = aid
        return aid

    def _write(self, batch: list[tuple]) -> None:
        con = self._connect()
        # The day is the day of writing, a second or two after the request: a
        # page read at 23:59:59 may count for the next day, and in return a
        # visitor number is never made with a salt already deleted.
        day = today()
        with con:
            salt = self._salt(con, day)
            views, browsers, listens, calls = [], [], [], []
            for item in batch:
                kind, ts, ip, ua = item[:4]
                who = visitor(salt, ip, ua)
                if kind == "browser":
                    browsers.append((day, who))
                elif kind == "listen":
                    voice, it = item[4:]
                    listens.append((day, who, voice, it, ts, self._place(con, ip)))
                elif kind == "api":
                    path, status, ref, host, api = item[4:]
                    since, version, whole = api or (None, None, None)
                    calls.append((ts, day, who, path, since, version,
                                  None if whole is None else int(whole), status,
                                  referrer(ref, host), self._agent(con, ua),
                                  self._place(con, ip)))
                else:
                    path, query, status, ref, host, accept, via, hits = item[4:]
                    views.append((ts, day, who, path, query or None, status, referrer(ref, host),
                                  self._agent(con, ua), self._place(con, ip),
                                  language(accept), via, hits))
            con.executemany(
                "INSERT INTO view(ts, day, visitor, path, query, status, referrer,"
                " agent_id, place_id, lang, via, hits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", views)
            con.executemany("INSERT OR IGNORE INTO browser VALUES (?, ?)", browsers)
            con.executemany("INSERT OR IGNORE INTO listen VALUES (?, ?, ?, ?, ?, ?)", listens)
            con.executemany(
                "INSERT INTO api_call(ts, day, visitor, path, since, version, whole, status,"
                " referrer, agent_id, place_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", calls)


RECORDER = Recorder()


class Counter:
    """ASGI middleware: note each GET for the recorder once it is answered.

    Pure ASGI rather than Starlette's BaseHTTPMiddleware, which would stand
    between a recording and the browser asking for a range of it.
    """

    def __init__(self, app, recorder: Recorder | None = None):
        self.app = app
        self.recorder = recorder or RECORDER

    async def __call__(self, scope, receive, send):
        if OFF or scope["type"] != "http" or scope["method"] != "GET":
            return await self.app(scope, receive, send)
        status = 500                               # if the app raises

        async def send_status(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        state = scope.setdefault("state", {})      # request.state: /search's hits
        try:
            await self.app(scope, receive, send_status)
        finally:
            try:
                self.note(scope, status, state)
            except Exception as exc:               # noqa: BLE001
                self.recorder.warn("note", f"visit not noted: {exc!r}")

    def note(self, scope, status: int, state: dict) -> None:
        path = scope["path"]
        if path.startswith("/static/"):
            if path != "/static/ub.css" or status not in (200, 304):
                return
            kind, rest = "browser", ()
        elif path.startswith("/audio/"):
            if status not in (200, 206):
                return
            _, _, voice, name = path.split("/", 3)
            kind, rest = "listen", (voice, name)
        elif path.startswith("/speech/"):
            if status != 200:
                return
            kind, rest = "listen", ("browser", path[len("/speech/"):])
        elif path in SKIP or path.startswith(("/rail/", "/offline/")):
            return                                 # /rail/N: a paper opened in the left rail;
                                                   # /offline/: a copy downloading (sw.js)
        elif path.startswith("/api/"):
            kind = "api"                           # another site's program, not a reader
        else:
            kind = "view"
        headers = dict(scope["headers"])
        if OWNER.search(headers.get(b"cookie", b"")):
            return
        client = scope.get("client")
        ip = client[0] if client else ""
        ua = headers.get(b"user-agent", b"").decode("latin-1")[:500]
        if kind == "view":
            via = headers.get(b"x-ub-fetch", b"").decode("latin-1")
            rest = (path[:300], scope.get("query_string", b"").decode("latin-1")[:500], status,
                    headers.get(b"referer", b"").decode("latin-1"),
                    headers.get(b"host", b"").decode("latin-1"),
                    headers.get(b"accept-language", b"").decode("latin-1"),
                    via if via in VIA else None, state.get("hits"))
        elif kind == "api":
            # (since, version, whole), as the route set them; None for a 404.
            rest = (path[:300], status, headers.get(b"referer", b"").decode("latin-1"),
                    headers.get(b"host", b"").decode("latin-1"), state.get("api"))
        self.recorder.put((kind, int(time.time()), ip, ua, *rest))
