"""A paper opens with its first letter dropped two lines, as the press sets it.

The section page marks each paper's first paragraph, the Foreword's included,
`opening`, and ub.css drops its ::first-letter.  That takes the paragraph's
first typographic letter, so every opening must begin with one: not a pilcrow,
not verse, not the heading.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Opening(unittest.TestCase):
    def test_every_paper_opens_with_a_letter(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT ref, text, gap_before, src, heading FROM paragraph"
            " WHERE section_n = 0 AND para_n = 1 ORDER BY paper_n").fetchall()
        self.assertEqual(len(rows), con.execute(
            "SELECT COUNT(DISTINCT paper_n) FROM paragraph").fetchone()[0])
        for ref, text, gap, src, heading in rows:
            self.assertRegex(text, r"^[A-Z]", ref)
            self.assertFalse(gap or heading or src != "vs", ref)

    def test_the_section_page_marks_the_opening_alone(self):
        for url, ref in (("/0:0", "0:0.1"), ("/196:0", "196:0.1")):
            status, _, body = get(url)
            self.assertEqual(status, 200)
            self.assertEqual(re.findall(r'<p class="t opening[^"]*"\s+id="([^"]+)"', body), [ref])
        status, _, body = get("/1:1")
        self.assertEqual(status, 200)
        self.assertNotRegex(body, r'<p class="t opening')


if __name__ == "__main__":
    unittest.main()
