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

from ubsite.app import fts_query  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
