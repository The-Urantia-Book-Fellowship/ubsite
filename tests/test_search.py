"""No query a reader can type may reach FTS5 in a form it cannot parse.

Before fts_query existed the search box passed its text straight to MATCH, and
FTS5 read "self-conscious" as a column filter: every hyphenated word in the
book, every possessive, a stray quote, all returned a 500.  Run against an
in-memory table with the tokenizer the database uses, so no ub.db is needed.
"""

import pathlib
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ubsite.app import TOKENIZE, _around, _marked, fts_query, mark_terms  # noqa: E402

ROWS = ["the self-conscious mind", "Adam and Eve", "the Adamic mission",
        "Jesus’ words", "a Thought Adjuster indwells", "God-knowing men"]


class FtsQuery(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.execute("CREATE VIRTUAL TABLE t USING fts5(x,"
                         " tokenize='unicode61 remove_diacritics 2')")
        self.con.executemany("INSERT INTO t VALUES (?)", [(r,) for r in ROWS])

    def hits(self, q):
        fq = fts_query(q)
        if fq is None:
            return None
        return {r for (r,) in self.con.execute("SELECT x FROM t WHERE t MATCH ?", (fq,))}

    def test_nothing_the_reader_types_raises(self):
        for q in ["self-conscious", "God-knowing", "Jesus'", "Jesus’", "mind:",
                  '"', 'adam"', "(love", "NOT", "AND OR", "a*b", "adam*", "*",
                  '"thought adjuster"', '"thought', "-", "col:val", "NEAR(a b)",
                  "   ", "^adam", "{x}", "a+b"]:
            with self.subTest(q=q):
                self.hits(q)

    def test_a_hyphenated_word_is_a_phrase(self):
        self.assertEqual(self.hits("self-conscious"), {"the self-conscious mind"})
        self.assertEqual(self.hits("God-knowing"), {"God-knowing men"})

    def test_a_possessive_matches_the_name(self):
        self.assertEqual(self.hits("Jesus'"), {"Jesus’ words"})

    def test_a_trailing_star_is_a_prefix(self):
        self.assertEqual(self.hits("adam*"), {"Adam and Eve", "the Adamic mission"})
        self.assertEqual(self.hits("adam"), {"Adam and Eve"})

    def test_a_quoted_phrase_stays_whole(self):
        self.assertEqual(self.hits('"thought adjuster"'), {"a Thought Adjuster indwells"})
        self.assertEqual(self.hits('"adjuster thought"'), set())

    def test_punctuation_alone_is_no_query(self):
        for q in ['"', "-", "*", "   ", ""]:
            with self.subTest(q=q):
                self.assertIsNone(fts_query(q))

    def test_stray_punctuation_does_not_empty_the_result(self):
        # FTS5 reads an empty phrase as matching nothing, which would make the
        # whole AND match nothing.
        self.assertEqual(self.hits("mind -"), {"the self-conscious mind"})



class MarkTerms(unittest.TestCase):
    """An index hit shows its chip with the reader's words marked, as a text hit
    does: by FTS5's own highlight(), over a table with the build's tokenizer."""

    def test_the_tokenizer_is_the_builds(self):
        sql = (ROOT / "build" / "schema" / "004_fts.sql").read_text()
        self.assertEqual(sql.count(f"tokenize='{TOKENIZE}'"), 3)

    def m(self, text, q):
        return str(mark_terms([text], q)[0])

    def test_a_word(self):
        self.assertEqual(self.m("as Creator, only in conjunction with Eternal Son", "conjunction"),
                         "as Creator, only in <mark>conjunction</mark> with Eternal Son")

    def test_each_word_and_a_phrase_whole(self):
        self.assertEqual(self.m("Saturn and Jupiter organized", "jupiter saturn"),
                         "<mark>Saturn</mark> and <mark>Jupiter</mark> organized")
        self.assertEqual(self.m("only in conjunction with the Son", '"in conjunction with"'),
                         "only <mark>in conjunction with</mark> the Son")

    def test_a_prefix_a_possessive_and_diacritics(self):
        self.assertEqual(self.m("conjunction of Jupiter", "conjunct*"),
                         "<mark>conjunction</mark> of Jupiter")
        self.assertEqual(self.m("Jesus’ words", "jesus'"), "<mark>Jesus</mark>’ words")
        self.assertEqual(self.m("the café", "cafe"), "the <mark>café</mark>")

    def test_a_word_not_shown_marks_the_others(self):
        # A hit can match one term only in a citation; its chip still shows the rest.
        self.assertEqual(self.m("Saturn and Jupiter organized", "saturn 57"),
                         "<mark>Saturn</mark> and Jupiter organized")
        self.assertEqual(self.m("Saturn and Jupiter organized", "57"),
                         "Saturn and Jupiter organized")

    def test_the_text_stays_text(self):
        self.assertEqual(self.m("6. & 7. Secrets of <Greatness>", "secrets"),
                         "6. &amp; 7. <mark>Secrets</mark> of &lt;Greatness&gt;")
        self.assertEqual(self.m("a & b", "amp"), "a &amp; b")
        self.assertEqual([str(x) for x in mark_terms(["a", "b"], "")], ["a", "b"])


class NoteHit(unittest.TestCase):
    """A 1955 reading found by search shows today's words around its ring."""

    TEXT = "It required great determination for Abraham to forgo the honors of the Egyptian court"

    def test_words_either_side_cut_where_a_word_ends(self):
        at = self.TEXT.index("forgo") + len("forgo")
        self.assertEqual(_around(self.TEXT, at),
                         ("It required great determination for Abraham to ", "forgo", "",
                          " the honors of the Egyptian court"))
        self.assertEqual(_around(self.TEXT, at, before=3, after=2),
                         ("…Abraham to ", "forgo", "", " the honors…"))

    def test_what_touches_the_ring_stays_with_it(self):
        text = "embrace the mussels, clams, oysters"
        self.assertEqual(_around(text, text.index(",")),
                         ("embrace the ", "mussels", ",", " clams, oysters"))

    def test_at_either_end(self):
        self.assertEqual(_around("one two", 0), ("", "", "one", " two"))
        self.assertEqual(_around("one two", 7), ("one ", "two", "", ""))

    def test_the_marks_after_escaping(self):
        self.assertEqual(str(_marked("Webster\u2019s & <b> \x02forego\x03")),
                         "Webster\u2019s &amp; &lt;b&gt; <mark>forego</mark>")


if __name__ == "__main__":
    unittest.main()
