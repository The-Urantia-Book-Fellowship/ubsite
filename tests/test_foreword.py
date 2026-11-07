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
        # Part I opens on the Foreword and names it in its range; with the
        # switch off, the Foreword's own row and Part I from Paper 1.
        body = get("/")[2]
        toc = re.search(r'<ol class="front-toc">.*?</ol>', body, re.S).group(0)
        rows = re.findall(r'<li(?: class="([^"]*)")?>\s*<a href="/(\d+)">.*?<span class="range">(.*?)</span>', toc, re.S)
        self.assertEqual([(c, n) for c, n, _ in rows],
                         [("foreword fwout", "0"), ("fwin", "0"), ("fwout", "1"), ("", "32"), ("", "57"), ("", "120")])
        self.assertIn("Definitions and terminology", rows[0][2])
        self.assertIn("Foreword and Papers 1&ndash;31", rows[1][2])
        self.assertIn("Papers 1&ndash;31", rows[2][2])
        self.assertNotIn("Foreword", rows[2][2])

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
