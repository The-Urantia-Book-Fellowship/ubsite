"""The King James Version (data/kjv/, build/kjv.py, build/bibleref.py,
ubsite/kjv.py; 2026-11-21): the copy, the database, the study notes' Bible
references made links, the pages and their addresses, and search.

    .venv/bin/python -m unittest discover -s tests -p test_kjv.py

The database is var/kjv.db, as `make kjv` builds it; the notes' links are in
var/ub.db, as `make data` builds it.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import subprocess
import sys
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from build import bibleref, kjv                     # noqa: E402
from build.problems import Report                  # noqa: E402
from build.render import strip_tags                # noqa: E402
from test_appendix_pages import get                # noqa: E402

KJV = ROOT / "var" / "kjv.db"
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
        books = (kjv.DATA / "books.tsv").read_text(encoding="utf-8").split("\n")
        self.assertEqual(books[0].split("\t"), kjv.BOOK_FIELDS)
        abbrs = [line.split("\t")[1] for line in books[1:] if line]
        self.assertEqual(len(abbrs), 66)
        self.assertEqual((abbrs[0], abbrs[38], abbrs[39], abbrs[-1]), ("Gen", "Mal", "Mat", "Rev"))
        for a in abbrs:
            rows = [line.split("\t") for line in (kjv.DATA / f"{a}.tsv").read_text(encoding="utf-8").split("\n")[1:]
                    if line]
            with self.subTest(book=a):
                self.assertTrue(all(len(r) == len(kjv.VERSE_FIELDS) for r in rows))
                at = [(int(r[0]), int(r[1])) for r in rows]
                self.assertEqual(at, sorted(at))
                self.assertTrue(all(r[2] in ("", "¶") for r in rows))
                # Only the two macros the copy keeps.
                for r in rows:
                    left = re.sub(r"\\(?:bibemph|textsc)\{[^{}\\]*\}", "", "".join(r[3:]))
                    self.assertNotRegex(left, r"[\\{}]", r)

    def test_a_correction_and_a_line_of_the_witness_say_why(self):
        for name, n in (("corrections.tsv", 7), ("witness.tsv", 6)):
            lines = (kjv.DATA / name).read_text(encoding="utf-8").split("\n")
            for line in lines[1:]:
                if line:
                    cells = line.split("\t")
                    self.assertEqual(len(cells), n, line)
                    self.assertTrue(cells[-1].strip(), line)


@unittest.skipUnless(KJV.exists(), "var/kjv.db is not built (make kjv)")
class Database(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{KJV}?mode=ro", uri=True)
        cls.want = tomllib.loads((ROOT / "verify" / "expectations.toml").read_text())["kjv"]

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def one(self, q, *a):
        return self.con.execute(q, a).fetchone()[0]

    def test_its_counts_are_the_expected(self):
        meta = dict(self.con.execute("SELECT key, value FROM kjv_meta"))
        for k in ("books", "chapters", "verses", "notes", "pilcrows", "heads", "afters", "supplied", "sc"):
            self.assertEqual(int(meta[k]), self.want[k], k)
        self.assertEqual(meta["data"], kjv.digest(), "var/kjv.db is not of data/kjv/ as it is")

    def test_a_verse_sets_its_supplied_words_the_lord_and_its_notes_mark(self):
        h = self.one("SELECT v.html_hy FROM kjv_verse v JOIN kjv_book b ON b.id = v.book"
                     " WHERE b.abbr = 'Gen' AND v.chapter = 1 AND v.verse = 4")
        self.assertIn('<span class="supplied">it was</span>', h)
        self.assertIn('<a class="fn" href="#fnGen1_4" id="fnrefGen1_4" data-k="kjv"', h)
        self.assertIn("\u00ad", h)                       # hyphenated: di­vided
        self.assertEqual(strip_tags(h).replace("\u00ad", ""),
                         "And God saw the light, that it was good: and God divided the light from the darkness.")
        lord = self.one("SELECT v.html FROM kjv_verse v JOIN kjv_book b ON b.id = v.book"
                        " WHERE b.abbr = 'Gen' AND v.chapter = 2 AND v.verse = 4")
        self.assertIn('<span class="sc">Lord</span>', lord)

    def test_titles_letters_and_subscriptions_stand_apart(self):
        head = self.one("SELECT v.head || '|' || v.text FROM kjv_verse v JOIN kjv_book b ON b.id = v.book"
                        " WHERE b.abbr = 'Psa' AND v.chapter = 3 AND v.verse = 1")
        self.assertTrue(head.startswith("A Psalm of David, when he fled from Absalom his son.|Lord, how"), head)
        self.assertEqual(self.one("SELECT v.head FROM kjv_verse v JOIN kjv_book b ON b.id = v.book"
                                  " WHERE b.abbr = 'Psa' AND v.chapter = 119 AND v.verse = 9"), "BETH.")
        after = self.one("SELECT v.after FROM kjv_verse v JOIN kjv_book b ON b.id = v.book"
                         " WHERE b.abbr = 'Rom' AND v.chapter = 16 AND v.verse = 27")
        self.assertTrue(after.startswith("Written to the Romans from Corinthus"), after)

    def test_a_note_ends_with_one_stop_and_its_ellipsis_is_one_character(self):
        self.assertEqual(self.one("SELECT COUNT(*) FROM kjv_note WHERE text LIKE '%?.%' OR text LIKE '%etc..%'"), 0)
        self.assertEqual(self.one("SELECT n.text FROM kjv_note n JOIN kjv_verse v ON v.id = n.verse_id"
                                  " JOIN kjv_book b ON b.id = v.book WHERE b.abbr = 'Gen' AND v.chapter = 1"
                                  " AND v.verse = 4"), "the light from…: Heb. between the light and between the darkness.")


@unittest.skipUnless(KJV.exists(), "var/kjv.db is not built (make kjv)")
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
            f"Psalms{T}104:1–2": [(f"Psalms{T}104:1–2", "/kjv/Psa/104:1-2")],
            f"Isaiah{T}40:12, 22 and{T}26": [(f"Isaiah{T}40:12", "/kjv/Isa/40:12"), ("22", "/kjv/Isa/40:22"),
                                            ("26", "/kjv/Isa/40:26")],
            f"John{T}1:1 and 14": [(f"John{T}1:1", "/kjv/Joh/1:1"), ("14", "/kjv/Joh/1:14")],
            f"1{T}Timothy{T}1:17 and 6:16": [(f"1{T}Timothy{T}1:17", "/kjv/1Ti/1:17"), ("6:16", "/kjv/1Ti/6:16")],
            f"Nehemiah{T}9:6 and 1{T}Samuel{T}2:2": [(f"Nehemiah{T}9:6", "/kjv/Neh/9:6"),
                                                    (f"1{T}Samuel{T}2:2", "/kjv/1Sa/2:2")],
            f"Luke{T}23:43, 2{T}Corinthians{T}12:4": [(f"Luke{T}23:43", "/kjv/Luk/23:43"),
                                                     (f"2{T}Corinthians{T}12:4", "/kjv/2Co/12:4")],
            f"Daniel{T}7:9–10; again at 7:13 and 7:22": [(f"Daniel{T}7:9–10", "/kjv/Dan/7:9-10"),
                                                         ("7:13", "/kjv/Dan/7:13"), ("7:22", "/kjv/Dan/7:22")],
            f"1{T}Corinthians{T}1:9 or 10:13": [(f"1{T}Corinthians{T}1:9", "/kjv/1Co/1:9"), ("10:13", "/kjv/1Co/10:13")],
            f"Jude{T}24": [(f"Jude{T}24", "/kjv/Jud/1:24")],
            "Psalm 23": [("Psalm 23", "/kjv/Psa/23")],
            f"Job{T}9:11 (p.{T}459)": [(f"Job{T}9:11", "/kjv/Job/9:11")],
            f"Romans{T}1:20: “For the invisible things": [(f"Romans{T}1:20", "/kjv/Rom/1:20")],
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
        self.assertEqual(got, ([("Matthew 22:39", "/kjv/Mat/22:39"), ("22:37–38", "/kjv/Mat/22:37-38")], []))
        got = self.links(text, at="16:9.8", known={("16:9.8", "22:37--38", 1): "-"})
        self.assertEqual(got, ([("Matthew 22:39", "/kjv/Mat/22:39")], []))
        # Never in a note's `corrects`: Block's slips.
        self.assertEqual(self.links("Psalms 145:17 for his 145:7", known={}, carry=False),
                         ([("Psalms 145:17", "/kjv/Psa/145:17")], []))

    def test_the_list_of_references_carried_is_read(self):
        known = bibleref.read_known()
        self.assertEqual(known[("11:3.1", "2:12", 1)], "Zec 2:12")
        self.assertEqual(known[("16:4.1", "5:6", 1)], "-")


@unittest.skipUnless(UB.exists() and KJV.exists(), "the databases are not built (make data)")
class Notes(unittest.TestCase):

    def test_every_link_of_a_note_to_the_kjv_names_a_verse_it_has(self):
        ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
        hrefs = [h for (html,) in ub.execute("SELECT html FROM footnote WHERE kind = 'study'")
                 for h in re.findall(r'href="(/kjv/[^"]+)"', html)]
        ub.close()
        self.assertGreater(len(hrefs), 300)
        last = kjv.verses_of()
        for h in set(hrefs):
            m = re.fullmatch(r"/kjv/([1-3]?[A-Z][a-z]{1,2})/(\d+)(?::(\d+)(?:-(\d+))?)?", h)
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
    (ub.db kjv_cite, build/bibleref.py store; Tigran, 2026-11-21)."""

    def test_every_link_of_a_note_is_a_citation_of_its_verses(self):
        ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
        links = sum(len(bibleref.RE_HREF.findall(h)) for (h,) in
                    ub.execute("SELECT html FROM footnote WHERE kind = 'study'"))
        n = ub.execute("SELECT COUNT(*) FROM kjv_cite").fetchone()[0]
        ub.close()
        self.assertEqual(n, links)

    def test_a_verse_names_the_paragraphs_whose_notes_cite_it(self):
        _, _, b = get("/kjv/Isa/40")
        after12 = b.split('id="v12">')[1].split('id="v13"')[0]
        self.assertIn('<p class="kvc"><span class="lbl">Study notes at</span> <a href="/1:5.3">1:5.3</a>', after12)
        after11 = b.split('id="v11">')[1].split('id="v12"')[0]
        self.assertNotIn('class="kvc"', after11)
        # A run of verses names each of them: Psalms 104:1-2.
        _, _, b = get("/kjv/Psa/104")
        for v in (1, 2):
            self.assertIn('<a href="/1:0.1">1:0.1</a>', b.split(f'id="v{v}">')[1].split(f'id="v{v + 1}"')[0])

    def test_a_book_and_a_chapter_cited_are_marked(self):
        _, _, b = get("/kjv")
        self.assertIn('<li class="cited"><a href="/kjv/Isa">', b)
        self.assertIn('<li><a href="/kjv/Nah">', b)
        self.assertRegex(b, r'<p class="kjvcite">Under a verse stand the paragraphs')
        _, _, b = get("/kjv/Isa")
        self.assertIn('<li class="cited"><a href="/kjv/Isa/40">40</a></li>', b)


