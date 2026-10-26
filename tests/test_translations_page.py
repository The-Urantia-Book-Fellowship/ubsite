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

from test_appendix_pages import DB, get
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
        v = re.search(r'<article data-trv="([0-9a-f]{12})">', body)
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
        self.assertIn('<div data-k="ud" data-head="title" lang="ru">ВСЕОБЩИЙ ОТЕЦ</div>', frag)
        self.assertIn("Из всех имён", frag)

    def test_a_translation_without_the_section_is_not_in_it(self):
        frag = get("/tr/140:4")[2]
        self.assertIn('data-k="urantia-ru"', frag)
        self.assertNotIn('data-k="ud"', frag)

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
        self.assertIn('<span lang="ru">Урантийские документы</span> (Aivazian)', self.panel)
        self.assertIn('<span lang="ru">Книга Урантии</span> (USGNY)', self.panel)
        self.assertIn("translated by Tigran Aivazian · Papers 0–40, and 41, 43, 195 and 196 in part", self.panel)
        self.assertIn("the whole book", self.panel)

    def test_its_value_is_one_hidden_input(self):
        self.assertEqual(re.findall(r'name="(\w+)"', self.panel), ["translations"])

    def test_a_fold_is_handed_their_names(self):
        got = json.loads(re.search(r'<script type="application/json" id="ub-translations">(.*?)</script>',
                                   self.panel, re.S)[1])
        self.assertEqual([x["key"] for x in got], ["ud", "urantia-ru"])
        self.assertEqual([x["label"] for x in got], ["Aivazian", "USGNY"])


if __name__ == "__main__":
    unittest.main()
