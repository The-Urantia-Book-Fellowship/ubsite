"""Work offline: the server's side, and how the copy cuts the site's pages.

The gate that holds every page of the copy to the server's is
`python -m offline check` (offline/check.py), which needs Node and takes half
a minute.  These are the quick facts beneath it: the routes the worker uses,
the scripts it loads named by their hashes, and pages cut and joined again.
Driven through the app as ASGI, with the visit counter off; skipped where
var/ub.db or var/offline/ has not been built.
"""

import gzip
import hashlib
import json
import os
import pathlib
import re
import sys
import unittest

os.environ["UB_VISITS"] = "off"
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "var" / "ub.db"
COPY = ROOT / "var" / "offline"


def call(path: str, query: str = "", headers: dict | None = None):
    from offline import site
    import asyncio
    hs = [(b"host", b"ubsite.test"), *((k.encode(), v.encode()) for k, v in (headers or {}).items())]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": hs, "client": ("198.51.100.7", 1), "server": ("ubsite.test", 443)}
    out = {"status": 0, "headers": {}, "body": b""}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        if m["type"] == "http.response.start":
            out["status"] = m["status"]
            out["headers"] = {k.decode().lower(): v.decode() for k, v in m["headers"]}
        else:
            out["body"] += m.get("body", b"")

    asyncio.run(site.app(scope, receive, send))
    return out["status"], out["headers"], out["body"]


class Worker(unittest.TestCase):
    def test_sw_names_its_scripts_by_their_hashes(self):
        status, h, body = call("/sw.js")
        self.assertEqual(status, 200)
        self.assertTrue(h["content-type"].startswith("text/javascript"))
        self.assertEqual(h["cache-control"], "no-cache")
        text = body.decode()
        v = json.loads(re.search(r"var V = (\{.*?\});", text).group(1))
        self.assertNotIn("var V = __VERSIONS__", text)
        core = (ROOT / "ubsite/static/offline-core.js").read_bytes()
        self.assertEqual(v["core"], f"/static/offline-core.js?v={hashlib.sha256(core).hexdigest()[:10]}")
        for k, name in (("js", "sqlite3.js"), ("wasm", "sqlite3.wasm")):
            data = (ROOT / "vendor/sqlite-wasm" / name).read_bytes()
            self.assertEqual(v[k], f"/offline/{name}?v={hashlib.sha256(data).hexdigest()[:10]}")

    def test_the_engine_is_sent_gzipped_when_asked(self):
        data = (ROOT / "vendor/sqlite-wasm/sqlite3.wasm").read_bytes()
        status, h, body = call("/offline/sqlite3.wasm", headers={"accept-encoding": "gzip, br"})
        self.assertEqual((status, h["content-encoding"], h["content-type"]), (200, "gzip", "application/wasm"))
        self.assertEqual(gzip.decompress(body), data)
        status, h, body = call("/offline/sqlite3.wasm")
        self.assertNotIn("content-encoding", h)
        self.assertEqual(body, data)
        self.assertEqual(call("/offline/sqlite3.mjs")[0], 404)

    def test_what_a_browser_asks_again_after_every_page_is_a_304(self):
        # With Work offline on, a browser asks for the worker and each script it
        # imports after every page it loads, to see whether they have changed.
        for path, enc in (("/sw.js", ""), ("/offline/sqlite3.js", "gzip"), ("/offline/sqlite3.js", "")):
            hs = {"accept-encoding": enc} if enc else {}
            status, h, _ = call(path, headers=hs)
            self.assertEqual((status, h["cache-control"]), (200, "no-cache"), path)
            status, h2, body = call(path, headers={**hs, "if-none-match": h["etag"]})
            self.assertEqual((status, body), (304, b""), (path, enc))
            self.assertEqual(h2["etag"], h["etag"])
        gz = call("/offline/sqlite3.js", headers={"accept-encoding": "gzip"})[1]["etag"]
        self.assertNotEqual(gz, call("/offline/sqlite3.js")[1]["etag"])

    def test_a_chunk_is_named_by_its_hash_and_nothing_else(self):
        for name in ("..%2Fmanifest.json", "0123456789abcdef.gz.bak", "0123456789ABCDEF.gz", "x.gz"):
            self.assertEqual(call(f"/offline/c/{name}")[0], 404, name)

    def test_the_app_manifest_names_icons_that_exist(self):
        status, h, body = call("/manifest.webmanifest")
        self.assertEqual(status, 200)
        m = json.loads(body)
        self.assertEqual((m["start_url"], m["display"]), ("/", "standalone"))
        for icon in m["icons"]:
            self.assertTrue((ROOT / "ubsite" / icon["src"].lstrip("/")).is_file(), icon["src"])


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class Pages(unittest.TestCase):
    def test_a_page_names_its_assets_by_their_hashes(self):
        from ubsite.app import STATIC
        body = call("/101:4")[2].decode()
        for name in ("ub.css", "ub.js", "listen.js", "offline.js"):
            h = hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]
            self.assertIn(f"/static/{name}?v={h}", body)
        self.assertIn('<link rel="manifest" href="/manifest.webmanifest">', body)
        self.assertRegex(body, r'<fieldset class="offline" hidden data-src="/static/offline\.js\?v=')

    def test_every_kind_of_page_cuts_and_joins_again(self):
        from offline import pages, site
        shell = None
        for path in ("/", "/101:4", "/i/god", "/appendix/A", "/lists/1955", "/part/2", "/search"):
            text = site.get(path).text
            sh, rec = pages.cut(text)
            shell = shell or sh
            self.assertEqual(sh, shell, path)
            self.assertEqual(pages.compose(sh, rec, rec.pop("q")), text, path)

    def test_a_sections_rail_is_its_papers_but_for_its_mark(self):
        from offline import pages, site
        rails = set()
        for s in (0, 4, 7):
            sh, rec = pages.cut(site.get(f"/101:{s}").text)
            body, rail = pages.lift_rail(rec["b"], 101, s)
            self.assertEqual(body.count(pages.RAIL), 1)
            self.assertNotIn('<li class="here"><a href="/101:', rail)
            rails.add(rail)
        self.assertEqual(len(rails), 1)

    def test_a_page_that_is_not_a_page_will_not_cut(self):
        from offline import pages
        with self.assertRaises(pages.Shape):
            pages.cut("<!doctype html><title>x</title>")


@unittest.skipUnless((COPY / "manifest.json").exists(), "var/offline/ has not been built")
class Copy(unittest.TestCase):
    def test_the_manifest_is_revalidated_by_its_etag(self):
        status, h, body = call("/offline/manifest.json")
        self.assertEqual((status, h["cache-control"]), (200, "no-cache"))
        m = json.loads(body)
        self.assertEqual(m["format"], 1)
        self.assertEqual(call("/offline/manifest.json", headers={"if-none-match": h["etag"]})[0], 304)

    def test_its_build_is_the_hash_of_what_it_holds(self):
        m = json.loads((COPY / "manifest.json").read_text())
        build = hashlib.sha256("\n".join(sorted(f"{c['name']} {c['hash']}" for c in m["chunks"]))
                               .encode()).hexdigest()[:16]
        self.assertEqual(m["build"], build)
        c = m["chunks"][0]
        status, h, body = call(f"/offline/{c['file']}")
        self.assertEqual((status, h["cache-control"]), (200, "public, max-age=31536000, immutable"))
        self.assertEqual(hashlib.sha256(gzip.decompress(body)).hexdigest()[:16], c["hash"])


if __name__ == "__main__":
    unittest.main()
