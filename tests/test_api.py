"""The text API sends the build's records as they are, and its HTTP is what /api promises.

Driven through the app as ASGI (the venv has no HTTP client), with the visit
counter off.  The delta tests make a second database: a copy of var/ub.db with
one paragraph edited and the book's last paragraph removed, its text tables
rebuilt by build/versions.py under a copy of the ledger in a temporary
directory -- never data/text/ itself.  Skipped when var/ub.db has not been built.
"""

import asyncio
import gzip
import html
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "var" / "ub.db"

from ubsite import api, visits  # noqa: E402

KINDS = ("parts", "papers", "sections", "paragraphs")


def call(path: str, query: str = "", headers: dict | None = None,
         method: str = "GET") -> tuple[int, dict, bytes]:
    from ubsite.app import app
    hs = {"host": "ubsite.test", "user-agent": "TestSite/1.0", **(headers or {})}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": method, "scheme": "https", "path": path,
             "raw_path": path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": [(k.encode(), v.encode()) for k, v in hs.items()],
             "client": ("198.51.100.7", 40000), "server": ("ubsite.test", 443)}
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


def text(since: str = "", headers: dict | None = None) -> tuple[int, dict, dict | None]:
    status, hs, body = call("/api/v1/text", f"since={since}" if since else "", headers)
    if hs.get("content-encoding") == "gzip":
        body = gzip.decompress(body)
    return status, hs, json.loads(body) if body else None


