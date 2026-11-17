"""The Foreword in Part I (settings.py `foreword`; Tigran, 2026-11-04).

On by default, it lists the Foreword as Part I's first paper wherever the parts
are listed, and off it stands on its own before them, as the press prints it.
Each list carries it both ways, .fwin and .fwout, and the CSS shows one, so no
page changes with the switch and the offline copy holds one page.  The left
rail's is in test_rail.py, the quiz's in test_quiz.py; the recordings' tree is
drawn by offline.js.  Rendered through the app as ASGI, as test_appendix_pages
does.  Skipped when var/ub.db has not been built.
"""

import re
import unittest

from test_appendix_pages import DB, ROOT, get
from ubsite import settings


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class ForewordInPartOne(unittest.TestCase):
    def test_the_setting_and_its_rule(self):
        it = next(s for s in settings.READING if s[0] == "foreword")
        self.assertEqual((it[1], it[2], it[3]), ("switch", "Foreword in Part I", True))
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text()
        self.assertIn(':root:not([data-foreword="off"]) .fwout, :root[data-foreword="off"] .fwin { display: none; }', css)

    def test_the_home_page(self):
        # Each part's card goes to its title page (Tigran, 2026-11-17), Part I's
        # naming the Foreword in its range; with the switch off, the Foreword's
        # own row before the parts and Part I's range from Paper 1.
        body = get("/")[2]
        toc = re.search(r'<ol class="front-toc">.*?</ol>', body, re.S).group(0)
        rows = re.findall(r'<li(?: class="([^"]*)")?>\s*<a href="/([\w/]+)">(.*?)</a>', toc, re.S)
        self.assertEqual([(c, n) for c, n, _ in rows],
                         [("foreword fwout", "0"), ("", "part/1"), ("", "part/2"), ("", "part/3"), ("", "part/4")])
        self.assertIn("Definitions and terminology", rows[0][2])
        ranges = [re.findall(r'<span class="(range[^"]*)">(.*?)</span>', r[2], re.S) for r in rows[1:]]
        self.assertEqual([[c for c, _ in r] for r in ranges],
                         [["range fwin", "range fwout"], ["range"], ["range"], ["range"]])
        self.assertIn("Foreword and Papers 1&ndash;31", ranges[0][0][1])
        self.assertIn("Papers 1&ndash;31", ranges[0][1][1])
        self.assertNotIn("Foreword", ranges[0][1][1])
        self.assertIn("Papers 32&ndash;56", ranges[1][0][1])
        # A card's name is the interface's, in both languages (Tigran, 2026-11-17).
        raw = re.search(r'<ol class="front-toc">.*?</ol>', get("/", raw=True)[2], re.S).group(0)
        names = re.findall(r'<span class="lbl">(.*?)</span>', raw, re.S)
        self.assertEqual(names, [f'<x-en>{e}</x-en><x-ru lang="ru">{r}</x-ru>' for e, r in [
            ("Foreword", "Предисловие"),
            ("The Central and Superuniverses", "Центральная вселенная и сверхвселенные"),
            ("The Local Universe", "Локальная вселенная"),
            ("The History of Urantia", "История Урантии"),
            ("The Life and Teachings of Jesus", "Жизнь и учения Иисуса")]])

    def test_the_contents(self):
        body = get("/read")[2]
        self.assertEqual(body.count("<b>0</b> Foreword</a>"), 2)
        self.assertRegex(body, r'<ol class="toc fwout">\s*<li><a href="/0"><b>0</b> Foreword</a><i>Divine Counselor</i></li>\s*</ol>')
        self.assertRegex(body, r'<h2>The Central and Superuniverses</h2>\s*<ol class="toc">\s*'
                               r'<li class="fwin"><a href="/0"><b>0</b> Foreword</a><i>Divine Counselor</i></li>\s*'
                               r'<li><a href="/1"><b>1</b> ')
        self.assertEqual(body.count("fwin"), 1)

    def test_the_parts_page(self):
        # Part I's ⏭ goes to the Foreword with the switch on and to Paper 1
        # with it off (2026-11-07); the other parts' to their first paper.
        body = get("/part/1")[2]
        self.assertRegex(body, r'<a class="next fwin" href="/0:0" rel="next" aria-label="Next section: 0:0"[^>]*>.*?</a>'
                               r'<a class="next fwout" href="/1:0" rel="next" aria-label="Next section: 1:0"', )
        nav = re.search(r'<nav class="transport"[^>]*>(.*?)</nav>', get("/part/2")[2], re.S).group(1)
        self.assertIn('<a class="next" href="/32:0"', nav)
        self.assertNotIn("fw", nav)


if __name__ == "__main__":
    unittest.main()
