"""A study note's math, TeX to MathML Core (build/texmath.py).

tests/fixtures/study-math.tsv holds every `$...$` of the study edition's notes,
so the converter is held to all of them before their papers are reviewed.  To
refresh it after the edition changes, read the notes with build.readers.study
and write each note's ref and each math span, tab-separated.  And
tests/fixtures/tr-math.tsv every one of ud's translator's notes
(build/translation.py), all on the site.
"""

import pathlib
import re
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


def cut(tex: str) -> list[str]:
    """The bodies of the <math> a formula is, where a line may break in it."""
    out = texmath.convert(tex, breaks=True)
    head = f'<math xmlns="{texmath.NS}">'
    assert out.startswith(head) and out.endswith("</math>")
    return out[len(head):-len("</math>")].split(f"</math><wbr/>{head}")


class Breaks(unittest.TestCase):
    """A line may break in a formula after a relation or a binary operation at
    its outer level, TeX's rule (Tigran, 2026-11-15, of 15:7.12's sum, which ran
    off its card on a phone: "let it break a formula after a relation or a
    binary operator")."""

    INF = '<mo form="infix">{}</mo>'

    def test_after_a_relation_or_a_binary_operation(self):
        self.assertEqual(cut("2^3 - 1 = 7"),
                         ["<msup><mn>2</mn><mn>3</mn></msup>" + self.INF.format("−"),
                          "<mn>1</mn>" + self.INF.format("="), "<mn>7</mn>"])
        self.assertEqual(cut("10\\times100\\times100=1,000,000"),
                         ["<mn>10</mn>" + self.INF.format("×"), "<mn>100</mn>" + self.INF.format("×"),
                          "<mn>100</mn>" + self.INF.format("="), "<mn>1,000,000</mn>"])
        self.assertEqual(cut("n<1"), ["<mi>n</mi>" + self.INF.format("&lt;"), "<mn>1</mn>"])

    def test_a_plain_bracket_is_no_level_of_its_own(self):
        self.assertEqual(cut("7\\times(1+70)"),
                         ["<mn>7</mn>" + self.INF.format("×"),
                          '<mo stretchy="false">(</mo><mn>1</mn>' + self.INF.format("+"),
                          '<mn>70</mn><mo stretchy="false">)</mo>'])

    def test_not_in_a_group_a_script_a_root_or_a_fraction(self):
        for tex in ("{a+b}", "x_{k+1}", "10^{-5}", "N_{k-1}", "\\sqrt{a+b}", "{a+b \\over c-d}",
                    "a+b \\over c", "\\mathbf{a+b}", "\\overline{a+b}"):
            with self.subTest(tex=tex):
                self.assertEqual(cut(tex), [body(tex)])

    def test_a_sign_of_a_number_is_no_place(self):
        # It has nothing before it to operate on, and is set as a prefix.
        self.assertEqual(cut("-1"), [body("-1")])
        self.assertEqual(cut("a=-1"), ["<mi>a</mi>" + self.INF.format("="), '<mo form="prefix">−</mo><mn>1</mn>'])
        self.assertEqual(cut("(-1)^k"), [body("(-1)^k")])
        self.assertEqual(cut("a\\times -b"),
                         ["<mi>a</mi>" + self.INF.format("×"), '<mo form="prefix">−</mo><mi>b</mi>'])

    def test_the_operator_that_counts_by_tex(self):
        # Of two relations together the break is after the second; a binary
        # operation before a closing bracket, a comma or a relation is none.
        self.assertEqual(cut("x:=y"), ["<mi>x</mi><mo>:</mo>" + self.INF.format("="), "<mi>y</mi>"])
        for tex in ("(a+)", "a+,b", "a\\times=b"):
            with self.subTest(tex=tex):
                self.assertNotIn(self.INF.format("+"), "".join(cut(tex)))
                self.assertNotIn(self.INF.format("×"), "".join(cut(tex)))

    def test_no_break_after_an_operator_that_begins_the_formula(self):
        # A browser weighs nothing, as TeX does with its penalties: it would
        # leave "≈" at a line's end as readily as a word.
        self.assertEqual(cut("\\approx 10^{12}"), [body("\\approx 10^{12}")])
        self.assertEqual(cut("=5"), [body("=5")])

    def test_a_number_times_a_power_of_ten_is_one_number(self):
        for tex in ("1.77\\times 10^{14}", "2.209\\times10^9", "6\\cdot 10^{-5}"):
            with self.subTest(tex=tex):
                self.assertEqual(cut(tex), [body(tex)])
        self.assertEqual(len(cut("7^6\\times10^{33}\\approx1.2\\times10^{38}")), 3)
        self.assertEqual(cut("7^6\\times10^{33}\\approx1.2\\times10^{38}")[2], body("1.2\\times10^{38}"))
        # Powers of ten multiplied are no one number.
        self.assertEqual(len(cut("10^3\\times10^5\\times10^7=10^{15}")), 4)

    def test_a_space_typed_after_the_operator_stays_with_it(self):
        self.assertEqual(cut("a=\\,b"), ['<mi>a</mi><mo>=</mo><mspace width="0.1667em"/>', "<mi>b</mi>"])
        self.assertEqual(cut("a=\\,"), [body("a=\\,")])

    def test_every_operator_keeps_the_form_it_had(self):
        # A browser takes the form from the place: first of several in its row
        # a prefix, last a postfix.  Cut, the operator before a break is last
        # in its piece, and what follows may be first: | has all three forms in
        # the dictionary, and would have lost the spaces it was given.
        self.assertEqual(cut("a=|x|+1"),
                         ["<mi>a</mi>" + self.INF.format("="),
                          '<mo stretchy="false" form="infix">|</mo><mi>x</mi><mo stretchy="false">|</mo>'
                          + self.INF.format("+"), "<mn>1</mn>"])
        # A bracket has one form, whatever its place: nothing to say.
        self.assertTrue(cut("a+(b)")[1].startswith('<mo stretchy="false">(</mo>'))

    def test_every_operator_of_the_set_has_its_forms_on_record(self):
        ops = set(texmath.OPERATORS.values()) | {texmath.CHARS.get(c, c) for c in texmath.OPCHARS} | {"∑", "∫"}
        self.assertEqual(ops - set(texmath._FORMS), set())
        self.assertLessEqual(texmath.BINARY | texmath.RELATIONS,
                             {c for c, forms in texmath._FORMS.items() if "infix" in forms})

    def test_the_corpus_cut_is_the_corpus_whole(self):
        form = re.compile(' form="(?:prefix|infix|postfix)"')
        n = broken = 0
        for name in ("study-math.tsv", "tr-math.tsv"):
            for line in (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                ref, tex = line.split("\t", 1)
                with self.subTest(ref=ref, tex=tex):
                    whole, pieces = body(tex), cut(tex)
                    n += 1
                    broken += len(pieces) > 1
                    # Without a break asked for, never one: a figure's label.
                    self.assertNotIn("<wbr", texmath.convert(tex))
                    self.assertEqual(form.sub("", "".join(pieces)), form.sub("", whole))
                    for piece in pieces:
                        ET.fromstring(f'<math xmlns="{texmath.NS}">{piece}</math>')
                    if len(pieces) == 1:
                        self.assertEqual(pieces[0], whole)
        self.assertEqual((n, broken), (159, 68))


class Refused(unittest.TestCase):
    def test_outside_the_set(self):
        for tex in ("\\frac{a}{b}", "\\oint x", "a'", "\\mathrm{d}", "{a", "a}", "^2", "", "a^2^3",
                    "\\mathbb{1}", "{a \\over b \\over c}"):
            with self.subTest(tex=tex), self.assertRaises(texmath.MathError):
                texmath.convert(tex)


if __name__ == "__main__":
    unittest.main()
