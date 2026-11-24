"""Search by meaning (Tigran, 2026-11-23 and 24; ARCHITECTURE.md, Search by meaning).

The units build/embed.py composes, the same twice and of the sizes the book
gives; the words route's query, which cannot fail to parse; the fusion's
arithmetic; one search, with the model's place taken by a stand-in that
answers a question with a known paragraph's own vector, so that the paragraph
must come first and its neighbours be joined to it; the page and the route,
their refusals, and that a question is written nowhere; and the pins of the
3090's environment, which are the site's.

Nothing here loads the model (1.5 GB): tools/embed/build.py embeds units
again on the CPU before it writes var/embed.db, and a worker embeds the probe
as it starts.  The tests of the vectors skip where var/embed.db is not built.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UB_VISITS", "off")

from build import config, embed                   # noqa: E402
from ubsite import meaning                        # noqa: E402

UB = ROOT / "var" / "ub.db"
BIBLE = ROOT / "var" / "bible.db"
EMBED = ROOT / "var" / "embed.db"
BUILT = UB.exists() and BIBLE.exists()


def ro(path: pathlib.Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class Pins(unittest.TestCase):
    def test_the_gpu_environment_is_pinned_as_the_site_is(self):
        """tools/embed/requirements.in is written by hand: the runtime's GPU
        build at the version of the site's CPU build, the rest the same."""
        site = dict(re.findall(r"^([a-z0-9-]+)==(\S+)", (ROOT / "requirements.txt").read_text(), re.M))
        gpu = dict(re.findall(r"^([a-z0-9-]+)(?:\[[^\]]*\])?==(\S+)", (ROOT / "tools/embed/requirements.in").read_text(), re.M))
        self.assertEqual(gpu, {"onnxruntime-gpu": site["onnxruntime"], "tokenizers": site["tokenizers"],
                               "numpy": site["numpy"]})

    def test_the_model_is_named_by_revision_and_digest(self):
        cfg = config.embed()
        self.assertRegex(cfg["rev"], r"^[0-9a-f]{40}$")
        self.assertIn(cfg["rev"], cfg["base"])
        self.assertEqual(set(cfg["sha256"]), {meaning.GRAPH, meaning.GRAPH + "_data", meaning.TOKENIZER})
        for sha in cfg["sha256"].values():
            self.assertRegex(sha, r"^[0-9a-f]{64}$")
        self.assertEqual(cfg["dim"], meaning.DIM)