@unittest.skipUnless(KJV.exists(), "var/kjv.db is not built (make kjv)")
class Pages(unittest.TestCase):

    def test_the_contents_a_book_and_a_chapter(self):
        s, _, b = get("/kjv")
        self.assertEqual(s, 200)
        self.assertEqual(len(re.findall(r'<li(?: class="cited")?><a href="/kjv/', b)), 66)
        s, _, b = get("/kjv/Gen")
        self.assertEqual(s, 200)
        self.assertEqual(len(re.findall(r'<li(?: class="cited")?><a href="/kjv/Gen/', b)), 50)
        self.assertIn('<span class="tm">genesis</span>', b)
        s, _, b = get("/kjv/Gen/1")
        self.assertEqual(s, 200)
        self.assertEqual(len(re.findall(r'<p class="kv[^"]*" id="v\d+">', b)), 31)
        self.assertNotIn('<p class="t', b.split('<div class="kverses">')[1])
        self.assertNotIn(" hit", b.split('<div class="kverses">')[1].split("</div>")[0])
        self.assertIn('<aside class="note" id="fnGen1_4">', b)

    def test_a_book_opens_with_its_first_letter_dropped(self):
        # As a paper does (Tigran, 2026-11-21): its first verse .opening, in
        # its first chapter only; and tinted too where an address names it.
        _, _, b = get("/kjv/Gen/1")
        self.assertRegex(b, r'<p class="kv(?: pil)? opening" id="v1">')
        self.assertEqual(len(re.findall(r'<p class="kv[^"]* opening', b)), 1)
        self.assertNotRegex(get("/kjv/Gen/2")[2], r'<p class="kv[^"]* opening')
        self.assertRegex(get("/kjv/Mat/1:1")[2], r'<p class="kv(?: pil)? opening hit" id="v1">')

    def test_a_chapter_is_a_readers_page_with_the_bibles_contents(self):
        # The rail at the left, as the book's (Tigran, 2026-11-21): the two
        # testaments, the 66 books, the one being read open to its chapters,
        # the chapter being read marked; the others lazy, opened by ub.js.
        _, _, b = get("/kjv/Mal/3")
        self.assertIn('<main class="reader kjv">', b)
        rail = re.search(r'<nav class="rail kjvrail".*?</nav>', b, re.S)[0]
        self.assertEqual(len(re.findall(r'<summary><a href="/kjv/[1-3]?[A-Z][a-z]{1,2}">', rail)), 66)
        self.assertEqual(len(re.findall(r'<li class="lazy">', rail)), 65)
        self.assertIn('<li class="here"><details open><summary><a href="/kjv/Mal">Malachi</a></summary><ol class="kch">', rail)
        self.assertIn('<li class="here"><a href="/kjv/Mal/3">3</a></li>', rail)
        self.assertEqual(rail.count('class="here"'), 2)
        self.assertIn('<article class="kjvch" data-book="Malachi" data-c="3">', b)

    def test_a_verse_address_tints_its_verses(self):
        _, _, b = get("/kjv/Psa/119:9-11")
        hit = re.findall(r'<p class="kv[^"]* hit" id="v(\d+)">', b)
        self.assertEqual(hit, ["9", "10", "11"])
        self.assertIn('<h2 class="kvl">BETH.</h2>', b)

    def test_an_address_written_otherwise_is_sent_on_or_explained(self):
        for path, status, where in (("/kjv/gen", 301, "/kjv/Gen"), ("/kjv/Genesis/1:1", 301, "/kjv/Gen/1:1"),
                                    ("/kjv/1samuel/3", 301, "/kjv/1Sa/3"), ("/kjv/Xyz", 404, None),
                                    ("/kjv/Gen/51", 404, None), ("/kjv/Gen/1:40", 404, None),
                                    ("/kjv/Gen/1:5-3", 404, None), ("/kjv/Gen/x", 404, None)):
            with self.subTest(path=path):
                s, h, b = get(path)
                self.assertEqual(s, status)
                if where:
                    self.assertEqual(h.get("location"), where)
        self.assertIn("Genesis has no chapter 51: its chapters run from", get("/kjv/Gen/51")[2])
        self.assertIn("Genesis 1 has no verse 40: its verses run from", get("/kjv/Gen/1:40")[2])
        self.assertIn("The King James Version has no book Xyz.", get("/kjv/Xyz")[2])


