"""Addresses a reader can type that name nothing in the book are a 404, never a
500, and a citation typed into the search box costs no more than the book.

Found by the review of 2026-11-09: a number of 2**63 or more in an address
reached SQLite, which cannot bind it (OverflowError, a 500); \\d and $ in
app.py RE_REF took fullwidth digits and a trailing newline as a reference,
which offline-core.js does not; "²".isdigit() is True and int("²") raises;
and cite.py expands every range it is given, so /search?q=1:1.1-99999999
asked a worker for 3 GB.  Where offline/check.py can compare the offline
copy's answer byte for byte, it does; these are the server's side.
"""

import pathlib
import resource
import sys
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from test_appendix_pages import DB, get  # noqa: E402

BIG = str(2**63)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Addresses(unittest.TestCase):
    def test_numbers_past_sqlite_are_not_found(self):
        for url in (f"/{BIG}:0", f"/1:{BIG}", f"/{BIG}", f"/{BIG}:0.1", f"/quiz/{BIG}", f"/part/{BIG}",
                    f"/speech/{BIG}:1", f"/speech/ud/{BIG}:1", f"/tr/{BIG}:1", f"/rail/{BIG}",
                    "/" + "9" * 30 + ":1"):
            self.assertEqual(get(url)[0], 404, url)

    def test_only_the_digits_0_to_9(self):
        for url in ("/１:１", "/١:١", "/１", "/1:1\n", "/1:1.2-3\n", "/tr/１:１", "/speech/１:１"):
            self.assertEqual(get(url)[0], 404, repr(url))
        self.assertEqual(get("/1:1.2-3")[0], 200)

    def test_a_page_number_is_digits(self):
        for page in ("²", "٢", "1" + "0" * 5000, "0" * 30 + "2", "x", "0"):
            self.assertEqual(get("/search?q=god&in=text&page=" + urllib.parse.quote(page))[0], 200, page[:10])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Citations(unittest.TestCase):
    def test_a_citation_opens(self):
        for q, to in (("1:1.1-3", "/1:1.1-3"), ("Papers 1-3", "/1"), ("101:4-6secs", "/101:4"),
                      ("1:1.1–3", "/1:1.1-3")):
            st, h, _ = get("/search?q=" + urllib.parse.quote(q))
            self.assertEqual((st, h.get("location")), (303, to), q)

    def test_a_range_past_the_book_is_words(self):
        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        for q in ("1:1.1-99999999", "1:1-99999999secs", "Papers 0-99999999", "Papers 0 - 99999999",
                  "1:1.1-99999999999999999999", "1:1.1-15000", "1:1.1-9000,1-9000", "1:1.1-١٠"):
            st, h, _ = get("/search?q=" + urllib.parse.quote(q))
            self.assertEqual(st, 200, q)
            self.assertNotIn("location", h, q)
        # A list of 10**8 numbers is gigabytes; what the page costs is megabytes.
        grew = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before
        self.assertLess(grew, 200 * 1024, "kilobytes")


if __name__ == "__main__":
    unittest.main()
