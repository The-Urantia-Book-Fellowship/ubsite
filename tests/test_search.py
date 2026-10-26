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
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from test_appendix_pages import DB, get  # noqa: E402
from ubsite.app import TOKENIZE, _around, _snip, _unfold, fold, fts_query, mark_terms, sups  # noqa: E402

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



class MarkTerms(unittest.TestCase):
    """An index hit shows its chip with the reader's words marked, as a text hit
    does: by FTS5's own highlight(), over a table with the build's tokenizer."""

    def test_the_tokenizer_is_the_builds(self):
        sql = (ROOT / "build" / "schema" / "004_fts.sql").read_text()
        self.assertEqual(sql.count(f"tokenize='{TOKENIZE}'"), 5)

    def m(self, text, q):
        return str(mark_terms([text], q)[0])

    def test_a_word(self):
        self.assertEqual(self.m("as Creator, only in conjunction with Eternal Son", "conjunction"),
                         "as Creator, only in <mark>conjunction</mark> with Eternal Son")

    def test_each_word_and_a_phrase_whole(self):
        self.assertEqual(self.m("Saturn and Jupiter organized", "jupiter saturn"),
                         "<mark>Saturn</mark> and <mark>Jupiter</mark> organized")
        self.assertEqual(self.m("only in conjunction with the Son", '"in conjunction with"'),
                         "only <mark>in conjunction with</mark> the Son")

    def test_a_prefix_a_possessive_and_diacritics(self):
        self.assertEqual(self.m("conjunction of Jupiter", "conjunct*"),
                         "<mark>conjunction</mark> of Jupiter")
        self.assertEqual(self.m("Jesus’ words", "jesus'"), "<mark>Jesus</mark>’ words")
        self.assertEqual(self.m("the café", "cafe"), "the <mark>café</mark>")

    def test_a_word_not_shown_marks_the_others(self):
        # A hit can match one term only in a citation; its chip still shows the rest.
        self.assertEqual(self.m("Saturn and Jupiter organized", "saturn 57"),
                         "<mark>Saturn</mark> and Jupiter organized")
        self.assertEqual(self.m("Saturn and Jupiter organized", "57"),
                         "Saturn and Jupiter organized")

    def test_the_text_stays_text(self):
        self.assertEqual(self.m("6. & 7. Secrets of <Greatness>", "secrets"),
                         "6. &amp; 7. <mark>Secrets</mark> of &lt;Greatness&gt;")
        self.assertEqual(self.m("a & b", "amp"), "a &amp; b")
        self.assertEqual([str(x) for x in mark_terms(["a", "b"], "")], ["a", "b"])


class NoteHit(unittest.TestCase):
    """A 1955 reading found by search shows today's words around its ring."""

    TEXT = "It required great determination for Abraham to forgo the honors of the Egyptian court"

    def test_words_either_side_cut_where_a_word_ends(self):
        at = self.TEXT.index("forgo") + len("forgo")
        self.assertEqual(_around(self.TEXT, at),
                         ("It required great determination for Abraham to ", "forgo", "",
                          " the honors of the Egyptian court"))
        self.assertEqual(_around(self.TEXT, at, before=3, after=2),
                         ("…Abraham to ", "forgo", "", " the honors…"))

    def test_what_touches_the_ring_stays_with_it(self):
        text = "embrace the mussels, clams, oysters"
        self.assertEqual(_around(text, text.index(",")),
                         ("embrace the ", "mussels", ",", " clams, oysters"))

    def test_at_either_end(self):
        self.assertEqual(_around("one two", 0), ("", "", "one", " two"))
        self.assertEqual(_around("one two", 7), ("one ", "two", "", ""))

    def test_the_marks_after_escaping(self):
        self.assertEqual(str(_snip("Webster\u2019s & <b> \x02forego\x03")),
                         "Webster\u2019s &amp; &lt;b&gt; <mark>forego</mark>")

    def test_a_superscript_beside_a_ring(self):
        text = "a little more than 1/2,000th of the smallest atom"
        at = text.index("more") + len("more")
        self.assertEqual(_around(text, at, sup=sups("a little more than 1/2,000<sup>th</sup> of"))[3],
                         " than 1/2,000<sup>th</sup> of the smallest atom")


