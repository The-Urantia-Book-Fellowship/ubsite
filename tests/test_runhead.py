"""The running head on demand (ub.js tapHead, 2026-10-31): a tap on the text
shows the book's running head over the top of the window, the paragraph's
reference, the paper's number, title and author, and the gear, and a tap or
two lines of reading hides it; since 2026-11-01 the reference is a button to
the Contents (toContents) and the site's mark beside the gear a link home.
It is built by ub.js from what the page carries and kept on <body>, so that
no template names it and no stored page of the offline copy moves with it
(CLAUDE.md trap 29).  These hold the static facts: the stylesheet hides it in
print and tints the paragraph it names as a search hit; the script names its
interface words as literals, in the form test_l10n and app.py read, and
appends the head to the body; and no template knows of it.  Chrome is driven through the gesture itself by
tools/runhead_e2e.py, which is not a gate.
"""

import re
import unittest

from test_appendix_pages import ROOT

CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text()
JS = (ROOT / "ubsite" / "static" / "ub.js").read_text()


class RunningHead(unittest.TestCase):
    def test_hidden_in_print(self):
        start = CSS.index("@media print {")
        block = CSS[start:CSS.index("\n}\n", start)]
        self.assertRegex(block, r"[^\n]*\.runhead[^\n]*display: none")

    def test_named_paragraph_is_tinted_as_a_hit(self):
        self.assertIn("p.t.hit, p.t.named, .rc p.rt.hit, .rc p.rt.named, .tf p.rt.named {", CSS)

    def test_a_translation_tapped_in_the_fold_is_named_too(self):
        # The fold under a paragraph is how a phone shows a translation, and
        # a tap on its text did nothing there (Tigran, 2026-11-17): its
        # paragraphs are text, its tabs, names and the room about them not.
        self.assertIn("function inFold(t) { return !!t.closest('.tf') && !t.closest('.tf p.rt'); }", JS)
        head = JS[JS.index("function tapHead(ev) {"):JS.index("// The second press of a mouse's double-click")]
        self.assertIn("|| inFold(t) ||", head)
        self.assertNotIn(".tf", head)
        # A fold drawn again or shut takes the head of a paragraph in it.
        self.assertIn("if (headP && panel.contains(headP)) hideHead();", JS)
        self.assertIn("if (headP && tf.contains(headP)) hideHead();", JS)

    def test_a_translations_head_is_its_own(self):
        # The paper's number, title and author as the translation has them,
        # from the fragment its paragraph was drawn from, never the English
        # (Tigran, 2026-11-17: "the page header is from English even on the
        # Russian text"); the English only where the fragment cannot be had.
        self.assertIn("if (!p.id && p.dataset.k && p.dataset.ref) headTr(p); else headSay(headOf(p));", JS)
        tr = JS[JS.index("function headTr(p) {"):JS.index("function showHead(p) {")]
        self.assertIn("trFetch(sec, p.dataset.ref.split('.')[0]).then(function (got) {", tr)
        self.assertIn("var g = got.h[k];", tr)
        self.assertIn("if (headP !== p) return;", tr)
        self.assertIn("num: g.paper ? '<b>' + g.paper + '</b>' : ''", tr)
        self.assertIn("function () { if (headP === p) headSay(en); }", tr)
        # The dash before the title is drawn where an element comes before it.
        self.assertIn('.runhead .tt:not(:first-child)::before { content: " – "; }', CSS)
        self.assertIn(".runhead .pn b { font-weight: inherit; }", CSS)

    def test_the_gear_comes_first(self):
        # As it is the first of the header's controls (Tigran, 2026-11-17).
        self.assertLess(JS.index("ctl.appendChild(btn);"), JS.index("ctl.appendChild(home);"))
        page = (ROOT / "ubsite" / "templates" / "help.html").read_text()
        eg = page[page.index('<div class="runhead"'):]
        self.assertLess(eg.index('<span class="set">'), eg.index('<a class="home"'))
        base = (ROOT / "ubsite" / "templates" / "base.html").read_text()
        ctl = base[base.index('<div class="ctl">'):]
        self.assertLess(ctl.index('class="gear"'), ctl.index('class="langs"'))

    def test_a_translation_tapped_in_columns_is_named_alone(self):
        # Never the English beside it (Tigran, 2026-11-08): its own reference
        # in the head, and Back from the Contents kept by the row's English.
        self.assertIn("return t.closest('p.t[id], .rc p.rt, .tf p.rt') ||", JS)
        self.assertIn("head.querySelector('.ref').textContent = p.id || p.dataset.ref;", JS)
        self.assertIn("toContents(p && (p.id ? p : document.getElementById(p.dataset.ref)), p && !p.id ? p.dataset.k : '');", JS)

    def test_a_tap_on_a_title_names_its_own_sections_first_paragraph(self):
        # Never the first on the screen, which above a title is a paragraph
        # of the section before (Tigran, 2026-11-15); under a translation's
        # title in columns, that translation's.  tools/compare_e2e.py clicks.
        js = (ROOT / "ubsite/static/ub.js").read_text()
        self.assertIn("paraCol((row = t.closest('.grid > .row')) && row.querySelector('p.t[id]'), x) || paraUnder(t, y, x);", js)
        self.assertIn("if (r.height && r.bottom > y) return paraCol(ps[i], x);", js)
        self.assertIn("""own = sec && sec.querySelector('.rc[data-k="' + ch.dataset.k + '"] p.rt')""", js)
        self.assertIn("      p = paraOf(t, ev.clientY, ev.clientX);\n", js)
        self.assertIn("showHead(paraOf(t, ev.clientY, ev.clientX) || firstOnScreen());", js)
        self.assertNotIn("paraOf(t)", js)

    def test_a_tap_in_a_columns_empty_room_names_that_columns_paragraph(self):
        # Between two sections, above a translation's title, beside a cell:
        # the paragraph named is the one of the column the tap fell in, never
        # the English whichever it was (Tigran, 2026-11-18).  By the row's own
        # cells, half the room between two columns to each; the English where
        # the column has not the paragraph, past the last column, in the
        # margin, and on a page not in columns.  The room is measured: a row
        # is a subgrid, whose own column-gap computes to normal.
        # tools/runhead_e2e.py clicks.
        col = JS[JS.index("function paraCol(p, x) {"):JS.index("// The first paragraph on the screen")]
        self.assertIn("var row = p && p.closest('article.cmp .grid > .row'), text, cells, edge, at = null, i, r;", col)
        self.assertIn("if (!row || !(x >= 0)) return p;", col)
        self.assertIn("if (x >= (edge + r.left) / 2) at = cells[i];", col)
        self.assertIn("if (!at || x >= edge) return p;", col)
        self.assertNotIn("columnGap", col)
        self.assertIn("""at.querySelector('p.rt[data-ref="' + p.id + '"]') || at.querySelector('p.rt') || p;""", col)

    def test_the_contents_mark_the_section_of_the_paragraph_named(self):
        # On the whole paper's page the mark was the section at the window's
        # top alone, and a wide window has the end of one there and the next
        # under it: 0:6.2 named, the Contents marked section 5 (Tigran,
        # 2026-11-18).  A paragraph named holds the mark while it is on the
        # screen, and the Contents opened at an entry of the history take it
        # from the entry's paragraph.
        show = JS[JS.index("function showHead(p) {"):JS.index("function hideHead() {")]
        self.assertIn("railMarkOf(p);", show)
        to = JS[JS.index("function toContents(p, k) {"):JS.index("// The place the address names")]
        self.assertIn("railMarkOf(p || (contentsAt && document.getElementById(contentsAt.p)));", to)
        of = JS[JS.index("function railMarkOf(p) {"):JS.index("  railMark();\n")]
        self.assertIn("var s = p && p.closest && p.closest('article.whole > section[id]');", of)
        self.assertIn("railMarkP = p;\n    railMarkAt = s;\n    railPut(s);", of)
        mark = JS[JS.index("function railMark() {"):JS.index("function railPut(s) {")]
        self.assertIn("if (r && r.height && r.bottom > 0 && r.top < innerHeight) return;\n      railMarkP = null;", mark)
        self.assertLess(mark.index("railMarkP = null;"), mark.index("if (s === railMarkAt) return;"))
        self.assertIn("document.addEventListener('ub:swap', function () { railMarkAt = railMarkP = null; railMark(); });", JS)

    def test_a_contents_link_is_told_by_the_address_the_rail_gave_it(self):
        # The Whole paper handler rewrites a link as it is clicked and leaves
        # it so (CLAUDE.md, trap 44): the Contents drawn in a translation knew
        # /0:6 and not /0#0:6, and a section once followed stayed in English
        # among the translation's titles (Tigran, 2026-11-18, his phone).
        self.assertIn("if (!hrefWas.has(a)) hrefWas.set(a, a.getAttribute('href'));", JS)
        self.assertLess(JS.index("hrefWas.set(a, a.getAttribute('href'));"), JS.index("a.href = to;"))
        self.assertIn("var m = RE_RAILA.exec(hrefWas.get(a) || a.getAttribute('href'));", JS)

    def test_a_double_click_is_never_a_tap(self):
        # A mouse's click shows the head after DBL, which the second press
        # cancels; Ctrl+X takes the head away, or it covers the box at the
        # page's top (Tigran, 2026-11-08).
        self.assertIn("var headSoon = 0, headBy = 0, DBL = 350;", JS)
        self.assertIn("if (!touch && (!head || head.hidden)) {", JS)
        self.assertIn("document.addEventListener('mousedown', function (ev) {\n    if (ev.detail < 2) return;\n    clearTimeout(headSoon);", JS)
        start = JS.index("function hideHead() {")
        self.assertIn("clearTimeout(headSoon);", JS[start:JS.index("}", start)])
        start = JS.index("// Ctrl+X searches")
        self.assertIn("hideHead();\n      back = { value: box.value", JS[start:])

    def test_dash_is_generated_content(self):
        # So that build/fonts.py, which reads content: strings and never a
        # script, keeps the glyph in the face.
        self.assertIn('.runhead .tt:not(:first-child)::before { content: " – "; }', CSS)
        self.assertNotIn("' – '", JS)

    def test_script_names_its_words_as_literals(self):
        self.assertIn("T.attr(head, 'aria-label', 'Running head')", JS)
        self.assertIn("T.attr(btn, 'aria-label', 'Settings')", JS)
        self.assertIn("T.attr(ref, 'title', 'Show in the contents')", JS)
        self.assertIn("T.attr(home, 'aria-label', 'Home')", JS)

    def test_reference_is_a_button_to_the_contents(self):
        # With the Contents' chevron after it, drawn and not a glyph.
        self.assertIn("ref = document.createElement('button')", JS)
        self.assertIn("ref.addEventListener('click', function () {\n      var p = headP;\n      hideHead();", JS)
        self.assertIn('.runhead .ref::after { content: "";', CSS)

    def test_home_is_the_mark_and_a_link(self):
        self.assertIn("home.href = '/'", JS)
        self.assertIn("logo = document.querySelector('.brand .logo')", JS)
        # In its own colours, the header's .logo rules (Tigran, 2026-11-01).
        self.assertNotIn(".runhead .home .logo .book", CSS)
        self.assertNotIn("currentColor; }\n.runhead .home", CSS)

    def test_the_jump_is_a_history_step(self):
        # On a phone; Back puts the paragraph back, arrive() leaves the entry's place alone.
        self.assertIn("state = { ub: 'contents', p: p.id, top: p.getBoundingClientRect().top, shown: !shut, href: location.href, k: k || '' };", JS)
        self.assertIn("if (location.href !== was.href) return;", JS)
        self.assertIn("if (contentsAt) history.replaceState(state, ''); else history.pushState(state, '');", JS)
        self.assertIn("if (contentsAt && history.state && history.state.ub === 'contents') return;", JS)
        self.assertIn("if (history.state && history.state.ub === 'contents') { contentsAt = history.state; toContents(null, history.state.k); }", JS)

    def test_the_contents_own_section_is_a_step_too(self):
        # A link in the Contents to the address their entry already has, the
        # section being read: the browser would only replace the entry, with
        # a popstate at the same address, which is Back's sign (Tigran,
        # 2026-11-17).  So it is a step of its own, as another section's is,
        # named so in its state, for Forward to it from the Contents.
        self.assertIn("var a = contentsAt && ev.target.closest && ev.target.closest('.rail a[href]'), to;", JS)
        self.assertIn("if (window.ubUnit) to = window.ubUnit(to);", JS)
        self.assertIn("if (to !== location.pathname + location.hash || a.search !== location.search) return;", JS)
        self.assertIn("history.pushState({ ub: 'place' }, '', location.href);", JS)
        self.assertIn("if (s && s.ub === 'place') { toPlace(); return; }", JS)
        # Before the same address is read as Back.
        self.assertLess(JS.index("if (s && s.ub === 'place') { toPlace(); return; }"),
                        JS.index("if (location.href !== was.href) return;"))
        self.assertEqual(len(re.findall(r"function toPlace\(", JS)), 1)

    def test_the_section_being_read_is_on_a_band(self):
        # Tinted as a paragraph named is, the section's own link alone
        # (Tigran, 2026-11-17: ink against grey was "not bold enough").
        tint = "color-mix(in oklch, var(--link) 12%, transparent)"
        m = re.search(r"\.rail li\.here > a \{([^}]*)\}", CSS)
        self.assertIsNotNone(m)
        self.assertIn("background: " + tint, m.group(1))
        self.assertIn("box-shadow: 0 0 0 .3rem " + tint, m.group(1))
        self.assertIn("p.t.hit, p.t.named, .rc p.rt.hit, .rc p.rt.named, .tf p.rt.named { background: " + tint, CSS)

    def test_the_contents_open_in_the_paragraphs_translation(self):
        # From a translation's paragraph, as that translation gives its
        # contents (Tigran, 2026-11-17: "it would be nice to switch
        # automatically to that translation's variant of Contents"): for that
        # opening, the reader's own choice, `toc`, never changed by it.
        to = JS[JS.index("function toContents(p, k) {"):JS.index("// The place the address names")]
        self.assertIn("k = k && tocTicked().indexOf(k) >= 0 ? k : null;", to)
        self.assertIn("if (tocOver !== k) { tocOver = k; drawn = tocApply(); }", to)
        self.assertNotIn("ubSettings.set", to)
        self.assertIn("var k = tocOver || load().toc || '';", JS)
        # Forward to the entry opens them in it again, Back lets go of it, and
        # so do a choice in the list and a new page.
        self.assertIn("if (s && s.ub === 'contents') { contentsAt = s; toContents(null, s.k); return; }", JS)
        self.assertIn("if (tocOver) { tocOver = null; tocApply(); }", JS)
        self.assertIn("    tocOver = null;\n    window.ubSettings.set('toc', ev.target.value);\n    tocApply();", JS)
        self.assertIn("document.addEventListener('ub:swap', function () { tocOver = null; tocApply(); });", JS)
        # The entry's fresh load comes after the translations are read.
        self.assertLess(JS.index("TRS.forEach(function (x) { trBy[x.key] = x; });"),
                        JS.index("toContents(null, history.state.k); }"))

    def test_the_contents_line_is_the_way_back(self):
        # On a phone, open from the running head's reference: a tap on their
        # line goes back to the paragraph left, as Back does (Tigran,
        # 2026-11-17), and the line stays at the window's top while they are
        # open, so that it is at hand wherever in them the reader is.
        self.assertIn("if (!shut && contentsAt) { history.back(); return; }", JS)
        fold = JS[JS.index("var b = ev.target.closest && ev.target.closest('.railfold'), rail, shut;"):JS.index("  railSync();\n  if (phone.addEventListener)")]
        self.assertLess(fold.index("history.back()"), fold.index("rail.classList.toggle('shown', shut);"))
        phone = CSS[CSS.index("/* ---- phone ----"):]
        self.assertIn(".rail.shown { overflow: visible; }", phone)
        self.assertIn(".rail.shown .railhead { position: sticky; top: 0; }", phone)

    def test_rail_keeps_its_mark_above_the_text(self):
        # Scrolled up to the Contents, the rail still names the section left.
        self.assertIn("if (railMarkAt && s.getBoundingClientRect().top > 60) return;", JS)

    def test_head_lives_on_body(self):
        self.assertIn("document.body.appendChild(head)", JS)
        self.assertNotRegex(JS, r"main[^\n]*appendChild\(head\)")

    def test_no_template_names_it(self):
        # But Help's, which draws one still as an example (2026-11-06): a page
        # of its own, not a page of the text.
        for path in (ROOT / "ubsite" / "templates").glob("*.html"):
            if path.name != "help.html":
                self.assertNotIn("runhead", path.read_text(), path.name)

    def test_a_tap_names_and_never_turns(self):
        # The one click handler decides: a card, else the head.  A tap turned
        # the page too, by Settings' Tap to turn the page, until 2026-11-17
        # (Tigran): the setting, its handler and its band at the window's top
        # are gone, and a tap on a paragraph names it wherever it lands.
        self.assertIn("if (!card) { tapHead(ev); return; }", JS)
        self.assertRegex(JS, r"selDown = !getSelection\(\)\.isCollapsed")
        for gone in ("tapTurn", "tappage", "BAND"):
            self.assertNotIn(gone, JS)
        self.assertNotIn("tappage", (ROOT / "ubsite" / "settings.py").read_text().replace("`tappage`", ""))
        self.assertNotIn("Tap to turn the page", (ROOT / "ubsite" / "ru.toml").read_text())


if __name__ == "__main__":
    unittest.main()
