"""The whole paper on one page, /15, and Settings' Whole paper (2026-10-30).

A paper's address is the whole paper: every section's text, as its own page
sets it, under one head, the paper's notes at its end, and a transport bar of
the two paper buttons alone; in Compare, /15/compare, the same page.  Whether a reader sees it or the paper's first
section is the setting, decided in the browser by base.html's ubUnit, which
these hold to its cases in Node, as test_l10n holds l10n.js.  Each section's
piece of the text is byte for byte the piece in its own page, which is what
lets the offline copy join the whole from them (test_offline).  Rendered
through the app as ASGI, as test_appendix_pages does; skipped when var/ub.db
has not been built.
"""

import json
import re
import shutil
import sqlite3
import subprocess
import unittest

from test_appendix_pages import DB, get
from test_transport import bar
from ubsite import settings
from ubsite.stats import page_kind

RE_SEC = re.compile(r'<section id="(\d+):(\d+)"[^>]*>')
RE_PARA = re.compile(r'<p class="t[^"]*"\n\s+id="(\d+:\d+\.\d+)">')


def inner(body: str, paper: int, sec: int) -> str:
    """Section paper:sec's text in a page, as offline/pages.py inner() cuts it."""
    tag = f'<section id="{paper}:{sec}"'
    assert body.count(tag) == 1, (paper, sec, body.count(tag))
    i = body.index(">", body.index(tag)) + 1
    return body[i:body.index("</section>", i)]


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class WholePaper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.papers = [n for (n,) in con.execute("SELECT n FROM paper ORDER BY n")]
        cls.sections = {}
        for p, s in con.execute("SELECT paper_n, n FROM section ORDER BY paper_n, n"):
            cls.sections.setdefault(p, []).append(s)
        cls.refs = {}
        for p, ref in con.execute("SELECT paper_n, ref FROM paragraph ORDER BY paper_n, section_n, para_n"):
            cls.refs.setdefault(p, []).append(ref)
        cls.quiz = {n for (n,) in con.execute("SELECT paper_n FROM quiz_paper")}

    def test_every_paper_opens_with_section_0(self):
        # ubUnit sends /15 to /15:0 with the setting off, with no table.
        self.assertEqual(len(self.papers), 197)
        for p in self.papers:
            self.assertEqual(self.sections[p][0], 0, p)

    def test_the_whole_paper_is_every_section_in_order(self):
        for p in (15, 139):
            status, _, body = get(f"/{p}")
            self.assertEqual(status, 200)
            self.assertEqual([(int(a), int(b)) for a, b in RE_SEC.findall(body)],
                             [(p, s) for s in self.sections[p]])
            self.assertEqual(RE_PARA.findall(body), self.refs[p])
            self.assertEqual(body.count('<p class="papernum">'), 1)
            self.assertEqual(body.count("<h1>"), 1)
            self.assertEqual(body.count("<h2>"), len(self.sections[p]) - 1)
            # What the whole paper cites stands once, over section 0 (Paper 15
            # has 470 citations); the paper's notes stand once, at its end.
            self.assertLessEqual(body.count("Cited across this whole paper"), 1)
            if p == 15:
                self.assertEqual(body.count("Cited across this whole paper"), 1)
            self.assertLessEqual(body.count('<section class="notes" '), 1)
            self.assertLessEqual(body.count('<section class="notes st" '), 1)
            self.assertIn('<article class="whole" style="--refw: ', body)
            self.assertEqual('class="quizcall"' in body, p in self.quiz)

    def test_139s_combined_section_is_titled_so(self):
        _, _, body = get("/139")
        self.assertRegex(body, r'<section id="139:9"[^>]*><header class="papertop"><h2>9 and 10\. ')
        self.assertNotIn('id="139:10"', body)

    def test_the_paper_buttons_alone_by_the_papers_own_addresses(self):
        links, off = bar("/15")
        self.assertEqual(links, {"fb": ("14", "Previous paper: 14"), "ff": ("16", "Next paper: 16")})
        self.assertEqual(off, [])
        links, off = bar("/1")
        self.assertEqual(links["fb"], ("0", "Previous paper: the Foreword"))
        links, off = bar("/0")
        self.assertEqual((list(links), off), (["ff"], ["fb"]))
        links, off = bar(f"/{self.papers[-1]}")
        self.assertEqual((list(links), off), (["fb"], ["ff"]))

    def test_each_sections_piece_is_the_one_in_its_own_page(self):
        # The premise of the offline copy's joining (offline/pages.py holes).
        for p in (1, 15, 139, 144):
            whole = get(f"/{p}", raw=True)[2]
            for s in self.sections[p]:
                own = inner(get(f"/{p}:{s}", raw=True)[2], p, s)
                self.assertEqual(whole.count(own), 1, f"{p}:{s}")

    def test_its_listening_is_one_unit_of_many_sections(self):
        body = get("/15", raw=True)[2]
        j = json.loads(re.search(r'id="ub-audio">(.*?)</script>', body, re.S)[1])
        self.assertEqual((j["paper"], j["section"], j["whole"]), (15, None, True))
        self.assertEqual(j["next"]["href"], "/16")
        self.assertTrue(j["next"]["label"].startswith("Paper 16. "))
        v = j["voices"]["mh"]
        self.assertEqual(len(v["files"]), len(set(v["files"])))
        heads = [s[0] for s in v["segs"] if "." not in s[0]]
        self.assertEqual(heads, [f"15:{s}" for s in self.sections[15]])
        paras = [s[0] for s in v["segs"] if "." in s[0]]
        self.assertEqual(paras, [r for r in self.refs[15] if r in paras])   # in the book's order
        files = [s[1] for s in v["segs"]]
        self.assertEqual(files, sorted(files))
        # A section's own page keeps its heading's ref null.
        j = json.loads(re.search(r'id="ub-audio">(.*?)</script>', get("/15:3", raw=True)[2], re.S)[1])
        self.assertEqual(j["voices"]["mh"]["segs"][0][0], None)
        self.assertNotIn("whole", j)

    def test_compare_is_the_same_page_with_its_toggle(self):
        plain, cmp = get("/15", raw=True), get("/15/compare", raw=True)
        self.assertEqual((plain[0], cmp[0]), (200, 200))
        self.assertEqual(plain[2], cmp[2])
        self.assertEqual(plain[2].count('class="cmphead"'), 1)
        # Each section carries the version its translations are asked for under.
        self.assertEqual(len(re.findall(r'<section id="15:\d+" data-trv="[0-9a-f]{12}">', plain[2])),
                         len(self.sections[15]))

    def test_what_is_not_a_paper(self):
        status, _, body = get("/300")
        self.assertEqual(status, 404)
        self.assertIn("There is no Paper 300.", body)

    def test_the_setting_is_off_by_default_and_has_no_css(self):
        self.assertIs(settings.defaults()["whole"], False)
        css = (DB.parent.parent / "ubsite" / "static" / "ub.css").read_text()
        self.assertNotIn('data-whole', css)
        self.assertIn("window.ubUnit = function", get("/15:3")[2])

    def test_a_whole_paper_is_a_page_to_the_stats(self):
        self.assertEqual(page_kind("/15"), ("paper", "15"))
        self.assertEqual(page_kind("/015"), ("paper", "15"))
        self.assertEqual(page_kind("/15:3"), ("section", "15:3"))


