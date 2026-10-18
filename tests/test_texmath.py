"""A study note's math, TeX to MathML Core (build/texmath.py).

tests/fixtures/study-math.tsv holds every `$...$` of the study edition's notes,
so the converter is held to all of them before their papers are reviewed.  To
refresh it after the edition changes, read the notes with build.readers.study
and write each note's ref and each math span, tab-separated.
"""

import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import texmath  # noqa: E402

M = "{http://www.w3.org/1998/Math/MathML}"


def body(tex: str) -> str:
    out = texmath.convert(tex)
    head = f'<math xmlns="{texmath.NS}">'
    assert out.startswith(head) and out.endswith("</math>")
    return out[len(head):-len("</math>")]


class Corpus(unittest.TestCase):
    def test_every_expression_converts_to_well_formed_mathml(self):
        rows = [line.split("\t", 1) for line in
                (ROOT / "tests" / "fixtures" / "study-math.tsv").read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]
        self.assertEqual(len(rows), 118)
        for ref, tex in rows:
            with self.subTest(ref=ref, tex=tex):
                root = ET.fromstring(texmath.convert(tex))
                self.assertEqual(root.tag, M + "math")
                self.assertNotIn("\\", "".join(root.itertext()))


class Forms(unittest.TestCase):
    def test_scripts(self):
        self.assertEqual(body("2^3 - 1 = 7"),
                         "<msup><mn>2</mn><mn>3</mn></msup><mo>−</mo><mn>1</mn><mo>=</mo><mn>7</mn>")
        self.assertEqual(body("C^2_6"), "<msubsup><mi>C</mi><mn>6</mn><mn>2</mn></msubsup>")
        self.assertEqual(body("x^{\\mu}"), "<msup><mi>x</mi><mi>μ</mi></msup>")

    def test_over_is_a_fraction_of_its_group(self):
        self.assertEqual(body("{6! \\over {2!4!}}"),
                         "<mfrac><mrow><mn>6</mn><mo>!</mo></mrow>"
                         "<mrow><mn>2</mn><mo>!</mo><mn>4</mn><mo>!</mo></mrow></mfrac>")

    def test_limits_go_under_and_over(self):
        self.assertIn("<munderover><mo movablelimits=\"false\">∑</mo>", body("\\sum\\limits_{k=1}^7 N_k"))
        self.assertIn("<msubsup><mo>∑</mo>", body("\\sum_{k=1}^7 N_k"))

    def test_letters_of_a_style_are_their_own_characters(self):
        self.assertEqual(body("\\mathbb{R}"), "<mi>ℝ</mi>")
        self.assertEqual(body("\\mathcal{M}"), "<mi>ℳ</mi>")
        self.assertEqual(body("\\mathbf{p}"), "<mi>𝐩</mi>")
        self.assertEqual(body("\\Delta x"), '<mi mathvariant="normal">Δ</mi><mi>x</mi>')

    def test_numbers(self):
        self.assertEqual(body("453,313,764,407"), "<mn>453,313,764,407</mn>")
        self.assertEqual(body("2,8,18"), "<mn>2</mn><mo>,</mo><mn>8</mn><mo>,</mo><mn>18</mn>")
        self.assertEqual(body("1.408"), "<mn>1.408</mn>")

    def test_accents_and_roots(self):
        self.assertEqual(body("\\vec{F}"), '<mover accent="true"><mi>F</mi><mo>→</mo></mover>')
        self.assertEqual(body("\\sqrt{ab}"), "<msqrt><mrow><mi>a</mi><mi>b</mi></mrow></msqrt>")

    def test_markup_characters_are_escaped(self):
        self.assertEqual(body("n<1"), "<mi>n</mi><mo>&lt;</mo><mn>1</mn>")


class Refused(unittest.TestCase):
    def test_outside_the_set(self):
        for tex in ("\\frac{a}{b}", "\\int x", "a'", "\\mathrm{d}", "{a", "a}", "^2", "", "a^2^3",
                    "\\mathbb{1}", "{a \\over b \\over c}"):
            with self.subTest(tex=tex), self.assertRaises(texmath.MathError):
                texmath.convert(tex)


if __name__ == "__main__":
    unittest.main()
