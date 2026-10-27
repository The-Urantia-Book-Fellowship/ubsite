"""The translations as the browser's voice reads them (build/speech.py
speak_ru, derive_tr; Tigran, 2026-10-27).

What a voice would trip on is changed, and nothing else: the stress mark and
the soft hyphen go, digit groups join, a power, a fraction, a degree and a few
abbreviations are said in words, a Latin list mark is its number, capitals are
capitalized, brackets go.  Then the route, /speech/<key>/<section>, on the
built database (skipped when var/ub.db has not been built).
"""

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.speech import ALLOWED_TR, heading_ru, speak_ru  # noqa: E402
from test_appendix_pages import DB, get  # noqa: E402


class SpeakRu(unittest.TestCase):
    def test_the_stress_mark_and_the_soft_hyphen_go(self):
        self.assertEqual(speak_ru("бо́ль\xadших плотно\xadстей"), "больших плотностей")

    def test_digit_groups_join(self):
        self.assertEqual(speak_ru("номер 611 121 и 100 000 лет"), "номер 611121 и 100000 лет")
        self.assertEqual(speak_ru("1\xa0354 458 км/с."), "1354458 километров в секунду.")
        self.assertEqual(speak_ru("12, 24, 48 и 365,25"), "12, 24, 48 и 365,25")

    def test_a_latin_list_mark_is_its_number(self):
        self.assertEqual(speak_ru('<span class="mark">IV.</span> Сыны Бога.'), "4. Сыны Бога.")
        self.assertEqual(speak_ru('<span class="mark">а.</span> Первые.'), "а. Первые.")

    def test_a_table_row_is_a_sentence(self):
        self.assertEqual(speak_ru('Сверхвселенные<span class="leader"></span>7'), "Сверхвселенные, 7.")

    def test_a_power_a_fraction_a_degree(self):
        self.assertEqual(speak_ru("(2 х 10<sup>27</sup>) тонн"), "(2 умножить на 10 в 27-й степени) тонн")
        self.assertEqual(speak_ru("1\xa0см<sup>3</sup> такой"), "1 кубический сантиметр такой")
        self.assertEqual(speak_ru('7 минут, 3⁠<span class="frac">1⁄8</span> секунды'),
                         "7 минут, 3 и 1/8 секунды")
        self.assertEqual(speak_ru("и 2½ минутам"), "и 2 с половиной минутам")
        self.assertEqual(speak_ru("между 75 и 90°F. От гор"), "между 75 и 90 градусов по Фаренгейту. От гор")
        with self.assertRaises(ValueError):
            speak_ru("x<sup>2</sup>")

    def test_abbreviations_keep_the_stop_that_ends_a_sentence(self):
        self.assertEqual(speak_ru("в 67 г. н.э. он"), "в 67 году нашей эры он")
        self.assertEqual(speak_ru("около 500 г. до н.э., не"), "около 500 года до нашей эры, не")
        self.assertEqual(speak_ru("к концу 68 г. н.э. В основу"), "к концу 68 года нашей эры. В основу")
        self.assertEqual(speak_ru("планеты и т. д.\xa0— происходят"), "планеты и так далее — происходят")
        self.assertEqual(speak_ru("[От лат. fīat]"), "От латинского fīat")

    def test_capitals_are_not_spelled(self):
        self.assertEqual(speak_ru("Я ЕСТЬ, и XX века"), "Я Есть, и XX века")

    def test_unknown_markup_fails(self):
        with self.assertRaises(ValueError):
            speak_ru('<span class="lettrine">В</span>')

    def test_a_heading(self):
        self.assertEqual(heading_ru(1, 1, None, "ИМЯ ОТЦА", "ДОКУМЕНТ", None, None), "1. Имя отца.")
        self.assertEqual(heading_ru(0, 1, None, "I. Божество и божественность", "Документ", None, None),
                         "1. Божество и божественность.")
        self.assertEqual(heading_ru(139, 9, 10, "9 и 10. Иаков и Иуда Алфеевы", "Текст", None, None),
                         "9 и 10. Иаков и Иуда Алфеевы.")
        self.assertEqual(heading_ru(1, 0, None, None, "ДОКУМЕНТ", "ВСЕОБЩИЙ ОТЕЦ", "Центральная вселенная"),
                         "Часть первая. Центральная вселенная. Документ 1. Всеобщий отец.")
        self.assertEqual(heading_ru(0, 0, None, None, "ДОКУМЕНТ", "ПРЕДИСЛОВИЕ", None), "Предисловие.")
        self.assertIsNone(heading_ru(41, 2, None, None, "ДОКУМЕНТ", None, None))

    def test_its_alphabet(self):
        self.assertTrue(ALLOWED_TR["ru"].match("«Да будет», — сказал он: 85% (1/8)… fīat!"))
        for odd in ("́", "\xad", "×", "°", "[", "<"):
            self.assertFalse(ALLOWED_TR["ru"].match(f"слово{odd}"), repr(odd))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Route(unittest.TestCase):
    def test_a_section_is_its_heading_then_its_paragraphs(self):
        status, headers, body = get("/speech/ud/1:1")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "no-cache")
        segs = json.loads(body)["segs"]
        self.assertEqual(segs[0], [None, "1. Имя отца."])
        self.assertEqual([s[0] for s in segs[1:]], [f"1:1.{n}" for n in range(1, len(segs))])

    def test_the_same_numbering_as_the_english(self):
        en = [s[0] for s in json.loads(get("/speech/1:1")[2])["segs"]]
        for key in ("urantia-ru", "uf-ru"):
            self.assertEqual([s[0] for s in json.loads(get(f"/speech/{key}/1:1")[2])["segs"]], en, key)

    def test_none_for_what_it_has_not(self):
        for url in ("/speech/ud/100:1", "/speech/x/1:1", "/speech/ud/1:99", "/speech/ud/x"):
            self.assertEqual(get(url)[0], 404, url)


if __name__ == "__main__":
    unittest.main()
