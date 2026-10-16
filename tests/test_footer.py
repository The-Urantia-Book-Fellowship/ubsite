"""The footer names the typeface the text is in, whichever Settings chose.

One sentence for each of Typeface's choices, all on every page, and ub.css
shows the one that is true: Goudy's with no data-face, another's under its
own.  So a typeface added to Settings fails here until the footer says what
it is.  Rendered through the app as ASGI, as test_appendix_pages does.
"""

import pathlib
import re
import unittest

from test_appendix_pages import DB, get
from ubsite.settings import READING

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text()
FACE = next(s for s in READING if s[0] == "face")
DEFAULT, CHOICES = FACE[3], [c[0] for c in FACE[4]]


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Footer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, _, body = get("/")
        assert status == 200, status
        cls.footer = body[body.rindex("<footer>"):body.rindex("</footer>")]

    def test_one_sentence_for_each_typeface(self):
        for face in CHOICES:
            self.assertEqual(len(re.findall(rf'class="setin {face}"', self.footer)), 1, face)
        self.assertEqual(len(re.findall(r'class="setin ', self.footer)), len(CHOICES))

    def test_goudy_is_named_with_its_licence(self):
        goudy = re.search(rf'class="setin {DEFAULT}">(.*?)</span>', self.footer).group(1)
        self.assertIn("UB&nbsp;Goudy", goudy)
        self.assertIn('href="/static/fonts/OFL.txt"', goudy)

    def test_the_stylesheet_shows_each_other_face_under_its_own_setting(self):
        # The rule that hides Goudy's sentence, and the one that shows another's.
        hide = re.search(r"([^}]*footer \.setin\.goudy[^{]*)\{", CSS).group(1)
        for face in CHOICES:
            if face != DEFAULT:
                self.assertIn(f'[data-face="{face}"]', hide, face)
                show = rf':root\[data-face="{face}"\] footer \.setin\.{face}\b'
                self.assertTrue(re.search(show, CSS), face)


if __name__ == "__main__":
    unittest.main()
