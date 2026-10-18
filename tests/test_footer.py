"""The footer says which text and which index this is, links the changelog,
and says what the site's terms are; nothing more (Tigran, 2026-10-18).

Until then it gave each source's commit date, linked to its private
repository on GitHub (/healthz still names the commits), said that other sites
may sync with the text (the home page links /api), named the typeface the
text is in, and said how visits are counted.  The typeface's licence is now in
Settings, beside Goudy.  Rendered through the app as ASGI, as
test_appendix_pages does.
"""

import re
import unittest

from test_appendix_pages import DB, get


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

    def test_settings_links_goudys_licence_beside_it(self):
        goudy = re.search(r'<label class="face-goudy"[^>]*>(.*?)</label>', self.body, re.S).group(1)
        self.assertIn('href="/static/fonts/OFL.txt"', goudy)
        status, _, licence = get("/static/fonts/OFL.txt")
        self.assertEqual(status, 200)
        self.assertIn("SIL OPEN FONT LICENSE", licence.upper())


if __name__ == "__main__":
    unittest.main()
