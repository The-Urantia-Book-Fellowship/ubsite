"""Settings' "Index and appendices": off, the site is the book alone.

The switch (settings.py `index`, Tigran, 2026-10-18) hides by CSS alone, since
no setting reaches the server: `data-index="off"` on <html> hides the margin,
the box of what a whole section or paper cites, the Index button, and whatever
is marked `.ix` (ub.css).  So the test is that every way into the index or the
appendices, on a page that is not one of their own, stands inside something
the switch hides.  Their own pages, /index, /i/..., /appendix..., and the search
results opened as the index alone, stay as they are.  Skipped when var/ub.db
has not been built.
"""

import re
import unittest
from html.parser import HTMLParser

from test_appendix_pages import DB, ROOT, get
from ubsite import settings

# Where a link goes into the index or the appendices.
INTO = re.compile(r"^/(i/|index\b|appendix\b)")
# What the switch hides, by class (ub.css).
HIDDEN = {"ix", "a", "blanket", "marginhead"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
PAGES = ["/", "/read", "/part/1", "/lists", "/lists/1955", "/api", "/101:4", "/144:3",
         "/search?q=jesus", "/search?q=god", "/0:0.99"]


class Links(HTMLParser):
    """Every link into the index, and whether the switch hides it."""

    def __init__(self):
        super().__init__()
        self.stack, self.links = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hid = (bool(self.stack) and self.stack[-1][1]) or bool(HIDDEN & set((a.get("class") or "").split()))
        if tag == "a" and INTO.match(a.get("href") or ""):
            self.links.append((a["href"], hid))
        if tag not in VOID:
            self.stack.append((tag, hid))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return


def links(body: str) -> list[tuple[str, bool]]:
    p = Links()
    p.feed(body)
    return p.links


class Switch(unittest.TestCase):
    def test_declared_on_by_default(self):
        self.assertIs(settings.defaults()["index"], True)
        show = [s[0] for s in settings.SHOW]
        self.assertEqual(show[0], "index")

    def test_css_hides_what_it_says(self):
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text()
        self.assertIn(':root[data-index="off"] :is(.ix, .a, .blanket, .reader .marginhead) { display: none; }', css)
        self.assertIn(':root:not([data-index="off"]) .noix { display: none; }', css)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Pages(unittest.TestCase):
    def test_every_way_into_the_index_is_hidden(self):
        seen = 0
        for url in PAGES:
            status, _, body = get(url)
            self.assertIn(status, (200, 404), url)
            if url == "/":
                self.assertIn('<input type="checkbox" name="index">', body)
            for href, hid in links(body):
                seen += 1
                self.assertTrue(hid, f"{url}: a link to {href} the switch leaves")
        # The pages above do link into the index, in their margins, boxes and lines.
        self.assertGreater(seen, 100)

    def test_a_box_and_a_margin_are_hidden(self):
        # 1:0 opens with entries citing the whole of Paper 1.
        status, _, body = get("/1:0")
        self.assertEqual(status, 200)
        self.assertIn('<aside class="blanket">', body)
        self.assertIn('<div class="marginhead">', body)
        self.assertTrue(all(hid for _, hid in links(body)))

    def test_search_hides_the_index_in_the_overview_only(self):
        _, _, body = get("/search?q=jesus")
        self.assertIn('<section class="ix"><h2>Headwords</h2>', body)
        self.assertIn('<section class="ix"><h2>In the index', body)
        self.assertIn("<section><h2>In the text", body)
        _, _, body = get("/search?q=jesus&in=index")
        self.assertIn("<section><h2>Headwords</h2>", body)
        self.assertIn("<section><h2>In the index", body)
        self.assertNotIn('class="ix"><h2>', body)

    def test_the_index_s_own_pages_stay(self):
        # An address asked for is answered: nothing on the index's own pages
        # is hidden but the header's link.
        for url in ("/index", "/i/god", "/appendix", "/appendix/C"):
            status, _, body = get(url)
            self.assertEqual(status, 200, url)
            ls = links(body)
            self.assertTrue(any(not hid for _, hid in ls), url)
