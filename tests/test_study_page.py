"""A study note reaches the reader: a number in the text, its card's words after it.

Rendered through the app, as test_notes_page.py renders the 1955 readings, for
whichever papers var/ub.db has reviewed notes for (data/study/); the parts that
need a note are skipped while none is on the site.  The setting that hides
them, and a site's own defaults for it, need no note.
"""

import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_appendix_pages import DB, get  # noqa: E402

from ubsite import settings  # noqa: E402


def notes() -> list[tuple]:
    if not DB.exists():
        return []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        return con.execute(
            "SELECT p.paper_n, p.section_n, s.key, s.num, s.human_source, p.ref"
            " FROM study_note s JOIN footnote f ON f.id = s.footnote_id"
            " JOIN paragraph p ON p.id = f.paragraph_id ORDER BY p.ord, f.anchor").fetchall()


NOTES = notes()


@unittest.skipUnless(NOTES, "no study notes on the site")
class StudyPage(unittest.TestCase):
    def test_each_note_has_its_number_and_its_endnote(self):
        pages: dict[str, str] = {}
        for paper, sec, key, num, hs, ref in NOTES:
            url = f"/{paper}:{sec}"
            page = pages.get(url) or pages.setdefault(url, get(url)[2])
            with self.subTest(ref=ref, num=num):
                mark = (f'<a class="fn" href="#fn{key}" id="fnref{key}" data-k="st" data-n="{num}"'
                        + (' data-hs="1"' if hs else "") + f' aria-label="Note {num}"></a>')
                self.assertEqual(page.count(mark), 1)
                m = re.search(rf'<aside class="note st" id="fn{key}">(.*?)</aside>', page, re.S)
                self.assertTrue(m, "no endnote")
                self.assertIn(f'<a class="lbl" href="#fnref{key}"><span class="at">{ref} </span>Note {num}</a>',
                              m.group(1))
        for page in pages.values():
            self.assertEqual(page.count('<section class="notes st" aria-label="Study notes">'), 1)

    def test_a_section_without_one_has_no_block_of_them(self):
        have = {(p, s) for p, s, *_ in NOTES}
        paper, sec = next((p, s) for p in range(197) for s in range(1, 20) if (p, s) not in have)
        self.assertNotIn('class="notes st"', get(f"/{paper}:{sec}")[2])

    def test_numbers_run_from_one_in_each_paper(self):
        by_paper: dict[int, list[int]] = {}
        for paper, _, _, num, *_ in NOTES:
            by_paper.setdefault(paper, []).append(num)
        for paper, nums in by_paper.items():
            self.assertEqual(nums, list(range(1, len(nums) + 1)), paper)

    def test_never_in_the_api(self):
        import json
        paper, sec, *_ = NOTES[0]
        body = json.loads(get(f"/api/v1/paragraphs/{paper}:{sec}")[2])
        self.assertFalse([p["ref"] for p in body["paragraphs"] if 'data-k="st"' in p["html"]])


@unittest.skipUnless(NOTES, "no study notes on the site")
class ListOfNotes(unittest.TestCase):
    def test_every_note_in_the_order_of_the_book(self):
        page = get("/lists/notes")[2]
        hrefs = re.findall(r'<li><a href="/([^"#]+)#note(st[\d_]+)">', page)
        self.assertEqual([k for _, k in hrefs], [key for _, _, key, *_ in NOTES])
        self.assertEqual([r for r, _ in hrefs], [ref for *_, ref in NOTES])

    def test_named_on_the_lists_and_the_home_page_by_its_switch(self):
        lists = get("/lists")[2]
        self.assertIn('<li class="nst"><a href="/lists/notes">List of study notes</a>', lists)
        self.assertIn('<li class="n1955"><a href="/lists/1955">', lists)
        home = get("/")[2]
        self.assertIn('<span class="nst">of the <a href="/lists/notes">study notes</a>', home)
        self.assertIn('<span class="n1955">of the <a href="/lists/1955">1955 readings</a>', home)


def works() -> list[tuple]:
    if not DB.exists():
        return []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        return con.execute(
            "SELECT DISTINCT x.key, s.key FROM study_source x JOIN study_cite c ON c.source_id = x.id"
            " JOIN study_note s ON s.footnote_id = c.footnote_id").fetchall()


WORKS = works()


