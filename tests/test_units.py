"""Unit conversions and the charts (Tigran, 2026-11-22).

data/units.toml as build/units.py reads it: each unit the size the book says,
exactly; the gates that hold the papers' words and their own cross-checks
failing when either is broken; the pages /units and /charts, and the home
page's tile to the second; the script's numbers written as the server writes
them; and both pages and the script in the offline copy.
"""

from __future__ import annotations

import json
import math
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import unittest
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
DB = ROOT / "var" / "ub.db"
STATIC = ROOT / "ubsite" / "static"

from build import units                      # noqa: E402
from build.problems import Report            # noqa: E402


def sized() -> units.Units:
    r = Report()
    U = units.Units(units.read(), r)
    assert not r.problems, r.problems
    return U


class Sizes(unittest.TestCase):
    """What the papers say, to the second, and the familiar units' standards."""

    @classmethod
    def setUpClass(cls):
        cls.U = sized()

    def test_the_papers_time(self):
        s = self.U.size
        self.assertEqual(s["year"], 31557600)                        # 365¼ days, 57:0.1
        self.assertEqual(s["phday"], Fraction("31557599576.875"))     # 1000 years less 7 min 3⅛ s, 14:1.12
        self.assertEqual(s["uvyear"], 259198680)                      # 3000 days less 22 min, 15:7.2
        self.assertEqual(s["uvday"] * 100, s["uvyear"])
        self.assertEqual(s["nbday"], 1576950)                        # 18 d 6 h 2½ min, 33:6.7
        self.assertEqual(s["nbyear"], 100 * s["nbday"])
        self.assertEqual(s["dekamil"], 10000 * s["nbyear"])           # 35:6.1
        self.assertEqual(s["jday"], 255345)                          # 3 d less 1 h 4 min 15 s, 46:1.2
        self.assertEqual(s["jweek"], 10 * s["jday"])                  # 45:2.5
        self.assertEqual(s["sysyear"], 100 * s["jday"])               # 46:1.2

    def test_distance_speed_weight(self):
        s = self.U.size
        self.assertEqual(s["mile"], Fraction("1609.344"))
        self.assertEqual(s["jmile"], 7 * s["mile"])
        self.assertEqual(s["lightyear"], 299792458 * 31557600)
        self.assertAlmostEqual(float(s["parsec"]) / (648000 / math.pi * float(s["au"])), 1, places=15)
        self.assertEqual(s["vlimit"], 186280 * s["mile"])
        self.assertEqual(s["vdouble"], 2 * s["vlimit"])
        self.assertEqual(s["vtriple"], 3 * s["vlimit"])
        self.assertEqual(s["pound"], Fraction("0.45359237"))
        self.assertEqual(s["gradant"], 10 * s["pound"] / 16)
        self.assertEqual(s["ton"], 2000 * s["pound"])

    def test_about_is_carried(self):
        about = {k for k, v in self.U.about.items() if v}
        self.assertEqual(about, {"jmile", "jmileps", "vtriple", "gradant"})

    def test_temperature(self):
        c = self.U.convert
        self.assertAlmostEqual(c(-40, "fahrenheit", "celsius"), -40, places=9)
        self.assertAlmostEqual(c(32, "fahrenheit", "kelvin"), 273.15, places=9)
        self.assertAlmostEqual(c(100, "celsius", "fahrenheit"), 212, places=9)
        self.assertAlmostEqual(c(0, "kelvin", "fahrenheit"), -459.67, places=9)

    def test_the_book_checks_itself(self):
        c = self.U.convert
        self.assertAlmostEqual(c(25000, "sysyear", "year"), 20228.487, places=3)    # 54:6.6, "twenty thousand"
        self.assertAlmostEqual(c(1, "uvyear", "year"), 8.2135, places=4)            # 15:7.2, "eight and one fifth"
        self.assertLess(c(1, "phday", "year"), 1000)                                # 14:1.12, "almost"
        self.assertLess(c(1, "uvday", "day"), 30)                                   # 15:7.2, "almost thirty"

    def test_expressions(self):
        self.assertEqual(units.terms("3 day - 1 hour"), [(3, "day", None), (-1, "hour", None)])
        self.assertEqual(units.terms("1/16 pound"), [(Fraction(1, 16), "pound", None)])
        self.assertEqual(units.terms("1 mile/second"), [(1, "mile", "second")])
        for bad in ("", "3 day 1 hour", "+3 day", "3 Day", "day -", "3 day * 2"):
            self.assertIsNone(units.terms(bad), bad)


