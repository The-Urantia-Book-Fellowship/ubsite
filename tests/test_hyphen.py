"""A study note's Greek breaks as TeX breaks it (build/hyphen.py GREEK).

The oracle is xelatex itself: polyglossia's `greek` with variant=ancient, which
loads hyph-grc with polyglossia's default minimums, 2/3, asked with
\\showhyphens for the words below on 2026-11-05 (the run is in the module's
head).  The English and Russian models are gated against the book and the
translations (build/checks/check_hyphen.py, tools/hyphen_print.py); the Greek
has no printed page to be held to, so it is held to TeX's answer here.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from build.expand import Span  # noqa: E402
from build.hyphen import ENGLISH, GREEK, RUSSIAN, Hyphenator  # noqa: E402

# \showhyphens{...} under \selectlanguage{greek}, variant=ancient, xelatex,
# TeX Live 2026, with \lefthyphenmin=2 \righthyphenmin=3 (polyglossia.sty's
# default where a gloss sets none): one line of its log.
TEX = ("κε-καυ-στη-ρι-α-σμέ-νων οὐ-ρα-νός κα-τα-καυ-χᾶ-ται λει-τουρ-γικὰ πνεύ-ματα "
       "φα-σγα-νουρ-γός συν-έ-στη-κεν σκή-νωμα ἐρεί-δε-ται προ-χαλ-κεύει ἐμαυ-τόν "
       "ἀγα-πη-τός ἄν-θρω-πος Δί-κας πυ-θμήν ἔλεος κρί-σεως ἑλ-κύσω πάν-τας ἀπό θεός")


def broken(h: Hyphenator, w: str) -> str:
    pts = sorted(h.word(w))
    return "-".join(w[a:b] for a, b in zip([0] + pts, pts + [len(w)]))


class Greek(unittest.TestCase):
    def test_every_word_breaks_where_tex_broke_it(self):
        h = Hyphenator((), GREEK)
        for entry in TEX.split():
            with self.subTest(entry):
                self.assertEqual(broken(h, entry.replace("-", "")), entry)

    def test_a_long_pattern_applies(self):
        # hyph-grc.tex has 38 patterns of 11 to 16 letters, which a search
        # window of 10 never reached: this word broke at 1,4,6,9,11 (review of
        # 2026-11-09).
        h = Hyphenator((), GREEK)
        self.assertEqual(sorted(h.patterns("ὁποιουστινασοῦν")), [1, 4, 7, 9, 12])
        self.assertGreater(h.longest, 10)

    def test_the_minimums_are_polyglossias(self):
        # The pattern file says 1/1; polyglossia sets 2/3 where a gloss says
        # nothing, and TeX printed ἔλεος, ἀπό and θεός whole.
        self.assertEqual((GREEK.left, GREEK.right), (2, 3))

    def test_a_notes_greek_breaks_and_its_english_as_before(self):
        # The note at 9:5.7: Greek in a \textgreek span, English around it.
        text = "seared with a hot iron (κεκαυστηριασμένων, branded)."
        a = text.index("κ")
        spans = [Span(a, a + len("κεκαυστηριασμένων"), "lang", {"lang": "grc"})]
        h = Hyphenator(["seared"], ENGLISH)
        pts = h.points(text, spans)
        self.assertEqual([text[:p][-2:] + "|" + text[p:][:2] for p in pts if p > a],
                         ["κε|κα", "αυ|στ", "τη|ρι", "ρι|ασ", "ια|σμ", "μέ|νω"])
        # Outside a \textgreek span the Greek is left whole, as any non-ASCII
        # run is; inside one, a word with a combining mark is too.
        self.assertEqual([p for p in h.points(text, []) if p > a], [])
        text2 = "αὐτός and " + text
        spans2 = [Span(0, 5, "lang", {"lang": "grc"})]
        self.assertEqual([p for p in h.points(text2, spans2) if p < 6], [])

    def test_the_last_word_of_a_note_is_left_whole_in_greek_too(self):
        text = "the word πνεύματα"
        spans = [Span(9, 17, "lang", {"lang": "grc"})]
        self.assertEqual(Hyphenator((), ENGLISH).points(text, spans), [])

    def test_a_russian_note_breaks_its_greek_the_same_way(self):
        text = "слово οὐρανός здесь"
        spans = [Span(6, 13, "lang", {"lang": "grc"})]
        # сло-во by the Russian model, οὐ-ρα-νός by the Greek.
        self.assertEqual(Hyphenator((), RUSSIAN).points(text, spans), [3, 6 + 2, 6 + 4])


if __name__ == "__main__":
    unittest.main()
