"""The reading place and the bar at the foot (Tigran, 2026-11-17; DECISIONS.md,
The home page): Continue reading, to the paragraph this browser last had on
the screen on a page of the text, kept in localStorage `ub_place`, and Begin
reading, to the Foreword, where it has none.  The bar is the shell's, the same
in every reader's page and in the offline copy, so the place is put into it by
script, a line of the page after it and ub.js when the place changes; the
stylesheet shows it by the <main> before it, as it shows the footer.  These
hold the static facts; Chrome is driven through it by tools/place_e2e.py,
which is not a gate.  Rendered through the app as ASGI, as test_appendix_pages
does.  Skipped when var/ub.db has not been built.
"""

import re
import unittest

from test_appendix_pages import DB, ROOT, get

CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text()
JS = (ROOT / "ubsite" / "static" / "ub.js").read_text()
BASE = (ROOT / "ubsite" / "templates" / "base.html").read_text()
RE_BAR = re.compile(r'<nav class="fbar"[^>]*>.*?</nav>\n<script>.*?</script>', re.S)


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class TheBar(unittest.TestCase):
    def test_every_page_carries_it_the_same(self):
        # One bar, after the footer and before the scripts, so in the offline
        # copy's shell (offline/pages.py cut): no page's own piece has it.
        bars = set()
        for url in ("/", "/101:4", "/101", "/part/1", "/index", "/i/faith", "/i/faith/read", "/cosmology", "/help",
                    "/search?q=faith", "/no-such-page"):
            body = get(url, raw=True)[2]
            found = RE_BAR.findall(body)
            self.assertEqual(len(found), 1, url)
            self.assertLess(body.rindex("\n<footer>"), body.index(found[0]), url)
            self.assertLess(body.index(found[0]), body.index('<script src="/static/ub.js'), url)
            bars.add(found[0])
        self.assertEqual(len(bars), 1)

    def test_with_no_place_it_begins_at_the_foreword(self):
        bar = RE_BAR.search(get("/", raw=True)[2]).group(0)
        self.assertRegex(bar, r'<a class="fgo" href="/0">')
        for words in ('<span class="fl fbegin"><x-en>Begin reading</x-en><x-ru lang="ru">Начать чтение</x-ru></span>',
                      '<span class="fl fcont"><x-en>Continue reading</x-en><x-ru lang="ru">Продолжить чтение</x-ru></span>',
                      '<span class="fref"></span><span class="fttl"><x-en>Foreword</x-en><x-ru lang="ru">Предисловие</x-ru></span>'):
            self.assertIn(words, bar)
        # The text's version, which the place is kept with.
        self.assertRegex(bar, r'<nav class="fbar"[^>]* data-tv="\d+">')
        self.assertIn(".fbar:not(.fhas) .fcont, .fbar.fhas .fbegin { display: none; }", CSS)

    def test_the_line_after_it_follows_only_a_reference(self):
        # What a browser keeps is never trusted as an address: a paragraph's
        # reference or nothing, and the title put in as text.
        script = re.search(r"\(window\.ubBar = function \(\) \{.*?\}\)\(\);", BASE, re.S).group(0)
        self.assertIn(r"/^\d+:\d+\.\d+$/.test(p.ref)", script)
        self.assertIn("setAttribute('href', '/' + p.ref)", script)
        self.assertIn(".textContent = p.title || ''", script)
        self.assertNotIn("innerHTML", script)
        self.assertEqual(re.findall(r"localStorage\.\w+\('([^']+)'", script), ["ub_place"])

    def test_where_it_is_shown(self):
        # Not while a page of the text is read, nor on a reading path, nor on
        # the chart; a part's title page has no text, and has it.  The footer
        # gives it room, and the player stands over it.
        self.assertIn("main:is(.path, .cosmo) ~ .fbar, main.reader:not(:has(> .partpage)) ~ .fbar { display: none; }", CSS)
        self.assertRegex(CSS, r"\.fbar \{ position: fixed; z-index: 5; left: 0; right: 0; bottom: 0;")
        self.assertRegex(CSS, r"main:not\(\.path, \.cosmo, \.reader\) ~ footer, main\.reader:has\(> \.partpage\) ~ footer \{\s*"
                              r"padding-bottom: calc\(3\.1rem \+ 1\.2rem \+ env\(safe-area-inset-bottom\)\); \}")
        self.assertRegex(CSS, r"main:not\(\.path, \.cosmo, \.reader\) ~ \.player, main\.reader:has\(> \.partpage\) ~ \.player \{\s*"
                              r"bottom: calc\(3\.1rem \+ \.6rem \+ env\(safe-area-inset-bottom\)\); \}")
        start = CSS.index("@media print {")
        self.assertRegex(CSS[start:CSS.index("\n}\n", start)], r"[^\n]*\.fbar[^\n]*display: none")
        # The pages the rules name are the pages there are.
        self.assertIn('<main class="reader">', get("/101:4")[2])
        self.assertIn('<main class="reader">', get("/101")[2])
        self.assertRegex(get("/part/1")[2], r'(?s)<main class="reader">.*<article class="partpage">')
        self.assertIn('<main class="path"', get("/i/faith/read")[2])
        self.assertIn('<main class="cosmo"', get("/cosmology")[2])

    def test_the_place_is_the_browsers_own(self):
        # A key of its own and no setting, so Restore the defaults leaves it
        # and nothing of it reaches the server; ub.js writes that key alone
        # here, on a page of the text, and never asks listen.js anything.
        block = JS[JS.index("  // The reading place (Tigran, 2026-11-17;"):JS.index("  rpBegin();\n") + 14]
        self.assertIn("var RP = 'ub_place', RP_DWELL = 5000,", block)
        self.assertEqual(block.count("localStorage."), 1)
        self.assertIn("localStorage.setItem(RP, JSON.stringify({ ref: p.id, title: headOf(p).title, at: Date.now(),", block)
        self.assertIn("main.reader article:not(.partpage) p.t[id]", block)
        self.assertNotIn("ub_place", JS.replace(block, "").replace("`ub_place`", ""))
        from ubsite import settings
        self.assertNotIn("place", settings.defaults())
        self.assertNotIn("ub_place", (ROOT / "ubsite" / "static" / "listen.js").read_text())

    def test_its_words_are_in_help(self):
        body = get("/help")[2]
        self.assertIn("Continue reading", re.search(r'<section id="moving">.*?</section>', body, re.S).group(0))


if __name__ == "__main__":
    unittest.main()
