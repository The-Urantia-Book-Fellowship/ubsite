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


def select(path: str, query: str = "", headers: dict | None = None
           ) -> tuple[int, dict, dict | None]:
    """/api/v1/paragraphs/<sel> or /api/v1/papers/<sel>, `path` from paragraphs/ on."""
    status, hs, body = call(f"/api/v1/{path}", query, headers)
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
        for path in ("/api/v1/nope", "/api/v2/text", "/api/v1/text/101:4.2",
                     "/api/v1/paragraphs", "/api/v1/papers/"):
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
        self.assertEqual((about["links"]["paragraphs"], about["links"]["papers"]),
                         ("https://ubsite.test/api/v1/paragraphs/{refs}",
                          "https://ubsite.test/api/v1/papers/{numbers}"))
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

    def test_what_stands_before_a_paragraph(self):
        """The separators and the 1955 groups, on every record (version 5)."""
        ps = self.reply["paragraphs"]
        self.assertTrue(all("separator_before" in x and isinstance(x["group_before"], bool)
                            for x in ps))
        five, three = "* * * * *", "* * *"
        self.assertEqual({x["ref"]: x["separator_before"] for x in ps if x["separator_before"]}, {
            "31:10.22": five, "56:10.23": five, "119:8.9": five,
            "120:3.12": three, "134:6.14": three,
            **{f"144:5.{n}": three for n in (11, 24, 36, 51, 69, 82)}})
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        groups = {r for (r,) in con.execute("SELECT ref FROM paragraph WHERE gap_before > 0")}
        self.assertEqual({x["ref"] for x in ps if x["group_before"]}, groups)
        self.assertIn("101:1.2", groups)
        page = html.unescape(call("/api")[2].decode())
        for field in ("separator_before", "group_before", "kind"):
            self.assertIn(f"<code>{field}</code>", page)

    def test_the_kind_of_paragraph(self):
        """Prose, a line of verse, or the one heading within the text (version 6)."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        verse = {r for (r,) in con.execute("SELECT ref FROM paragraph WHERE src <> 'vs'")}
        self.assertEqual(len(verse), 144)
        kinds = {x["ref"]: x["kind"] for x in self.reply["paragraphs"]}
        self.assertEqual({r for r, k in kinds.items() if k == "heading"}, {"0:12.10"})
        self.assertEqual({r for r, k in kinds.items() if k == "verse"}, verse)
        self.assertEqual(set(kinds.values()), {"prose", "verse", "heading"})
        self.assertEqual((kinds["144:5.11"], kinds["48:6.9"], kinds["101:1.2"]),
                         ("verse", "verse", "prose"))

    def test_the_1955_readings(self):
        """An empty marker where each stands, its reading in readings_1955 (version 8)."""
        ps = self.reply["paragraphs"]
        mark = '<span class="v1955"></span>'
        self.assertTrue(all(isinstance(x["readings_1955"], list) for x in ps))
        self.assertEqual(sum(x["html"].count(mark) for x in ps), 180)
        self.assertEqual(sum(len(x["readings_1955"]) for x in ps), 180)
        self.assertEqual(sum(1 for x in ps if x["readings_1955"]), 172)
        self.assertTrue(all(x["html"].count(mark) == len(x["readings_1955"]) for x in ps))
        by = {x["ref"]: x for x in ps}
        self.assertEqual(by["134:3.3"]["readings_1955"], ["10:00", "3:00", "8:00"])
        self.assertEqual(by["112:1.7"]["readings_1955"], ["<em>Vertical</em> depth"])
        self.assertTrue(by["112:1.7"]["html"].startswith(
            '<span class="mark">2.</span> <em>Vertical depth</em>' + mark + " embraces"))
        self.assertEqual(by["101:1.2"]["readings_1955"], [])
        page = html.unescape(call("/api")[2].decode())
        self.assertIn("<code>readings_1955</code>", page)
        self.assertIn('"readings_1955": [\n  "<em>Vertical</em> depth"', page)

    def test_the_lines_set_in(self):
        """The Lord's Prayer's second lines (version 7)."""
        self.assertEqual({x["ref"] for x in self.reply["paragraphs"] if x["setoff"]},
                         {"144:3.4", "144:3.6", "144:3.8", "144:3.10"})
        self.assertTrue(all(isinstance(x["setoff"], bool) for x in self.reply["paragraphs"]))
        self.assertIn("<code>setoff</code>", html.unescape(call("/api")[2].decode()))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Select(Quiet):
    """A passage or a paper by reference: the stored records, and those around them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.current = con.execute("SELECT MAX(n) FROM text_version").fetchone()[0]
        cls.body = {(k, key): b for k, key, b in con.execute(
            "SELECT kind, key, body FROM text_unit")}
        cls.order = [r for (r,) in con.execute(
            "SELECT key FROM text_unit WHERE kind = 'paragraph' ORDER BY ord")]

    def refs(self, r: dict) -> list[str]:
        return [x["ref"] for x in r["paragraphs"]]

    def between(self, a: str, b: str) -> list[str]:
        return self.order[self.order.index(a):self.order.index(b) + 1]

    def bad(self, path: str, query: str = "") -> str:
        status, hs, r = select(path, query)
        self.assertEqual(status, 400, path)
        self.assertEqual(hs["access-control-allow-origin"], "*")
        self.assertEqual(r["docs"], "/api")
        return r["error"]

    def test_one_paragraph_and_what_it_stands_in(self):
        status, hs, r = select("paragraphs/101:4.2")
        self.assertEqual(status, 200)
        self.assertEqual((r["api"], r["version"]), (1, self.current))
        self.assertEqual(r["licence"]["text"], "public domain")
        for k in ("since", "full", "removed"):
            self.assertNotIn(k, r, "a selection is not a step in keeping a copy")
        self.assertEqual({k: [json.dumps(x, ensure_ascii=False, separators=(",", ":"))
                              for x in r[k]] for k in KINDS},
                         {"parts": [self.body[("part", "3")]],
                          "papers": [self.body[("paper", "101")]],
                          "sections": [self.body[("section", "101:4")]],
                          "paragraphs": [self.body[("paragraph", "101:4.2")]]})

    def test_ranges(self):
        r = select("paragraphs/101:4.2-7")[2]
        self.assertEqual(self.refs(r), [f"101:4.{n}" for n in range(2, 8)])
        self.assertEqual(select("paragraphs/101:4.2\u20137")[2], r, "an en dash will do")
        r = select("paragraphs/101:4.7-5.2")[2]
        self.assertEqual(self.refs(r), self.between("101:4.7", "101:5.2"))
        self.assertEqual([x["ref"] for x in r["sections"]], ["101:4", "101:5"])
        r = select("paragraphs/101:4.7-102:1.3")[2]
        self.assertEqual(self.refs(r), self.between("101:4.7", "102:1.3"))
        self.assertEqual([x["paper"] for x in r["papers"]], [101, 102])
        r = select("paragraphs/101:4-6")[2]
        self.assertEqual(self.refs(r), [x for x in self.order
                                        if x.split(".")[0] in ("101:4", "101:5", "101:6")])
        r = select("paragraphs/31:10-32:0")[2]
        self.assertEqual([x["part"] for x in r["parts"]], [1, 2], "across a part")

    def test_reading_order_each_once(self):
        r = select("paragraphs/101:4.2, 5:1.3,101:4")[2]
        self.assertEqual(self.refs(r), ["5:1.3"] + self.between("101:4.1", "101:4.10"))
        self.assertEqual([x["ref"] for x in r["sections"]], ["5:1", "101:4"])
        self.assertEqual([x["part"] for x in r["parts"]], [1, 3])

    def test_a_bare_number_is_not_a_paragraph(self):
        msg = self.bad("paragraphs/61:4.3,4")
        self.assertIn("61:4.3-4", msg)
        self.assertIn("/api/v1/papers/4", msg)
        self.assertIn("/api/v1/papers/4-5", self.bad("paragraphs/4-5"))

    def test_what_cannot_be_read_is_a_400(self):
        for sel in ("abc", "101:", "101:4.2-", "101:4.2,,5:1", "101:4.2,", "101:4.7-2",
                    "101:5-4", "101:4.2-101:5", "101:4-5.2", "1e3", "101:4.2.1",
                    ",".join(["1:1.1"] * 101)):
            self.bad(f"paragraphs/{sel}")
        self.assertIn("forwards", self.bad("paragraphs/101:4.7-2"))
        self.assertIn('"uf"', self.bad("paragraphs/101:4.2", "numbering=foundation"))

    def test_what_is_not_in_the_text_is_one_404(self):
        status, hs, r = select("paragraphs/101:4.99,197:0.1,1:1.1,139:10")
        self.assertEqual(status, 404)
        self.assertEqual(r["missing"], ["101:4.99", "197:0.1", "139:10"])
        self.assertEqual(hs["access-control-allow-origin"], "*")
        self.assertEqual(select("paragraphs/101:4.2-99")[2]["missing"], ["101:4.99"])

    def test_the_foundations_numbering(self):
        r = select("paragraphs/144:5.108", "numbering=uf")[2]
        self.assertEqual([(x["ref"], x["uf_ref"]) for x in r["paragraphs"]],
                         [("144:5.102", "144:5.108")])
        r = select("paragraphs/139:10", "numbering=uf")[2]
        self.assertEqual(self.refs(r), [f"139:9.{n}" for n in range(1, 12)])
        self.assertEqual([x["uf_ref"] for x in r["sections"]], ["139:10"])
        r = select("paragraphs/134:6.13-16", "numbering=uf")[2]
        self.assertEqual(self.refs(r), ["134:6.13", "134:6.14", "134:6.15"])
        status, _, r = select("paragraphs/134:6.14,139:9", "numbering=uf")
        self.assertEqual((status, r["missing"]), (404, ["134:6.14", "139:9"]),
                         "a separator the Foundation numbers, and its 139:9")
        self.assertEqual(select("paragraphs/101:4.2", "numbering=uf")[2],
                         select("paragraphs/101:4.2")[2], "where the two agree")

    def test_papers(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        r = select("papers/0")[2]
        self.assertEqual(r["parts"], [], "the Foreword is in no part")
        self.assertEqual(len(r["paragraphs"]), con.execute(
            "SELECT COUNT(*) FROM paragraph WHERE paper_n = 0").fetchone()[0])
        r = select("papers/105, 101,103-105")[2]
        self.assertEqual([x["paper"] for x in r["papers"]], [101, 103, 104, 105])
        self.assertEqual(self.refs(r), [p for (p,) in con.execute(
            "SELECT ref FROM paragraph WHERE paper_n IN (101, 103, 104, 105) ORDER BY ord")])
        self.assertEqual(len(r["sections"]), con.execute(
            "SELECT COUNT(*) FROM section WHERE paper_n IN (101, 103, 104, 105)").fetchone()[0])
        self.assertEqual(select("papers/101", "numbering=uf")[2], select("papers/101")[2])
        status, _, r = select("papers/197,0,200")
        self.assertEqual((status, r["missing"]), (404, ["197", "200"]))
        for sel in ("5-3", "abc", "1,,2", "-1"):
            self.bad(f"papers/{sel}")
        self.assertIn("/api/v1/paragraphs/101:4", self.bad("papers/101:4"))

    def test_etag(self):
        status, hs, _ = select("paragraphs/101:4.2-3")
        etag = hs["etag"]
        self.assertTrue(etag.startswith(f'W/"v{self.current}-r'))
        self.assertEqual(select("paragraphs/101:4.3,101:4.2", "", {"if-none-match": etag})[0],
                         304, "the same paragraphs however written")
        self.assertEqual(select("paragraphs/101:4.2-4", "", {"if-none-match": etag})[0], 200)
        self.assertEqual(select("papers/101", "", {"if-none-match": etag})[0], 200)

    def test_http(self):
        status, hs, body = call("/api/v1/papers/101", "", {"accept-encoding": "gzip"})
        self.assertEqual(hs["content-encoding"], "gzip")
        status, plain, raw = call("/api/v1/papers/101", "", {"accept-encoding": "identity"})
        self.assertNotIn("content-encoding", plain)
        self.assertEqual(json.loads(gzip.decompress(body)), json.loads(raw))
        self.assertEqual((plain["access-control-allow-origin"], plain["cache-control"]),
                         ("*", "no-cache"))
        for path in ("/api/v1/paragraphs/101:4.2", "/api/v1/papers/101"):
            status, hs, _ = call(path, method="OPTIONS")
            self.assertEqual(status, 204, path)

    def test_the_page_that_documents_it(self):
        page = html.unescape(call("/api")[2].decode())
        self.assertIn("GET https://ubsite.test/api/v1/paragraphs/101:4.2-7", page)
        self.assertIn("?numbering=uf", page)
        self.assertIn('"paragraphs": [ 6 records ]', page, "the reply to 101:4.7-5.2")
        self.assertIn('"parts": [ 1 record ]', page)


class Render(unittest.TestCase):
    def test_the_1955_marker_is_empty_and_round_trips(self):
        from build.render import render, strip_tags
        from build.versions import _Span
        out = render("Vertical depth embraces", [_Span(14, 14, "v1955"), _Span(0, 8, "em")])
        self.assertEqual(out, '<em>Vertical</em> depth<span class="v1955"></span> embraces')
        self.assertEqual(strip_tags(out), "Vertical depth embraces")


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
        cls.clear()

    @staticmethod
    def clear():
        for cache in (api._meta, api._text, api._book, api._select):
            cache.cache_clear()

    @classmethod
    def tearDownClass(cls):
        api.DB = cls.saved_db
        cls.clear()
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

    def test_a_passage_is_the_current_text(self):
        status, _, r = select("paragraphs/101:4.2")
        self.assertEqual(r["version"], self.after)
        self.assertTrue(r["paragraphs"][0]["html"].endswith(" (edited)"))
        status, _, r = select(f"paragraphs/{self.gone}")
        self.assertEqual((status, r["missing"]), (404, [self.gone]))


if __name__ == "__main__":
    unittest.main()