def broken(edit) -> list:
    """The hard problems of data/units.toml with `edit` made to it, loaded into
    a copy of what the build reads from ub.db."""
    doc = units.read()
    edit(doc)
    con = sqlite3.connect(":memory:")
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.executescript((ROOT / "build" / "schema" / "015_units.sql").read_text(encoding="utf-8"))
    con.execute("CREATE TABLE paragraph (id INTEGER, ref TEXT, text TEXT)")
    con.execute("CREATE TABLE translation (key TEXT)")
    con.execute("CREATE TABLE tr_paragraph (paragraph_id INTEGER, translation TEXT, text TEXT)")
    con.execute("CREATE TABLE index_entry (level INTEGER, slug TEXT)")
    con.executemany("INSERT INTO paragraph VALUES (?,?,?)", src.execute("SELECT id, ref, text FROM paragraph"))
    con.executemany("INSERT INTO translation VALUES (?)", src.execute("SELECT key FROM translation"))
    con.executemany("INSERT INTO tr_paragraph VALUES (?,?,?)",
                    src.execute("SELECT paragraph_id, translation, text FROM tr_paragraph WHERE translation = 'uf-ru'"))
    con.executemany("INSERT INTO index_entry VALUES (?,?)",
                    src.execute("SELECT level, slug FROM index_entry WHERE level = 1"))
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "units.toml"
        path.write_text(dump(doc), encoding="utf-8")
        r = Report()
        units.load(con, r, path)
    return [(p.code, p.message) for p in r.problems if p.severity == "hard"]


