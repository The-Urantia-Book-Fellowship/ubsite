"""A 1955 note that differs only in italics is told in words and marked.

The cases are the live ones: 102:3.5's semicolon, 112:1.7's "depth", and
59:4.18's whole note.  A note with other words is left alone.
"""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.render import render  # noqa: E402
from build.variants import Mark, italics_only  # noqa: E402


class Em:
    kind = "em"

    def __init__(self, start, end):
        self.start, self.end = start, end


class ItalicsOnly(unittest.TestCase):
    def test_semicolon(self):
        text = "the consciousness of true reality; while the co-ordination"
        a = text.index(" the co-")
        s = text.index("true")
        gloss, marks = italics_only(text, [Em(s, s + len("true reality;"))], a,
                                    "true reality; while", [Em(0, len("true reality"))])
        self.assertEqual(gloss, "the semicolon is upright in 1955, italic here")
        self.assertEqual(marks, [Mark(12, 13)])
        self.assertEqual(render("true reality; while", [Em(0, 12), *marks]),
                         '<em>true reality</em><mark class="chg">;</mark> while')

    def test_word_without_its_space(self):
        text = "2. Vertical depth embraces"
        gloss, marks = italics_only(text, [Em(3, 17)], 17, "Vertical depth", [Em(0, 8)])
        self.assertEqual(gloss, "“depth” is upright in 1955, italic here")
        self.assertEqual(marks, [Mark(9, 14)])

    def test_whole_note(self):
        text = "evolution, the age of fishes"
        a = text.index(" age")
        self.assertEqual(italics_only(text, [Em(a + 1, len(text))], a, "the", [Em(0, 3)])[0],
                         "italic in 1955, upright here")

    def test_other_words(self):
        self.assertIsNone(italics_only("the zones of", [], 9, "zone", []))

    def test_says_nothing(self):
        self.assertEqual(italics_only("a fact; b", [Em(2, 6)], 7, "fact;", [Em(0, 4)]),
                         ("", []))


if __name__ == "__main__":
    unittest.main()