# The head script's ubUnit, run in Node with the setting off and on.
CASES = {
    "off": {"/15": "/15:0", "/0": "/0:0", "/15:3": "/15:3", "/15:3.4": "/15:3.4", "/15:3.4-6": "/15:3.4-6",
            "/15#15:3": "/15:3", "/15#15:3.4": "/15:3.4", "/15#15:3.4-6": "/15:3.4-6",
            "/15#15:3.4#tr-ud": "/15:3.4#tr-ud", "/15#note15_3_4_0": "/15:3.4#note15_3_4_0",
            "/15#notest15_3_4_0": "/15:3.4#notest15_3_4_0", "/15#notetn_ud_15_3_4_0": "/15:3.4#notetn_ud_15_3_4_0",
            "/15#fnref15_3_4_0": "/15:3.4#fnref15_3_4_0", "/15#listen": "/15:0#listen", "/15#16:3": "/15:0#16:3",
            "/15:3#note15_3_4_0": "/15:3#note15_3_4_0",
            "/15/compare": "/15:0/compare", "/15/compare#15:3": "/15:3/compare", "/15/compare#15:3.4#tr-ud": "/15:3.4/compare#tr-ud",
            "/15:3/compare": "/15:3/compare", "/15:3.4/compare#tr-ud": "/15:3.4/compare#tr-ud", "/i/god": "/i/god", "/": "/"},
    "on": {"/15": "/15", "/15:0": "/15", "/15:3": "/15#15:3", "/15:3.4": "/15#15:3.4", "/15:3.4-6": "/15#15:3.4-6",
           "/15:0.3": "/15#15:0.3", "/15:3.4#tr-ud": "/15#15:3.4#tr-ud", "/15:3.4#note15_3_4_0": "/15#note15_3_4_0",
           "/15:3.4#notetn_ud_15_3_4_0": "/15#notetn_ud_15_3_4_0", "/16:0#listen": "/16#16:0#listen",
           "/15#15:3": "/15#15:3", "/15#listen": "/15#listen",
           "/15:3/compare": "/15/compare#15:3", "/15:0/compare": "/15/compare", "/15:3.4/compare#tr-ud": "/15/compare#15:3.4#tr-ud",
           "/15/compare": "/15/compare", "/15/compare#15:3": "/15/compare#15:3", "/i/god": "/i/god"},
}


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
@unittest.skipUnless(shutil.which("node"), "Node is not installed")
class Unit(unittest.TestCase):
    def test_every_address_in_the_readers_unit(self):
        body = get("/", raw=True)[2]
        fn = re.search(r"window\.ubUnit = function[\s\S]*?\n};", body)[0]
        js = ("var document = { documentElement: { dataset: {} } }, window = {};\n" + fn +
              "\nvar cases = " + json.dumps(CASES) + ", out = {};\n"
              "for (var mode in cases) { if (mode === 'on') document.documentElement.dataset.whole = 'true';"
              " else delete document.documentElement.dataset.whole; out[mode] = {};"
              " for (var a in cases[mode]) out[mode][a] = [window.ubUnit(a), window.ubUnit(window.ubUnit(a))]; }\n"
              "console.log(JSON.stringify(out));")
        got = json.loads(subprocess.run(["node", "-"], input=js, capture_output=True, text=True, check=True).stdout)
        for mode, cases in CASES.items():
            for a, want in cases.items():
                self.assertEqual(got[mode][a][0], want, f"{mode}: {a}")
                self.assertEqual(got[mode][a][1], want, f"{mode}: {a}, again")   # idempotent


if __name__ == "__main__":
    unittest.main()
