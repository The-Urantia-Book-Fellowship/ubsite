"""The translations beside the text, read and joined to our numbering.

ROADMAP item 15, step 2 (build/translation.py).  Proved on the reader and the
expander for the cases each translation's TeX has, then on the built database
(skipped when var/ub.db has not been built): every translation is stored under
OUR paragraph, the press's numbering, wherever it numbers otherwise.
"""

import pathlib
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import translation  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import translation as reader  # noqa: E402
from test_appendix_pages import DB  # noqa: E402


def expand(key: str, body: str):
    report = Report()
    text, spans, notes = translation._expand(key, body, report, "test")
    return text, spans, notes, [p.code for p in report.problems]


def note(tex: str, odd=None, paras=("104:4.1", "2:4.2", "2:4.3")):
    """A note of ud's set as the build sets it (build/translation.py _notes)."""
    report = Report()
    text, html, cites = translation.set_note("ud", tex, set(paras), {"Jeans1": ""}, "test", report, odd=odd)
    return text, html, cites, [p.code for p in report.problems]


class TeX(unittest.TestCase):
    def test_the_stress_mark_is_kept(self):
        text, *_ = expand("ud", "Все миры призна\\'ют Отца")
        self.assertEqual(text, "Все миры признаю\u0301т Отца")  # on the letter after it, as TeX sets it

    def test_the_quotes_and_dashes_are_set(self):
        text, *_ = expand("ud", "Бог~--- <<вечный>> и ,,тот``")
        self.assertEqual(text, "Бог\u00a0— «вечный» и „тот“")

    def test_a_group_mark_takes_no_argument(self):
        # Read with the press's optional argument, 31:10.21 was lost whole (trap 2).
        text, *_, problems = expand("urantia-ru", "\\pc [Под объединенным покровительством]")
        self.assertEqual((text, problems), ("[Под объединенным покровительством]", []))

    def test_a_list_label_is_marked_and_spaced(self):
        for key, body in (("ud", "\\li{1.}Семь Главных Духов."),
                          ("urantia-ru", "\\ublistelem{1.}\\bibnobreakspace Семь Главных Духов.")):
            text, spans, *_ = expand(key, body)
            self.assertEqual(text, "1. Семь Главных Духов.", key)
            self.assertEqual([(s.start, s.end, s.kind) for s in spans], [(0, 2, "listmark")], key)

    def test_a_note_is_kept_as_written_at_its_place(self):
        text, spans, notes, _ = expand("ud", "о вседержителе\\fnst{То есть <<о вечно>>.}. Истина")
        self.assertEqual(text, "о вседержителе. Истина")
        self.assertEqual([(n.offset, n.raw) for n in notes], [(14, "То есть <<о вечно>>.")])

    def test_a_fraction_is_drawn_as_one(self):
        self.assertEqual(expand("ud", "2\\bibfrac{1}{2} минуты")[0], "2½ минуты")
        text, spans, *_ = expand("ud", "3\\bibfrac{1}{8} секунды")
        self.assertEqual(text, "3\u20601\u20448 секунды")
        self.assertEqual([(s.start, s.end, s.kind) for s in spans], [(2, 5, "frac")])

    def test_spaces_are_squeezed(self):
        text, spans, *_ = expand("ud", "вселенной  и \\bibemph{сверх}")
        self.assertEqual(text, "вселенной и сверх")
        self.assertEqual([(s.start, s.end) for s in spans], [(12, 17)])

    def test_an_unknown_macro_fails(self):
        self.assertIn("unknown-macro", expand("urantia-ru", "\\fnst{x}")[3])