@unittest.skipUnless(BUILT, "var/ub.db and var/bible.db not built")
class Units(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ub, cls.bible = ro(UB), ro(BIBLE)
        cls.us = embed.units(cls.ub, cls.bible)
        cls.by = {}
        for u in cls.us:
            cls.by.setdefault(u.kind, []).append(u)

    def test_composed_the_same_twice(self):
        again = embed.units(ro(UB), ro(BIBLE))
        self.assertEqual(embed.digest(again), embed.digest(self.us))

    def test_the_kinds_stand_together_in_their_order(self):
        kinds = [u.kind for u in self.us]
        self.assertEqual(list(dict.fromkeys(kinds)), list(embed.KINDS))
        self.assertEqual(sorted(kinds, key=embed.KINDS.index), kinds)

    def test_every_paragraph_once_under_its_titles(self):
        refs = [r for (r,) in self.ub.execute("SELECT ref FROM paragraph ORDER BY ord")]
        self.assertEqual([u.label for u in self.by["para"]], refs)
        u = next(u for u in self.by["para"] if u.label == "101:4.2")
        self.assertTrue(u.text.startswith("The Real Nature of Religion: The Limitations of Revelation\n"))
        intro = next(u for u in self.by["para"] if u.label == "101:0.1")
        self.assertTrue(intro.text.startswith("The Real Nature of Religion\n"), "an introduction has no section's title")

    def test_an_entry_is_its_path_written_out_and_only_one_that_cites(self):
        n = self.ub.execute("SELECT COUNT(DISTINCT entry_id) FROM citation").fetchone()[0]
        self.assertEqual(len(self.by["entry"]), n)
        short = [u for u in self.by["entry"] if "T.A." in u.label]
        self.assertTrue(short)
        for u in short:
            self.assertNotIn("T.A.", u.text, u.label)
            self.assertIn("Thought Adjuster", u.text)
            self.assertNotRegex(u.text, r"\(\d+:\d", "an entry's text has no citation")
        ids = dict(self.ub.execute("SELECT id, path_plain FROM index_entry"))
        for u in self.by["entry"]:
            self.assertEqual(ids[int(u.target)], u.label)

    def test_a_note_leads_to_its_paragraph(self):
        refs = {r for (r,) in self.ub.execute("SELECT ref FROM paragraph")}
        self.assertEqual(len(self.by["note"]), self.ub.execute(
            "SELECT COUNT(*) FROM footnote WHERE kind = 'study'").fetchone()[0])
        for u in self.by["note"]:
            self.assertIn(u.target, refs)

    def test_every_verse_of_the_kjv_is_in_a_passage(self):
        have = set()
        for u in self.by["kjv"]:
            book, where = u.label.split(" ")
            chapter, verses = where.split(":")
            a, _, z = verses.partition("-")
            self.assertLessEqual(int(z or a) - int(a) + 1, embed.KJV_WHOLE)
            have.update((book, int(chapter), v) for v in range(int(a), int(z or a) + 1))
        want = {tuple(r) for r in self.bible.execute(
            "SELECT b.abbr, v.chapter, v.verse FROM bible_verse v JOIN bible_book b ON b.id = v.book"
            " WHERE v.version = 'kjv' AND v.kind = 'verse'")}
        self.assertEqual(have, want)
        psalm = next(u for u in self.by["kjv"] if u.label == "Psa 3:1-8")
        self.assertIn("A Psalm of David, when he fled from Absalom his son.", psalm.text)

    def test_no_name_twice(self):
        for k in ("para", "note", "kjv"):
            labels = [u.label for u in self.by[k]]
            self.assertEqual(len(labels), len(set(labels)), k)


class Words(unittest.TestCase):
    def test_every_word_quoted_and_a_longer_one_by_its_beginning(self):
        self.assertEqual(meaning.match("Why does God allow suffering?"),
                         '"why" OR "does" OR "god" OR "allow" OR "suffering" OR "sufferi"*')
        self.assertEqual(meaning.match("prayer", stems=False), '"prayer"')

    def test_what_fts5_would_read_as_its_own_syntax_is_words(self):
        m = meaning.match('self-conscious AND "NEAR" col:x -y *')
        self.assertEqual(m, '"self" OR "conscious" OR "conscio"* OR "and" OR "near" OR "col"')
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.execute("SELECT * FROM t WHERE t MATCH ?", (m,)).fetchall()

    def test_yo_as_ye_and_nothing_of_nothing(self):
        self.assertEqual(meaning.match("Ёж", stems=False), '"еж"')
        self.assertIsNone(meaning.match("?! …"))
        self.assertIsNone(meaning.match("a"))

    def test_the_language_of_a_question(self):
        self.assertEqual(meaning.language("Кто такой Thought Adjuster?"), "ru")
        self.assertEqual(meaning.language("Who is God?"), "en")
        self.assertEqual(meaning.language("神は誰ですか"), "")

    def test_a_question_as_it_is_asked(self):
        self.assertEqual(meaning.question("  Who\n is   God? "), "Who is God?")
        for bad in ("", "   ", "x" * (meaning.QUESTION + 1), None, 5, ["q"]):
            with self.assertRaises(meaning.Refused) as c:
                meaning.question(bad)
            self.assertEqual(c.exception.status, 400)
        meaning.question("x" * meaning.QUESTION)


class Fusion(unittest.TestCase):
    def test_reciprocal_rank(self):
        got = dict(meaning.fuse({"para": [1, 2], "words": [2, 3]}, {"para": 1.0, "words": 1.0}, k=60))
        self.assertAlmostEqual(got[1], 1 / 61)
        self.assertAlmostEqual(got[2], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(got[3], 1 / 62)
        self.assertEqual([p for p, _ in meaning.fuse({"para": [1, 2], "words": [2, 3]}, {"para": 1, "words": 1})][0], 2)

    def test_a_route_without_a_weight_is_left_out(self):
        self.assertEqual(meaning.fuse({"note": [9]}, {"para": 1.0}), [])
        self.assertNotIn("note", meaning.WEIGHTS, "the study notes' paragraphs are not fused")
        self.assertEqual(set(meaning.WEIGHTS), {"para", "index", "words"})


class Stand:
    """In the engine's place: a question's vector is a known paragraph's own."""

    def __init__(self, units: meaning.Units, ref: str):
        self.units, self.ref = units, ref

    def fresh(self) -> meaning.Units:
        return self.units

    def vector(self, q: str):
        a, z = self.units.at["para"]
        return self.units.m[a + self.units.label[a:z].index(self.ref)]


@unittest.skipUnless(BUILT and EMBED.exists(), "var/embed.db not built (make embed)")
class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = meaning.Units()
        cls.was = meaning._engine

    def tearDown(self):
        meaning._engine = self.was

    def ask(self, ref: str, q: str = "zzzz") -> dict:
        meaning._engine = Stand(self.units, ref)
        return meaning.search(q, ro(UB))

    def refs(self, run: list[int]) -> list[str]:
        return [self.units.para[p][0] for p in run]

    def test_the_paragraph_whose_vector_it_is_is_in_the_answer(self):
        """Nearest of all by meaning, and so among the first passages; not
        first of all for certain: a paragraph two routes agree on is worth
        more than one a single route puts first, which is what the fusion is."""
        for ref in ("112:3.7", "5:3.3", "0:1.1", "196:3.35"):
            r = self.ask(ref)
            first = [x for run in r["runs"][:10] for x in self.refs(run)]
            self.assertIn(ref, first, ref)
            pid = next(p for run in r["runs"] for p in run if self.units.para[p][0] == ref)
            self.assertIn("meaning", r["why"][pid])
            self.assertEqual(self.refs([meaning.fuse({"para": [pid]})[0][0]]), [ref])

    def test_neighbours_are_one_passage_in_the_books_order(self):
        r = self.ask("112:3.7")
        for run in r["runs"]:
            secs = {self.units.para[p][1] for p in run}
            ns = [self.units.para[p][2] for p in run]
            self.assertEqual(len(secs), 1)
            self.assertEqual(ns, list(range(ns[0], ns[0] + len(ns))))
        flat = [p for run in r["runs"] for p in run]
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(len(r["runs"]), meaning.PASSAGES, "an answer is twenty passages, and says so")
        self.assertGreaterEqual(len(flat), meaning.PASSAGES)

    def test_words_find_what_meaning_does_not(self):
        r = self.ask("0:1.1", "Andon and Fonta lived to the age of forty-two")
        found = {self.units.para[p][0]: r["why"][p] for run in r["runs"] for p in run}
        self.assertTrue(any("words" in w for w in found.values()))
        self.assertEqual(r["lang"], "en")

    def test_through_the_index_names_the_entries_that_cite_it(self):
        r = self.ask("112:3.7")
        ub = ro(UB)
        self.assertTrue(r["via"])
        for pid, eids in r["via"].items():
            self.assertIn("index", r["why"][pid])
            for e in eids:
                self.assertTrue(ub.execute("SELECT 1 FROM citation_target WHERE entry_id = ? AND paragraph_id = ?",
                                           (e, pid)).fetchone())
        self.assertLessEqual(len(r["entries"]), meaning.SHOWN["entries"])
        self.assertEqual(len(r["entries"]), len(set(r["entries"])))

    def test_the_kjvs_passages_do_not_overlap(self):
        r = self.ask("112:3.7")
        self.assertEqual(len(r["kjv"]), meaning.SHOWN["kjv"])
        for i, a in enumerate(r["kjv"]):
            for b in r["kjv"][:i]:
                self.assertFalse(a[:2] == b[:2] and a[2] <= b[3] and b[2] <= a[3], (a, b))

    def test_a_database_of_another_build_is_refused_aloud(self):
        """An entry's id that is another entry's in the book's database."""
        units = meaning.Units()
        a, _ = units.at["entry"]
        row = units.nearest(units.m @ Stand(units, "112:3.7").vector(""), "entry", 1)[0]
        units.label[row] = "not this entry"
        meaning._engine = Stand(units, "112:3.7")
        with self.assertRaises(meaning.Mismatch):
            meaning.search("zzzz", ro(UB))
        self.assertGreaterEqual(row, a)


@unittest.skipUnless(BUILT, "var/ub.db not built")
class Page(unittest.TestCase):
    def test_the_page_is_one_for_every_question(self):
        from test_appendix_pages import get
        st, _, body = get("/meaning", raw=True)
        self.assertEqual(st, 200)
        self.assertIn('<main class="prose meaning"', body)
        self.assertRegex(body, r'<input class="mnq"[^>]*maxlength="%d"' % meaning.QUESTION)
        self.assertRegex(body, r'<script src="/static/meaning\.js\?v=[0-9a-f]+" defer>')
        self.assertIn("Поиск по смыслу", body)
        self.assertEqual(body.count('class="mnex"'), 6)
        self.assertEqual(get("/meaning?q=anything", raw=True)[2], body, "the page is not drawn from a question")

    def test_a_machine_without_the_model_says_so(self):
        from test_board import call
        was, off = meaning._engine, os.environ.get("UB_MEANING")
        meaning._engine, os.environ["UB_MEANING"] = None, "off"
        try:
            st, h, j = call("POST", "/meaning/find", json.dumps({"q": "Who is God?"}).encode())
            self.assertEqual((st, j), (503, {"error": "none"}))
            self.assertEqual(h["cache-control"], "no-store")
            self.assertIsNone(meaning.status())
        finally:
            meaning._engine = was
            os.environ.pop("UB_MEANING") if off is None else os.environ.__setitem__("UB_MEANING", off)

    def test_refusals(self):
        from test_board import call
        self.assertEqual(call("POST", "/meaning/find", b"not json")[::2], (400, {"error": "json"}))
        self.assertEqual(call("POST", "/meaning/find", b"[]")[::2], (400, {"error": "json"}))
        self.assertEqual(call("POST", "/meaning/find", b"{}")[::2], (400, {"error": "json"}))
        self.assertEqual(call("POST", "/meaning/find", json.dumps({"q": " "}).encode())[::2], (400, {"error": "empty"}))
        long = json.dumps({"q": "x" * (meaning.QUESTION + 1)}).encode()
        self.assertEqual(call("POST", "/meaning/find", long)[::2], (400, {"error": "long"}))
        self.assertEqual(call("POST", "/meaning/find", b"x" * 1025)[::2], (413, {"error": "long"}))
        self.assertEqual(call("GET", "/meaning/find")[0], 405)

    def test_a_question_of_300_cyrillic_letters_fits_nginxs_kilobyte(self):
        from ubsite import app as A
        self.assertLessEqual(len(json.dumps({"q": "я" * meaning.QUESTION}, ensure_ascii=False).encode()), A.MEANING_BODY)
        for conf in ("ubsite.nginx", "ubsite-sigmaai.nginx"):
            self.assertIn("client_max_body_size 1k;", (ROOT / "deploy" / conf).read_text())


@unittest.skipUnless(BUILT and EMBED.exists(), "var/embed.db not built (make embed)")
class Answer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = meaning.Units()
        cls.was = meaning._engine

    def tearDown(self):
        meaning._engine = self.was

    def answer(self, ref: str, q: str = "What happens after death?") -> tuple[int, dict, str]:
        from test_board import call
        meaning._engine = Stand(self.units, ref)
        return call("POST", "/meaning/find", json.dumps({"q": q}).encode())

    def test_the_answer_is_set_as_the_text_is(self):
        st, h, body = self.answer("112:3.7")
        self.assertEqual(st, 200)
        self.assertEqual((h["cache-control"], h["x-robots-tag"]), ("no-store", "noindex"))
        self.assertTrue(h["content-type"].startswith("text/html"))
        self.assertTrue(body.lstrip().startswith('<div class="mnanswer"'))
        self.assertNotIn("<html", body)
        self.assertRegex(body, r'<section class="mnp" data-sec="112:3" data-trv="[0-9a-f]{12}">')
        self.assertRegex(body, r'<p class="t[^"]*"\s+id="112:3\.7">')
        self.assertIn('<div class="tf" data-has="', body)
        self.assertIn('<section class="mnix ix">', body)
        self.assertIn('<ul class="hits mnentries">', body, "the index's entries one to a line, as every list is")
        self.assertIn('<section class="mnbible bybible" data-bible="kjv">', body)
        self.assertNotIn("id=\"112:3\"", body, "a passage's section has no id: an id is the page's")
        ids = re.findall(r'<p class="t[^"]*"\s+id="([^"]+)"', body)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_word_of_it_in_both_languages(self):
        _, _, body = self.answer("112:3.7")
        for en, ru in (("In the index", "В указателе"), ("In the text", "В тексте"), ("by meaning", "по смыслу"),
                       ("In the King James Version", "В Библии короля Якова")):
            self.assertIn(f"<x-en>{en}</x-en>", body)
            self.assertIn(f'<x-ru lang="ru">{ru}</x-ru>', body)

    def test_each_list_says_how_many_it_holds(self):
        """In the text (20), as the ordinary search's headings say it."""
        _, _, body = self.answer("112:3.7")
        for name, cls, item in (("In the index", "mnix", r"<li>"), ("In the King James Version", "mnbible", r"<li>")):
            part = body[body.index(f'<section class="{cls}'):]
            part = part[:part.index("</section>")]
            n = len(re.findall(item, part))
            self.assertIn(f"<h2><x-en>{name}</x-en>", part)
            self.assertRegex(part, r"<h2>.*? <span>\(%d\)</span></h2>" % n)
        self.assertEqual(body.count('<section class="mnp"'), meaning.PASSAGES)
        self.assertRegex(body, r"<x-en>In the text</x-en><x-ru[^>]*>В тексте</x-ru> <span>\(%d\)</span></h2>" % meaning.PASSAGES)

    def test_the_entries_beside_a_passage_are_those_that_brought_it(self):
        _, _, body = self.answer("112:3.7")
        self.assertIn('<ul class="chips">', body)
        self.assertIn("<x-en>through the index</x-en>", body)

    def test_a_question_is_written_nowhere(self):
        """Not by the route, and not where the search fails either: only the
        failure's kind is said."""
        from test_board import call
        marker = "zebra-crossing-question-4471"

        class Broken(Stand):
            def vector(self, q):
                raise sqlite3.OperationalError(f"near {q}")
        meaning._engine = Broken(self.units, "112:3.7")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            st, _, j = call("POST", "/meaning/find", json.dumps({"q": marker}).encode())
            ok = self.answer("112:3.7", marker)
        self.assertEqual((st, j), (503, {"error": "none"}))
        self.assertEqual(ok[0], 200)
        self.assertNotIn(marker, out.getvalue() + err.getvalue())
        self.assertIn("OperationalError", err.getvalue())
        self.assertNotIn(marker, ok[2], "nor is it sent back in the answer")

    def test_only_a_get_is_counted(self):
        from ubsite import visits
        src = pathlib.Path(visits.__file__).read_text()
        self.assertIn('scope["method"] != "GET"', src)


class Wiring(unittest.TestCase):
    def test_the_scripts_words_are_sent(self):
        from ubsite import app as A
        self.assertIn("meaning.js", A.L10N_SCRIPTS)
        js = (ROOT / "ubsite/static/meaning.js").read_text()
        self.assertNotIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertIn("'/meaning/find'", js)
        self.assertIn("method: 'POST'", js)

    def test_the_headers_tick_is_no_field_of_the_form(self):
        """Ticked, Enter asks by meaning; with scripts off the tick is hidden
        and sends nothing, having no name, and Enter is the ordinary search."""
        from test_appendix_pages import get
        for url in ("/", "/1:0", "/search?q=prayer", "/meaning", "/help"):
            body = get(url, raw=True)[2]
            form = body[body.index('<form class="find"'):]
            form = form[:form.index("</form>")]
            self.assertRegex(form, r'<label class="bym"[^>]* hidden><input type="checkbox"><span>', url)
            self.assertEqual(re.findall(r'\bname="([^"]+)"', form), ["q"], url)
            self.assertIn('action="/search"', form)
        js = (ROOT / "ubsite/static/ub.js").read_text()
        self.assertIn("'ub_bym'", js)
        self.assertIn("'/meaning' + (q ? '#q=' + encodeURIComponent(q) : '')", js)

    def test_ub_js_draws_the_readers_texts_over_the_passages(self):
        js = (ROOT / "ubsite/static/ub.js").read_text()
        for name in ("function meanArt()", "function txtArt()", "function meanDraw()", "'ub:meaning'", "window.ubMeaning"):
            self.assertIn(name, js)

    def test_the_writers_are_held_to_var(self):
        from test_no_writes import ALLOWED
        self.assertEqual(ALLOWED["tools/embed/build.py"], "var/")
        self.assertEqual(ALLOWED["tools/embed/fetch.py"], "var/embed/")


if __name__ == "__main__":
    unittest.main()
