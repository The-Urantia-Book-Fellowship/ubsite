"""A study note's math, TeX to MathML Core (build/texmath.py).

tests/fixtures/study-math.tsv holds every `$...$` of the study edition's notes,
so the converter is held to all of them before their papers are reviewed.  To
refresh it after the edition changes, read the notes with build.readers.study
and write each note's ref and each math span, tab-separated.  And
tests/fixtures/tr-math.tsv every one of ud's translator's notes
(build/translation.py), all on the site.
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
        rows = []
        for name, n in (("study-math.tsv", 118), ("tr-math.tsv", 41)):
            got = [line.split("\t", 1) for line in
                   (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8").splitlines()
                   if line and not line.startswith("#")]
            self.assertEqual(len(got), n, name)
            rows += got
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

    def test_an_integral_and_a_set(self):
        self.assertEqual(body("\\{\\int x\\,d\\mu|n\\in \\mathbb {N}\\}"),
                         "<mo stretchy=\"false\">{</mo><mo>∫</mo><mi>x</mi><mspace width=\"0.1667em\"/>"
                         "<mi>d</mi><mi>μ</mi><mo stretchy=\"false\">|</mo><mi>n</mi><mo>∈</mo><mi>ℕ</mi>"
                         "<mo stretchy=\"false\">}</mo>")
        self.assertIn('<munderover><mo movablelimits="false">∫</mo>', body("\\int\\limits_0^1 x"))

    def test_a_times_sign_as_written(self):
        self.assertEqual(body("70×6"), "<mn>70</mn><mo>×</mo><mn>6</mn>")

    def test_a_bold_group_keeps_its_brackets(self):
        self.assertEqual(body("\\mathbf {A(r)}"), '<mi>𝐀</mi><mo stretchy="false">(</mo><mi>𝐫</mi><mo stretchy="false">)</mo>')

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

    def test_a_function_name_is_upright_with_a_thin_space_after_it(self):
        # 11:8.9's $P_2(\cos\theta)$ (2026-11-06): the name is one <mi>, so the
        # browser sets it upright, and TeX's thin space stands before a letter or
        # a number, not before a bracket, as its spacing table has it.
        self.assertEqual(body("\\cos\\theta"), '<mi>cos</mi><mspace width="0.1667em"/><mi>θ</mi>')
        self.assertEqual(body("\\cos(x)"),
                         '<mi>cos</mi><mo stretchy="false">(</mo><mi>x</mi><mo stretchy="false">)</mo>')
        self.assertEqual(body("\\cos^2\\theta"),
                         '<msup><mi>cos</mi><mn>2</mn></msup><mspace width="0.1667em"/><mi>θ</mi>')
        self.assertEqual(body("{3\\cos^2\\theta - 1 \\over 2}"),
                         '<mfrac><mrow><mn>3</mn><msup><mi>cos</mi><mn>2</mn></msup>'
                         '<mspace width="0.1667em"/><mi>θ</mi><mo>−</mo><mn>1</mn></mrow><mn>2</mn></mfrac>')
        self.assertEqual(body("\\sin\\theta"), '<mi>sin</mi><mspace width="0.1667em"/><mi>θ</mi>')
        self.assertEqual(texmath.drawn(texmath.convert("\\cos\\theta")), {"c", "o", "s", "𝜃"})

    def test_a_plain_bracket_never_stretches(self):
        # 14:1.9's $N_k=35k+(-1)^k+3$ (Tigran, 2026-11-11: "the parentheses are
        # crooked, one lower than the other"): MathML stretches a row's brackets
        # to the row and centres them, and the ) that carries the k is not one
        # of the row's, so the ( moved and the ) did not.  TeX stretches a
        # bracket only for \left and \right, which are not in the set.
        self.assertEqual(body("(-1)^k"),
                         '<mo stretchy="false">(</mo><mo form="prefix">−</mo><mn>1</mn>'
                         '<msup><mo stretchy="false">)</mo><mi>k</mi></msup>')
        for tex in ("f(a,b)", "[1-x]", "\\{a\\}", "|x|", "g(r,\\theta)={GM \\over r^2}(R/r)^2"):
            with self.subTest(tex=tex):
                out = body(tex)
                for ch in "()[]{}|":
                    self.assertNotIn(f"<mo>{ch}</mo>", out)
        # An accent's mark still stretches over what it stands on.
        self.assertEqual(body("\\overline{ab}"),
                         '<mover accent="true"><mrow><mi>a</mi><mi>b</mi></mrow><mo>¯</mo></mover>')

    def test_a_sign_with_nothing_before_it_is_no_binary_operator(self):
        # TeX's rule: at the start of its list, or after an operator, a
        # relation, an opening bracket or a comma, a sign is set close to its
        # number; MathML takes one in the middle of a row for binary.
        unary = '<mo form="prefix">−</mo>'
        for tex in ("-1", "(-1)", "P_2=-{1 \\over 2}", "10^{-5}", "(a,-b)", "a\\times -b", "a=\\,-1",
                    "{1 \\over -2}", "\\cos -x"):
            with self.subTest(tex=tex):
                self.assertIn(unary, body(tex))
        for tex in ("2^3-1", "x_{k}-1", "(a)-b", "n!-1", "3\\cos^2\\theta-1", "\\mu-1", "|-1|", "N_{k-1}"):
            with self.subTest(tex=tex):
                self.assertIn("<mo>−</mo>", body(tex))
                self.assertNotIn(unary, body(tex))
        self.assertEqual(body("\\pm 1"), '<mo form="prefix">±</mo><mn>1</mn>')
        self.assertEqual(body("a+b"), "<mi>a</mi><mo>+</mo><mi>b</mi>")

    def test_a_root_draws_the_radical_sign(self):
        # No token carries it: the browser draws √ for <msqrt> from the font,
        # so the subset is told to keep it (11:2.2's eccentricity lost it).
        self.assertIn("√", texmath.drawn(texmath.convert("\\sqrt{1-(6/7)^2}")))
        self.assertNotIn("√", texmath.drawn(texmath.convert("(6/7)^2")))


class Refused(unittest.TestCase):
    def test_outside_the_set(self):
        for tex in ("\\frac{a}{b}", "\\oint x", "a'", "\\mathrm{d}", "{a", "a}", "^2", "", "a^2^3",
                    "\\mathbb{1}", "{a \\over b \\over c}"):
            with self.subTest(tex=tex), self.assertRaises(texmath.MathError):
                texmath.convert(tex)


if __name__ == "__main__":
    unittest.main()
