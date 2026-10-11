"""A 1955 note must differ from the text: in its words, or at least its italics.

The cases are the live ones: 102:3.5's semicolon, 112:1.7's "depth", and
59:4.18's whole note, each of which differs in italics only.
"""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.variants import says_nothing  # noqa: E402


class Em:
    kind = "em"

    def __init__(self, start, end):
        self.start, self.end = start, end


class SaysNothing(unittest.TestCase):
    def test_semicolon(self):
        text = "the consciousness of true reality; while the co-ordination"
        a = text.index(" the co-")
        s = text.index("true")
        self.assertFalse(says_nothing(text, [Em(s, s + len("true reality;"))], a,
                                      "true reality; while", [Em(0, len("true reality"))]))

    def test_word_without_its_space(self):
        self.assertFalse(says_nothing("2. Vertical depth embraces", [Em(3, 17)], 17,
                                      "Vertical depth", [Em(0, 8)]))

    def test_whole_note(self):
        text = "evolution, the age of fishes"
        a = text.index(" age")
        self.assertFalse(says_nothing(text, [Em(a + 1, len(text))], a, "the", [Em(0, 3)]))

    def test_other_words(self):
        self.assertFalse(says_nothing("the zones of", [], 9, "zone", []))

    def test_same_words_and_italics(self):
        self.assertTrue(says_nothing("a fact; b", [Em(2, 6)], 7, "fact;", [Em(0, 4)]))

    def test_an_italic_space_is_no_difference(self):
        self.assertTrue(says_nothing("a fact b", [Em(2, 7)], 7, "fact ", [Em(0, 4)]))


if __name__ == "__main__":
    unittest.main()
