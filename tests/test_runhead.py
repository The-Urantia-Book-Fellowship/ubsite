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
        self.assertIn("p.t.hit, p.t.named, .rc p.rt.hit, .rc p.rt.named {", CSS)

    def test_a_translation_tapped_in_columns_is_named_alone(self):
        # Never the English beside it (Tigran, 2026-11-08): its own reference
        # in the head, and Back from the Contents kept by the row's English.
        self.assertIn("return t.closest('p.t[id], .rc p.rt') ||", JS)
        self.assertIn("head.querySelector('.ref').textContent = p.id || p.dataset.ref;", JS)
        self.assertIn("toContents(p && (p.id ? p : document.getElementById(p.dataset.ref)));", JS)

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
        self.assertIn("state = { ub: 'contents', p: p.id, top: p.getBoundingClientRect().top, shown: !shut, href: location.href };", JS)
        self.assertIn("if (location.href !== was.href) return;", JS)
        self.assertIn("if (contentsAt) history.replaceState(state, ''); else history.pushState(state, '');", JS)
        self.assertIn("if (contentsAt && history.state && history.state.ub === 'contents') return;", JS)
        self.assertIn("if (history.state && history.state.ub === 'contents') { contentsAt = history.state; toContents(null); }", JS)

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

    def test_tap_comes_before_the_turn(self):
        # The one click handler decides: a card, else the head, else the turn.
        self.assertIn("if (!card) { if (!tapHead(ev)) tapTurn(ev); return; }", JS)
        self.assertRegex(JS, r"selDown = !getSelection\(\)\.isCollapsed")


if __name__ == "__main__":
    unittest.main()
