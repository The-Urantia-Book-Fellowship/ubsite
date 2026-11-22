"""The Bible (data/kjv/, data/rsb/, build/bible.py, build/versify.py,
build/bibleref.py, ubsite/bible.py; 2026-11-21): the copies and the table of
numbers, the database, the study notes' Bible references made links, the pages
and their addresses, the Synodal's lines and its own numbers, and search.

    .venv/bin/python -m unittest discover -s tests -p test_bible.py

The database is var/bible.db, as `make bible` builds it; the notes' links are
in var/ub.db, as `make data` builds it.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import subprocess
import sys
import tomllib
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from build import bible, bibleref, versify          # noqa: E402
from build.problems import Report                  # noqa: E402
from build.render import strip_tags                # noqa: E402
from test_appendix_pages import get                # noqa: E402

KJV = ROOT / "var" / "bible.db"
UB = ROOT / "var" / "ub.db"


class Copy(unittest.TestCase):
    """data/kjv/: the edition's KJV, its corrections and the witness's lines."""

    def test_the_copy_is_the_edition_mended_and_merged_as_listed(self):
        study = ROOT.parent / "urantia-study-edition"
        if not study.is_dir():
            self.skipTest("the study edition is not on this machine")
        r = subprocess.run([sys.executable, "-m", "tools.kjv.convert", "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_each_book_is_its_chapters_and_verses_in_order(self):
        books = (bible.KJV / "books.tsv").read_text(encoding="utf-8").split("\n")
        self.assertEqual(books[0].split("\t"), bible.KJV_BOOK)
        abbrs = [line.split("\t")[1] for line in books[1:] if line]
        self.assertEqual(len(abbrs), 66)
        self.assertEqual((abbrs[0], abbrs[38], abbrs[39], abbrs[-1]), ("Gen", "Mal", "Mat", "Rev"))
        for a in abbrs:
            rows = [line.split("\t") for line in (bible.KJV / f"{a}.tsv").read_text(encoding="utf-8").split("\n")[1:]
                    if line]
            with self.subTest(book=a):
                self.assertTrue(all(len(r) == len(bible.KJV_VERSE) for r in rows))
                at = [(int(r[0]), int(r[1])) for r in rows]
                self.assertEqual(at, sorted(at))
                self.assertTrue(all(r[2] in ("", "¶") for r in rows))
                # Only the two macros the copy keeps.
                for r in rows:
                    left = re.sub(r"\\(?:bibemph|textsc)\{[^{}\\]*\}", "", "".join(r[3:]))
                    self.assertNotRegex(left, r"[\\{}]", r)

    def test_a_correction_and_a_line_of_the_witness_say_why(self):
        for name, n in (("corrections.tsv", 7), ("witness.tsv", 6)):
            lines = (bible.KJV / name).read_text(encoding="utf-8").split("\n")
            for line in lines[1:]:
                if line:
                    cells = line.split("\t")
                    self.assertEqual(len(cells), n, line)
                    self.assertTrue(cells[-1].strip(), line)


@unittest.skipUnless(KJV.exists(), "var/bible.db is not built (make bible)")
class Database(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{KJV}?mode=ro", uri=True)
        cls.want = tomllib.loads((ROOT / "verify" / "expectations.toml").read_text())["bible"]

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def one(self, q, *a):
        return self.con.execute(q, a).fetchone()[0]

    def verse(self, version, abbr, c, v, col="html", kind="verse"):
        return self.one(f"SELECT v.{col} FROM bible_verse v JOIN bible_book b ON b.id = v.book WHERE v.version = ?"
                        " AND b.abbr = ? AND v.chapter = ? AND v.verse = ? AND v.kind = ?", version, abbr, c, v, kind)

    def test_its_counts_are_the_expected(self):
        meta = dict(self.con.execute("SELECT key, value FROM bible_meta"))
        for k, v in self.want.items():
            if k in meta:
                self.assertEqual(int(meta[k]), v, k)
        self.assertEqual(meta["data"], bible.digest(), "var/bible.db is not of data/ as it is")

    def test_a_verse_sets_its_supplied_words_the_lord_and_its_notes_mark(self):
        h = self.verse("kjv", "Gen", 1, 4, "html_hy")
        self.assertIn('<span class="supplied">it was</span>', h)
        self.assertIn('<a class="fn" href="#fnGen1_4" id="fnrefGen1_4" data-k="kjv"', h)
        self.assertIn("\u00ad", h)                       # hyphenated: di­vided
        self.assertEqual(strip_tags(h).replace("\u00ad", ""),
                         "And God saw the light, that it was good: and God divided the light from the darkness.")
        self.assertIn('<span class="sc">Lord</span>', self.verse("kjv", "Gen", 2, 4))

    def test_titles_letters_and_subscriptions_stand_apart(self):
        # A KJV psalm's title is a row 0 of its own (2026-11-21), beside the
        # Synodal's title, a numbered verse; a letter of Psalm 119 its verse's head.
        self.assertEqual(self.verse("kjv", "Psa", 3, 0, "text", "title"), "A Psalm of David, when he fled from Absalom his son.")
        self.assertTrue(self.verse("kjv", "Psa", 3, 1, "text").startswith("Lord, how"))
        self.assertEqual(self.verse("kjv", "Psa", 119, 9, "head"), "BETH.")
        self.assertTrue(self.verse("kjv", "Rom", 16, 27, "after").startswith("Written to the Romans from Corinthus"))

    def test_a_note_ends_with_one_stop_and_its_ellipsis_is_one_character(self):
        self.assertEqual(self.one("SELECT COUNT(*) FROM bible_note n JOIN bible_verse v ON v.id = n.verse_id"
                                  " WHERE v.version = 'kjv' AND (n.text LIKE '%?.%' OR n.text LIKE '%etc..%')"), 0)
        self.assertEqual(self.one("SELECT n.text FROM bible_note n WHERE n.key = 'Gen1_4'"),
                         "the light from…: Heb. between the light and between the darkness.")

    def test_the_synodal_sets_its_stress_its_notes_where_they_stand_and_its_paragraphs(self):
        # \acc as the letter and U+0301; a note's mark at its place in the
        # verse; \rsbpar inside a verse a mark of its own, with its space.
        self.assertIn("что\u0301 есть", self.verse("rsb", "1Jo", 2, 8, "text"))
        self.assertIn("та\u0301к поступайте", self.verse("rsb", "Mat", 7, 12, "text"))
        h = self.verse("rsb", "Mat", 3, 12)
        self.assertTrue(h.startswith('лопата<a class="fn" href="#fnrMat3_12_1" id="fnrefrMat3_12_1" data-k="rsb"'), h)
        self.assertEqual(self.one("SELECT text FROM bible_note WHERE key = 'rMat3_12_1'"), "Которою веют хлеб.")
        self.assertIn('огорчением].<span class="pm"></span> Сынов', self.verse("rsb", "Gen", 35, 22))
        # The non-canonical books between the testaments, in English and Russian.
        self.assertEqual([r for r in self.con.execute("SELECT abbr, en FROM bible_book WHERE id IN (39, 40, 50, 51)")],
                         [("Mal", "Malachi"), ("2Ez", "1 Esdras"), ("3Ez", "2 Esdras"), ("Mat", "Matthew")])

    def test_rows_join_the_verses_that_are_the_same_words(self):
        row = lambda version, abbr, c, v: self.one(
            "SELECT v.rc || '.' || v.rv || '.' || v.rs FROM bible_verse v JOIN bible_book b ON b.id = v.book"
            " WHERE v.version = ? AND b.abbr = ? AND v.chapter = ? AND v.verse = ? AND v.alt = 0"
            " ORDER BY v.kind = 'title' LIMIT 1", version, abbr, c, v)
        self.assertEqual(row("rsb", "Psa", 22, 1), "23.1.0")              # the Greek's numbering
        self.assertEqual(row("rsb", "Psa", 22, 0), "23.0.0")              # its title, beside the KJV's
        self.assertEqual(row("rsb", "Psa", 9, 22), "10.1.0")
        self.assertEqual(row("rsb", "Dan", 3, 24), "3.23.1")              # the Greek's alone, after 3:23
        self.assertEqual(row("rsb", "Dan", 3, 91), "3.24.0")
        self.assertEqual(row("rsb", "Rom", 14, 24), "16.25.0")            # the doxology where the KJV has it
        self.assertEqual((row("kjv", "2Co", 13, 12), row("kjv", "2Co", 13, 13)), ("13.12.0", "13.12.0"))
        self.assertEqual(row("rsb", "Psa", 151, 1), "151.1.0")            # a chapter of its own
        self.assertEqual(row("rsb", "Est", 0, 0), "1.0.1")                # an opening, at the head of chapter 1
        self.assertEqual(row("rsb", "Tob", 1, 3), "1.3.0")                # a book of its own, its own numbers


class Table(unittest.TestCase):
    """data/rsb/versification.tsv (build/versify.py)."""

    def test_its_lines_read(self):
        rules = versify.read(bible.TABLE_FILE)
        kinds = {r["kind"] for r in rules}
        self.assertEqual(kinds, {"moved", "after", "own", "kjvonly"})
        self.assertEqual([r for r in rules if r["kind"] == "kjvonly"][0]["kjv"], [(1, 1)])   # Sol 1:1

    def test_a_verse_in_two_rows_or_in_none_fails(self):
        syn, kjv = [(1, 1), (1, 2)], [(1, 1), (1, 2), (1, 3)]
        with self.assertRaises(SystemExit):
            versify.place("Xyz", syn, kjv, [])                         # KJV 1:3 is no one's
        rules = [{"kind": "kjvonly", "book": "Xyz", "syn": [], "kjv": [(1, 3)], "line": 2}]
        sr, kr = versify.place("Xyz", syn, kjv, rules)
        self.assertEqual((sr[(1, 2)], kr[(1, 3)]), ((1, 2, 0), (1, 3, 0)))
        rules.append({"kind": "moved", "book": "Xyz", "syn": [(1, 2)], "kjv": [(1, 2), (1, 3)], "line": 3})
        with self.assertRaises(SystemExit):
            versify.place("Xyz", syn, kjv, rules)                      # 1:3 said twice

    def test_the_table_places_every_verse_of_both(self):
        r = subprocess.run([sys.executable, "-m", "tools.rsb.versify", "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_synodal_copy_is_its_edition(self):
        if not (ROOT.parent / "russian-synodal-bible").is_dir():
            self.skipTest("the Synodal's edition is not on this machine")
        r = subprocess.run([sys.executable, "-m", "tools.rsb.convert", "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipUnless(KJV.exists(), "var/bible.db is not built (make bible)")
class References(unittest.TestCase):
    """build/bibleref.py on the forms the notes write, and some it refuses."""

    @classmethod
    def setUpClass(cls):
        cls.r = bibleref.Recognizer.load()

    def links(self, text, at="1:1.1", known=None, carry=True):
        if known is not None:
            self.r.known = known
        rep = Report()
        got = [(text[a:b], h) for a, b, h in self.r.find(text, [], "test", at, rep, carry)]
        return got, sorted({p.code for p in rep.problems})

    def test_the_forms_the_notes_write(self):
        T = "\u00a0"                                  # a tie, `~`, as the note's text has it
        cases = {
            f"Psalms{T}104:1–2": [(f"Psalms{T}104:1–2", "/bible/Psa/104:1-2")],
            f"Isaiah{T}40:12, 22 and{T}26": [(f"Isaiah{T}40:12", "/bible/Isa/40:12"), ("22", "/bible/Isa/40:22"),
                                            ("26", "/bible/Isa/40:26")],
            f"John{T}1:1 and 14": [(f"John{T}1:1", "/bible/Joh/1:1"), ("14", "/bible/Joh/1:14")],
            f"1{T}Timothy{T}1:17 and 6:16": [(f"1{T}Timothy{T}1:17", "/bible/1Ti/1:17"), ("6:16", "/bible/1Ti/6:16")],
            f"Nehemiah{T}9:6 and 1{T}Samuel{T}2:2": [(f"Nehemiah{T}9:6", "/bible/Neh/9:6"),
                                                    (f"1{T}Samuel{T}2:2", "/bible/1Sa/2:2")],
            f"Luke{T}23:43, 2{T}Corinthians{T}12:4": [(f"Luke{T}23:43", "/bible/Luk/23:43"),
                                                     (f"2{T}Corinthians{T}12:4", "/bible/2Co/12:4")],
            f"Daniel{T}7:9–10; again at 7:13 and 7:22": [(f"Daniel{T}7:9–10", "/bible/Dan/7:9-10"),
                                                         ("7:13", "/bible/Dan/7:13"), ("7:22", "/bible/Dan/7:22")],
            f"1{T}Corinthians{T}1:9 or 10:13": [(f"1{T}Corinthians{T}1:9", "/bible/1Co/1:9"), ("10:13", "/bible/1Co/10:13")],
            f"Jude{T}24": [(f"Jude{T}24", "/bible/Jud/1:24")],
            "Psalm 23": [("Psalm 23", "/bible/Psa/23")],
            f"Job{T}9:11 (p.{T}459)": [(f"Job{T}9:11", "/bible/Job/9:11")],
            f"Romans{T}1:20: “For the invisible things": [(f"Romans{T}1:20", "/bible/Rom/1:20")],
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.links(text, carry=False), (want, []))

    def test_what_is_no_reference(self):
        for text in ("John names the seven Spirits", "Job’s comforters", "the Psalm’s verse", "chapter 58",
                     "Num. 23. 19", "This seems to be Rev 5:6"):
            with self.subTest(text=text):
                self.assertEqual(self.links(text, carry=False), ([], []))

    def test_what_fails_the_build(self):
        self.assertEqual(self.links("John 3.16", carry=False)[1], ["study-bible-unread"])
        self.assertEqual(self.links("Genesis 51:1", carry=False)[1], ["study-bible-ref"])
        self.assertEqual(self.links("Genesis 1:40", carry=False)[1], ["study-bible-ref"])
        self.assertEqual(self.links("Psalms 23:4–2", carry=False)[1], ["study-bible-ref"])

    def test_a_reference_with_no_book_is_linked_only_as_listed(self):
        text = "Matthew 22:39, and the first (22:37–38)."
        self.assertEqual(self.links(text, at="16:9.8", known={})[1], ["study-bible-carried"])
        got = self.links(text, at="16:9.8", known={("16:9.8", "22:37--38", 1): "Mat 22:37-38"})
        self.assertEqual(got, ([("Matthew 22:39", "/bible/Mat/22:39"), ("22:37–38", "/bible/Mat/22:37-38")], []))
        got = self.links(text, at="16:9.8", known={("16:9.8", "22:37--38", 1): "-"})
        self.assertEqual(got, ([("Matthew 22:39", "/bible/Mat/22:39")], []))
        # Never in a note's `corrects`: Block's slips.
        self.assertEqual(self.links("Psalms 145:17 for his 145:7", known={}, carry=False),
                         ([("Psalms 145:17", "/bible/Psa/145:17")], []))

    def test_the_list_of_references_carried_is_read(self):
        known = bibleref.read_known()
        self.assertEqual(known[("11:3.1", "2:12", 1)], "Zec 2:12")
        self.assertEqual(known[("16:4.1", "5:6", 1)], "-")


@unittest.skipUnless(UB.exists() and KJV.exists(), "the databases are not built (make data)")
class Notes(unittest.TestCase):

    def test_every_link_of_a_note_to_the_kjv_names_a_verse_it_has(self):
        ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
        hrefs = [h for (html,) in ub.execute("SELECT html FROM footnote WHERE kind = 'study'")
                 for h in re.findall(r'href="(/bible/[^"]+)"', html)]
        ub.close()
        self.assertGreater(len(hrefs), 300)
        last = bible.verses_of()
        for h in set(hrefs):
            m = re.fullmatch(r"/bible/([1-3]?[A-Z][a-z]{1,2})/(\d+)(?::(\d+)(?:-(\d+))?)?", h)
            with self.subTest(href=h):
                self.assertIsNotNone(m)
                chs = last[m[1]]
                self.assertIn(int(m[2]), chs)
                for v in (m[3], m[4]):
                    if v:
                        self.assertTrue(1 <= int(v) <= chs[int(m[2])])


@unittest.skipUnless(UB.exists() and KJV.exists(), "the databases are not built (make data)")
class FromTheBiblesSide(unittest.TestCase):
    """A verse's page names the paragraphs whose study notes cite it
    (ub.db bible_cite, build/bibleref.py store; Tigran, 2026-11-21), in the
    row's margin, so that it stays whichever text is shown."""

    def test_every_link_of_a_note_is_a_citation_of_its_verses(self):
        ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
        links = sum(len(bibleref.RE_HREF.findall(h)) for (h,) in
                    ub.execute("SELECT html FROM footnote WHERE kind = 'study'"))
        n = ub.execute("SELECT COUNT(*) FROM bible_cite").fetchone()[0]
        ub.close()
        self.assertEqual(n, links)

    def test_a_verse_names_the_paragraphs_whose_notes_cite_it(self):
        _, _, b = get("/bible/Isa/40")
        row12 = b.split('data-row="v12">')[1].split('data-row="v13"')[0]
        # An orange dot at the verse's end, a note's mark, its card the line
        # .ka, which scripts hide (Tigran, 2026-11-21: "even a small line
        # under each row is a waste"; "the orange dot").
        self.assertIn('aria-label="Translators’ note"></a><a class="fn" data-k="kc" href="#kcv12"'
                      ' aria-label="Study notes at"></a></p>', row12)
        self.assertIn('<div class="ka" id="kcv12"><p class="kvc"><span class="lbl">Study notes at</span>'
                      ' <a href="/1:5.3">1:5.3</a>', row12)
        self.assertNotIn('class="kvc"', b.split('data-row="v11">')[1].split('data-row="v12"')[0])
        css = (ROOT / "ubsite/static/ub.css").read_text()
        self.assertIn(".js main.bible .ka { display: none; }", css)
        # No margin's track beside the Bible's text, nor asked of the columns.
        self.assertNotIn("minmax(0, 26ch)", css[css.index(".krow { display: grid;"):css.index("article.bcmp .bnames {")])
        self.assertIn("article:not(.partpage, .biblech) > .cprobe", css)
        # A run of verses names each of them: Psalms 104:1-2.
        _, _, b = get("/bible/Psa/104")
        for v in (1, 2):
            self.assertIn('<a href="/1:0.1">1:0.1</a>', b.split(f'data-row="v{v}">')[1].split(f'data-row="v{v + 1}"')[0])

    def test_a_book_and_a_chapter_cited_are_marked(self):
        _, _, b = get("/bible")
        self.assertIn('<li class="cited"><a href="/bible/Isa">', b)
        self.assertIn('<li><a href="/bible/Nah">', b)
        self.assertRegex(b, r'<p class="kjvcite">An orange dot at a verse’s end opens the paragraphs')
        _, _, b = get("/bible/Isa")
        self.assertIn('<li class="cited"><a href="/bible/Isa/40">40</a></li>', b)


