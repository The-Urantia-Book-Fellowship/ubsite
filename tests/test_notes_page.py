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
    """A 1955 note's endnote, which its card carries, as a reader reads it: without
    the soft hyphens that let it break where the book would (footnote.html_hy)."""
    m = re.search(rf'<aside class="note" id="fn{key}">(.*?)</aside>', page, re.S)
    return m.group(1).replace("\u00ad", "") if m else ""


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class NotesPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p41 = get("/41:4")[2]

    def test_the_ring(self):
        self.assertIn('<a class="fn" href="#fn41_4_4_0" id="fnref41_4_4_0" data-k="1955"'
                      ' aria-label="1955 reading"></a>', self.p41)

    def test_set_as_the_text_is(self):
        # Justified in the card, so hyphenated where the book would break.
        m = re.search(r'<aside class="note" id="fn41_4_4_0">(.*?)</aside>', self.p41, re.S)
        self.assertIn("Tex\u00adtual con\u00adsis\u00adtency", m.group(1))

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


def old(page: str) -> str:
    """The 1955 readings among the search results, as the overview has them."""
    m = re.search(r'<section class="by1955">(.*?)</section>', page, re.S)
    return m.group(1) if m else ""


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class NotesSearched(unittest.TestCase):
    """Search finds what a card says: the reading, and the committee's reasons.
    The list is always sent and shown only when Settings asks (ub.css)."""

    def test_a_1955_spelling(self):
        o = old(get("/search?q=forego")[2])
        self.assertIn('<a href="/89:3.1#note89_3_1_0">89:3.1</a>', o)
        self.assertIn('<a href="/93:5.8#note93_5_8_0">93:5.8</a>', o)
        self.assertIn('<span class="lbl">1955</span> <mark>forego</mark>', o)
        # The text's own ring, which opens the same card here, its note beside it.
        self.assertIn('for Abraham to <span class="nw">forgo<a class="fn" href="#fn93_5_8_0"'
                      ' id="fnref93_5_8_0" data-k="1955" aria-label="1955 reading"></a></span>'
                      ' the honors', o)
        self.assertIn('<aside class="note" id="fn93_5_8_0">', o)
        self.assertNotIn('class="dec">Adopted</span>', o.split('<section class="notes"')[0])

    def test_a_name_the_text_no_longer_has(self):
        o = old(get("/search?q=Badanon")[2])
        self.assertIn('href="/86:5.17#note86_5_17_0"', o)
        # Its card, which its ring opens here, has the committee's reasons.
        self.assertIn("</em> is the correct spelling", note(o, "86_5_17_0"))

    def test_found_in_the_reasons_alone(self):
        # "Webster" is in no reading: each hit is its note, by the committee's words.
        o = old(get("/search?q=webster")[2])
        self.assertIn('href="/30:3.12#note30_3_12_0"', o)
        self.assertIn('<span class="lbl">SRT Committee</span>', o)
        self.assertIn("<mark>Webster</mark>", o)

    def test_the_reasons_only_where_they_matched(self):
        o = old(get("/search?q=Badonan")[2])     # today's spelling, in the reasons
        self.assertIn("86:5.17", o)
        o = old(get("/search?q=quartette")[2])   # a note the committee is silent on
        self.assertIn("55:4.15", o)
        self.assertNotIn("SRT Committee", o)

    def test_nothing_matched_no_list(self):
        page = get("/search?q=Thought%20Adjuster")[2]
        self.assertNotIn("In the 1955 readings", page)

    def test_the_list_alone(self):
        page = get("/search?q=forego&in=notes")[2]
        self.assertIn("<section><h2>In the 1955 readings", page)
        self.assertNotIn("by1955", page)
        self.assertNotIn("In the index", page)
        self.assertNotIn("In the text", page)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class ListOf1955Readings(unittest.TestCase):
    """/lists/1955: every reading, by paper, each ring opening its card in place."""

    @classmethod
    def setUpClass(cls):
        page = get("/lists/1955")[2]
        cls.main = page[page.index("<main"):page.index("</main>")]

    def test_every_reading_with_its_note(self):
        import sqlite3
        n = sqlite3.connect(f"file:{DB}?mode=ro", uri=True).execute(
            "SELECT COUNT(*) FROM footnote WHERE kind='variant-1955'").fetchone()[0]
        rings = re.findall(r'<a class="fn" href="#fn([\d_]+)" id="fnref\1"', self.main)
        notes = re.findall(r'<aside class="note" id="fn([\d_]+)">', self.main)
        self.assertEqual(len(rings), n)
        self.assertEqual(rings, notes)

    def test_each_reference_opens_its_paragraph_and_card(self):
        import sqlite3
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        for ref, k in re.findall(r'<a href="/([\d:.]+)#note([\d_]+)">', self.main):
            with self.subTest(ref=ref):
                self.assertTrue(con.execute("SELECT 1 FROM paragraph WHERE ref=? AND html LIKE ?",
                                            (ref, f'%id="fnref{k}"%')).fetchone())

    def test_by_paper_with_the_verdict(self):
        self.assertIn('<h2><a href="/0:0">Foreword</a>', self.main)
        self.assertIn('<h2><a href="/93:0">Paper 93. Machiventa Melchizedek</a>', self.main)
        self.assertIn('<span class="dec">Rejected</span>', self.main)

    def test_named_on_the_lists_page(self):
        self.assertIn('<a href="/lists/1955">List of 1955 readings</a>', get("/lists")[2])


if __name__ == "__main__":
    unittest.main()