@unittest.skipUnless(WORKS, "no study note on the site cites a source")
class Bibliography(unittest.TestCase):
    """/lists/bibliography: every work the study notes cite, once, by its key,
    each with every note that cites it."""

    def test_each_work_once_by_its_key_with_its_notes(self):
        page = get("/lists/bibliography")[2]
        items = re.findall(r"<li><p class=\"work\">(.*?)</li>", page, re.S)
        keys = sorted({k for k, _ in WORKS}, key=str.casefold)
        self.assertEqual(len(items), len(keys))
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
            html = dict(con.execute("SELECT key, html FROM study_source"))
        for key, item in zip(keys, items):
            self.assertTrue(item.startswith(html[key] + "</p>"), key)
            cited = re.findall(r'<a href="/[^"#]+#note(st[\d_]+)">', item)
            self.assertEqual(sorted(cited), sorted(n for k, n in WORKS if k == key), key)

    def test_a_work_that_can_be_read_freely_links_its_page(self):
        """Under the work, and after it wherever a card cites it, and nowhere
        else (Tigran, 2026-10-25): its page in the library, LIBRARY.tsv's."""
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
            url = dict(con.execute("SELECT key, url FROM study_source"))
            cards = con.execute(
                "SELECT DISTINCT p.paper_n, p.section_n, x.html, x.url FROM study_source x"
                " JOIN study_cite c ON c.source_id = x.id JOIN footnote f ON f.id = c.footnote_id"
                " JOIN paragraph p ON p.id = f.paragraph_id").fetchall()
        if not any(url.values()):
            self.skipTest("no work on the site has a page in the library")
        page = get("/lists/bibliography")[2]
        items = re.findall(r"<li><p class=\"work\">(.*?)</li>", page, re.S)
        for key, item in zip(sorted(url, key=str.casefold), items):
            links = re.findall(r'<a class="lib" href="([^"]*)" target="_blank" rel="noopener">'
                               r'Read it in the Urantia Library&nbsp;↗</a>', item)
            self.assertEqual(links, [url[key]] if url[key] else [], key)
        self.assertEqual(page.count('class="lib"'), 2 * sum(1 for u in url.values() if u))
        sections: dict[tuple, str] = {}
        for paper, section, html, u in cards:
            body = sections.setdefault((paper, section), get(f"/{paper}:{section}")[2])
            linked = f'{html} <a class="lib" href="{u}" target="_blank" rel="noopener">'
            self.assertEqual(linked in body, bool(u), (paper, section, u))
            self.assertIn(html, body)

    def test_named_on_the_lists_and_the_home_page_by_its_switch(self):
        self.assertIn('<li class="nst"><a href="/lists/bibliography">Bibliography</a>', get("/lists")[2])
        n = len({k for k, _ in WORKS})
        self.assertRegex(get("/")[2], r'<span class="nst">of the\s+<a href="/lists/notes">study notes</a>'
                                      r'[^<]*, with a <a href="/lists/bibliography">bibliography</a>'
                                      rf' of {n} works they cite</span>')


class Setting(unittest.TestCase):
    def test_off_by_default_and_not_first(self):
        keys = [s[0] for s in settings.SHOW]
        self.assertEqual(keys[0], "index")
        self.assertIn("studynotes", keys)
        self.assertIs(settings.defaults()["studynotes"], False)

    def test_in_the_dialog(self):
        page = get("/")[2]
        self.assertRegex(page, r'name="studynotes"')
        self.assertIn("from The British Study Edition (ed. Tigran Aivazian)", page)

    def test_a_site_default_names_a_setting_and_keeps_its_type(self):
        for bad in ({"studynote": False}, {"studynotes": "off"}):
            with self.subTest(bad=bad):
                was = dict(settings.SITE_DEFAULTS)
                settings.SITE_DEFAULTS.clear()
                settings.SITE_DEFAULTS["read.example.org"] = bad
                try:
                    self.assertRaises(ValueError, settings.site_defaults)
                finally:
                    settings.SITE_DEFAULTS.clear()
                    settings.SITE_DEFAULTS.update(was)

    def test_the_head_script_keeps_the_base_apart(self):
        page = get("/")[2]
        self.assertIn("window.ubBase = {", page)
        self.assertIn("window.ubDefaults = Object.assign({}, window.ubBase, ", page)
        # The CSS polarity: data-<key> where a value differs from the base.
        self.assertIn("if (x !== B[k]) r.dataset[k]", page)

    def test_a_list_goes_with_its_switch(self):
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertIn(':root[data-notes="off"] .n1955, :root:not([data-studynotes="true"]) .nst,', css)

    def test_the_1955_switch_leaves_study_notes_alone(self):
        # And a translator's, in a fold, shown whenever its translation is.
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertIn(':root[data-notes="off"] :is(a.fn:not([data-k="st"]):not([data-k="tn"]), .notes:not(.st),\n'
                      '                            .pop:not(.st):not(.tn)) { display: none; }', css)
        self.assertIn(':root:not([data-studynotes="true"]) :is(a.fn[data-k="st"], .notes.st, .pop.st)', css)


if __name__ == "__main__":
    unittest.main()