@unittest.skipUnless(KJV.exists(), "var/bible.db is not built (make bible)")
class ContentsNumbers(unittest.TestCase):
    # The Contents number a book's chapters as the first text does (Tigran,
    # 2026-11-21: "match the Contents to the actual books"): both lists where
    # the Synodal numbers them otherwise, CSS showing one.

    def test_the_books_the_synodal_numbers_otherwise(self):
        from ubsite import bible as B
        got = {b["abbr"] for b in B.books() if B.numbers(b)}
        self.assertEqual(got, {"Num", "Jos", "1Sa", "Job", "Psa", "Ecc", "Sol", "Dan", "Hos", "Jon"})
        psa = B.numbers(B.book("Psa"))
        h = dict(psa["list"])
        self.assertEqual(len(psa["list"]), 151)
        self.assertEqual((h[9], h[10], h[22], h[113], h[114], h[115], h[147], h[148], h[151]),
                         ("/bible/Psa/9", "/bible/Psa/11", "/bible/Psa/23", "/bible/Psa/114", "/bible/Psa/116",
                          "/bible/Psa/116#s115-0", "/bible/Psa/147#s147-0", "/bible/Psa/148", "/bible/Psa/151"))
        self.assertEqual([psa["here"][c] for c in (9, 10, 11, 23, 116, 117, 151)], [9, 9, 10, 22, 114, 116, 151])
        num = dict(B.numbers(B.book("Num"))["list"])
        self.assertEqual((num[12], num[13], num[14]), ("/bible/Num/12", "/bible/Num/12#v16", "/bible/Num/14"))
        self.assertIsNone(B.numbers(B.book("Gen")))
        self.assertIsNone(B.numbers(B.book("Est")))     # its prologue, 0:0, on its first page
        self.assertIsNone(B.numbers(B.book("Tob")))     # the Synodal's alone

    def test_both_lists_at_the_left_and_on_the_book_page(self):
        _, _, b = get("/bible/Psa/23")
        self.assertIn('<ol class="kch kchk">', b)
        self.assertIn('<ol class="kch kchs"><li><a href="/bible/Psa/1">1</a></li>', b)
        self.assertIn('<li class="here"><a href="/bible/Psa/23">22</a></li>', b)
        self.assertIn('<li class="here"><a href="/bible/Psa/23">23</a></li>', b)
        _, _, b = get("/bible/Gen/1")
        self.assertIn('<ol class="kch">', b)
        self.assertNotIn("kchs", b)
        _, _, b = get("/bible/Psa")
        self.assertIn('<ol class="kchaps kchk">', b)
        self.assertIn('<ol class="kchaps kchs">', b)
        self.assertIn('<a href="/bible/Psa/23">22</a>', b)
        css = (ROOT / "ubsite/static/ub.css").read_text()
        self.assertIn(':root:not([data-bible^="rsb"]) ol.kchs, :root[data-bible^="rsb"] ol.kchk { display: none; }', css)


