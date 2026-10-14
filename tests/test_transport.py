"""A section's transport bar: ⏪ a paper back, ⏮ a section back, ⏭ a section
on, ⏩ a paper on, in the order of the book and across papers' edges.

Every section's four targets are held to its neighbours in the list of all
sections, and a part's page has the one, ⏭ to its first paper's first
section; a few pages are rendered through the app as ASGI, as
test_appendix_pages does, for the bar itself and its greyed ends.  The
Tooltips switch is a setting, on by default.  Skipped when var/ub.db has not
been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get
from ubsite import settings

RE_BAR = re.compile(r'<nav class="transport"[^>]*>(.*?)</nav>', re.S)
RE_LINK = re.compile(r'<a class="(\w+)" href="/([\d:]+)"(?: rel="\w+")? aria-label="([^"]+)" title="\3">')
RE_OFF = re.compile(r'<span class="(\w+) off" aria-hidden="true">')


def bar(url: str) -> tuple[dict, list]:
    status, _, body = get(url)
    assert status == 200, (url, status)
    m = RE_BAR.search(body)
    assert m, f"{url}: no transport bar"
    links = {k: (href, label) for k, href, label in RE_LINK.findall(m.group(1))}
    return links, RE_OFF.findall(m.group(1))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.sections = list(con.execute("SELECT paper_n, n FROM section ORDER BY paper_n, n"))
        cls.first = {}
        for p, s in cls.sections:
            cls.first.setdefault(p, s)
        cls.parts = list(con.execute("SELECT n, first_paper FROM part ORDER BY n"))

    def test_every_section_steps_to_its_neighbours(self):
        from ubsite.app import db, transport
        con, papers = db(), sorted(self.first)
        for i, (p, s) in enumerate(self.sections):
            go = transport(con, p, s)
            want_prev = self.sections[i - 1] if i else None
            want_next = self.sections[i + 1] if i + 1 < len(self.sections) else None
            j = papers.index(p)
            want_fb = (papers[j - 1], self.first[papers[j - 1]]) if j else None
            want_ff = (papers[j + 1], self.first[papers[j + 1]]) if j + 1 < len(papers) else None
            for k, want in (("prev", want_prev), ("next", want_next), ("fb", want_fb), ("ff", want_ff)):
                got = go[k] and (go[k]["paper_n"], go[k]["n"])
                self.assertEqual(got, want, f"{p}:{s} {k}")
                if want:
                    self.assertEqual(go[k]["href"], f"/{want[0]}:{want[1]}")

    def test_across_a_papers_edge(self):
        links, off = bar("/101:0")
        self.assertEqual(off, [])
        self.assertEqual(links["fb"], ("100:0", "Previous paper: 100"))
        self.assertEqual(links["prev"], ("100:7", "Previous section: 100:7"))
        self.assertEqual(links["next"], ("101:1", "Next section: 101:1"))
        self.assertEqual(links["ff"], ("102:0", "Next paper: 102"))
        self.assertEqual(list(links), ["fb", "prev", "next", "ff"])

    def test_the_foreword(self):
        links, off = bar("/1:0")
        self.assertEqual(links["fb"], ("0:0", "Previous paper: the Foreword"))
        self.assertEqual(links["prev"], ("0:12", "Previous section: 0:12"))

    def test_the_books_ends_are_greyed(self):
        links, off = bar("/0:0")
        self.assertEqual(off, ["fb", "prev"])
        self.assertEqual(list(links), ["next", "ff"])
        p, s = self.sections[-1]
        links, off = bar(f"/{p}:{s}")
        self.assertEqual(off, ["next", "ff"])
        self.assertEqual(list(links), ["fb", "prev"])

    def test_a_parts_page_goes_on_to_its_first_section(self):
        self.assertEqual(len(self.parts), 4)
        for n, fp in self.parts:
            links, off = bar(f"/part/{n}")
            here = f"{fp}:{self.first[fp]}"
            self.assertEqual(links, {"next": (here, f"Next section: {here}")}, n)
            self.assertEqual(off, [], n)

    def test_tooltips_are_on_by_default(self):
        self.assertIs(settings.defaults()["tips"], True)


if __name__ == "__main__":
    unittest.main()
