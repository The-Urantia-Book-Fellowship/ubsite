"""The footer says which text and which index this is, links the changelog,
and says what the site's terms are; nothing more (Tigran, 2026-10-18).  It is
in every page's markup and shown on three, the home page, Help and the API's
(Tigran, 2026-11-14), by the stylesheet, so that no stored page of the offline
copy moves; tools/help_e2e.py looks at it in Chrome.

Until then it gave each source's commit date, linked to its private
repository on GitHub (/healthz still names the commits), said that other sites
may sync with the text (the home page links /api), named the typeface the
text is in, and said how visits are counted.  The typeface's licence is now in
Settings, beside Goudy.  Rendered through the app as ASGI, as
test_appendix_pages does.
"""

import pathlib
import re
import unittest

from test_appendix_pages import DB, get

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Footer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, _, body = get("/")
        assert status == 200, status
        cls.body = body
        cls.footer = body[body.rindex("<footer>"):body.rindex("</footer>")]

    def test_names_no_commit_and_no_typeface(self):
        self.assertNotIn("github", self.footer.lower())
        self.assertNotRegex(self.footer, r"\d{4}-\d\d-\d\d|[0-9a-f]{7,40}")
        self.assertNotIn("Goudy", self.footer)
        self.assertNotIn('href="/api"', self.footer)
        self.assertNotIn("cookies", self.footer)

    def test_links_the_changelog_and_the_licence(self):
        self.assertIn('<a href="/changelog">Changelog</a>', self.footer)
        self.assertIn('rel="license"', self.footer)

    def test_every_page_carries_it_and_three_show_it(self):
        """The same footer in a page of the text as on the home page; shown by
        the <main> before it, which is the home page's, Help's or the API's."""
        for url in ("/1:1", "/i/god", "/cosmology", "/help", "/api"):
            status, _, body = get(url)
            self.assertEqual(status, 200, url)
            self.assertEqual(body[body.rindex("<footer>"):body.rindex("</footer>")], self.footer, url)
        for url, cls in (("/", "front"), ("/help", "helppage"), ("/api", "api")):
            _, _, body = get(url)
            self.assertRegex(body, r'<main class="[^"]*\b%s\b' % cls, url)
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertIn("footer p { display: none;", css)
        self.assertIn("main:is(.front, .helppage, .api) ~ footer p { display: block; }", css)
        # The line that says a page is from the offline copy is shown wherever it is so.
        self.assertIn("main:is(.front, .helppage, .api) ~ footer, footer[data-copy] {", css)
        # And the room for the player under a page's foot is still the footer's.
        self.assertIn("body.listening footer { padding-bottom: 5.5rem; }", css)

    def test_settings_links_goudys_licence_beside_it(self):
        goudy = re.search(r'<label class="face-goudy"[^>]*>(.*?)</label>', self.body, re.S).group(1)
        self.assertIn('href="/static/fonts/OFL.txt"', goudy)
        status, _, licence = get("/static/fonts/OFL.txt")
        self.assertEqual(status, 200)
        self.assertIn("SIL OPEN FONT LICENSE", licence.upper())


if __name__ == "__main__":
    unittest.main()
