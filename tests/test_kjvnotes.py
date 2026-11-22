"""build/kjvnotes.py: a KJV note split into its glosses, and where each stands.

Pure: no database.  The notes' forms are the copy's own (data/kjv/), and the
places the build makes of them are held in tests/test_bible.py.
"""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import kjvnotes as K                    # noqa: E402
from build.expand import Span                      # noqa: E402


def lemmas(note):
    return [g.lemma for g in K.glosses(note)]


class Glosses(unittest.TestCase):
    def test_a_note_is_its_glosses_each_from_its_lemma(self):
        gs = K.glosses("substance: or, cattle. household: or, husbandry. men: Heb. sons.")
        self.assertEqual([(g.lemma, g.text) for g in gs],
                         [("substance", "substance: or, cattle."), ("household", "household: or, husbandry."),
                          ("men", "men: Heb. sons.")])

    def test_an_ellipsis_written_either_way_ends_the_lemma(self):
        self.assertEqual(lemmas("the light from…: Heb. between the light and between the darkness."),
                         ["the light from…"])
        self.assertEqual(lemmas("the light from...: Heb. between the light and between the darkness."),
                         ["the light from..."])
        self.assertEqual(K.lemma_words("the light from…"), ["the", "light", "from"])
        self.assertEqual(K.lemma_words("Shupham…Hupham"), ["shupham"])

    def test_a_second_sentence_of_a_gloss_is_no_lemma(self):
        # After an abbreviation's stop: "Chavah" is the gloss's word.
        self.assertEqual(lemmas("Eve: Heb. Chavah: that is Living."), ["Eve"])
        self.assertEqual(lemmas("an…: or, an evil speaker (Heb. a man of tongue), a wicked man of violence, "
                                "be established in the earth: let him be hunted to his overthrow."), ["an…"])
        # Another reading's, `or, …: …`.
        self.assertEqual(lemmas("and…: or, wilt thou cease to help him? or, and wouldest cease to leave thy "
                                "business for him: thou shalt surely leave it to join with him."), ["and…"])
        # But a gloss may end in Chaldee, and the next lemma follows it.
        self.assertEqual(lemmas("Jegarsahadutha: that is, The heap of witness, Chaldee. "
                                "Galeed: that is, The heap of witness, Heb."), ["Jegarsahadutha", "Galeed"])

    def test_a_question_ends_a_gloss_as_a_stop_does(self):
        self.assertEqual(lemmas("straitened: or, shortened? uprightly: Heb. upright?"), ["straitened", "uprightly"])
        self.assertEqual(lemmas("What shall be given…: or, What shall the deceitful tongue give unto thee? "
                                "or, what shall it profit thee? done: Heb. added."),
                         ["What shall be given…", "done"])

    def test_words_before_the_first_lemma_are_its_glosss_and_a_note_with_none_is_one(self):
        gs = K.glosses("Praise ye the Lord. Praise: Heb. Hallelujah, etc.")
        self.assertEqual([(g.lemma, g.text) for g in gs], [("Praise", "Praise ye the Lord. Praise: Heb. Hallelujah, etc.")])
        gs = K.glosses("this verse is not found in most of the Greek copies.")
        self.assertEqual([(g.lemma, g.start) for g in gs], [(None, 0)])
        self.assertEqual(K.lemma_key(None), "-")
        self.assertEqual(K.lemma_key("as it were a day’s…"), "as it were a day's...")

    def test_each_gloss_keeps_its_spans_rebased_and_none_may_cross(self):
        note = "of the LORD: Heb. of it. men: Heb. sons."
        gs = K.glosses(note, [Span(7, 11, "sc"), Span(30, 34, "supplied")])
        self.assertEqual([(a, z, s.kind) for s, a, z in gs[0].spans], [(7, 11, "sc")])
        self.assertEqual([(a, z, s.kind) for s, a, z in gs[1].spans], [(5, 9, "supplied")])
        with self.assertRaises(ValueError):
            K.glosses(note, [Span(20, 28, "supplied")])


class Places(unittest.TestCase):
    V = [("text", "And when they came to Marah, they could not drink of the waters of Marah, for they were "
                  "bitter: therefore the name of it was called Marah.")]

    def test_a_lemmas_places_are_its_words_in_order_case_and_apostrophe_aside(self):
        self.assertEqual(K.occurrences("Marah", self.V), [("text", 22), ("text", 67), ("text", 132)])
        self.assertEqual(K.occurrences("the waters…", self.V), [("text", 53)])
        self.assertEqual(K.occurrences("brother's", [("text", "his brother’s wife")]), [("text", 4)])
        self.assertEqual(K.occurrences("Nachon", [("text", "to Nachon’s threshingfloor")]), [("text", 3)])
        self.assertEqual(K.occurrences("the", [("text", "thee there")]), [])

    def test_a_title_is_searched_before_its_verse(self):
        parts = [("title", "A Psalm of Asaph."), ("text", "even to such as are of a clean heart.")]
        self.assertEqual(K.occurrences("of", parts), [("title", 8), ("text", 20)])

    def test_the_places_marks_tsv_writes(self):
        self.assertEqual(K.place("3", "Marah", self.V), ("text", 132))
        self.assertIsNone(K.place("4", "Marah", self.V))
        self.assertEqual(K.place("at they could", None, self.V), ("text", 29))
        self.assertEqual(K.place("at they #3", None, self.V), ("text", 78))
        self.assertEqual(K.place("end", None, self.V), ("text", len(self.V[0][1])))
        self.assertTrue(K.places_ok("1, 2"))
        self.assertTrue(K.places_ok("at Remmonmethoar"))
        self.assertFalse(K.places_ok("first"))
        self.assertFalse(K.places_ok("1,2"))


if __name__ == "__main__":
    unittest.main()
