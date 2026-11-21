"""A concept page, /i/<slug>: the headword's own line is not in its tree.

Its words are the page's heading, and its See or See also is under
Cross-references, the same words to the same link; what the line alone
carries, its citations, stands under the heading (derive.head_cites).  So the
subentries stand at the left, a level of indent less (Tigran, 2026-11-21).
The index is edited daily, so the cases are asked of the database.  Skipped
when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, ROOT, get

RE_LI = re.compile(r'<li class="l(\d)"')


class HeadCites(unittest.TestCase):
    """derive.head_cites on lines made up here: every form the index prints,
    and a line with a word more, which fails the build."""

    def run_on(self, lines: list[tuple[str, str]]):
        from build import derive

        class Report:
            def __init__(self):
                self.hard_ = []

            def hard(self, code, where, msg):
                self.hard_.append((code, where))

        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE index_entry (id INTEGER PRIMARY KEY, scope TEXT, level INTEGER,"
                    " text_html TEXT, headword_html TEXT, source_file TEXT, source_line INTEGER)")
        con.executemany("INSERT INTO index_entry VALUES (?, 'az', 1, ?, ?, 'idx.tex', ?)",
                        [(i, h, w, i) for i, (w, h) in enumerate(lines, 1)])
        report = Report()
        derive.head_cites(con, report)
        return [c for c, in con.execute("SELECT cites_html FROM index_entry ORDER BY id")], report.hard_

    def test_the_forms(self):
        c1 = '<a class="cit" href="/74">(Papers 74–75)</a>'
        c2 = '<a class="cit" href="/165:0.1">(165:0.1)</a>'
        see = '<i>See also</i> <a class="hw" href="/i/eve">Eve</a>; <a class="hw" href="/i/m">m: 1<sup>st</sup></a>'
        cites, hard = self.run_on([
            ("Adam", f"Adam {c1} {c2}. {see}"),
            ("apes", f"apes. {c2} {see}"),
            ("midwayers", f"midwayers {c1} {see}"),
            ("oaths", f"oaths. {see}"),
            ("chronoldeks", f"chronoldeks {see}"),
            ("606", '606. <i>See</i> <a class="hw" href="/i/u">Urantia</a>'),
            ("Abila", f"Abila {c2}"),
            ("adoption", "adoption"),
        ])
        self.assertEqual(hard, [])
        self.assertEqual(cites, [f"{c1} {c2}", c2, c1, None, None, None, c2, None])

    def test_a_word_more_fails(self):
        c = '<a class="cit" href="/1">(Paper 1)</a>'
        see = '<i>See also</i> <a class="hw" href="/i/eve">Eve</a>'
        _, hard = self.run_on([
            ("Adam", f"Adam, the first {c}"),
            ("Adam", f"Adam {c}. {see} and others"),
            ("Adam", f"Adam {c} (in part)"),
            ("Adam", f"Eve {c}"),
        ])
        self.assertEqual([code for code, _ in hard], ["headword-line-other"] * 4)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Concept(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def root(self, slug: str) -> sqlite3.Row:
        return self.con.execute("SELECT * FROM index_entry WHERE slug = ?", (slug,)).fetchone()

    def page(self, slug: str) -> tuple[str, str]:
        """The page's <main> up to its Cross-references, and that list."""
        status, _, body = get(f"/i/{slug}")
        self.assertEqual(status, 200, slug)
        main = body[body.index("<main"):body.index("</main>")]
        head, _, rest = main.partition("<h2>Cross-references</h2>")
        return head, rest.partition("</ul>")[0]

    def crossrefs(self, root_id: int) -> list[str]:
        return [f'<a href="{h}">{t}</a>' for t, h in self.con.execute(
            "SELECT x.target_html, x.href FROM xref x JOIN index_entry e ON e.id = x.entry_id"
            " WHERE e.root_id = ? AND x.kind IN ('see', 'seealso') ORDER BY e.ord, x.ord",
            (root_id,))]

    def test_no_headword_line_in_any_tree(self):
        # oaths: the line was its headword and a See also; adam: citations and
        # a See also; soul: citations alone; adoption: the headword alone.
        for slug in ("oaths", "adam", "soul", "adoption"):
            with self.subTest(slug=slug):
                head, _ = self.page(slug)
                levels = RE_LI.findall(head)
                self.assertTrue(levels, slug)
                self.assertNotIn("1", levels)
                self.assertEqual(levels[0], "2")
                self.assertNotIn(f'>{self.root(slug)["text_html"]}</li>', head)

    def test_the_see_also_is_under_cross_references(self):
        head, listed = self.page("oaths")
        self.assertNotIn("<i>See also</i>", head)
        self.assertIn('<i>See also</i>\n  <a href="/i/promises">promises</a>', listed)
        self.assertNotIn('class="hwcites"', head)

    def test_the_citations_stand_under_the_heading(self):
        for slug in ("adam", "abila", "apes", "midwayers"):
            with self.subTest(slug=slug):
                r = self.root(slug)
                cites = re.findall(r'<a class="cit" href="[^"]*">[^<]*</a>', r["text_html"])
                self.assertTrue(cites)
                self.assertEqual(r["cites_html"], " ".join(cites))
                head, _ = self.page(slug)
                self.assertIn(f'</h1>\n<p class="hwcites">{r["cites_html"]}</p>', head)

    def test_the_headword_s_own_come_first(self):
        # Adam: its See also Eve; Garden of Eden; Material Sons of God, then a
        # subentry's See original sin doctrine, where the list once put every
        # See before every See also.
        r = self.root("adam")
        _, listed = self.page("adam")
        want = self.crossrefs(r["id"])
        self.assertEqual(want[:3], ['<a href="/i/eve">Eve</a>',
                                    '<a href="/i/garden-of-eden">Garden of Eden</a>',
                                    '<a href="/i/material-sons-of-god">Material Sons of God</a>'])
        self.assertEqual(re.findall(r'<a href="[^"]*">.*?</a>', listed), want)

    def test_a_headword_with_no_subentries(self):
        head, listed = self.page("606-of-satania")
        self.assertNotIn('<ul class="tree">', head)
        self.assertNotIn("subentries", head)
        self.assertIn('<a href="/i/urantia">Urantia</a>', listed)

    def test_every_headword_line_is_its_parts(self):
        # Nothing but the headword, its citations and its See clause, which
        # derive.head_cites fails the build over; and its citations, all of
        # them, under the heading (check_db holds the count for every one).
        for r in self.con.execute(
                "SELECT text_html, headword_html, cites_html FROM index_entry"
                " WHERE scope = 'az' AND level = 1"):
            h = r["text_html"]
            for c in re.findall(r'<a class="cit" href="[^"]*">[^<]*</a>', h):
                self.assertIn(c, r["cites_html"] or "", h)

    def test_the_tree_is_a_step_to_the_left(self):
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"\.tree \.l2 \{ margin-left")
        self.assertIn(".tree .l3 { margin-left: 1.5em; }", css)


if __name__ == "__main__":
    unittest.main()
