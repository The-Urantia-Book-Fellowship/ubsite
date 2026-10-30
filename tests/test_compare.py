"""Compare, the text and the translations a reader has ticked side by side.

ROADMAP item 15, step 2 (Tigran, 2026-10-26).  Its address is a section's with
/compare after it, the same page byte for byte, which ub.js draws in columns
from /tr/: so a reload or a link keeps it, and no setting reaches the server.
A paper's number is the whole paper, in Compare too, every section in columns
(test_whole).  The toggle is in every page whose section has a translation, after
the Index's head and before the paper's, shown by the head script only where
one the reader has ticked has it.  Rendered through the app as ASGI, as
test_appendix_pages does; skipped when var/ub.db has not been built.
"""

import json
import re
import unittest

from test_appendix_pages import DB, get
from ubsite.stats import page_kind


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Address(unittest.TestCase):
    def test_it_is_the_same_page(self):
        for ref in ("1:1", "1:1.3-4", "0:0", "144:5", "196:3.2"):
            plain, cmp = get("/" + ref, raw=True), get(f"/{ref}/compare", raw=True)
            self.assertEqual(plain[0], 200, ref)
            self.assertEqual(cmp[0], 200, ref)
            self.assertEqual(plain[2], cmp[2], ref)

    def test_a_whole_paper_in_compare_is_the_same_page(self):
        plain, cmp = get("/1", raw=True), get("/1/compare", raw=True)
        self.assertEqual((plain[0], cmp[0]), (200, 200))
        self.assertEqual(plain[2], cmp[2])
        self.assertIn('class="cmphead"', plain[2])
        # Not a query of /N: nothing but the address says Compare.
        self.assertEqual(get("/1?compare=true")[2], get("/1")[2])

    def test_what_is_not_there_is_said_as_without_it(self):
        for ref, words in (("1:99", "Paper 1 has no section 99."), ("300", "There is no Paper 300."),
                           ("1:1.99", "There is no paragraph 1:1.99"), ("x", "There is no page at this address."),
                           ("search", "There is no page at this address.")):
            status, _, body = get(f"/{ref}/compare")
            self.assertEqual(status, 404, ref)
            self.assertIn(words, body, ref)
            self.assertIn(f"<code>/{ref}/compare</code>", body, ref)
        self.assertEqual(get("/i/god/compare")[0], 404)

    def test_the_api_answers_its_own_404(self):
        status, _, body = get("/api/compare")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "There is no such endpoint.")

    def test_a_view_in_compare_counts_for_its_section(self):
        self.assertEqual(page_kind("/1:1/compare"), ("section", "1:1"))
        self.assertEqual(page_kind("/1:1.3-4/compare"), ("section", "1:1"))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Toggle(unittest.TestCase):
    def test_it_stands_between_the_index_s_head_and_the_paper_s(self):
        body = get("/1:1")[2]
        self.assertEqual(body.count('<div class="cmphead">'), 1)
        self.assertLess(body.index('<div class="marginhead">'), body.index('<div class="cmphead">'),
                        body.index('<header class="papertop">'))
        self.assertIn('<button class="cmpbtn" type="button" aria-pressed="false">', body)
        self.assertIn('<span class="long">Compare translations</span><span class="short">Compare</span>', body)

    def test_its_words_in_russian(self):
        body = get("/1:1", raw=True)[2]
        self.assertIn('<span class="long"><x-en>Compare translations</x-en>'
                      '<x-ru lang="ru">Сравнить переводы</x-ru></span>', body)
        self.assertIn('<span class="short"><x-en>Compare</x-en><x-ru lang="ru">Сравнить</x-ru></span>', body)

    def test_the_head_script_reads_the_address_and_shows_it_where_a_ticked_one_has_the_section(self):
        body = get("/1:1", raw=True)[2]
        self.assertIn("if (/\\/compare$/.test(location.pathname)) r.classList.add('compare');", body)
        self.assertRegex(body, re.escape("article:has(' + f + ')>.cmphead{display:flex}"))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Heads(unittest.TestCase):
    """Each column's titles, as its own TeX sets them: its word for a Paper
    (\\papertxt) and the number, never over the Foreword; a section's number
    added where its \\usection adds it (ud), as written where the title
    carries it (urantia-ru)."""

    def heads(self, ref):
        frag = get("/tr/" + ref)[2]
        return re.findall(r'<div data-k="([a-z-]+)" data-head="(\w+)" lang="ru">(.*?)</div>', frag)

    def test_a_paper(self):
        # ud's title, which its \upaper writes in capitals, as its contents
        # give it (Tigran, 2026-10-27), and its section's, written in capitals
        # alone, in small capitals.
        self.assertEqual(self.heads("1:1"), [
            ("ud", "paper", "ДОКУМЕНТ 1"), ("ud", "title", "Всеобщий Отец"),
            ("ud", "author", "Божественный Советник"), ("ud", "section", '1. <span class="caps">ИМЯ ОТЦА</span>'),
            ("urantia-ru", "paper", "ТЕКСТ 1"), ("urantia-ru", "title", "Отец Всего Сущего"),
            ("urantia-ru", "author", "Божественный Советник"), ("urantia-ru", "section", "1. Имя Отца"),
            # The Foundation's: its word for a Paper as its p.paper writes it, and
            # no author line, which is its last paragraph.
            ("uf-ru", "paper", "Документ 1"), ("uf-ru", "title", "Всеобщий Отец"),
            ("uf-ru", "section", "1. Имя Отца")])

    def test_the_foreword_and_an_introduction(self):
        heads = self.heads("0:3")
        self.assertNotIn("paper", [k for _, k, _ in heads])
        self.assertIn(("ud", "title", "Предисловие"), heads)
        self.assertIn(("ud", "section", '3. <span class="caps">ПЕРВЫЙ ИСТОЧНИК И ЦЕНТР</span>'), heads)
        self.assertIn(("urantia-ru", "section", "III. Первоисточник и центр"), heads)
        self.assertNotIn("section", [k for _, k, _ in self.heads("1:0")])

    def test_a_title_its_contents_lack_stays_in_small_capitals(self):
        # ud's 195 and 196, which its contents do not give.
        self.assertIn(("ud", "title", '<span class="caps">ПОСЛЕ ПЯТИДЕСЯТНИЦЫ</span>'), self.heads("195:0"))


if __name__ == "__main__":
    unittest.main()