@unittest.skipUnless(KJV.exists() and UB.exists(), "the databases are not built")
class Search(unittest.TestCase):

    def test_a_bible_address_goes_to_its_verse(self):
        for q, where in (("John 3:16", "/kjv/Joh/3:16"), ("psalm 23", "/kjv/Psa/23"), ("Jude 24", "/kjv/Jud/1:24"),
                         ("1 John 4:8", "/kjv/1Jo/4:8"), ("I John 4:8", "/kjv/1Jo/4:8"),
                         ("Song of Solomon 2:1", "/kjv/Sol/2:1"), ("Psalms 104:1-2", "/kjv/Psa/104:1-2")):
            with self.subTest(q=q):
                s, h, _ = get("/search?q=" + q.replace(" ", "+"))
                self.assertEqual((s, h.get("location")), (303, where))
        # Not an address: a chapter the book lacks, the book's own citation.
        self.assertEqual(get("/search?q=Gen+99:1")[0], 200)
        self.assertNotEqual(get("/search?q=1:1")[1].get("location", "").startswith("/kjv"), True)

    def test_its_verses_and_notes_are_a_list_of_their_own(self):
        s, _, b = get("/search?q=houghed")
        self.assertEqual(s, 200)
        sec = re.search(r'<section data-kjv class="bykjv">.*?</section>', b, re.S)
        self.assertIsNotNone(sec)
        self.assertIn('<a href="/kjv/Gen/49:6">Genesis 49:6</a>', sec[0])
        self.assertIn('<span class="kjvnote">', sec[0])
        s, _, b = get("/search?q=houghed&in=kjv")
        self.assertIn('<section data-kjv><h2>In the King James Version', b)


if __name__ == "__main__":
    unittest.main()
