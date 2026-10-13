"""The margin beside a paragraph: a range stands once, and nothing is said of none.

An entry citing a range, 44:0.20-21, stands beside its first paragraph alone,
and its citation on the concept page still opens the range with every
paragraph of it tinted (Tigran, 2026-10-13).  A paragraph that nothing cites
precisely has an empty margin, not "no entry cites this paragraph precisely".
Which ranges the index cites is edited daily, so the cases are asked of the
database.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get


def margin(body: str, ref: str) -> str:
    """What stands beside paragraph `ref` of a section page."""
    m = re.search(r'id="' + re.escape(ref) + r'">.*?</p>\s*<div class="a">(.*?)</div>', body, re.S)
    assert m, f"no margin after {ref}"
    return m.group(1)


def classes(body: str, ref: str) -> list[str]:
    m = re.search(r'<p class="([^"]*)"\s+id="' + re.escape(ref) + '"', body)
    assert m, f"no paragraph {ref}"
    return m.group(1).split()


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Margin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def test_a_range_stands_beside_its_first_paragraph(self):
        from ubsite.app import entry_href
        # An A-Z entry citing two paragraphs of prose as a range, and naming the
        # second nowhere on its own.
        r = self.con.execute(
            "SELECT c.canonical, r.slug, e.level, e.anchor, p.paper_n, p.section_n,"
            "       p.para_n - 1 AS first, p.para_n AS cont"
            " FROM citation_target t JOIN citation c ON c.id = t.citation_id"
            " JOIN index_entry e ON e.id = t.entry_id JOIN index_entry r ON r.id = e.root_id"
            " JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE NOT t.opens AND e.scope = 'az' AND c.n_targets = 2"
            "   AND c.canonical NOT LIKE '%,%' AND p.src = 'vs'"
            "   AND NOT EXISTS (SELECT 1 FROM citation_target u WHERE u.entry_id = t.entry_id"
            "                   AND u.paragraph_id = t.paragraph_id AND u.opens)"
            " ORDER BY c.id LIMIT 1").fetchone()
        self.assertIsNotNone(r)
        sec = f"{r['paper_n']}:{r['section_n']}"
        first, cont = f"{sec}.{r['first']}", f"{sec}.{r['cont']}"
        self.assertEqual(r["canonical"], f"{first}-{r['cont']}")
        href = f'href="{entry_href(r["slug"], r["level"], r["anchor"])}"'

        status, _, body = get(f"/{sec}")
        self.assertEqual(status, 200)
        self.assertIn(href, margin(body, first))
        self.assertNotIn(href, margin(body, cont))

        # The concept page still cites the range, and the range tints both.
        status, _, page = get(f"/i/{r['slug']}")
        self.assertEqual(status, 200)
        self.assertIn(f'href="/{r["canonical"]}"', page)
        status, _, body = get(f"/{r['canonical']}")
        self.assertEqual(status, 200)
        self.assertIn("hit", classes(body, first))
        self.assertIn("hit", classes(body, cont))

    def test_a_paragraph_nothing_cites_has_an_empty_margin(self):
        ref, = self.con.execute(
            "SELECT p.ref FROM paragraph p JOIN para_density d ON d.paragraph_id = p.id"
            " WHERE d.thin AND p.src = 'vs' ORDER BY p.ord LIMIT 1").fetchone()
        status, _, body = get("/" + ref.split(".")[0])
        self.assertEqual(status, 200)
        self.assertEqual(margin(body, ref), "")
        self.assertNotIn("no entry cites", body)


if __name__ == "__main__":
    unittest.main()
