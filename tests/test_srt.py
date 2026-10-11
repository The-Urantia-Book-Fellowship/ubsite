"""The SRT Committee's page is read as the page has it, and refused where it is not.

Each fixture is a row in a shape the page really uses (build/srt.py): one change,
several divided by a dashed rule or by "also...", the decision's label inside
its italics, a bare "See SRT note for ...", a misspelt label.  Anything else is
an error, never a guess.
"""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import srt  # noqa: E402

U = '<span style="text-decoration: underline;">'
RULE = '<div class="c1"> <p>- - - - - -</p> </div>'


def row(place, then, decision):
    return f"<tr><td>{place}</td><td>{then}</td><td>{decision}</td></tr>"


def place(ref, page="460.1"):
    a = "U" + ref.replace(":", "_").replace(".", "_")
    return f'<a name="{a}"></a> <a href="https://www.urantia.org/x#{a}">{ref}</a><br> ({page})'


def items(*rows):
    return srt.parse("".join(rows))


class Parse(unittest.TestCase):
    def test_one_change(self):
        [it] = items(row(place("41:4.4"),
                         f"<em>1955 text:</em> ...having become {U}sixty thousand</span> times...<br>"
                         f" <em>Review:</em> ...having become {U}forty thousand</span> times...",
                         "<em>Adopted:</em> Textual consistency supports the change."))
        self.assertEqual((it.name, it.n, it.label, it.page, it.verdict, it.see),
                         ("U41_4_4", 1, "41:4.4", "460.1", "Adopted", None))
        self.assertIn("sixty thousand", it.then)
        self.assertIn("forty thousand", it.review)
        self.assertEqual(it.why, "Textual consistency supports the change.")

    def test_label_inside_its_italics(self):
        [it] = items(row(place("42:5.1"), "<em>1955 text:</em> Y rays",
                         "<em>Adopted: Y rays</em> changed to <em>gamma rays.</em>"))
        self.assertEqual(it.verdict, "Adopted")
        self.assertEqual(it.why, "<em>Y rays</em> changed to <em>gamma rays.</em>")

    def test_see_only(self):
        [it] = items(row(place("157:1.3"), "<em>1955 text:</em> foregoing",
                         'See SRT note for <a href="#U89_3_1">89:3.1</a> above.'))
        self.assertIsNone(it.verdict)
        self.assertEqual(it.see, ("U89_3_1", "89:3.1"))

    def test_changes_divided_by_a_rule(self):
        a, b = items(row(place("134:3.3"),
                         f"<em>1955 text:</em> at {U}10:00</span><br> <em>Review:</em> ten {RULE}"
                         f"<em>1955 text:</em> at {U}3:00</span><br> <em>Review:</em> three",
                         f"<em>Adopted:</em> Spelled out. {RULE}<em>Adopted</em>"))
        self.assertEqual((a.n, b.n), (1, 2))
        self.assertEqual((a.why, b.why), ("Spelled out.", ""))

    def test_changes_divided_by_also(self):
        a, b = items(row(place("90:2.9"),
                         "<em>1955 text:</em> Teuskwatawa<br> <br> also...<br> <br>"
                         "<em>1955 text:</em> 1808",
                         "<em>Adopted:</em> A spelling.<br> <br> <br> <em>Adopted:</em> A date."))
        self.assertEqual((a.why, b.why), ("A spelling.", "A date."))

    def test_one_decision_for_two_changes(self):
        a, b = items(row(place("0:4.3"),
                         f"<em>1955 text:</em> one {RULE}<em>1955 text:</em> two",
                         "<em>Adopted:</em> Both."))
        self.assertEqual((a.why, b.why), ("Both.", "Both."))

    def test_two_rows_under_one_anchor(self):
        a, b = items(row(place("42:6.7"), "<em>1955 text:</em> less", "<em>Adopted:</em> x"),
                     row(place("42:6.7"), "<em>1955 text:</em> two", "<em>Adopted:</em> y"))
        self.assertEqual((a.n, b.n), (1, 2))

    def test_misspelt_label(self):
        [it] = items(row(place("0:1.1"), "<em>1955 text:</em> x", "<em>Informatonal:</em> y"))
        self.assertEqual(srt.VERDICTS[it.verdict][0], "informational")

    def test_head_row_skipped(self):
        self.assertEqual(items(row("<strong>1955 text</strong>", "<strong>Consideration</strong>",
                                   "<strong>Decision</strong>")), [])

    def test_unknown_label_refused(self):
        with self.assertRaises(ValueError):
            items(row(place("0:1.1"), "<em>1955 text:</em> x", "<em>Approved:</em> y"))

    def test_uneven_division_refused(self):
        with self.assertRaises(ValueError):
            items(row(place("0:1.1"), f"<em>1955 text:</em> a {RULE}<em>1955 text:</em> b {RULE}"
                                      "<em>1955 text:</em> c",
                      f"<em>Adopted:</em> x {RULE}<em>Adopted:</em> y"))

    def test_no_1955_text_refused(self):
        with self.assertRaises(ValueError):
            items(row(place("0:1.1"), "<em>Review:</em> x", "<em>Adopted:</em> y"))


class ToText(unittest.TestCase):
    def test_spans_and_entities(self):
        text, spans = srt.to_text(f"our sun&#8217;s {U}density</span> <em>is</em>", lambda h, w: h)
        self.assertEqual(text, "our sun’s density is")
        self.assertEqual([(text[s.start:s.end], s.kind) for s in spans],
                         [("density", "chg"), ("is", "em")])

    def test_a_link_is_resolved_with_its_words(self):
        seen = []

        def link(href, words):
            seen.append((href, words))
            return "/43:1.6"
        text, [s] = srt.to_text('the problem at <a href="#U43_1_6">43:1.6</a> here', link)
        self.assertEqual(seen, [("#U43_1_6", "43:1.6")])
        self.assertEqual((text[s.start:s.end], s.attr), ("43:1.6", {"href": "/43:1.6"}))

    def test_a_link_to_nowhere_is_its_words(self):
        text, spans = srt.to_text('at <a href="#x">174:0.1175</a>', lambda h, w: None)
        self.assertEqual((text, spans), ("at 174:0.1175", []))

    def test_unknown_tag_refused(self):
        with self.assertRaises(ValueError):
            srt.to_text("<table>x</table>", lambda h, w: h)


if __name__ == "__main__":
    unittest.main()