class Quiet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_off, visits.OFF = visits.OFF, True

    @classmethod
    def tearDownClass(cls):
        visits.OFF = cls.saved_off


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Whole(Quiet):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.current = con.execute("SELECT MAX(n) FROM text_version").fetchone()[0]
        cls.bodies = {k: [b for (b,) in con.execute(
            "SELECT body FROM text_unit WHERE kind=? ORDER BY ord", (k[:-1],))] for k in KINDS}
        cls.status, cls.headers, cls.reply = text("0")

    def test_from_nothing_the_whole_text(self):
        self.assertEqual(self.status, 200)
        r = self.reply
        self.assertEqual((r["api"], r["version"], r["since"], r["full"]), (1, self.current, 0, True))
        self.assertEqual({k: len(r[k]) for k in KINDS},
                         {"parts": 4, "papers": 197, "sections": 1626, "paragraphs": 14586})
        self.assertEqual(r["removed"], {k: [] for k in KINDS})
        self.assertEqual(r["licence"]["text"], "public domain")

    def test_records_are_the_stored_ones_in_reading_order(self):
        for k in KINDS:
            self.assertEqual([json.dumps(x, ensure_ascii=False, separators=(",", ":"))
                              for x in self.reply[k]], self.bodies[k], k)

    def test_no_since_is_since_zero(self):
        self.assertEqual(text()[2], self.reply)

    def test_a_site_up_to_date_gets_nothing(self):
        status, _, r = text(str(self.current))
        self.assertEqual(status, 200)
        self.assertFalse(r["full"])
        self.assertEqual([len(r[k]) for k in KINDS], [0, 0, 0, 0])

    def test_a_version_never_made_gets_everything(self):
        status, _, r = text(str(self.current + 999))
        self.assertTrue(r["full"])
        self.assertEqual(r["since"], 0)
        self.assertEqual(len(r["paragraphs"]), 14586)

    def test_gzip_when_asked_and_the_same_json(self):
        status, hs, body = call("/api/v1/text", "since=0", {"accept-encoding": "gzip, br"})
        self.assertEqual(hs.get("content-encoding"), "gzip")
        self.assertEqual(json.loads(gzip.decompress(body)), self.reply)
        self.assertLess(len(body), 4_000_000)
        status, hs, body = call("/api/v1/text", "since=0", {"accept-encoding": "gzip;q=0"})
        self.assertNotIn("content-encoding", hs)
        self.assertEqual(json.loads(body), self.reply)

    def test_etag_round_trip(self):
        etag = self.headers["etag"]
        status, hs, body = call("/api/v1/text", "since=0", {"if-none-match": etag})
        self.assertEqual((status, body), (304, b""))
        self.assertEqual(hs["etag"], etag)
        status, _, _ = call("/api/v1/text", f"since={self.current}", {"if-none-match": etag})
        self.assertEqual(status, 200, "another reply's ETag must not match")

    def test_headers(self):
        hs = self.headers
        self.assertEqual(hs["access-control-allow-origin"], "*")
        self.assertIn("ETag", hs["access-control-expose-headers"])
        self.assertEqual(hs["cache-control"], "no-cache")
        self.assertEqual(hs["vary"], "Accept-Encoding")
        self.assertTrue(hs["content-type"].startswith("application/json"))

    def test_bad_since_is_a_json_400(self):
        for bad in ("abc", "-1", "1.5", "1e3"):
            status, hs, body = call("/api/v1/text", f"since={bad}")
            self.assertEqual(status, 400, bad)
            self.assertIn("error", json.loads(body))
            self.assertEqual(hs["access-control-allow-origin"], "*")

    def test_not_an_endpoint_is_a_json_404(self):
        for path in ("/api/v1/nope", "/api/v2/text", "/api/v1/text/101:4.2"):
            status, hs, body = call(path)
            self.assertEqual(status, 404, path)
            self.assertEqual(json.loads(body)["docs"], "/api")

    def test_preflight(self):
        status, hs, _ = call("/api/v1/text", method="OPTIONS")
        self.assertEqual(status, 204)
        self.assertIn("If-None-Match", hs["access-control-allow-headers"])

    def test_about_and_versions(self):
        status, hs, body = call("/api/v1")
        about = json.loads(gzip.decompress(body) if hs.get("content-encoding") else body)
        self.assertEqual(about["version"], self.current)
        self.assertEqual(about["counts"]["paragraphs"], 14586)
        self.assertTrue(about["links"]["text"].startswith("https://ubsite.test/api/v1/text"))
        status, hs, body = call("/api/v1/versions")
        vs = json.loads(body)["versions"]
        self.assertEqual([v["version"] for v in vs], list(range(1, self.current + 1)))

    def test_the_page_that_documents_it(self):
        status, hs, body = call("/api")
        self.assertEqual(status, 200)
        self.assertTrue(hs["content-type"].startswith("text/html"))
        page = html.unescape(body.decode())
        self.assertTrue('"uf_ref": "144:5.12"' in page, "the renumbered example is shown")
        self.assertTrue('BASE = "https://ubsite.test/api/v1"' in page, "the client names this site")
        self.assertTrue(f'"version": {self.current},' in page, "a reply is shown, with its version")
        self.assertTrue("mailto:tigran.aivazian@urantiabook.org" in page, "a contact")

    def test_a_section_page_carries_the_1955_pages(self):
        status, _, body = call("/101:4")
        self.assertEqual(status, 200)
        self.assertIn('id="101:4.2"><a class="num" href="/101:4.2">101:4.2</a>'
                      '<span class="pg" data-pg="1109.3"></span>', body.decode())

    def test_the_two_numberings(self):
        uf = {x["ref"]: x["uf_ref"] for x in self.reply["paragraphs"]}
        self.assertEqual(uf["134:6.14"], "134:6.15")
        self.assertEqual(uf["139:9.1"], "139:10.1")
        self.assertEqual(uf["144:5.102"], "144:5.108")
        self.assertEqual(uf["0:12.10"], "0:12.10")
        self.assertEqual(sum(1 for r, u in uf.items() if r != u), 106)
        pages = {x["ref"]: x["page_1955"] for x in self.reply["paragraphs"]}
        self.assertEqual(pages["101:4.2"], "1109.3")
        self.assertEqual(pages["144:5.11"], "1622.10")
        self.assertEqual(pages["0:12.10"], "16.7")
        secs = {x["ref"]: x["uf_ref"] for x in self.reply["sections"]}
        self.assertEqual(secs["139:9"], "139:10")

    def test_html_alone_and_it_strips_to_the_text(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        texts = dict(con.execute("SELECT ref, text FROM paragraph"))
        for x in self.reply["paragraphs"]:
            self.assertNotIn("text", x)
            # The recipe /api gives.
            self.assertEqual(html.unescape(re.sub(r"<[^>]+>", "", x["html"])), texts[x["ref"]])

    def test_html_carries_no_note_marker(self):
        self.assertFalse([x["ref"] for x in self.reply["paragraphs"] if 'class="fn"' in x["html"]])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Delta(Quiet):
    """One paragraph edited and one removed: version N+1 sends exactly those."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from build import versions
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        ledger = tmp / "text"
        shutil.copytree(ROOT / "data" / "text", ledger)
        copy = tmp / "ub.db"
        src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        cls.before = dst.execute("SELECT MAX(n) FROM text_version").fetchone()[0]
        cls.gone = dst.execute("SELECT ref FROM paragraph ORDER BY ord DESC LIMIT 1").fetchone()[0]
        dst.execute("UPDATE paragraph SET text = text || ' (edited)', html = html || ' (edited)'"
                    " WHERE ref = '101:4.2'")
        pid = dst.execute("SELECT id FROM paragraph WHERE ref = ?", (cls.gone,)).fetchone()[0]
        for t in ("uf_paragraph", "span"):
            dst.execute(f"DELETE FROM {t} WHERE paragraph_id = ?", (pid,))
        dst.execute("DELETE FROM paragraph WHERE id = ?", (pid,))
        for t in ("text_unit", "text_version", "text_removed"):
            dst.execute(f"DELETE FROM {t}")
        cls.after, pending = versions.assign(dst, {"commit": "test", "dirty": False}, ledger)
        dst.commit()
        dst.close()
        pending.append()
        cls.saved_db, api.DB = api.DB, copy
        api._meta.cache_clear()
        api._text.cache_clear()

    @classmethod
    def tearDownClass(cls):
        api.DB = cls.saved_db
        api._meta.cache_clear()
        api._text.cache_clear()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_a_new_version(self):
        self.assertEqual(self.after, self.before + 1)

    def test_the_site_one_behind_gets_exactly_the_change(self):
        status, _, r = text(str(self.before))
        self.assertEqual((r["version"], r["since"], r["full"]), (self.after, self.before, False))
        self.assertEqual([x["ref"] for x in r["paragraphs"]], ["101:4.2"])
        self.assertTrue(r["paragraphs"][0]["html"].endswith(" (edited)"))
        self.assertEqual([len(r[k]) for k in ("parts", "papers", "sections")], [0, 0, 0])
        self.assertEqual(r["removed"]["paragraphs"], [self.gone])

    def test_from_nothing_no_removals_listed(self):
        status, _, r = text("0")
        self.assertTrue(r["full"])
        self.assertEqual(len(r["paragraphs"]), 14585)
        self.assertNotIn(self.gone, {x["ref"] for x in r["paragraphs"]})
        self.assertEqual(r["removed"]["paragraphs"], [])

    def test_the_site_up_to_date_gets_nothing(self):
        status, _, r = text(str(self.after))
        self.assertEqual(r["removed"]["paragraphs"], [])
        self.assertEqual(len(r["paragraphs"]), 0)


if __name__ == "__main__":
    unittest.main()
