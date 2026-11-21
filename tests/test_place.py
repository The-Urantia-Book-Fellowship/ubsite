"""The reading place, the bookmarks and the bar at the foot (Tigran,
2026-11-17; DECISIONS.md, The home page): Continue reading, to the paragraph
this browser last had on the screen on a page of the text, kept in
localStorage `ub_place`, and Begin reading, to the Foreword, where it has
none; and the bookmarks set by hand, `ub_marks`, their list opened from the
bar's right end, and on a page of the text the bar itself at a tap on a
paragraph, with Bookmark this paragraph.  The bar is the shell's, the same
in every reader's page and in the offline copy, so the place and the number
of bookmarks are put into it by script, a line of the page after it and ub.js
when they change; the stylesheet shows it by the <main> before it, as it
shows the footer, and draws a bookmarked paragraph's ribbon on a class the
script gives it.  These hold the static facts; Chrome is driven through it
by tools/place_e2e.py, which is not a gate.  Rendered through the app as ASGI, as test_appendix_pages
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
        self.assertIn(r"REF = /^\d+:\d+\.\d+$/", script)
        self.assertIn("if (p && REF.test(p.ref)) {", script)
        self.assertIn("setAttribute('href', '/' + p.ref)", script)
        self.assertIn(".textContent = p.title || ''", script)
        self.assertNotIn("innerHTML", script)
        # It reads the two keys, and writes neither: the number of bookmarks
        # that are a paragraph's reference, on the list's button, which is
        # shown where there is one.
        self.assertEqual(re.findall(r"localStorage\.(\w+)\('([^']+)'", script),
                         [("getItem", "ub_place"), ("getItem", "ub_marks")])
        self.assertIn("n = m.filter(function (x) { return x && REF.test(x.ref); }).length;", script)
        self.assertIn("b.querySelector('.flist').hidden = !n;", script)

    def test_where_it_is_shown(self):
        # Not while a page of the text is read, nor on a reading path, nor on
        # the chart; a part's title page has no text, and has it.  The footer
        # gives it room, and the player stands over it.
        # On a page of the text and a reading path it is up only with the
        # running head (.fup, ub.js barUp), with Bookmark this paragraph in
        # Continue reading's place.
        self.assertIn("main.cosmo ~ .fbar, main.path ~ .fbar:not(.fup), main.reader:not(:has(> .partpage)) ~ .fbar:not(.fup) "
                      "{ display: none; }", CSS)
        self.assertIn(".fbar.fup .fgo { display: none; }", CSS)
        self.assertRegex(CSS, r"\.fbar \{ position: fixed; z-index: 5; left: 0; right: 0; bottom: 0;")
        self.assertRegex(CSS, r"main:not\(\.path, \.cosmo, \.reader\) ~ footer, main\.reader:has\(> \.partpage\) ~ footer \{\s*"
                              r"padding-bottom: calc\(3\.1rem \+ 1\.2rem \+ env\(safe-area-inset-bottom\)\); \}")
        self.assertRegex(CSS, r"main:not\(\.path, \.cosmo, \.reader\) ~ \.player, main\.reader:has\(> \.partpage\) ~ \.player, "
                              r"\.fbar\.fup ~ \.player \{\s*bottom: calc\(3\.1rem \+ \.6rem \+ env\(safe-area-inset-bottom\)\); \}")
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
        # The paper named as the paragraph read is, in its own text (titleOf).
        self.assertIn("localStorage.setItem(RP, JSON.stringify({ ref: p.id, title: titleOf(p), at: Date.now(),", block)
        self.assertIn("main.reader article:not(.partpage) p.t[id]", block)
        # Heard, the place is the paragraph listen.js marks, a translation's
        # line by the paragraph it translates, and it stays that paragraph
        # with the player shut, while any of it is on the screen (Tigran,
        # 2026-11-17); the marks are read from the page, never asked of
        # listen.js (trap 51).
        self.assertIn("document.querySelector('main.reader :is(p.t.now[id], p.rt.now)');", block)
        self.assertIn("if (now) return (rpLast = now);", block)
        self.assertIn("if (r && r.height && r.bottom > 0 && r.top < innerHeight) return rpLast;", block)
        self.assertIn(".observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });", block)
        self.assertNotIn("ub_place", JS.replace(block, "").replace("`ub_place`", ""))
        from ubsite import settings
        self.assertNotIn("place", settings.defaults())
        self.assertNotIn("ub_place", (ROOT / "ubsite" / "static" / "listen.js").read_text())

    def test_its_words_are_in_help(self):
        body = get("/help")[2]
        moving = re.search(r'<section id="moving">.*?</section>', body, re.S).group(0)
        self.assertIn("Continue reading", moving)
        self.assertIn("Bookmark this paragraph", moving)


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class Bookmarks(unittest.TestCase):
    def test_the_bars_controls(self):
        # In the shell with the bar, hidden until a script shows them: the
        # button that sets one, both its words in both languages, and the
        # list's button and the list, whose rows ub.js makes.
        bar = RE_BAR.search(get("/", raw=True)[2]).group(0)
        self.assertRegex(bar, r'<button type="button" class="fmark" aria-pressed="false" hidden><svg class="frib"[^>]*>'
                              r'<path d="M4\.5 2\.5h7v11\.2l-3\.5-2\.6-3\.5 2\.6z"/></svg>'
                              r'<span class="fmset"><x-en>Bookmark this paragraph</x-en><x-ru lang="ru">Поставить закладку</x-ru></span>'
                              r'<span class="fmis"><x-en>Bookmarked</x-en><x-ru lang="ru">В закладках</x-ru></span></button>')
        self.assertRegex(bar, r'<button type="button" class="flist" aria-expanded="false" aria-controls="fsheet" aria-label="Bookmarks"'
                              r'[^>]* hidden><svg class="frib"[^>]*>.*?</svg><span class="fcount"></span></button>')
        self.assertRegex(bar, r'(?s)<div class="fsheet" id="fsheet" hidden>\s*<p class="fsh"><x-en>Bookmarks</x-en>'
                              r'<x-ru lang="ru">Закладки</x-ru></p>\s*<ul></ul>\s*</div>')
        self.assertIn('.fmark[aria-pressed="false"] .fmis, .fmark[aria-pressed="true"] .fmset { display: none; }', CSS)
        # No class of the text's own among the bar's (CLAUDE.md trap 58): `fn`
        # is a note's mark.
        self.assertNotRegex(bar, r'class="[^"]*\bfn\b')

    def test_the_ribbon_is_the_stylesheets(self):
        # A class on the paragraph, given by ub.js, and the drawing here, on a
        # pseudo-element no other rule uses: no page's markup knows of it, so
        # no stored page moves (trap 29).  The shape is the drawing's.
        self.assertRegex(CSS, r'p\.t\.bmk::after \{ content: ""; position: absolute; left: -\.92rem;')
        self.assertIn("clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 77%, 0 100%); }", CSS)
        self.assertEqual(re.findall(r"p\.t[^,{]*::after", CSS.replace("p.t.bmk::after", "").replace("p.t.opening.bmk::after", "")), [])
        self.assertIn("p.t { position: relative; }", CSS)
        start = CSS.index("@media print {")
        self.assertIn("p.t.bmk::after { display: none; }", CSS[start:CSS.index("\n}\n", start)])
        for path in (ROOT / "ubsite" / "templates").glob("*.html"):
            self.assertNotIn("bmk", path.read_text(), path.name)
        self.assertNotIn("bmk", get("/101:4", raw=True)[2])

    def test_they_are_the_browsers_own(self):
        # A key of its own and no setting; ub.js writes it here alone, puts
        # what it keeps into the page as text, and follows only a reference.
        block = JS[JS.index("  // Bookmarks (Tigran, 2026-11-17;"):JS.index("    bmPaint();\n  }\n") + 20]
        self.assertIn("var BM = 'ub_marks', RE_REF = /^(\\d+):(\\d+)\\.(\\d+)$/,", block)
        self.assertEqual(sorted(set(re.findall(r"localStorage\.(\w+)\(", block))), ["getItem", "removeItem", "setItem"])
        self.assertEqual(set(re.findall(r"localStorage\.\w+\((\w+)", block)), {"BM"})
        self.assertNotIn("ub_marks", JS.replace(block, "").replace("`ub_marks`", ""))
        self.assertIn("return m.filter(function (x) { return x && typeof x.ref === 'string' && RE_REF.test(x.ref); }).sort(bmOrder);", block)
        self.assertIn("m.push({ ref: ref, title: bmTitle(p), q: bmWords(p), at: Date.now(), v: fbar.dataset.tv || '' });", block)
        # What is kept reaches the page by textContent; innerHTML is the
        # interface's own words and the drawing of the cross.
        self.assertEqual(sorted(re.findall(r"innerHTML = ([^;]+);", block)), ["BM_X", "T('Removed')", "T('Undo')"])
        self.assertIn("a.href = '/' + x.ref;", block)
        from ubsite import settings
        self.assertNotIn("marks", settings.defaults())
        self.assertNotIn("ub_marks", (ROOT / "ubsite" / "static" / "listen.js").read_text())

    def test_the_bar_comes_and_goes_with_the_running_head(self):
        # One rule for both: every way the head is shown and hidden carries
        # the bar, and Escape shuts the list first.
        show = JS[JS.index("  function showHead(p) {"):JS.index("  function hideHead() {")]
        hide = JS[JS.index("  function hideHead() {"):JS.index("  // The tour's (help.js): the head shown")]
        # Never for a verse of the Bible, which is no bookmark (2026-11-21).
        self.assertIn("    if (!p.classList.contains('kv')) barUp();\n", show)
        self.assertIn("    barDown();\n", hide)
        self.assertIn("if (card) shut(true); else if (bmSheet && !bmSheet.hidden) bmShut(true); else hideHead();", JS)
        self.assertIn("document.addEventListener('ub:swap', bmPaint);", JS)

    def test_its_links_are_no_references(self):
        # Paragraph previews show the paragraph a reference points to; the
        # bar's links are ways to a place, and never get a card: one made the
        # page taller, and on a phone took the tap (Tigran, 2026-11-17).
        self.assertIn("if (!a || a.closest('.pop.pv, .fbar, .fpass')) return null;", JS)
        self.assertEqual(len(re.findall(r"\bpvLink\(", JS)), 4)       # its definition, and the three that ask it

    def test_a_tap_meant_for_the_text_sets_nothing(self):
        # The bar rises under the finger where the paragraph tapped was low on
        # the screen: a tap on its ground, or on anything of it in the moment
        # after it rose, takes the bars away and reaches no button.
        self.assertIn("var barAt = 0, BAR_SOON = 400;", JS)
        guard = JS[JS.index("    fbar.addEventListener('click', function (ev) {"):JS.index("    bmMark.addEventListener('click', function () {")]
        self.assertIn("if (Date.now() - barAt >= BAR_SOON && ev.target.closest('a, button, .fsheet')) return;", guard)
        self.assertIn("ev.stopPropagation();", guard)
        self.assertIn("hideHead();", guard)
        self.assertIn("}, true);", guard)
        # Copy link beside it, the two in the middle together (2026-11-19).
        self.assertRegex(CSS, r"\.fmark \{ flex: 0 1 auto; min-width: 0; margin: 0 0 0 auto;")
        self.assertRegex(CSS, r"\.fcopy \{ flex: none; margin: 0 auto 0 0;")


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class ParagraphLink(unittest.TestCase):
    """A paragraph's link copied (Tigran, 2026-11-19: "we definitely need a
    way to save a stable reference to the current paragraph, which can be sent
    outside"): a click or a tap on its reference, where references are shown,
    and Copy link in the bar, with them shown or not, copying on a phone too.
    Chrome copies through both in tools/place_e2e.py."""

    def test_the_bars_button(self):
        # In the shell with the bar, hidden until a script shows it, after the
        # bookmark's button and before the list's; on a phone its drawing alone.
        bar = RE_BAR.search(get("/", raw=True)[2]).group(0)
        self.assertRegex(bar, r'<button type="button" class="fcopy" aria-label="Copy link to this paragraph"'
                              r' data-ru-aria-label="Скопировать ссылку на этот абзац" hidden><svg class="flink"[^>]*>.*?</svg>'
                              r'<span class="fcl"><x-en>Copy link</x-en><x-ru lang="ru">Копировать ссылку</x-ru></span></button>')
        self.assertLess(bar.index('class="fmark"'), bar.index('class="fcopy"'))
        self.assertLess(bar.index('class="fcopy"'), bar.index('class="flist"'))
        self.assertRegex(CSS, r"@media \(max-width: 40rem\) \{\n  \.fcopy \{ min-width: 2\.75rem;[^}]*\}\n  \.fcopy \.fcl \{ display: none; \}")

    def test_it_comes_and_goes_with_the_bar(self):
        up = JS[JS.index("  function barUp() {"):JS.index("  function barDown() {")]
        down = JS[JS.index("  function barDown() {"):JS.index("  if (bmMark && bmList && bmSheet) {")]
        self.assertIn("if (fcopy) fcopy.hidden = false;", up)
        self.assertIn("if (fcopy) fcopy.hidden = true;", down)
        self.assertIn("var ref = bmRef(headP);\n    if (ref) copyLink(ref, fcopy);", JS)

    def test_the_reference_copies_and_goes_nowhere(self):
        # Before the running head hears the click, and never a link in the
        # markup: no stored page moves (CLAUDE.md trap 29).
        self.assertIn("var NUM = 'main p.t > .stk > span.num'", JS)
        click = JS.index("    if (num && bmRef(num.closest('p.t'))) {")
        self.assertLess(click, JS.index("    if (!card) { tapHead(ev); return; }"))
        self.assertIn("if (ev.button || ev.detail > 1 || !getSelection().isCollapsed) return;", JS[click:click + 200])
        body = get("/101:4", raw=True)[2]
        self.assertIn('id="101:4.1"><span class="stk"><span class="num">101:4.1</span>', body)
        self.assertNotIn('title="Copy link', body)
        self.assertIn('p.t[id] > .stk > span.num { cursor: pointer; }', CSS)

    def test_the_address_is_the_paragraphs_own(self):
        # /101:4.2, whatever the reader's unit (CLAUDE.md trap 44), on the
        # site the reader is on.
        self.assertIn("var url = location.origin + '/' + ref;", JS)

    def test_the_copy_command_takes_the_address_alone(self):
        # Where the clipboard's own call is not to be had: the copy event
        # carries the address, and nothing of the soft hyphens' work.
        at = JS.index("  document.addEventListener('copy', function (ev) {")
        self.assertIn("if (copyNext !== null) {\n      ev.clipboardData.setData('text/plain', copyNext);\n"
                      "      ev.preventDefault();", JS[at:at + 300])
        self.assertIn("if (navigator.clipboard && window.isSecureContext)", JS)

    def test_its_words_are_in_help(self):
        body = get("/help")[2]
        self.assertIn("Copy link", re.search(r'<section id="moving">.*?</section>', body, re.S).group(0))
        self.assertIn("copies the paragraph’s link", body)


if __name__ == "__main__":
    unittest.main()
