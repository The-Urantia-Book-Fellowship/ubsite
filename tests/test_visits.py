"""The visit counter records what it should, keeps no address, and never costs a page.

Driven through the app itself, as ASGI with no HTTP client (the venv has none),
into a visits.db in a temporary directory.  Page tests are skipped when var/ub.db
has not been built; the place of a view, when `make geoip` has not been run.
"""

import asyncio
import base64
import ipaddress
import pathlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ubsite import stats, visits  # noqa: E402

CHROME = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
          " Chrome/154.0.0.0 Safari/537.36")
# Documentation ranges (RFC 5737, RFC 3849): no database places them, and their
# bytes are distinctive enough to look for in a file.
QUIET4 = "198.51.100.213"
QUIET6 = "2001:db8:5eed:1::77"


def call(path: str, query: str = "", headers: dict | None = None,
         client: str = QUIET4) -> tuple[int, dict, bytes]:
    from ubsite.app import app
    hs = {"host": "ubsite.test", "user-agent": CHROME, **(headers or {})}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "https", "path": path,
             "raw_path": path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": [(k.encode(), v.encode()) for k, v in hs.items()],
             "client": (client, 40000), "server": ("ubsite.test", 443)}
    out = {"status": 0, "headers": {}, "body": b""}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        if m["type"] == "http.response.start":
            out["status"] = m["status"]
            out["headers"] = {k.decode(): v.decode() for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            out["body"] += m.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return out["status"], out["headers"], out["body"]


class Counted(unittest.TestCase):
    """Each test gets an empty visits.db, and the counter on whatever UB_VISITS says."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "visits.db"
        rec = visits.RECORDER
        self.saved = (visits.OFF, rec.path, rec.con, rec.day)
        visits.OFF = False
        rec.path, rec.con, rec.day = self.db, None, None
        rec.agents, rec.places = {}, {}
        # No writer thread: the tests flush by hand, so that nothing is written
        # behind their backs.  A thread already running is stopped.
        rec.stop.set()
        if rec.thread is not None and rec.thread is not threading.current_thread():
            rec.thread.join(5)
        rec.thread = threading.current_thread()

    def tearDown(self):
        rec = visits.RECORDER
        rec.flush()
        with rec.lock:
            if rec.con is not None:
                rec.con.close()
            visits.OFF, rec.path, rec.con, rec.day = self.saved
            rec.agents, rec.places = {}, {}
            rec.thread = None
            rec.stop.clear()
        self.tmp.cleanup()

    def rows(self, sql: str, *args) -> list[tuple]:
        visits.RECORDER.flush()
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()


@unittest.skipUnless((ROOT / "var" / "ub.db").exists(), "var/ub.db not built")
class Pages(Counted):
    def test_a_page_view_is_one_row(self):
        status, _, _ = call("/102:3", headers={
            "referer": "https://www.google.com/search?q=urantia&sclient=gws",
            "accept-language": "en-GB,en;q=0.9"})
        self.assertEqual(status, 200)
        call("/static/ub.css")
        (path, st, ref, lang, via), = self.rows(
            "SELECT path, status, referrer, lang, via FROM view")
        self.assertEqual((path, st, lang, via), ("/102:3", 200, "en-GB", None))
        self.assertEqual(ref, "https://www.google.com/search")   # no query string
        self.assertEqual(len(self.rows("SELECT * FROM browser")), 1)

    def test_a_link_inside_the_site_keeps_only_its_path(self):
        call("/102:3", headers={"referer": "https://ubsite.test/i/adoption?x=1#y"})
        self.assertEqual(self.rows("SELECT referrer FROM view"), [("/i/adoption",)])

    @unittest.skipUnless(visits.GEOIP.exists(), "no DB-IP database (make geoip)")
    def test_a_view_is_placed(self):
        call("/102:3", client="8.8.8.8")
        (country, city), = self.rows(
            "SELECT p.country, p.city FROM view v JOIN place p ON p.id = v.place_id")
        self.assertEqual(country, "US")
        self.assertTrue(city)

    def test_no_address_is_kept(self):
        for ip in (QUIET4, QUIET6, "8.8.8.8"):
            call("/102:3", client=ip)
            call("/static/ub.css", client=ip)
            call("/speech/102:3", client=ip)
        self.assertEqual(len(self.rows("SELECT * FROM view")), 3)
        files = [p for p in self.db.parent.iterdir() if p.name.startswith("visits.db")]
        blob = b"".join(p.read_bytes() for p in files)
        for ip in (QUIET4, QUIET6, "8.8.8.8"):
            self.assertNotIn(ip.encode(), blob)
        for ip in (QUIET4, QUIET6):
            self.assertNotIn(ipaddress.ip_address(ip).packed, blob)

    def test_search_records_what_it_found(self):
        call("/search", "q=xyzzyplugh")
        call("/search", "q=adjuster")
        got = dict(self.rows("SELECT query, hits FROM view"))
        self.assertEqual(got["q=xyzzyplugh"], 0)
        self.assertGreater(got["q=adjuster"], 0)

    def test_a_citation_searched_for_is_a_jump(self):
        call("/search", "q=101:4.2")
        self.assertEqual(self.rows("SELECT status, hits FROM view"), [(303, None)])

    def test_listening_fetches_say_so(self):
        call("/102:3", headers={"x-ub-fetch": "next"})
        call("/102:4", headers={"x-ub-fetch": "bogus"})
        self.assertEqual(self.rows("SELECT via FROM view ORDER BY id"), [("next",), (None,)])

    def test_what_is_not_reading_is_not_a_view(self):
        for path in ("/healthz", "/favicon.ico", "/static/ub.js", "/static/ub.css", "/stats",
                     "/rail/1"):
            call(path)
        self.assertEqual(self.rows("SELECT path FROM view"), [])

    def test_an_api_call_is_not_a_view(self):
        site = {"user-agent": "UPExplorer/1.0 (+https://upexplorer.example)"}
        call("/api/v1/text", "since=0", headers=site)
        (version,), = self.rows("SELECT MAX(version) FROM api_call")
        call("/api/v1/text", f"since={version}", headers=site)
        call("/api/v1/text", "since=abc", headers=site)
        call("/api/v1/nope", headers=site)
        call("/api/v1", headers=site)
        self.assertEqual(self.rows("SELECT path FROM view"), [])
        got = self.rows("SELECT a.ua, c.path, c.since, c.version, c.whole, c.status"
                        " FROM api_call c JOIN agent a ON a.id = c.agent_id ORDER BY c.id")
        ua = site["user-agent"]
        self.assertEqual(got, [(ua, "/api/v1/text", 0, version, 1, 200),
                               (ua, "/api/v1/text", version, version, 0, 200),
                               (ua, "/api/v1/text", None, None, None, 400),
                               (ua, "/api/v1/nope", None, None, None, 404),
                               (ua, "/api/v1", None, version, 0, 200)])

    def test_the_page_documenting_the_api_is_a_view(self):
        call("/api")
        self.assertEqual(self.rows("SELECT path FROM view"), [("/api",)])
        self.assertEqual(self.rows("SELECT * FROM api_call"), [])

    def test_the_browser_voice_is_a_listen(self):
        call("/speech/102:3")
        call("/speech/102:3")
        self.assertEqual(self.rows("SELECT voice, item FROM listen"), [("browser", "102:3")])

    def test_the_owner_is_not_counted(self):
        call("/102:3", headers={"cookie": "a=b; ub_me=1"})
        call("/102:3", headers={"cookie": "ub_me=0"})
        self.assertEqual(len(self.rows("SELECT * FROM view")), 1)

    def test_a_broken_counter_costs_no_page(self):
        visits.RECORDER.path = pathlib.Path("/proc/nonexistent/visits.db")
        status, _, _ = call("/102:3")
        self.assertEqual(status, 200)
        with self.assertLogs("ubsite.visits", "WARNING"):
            visits.RECORDER.warned.discard("write")
            visits.RECORDER.flush()                # logs, does not raise
        visits.RECORDER.path = self.db

    def test_off_is_off(self):
        visits.OFF = True
        call("/102:3")
        self.assertEqual(self.rows("SELECT name FROM sqlite_master"), [])


class Salt(Counted):
    def test_a_new_day_forgets_the_old_salt(self):
        rec = visits.RECORDER
        item = ("view", 0, QUIET4, CHROME, "/", "", 200, "", "h", "", None, None)
        with mock.patch.object(visits, "today", return_value="2026-01-01"):
            rec.put(item)
            first = self.rows("SELECT visitor FROM view")[0][0]
        with mock.patch.object(visits, "today", return_value="2026-01-02"):
            rec.put(item)
            second = self.rows("SELECT visitor FROM view ORDER BY id")[1][0]
            self.assertEqual(self.rows("SELECT day FROM salt"), [("2026-01-02",)])
        self.assertNotEqual(first, second)


class Agents(unittest.TestCase):
    def test_classify(self):
        cases = {
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)": ("bot", "Googlebot"),
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)": ("bot", "bingbot"),
            "curl/8.5.0": ("bot", "curl"),
            "": ("bot", "(none)"),
            "WhatsApp/2.23.20.0 A": ("preview", "WhatsApp"),
            "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)": ("preview", "Facebook"),
        }
        for ua, (kind, name) in cases.items():
            got = stats.classify(ua)
            self.assertEqual((got["kind"], got["name"]), (kind, name), ua)
        got = stats.classify(CHROME)
        self.assertEqual((got["kind"], got["browser"], got["os"], got["device"]),
                         ("person", "Chrome", "Linux", "Desktop"))
        iphone = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15"
                  " (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        self.assertEqual(stats.classify(iphone)["device"], "Phone")


@unittest.skipUnless((ROOT / "var" / "ub.db").exists(), "var/ub.db not built")
class StatsPage(Counted):
    def setUp(self):
        super().setUp()
        self.passwd = pathlib.Path(self.tmp.name) / "stats.passwd"
        self.patches = [mock.patch.object(stats, "PASSWD", self.passwd),
                        mock.patch.object(stats, "VISITS", self.db)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def auth(self, password: str) -> dict:
        return {"authorization": "Basic " + base64.b64encode(f"me:{password}".encode()).decode()}

    def test_no_password_no_page(self):
        self.assertEqual(call("/stats")[0], 404)

    def test_the_password_is_asked_for(self):
        self.passwd.write_text(stats.make_hash("right horse battery") + "\n")
        status, headers, _ = call("/stats")
        self.assertEqual(status, 401)
        self.assertIn("Basic", headers["www-authenticate"])
        self.assertEqual(call("/stats", headers=self.auth("wrong"))[0], 401)

    def test_the_page_with_the_password(self):
        self.passwd.write_text(stats.make_hash("right horse battery") + "\n")
        call("/102:3", client="8.8.8.8")
        call("/static/ub.css", client="8.8.8.8")
        call("/search", "q=xyzzyplugh", client="8.8.8.8")
        call("/102:3", headers={"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"})
        call("/api/v1/text", "since=0", headers={"user-agent": "UPExplorer/1.0 (+https://x)"},
             client="8.8.8.8")
        visits.RECORDER.flush()
        for days in ("1", "30", "all"):
            status, headers, body = call("/stats", f"days={days}", headers=self.auth("right horse battery"))
            self.assertEqual(status, 200, days)
            self.assertEqual(headers["cache-control"], "no-store")
            self.assertIn("ub_me=1", headers["set-cookie"])
            html = body.decode()
            self.assertIn("xyzzyplugh", html)                 # a search that found nothing
            self.assertIn("Googlebot", html)
            self.assertIn("UPExplorer/1.0", html)             # an API caller, by its name
        self.assertEqual(len(self.rows("SELECT * FROM view WHERE path = '/stats'")), 0)


if __name__ == "__main__":
    unittest.main()
