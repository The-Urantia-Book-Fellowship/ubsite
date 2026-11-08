"""Compare, the text and the translations a reader has ticked side by side.

ROADMAP item 15, step 2 (Tigran, 2026-10-26), drawn by ub.js in columns from
/tr/.  A setting since 2026-11-08, Translations in parallel columns
(settings.py `compare`), in the Translations tab: until then a toggle at the
head of the text, at an address of its own, the section's with /compare after
it, which the tab kept as one moved about.  Those addresses go to the page's
own now, which the reader's settings show; one that is no page of the book is
the 404 it was.  A paper's number is the whole paper, in Compare too, every
section in columns (test_whole).  Rendered through the app as ASGI, as
test_appendix_pages does; skipped when var/ub.db has not been built.
"""

import json
import re
import unittest

from test_appendix_pages import DB, ROOT, get
from ubsite.settings import NEEDS, TRANSLATIONS
from ubsite.stats import page_kind


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Address(unittest.TestCase):
    def test_an_old_address_goes_to_the_page_for_good(self):
        for ref in ("1:1", "1:1.3-4", "0:0", "144:5", "196:3.2", "1", "007", "300", "1:99", "1:1.99",
                    "part/1", "part/9"):
            status, headers, _ = get(f"/{ref}/compare")
            self.assertEqual((status, headers.get("location")), (301, "/" + ref), ref)

    def test_what_is_no_page_of_the_book_is_said_as_before(self):
        for ref in ("x", "search"):
            status, _, body = get(f"/{ref}/compare")
            self.assertEqual(status, 404, ref)
            self.assertIn("There is no page at this address.", body, ref)
            self.assertIn(f"<code>/{ref}/compare</code>", body, ref)
        self.assertEqual(get("/i/god/compare")[0], 404)
        self.assertEqual(get("/1:1/compare/x")[0], 404)

    def test_the_api_answers_its_own_404(self):
        status, _, body = get("/api/compare")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "There is no such endpoint.")

    def test_a_view_recorded_in_compare_counts_for_its_section(self):
        self.assertEqual(page_kind("/1:1/compare"), ("section", "1:1"))
        self.assertEqual(page_kind("/1:1.3-4/compare"), ("section", "1:1"))
        self.assertEqual(page_kind("/1/compare"), ("paper", "1"))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Setting(unittest.TestCase):
    def test_a_switch_under_the_list_greyed_while_none_is_ticked(self):
        self.assertEqual([s[0] for s in TRANSLATIONS], ["translations", "compare"])
        key, kind, label, default, _, hint = TRANSLATIONS[1]
        self.assertEqual((kind, label, default), ("switch", "Translations in parallel columns", False))
        self.assertIn("narrow screen", hint)
        self.assertEqual(NEEDS["compare"], "translations")
        body = get("/1:1", raw=True)[2]
        panel = body[body.index('id="set-p-translations"'):body.index('id="set-p-listening"')]
        self.assertLess(panel.index('class="trlist trshown"'), panel.index('name="compare"'))
        self.assertIn('<label data-needs="translations"><input type="checkbox" name="compare"> '
                      '<x-en>Translations in parallel columns</x-en>'
                      '<x-ru lang="ru">Переводы в параллельных колонках</x-ru>', panel)

    def test_a_list_none_ticked_greys_what_needs_it(self):
        js = (ROOT / "ubsite/static/ub.js").read_text()
        self.assertIn("v === 'off' || v === false || v === ''", js)

    def test_no_toggle_and_no_address_kept(self):
        for url in ("/1:1", "/1", "/part/1", "/help"):
            body = get(url, raw=True)[2]
            self.assertNotIn("cmphead", body, url)
            self.assertNotIn("cmpbtn", body, url)
            self.assertNotIn("ubCompare", body, url)
            self.assertNotIn("/compare", body, url)

    def test_the_head_script_sets_its_class_from_the_setting(self):
        # The class, which ub.js cmpDraw keeps, never data-compare, which
        # changes before Compare has measured the paragraph to keep in place.
        body = get("/1:1", raw=True)[2]
        self.assertIn("if (('compare' in s ? s.compare : D.compare) === true) r.classList.add('compare');", body)
        self.assertIn(':root[data-margin="off"]:not(.compare, [data-index="off"])', body)
        self.assertIn(':root.compare .partpage .dividers', body)
        css = (ROOT / "ubsite/static/ub.css").read_text()
        self.assertNotIn("[data-compare", css)
        self.assertIn(':root.compare .grid > .row > .tf', css)
        js = (ROOT / "ubsite/static/ub.js").read_text()
        self.assertIn("document.documentElement.classList.toggle('compare', on);", js)


class SearchHit(unittest.TestCase):
    """A search's hit in a translation, /0:0.1#tr-ud, in columns: that
    translation's paragraph is marked, never the English beside it (Tigran,
    2026-11-08).  Driven in Chrome by hand; these hold the script's parts."""

    JS = (ROOT / "ubsite/static/ub.js").read_text()

    def test_the_mark_moves_to_its_column_and_back(self):
        js = self.JS
        self.assertIn("var row = p.closest('.row'), rt = row && row.querySelector('.rc[data-k=\"' + k + '\"] p.rt[data-ref=\"' + p.id + '\"]');", js)
        self.assertIn("      cmpHit();\n      // listen.js puts each translation's ▶ in its cells.", js)
        start = js.index("function cmpUndraw(art) {")
        self.assertIn("var p = document.getElementById(rt.dataset.ref);", js[start:start + 600])

    def test_the_hash_is_read_before_arrive_first_runs(self):
        js = self.JS
        self.assertLess(js.index("var TR_HASH = "), js.index("\n  arrive();\n"))
        self.assertEqual(js.count("var TR_HASH = "), 1)
        self.assertIn("focus = cmpHit() || focus;", js)

    def test_every_letting_go_takes_either_mark(self):
        js = self.JS
        self.assertIn("var HIT = 'p.t.hit, .rc p.rt.hit';", js)
        self.assertNotIn("querySelectorAll('p.t.hit'), function (p) { p.classList.remove('hit'); }", js)
        self.assertIn("querySelectorAll('p.t.hit, .rc p.rt.hit')", (ROOT / "ubsite/static/listen.js").read_text())
        css = (ROOT / "ubsite/static/ub.css").read_text()
        self.assertIn("p.t.hit, p.t.named, .rc p.rt.hit, .rc p.rt.named {", css)

    def test_placed_under_the_columns_names(self):
        self.assertIn("if (floor) scrollBy({ top: focus.getBoundingClientRect().top - floor - 12, behavior: 'instant' });", self.JS)


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
