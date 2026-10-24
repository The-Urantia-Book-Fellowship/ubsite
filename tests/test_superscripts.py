"""An ordinal's suffix is a superscript wherever the index's words are shown.

The index sets it as the book does, `611,121\\ts{st}` (its 0aeae38).  The plain
columns read `1st`, as they did, so that slugs, anchors and search are what
they were; each has an `_html` sibling with `<sup>`, and the pages show that.
Search shows a hit's superscripts too, the text's among them, placed by offset
(app.py `_snip`).  The index is edited daily, so the cases are asked of the
database where they can be.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Superscripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def has(self, body: str, piece: str):
        self.assertTrue(piece in body, f"{piece!r} is not in the page")

    def page(self, url: str) -> str:
        status, _, body = get(url)
        self.assertEqual(status, 200, url)
        return body

    def test_plain_columns_stay_plain(self):
        for sql in ("SELECT COUNT(*) FROM index_entry WHERE text LIKE '%<%' OR path_plain LIKE '%<%'"
                    " OR headword LIKE '%<%'",
                    "SELECT COUNT(*) FROM xref WHERE target LIKE '%<%'",
                    "SELECT COUNT(*) FROM chronology_event WHERE label LIKE '%<%'"):
            self.assertEqual(self.con.execute(sql).fetchone()[0], 0, sql)
        (slug,) = self.con.execute(
            "SELECT slug FROM index_entry WHERE headword = 'December 25th'").fetchone()
        self.assertEqual(slug, "december-25th")

    def test_a_headword(self):
        body = self.page("/i/december-25th")
        self.has(body, "<title>December 25th")
        self.has(body, "<h1>December 25<sup>th</sup></h1>")
        self.has(self.page("/index/D"), ">December 25<sup>th</sup></a>")

    def test_a_see_where_it_stands_and_listed(self):
        html, href = self.con.execute(
            "SELECT target_html, href FROM xref"
            " WHERE kind = 'see' AND target = 'mansion worlds: 1st'").fetchone()
        self.assertEqual(html, "mansion worlds: 1<sup>st</sup>")
        body = self.page("/i/first-mansion-world")
        tree, _, listed = body.partition("<h2>Cross-references</h2>")
        self.has(tree, f'<a class="hw" href="{href}">{html}</a>')
        self.has(listed, f'<a href="{href}">{html}</a>')

    def test_a_qv_after_its_number(self):
        body = self.page("/i/supreme-power-centers")
        self.assertRegex(body, r'1<sup>st</sup>\. <a class="hw" href="/i/[^"]+">'
                               r'Supreme Center Supervisors</a> <i>q\.v\.</i>')

    def test_a_chip_and_a_chronology_window(self):
        self.has(self.page("/77:3"), "1<sup>st</sup> tower built 50,000 years")
        self.has(self.page("/189:4"), "30 A.D.: 1<sup>st</sup> appearance, at tomb</a>")
        self.has(self.page("/appendix/A"), "1<sup>st</sup> appearance, at tomb")

    def test_search(self):
        body = self.page("/search?q=611%2C121st&in=text")
        self.has(body, "the <mark>611,121<sup>st</sup></mark> original concept")
        body = self.page("/search?q=tower&in=index")
        self.has(body, "1<sup>st</sup> <mark>tower</mark> built")
        # Found by the plain words, as before.
        body = self.page("/search?q=1st&in=index")
        self.has(body, "<mark>1<sup>st</sup></mark>")
        body = self.page("/search?q=December+25th")
        self.has(body, '<a href="/i/december-25th">December 25<sup>th</sup></a>')

    def test_the_committee_s_words(self):
        body = self.page("/search?q=Britannica+11th&in=notes")
        self.has(body, "<mark>Britannica</mark> is found in its <mark>11<sup>th</sup></mark> Edition")

    def test_today_s_words_beside_a_1955_reading(self):
        body = self.page("/lists/1955")
        line = body[body.index('href="/42:6.7#note'):]
        line = line[:line.index("</li>")]
        self.has(line, "1/2,000<sup>th</sup>")

    def test_every_sup_is_whole(self):
        # Each superscript in a page of search results opens and closes inside
        # one mark or outside all of them.
        body = self.page("/search?q=appearance")
        self.assertGreater(body.count("<sup>"), 5)
        self.assertNotRegex(body, r"<sup>[^<]*<mark>|<mark>[^<]*<sup>[^<]*</mark>")


if __name__ == "__main__":
    unittest.main()
