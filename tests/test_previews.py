"""Paragraph previews and the cards' own drag (ub.js pvLink, popTouch).

Settings' Paragraph previews shows the paragraph a reference points to in a
card, under the pointer where it rests and at a tap on a touch screen.  Two
things went wrong on Tigran's phone, both found on 2026-11-12:

With Whole paper on, a tap went to the place instead.  The Whole paper
handler has every click first, in the capture phase, and rewrites the link in
the reader's unit, /30:4.1-8 to /30#30:4.1-8 (base.html ubUnit); the preview's
handler then read an address in a form it did not know.  So PV reads both.

And dragging on past the end of a long note moved the text under it.  The
words are held by the stylesheet's overscroll-behavior, but the strip above
them is not part of what scrolls; popTouch, on every card as it is made,
cancels a stroke the words cannot take.

These hold the static facts.  Chrome is driven through the taps and the drags
themselves by tools/preview_e2e.py, which is not a gate.
"""

import re
import unittest

from test_appendix_pages import ROOT

CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text()
JS = (ROOT / "ubsite" / "static" / "ub.js").read_text()


def body(name: str) -> str:
    """A function of ub.js, from its name to the next one at its depth."""
    start = JS.index("\n  function " + name + "(")
    return JS[start:JS.index("\n  function ", start + 1)]


class Address(unittest.TestCase):
    # The pattern as ub.js has it, run here: a backreference and a group that
    # is not kept read the same in both languages.
    PV = re.compile(re.search(r"\n  var PV = /(.+?)/, pv = null", JS).group(1))

    def test_as_the_server_writes_it(self):
        self.assertEqual(self.PV.fullmatch("/30:4.1-8").groups(), ("30", "4", "1", "8"))
        self.assertEqual(self.PV.fullmatch("/12:4.14").groups(), ("12", "4", "14", None))

    def test_as_whole_paper_makes_it(self):
        # The same groups, so nothing after pvLink knows which form it was.
        self.assertEqual(self.PV.fullmatch("/30#30:4.1-8").groups(), ("30", "4", "1", "8"))
        self.assertEqual(self.PV.fullmatch("/12#12:4.14").groups(), ("12", "4", "14", None))

    def test_nothing_else(self):
        for a in ("/30#31:4.1",          # a place on another paper is no address
                  "/30:4", "/30#30:4",   # a section is a page, and shows nothing
                  "/30", "/30:4.1#tr-ud", "/30#30:4.1#tr-ud", "/i/god", "/30:4.1-", "30:4.1"):
            self.assertIsNone(self.PV.fullmatch(a), a)

    def test_the_link_is_read_once_through_it(self):
        self.assertIn("m = PV.exec(a.getAttribute('href') || '');", body("pvLink"))

    def test_whole_paper_has_the_click_first(self):
        # Which is why both forms: its handler is registered before the
        # preview's, both on the document in the capture phase.
        unit = JS.index("if (to !== at) a.href = to;")
        self.assertLess(unit, JS.index("r = pvLink(t);"))
        self.assertRegex(JS[unit:JS.index("\n  // Bring the page's focus into view.")], r"\}, true\);")


class Drag(unittest.TestCase):
    def test_every_card_has_it(self):
        # A note's, a 1955 reading's and a translator's (open), and a preview.
        self.assertIn("host.appendChild(el);\n    popTouch(el);", body("open"))
        self.assertIn("host.appendChild(el);\n      popTouch(el);", body("pvOpen"))
        self.assertEqual(JS.count("popTouch(el);"), 2)

    def test_on_the_card_and_never_the_document(self):
        # A listener that may cancel makes every touch under it wait for script.
        f = body("popTouch")
        self.assertIn("el.addEventListener('touchmove', function (ev) {", f)
        self.assertIn("}, { passive: false });", f)
        self.assertEqual(JS.count("passive: false"), 1)
        self.assertNotRegex(JS, r"document\.addEventListener\('touch(?:start|move)'")

    def test_decided_once_at_the_first_move(self):
        f = body("popTouch")
        self.assertIn("mine = null;\n    }, { passive: true });", f)      # at each touch
        self.assertIn("if (mine === null) {", f)
        self.assertIn("mine = body.contains(ev.target) && (", f)             # the strip is not the words
        self.assertIn("if (!mine && ev.cancelable) ev.preventDefault();", f)

    def test_a_pinch_and_a_selection_are_the_browsers(self):
        self.assertIn("if (ev.touches.length > 1 || !getSelection().isCollapsed) return;", body("popTouch"))

    def test_the_stylesheet_holds_the_words_still(self):
        # For the wheel and the trackpad, which no touch handler sees.
        self.assertRegex(CSS, r"\.pop \.body \{[^}]*overflow-y: auto;\s*overscroll-behavior: contain; \}")


if __name__ == "__main__":
    unittest.main()
