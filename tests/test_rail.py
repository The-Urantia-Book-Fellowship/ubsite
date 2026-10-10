"""The left rail is the whole book, closed but for the paper being read.

Every paper is there, once; only the paper being read carries its sections, and
another's come from /rail/N, kept by the browser when asked for under the
database's version.  Rendered through the app as ASGI, as test_appendix_pages
does.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get

RE_RAIL = re.compile(r'<nav class="rail"[^>]*>.*?</nav>', re.S)
RE_PAPER = re.compile(r'href="/(\d+)"')
RE_SECTION = re.compile(r'href="/(\d+):(\d+)"')
RE_OPEN_PART = re.compile(r'<li class="part"><details open><summary>Part ([IV]+)\.')


def rail(url: str) -> str:
    status, _, body = get(url)
    assert status == 200, (url, status)
    m = RE_RAIL.search(body)
    assert m, f"{url}: no rail"
    return m.group(0)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Rail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.papers = [n for (n,) in con.execute("SELECT n FROM paper ORDER BY n")]
        cls.sections = {}
        for p, s in con.execute("SELECT paper_n, n FROM section ORDER BY paper_n, n"):
            cls.sections.setdefault(p, []).append(s)
        cls.version = str(DB.stat().st_mtime_ns)

    def test_every_paper_once_and_only_its_own_sections(self):
        r = rail("/133:2")
        self.assertEqual([int(n) for n in RE_PAPER.findall(r)], self.papers)
        secs = [(int(p), int(s)) for p, s in RE_SECTION.findall(r)]
        self.assertEqual(secs, [(133, s) for s in self.sections[133]])

    def test_open_on_the_paper_being_read(self):
        r = rail("/133:2")
        self.assertEqual(RE_OPEN_PART.findall(r), ["IV"])
        self.assertIn('<li class="here"><details open><summary><a href="/133">', r)
        self.assertEqual(r.count("<details open>"), 2)          # Part IV and Paper 133
        self.assertEqual(re.findall(r'<li class="here"><a href="/([\d:]+)"', r), ["133:2"])

    def test_the_foreword_is_in_no_part(self):
        r = rail("/0:3")
        self.assertEqual(RE_OPEN_PART.findall(r), [])
        self.assertIn('<li class="here"><details open><summary><a href="/0">Foreword</a>', r)
        self.assertEqual(re.findall(r'<li class="here"><a href="/([\d:]+)"', r), ["0:3"])

    def test_a_papers_sections_on_demand(self):
        status, headers, body = get(f"/rail/101?v={self.version}")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "public, max-age=31536000, immutable")
        self.assertEqual([(int(p), int(s)) for p, s in RE_SECTION.findall(body)],
                         [(101, s) for s in self.sections[101]])
        self.assertNotIn('class="here"', body)

    def test_unversioned_or_stale_is_not_kept(self):
        for url in ("/rail/101", "/rail/101?v=1"):
            self.assertEqual(get(url)[1].get("cache-control"), "no-cache", url)

    def test_no_such_paper(self):
        self.assertEqual(get("/rail/197")[0], 404)

    def test_139_names_its_combined_section(self):
        _, _, body = get("/rail/139")
        self.assertIn('<a href="/139:9">9 and 10. ', body)


if __name__ == "__main__":
    unittest.main()
