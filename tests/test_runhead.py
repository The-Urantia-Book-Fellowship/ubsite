"""The running head on demand (ub.js tapHead, 2026-10-31): a tap on the text
shows the book's running head over the top of the window, the paragraph's
reference, the paper's number, title and author, and the gear, and a tap or
two lines of reading hides it.  It is built by ub.js from what the page
carries and kept on <body>, so that no template names it and no stored page
of the offline copy moves with it (CLAUDE.md trap 29).  These hold the static
facts: the stylesheet hides it in print and tints the paragraph it names as a
search hit; the script names its one interface word as a literal, in the
form test_l10n and app.py read, and appends the head to the body; and no
template knows of it.  Chrome is driven through the gesture itself by
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
        self.assertIn("p.t.hit, p.t.named {", CSS)

    def test_dash_is_generated_content(self):
        # So that build/fonts.py, which reads content: strings and never a
        # script, keeps the glyph in the face.
        self.assertIn('.runhead .tt:not(:first-child)::before { content: " – "; }', CSS)
        self.assertNotIn("' – '", JS)

    def test_script_names_its_words_as_literals(self):
        self.assertIn("T.attr(head, 'aria-label', 'Running head')", JS)
        self.assertIn("T.attr(btn, 'aria-label', 'Settings')", JS)

    def test_head_lives_on_body(self):
        self.assertIn("document.body.appendChild(head)", JS)
        self.assertNotRegex(JS, r"main[^\n]*appendChild\(head\)")

    def test_no_template_names_it(self):
        for path in (ROOT / "ubsite" / "templates").glob("*.html"):
            self.assertNotIn("runhead", path.read_text(), path.name)

    def test_tap_comes_before_the_turn(self):
        # The one click handler decides: a card, else the head, else the turn.
        self.assertIn("if (!card) { if (!tapHead(ev)) tapTurn(ev); return; }", JS)
        self.assertRegex(JS, r"selDown = !getSelection\(\)\.isCollapsed")


if __name__ == "__main__":
    unittest.main()
