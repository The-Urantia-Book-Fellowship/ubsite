"""The left rail is the whole book, closed but for the paper being read.

Every paper is there, once; only the paper being read carries its sections, and
another's come from /rail/N, kept by the browser when asked for under the
database's version.  A part's title opens its own page, /part/N: the divider,
and none of the text.  A button at its head folds it, kept as a setting that
the dialog does not show.  Rendered through the app as ASGI, as test_appendix_pages
does.  Skipped when var/ub.db has not been built.
"""

import json
import re
import sqlite3
import unittest

from test_appendix_pages import DB, get
from ubsite import l10n, settings

RE_RAIL = re.compile(r'<nav class="rail"[^>]*>.*?</nav>', re.S)
RE_PAPER = re.compile(r'href="/(\d+)"')
RE_SECTION = re.compile(r'href="/(\d+):(\d+)"')
RE_OPEN_PART = re.compile(r'<li class="part[^"]*"><details open><summary><a href="/part/\d">Part ([IV]+)\.')


def rail(url: str) -> str:
    status, _, body = get(url)
    assert status == 200, (url, status)
    m = RE_RAIL.search(body)
    assert m, f"{url}: no rail"
    return m.group(0)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Rail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.papers = [n for (n,) in con.execute("SELECT n FROM paper ORDER BY n")]
        cls.sections = {}
        for p, s in con.execute("SELECT paper_n, n FROM section ORDER BY paper_n, n"):
            cls.sections.setdefault(p, []).append(s)
        # The version a page asks for its rail's sections under: a hash of what
        # the rail draws, so that a build that changes none of it keeps it.
        cls.version = re.search(r'data-v="([0-9a-f]{12})"', rail("/101:1")).group(1)

    def test_every_paper_once_and_only_its_own_sections(self):
        r = rail("/133:2")
        self.assertEqual([int(n) for n in RE_PAPER.findall(r)], self.papers)
        secs = [(int(p), int(s)) for p, s in RE_SECTION.findall(r)]
        self.assertEqual(secs, [(133, s) for s in self.sections[133]])

    def test_open_on_the_paper_being_read(self):
        r = rail("/133:2")
        self.assertEqual(RE_OPEN_PART.findall(r), ["IV"])
        self.assertIn('<li class="here"><details open><summary><a href="/133">', r)
        self.assertEqual(r.count("<details open>"), 2)          # Part IV and Paper 133
        self.assertEqual(re.findall(r'<li class="here"><a href="/([\d:]+)"', r), ["133:2"])

    def test_the_whole_papers_page_marks_no_section(self):
        # Its rail is its sections' but for their mark (offline/pages.py keeps
        # one for the paper); ub.js marks the section being read as the page
        # scrolls.
        r = rail("/133")
        self.assertIn('<li class="here"><details open><summary><a href="/133">', r)
        self.assertEqual(re.findall(r'<li class="here"><a href="/([\d:]+)"', r), [])
        secs = [(int(p), int(s)) for p, s in RE_SECTION.findall(r)]
        self.assertEqual(secs, [(133, s) for s in self.sections[133]])

    def test_the_foreword_is_in_no_part(self):
        r = rail("/0:3")
        self.assertEqual(RE_OPEN_PART.findall(r), [])
        self.assertIn('<li class="here"><details open><summary><a href="/0">Foreword</a>', r)
        self.assertEqual(re.findall(r'<li class="here"><a href="/([\d:]+)"', r), ["0:3"])

    def test_a_papers_sections_on_demand(self):
        status, headers, body = get(f"/rail/101?v={self.version}")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "public, max-age=31536000, immutable")
        self.assertEqual([(int(p), int(s)) for p, s in RE_SECTION.findall(body)],
                         [(101, s) for s in self.sections[101]])
        self.assertNotIn('class="here"', body)

    def test_unversioned_or_stale_is_not_kept(self):
        for url in ("/rail/101", "/rail/101?v=1"):
            self.assertEqual(get(url)[1].get("cache-control"), "no-cache", url)

    def test_no_such_paper(self):
        self.assertEqual(get("/rail/197")[0], 404)

    def test_a_part_title_opens_its_page(self):
        r = rail("/133:2")
        self.assertEqual(re.findall(r'<a href="/part/(\d)">Part ([IV]+)\.', r),
                         [("1", "I"), ("2", "II"), ("3", "III"), ("4", "IV")])

    def test_a_parts_page_is_its_divider(self):
        status, _, body = get("/part/4")
        self.assertEqual(status, 200)
        self.assertIn('<p class="papernum">PART IV</p>', body)
        self.assertIn("<h1>The Life and Teachings<br>of Jesus</h1>", body)
        self.assertIn("watchcare of the Apostle Andrew.</p>", body)
        self.assertNotRegex(body, r'<p class="t[ "]')           # no paragraph of text
        self.assertIn('<a class="next" href="/120:0" rel="next" aria-label="Next section: 120:0"', body)
        r = rail("/part/4")
        self.assertEqual(RE_OPEN_PART.findall(r), ["IV"])
        self.assertEqual(r.count("<details open>"), 1)          # the part, and no paper
        self.assertIn('<li class="part here"><details open>', r)

    def test_there_are_four_parts(self):
        for n in (0, 5):
            self.assertEqual(get(f"/part/{n}")[0], 404, n)

    def test_the_button_at_its_head_folds_it(self):
        for url in ("/133:2", "/part/4"):
            r = rail(url)
            self.assertRegex(r, r'^<nav class="rail"[^>]*>\n<div class="railhead"><button class="railfold" type="button"'
                                r' aria-controls="rail-tree" aria-expanded="true"><span>Contents</span>'
                                r'</button>\n<label class="railtr" hidden><select [^>]*></select></label></div>'
                                r'\n<ol id="rail-tree">', url)

    def test_folded_is_kept_but_not_in_the_dialog(self):
        # The rail's fold, and the index's: each button is its only control;
        # the language, the flags' (2026-10-25); and a fold's tab of translations,
        # the fold's (2026-10-26); and the contents in a translation, the rail's
        # list's (2026-10-27).
        d = settings.defaults()
        self.assertEqual((d["rail"], d["margin"], d["toc"]), ("open", True, ""))
        # A language's browser voice is in it where a translation is in that language.
        ru = [{"key": "ud", "lang": "ru", "label": "Aivazian", "language": l10n.tr("Russian")}]
        shown = [it["key"] for g in settings.groups([], ru) for it in g["items"]]
        self.assertEqual(sorted(set(d) - set(shown)), ["lang", "margin", "rail", "toc", "trtab"])
        self.assertEqual(len(shown), len(set(shown)))

    def test_139_names_its_combined_section(self):
        _, _, body = get("/rail/139")
        self.assertIn('<a href="/139:9">9 and 10. ', body)

    def test_its_own_words_are_english_whatever_the_interface_s(self):
        # Until 2026-10-27 they were the interface's, and a reader of it in
        # Russian read «0. Введение» and «Часть I.» among the book's titles.
        for url in ("/139:9", "/rail/139"):
            body = get(url, raw=True)[2]
            for w in ("0. Введение", "Часть I.", "9 и 10."):
                self.assertNotIn(w, body, url)
        r = get("/1:1", raw=True)[2]
        self.assertIn('<a href="/1:0">0. Introduction</a>', r)
        self.assertIn('<a href="/part/1">Part I. The Central and Superuniverses</a>', r)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Contents(unittest.TestCase):
    """A translation's own contents, which the rail shows when a reader
    chooses it on its line (app.py toc_of, ub.js tocApply)."""

    def toc(self, key):
        status, headers, body = get(f"/rail/{key}")
        self.assertEqual(status, 200, key)
        return headers, json.loads(body)

    def test_the_foundation_s_whole(self):
        _, d = self.toc("uf-ru")
        self.assertEqual((len(d["parts"]), len(d["papers"]), len(d["sections"])), (4, 197, 1429))
        self.assertEqual(d["words"], {"intro": "0. Введение", "part": "Часть {r}.", "and": "{a} и {b}"})
        self.assertEqual((d["papers"]["1"], d["sections"]["1:1"], d["sections"]["139:9"]),
                         ("Всеобщий Отец", "Имя Отца", "Иаков и Иуда Алфеевы"))
        self.assertEqual(d["caps"], {"parts": [], "papers": [], "sections": []})

    def test_ud_s_from_its_printed_contents(self):
        # Its \upaper is in capitals, its contents are not; its sections'
        # titles, in capitals, are set in small capitals.
        _, d = self.toc("ud")
        self.assertEqual(len(d["papers"]), 45)
        self.assertEqual((d["papers"]["1"], d["parts"]["1"]),
                         ("Всеобщий Отец", "Центральная вселенная и сверхвселенные"))
        self.assertEqual(d["sections"]["1:1"], "ИМЯ ОТЦА")
        self.assertIn("1:1", d["caps"]["sections"])
        self.assertNotIn("139", d["papers"])

    def test_kept_for_good_under_its_version(self):
        from ubsite import app as A
        v = A.toc_of("uf-ru")["v"]
        self.assertIn("immutable", get(f"/rail/uf-ru?v={v}")[1].get("cache-control", ""))
        self.assertEqual(get("/rail/uf-ru")[1].get("cache-control"), "no-cache")
        self.assertIn(f'"toc": "{v}"', get("/1:1", raw=True)[2])

    def test_a_key_no_translation_has(self):
        for key in ("nothing", "UF-RUS"):
            self.assertEqual(get(f"/rail/{key}")[0], 404, key)


if __name__ == "__main__":
    unittest.main()
