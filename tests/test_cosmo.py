"""The chart of the personalities (build/cosmo.py, readers/cosmo.py,
tools/cosmo/snapshot.py; templates/cosmology.html, static/cosmo.js): Alexander
Alyuev's chart, drawn by the site from the snapshot of his repository.

The snapshot as the tool writes it, and sound; the reader seeing what is
wrong with one that is not; a key the tool does not know stopping it; what
the build derives, a line's path, a card's sign, a name found in the text;
and the page as a reader is sent it: every card and entry once, every address
on it landing, every source a place of the book, and no sign of three circles
about one centre, which is the Foundation's mark and never drawn here
(DECISIONS.md, The sites).
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
DB = ROOT / "var" / "ub.db"
SNAPSHOT = ROOT / "data" / "cosmology" / "chart.json"
STATIC = ROOT / "ubsite" / "static"
TEMPLATES = ROOT / "ubsite" / "templates"

# An id, and not a data-id.
RE_ID = re.compile(r'(?<![\w-])id="([^"]+)"')

from build import cosmo                      # noqa: E402
from build.readers import cosmo as reader    # noqa: E402


@unittest.skipUnless(SNAPSHOT.exists(), "data/cosmology/chart.json is absent")
class Snapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SNAPSHOT.read_text(encoding="utf-8")
        cls.doc = json.loads(cls.text)

    def test_the_file_is_as_the_tool_writes_it(self):
        """A record to a line, by dump(): an edit by hand would not be."""
        from tools.cosmo import snapshot
        self.assertEqual(snapshot.dump(self.doc), self.text)
        self.assertIn("never edit it by hand", self.doc["made"])
        self.assertRegex(self.doc["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertNotIn("fetched", self.text)       # the same commit makes the same file

    def test_its_shape_is_sound(self):
        self.assertEqual(reader.problems(self.doc), [])

    def doctored(self, change) -> list[str]:
        doc = copy.deepcopy(self.doc)
        change(doc)
        return reader.problems(doc)

    def test_the_reader_sees_what_is_wrong(self):
        places = {p["id"]: p for p in self.doc["places"]}
        father, son = places["father"]["at"], places["son"]["at"]

        def twice(d): d["persons"].append(copy.deepcopy(d["persons"][0]))
        def nowhere(d): d["places"][:] = [p for p in d["places"] if p["id"] != "son"]
        def outside(d): next(p for p in d["places"] if p["id"] == "father")["at"] = [0, 0]
        def overlap(d): next(p for p in d["places"] if p["id"] == "son")["at"] = [father[0] + 20, father[1]]
        def no_end(d): d["links"][0]["to"] = "nobody"
        def to_a_unit(d): d["links"][0]["to"] = "paradise"            # no line may end at Paradise
        def aslant(d): d["links"][0]["route"]["en"] = [[0, 0], [50, 70]]
        def off_edge(d):
            # Its first corner drawn back along its own line: still level or
            # upright, and begun short of the card's edge.
            pts = d["links"][0]["route"]["ru"]
            (x0, y0), (x1, y1) = pts[0], pts[1]
            pts[0] = [x0 - 37 * ((x1 > x0) - (x1 < x0)), y0 - 37 * ((y1 > y0) - (y1 < y0))]
        def no_russian(d): del d["persons"][3]["name"]["ru"]
        def one_way(d): next(p for p in d["persons"] if p["id"] == "michael")["pair"] = "son"
        def a_ref(d): d["persons"][0]["refs"] = ["1:2.3"]
        def a_key(d): d["extra"] = 1
        def a_class(d): d["persons"][0]["class"] = "Q"

        def through(d):
            # A line from the Trinity's box straight across the Father's card.
            l = next(x for x in d["links"] if x["from"] != "father" and x["to"] != "father")
            y = father[1] + 20
            l["route"]["en"] = [[father[0] - 40, y], [father[0] + 300, y]]

        for change, word in ((twice, "twice"), (nowhere, "stands nowhere"), (outside, "not inside its unit"),
                             (overlap, "overlap"), (no_end, "no card"), (to_a_unit, "no card"),
                             (aslant, "straight across"), (off_edge, "off the edge"),
                             (no_russian, "no name in ru"), (one_way, "does not name it back"),
                             (a_ref, "not a paper or paper:section"), (a_key, "does not know"),
                             (a_class, "none of the classes"), (through, "runs through father")):
            got = self.doctored(change)
            self.assertTrue(any(word in p for p in got), f"{change.__name__}: {got[:3]}")
        self.assertNotEqual(father, son)

    def test_a_key_the_tool_does_not_know_stops_it(self):
        from tools.cosmo import snapshot
        snapshot.known({"color": "#fff"}, "key", "x")
        with self.assertRaises(snapshot.Unknown) as e:
            snapshot.known({"color": "#fff", "weight": 3}, "key", "classes.T")
        self.assertIn("weight", str(e.exception))
        self.assertIn("classes.T", str(e.exception))

    def test_the_tool_joins_the_words_as_his_loader_does(self):
        """tools/cosmo.py load() of his: a string is a name, a field in each
        language under its code, and none where a language has none."""
        from tools.cosmo import snapshot
        d = {"classes": {"T": {"color": "#000000"}}, "groups": {}, "functions": {},
             "units": [{"id": "u", "color": "#111111", "content": [["a"], {"id": "v", "color": "#222222", "content": []}]}],
             "persons": {"a": {"class": "T"}}, "links": []}
        langs = {"en": {"classes": {"T": "Trinity"}, "units": {"u": {"name": "U", "desc": "the u"}, "v": "V"},
                        "persons": {"a": {"name": "A", "aka": "Alpha", "serves": "here"}}},
                 "ru": {"classes": {"T": "Троица"}, "units": {"u": {"name": "У"}}, "persons": {"a": "А"}}}
        m = snapshot.merged(d, langs)
        self.assertEqual(m["meta"]["languages"], ["en", "ru"])
        self.assertEqual(m["classes"]["T"]["name"], {"en": "Trinity", "ru": "Троица"})
        self.assertEqual(m["units"][0]["name"], {"en": "U", "ru": "У"})
        self.assertEqual(m["units"][0]["desc"], {"en": "the u"})
        self.assertEqual(m["units"][0]["content"][1]["name"], {"en": "V"})
        self.assertEqual(m["persons"]["a"], {"class": "T", "name": {"en": "A", "ru": "А"},
                                             "aka": {"en": "Alpha"}, "serves": {"en": "here"}})
        self.assertNotIn("name", d["persons"]["a"])                 # his data is not written on

    def test_the_headwords_table_is_all_used(self):
        """Every line of data/cosmology/headwords.tsv names one of the chart's,
        which the build would refuse otherwise; and none twice."""
        lines = [ln.split("\t") for ln in cosmo.HEADS.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
        self.assertEqual(lines[0], ["id", "slug", "why"])
        ids = {x["id"] for x in self.doc["units"] + self.doc["persons"]}
        for row in lines[1:]:
            self.assertEqual(len(row), 3, row)
            self.assertIn(row[0], ids)
            self.assertTrue(row[2].strip(), row)
        self.assertEqual(len({(r[0], r[1]) for r in lines[1:]}), len(lines) - 1)


class Derived(unittest.TestCase):
    def test_a_line_s_path_rounds_its_corners(self):
        self.assertEqual(cosmo.path_d([[0, 0], [0, 100]]), "M0,0 L0,100")
        self.assertEqual(cosmo.path_d([[0, 0], [0, 100], [50, 100]]), "M0,0 L0,91 Q0,100 9,100 L50,100")
        # A corner no rounder than half of either side of it.
        self.assertEqual(cosmo.path_d([[0, 0], [0, 10], [10, 10]]), "M0,0 L0,5 Q0,10 5,10 L10,10")
        self.assertEqual(cosmo.path_d([[0, 0], [15, 0], [15, 30]]), "M0,0 L7.5,0 Q15,0 15,7.5 L15,30")

    def test_a_card_s_sign(self):
        for origin, groups, want in (
                ("T", ["supreme"], "trinity"), ("T", ["trin", "par", "desc"], "trinity"),
                ("T", ["deity"], "deity"), ("F", ["deity"], "deity"), ("A", ["deity"], "absolute"),
                ("E", ["asc", "trin"], "ascender"), ("F", ["asc"], "ascender"),
                ("FS", ["par", "desc"], "descending"), ("D", ["angel", "spirit"], "angel"),
                ("FSD", ["local"], "local"), ("FSD", ["local", "desc"], "descending"),
                ("D", ["spirit"], "spirit"), ("", ["unclass"], "spirit"), ("D", ["a-new-group"], "spirit")):
            self.assertEqual(cosmo.glyph(origin, groups)[0], want, (origin, groups))
        # The colour is the group's the sign was chosen by.
        self.assertEqual(cosmo.glyph("FS", ["par", "desc"])[1], "desc")
        self.assertEqual(cosmo.glyph("D", ["a-new-group"])[1], "a-new-group")

    def test_a_name_is_found_in_the_text_by_his_rule(self):
        en = cosmo.fold("The Thought Adjusters’ mission; a Solitary Messenger; the Master Spirit's own")
        self.assertTrue(cosmo.found("Thought Adjuster", en, "en"))
        self.assertTrue(cosmo.found("Solitary Messengers", en, "en"))
        self.assertTrue(cosmo.found("Master Spirits", en, "en"))
        self.assertFalse(cosmo.found("Solitary Adjusters", en, "en"))
        self.assertFalse(cosmo.found("Messenger", cosmo.fold("supermessengers"), "en"))      # not inside a word
        ru = cosmo.fold("тринитизованных Тайн Верховности; Древние Дне\u0301й; о Вечном Сыне; Ещё")
        self.assertTrue(cosmo.found("Тринитизованные Тайны Верховности", ru, "ru"))
        self.assertTrue(cosmo.found("Древние Дней", ru, "ru"))            # the stress mark is not a letter
        self.assertTrue(cosmo.found("Вечный Сын", ru, "ru"))              # a stem, with any ending
        self.assertTrue(cosmo.found("еще", ru, "ru"))                     # ё as е
        self.assertFalse(cosmo.found("Бесконечный Дух", ru, "ru"))
        self.assertEqual(cosmo.parts("Михаилы — Сыны-Создатели (Творцы)"), ["Михаилы", "Сыны-Создатели", "Творцы"])


@unittest.skipUnless(DB.exists() and SNAPSHOT.exists(), "var/ub.db has not been built, or the snapshot is absent")
class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_appendix_pages import get
        cls.get = staticmethod(get)
        cls.doc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.status, _, cls.raw = get("/cosmology", raw=True)
        cls.body = get("/cosmology")[2]
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_the_database_holds_the_snapshot(self):
        stat = dict(self.con.execute("SELECT key, value FROM stat WHERE key LIKE 'cosmo_%'"))
        self.assertEqual(stat["cosmo_persons"], len(self.doc["persons"]))
        self.assertEqual(stat["cosmo_units"], len(self.doc["units"]))
        self.assertEqual(stat["cosmo_links"], len(self.doc["links"]))
        row = self.con.execute("SELECT commit_id, rev FROM build_source WHERE repo='cosmology'").fetchone()
        self.assertEqual(row, (self.doc["source"]["commit"], "snapshot"))

    def test_every_card_and_entry_stands_once(self):
        self.assertEqual(self.status, 200)
        places = {p["id"] for p in self.doc["places"]}
        cards = re.findall(r'<a class="cp( ghost)?" id="([cg])-(\w+)" href="#(\w+)" data-id="(\w+)"', self.body)
        self.assertEqual(len(cards), len(places))
        self.assertEqual({("~" if g else "") + i for g, _, i, _, _ in cards}, places)
        for ghost, kind, i, href, did in cards:
            self.assertEqual((kind, href, did), ("g" if ghost else "c", i, i))
        entries = re.findall(r'<article class="ci (unit|person)" id="(\w+)"', self.body)
        self.assertEqual(sorted(i for _, i in entries),
                         sorted(x["id"] for x in self.doc["units"] + self.doc["persons"]))
        self.assertEqual(len(re.findall(r'<g class="ce ', self.body)), len(self.doc["links"]))
        self.assertEqual(len(re.findall(r'<rect class="cu"', self.body)), len(self.doc["units"]))

    def test_every_id_is_one_and_none_is_the_shell_s(self):
        ids = RE_ID.findall(self.body)
        self.assertEqual(len(ids), len(set(ids)), [i for i in set(ids) if ids.count(i) > 1][:5])
        base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        shell = set(re.findall(r'(?<![\w-])id="([\w-]+)"', base)) | {"ub-tr"}
        main = self.body[self.body.index("<main"):self.body.index("</main>")]
        self.assertEqual(set(RE_ID.findall(main)) & shell, set())

    def test_every_address_on_the_page_lands(self):
        main = self.body[self.body.index("<main"):self.body.index("</main>")]
        ids = set(RE_ID.findall(main))
        for h in set(re.findall(r'href="#([^"]+)"', main)):
            self.assertIn(h, ids)
        secs = {(p, s) for p, s in self.con.execute("SELECT paper_n, n FROM section")}
        refs = re.findall(r'<a class="cref" href="/(\d+)(?::(\d+))?">', main)
        self.assertEqual(len(refs), sum(len(x["refs"]) for x in self.doc["units"] + self.doc["persons"]))
        for p, s in refs:
            self.assertIn((int(p), int(s or 0)), secs)
        slugs = {s for (s,) in self.con.execute("SELECT slug FROM index_entry WHERE scope='az' AND level=1")}
        heads = re.findall(r'href="/i/([^"#]+)"', main)
        self.assertGreater(len(heads), 100)
        for s in heads:
            self.assertIn(s, slugs)
        # A line's two ends are a card's id or a unit's a line may end at.
        ends = {p["id"] for p in self.doc["places"]} | {u["id"] for u in self.doc["units"] if u.get("linkable")}
        for a, b in re.findall(r'<g class="ce [a-z ]+" data-a="([^"]+)" data-b="([^"]+)">', main):
            self.assertIn(a, ends)
            self.assertIn(b, ends)

    def test_no_sign_is_three_circles_about_one_centre(self):
        """His page's sign for Trinity origin is three concentric azure
        circles, the Foundation's mark: ours is three rings interlaced, each
        about its own centre.  No sign has three circles about one centre,
        and none a ring within a ring."""
        signs = re.findall(r'<svg class="cg".*?</svg>', self.raw, re.S)
        self.assertGreater(len(signs), 130)
        trinity = 0

        def centres(circles):
            at = [(re.search(r'\bcx="([^"]+)"', c), re.search(r'\bcy="([^"]+)"', c)) for c in circles]
            return [(float(x[1]) if x else 0.0, float(y[1]) if y else 0.0) for x, y in at]

        for s in signs:
            every = centres(re.findall(r"<(?:circle|ellipse)\b[^>]*>", s))
            self.assertLess(max(every.count(c) for c in every) if every else 0, 3, s[:200])
            rings = centres(re.findall(r'<circle class="gt"[^>]*>', s))        # the only circles not filled
            self.assertEqual(len(rings), len(set(rings)), s[:200])
            trinity += len(rings) == 3
        # Every card of Trinity origin but a Deity's, and the legend's one.
        want = sum(1 for (g,) in self.con.execute(
            "SELECT p.glyph FROM cosmo_place c JOIN cosmo_person p ON p.id = c.person") if g == "trinity")
        self.assertEqual(trinity, want + 1)
        css = (STATIC / "ub.css").read_text(encoding="utf-8")
        self.assertIn(".cg .gt { fill: none;", css)

    def test_both_languages_are_drawn_and_each_line_twice(self):
        self.assertIn("<x-en>Cosmology of Personalities</x-en><x-ru lang=\"ru\">Космология личностей</x-ru>", self.raw)
        self.assertEqual(self.raw.count('<g class="en"><path class="h"'), len(self.doc["links"]))
        self.assertEqual(self.raw.count('<g class="ru"><path class="h"'), len(self.doc["links"]))
        father = next(p for p in self.doc["persons"] if p["id"] == "father")["name"]
        self.assertIn(f'<x-en>{father["en"]}</x-en><x-ru lang="ru">{father["ru"]}</x-ru>', self.raw)
        # A unit's title carries the width his page drew it at, in each.
        u = self.doc["units"][0]
        self.assertIn(f'data-en="{u["title"]["en"]}" data-ru="{u["title"]["ru"]}"', self.raw)

    def test_the_ways_in(self):
        home = self.get("/")[2]
        self.assertIn('<a href="/cosmology">Cosmology of Personalities</a>', home)
        slug = self.con.execute("SELECT slug FROM cosmo_head WHERE kind='person' AND key='michael'").fetchone()[0]
        concept = self.get(f"/i/{slug}")[2]
        self.assertIn('<a href="/cosmology#michael">', concept)
        self.assertNotIn("/cosmology", self.get("/i/god")[2])
        app_b = self.get("/appendix/B")[2]
        marks = re.findall(r'<a class="tochart" href="/cosmology#(\w+)"', app_b)
        self.assertGreater(len(marks), 50)
        entries = set(re.findall(r'<article class="ci (?:unit|person)" id="(\w+)"', self.body))
        self.assertLessEqual(set(marks), entries)
        self.assertNotIn("tochart", self.get("/appendix/D")[2])
        self.assertIn('<section id="chart">', self.get("/help")[2])

    def test_one_address(self):
        self.assertEqual(self.get("/cosmology/")[0], 307)
        self.assertEqual(self.get("/cosmology/x")[0], 404)
        self.assertEqual(self.get("/Cosmology")[0], 404)


class Static(unittest.TestCase):
    def test_the_scripts_know_the_chart(self):
        ub = (STATIC / "ub.js").read_text(encoding="utf-8")
        # Not the tour's first page; its addresses its own; its script run for a <main> brought in.
        self.assertIn("/^\\/(help$|quiz|api$|stats$|cosmology$)/", ub)
        self.assertIn("if (document.querySelector('main.cosmo')) return;", ub)
        self.assertIn("if (window.ubCosmo) return window.ubCosmo();", ub)
        js = (STATIC / "cosmo.js").read_text(encoding="utf-8")
        self.assertIn("window.ubCosmo = init;", js)
        self.assertNotIn("localStorage", js)            # it keeps nothing
        self.assertNotIn("fetch(", js)                  # and asks for nothing
        tpl = (TEMPLATES / "cosmology.html").read_text(encoding="utf-8")
        # The ids go before the deferred scripts look, ub.js's arrive() among them.
        self.assertLess(tpl.index("e.removeAttribute('id')"), tpl.index("asset('cosmo.js') }}\" defer"))

    def test_the_offline_copy_keeps_it(self):
        from offline import pack
        self.assertIn("cosmo.js", pack.ASSETS)
        core = (STATIC / "offline-core.js").read_text(encoding="utf-8")
        self.assertIn("if (path === '/cosmology' && sh.cosmo !== false) {", core)
        self.assertIn("chunk: 'cosmo'", core)
        pages = (ROOT / "offline" / "pages.py").read_text(encoding="utf-8")
        self.assertIn('chunks["cosmo"] = {"pages": {"/cosmology": own("/cosmology"', pages)

    def test_a_snapshot_not_committed_is_not_deployed(self):
        sh = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
        self.assertIn('if [ -n "$(git status --porcelain -- data/cosmology)" ]; then', sh)

    def test_the_build_never_reads_his_repository(self):
        """build/ reads the snapshot; only the tool reads the repository, at a
        commit, through _io."""
        for f in ("build/cosmo.py", "build/readers/cosmo.py"):
            src = (ROOT / f).read_text(encoding="utf-8")
            for word in ("_io", "subprocess", "import yaml", "playwright"):
                self.assertFalse(word in src, f"{f} names {word}")
        tool = (ROOT / "tools/cosmo/snapshot.py").read_text(encoding="utf-8")
        self.assertEqual(tool.count("_io.read_at_rev(repo, "), 3)
        self.assertIn('_io.list_at_rev(repo, "data/lang", at)', tool)
        self.assertIn("route.abort()", tool)            # his page asks the network for nothing, or stops it


if __name__ == "__main__":
    unittest.main()
