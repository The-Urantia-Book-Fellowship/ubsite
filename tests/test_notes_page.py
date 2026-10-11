"""A 1955 reading reaches the reader: a ring in the text, its words and reason after it.

Rendered through the app itself (the ASGI helper of test_appendix_pages), as a
reader is sent the page.  The margin holds the index alone; the notes are the
section's endnotes, which ub.js opens as cards.  Skipped when var/ub.db has not
been built.
"""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_appendix_pages import DB, get  # noqa: E402


def note(page: str, key: str) -> str:
    m = re.search(rf'<aside class="note" id="fn{key}">(.*?)</aside>', page, re.S)
    return m.group(1) if m else ""


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class NotesPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p41 = get("/41:4")[2]

    def test_the_ring(self):
        self.assertIn('<a class="fn" href="#fn41_4_4_0" id="fnref41_4_4_0" data-k="1955"'
                      ' aria-label="1955 reading"></a>', self.p41)

    def test_the_committee_reason(self):
        n = note(self.p41, "41_4_4_0")
        # 1955 as the press gives it, never the committee's quotation of it.
        self.assertIn('1955</a> sixty</p>', n)
        self.assertNotIn("having become", n)
        self.assertIn('<span class="dec">Adopted.</span> Textual consistency', n)
        self.assertIn('href="/43:1.6"', n)               # a link to the book, made ours
        self.assertIn("text-standardization-Urantia-Book#U41_4_4", n)

    def test_the_margin_holds_the_index_alone(self):
        for a in re.findall(r'<div class="a">(.*?)</div>', self.p41, re.S):
            self.assertNotIn("note", a)

    def test_a_note_without_an_entry(self):
        n = note(get("/55:4")[2], "55_4_15_0")
        self.assertIn("quartette", n)
        self.assertNotIn("SRT Committee", n)

    def test_a_note_referred_on(self):
        n = note(get("/157:1")[2], "157_1_3_0")
        self.assertIn('<p class="why see"><a href="/89:3.1">89:3.1</a>:', n)

    def test_a_reason_shared_in_its_paragraph(self):
        n = note(get("/134:3")[2], "134_3_3_1")
        self.assertIn("The three occurrences of time", n)
        self.assertNotIn('class="why see"', n)


if __name__ == "__main__":
    unittest.main()