def dump(doc: dict) -> str:
    """Enough TOML for data/units.toml's shapes: tables of strings, numbers,
    booleans and inline tables of those."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{k} = {val(x)}" for k, x in v.items()) + " }"
        return json.dumps(v, ensure_ascii=False)
    out = []
    for kind in ("group", "band", "unit", "example"):
        for row in doc.get(kind, []):
            out.append(f"[[{kind}]]")
            out += [f"{k} = {val(v)}" for k, v in row.items()]
            out.append("")
    return "\n".join(out)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Gates(unittest.TestCase):
    def test_the_file_passes(self):
        self.assertEqual(broken(lambda d: None), [])

    def unit(self, d, k):
        return next(u for u in d["unit"] if u["key"] == k)

    def test_words_not_in_the_paragraph(self):
        got = broken(lambda d: self.unit(d, "jday").update(words="The Satania day equals four days"))
        self.assertEqual([c for c, _ in got], ["units-words"])

    def test_russian_words_not_in_uf_ru(self):
        got = broken(lambda d: self.unit(d, "gradant").update(words_ru="градант весит фунт"))
        self.assertEqual([c for c, _ in got], ["units-words"])

    def test_words_that_occur_twice_or_inside_a_word(self):
        got = broken(lambda d: self.unit(d, "jmile").update(words="mile"))
        self.assertEqual([c for c, _ in got], ["units-words"])

    def test_a_cross_check_the_table_fails(self):
        def edit(d):
            d["example"][5]["says"]["value"] = 15000       # 54:6.6's twenty thousand
        got = broken(edit)
        self.assertEqual([c for c, _ in got], ["units-says"])

    def test_a_circle_and_a_mixed_table(self):
        got = broken(lambda d: self.unit(d, "day").update(size="1 jday"))
        self.assertIn("units-circle", [c for c, _ in got])
        got = broken(lambda d: self.unit(d, "gradant").update(size="10 mile"))
        self.assertEqual([c for c, _ in got], ["units-size"])

    def test_a_unit_neither_the_books_nor_familiar(self):
        got = broken(lambda d: self.unit(d, "hour").pop("def"))
        self.assertEqual([c for c, _ in got], ["units-what"])

    def test_an_index_headword_there_is_not(self):
        got = broken(lambda d: d["group"][0].update(index="no-such-headword"))
        self.assertEqual([c for c, _ in got], ["units-index"])


class Numbers(unittest.TestCase):
    """static/units.js fmt() writes every number as queries.unit_number does."""

    VALUES = [0, 1, -1, 0.1 + 0.2, 1234.5, 12345.5, 5280.000000000001, 365249.9951027199, 999.99998659,
              -39.99999999999997, 0.0000012, 4.4704e-7, 1354458739822848.0, 2e27, 0.28349523125,
              123456789012345.6, 999999999999999.9, 0.000001, 9.99999999999e-7, 20228.486957183057]

    def test_the_server_writes_them(self):
        from ubsite.queries import unit_number
        self.assertEqual(unit_number(1234.5, "en"), "1,234.5")
        self.assertEqual(unit_number(1234.5, "ru"), "1234,5")
        self.assertEqual(unit_number(12345.5, "ru"), "12 345,5")
        self.assertEqual(unit_number(-39.99999999999997, "en"), "−40")
        self.assertEqual(unit_number(2e27, "en"), "2 × 10^27")
        self.assertEqual(unit_number(4.4704e-7, "ru"), "4,4704 × 10^−7")
        self.assertEqual(unit_number(365249.9951027199, "en"), "365,249.995103")

    @unittest.skipUnless(shutil.which("node"), "no Node")
    def test_the_script_writes_them_alike(self):
        from ubsite.queries import unit_number
        js = (STATIC / "units.js").read_text(encoding="utf-8")
        fmt = js[js.index("  function fmt(x, lg) {"):]
        fmt = fmt[:fmt.index("\n  }\n") + 4]
        prog = fmt + f"\nconsole.log(JSON.stringify({json.dumps(self.VALUES)}.map(function (x) {{" \
                     " return [fmt(x, 'en'), fmt(x, 'ru')]; })));"
        out = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
        for x, (en, ru) in zip(self.VALUES, out):
            self.assertEqual((en, ru), (unit_number(x, "en"), unit_number(x, "ru")), x)


    @unittest.skipUnless(shutil.which("node"), "no Node")
    def test_what_the_script_reads(self):
        """Tigran, 2026-11-22: "Is the Unicode symbol '×' required or can one
        enter asterisk '*' or just 'x'?"  Any of them, before a power of ten."""
        js = (STATIC / "units.js").read_text(encoding="utf-8")
        parse = js[js.index("  function parse(s, lg) {"):]
        parse = parse[:parse.index("\n  }\n") + 4]
        cases = {"2*10^27": 2e27, "2 x 10^27": 2e27, "2X10^27": 2e27, "2·10^27": 2e27, "2 × 10^−7": 2e-7,
                 "2e27": 2e27, "10^27": 1e27, "-10^3": -1000, "1.5 × 10⁻³": 0.0015, "1,234.5": 1234.5,
                 "1\u202f000": 1000, "7*5280": None, "abc": None, "": None}
        prog = "var SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';\n" + parse + f"\nconsole.log(JSON.stringify({json.dumps(list(cases))}" \
               ".map(function (x) { return [parse(x, 'en'), parse(x.replace('.', ','), 'ru')]; })));"
        out = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
        for (typed, want), (en, ru) in zip(cases.items(), out):
            self.assertEqual(en, want, typed)
            if "," not in typed:
                self.assertEqual(ru, want, typed + " in Russian, its point a comma")


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_appendix_pages import get
        cls.get = staticmethod(get)
        cls.status, _, cls.raw = get("/units", raw=True)
        cls.body = get("/units")[2]
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    def test_every_unit_a_row_with_its_value(self):
        self.assertEqual(self.status, 200)
        keys = [k for (k,) in self.con.execute("SELECT key FROM unit ORDER BY group_key, n")]
        self.assertEqual(sorted(re.findall(r'<tr data-u="(\w+)"', self.body)), sorted(keys))
        # The table opens at the build's start, as the server works it out.
        self.assertRegex(self.body, r'<tr data-u="phday"[^>]*>\s*<td class="ucv"><input [^>]*value="1"')
        self.assertRegex(self.body, r'<tr data-u="year"[^>]*>\s*<td class="ucv"><input [^>]*value="999.999986592"')
        self.assertRegex(self.body, r'<tr data-u="fahrenheit"[^>]*>\s*<td class="ucv"><input [^>]*value="70"')
        for g in ("time", "distance", "speed", "weight", "temperature"):
            self.assertIn(f'<section class="ucg" id="{g}" data-g="{g}">', self.body)

    def test_the_papers_words_with_their_paragraph(self):
        self.assertIn("<q>The standard mile of Jerusem is equivalent to about seven Urantia miles.</q>"
                      ' <a href="/46:1.2">46:1.2</a>', self.body)
        # An ellipsis where the words begin or end inside a sentence.
        self.assertIn("<q>…the present leap-year calendar of 365¼ days to the year…</q>", self.body)
        # The Russian, the Foundation's.
        self.assertIn('<x-ru lang="ru"><q>Стандартная иерусемская миля равна примерно семи урантийским милям.</q></x-ru>',
                      self.raw)
        self.assertIn('<x-en>Paradise-Havona standard day</x-en><x-ru lang="ru">стандартный день системы Рай-Хавона</x-ru>',
                      self.raw)
        self.assertEqual(self.body.count('class="ucab"'), 4 + 1)     # four units, and the lead
        self.assertIn('<a class="ucgo" href="#sysyear=25000" data-to="year">', self.body)
        self.assertIn('<a href="/i/time">time</a>', self.body)

    def test_the_data_for_the_script(self):
        data = json.loads(re.search(r'<script type="application/json" class="ucdata">(.*?)</script>', self.raw, re.S)[1])
        self.assertEqual(data["units"]["jday"], ["time", 255345.0, 0.0])
        self.assertEqual(data["start"]["temperature"], ["fahrenheit", 70.0])
        self.assertIn('<main class="prose units" data-src="/static/units.js?v=', self.raw)
        # No row has an id for arrive() to scroll to (CLAUDE.md trap 52).
        self.assertNotRegex(self.raw, r'<tr [^>]*\bid=')

    def test_charts_and_the_tile(self):
        status, _, charts = self.get("/charts")
        self.assertEqual(status, 200)
        # A card to each, the chart's first, its picture the chart in
        # miniature, drawn from the data (queries.charts_minis).
        self.assertEqual(re.findall(r'<a class="minicard" href="(/\w+)">', charts), ["/cosmology", "/units"])
        cosmo = charts[charts.index('<svg class="minipic cosmo"'):]
        cosmo = cosmo[:cosmo.index("</svg>")]
        h = int(re.search(r'viewBox="0 0 1900 (\d+)"', cosmo)[1])
        self.assertEqual(h, 1188)
        cards = self.con.execute("SELECT COUNT(*) FROM cosmo_place WHERE y < ?", (h,)).fetchone()[0]
        self.assertEqual(cosmo.count('<rect class="minip"'), cards)
        self.assertGreater(cosmo.count('<path class="minie"'), 50)
        self.assertNotIn("<text", cosmo)                     # no words, in either language
        units = charts[charts.index('<svg class="minipic units"'):]
        units = units[:units.index("</svg>")]
        self.assertIn('<text class="miniv en" x="632" y="366">121.750618394</text>', units)
        _, _, raw = self.get("/charts", raw=True)
        self.assertIn('<text class="miniv ru" x="632" y="490">12\u202f175,0618394</text>', raw)
        home = self.get("/")[2]
        self.assertRegex(home, r'<li><a href="/charts"><svg [^>]*>.*?</svg><span class="lbl">Charts</span>')
        self.assertEqual(len(re.findall(r"<li[ >]", home[home.index('<ul class="ftiles">'):home.index("</ul>", home.index('<ul class="ftiles">'))])), 8)
        help_ = self.get("/help")[2]
        self.assertIn('<a href="/units">Unit conversions</a>', help_)

    def test_one_address_each(self):
        for p in ("/units", "/charts"):
            self.assertEqual(self.get(p + "/")[0], 307)
            self.assertEqual(self.get(p + "/x")[0], 404)
            self.assertEqual(self.get(p.title())[0], 404)