class Superscripts(unittest.TestCase):
    """A hit's superscripts are set where its text has them: 611,121st."""

    TEXT = "Our Creator Son is the 611,121st original concept"

    def test_where_they_stand_in_the_text(self):
        self.assertEqual(sups("a 1<sup>st</sup> &amp; <i>b</i><sup>2</sup>"), [(3, 5), (9, 10)])
        self.assertEqual(sups("no superscript"), [])

    def test_inside_a_mark_and_beside_a_cut(self):
        at = [(self.TEXT.index("st original"), self.TEXT.index(" original"))]
        self.assertEqual(str(_snip("\x04the \x02611,121st\x03 original\x04", self.TEXT, at)),
                         "\u2026the <mark>611,121<sup>st</sup></mark> original\u2026")
        self.assertEqual(str(_snip("\x04121st original concept", self.TEXT, at)),
                         "\u2026121<sup>st</sup> original concept")
        self.assertEqual(str(_snip("\x04Son is the\x04", self.TEXT, at)), "\u2026Son is the\u2026")

    def test_a_chip(self):
        self.assertEqual(str(mark_terms(["1st tower built"], "tower", [[(1, 3)]])[0]),
                         "1<sup>st</sup> <mark>tower</mark> built")


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Jump(unittest.TestCase):
    """A citation typed into the box opens where it points, a range whole."""

    def test_where_each_citation_opens(self):
        for q, to in [("86:5.14", "/86:5.14"),
                      ("86:5.14-15", "/86:5.14-15"),
                      ("86:5.14\u201315", "/86:5.14-15"),     # an en dash
                      ("86:5.14-15,17", "/86:5.14-15"),       # one range to an address
                      ("86:5.14,16", "/86:5.14"),             # a list is no range
                      ("86:5.15-14", "/86:5.15-14"),          # the page says what is wrong
                      ("0:0.0-1", "/0:0.0-1"),
                      ("76:2sec", "/76:2"),
                      ("Paper 100", "/100")]:
            with self.subTest(q=q):
                status, headers, _ = get("/search?q=" + quote(q))
                self.assertEqual((status, headers.get("location")), (303, to))

    def test_an_address_names_paragraphs_that_exist(self):
        for url in ["/86:5.1", "/86:5.17", "/86:5.14-15", "/86:5.1-17"]:
            with self.subTest(url=url):
                self.assertEqual(get(url)[0], 200)
        for url, says in [
                ("/0:0.0-1", 'There is no paragraph 0:0.0: 0:0 runs from'
                             ' <a href="/0:0.1">0:0.1</a> to <a href="/0:0.6">0:0.6</a>.'),
                ("/0:0.0", "There is no paragraph 0:0.0:"),
                ("/86:5.18", 'There is no paragraph 86:5.18: 86:5 runs from'
                             ' <a href="/86:5.1">86:5.1</a> to <a href="/86:5.17">86:5.17</a>.'),
                ("/86:5.14-99", "There is no paragraph 86:5.99:"),
                ("/86:5.15-14", "A range runs forwards, in the order of the book:"
                                ' <a href="/86:5.14-15">86:5.14-15</a>, not 86:5.15-14.')]:
            with self.subTest(url=url):
                status, _, body = get(url)
                self.assertEqual(status, 404)
                self.assertIn(says, body)


class Folded(unittest.TestCase):
    """The translations' search reads ё as е (app.py fold, 004_fts.sql), and a
    snippet made of what it read is put back into the translation's own
    letters (_unfold).  A stress mark the tokenizer drops itself."""

    def test_one_letter_for_one(self):
        self.assertEqual(fold("Всё, ЁЛКА и ель"), "Все, ЕЛКА и ель")

    def test_a_snippet_in_its_own_letters(self):
        text = "Он является объединённым изображением, и всё."
        self.assertEqual(_unfold("\x04является \x02объединенным\x03 изображением, и все\x04", text),
                         "\x04является \x02объединённым\x03 изображением, и всё\x04")
        self.assertEqual(_unfold("\x02все\x03", "все"), "\x02все\x03")
        with self.assertRaises(ValueError):
            _unfold("\x02нет\x03", "всё")

    def test_a_stress_mark_is_dropped(self):
        con = sqlite3.connect(":memory:")
        con.execute(f"CREATE VIRTUAL TABLE t USING fts5(x, tokenize='{TOKENIZE}')")
        con.execute("INSERT INTO t VALUES ('с бо\u0301льшим искажением')")
        self.assertEqual(con.execute("SELECT highlight(t, 0, '[', ']') FROM t WHERE t MATCH ?",
                                     (fts_query("большим"),)).fetchall(),
                         [("с [бо\u0301льшим] искажением",)])


