"""The margin beside a paragraph: a range stands once, and nothing is said of none.

An entry citing a range, 44:0.20-21, stands beside its first paragraph alone,
and its citation on the concept page still opens the range with every
paragraph of it tinted (Tigran, 2026-10-13).  A paragraph that nothing cites
precisely has an empty margin, not "no entry cites this paragraph precisely".
Which ranges the index cites is edited daily, so the cases are asked of the
database.  Skipped when var/ub.db has not been built.

The index folds (templates/_fold.html): a button at the head of a section page
and of a reading path, and in every box of entries a line saying how many it
holds, which is the box on a phone while the index is folded.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get


RE_AFOLD = re.compile(r'<button class="afold" type="button" aria-expanded="false">'
                      r'(\d+) index entr(y|ies)( across this whole section)?</button>')


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

    def test_the_index_folds_from_the_head_of_the_page(self):
        head = '<div class="marginhead"><button class="indexfold" type="button" aria-expanded="true">'
        for url in ("/1:0", "/144:3", "/i/ice-ages/read", "/i/prayer/read/theme"):
            body = get(url)[2]
            self.assertEqual(body.count(head), 1, url)
        self.assertRegex(get("/1:0")[2], r"<article>\s*" + re.escape(head))
        self.assertNotIn("marginhead", get("/part/4")[2])          # a part's page has no index

    def test_each_box_says_how_many_entries_it_holds(self):
        for url in ("/1:0", "/144:3", "/15:4"):
            body = get(url)[2]
            for a in re.findall(r'<div class="a">(.*?)</div>', body, re.S):
                if not a:
                    continue
                m = RE_AFOLD.match(a.strip())
                self.assertTrue(m, f"{url}: {a[:80]}")
                self.assertEqual(int(m[1]), a.count("<li>"), url)
                self.assertEqual(m[2], "y" if m[1] == "1" else "ies")
            b = re.search(r'<aside class="blanket">(.*?)</aside>', body, re.S)
            if b:
                m = RE_AFOLD.match(b[1].strip())
                self.assertEqual((int(m[1]), m[3]), (b[1].count("<li>"), " across this whole section"))

    def test_each_caption_on_a_reading_path_says_how_many(self):
        for url in ("/i/ice-ages/read", "/i/prayer/read/theme", "/i/thirst/read"):   # thirst: verse
            body = get(url)[2]
            rows = re.findall(r'<div class="row[^"]*">(<button class="afold"[^>]*>(\d+) index entr(?:y|ies)</button>)?'
                              r'(<ul class="cites">.*?</ul>|<div class="cites">.*?</div>)', body, re.S)
            self.assertTrue(rows, url)
            for button, n, cites in rows:
                self.assertTrue(button, f"{url}: a caption without its line")
                self.assertEqual(int(n), cites.count("<li>"), url)


if __name__ == "__main__":
    unittest.main()