@unittest.skipUnless(KJV.exists(), "var/bible.db is not built (make bible)")
class Pages(unittest.TestCase):

    def test_the_contents_a_book_and_a_chapter(self):
        s, _, b = get("/bible")
        self.assertEqual(s, 200)
        # The 77, the eleven non-canonical between the testaments (Tigran,
        # 2026-11-21: "Between the testaments"), each in both languages.
        self.assertEqual(len(re.findall(r'<li(?: class="cited")?><a href="/bible/', b)), 77)
        self.assertLess(b.index('href="/bible/Mal"'), b.index('href="/bible/Tob"'))
        self.assertLess(b.index('href="/bible/3Ez"'), b.index('href="/bible/Mat"'))
        # Each by its name in the interface's language, whichever text is
        # first (Tigran, 2026-11-21: "the Bible books should be in Russian if
        # the Russian UI is selected"); the eleven by English Bibles' names.
        both = get("/bible", raw=True)[2]
        self.assertIn('<a href="/bible/Gen"><x-en>Genesis</x-en><x-ru lang="ru">Бытие</x-ru></a>', both)
        self.assertIn('<a href="/bible/2Ez"><x-en>1 Esdras</x-en><x-ru lang="ru">2-я Ездры</x-ru></a>', both)
        self.assertIn('<a href="/bible/Gen">Genesis</a>', b)
        s, _, b = get("/bible/Gen")
        self.assertEqual(s, 200)
        self.assertEqual(len(re.findall(r'<li(?: class="cited")?><a href="/bible/Gen/', b)), 50)
        self.assertIn('<span class="tm">genesis</span>', b)
        self.assertIn('<span class="tm">Бытие</span>', b)
        s, _, b = get("/bible/Gen/1")
        self.assertEqual(s, 200)
        rows = b.split('<div class="kverses">')[1].split("</div>\n    <section")[0]
        self.assertEqual(len(re.findall(r'<p class="kv[^"]*" id="v\d+" data-k="kjv" data-ref="1:\d+">', rows)), 31)
        self.assertEqual(rows.count('<div class="btf" data-has="rsb">'), 31)
        self.assertNotIn('<p class="t', rows)
        self.assertNotIn(" hit", rows)
        self.assertIn('<aside class="note" id="fnGen1_4" data-k="kjv">', b)
        self.assertRegex(b, r'<article class="biblech" data-book="Genesis" data-book-ru="Бытие" data-c="1"\s+'
                            r'data-abbr="Gen" data-trv="[0-9a-f]{12}" data-has="rsb">')

    def test_the_synodals_lines_are_their_own_fragment(self):
        # What ub.js draws first, in columns or in folds (bibDraw), every row's
        # whose base line is the KJV's, by its own numbers, with no ids; and
        # kept for good under the version the page names.
        _, _, b = get("/bible/Psa/23")
        v = re.search(r'data-trv="([0-9a-f]{12})"', b)[1]
        s, h, f = get(f"/bible/tr/Psa/23?v={v}")
        self.assertEqual(s, 200)
        self.assertIn("immutable", h.get("cache-control", ""))
        self.assertIn('<h1>Псалом 22</h1>', f)
        self.assertIn('<div class="brt" data-k="rsb" data-row="v1">', f)
        self.assertIn('<p class="kv pil" data-k="rsb" data-ref="22:1" lang="ru"><span class="vn" data-n="1"'
                      ' data-c="22"></span>Гос\u00adподь\u00a0— Пас\u00adтырь мой', f)
        self.assertNotIn(' id="', f.split("</h1>")[1].split('<aside')[0])
        self.assertEqual(get("/bible/tr/Tob/1")[0], 404)               # the Synodal's own book: its page has it
        self.assertEqual(get("/bible/tr/Gen/51")[0], 404)

    def test_rows_the_kjv_has_not_are_the_synodals_on_the_page(self):
        _, _, b = get("/bible/Dan/3")
        self.assertIn('<div class="krow" data-row="s3-24">\n      <p class="bwho" lang="ru">Синодальный</p>', b)
        self.assertIn('id="s3-24" data-k="rsb" data-ref="3:24" lang="ru"', b)
        self.assertEqual(b.count('class="bwho"'), 1)
        # A book of the Synodal's alone, its own numbers; the KJV has it not.
        s, _, b = get("/bible/Tob/1:3")
        self.assertEqual(s, 200)
        self.assertIn('id="v3" data-k="rsb" data-ref="1:3" lang="ru"', b)
        self.assertRegex(b, r'<p class="kv[^"]* hit" id="v3" data-k="rsb"')
        self.assertIn('class="biblech bonly"', b)
        self.assertIn("the KJV has none of them", b)
        # Psalm 151, a chapter of its own; the joined row of 2Co 13:12-13.
        self.assertEqual(get("/bible/Psa/151")[0], 200)
        _, _, b = get("/bible/2Co/13:13")
        self.assertRegex(b, r'<p class="kv[^"]* hit" id="v13" data-k="kjv" data-ref="13:13">')

    def test_a_book_opens_with_its_first_letter_dropped(self):
        # As a paper does (Tigran, 2026-11-21): its first verse .opening, in
        # its first chapter only; and tinted too where an address names it.
        _, _, b = get("/bible/Gen/1")
        self.assertRegex(b, r'<p class="kv(?: pil)? opening" id="v1" data-k="kjv"')
        self.assertEqual(len(re.findall(r'<p class="kv[^"]* opening', b)), 1)
        self.assertNotRegex(get("/bible/Gen/2")[2], r'<p class="kv[^"]* opening')
        self.assertRegex(get("/bible/Mat/1:1")[2], r'<p class="kv(?: pil)? opening hit" id="v1" data-k="kjv"')

    def test_a_chapter_is_a_readers_page_with_the_bibles_contents(self):
        # The rail at the left, as the book's (Tigran, 2026-11-21): the
        # testaments and the non-canonical books between them, the 77 books,
        # the one being read open to its chapters, the chapter being read
        # marked; the others lazy, opened by ub.js.
        _, _, b = get("/bible/Mal/3", raw=True)
        self.assertIn('<main class="reader bible">', b)
        rail = re.search(r'<nav class="rail kjvrail".*?</nav>', b, re.S)[0]
        # A book's name goes to its first chapter, its chapters lifted from its
        # page; a testament's to its first book's (Tigran, 2026-11-21: "in the
        # Contents the parent node is just a shortcut for the first of its
        # children").
        self.assertEqual(len(re.findall(r'<summary><a href="/bible/([1-3]?[A-Z][a-z]{1,2})/1" data-ch="/bible/\1">',
                                        rail)), 77)
        self.assertEqual(len(re.findall(r'<li class="lazy">', rail)), 76)
        self.assertIn('<li class="here"><details open><summary><a href="/bible/Mal/1" data-ch="/bible/Mal"><x-en>Malachi</x-en>'
                      '<x-ru lang="ru">Малахия</x-ru></a></summary><ol class="kch">', rail)
        self.assertEqual(re.findall(r'<li class="part"><details(?: open)?><summary><a href="([^"]+)">', rail),
                         ["/bible/Gen/1", "/bible/2Ez/1", "/bible/Mat/1"])
        # The breadcrumb, the window's title and the transport bar name the
        # book in the interface's language too; the text's own head its own.
        self.assertIn('<a href="/bible/Mal"><x-en>Malachi</x-en><x-ru lang="ru">Малахия</x-ru></a></p>', b)
        self.assertIn('<title data-ru="Малахия 3 — Библия">Malachi 3 — The Bible</title>', b)
        self.assertIn('data-ru-title="Предыдущая глава: Малахия 2"', b)
        self.assertIn('data-book="Malachi" data-book-ru="Малахия"', b)
        # The KJV's own head is its own English, whatever the interface's
        # language: "CHAPTER 3", never the interface's «Глава 3».
        self.assertIn('<div class="bhd" data-k="kjv">\n  <h1>Chapter 3</h1>', b)
        self.assertIn('<h1>Psalm 23</h1>', get("/bible/Psa/23", raw=True)[2])
        self.assertIn('<li class="here"><a href="/bible/Mal/3">3</a></li>', rail)
        self.assertEqual(rail.count('class="here"'), 2)
        self.assertIn('<article class="biblech" data-book="Malachi" data-book-ru="Малахия" data-c="3"', b)

    def test_a_verse_address_tints_its_verses(self):
        _, _, b = get("/bible/Psa/119:9-11")
        hit = re.findall(r'<p class="kv[^"]* hit" id="v(\d+)"', b)
        self.assertEqual(hit, ["9", "10", "11"])
        self.assertIn('<h2 class="kvl" data-k="kjv">BETH.</h2>', b)
        # Never 3 Ezra's bracketed series, whose numbers are no address.
        _, _, b = get("/bible/3Ez/7:36")
        self.assertEqual(re.findall(r'<p class="kv[^"]* hit" id="([^"]+)"', b), ["v36"])

    def test_an_address_written_otherwise_is_sent_on_or_explained(self):
        for path, status, where in (("/bible/gen", 301, "/bible/Gen"), ("/bible/Genesis/1:1", 301, "/bible/Gen/1:1"),
                                    ("/bible/1samuel/3", 301, "/bible/1Sa/3"), ("/bible/Бытие", 301, "/bible/Gen"),
                                    ("/bible/1-я Царств/2", 301, "/bible/1Sa/2"), ("/bible/tobit", 301, "/bible/Tob"),
                                    ("/bible/Xyz", 404, None), ("/bible/Gen/51", 404, None),
                                    ("/bible/Gen/1:40", 404, None), ("/bible/Gen/1:5-3", 404, None),
                                    ("/bible/Gen/x", 404, None)):
            with self.subTest(path=path):
                s, h, b = get(path)
                self.assertEqual(s, status)
                if where:
                    self.assertEqual(h.get("location"), where)
        self.assertIn("Genesis has no chapter 51: its chapters run from", get("/bible/Gen/51")[2])
        self.assertIn("Genesis 1 has no verse 40: its verses run from", get("/bible/Gen/1:40")[2])
        self.assertIn("The Bible has no book Xyz.", get("/bible/Xyz")[2])

    def test_the_synodals_own_numbers_are_sent_on_to_their_rows(self):
        for path, where in (("/bible/rsb/Psa/22:1", "/bible/Psa/23:1#tr-rsb"), ("/bible/rsb/Psa/22", "/bible/Psa/23"),
                            ("/bible/rsb/Psa/22:0", "/bible/Psa/23#v0"), ("/bible/rsb/Psa/9:22", "/bible/Psa/10:1#tr-rsb"),
                            ("/bible/rsb/Dan/3:24", "/bible/Dan/3#s3-24"), ("/bible/rsb/Tob/1:3", "/bible/Tob/1#v3"),
                            ("/bible/rsb/Psa/114", "/bible/Psa/116"), ("/bible/rsb/Gen/1:1", "/bible/Gen/1:1#tr-rsb")):
            with self.subTest(path=path):
                s, h, _ = get(path)
                self.assertEqual((s, h.get("location")), (301, where))
        for path in ("/bible/rsb/Psa/22:99", "/bible/rsb/Xyz/1:1", "/bible/rsb/Tob/1:1-2"):
            self.assertEqual(get(path)[0], 404, path)