def results(q: str, scope: str = "", page: str = "") -> str:
    """The <main> of a search's page, in English."""
    status, _, body = get("/search?q=" + quote(q) + (f"&in={scope}" if scope else "")
                          + (f"&page={page}" if page else ""))
    assert status == 200, status
    return body[body.index("<main"):body.index("</main>")]


def section(main: str, key: str) -> str:
    """A translation's list in a search's page."""
    a = main.index(f'<section data-tr="{key}">')
    return main[a:main.index("</section>", a)]


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Translations(unittest.TestCase):
    """Each translation beside the text has a list of its own among a search's
    results: a line to a paragraph, by ours, with what the search found in
    its words, and under them in its translator's notes (Tigran, 2026-10-26)."""

    def test_e_finds_yo_and_the_hit_keeps_it(self):
        ud = section(results("объединенным"), "ud")
        self.assertIn('<a href="/0:1.13#tr-ud">0:1.13</a> <span lang="ru">', ud)
        self.assertIn("<mark>объединённым</mark>", ud)
        self.assertNotIn("<mark>объединенным</mark>", ud)

    def test_yo_finds_e(self):
        self.assertIn("<mark>все</mark>", section(results("всё"), "urantia-ru"))

    def test_a_stress_mark_is_the_translations(self):
        self.assertIn("<mark>бо\u0301льшим</mark>", section(results("большим"), "ud"))

    def test_in_settings_order_and_only_those_that_found_something(self):
        main = results("греческого")
        self.assertLess(main.index('<div class="trhits"><section data-tr="ud">'),
                        main.index('<section data-tr="urantia-ru">'))
        self.assertNotIn("trhits", results("Hume"))
        self.assertNotIn("data-tr=", results("prayer"))

    def test_a_note_under_its_paragraph(self):
        # Only a note matched at 0:0.1: it stands beside the reference.
        self.assertIn('<li><a href="/0:0.1#tr-ud">0:0.1</a> <span class="tnhit">'
                      '<a class="lbl" href="/0:0.1#notetn_ud_0_0_1_0">Note 1</a> <span lang="ru">'
                      "Синтетическое слово «Ура\u0301нтия», возможно, происходит от <mark>греческого</mark>",
                      section(results("греческого"), "ud"))

    def test_a_superscript(self):
        self.assertIn("около 10<sup>9</sup>\u202fкм", section(results("диаметр"), "ud"))
        self.assertIn("1,392684×10<sup>6</sup>", section(results('"значение диаметра"'), "ud"))

    def test_opened_whole(self):
        main = results("бог", "urantia-ru")
        self.assertNotIn("trhits", main)
        self.assertIn('<section data-tr="urantia-ru"><h2><bdi lang="ru">Книга Урантии</bdi> (USGNY) <span>(1–100 of ', main)
        self.assertIn('<a class="next" href="/search?q=%D0%B1%D0%BE%D0%B3&amp;in=urantia-ru&amp;page=2">', main)
        self.assertIn("(101–200 of ", results("бог", "urantia-ru", "2"))
        self.assertNotIn("data-tr=", results("бог", "text"))
        # Nothing found, opened whole, says so, as with no words to find.
        for q in ("Badanon", '"'):
            self.assertIn('(0)</span></h2>\n<p class="none">nothing</p>', results(q, "ud"))

    def test_a_key_is_never_one_of_search_s_own_lists(self):
        from build import translation
        self.assertFalse(set(translation.SCOPES) & set(translation.meta()))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class StudyNotes(unittest.TestCase):
    """The study notes among a search's results, as the List of study notes
    has them, shown while Settings shows the notes (Tigran, 2026-10-26)."""

    def test_on_the_overview_only_when_something_matched(self):
        self.assertIn('<section class="bystudy"><h2>In the study notes <span>', results("Hume"))
        self.assertNotIn("In the study notes", results("Nebadonia"))

    def test_a_line(self):
        self.assertIn('<li><a href="/2:1.2#notest2_1_2_0">2:1.2</a> <span class="lbl">Note 3</span>\n'
                      '  <span class="today">…God, the infinite Father, who is also a faithful Creator.”</span>\n'
                      '  <div class="snote"><p>This paragraph is a chain of quotations from <mark>Hume</mark>',
                      results("Hume"))

    def test_opened_whole(self):
        main = results("Hume", "study")
        self.assertIn("<section><h2>In the study notes <span>", main)
        self.assertNotIn("In the text", main)
        self.assertIn('<section><h2>In the study notes <span>(0)</span></h2><p class="none">nothing</p>',
                      results("Nebadonia", "study"))


if __name__ == "__main__":
    unittest.main()