class Notes(unittest.TestCase):
    """A translator's note, set as a study note is, by ud's own table."""

    def test_its_quotes_and_its_own_macros_are_set(self):
        text, html, _, problems = note("<<Бог>>~--- 700\\,000\\dt 3 и \\textbf{У}верса")
        self.assertEqual(text, "«Бог»\u00a0— 700\u202f000·3 и Уверса")
        self.assertIn("<strong>У</strong>верса", html)
        self.assertEqual(problems, [])

    def test_its_hebrew_is_turned_to_logical_order(self):
        # Written word by word reversed, as the study edition writes it (trap 32).
        html = note("\\textheb {עוֹלָם אֱלֹהֵי}")[1]
        self.assertEqual(html, '<span class="lang" lang="he" dir="rtl">אֱלֹהֵי עוֹלָם</span>')
        self.assertIn("study-hebrew", note("\\textheb {עוֹלָם {אֱלֹהֵי}}")[3])

    def test_a_section_named_by_its_first_paragraph_links_the_section(self):
        self.assertEqual(note("См. \\bibref [104:4]{p104 4:1}.")[1], 'См. <a href="/104:4">104:4</a>.')

    def test_words_that_disagree_with_their_target_fail_unless_declared(self):
        self.assertIn("study-bibref", note("\\bibref [2:4.2]{p002 4:3}")[3])
        odd = []
        _, html, _, problems = note("\\bibref [2:4.2]{p002 4:3}", odd)
        self.assertEqual((html, odd, problems), ('<a href="/2:4.3">2:4.2</a>', [("2:4.2", "2:4.3")], []))

    def test_its_math_is_mathml(self):
        html = note("$\\{\\int x^n\\,d\\mu (x)|n\\in \\mathbb {N}\\}$")[1]
        self.assertTrue(html.startswith("<math") and "<mo>∫</mo>" in html and "<mo>∈</mo>" in html, html)

    def test_its_citations_are_numbered(self):
        self.assertEqual(note("по \\cite {Jeans1} и \\cite {Jeans1}")[:3:2], ("по [1] и [1]", ["Jeans1"]))


class Reader(unittest.TestCase):
    def read(self, src: str, n: int = 0):
        report = Report()
        paper = reader.read_paper("ud", n, src, report)
        return paper, [p.code for p in report.problems]

    def test_a_title_belongs_to_the_paragraph_after_it(self):
        paper, problems = self.read("\\upaper{0}{ПРЕДИСЛОВИЕ}\n\\vs p000 12:9 Слова.\n"
                                    "\\usection{БЛАГОДАРНОСТЬ}\n\\vs p000 12:11 Ещё.\n")
        self.assertEqual(problems, [])
        self.assertEqual([h.before for h in paper.sections], [(12, 11)])

    def test_a_line_it_cannot_place_fails(self):
        self.assertIn("tr-line-unread", self.read("\\upaper{0}{X}\n\\something{else}\n")[1])

    def test_the_page_s_own_lines_are_passed_over(self):
        paper, problems = self.read("\\upaper{1}{X}\n\\uminitoc{ИМЯ}\n\\author{Y}\n\\vsetoff\n"
                                    "\\begin{quote}\n\\vs p001 0:1 Слова.\n\\end{quote}\n\\quizlink\n", 1)
        self.assertEqual((problems, len(paper.paras)), ([], 1))

    def test_its_hyphenation_list_is_read(self):
        report = Report()
        got = reader.read_hyphenation("\\begin{hyphenrules}{russian}\n\\lccode`\\==`\\- % compounds\n"
                                      "\\hyphenation{%\nне-лич-ност-ным\nИе-ру-се-ма\n}\n\\end{hyphenrules}\n",
                                      "test", report)
        self.assertEqual((got, report.problems), (["не-лич-ност-ным", "Ие-ру-се-ма"], []))


