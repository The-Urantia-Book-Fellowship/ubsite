"""The left rail is the whole book, closed but for the paper being read.

Every paper is there, once; only the paper being read carries its sections, and
another's come from /rail/N, kept by the browser when asked for under the
database's version.  A part's title opens its own page, /part/N: the divider,
and none of the text.  A button at its head folds it, kept as a setting that
the dialog does not show.  Rendered through the app as ASGI, as test_appendix_pages
does.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get
from ubsite import settings

RE_RAIL = re.compile(r'<nav class="rail"[^>]*>.*?</nav>', re.S)
RE_PAPER = re.compile(r'href="/(\d+)"')
RE_SECTION = re.compile(r'href="/(\d+):(\d+)"')
RE_OPEN_PART = re.compile(r'<li class="part[^"]*"><details open><summary><a href="/part/\d">Part ([IV]+)\.')


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

    def test_a_part_title_opens_its_page(self):
        r = rail("/133:2")
        self.assertEqual(re.findall(r'<a href="/part/(\d)">Part ([IV]+)\.', r),
                         [("1", "I"), ("2", "II"), ("3", "III"), ("4", "IV")])

    def test_a_parts_page_is_its_divider(self):
        status, _, body = get("/part/4")
        self.assertEqual(status, 200)
        self.assertIn('<p class="papernum">PART IV</p>', body)
        self.assertIn("<h1>The Life and Teachings<br>of Jesus</h1>", body)
        self.assertIn("watchcare of the Apostle Andrew.</p>", body)
        self.assertNotRegex(body, r'<p class="t[ "]')           # no paragraph of text
        self.assertIn('<a class="next" href="/120">', body)
        r = rail("/part/4")
        self.assertEqual(RE_OPEN_PART.findall(r), ["IV"])
        self.assertEqual(r.count("<details open>"), 1)          # the part, and no paper
        self.assertIn('<li class="part here"><details open>', r)

    def test_there_are_four_parts(self):
        for n in (0, 5):
            self.assertEqual(get(f"/part/{n}")[0], 404, n)

    def test_the_button_at_its_head_folds_it(self):
        for url in ("/133:2", "/part/4"):
            r = rail(url)
            self.assertRegex(r, r'^<nav class="rail"[^>]*>\n<button class="railfold" type="button"'
                                r' aria-controls="rail-tree" aria-expanded="true"><span>Contents</span>'
                                r'</button>\n<ol id="rail-tree">', url)

    def test_folded_is_kept_but_not_in_the_dialog(self):
        # The rail's fold, and the index's: each button is its only control.
        d = settings.defaults()
        self.assertEqual((d["rail"], d["margin"]), ("open", True))
        shown = [it["key"] for g in settings.groups([]) for it in g["items"]]
        self.assertEqual(sorted(set(d) - set(shown)), ["margin", "rail"])
        self.assertEqual(len(shown), len(set(shown)))

    def test_139_names_its_combined_section(self):
        _, _, body = get("/rail/139")
        self.assertIn('<a href="/139:9">9 and 10. ', body)


if __name__ == "__main__":
    unittest.main()
