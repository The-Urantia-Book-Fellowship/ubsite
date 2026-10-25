"""Each appendix page holds every one of its entries once, and a link to one lands.

Rendered through the app itself, called as ASGI with no HTTP client -- the venv
has none, and what matters is the HTML a reader is sent, not a query that
describes it.  Skipped when var/ub.db has not been built.
"""

import asyncio
import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "var" / "ub.db"

RE_ID = re.compile(r'\bid="([^"]+)"')
# The page as a reader of English is sent it (ubsite/l10n.py): the Russian of
# the interface out, its elements and its attributes, and the English as it
# was before both were drawn.  What UB_BILINGUAL=0 sends, byte for byte.
RE_RU = re.compile(r'<x-ru lang="ru">.*?</x-ru>|</?x-en>|\sdata-ru(?:-[\w-]+)?="[^"]*"'
                   r'|, "label_ru": "(?:[^"\\]|\\.)*"', re.S)


def en(body: str) -> str:
    return RE_RU.sub("", body)
RE_APP_HREF = re.compile(r'href="/appendix/([A-F])#([^"]+)"')


def get(url: str, raw: bool = False) -> tuple[int, dict, str]:
    """(status, headers, body) for a GET of url: the body in English (en()),
    or with `raw` as sent, in both languages."""
    from ubsite.app import app
    path, _, query = url.partition("?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path,
             "raw_path": path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": [(b"host", b"test")],
             "client": ("127.0.0.1", 1), "server": ("test", 80)}
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
    body = out["body"].decode()
    return out["status"], out["headers"], body if raw else en(body)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class AppendixPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.anchors = {}
        for scope, anchor in con.execute(
                "SELECT scope, anchor FROM index_entry WHERE scope <> 'az'"):
            cls.anchors.setdefault(scope, []).append(anchor)
        cls.pages = {}
        for letter in "ABCDEF":
            status, _, body = get(f"/appendix/{letter}")
            cls.pages[letter] = (status, body, RE_ID.findall(body))

    def test_every_entry_once(self):
        for letter, (status, body, ids) in self.pages.items():
            with self.subTest(appendix=letter):
                self.assertEqual(status, 200)
                self.assertEqual(len(ids), len(set(ids)), "an id repeats")
                entries = [i for i in ids if i in set(self.anchors[letter])]
                self.assertEqual(sorted(entries), sorted(self.anchors[letter]))

    def test_chips_land(self):
        # 135:8 has Chronology chips; 53:1 has Abaddon, cited by both the A-Z and
        # Appendix C at 53:1.5; 122:8 has the three conjunctions in Pisces.
        seen = 0
        for ref in ("135:8", "53:1", "122:8", "57:1"):
            status, _, body = get(f"/{ref}")
            self.assertEqual(status, 200, ref)
            for letter, anchor in RE_APP_HREF.findall(body):
                seen += 1
                self.assertIn(anchor, self.pages[letter][2], f"{ref} -> {letter}#{anchor}")
        self.assertGreater(seen, 0)

    def test_no_chip_repeats_the_a_z(self):
        _, _, body = get("/53:1")
        self.assertTrue('href="/i/abaddon#' in body, "the A-Z chip for Abaddon is gone")
        self.assertFalse("Individuals Named</span> Abaddon" in body,
                         "Appendix C repeats Abaddon beside 53:1.5")

    def test_concept_page_names_its_appendices(self):
        _, _, body = get("/i/adam")
        listed = body[body.index('class="listed"'):]
        listed = listed[:listed.index("</p>")]
        self.assertEqual(sorted(l for l, _ in RE_APP_HREF.findall(listed)), ["C", "D"])

    def test_search_finds_a_name_the_a_z_lacks(self):
        _, _, body = get("/search?q=Sumeria")
        self.assertRegex(body, r'href="/appendix/F#e[0-9a-f]+">Sumeria</a>')

    def test_addresses(self):
        status, headers, _ = get("/appendix/c")
        self.assertEqual((status, headers.get("location")), (301, "/appendix/C"))
        self.assertEqual(get("/appendix/G")[0], 404)
        self.assertEqual(get("/appendix")[0], 200)


if __name__ == "__main__":
    unittest.main()