class Wiring(unittest.TestCase):
    def test_the_script_and_its_words(self):
        from ubsite import app
        self.assertIn("units.js", app.L10N_SCRIPTS)
        js = (STATIC / "units.js").read_text(encoding="utf-8")
        self.assertIn("window.ubUnits = init;", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("fetch(", js)
        ub = (STATIC / "ub.js").read_text(encoding="utf-8")
        self.assertIn("if (window.ubUnits) return window.ubUnits();", ub)
        # listen.js, which every section's page names, knows nothing of it (trap 51).
        self.assertNotIn("units", (STATIC / "listen.js").read_text(encoding="utf-8"))

    def test_the_offline_copy_keeps_both(self):
        from offline import pack
        self.assertIn("units.js", pack.ASSETS)
        core = (STATIC / "offline-core.js").read_text(encoding="utf-8")
        self.assertIn("if (path === '/charts/' || path === '/units/')", core)

    @unittest.skipUnless(DB.exists(), "var/ub.db not built")
    def test_the_pages_are_in_misc(self):
        from offline import pages
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        misc = pages.universe(con)["misc"]
        self.assertIn("/charts", misc)
        self.assertIn("/units", misc)

    def test_the_fonts_draw_what_the_script_writes(self):
        from build import fonts
        self.assertLessEqual(set("−× "), set(fonts.SCRIPTED))
        self.assertIn("≈", fonts.ELSEWHERE)

    def test_expectations(self):
        with open(ROOT / "verify" / "expectations.toml", "rb") as fh:
            want = tomllib.load(fh)["units"]
        doc = units.read()
        self.assertEqual(want["units"], len(doc["unit"]))
        self.assertEqual(want["book_units"], sum("ref" in u for u in doc["unit"]))
        self.assertEqual(want["examples"], len(doc["example"]))
        self.assertEqual(want["gated"], sum("says" in x for x in doc["example"]))


if __name__ == "__main__":
    unittest.main()