class Numbering(unittest.TestCase):
    def test_the_runs_are_of_one_length_and_section(self):
        for key, rows in translation.load_known().items():
            m, titles = translation._mapping(rows)
            self.assertEqual(len(set(v for v in m.values() if v)), len([v for v in m.values() if v]), key)
            self.assertEqual(list(titles), [(0, 12)], key)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Database(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(DB)

    def text(self, key: str, ref: str) -> str | None:
        row = self.con.execute("SELECT t.text FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                               " WHERE t.translation = ? AND p.ref = ?", (key, ref)).fetchone()
        return row and row[0]

    def src(self, key: str, ref: str) -> str | None:
        return self.con.execute("SELECT t.src_ref FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                                " WHERE t.translation = ? AND p.ref = ?", (key, ref)).fetchone()[0]

    def test_each_is_under_our_numbering_where_it_numbers_otherwise(self):
        self.assertEqual(self.src("urantia-ru", "144:5.11"), "144:5.12")
        self.assertEqual(self.src("urantia-ru", "144:5.102"), "144:5.108")
        self.assertIsNone(self.src("urantia-ru", "144:5.10"))
        self.assertEqual(self.src("ud", "31:10.22"), "31:10.23")

    def test_urantia_ru_has_the_whole_book(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM tr_paragraph WHERE translation = 'urantia-ru'"
                                          ).fetchone()[0],
                         self.con.execute("SELECT COUNT(*) FROM paragraph").fetchone()[0])

    def test_the_acknowledgment_s_heading_is_our_0_12_10(self):
        self.assertEqual(self.text("ud", "0:12.10"), "БЛАГОДАРНОСТЬ")
        self.assertEqual(self.text("urantia-ru", "0:12.10"), "Заключительные замечания")

    def test_it_is_set_in_italic_as_its_style_sets_it(self):
        # ud.sty's \usection italicises its \ackn; urantia-ru writes \bibemph itself.
        for key, want in (("ud", "<em>БЛАГОДАРНОСТЬ</em>"), ("urantia-ru", "<em>Заключительные замечания</em>")):
            got = self.con.execute("SELECT t.html_hy FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                                   " WHERE t.translation = ? AND p.ref = '0:12.10'", (key,)).fetchone()[0]
            self.assertEqual(got, want, key)

    def test_a_paragraph_reads_as_written(self):
        self.assertTrue(self.text("ud", "1:1.1").startswith("Из всех имён, под которыми Бог Отец известен"))
        self.assertIn("признаю\u0301т", self.text("ud", "1:0.3"))

    def test_no_placeholder_and_no_empty_paragraph_is_stored(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM tr_paragraph WHERE text = ''"
                                          " OR text LIKE 'Бла-бла%'").fetchone()[0], 0)
        self.assertIsNone(self.text("ud", "100:0.1"))

    def test_a_translator_s_note_is_numbered_through_its_paper(self):
        nums = [n for (n,) in self.con.execute(
            "SELECT n.num FROM tr_note n JOIN paragraph p ON p.id = n.paragraph_id"
            " WHERE n.translation = 'ud' AND p.paper_n = 1 ORDER BY p.ord, n.at")]
        self.assertEqual(nums, list(range(1, len(nums) + 1)))
        self.assertGreater(len(nums), 5)

    def notes(self, ref: str) -> list[tuple]:
        return self.con.execute(
            "SELECT n.num, n.at, n.key, n.text, n.html_hy FROM tr_note n JOIN paragraph p ON p.id = n.paragraph_id"
            " WHERE n.translation = 'ud' AND p.ref = ? ORDER BY n.num", (ref,)).fetchall()

    def test_a_note_s_marker_stands_where_its_fnst_stood(self):
        got = self.notes("1:1.3")
        self.assertEqual([(n, key) for n, _, key, *_ in got], [(6, "tn_ud_1_1_3_0"), (7, "tn_ud_1_1_3_1")])
        text = self.text("ud", "1:1.3")
        self.assertEqual(text[:got[0][1]], "Когда ты")
        (hy,) = self.con.execute("SELECT t.html_hy FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                                 " WHERE t.translation = 'ud' AND p.ref = '1:1.3'").fetchone()
        self.assertTrue(hy.startswith('Ко\u00adгда ты<a class="fn" href="#fntn_ud_1_1_3_0" id="fnreftn_ud_1_1_3_0"'
                                      ' data-k="tn" data-n="6" aria-label="Note 6"></a> на\u00adко\u00adнец'), hy[:200])

    def test_a_note_s_hebrew_is_in_logical_order(self):
        self.assertIn("Исайя\u00a040:28: אֱלֹהֵי עוֹלָם", self.notes("1:1.6")[0][3])

    def test_a_note_links_the_book(self):
        self.assertIn('<a href="/2:4.3">2:4.2</a>', self.notes("0:1.15")[0][4])   # a slip, declared
        self.assertIn('<a href="/158:1.6-7">158:1.6–7</a>', self.notes("35:1.2")[0][4])
        self.assertIn('<a href="/104:4">104:4</a>', self.notes("10:5.7")[0][4])

    def test_a_note_s_math_is_mathml(self):
        html = self.notes("19:5.7")[0][4]
        self.assertIn("<mo>∫</mo>", html)
        self.assertIn("<mo>∈</mo>", html)

    def test_a_note_s_sources_are_its_paper_s_in_the_order_it_cites_them(self):
        got = self.con.execute(
            "SELECT x.key, x.paper_n FROM tr_cite c JOIN tr_note n ON n.id = c.note_id"
            " JOIN tr_source x ON x.id = c.source_id WHERE n.key = 'tn_ud_41_3_2_1' ORDER BY c.ord").fetchall()
        self.assertEqual(got, [("Aivazian1", 41), ("Jeans1", 41), ("Ohnaka1", 41)])
        self.assertIn("[1]", self.notes("41:3.2")[1][3])


if __name__ == "__main__":
    unittest.main()
