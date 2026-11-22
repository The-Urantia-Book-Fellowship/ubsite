"""The translations beside the text, as a section page and /tr/ send them.

ROADMAP item 15, step 2 (Tigran, 2026-10-26).  A page carries which
translations each row of its text has, a fold under the row, and the
version its translations are asked for under; /tr/<paper>:<section> sends
them, every translation the section has, kept for good under that version.
None is shown unless a reader ticks it in Settings, which the page never
knows: the head script shows the folds (base.html ubTr).  Rendered through
the app as ASGI, as test_appendix_pages does; skipped when var/ub.db has not
been built.
"""

import json
import re
import sqlite3
import unittest

from test_appendix_pages import DB, ROOT, get
from ubsite import settings

RE_TF = re.compile(r'<div class="tf" data-has="([a-z -]+)"><button class="trfold" type="button"'
                   r' aria-expanded="false"></button></div>')


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    def has(self, paper: int, sec: int) -> list[str]:
        """What each row of the section has, by the database: a paragraph, or
        a block of verse its lines together, in Settings' order."""
        rows = []
        for ref, src, start in self.con.execute(
                "SELECT ref, src, verse_start FROM paragraph WHERE paper_n=? AND section_n=? ORDER BY para_n",
                (paper, sec)):
            ks = [k for (k,) in self.con.execute(
                "SELECT t.translation FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                " JOIN translation r ON r.key = t.translation WHERE p.ref = ? ORDER BY r.ord", (ref,))]
            if src == "vs" or start or not rows:
                rows.append(ks)
            else:
                rows[-1] += [k for k in ks if k not in rows[-1]]
        return [" ".join(ks) for ks in rows if ks]

    def test_each_row_carries_what_it_has(self):
        for url in ("/1:1", "/140:4", "/144:5", "/0:12", "/41:3"):
            body = get(url)[2]
            p, s = map(int, url[1:].split(":"))
            self.assertEqual(RE_TF.findall(body), self.has(p, s), url)

    def test_a_translation_with_no_paragraph_here_has_no_fold(self):
        body = get("/140:4")[2]
        self.assertTrue(RE_TF.findall(body))
        self.assertNotIn("ud", " ".join(RE_TF.findall(body)).split())

    def test_none_is_shown_until_a_reader_ticks_one(self):
        self.assertEqual(settings.defaults()["translations"], "")
        self.assertNotIn('id="ub-tr"', get("/1:1")[2])      # made by the head script, from the setting

    def test_the_page_names_its_translations_version(self):
        body = get("/1:1")[2]
        # On the section's own element, which the whole paper's page has one of
        # for each section (templates/_text.html textof).
        v = re.search(r'<section id="1:1" data-trv="([0-9a-f]{12})">', body)
        self.assertTrue(v)
        status, headers, frag = get("/tr/1:1?v=" + v[1])
        self.assertEqual(status, 200)
        self.assertEqual(headers["cache-control"], "public, max-age=31536000, immutable")
        self.assertEqual(get("/tr/1:1?v=old")[1]["cache-control"], "no-cache")


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Fragment(unittest.TestCase):
    def test_it_holds_every_translation_s_paragraphs_and_titles(self):
        status, _, frag = get("/tr/1:1")
        self.assertEqual(status, 200)
        refs = re.findall(r'<div data-k="(ud|urantia-ru)" data-ref="(1:1\.\d+)" lang="ru">', frag)
        self.assertEqual(sorted(set(k for k, _ in refs)), ["ud", "urantia-ru"])
        self.assertEqual(len(refs), 12)
        self.assertIn('<div data-k="urantia-ru" data-head="section" lang="ru">1. Имя Отца</div>', frag)
        self.assertIn('<div data-k="ud" data-head="title" lang="ru">Всеобщий Отец</div>', frag)
        self.assertIn("Из всех имён", frag)

    def test_a_translation_without_the_section_is_not_in_it(self):
        frag = get("/tr/140:4")[2]
        self.assertIn('data-k="urantia-ru"', frag)
        self.assertNotIn('data-k="ud"', frag)

    def test_a_translator_s_notes_follow_their_paragraph_as_cards(self):
        # Each the card its number opens in the fold (ub.js open()): "Note N",
        # the note, and last the translation it is of, as Settings names it.
        frag = get("/tr/1:1", raw=True)[2]
        asides = re.findall(r'<aside class="note tn" id="fn(tn_ud_1_1_\d+_\d)" data-k="ud" data-of="(1:1\.\d+)">'
                            r'(.*?)</aside>', frag, re.S)
        self.assertEqual([(k, ref) for k, ref, _ in asides],
                         [("tn_ud_1_1_3_0", "1:1.3"), ("tn_ud_1_1_3_1", "1:1.3"), ("tn_ud_1_1_5_0", "1:1.5"),
                          ("tn_ud_1_1_6_0", "1:1.6"), ("tn_ud_1_1_6_1", "1:1.6")])
        first = asides[0][2]
        self.assertIn('<a class="lbl" href="#fnreftn_ud_1_1_3_0"><x-en>Note 6</x-en>'
                      '<x-ru lang="ru">Примечание 6</x-ru></a> <span lang="ru">', first)
        self.assertIn("Ан­глий­ское сло­во you", first)
        self.assertTrue(first.rstrip().endswith(
            '<p class="src"><span lang="ru">Урантийские документы</span> <span class="nobreak">(Aivazian)</span></p>'), first)
        # Each after its paragraph, which carries its marker.
        para = frag.index('data-ref="1:1.3"')
        self.assertLess(para, frag.index('id="fnreftn_ud_1_1_3_0"'), frag.index('id="fntn_ud_1_1_3_0"'))
        self.assertLess(frag.index('id="fntn_ud_1_1_3_1"'), frag.index('data-ref="1:1.4"'))

    def test_a_note_s_sources_are_in_its_card(self):
        frag = get("/tr/41:3")[2]
        card = frag[frag.index('id="fntn_ud_41_3_2_1"'):]
        card = card[:card.index("</aside>")]
        self.assertEqual(re.findall(r'<p class="cite">\[(\d)\] ([^“]+)\. “', card),
                         [("1", "T. Aivazian"), ("2", "J. Jeans"), ("3", "Keiichi Ohnaka, Karl-Heinz Hofmann,"
                                                                                " Dieter Schertl, Gerd Weigelt, Carlo Baffa,"
                                                                                " Alain Chelli, Romain Petrov, Sylvie Robbe-Dubois")])

    def test_a_section_none_has_is_not_found(self):
        self.assertEqual(get("/tr/1:99")[0], 404)
        self.assertEqual(get("/tr/nothing")[0], 404)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        body = get("/1:1")[2]
        cls.panel = body[body.index('id="set-p-translations"'):body.index('id="set-p-listening"')]

    def test_it_lists_each_with_who_made_it_and_what_it_covers(self):
        self.assertIn('<li data-k="ud">', self.panel)
        self.assertIn('<li data-k="urantia-ru">', self.panel)
        self.assertIn('<li data-k="uf-ru">', self.panel)
        self.assertIn('<span lang="ru">Урантийские документы</span> <span class="nobreak">(Aivazian)</span>', self.panel)
        self.assertIn('<span lang="ru">Книга Урантии</span> <span class="nobreak">(USGNY)</span>', self.panel)
        self.assertIn('<span lang="ru">Книга Урантии</span> <span class="nobreak">(UF-RUS)</span>', self.panel)
        self.assertIn("translated by Tigran Aivazian · Papers 0–40, and 41, 43, 195 and 196 in part", self.panel)
        self.assertIn("the whole book", self.panel)

    def _li(self, key):
        li = self.panel[self.panel.index(f'<li data-k="{key}">'):]
        return li[:li.index("</li>")]

    def test_the_foundation_s_with_its_credit(self):
        # Its copyright, as Tigran worded it (2026-10-27), under who made it.
        li = self._li("uf-ru")
        self.assertIn("translated by the Urantia Foundation, 2024 release", li)
        self.assertIn('<span class="cr">Copyright © Urantia Foundation and used by permission</span>', li)

    def test_usgny_s_with_the_fellowship_s_credit(self):
        # Owned by the Fellowship since 2026 (Geoff, 2026-11-04), the short name
        # the Society's still; Tigran's own has no credit line.
        li = self._li("urantia-ru")
        self.assertIn("translated by Lila Dogim, corrected by Sergey Prokopov; The Urantia Book Fellowship", li)
        self.assertIn('<span class="cr">Copyright © The Urantia Book Fellowship</span>', li)
        self.assertNotIn("Greater New York", li)
        self.assertNotIn('class="cr"', self._li("ud"))

    def test_its_value_is_one_hidden_input(self):
        # The list and the English's place in it (2026-11-20): Compare's
        # switch stood under the list from 2026-11-08 to 2026-11-16, since
        # when the columns come where the window has room.
        # And the Bible's texts in order, a list of their own under The Bible
        # (2026-11-21), its hidden input `bible`.
        self.assertEqual(re.findall(r'name="(\w+)"', self.panel), ["translations", "english", "bible"])
        # The English is a row of the list, among the others until shown.
        self.assertIn('<li data-k="up"><label><input type="checkbox" value="up">', self.panel)

    def test_a_fold_is_handed_their_names(self):
        got = json.loads(re.search(r'<script type="application/json" id="ub-translations">(.*?)</script>',
                                   self.panel, re.S)[1])
        self.assertEqual([x["key"] for x in got], ["ud", "urantia-ru", "uf-ru"])
        self.assertEqual([x["label"] for x in got], ["Aivazian", "USGNY", "UF-RUS"])


class OneState(unittest.TestCase):
    """The folds open or shut together, kept (Tigran, 2026-11-20: "Folding or
    unfolding a single paragraph's translations should affect all paragraphs
    and this state should be preserved globally").  A setting with no row in
    Settings, which follows the account; ub.js opens every fold where it is
    on and the page is not in columns, and keeps the line tapped where it
    stood.  Driven in Chrome by tools/trfold_e2e.py."""

    JS = (ROOT / "ubsite" / "static" / "ub.js").read_text(encoding="utf-8")

    def test_a_setting_that_follows_the_account_with_its_tab(self):
        d = settings.defaults()
        self.assertIs(d["tropen"], False)
        self.assertIn(("tropen", "kept", "Translations", False, [], ""), settings.KEPT)
        for k in ("tropen", "trtab"):
            self.assertIn(k, settings.followed())
            self.assertNotIn(k, settings.DEVICE)

    def test_the_page_opens_them_where_it_is_not_in_columns(self):
        js = self.JS
        # As the page is drawn, and not in columns: as it loads, as listen.js
        # brings one in, as the columns give way, as a translation is ticked.
        # Where the English is first: another first text is drawn first, and
        # the folds after it (2026-11-20).
        self.assertIn("if (!secs.length || (!on && !ftxAny())) {\n      cmpUndraw(art);\n      ftxReady();\n      return trAll();", js)
        self.assertIn("return trSync().then(trAll).then(function (opened) { return drew + opened; });", js)
        trall = js[js.index("  function trAll() {"):js.index("  function trPlace(tf) {")]
        # Asked again once the translations are had: no fold drawn under columns.
        self.assertIn("if (n !== cmpN || !trOpen || cmpIs || !art.isConnected) return 0;", trall)
        # A section's translations not had, or a fold with nothing to show: shut.
        self.assertIn("if (got) shutIn(sec).forEach(function (tf) {", trall)
        # Placed again once they are open, where the page was come to at a paragraph.
        self.assertIn("if (!cmpIs && !opened) return;", js)
        self.assertIn("if (drawn) drawn.then(function (opened) { if ((cmpIs || opened) && arriveTouched <= t) arrive(true); });", js)

    def test_a_tap_asks_the_page_and_not_what_is_stored(self):
        js = self.JS
        click = js[js.index("    var ks = trKeys(tf), pl = trPlace(tf), want;"):js.index("  // The line a translation's voice is reading")]
        # Help's example of a fold is none.
        self.assertIn("if (!ks.length) return;", click)
        self.assertIn("if (want === trOpen) return void (want && trKeep(pl, trAll(), true));", click)
        self.assertIn("try { window.ubSettings.set('tropen', want); } finally { trTap = false; }", click)
        self.assertNotIn("load().tropen", click)
        # The place by the fold's line, never its .tf, which has no box on a
        # phone with the index folded (base.html ubTr).
        self.assertIn("var b = tf && tf.querySelector('.trfold');", js)
        self.assertIn("r + '>:is(.a,.tf){display:contents}'",
                      (ROOT / "ubsite" / "templates" / "base.html").read_text(encoding="utf-8"))
        # The reading shuts none where every fold is open.
        self.assertIn("if (trOpen) { trMine = null; return; }", js)

    def test_the_place_is_the_paragraph_whose_translations_stand_at_the_top(self):
        js = self.JS
        self.assertIn("if (r.height && r.bottom > top + 24) return foldOver(ps[i - 1], top + 24) || ps[i];", js)
        self.assertIn("ps = document.querySelectorAll('main :is(p.t[id], .tf.open p.rt)');", js)
        # Gone or with no box: the same paragraph found again, in its text or
        # the one now first (placeAgain, 2026-11-20), else the fold's line.
        self.assertIn("if (!pl.el.isConnected || !pl.el.getClientRects().length) {\n      el = pl.ref && placeAgain(pl);\n      if (!el) return placeBack(pl.alt);", js)

    def test_a_page_loaded_again_from_its_entry_comes_back_at_its_line(self):
        js = self.JS
        self.assertIn("try { history.replaceState(Object.assign({}, history.state, { ubAt: atNow() }), ''); } catch (e) {}", js)
        self.assertIn("if (!s || !nav || !/^(back_forward|reload)$/.test(nav.type)) return false;", js)
        self.assertIn("if (arriveTouched <= t && !atBack()) arrive(true);", js)
        # listen.js's own entries keep their own, and it is not touched.
        self.assertNotIn("ubAt", (ROOT / "ubsite" / "static" / "listen.js").read_text(encoding="utf-8"))

    def test_help_shows_its_example(self):
        h = (ROOT / "ubsite" / "templates" / "help.html").read_text(encoding="utf-8")
        self.assertIn(".helppage .eg .tf { display: block; margin: 0; }", h)
        self.assertNotIn(".helppage .eg .trfold::before", h)
        self.assertIn("Array.prototype.forEach.call(document.querySelectorAll('.tf[data-has]'), function (tf) {", self.JS)


if __name__ == "__main__":
    unittest.main()
