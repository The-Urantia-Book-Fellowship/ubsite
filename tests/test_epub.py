"""The EPUB's two hinges: where a site address lands, and what a paragraph says.

`hrefs.Hrefs.site` must map every form the stored index HTML uses and refuse
anything else; `check.para_text` must take back exactly what the EPUB adds to
a paragraph (its reference, pilcrow, note marker) and nothing more.  The whole
book is gated by `make epub`; these pin the rules.  The address tests are
skipped when var/ub.db has not been built.
"""

import pathlib
import sqlite3
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "var" / "ub.db"

from epub import check, hrefs  # noqa: E402


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Addresses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.h = hrefs.Hrefs(con)
        slug, anchor = con.execute(
            "SELECT r.slug, e.anchor FROM index_entry e JOIN index_entry r ON r.id=e.root_id"
            " WHERE e.scope='az' AND e.level=2 AND r.slug='seraphim' ORDER BY e.ord").fetchone()
        cls.deep = (slug, anchor)
        cls.app = con.execute("SELECT anchor FROM index_entry WHERE scope='C' ORDER BY ord"
                              ).fetchone()[0]
        cls.h.index_file["seraphim"] = "index-S-9.xhtml"
        con.close()

    def test_the_text(self):
        self.assertEqual(self.h.site("/101:4.2"), "p101.xhtml#p101_4_2")
        self.assertEqual(self.h.site("/77:9.4-5"), "p077.xhtml#p77_9_4")    # a range: its first
        self.assertEqual(self.h.site("/76:2"), "p076.xhtml#s76_2")
        self.assertEqual(self.h.site("/0"), "p000.xhtml")

    def test_the_index(self):
        slug, anchor = self.deep
        self.assertTrue(self.h.site("/i/seraphim").startswith("index-S-9.xhtml#e"))
        self.assertEqual(self.h.site(f"/i/{slug}#{anchor}"), f"index-S-9.xhtml#{anchor}")
        self.assertEqual(self.h.site(f"/appendix/C#{self.app}"), f"app-C.xhtml#{self.app}")

    def test_refuses(self):
        for bad in ("/search?q=God", "/read", "/i/seraphim#nope", "/101:4.999",
                    "/101:4.2-999", "/197", "/appendix/G#x", "http://x/"):
            with self.subTest(bad), self.assertRaises((KeyError, ValueError)):
                self.h.site(bad)
        with self.assertRaises(KeyError):
            self.h.site("/i/adoption")                  # not laid out: no file yet

    def test_rewrite_keeps_a_note(self):
        s = '<a class="fn" href="#fn105_3_8_0" id="fnref105_3_8_0"></a><a href="/1:0.1">x</a>'
        self.assertEqual(self.h.rewrite(s), s.replace("/1:0.1", "p001.xhtml#p1_0_1"))


class ParagraphText(unittest.TestCase):
    X = 'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'

    def text(self, inner):
        return check.para_text(ET.fromstring(f'<p {self.X} class="t">{inner}</p>'))

    def test_takes_back_what_the_epub_adds(self):
        self.assertEqual(self.text(
            '<span class="ref">105:3.8</span> <span class="pc">¶</span><span class="mark">7.</span>'
            ' <em>The Universal Absolute.</em> correlator<a class="fn" epub:type="noteref"'
            ' href="#fn" id="r">*</a> of the absolute'),
            "7. The Universal Absolute. correlator of the absolute")

    def test_keeps_everything_else(self):
        self.assertEqual(self.text('<span class="ref">1:0.1</span> A <span class="jesus">'
                                   '“Fear not.”</span> B<span class="leader"></span>7'),
                         "A “Fear not.” B7")


if __name__ == "__main__":
    unittest.main()