@unittest.skipUnless(KJV.exists() and UB.exists(), "the databases are not built")
class Search(unittest.TestCase):

    def test_a_bible_address_goes_to_its_verse(self):
        for q, where in (("John 3:16", "/bible/Joh/3:16"), ("psalm 23", "/bible/Psa/23"), ("Jude 24", "/bible/Jud/1:24"),
                         ("1 John 4:8", "/bible/1Jo/4:8"), ("I John 4:8", "/bible/1Jo/4:8"),
                         ("Song of Solomon 2:1", "/bible/Sol/2:1"), ("Psalms 104:1-2", "/bible/Psa/104:1-2"),
                         ("Tobit 1:3", "/bible/Tob/1:3"),
                         # By the Synodal's names and numbers, to its own address (2026-11-21).
                         ("Пс 22:1", "/bible/rsb/Psa/22:1"), ("Псалом 22", "/bible/rsb/Psa/22"),
                         ("1 Цар 2:2", "/bible/rsb/1Sa/2:2"), ("Ин 3:16", "/bible/rsb/Joh/3:16"),
                         ("Иуд 24", "/bible/rsb/Jud/1:24")):
            with self.subTest(q=q):
                s, h, _ = get("/search?q=" + urllib.parse.quote_plus(q))
                self.assertEqual((s, h.get("location")), (303, where))
        # Not an address: a chapter the book lacks, the book's own citation.
        self.assertEqual(get("/search?q=Gen+99:1")[0], 200)
        self.assertEqual(get("/search?q=" + urllib.parse.quote_plus("Пс 22:99"))[0], 200)
        self.assertNotEqual(get("/search?q=1:1")[1].get("location", "").startswith("/bible"), True)

    def test_each_versions_verses_and_notes_are_a_list_of_their_own(self):
        s, _, b = get("/search?q=houghed")
        self.assertEqual(s, 200)
        sec = re.search(r'<section data-bible="kjv" class="bybible">.*?</section>', b, re.S)
        self.assertIsNotNone(sec)
        self.assertIn('<a href="/bible/Gen/49:6">Genesis 49:6</a>', sec[0])
        self.assertIn('<span class="kjvnote">', sec[0])
        s, _, b = get("/search?q=houghed&in=kjv")
        self.assertIn('<section data-bible="kjv"><h2>In the King James Version', b)
        # The Synodal's, ё read as е and shown as written; its hits by its own
        # numbers, which are sent on to their rows.
        _, _, b = get("/search?q=" + urllib.parse.quote_plus("четвертый"))
        sec = re.search(r'<section data-bible="rsb" class="bybible">.*?</section>', b, re.S)[0]
        self.assertIn('<a href="/bible/rsb/Gen/1:19">Быт 1:19</a>', sec)
        self.assertIn("<mark>четвёртый</mark>", sec)

if __name__ == "__main__":
    unittest.main()
