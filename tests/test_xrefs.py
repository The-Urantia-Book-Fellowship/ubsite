"""See and See also: a link where each stands, and gathered under Cross-references.

Every target is a link in its entry, to the line it names when that is a
subentry, and the concept page's Cross-references list gives each the same
link (Tigran, 2026-10-18).  The index is edited daily, so the cases are asked
of the database.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from markupsafe import escape

from test_appendix_pages import DB, get

RE_ID = re.compile(r'\bid="([^"]+)"')


def in_order(body: str, pieces: list[str]) -> bool:
    p = 0
    for s in pieces:
        p = body.find(s, p)
        if p < 0:
            return False
        p += len(s)
    return True


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Xrefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def xrefs(self, root_id: int) -> list[tuple[int, str, str]]:
        return self.con.execute(
            "SELECT x.entry_id, x.target, x.href FROM xref x"
            " JOIN index_entry e ON e.id = x.entry_id"
            " WHERE e.root_id = ? AND x.kind IN ('see', 'seealso')"
            " ORDER BY e.ord, x.ord", (root_id,)).fetchall()

    def page(self, slug: str) -> tuple[str, str]:
        """A concept page, split into its tree and its Cross-references."""
        status, _, body = get(f"/i/{slug}")
        self.assertEqual(status, 200, slug)
        tree, sep, rest = body.partition("<h2>Cross-references</h2>")
        self.assertTrue(sep, f"/i/{slug} has no Cross-references")
        return tree, rest.partition("</ul>")[0]

    def test_linked_where_they_stand_and_listed(self):
        # body, human: one long See also; mind: a See into its own subentry;
        # Master Spirits, Seven: the one range (Master Spirit #1 - #7).
        for slug in ("body-human", "mind", "master-spirits-seven", "reality"):
            with self.subTest(slug=slug):
                (root,) = self.con.execute(
                    "SELECT id FROM index_entry WHERE slug = ?", (slug,)).fetchone()
                xs = self.xrefs(root)
                self.assertTrue(xs)
                tree, listed = self.page(slug)
                self.assertTrue(in_order(tree, [f'<a class="hw" href="{h}">{t}</a>'
                                                 for _, t, h in xs]))
                for _, t, h in xs:
                    self.assertIn(f'<a href="{h}">{escape(t)}</a>', listed)

    def test_the_longest_clause(self):
        # "named philosophies", under philosophy, when this was written: each
        # target is found where it stands, never inside an earlier one.
        eid, n = self.con.execute(
            "SELECT entry_id, COUNT(*) FROM xref WHERE kind IN ('see', 'seealso')"
            " GROUP BY entry_id ORDER BY 2 DESC LIMIT 1").fetchone()
        self.assertGreater(n, 20)
        root, slug, anchor = self.con.execute(
            "SELECT r.id, r.slug, e.anchor FROM index_entry e"
            " JOIN index_entry r ON r.id = e.root_id WHERE e.id = ?", (eid,)).fetchone()
        tree, _ = self.page(slug)
        li = tree[tree.index(f'id="{anchor}"'):]
        li = li[:li.index("</li>")]
        links = re.findall(r'<a class="hw" href="([^"]*)">([^<]*)</a>', li)
        self.assertEqual(links, [(h, t) for e, t, h in self.xrefs(root) if e == eid])

    def test_a_link_to_a_line_lands_on_it(self):
        rows = self.con.execute(
            "SELECT href FROM xref WHERE kind IN ('see', 'seealso') AND href LIKE '%#%'"
            " ORDER BY id").fetchall()
        self.assertGreater(len(rows), 100)
        pages = {}
        for (href,) in rows[::25]:
            slug, _, anchor = href[len("/i/"):].partition("#")
            if slug not in pages:
                status, _, body = get(f"/i/{slug}")
                self.assertEqual(status, 200, href)
                pages[slug] = set(RE_ID.findall(body))
            self.assertIn(anchor, pages[slug], href)


if __name__ == "__main__":
    unittest.main()
