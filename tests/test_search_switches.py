"""Settings' switches for what the search results list (Tigran, 2026-10-28).

As "1955 readings in search results" (`notesearch`) has done since 2026-10-12,
three switches under Show take a kind of result off the search overview: the
index's Headwords and In the index (`indexsearch`), the study notes
(`studysearch`) and the translations (`trsearch`).  Each list is always sent,
since no setting reaches the server, and ub.css hides it.  The first two follow
their own switch and are greyed while it is off (settings.NEEDS); the
translations' is never greyed.  All three are on by default, so that nothing
changed for a reader who never turns one off.
"""

import re
import unittest

from test_appendix_pages import DB, ROOT, get
from ubsite import settings

# Each switch, and the one it follows in Show and needs, if any.
AFTER = {"indexsearch": ("index", "index"), "studysearch": ("studynotes", "studynotes"),
         "trsearch": ("notesearch", None)}


class Declared(unittest.TestCase):
    def test_each_follows_its_switch_and_is_on(self):
        keys = [s[0] for s in settings.SHOW]
        for key, (after, _) in AFTER.items():
            with self.subTest(key=key):
                self.assertEqual(keys[keys.index(key) - 1], after)
                self.assertIs(settings.defaults()[key], True)

    def test_greyed_while_what_it_lists_is_off(self):
        for key, (_, needs) in AFTER.items():
            with self.subTest(key=key):
                self.assertEqual(settings.NEEDS.get(key), needs)

    def test_css_hides_what_it_says(self):
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        self.assertIn(':root[data-studynotes="true"]:not([data-studysearch="off"]) .bystudy { display: block; }', css)
        self.assertIn(':root[data-indexsearch="off"] .results > .ix { display: none; }', css)
        self.assertIn(':root[data-trsearch="off"] .trhits { display: none; }', css)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Dialog(unittest.TestCase):
    def test_in_the_dialog(self):
        page = get("/")[2]
        for key, (_, needs) in AFTER.items():
            with self.subTest(key=key):
                m = re.search(r'<label([^>]*)><input type="checkbox" name="' + key + '">', page)
                self.assertIsNotNone(m)
                self.assertEqual(re.search(r'data-needs="([^"]*)"', m[1])[1] if needs else m[1],
                                 needs or "")


if __name__ == "__main__":
    unittest.main()
