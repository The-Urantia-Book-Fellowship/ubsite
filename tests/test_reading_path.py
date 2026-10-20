"""Reading paths, /i/<slug>/read: a headword's citations read as one text.

Every paragraph a headword cites is drawn in full once, in book order or by
theme, with its reference as its id; one met again is a line pointing back;
what a section has between two drawn is folded, and a fold's copy carries no
id (Tigran, 2026-10-13).  A headword citing fewer than three paragraphs has
no path.  Which headwords cite what is edited daily, so the cases are asked of
the database.  Skipped when var/ub.db has not been built.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get

RE_ID = re.compile(r'\bid="([^"]+)"')


def cited(con, root_id: int) -> set[str]:
    """The references of every paragraph a headword's path draws in full."""
    return {r[0] for r in con.execute(
        "SELECT DISTINCT p.ref FROM para_citers c JOIN index_entry e ON e.id = c.entry_id"
        " JOIN paragraph p ON p.id = c.paragraph_id"
        " WHERE e.root_id = ? AND c.precision IN ('para', 'sec')", (root_id,))}


def drawn(body: str) -> list[str]:
    """The ids of the paragraphs a page draws in full."""
    return re.findall(r'<p class="t[^"]*"\s+id="([^"]+)"', body)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class ReadingPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def path(self, slug):
        return self.con.execute(
            "SELECT e.id, e.slug, r.* FROM index_entry e JOIN reading_path r ON r.root_id = e.id"
            " WHERE e.slug = ?", (slug,)).fetchone()

    def test_every_cited_paragraph_once_in_both_orders(self):
        for slug in ("humor", "prayer"):
            r = self.path(slug)
            refs = cited(self.con, r["id"])
            self.assertEqual(len(refs), r["n_paragraphs"])
            for url in (f"/i/{slug}/read", f"/i/{slug}/read/theme"):
                status, _, body = get(url)
                self.assertEqual(status, 200, url)
                ids = drawn(body)
                self.assertEqual(sorted(ids), sorted(refs), url)
                self.assertTrue(f"{r['n_paragraphs']} paragraphs" in body, url)
                all_ids = RE_ID.findall(body)
                self.assertEqual(len(all_ids), len(set(all_ids)), f"{url}: an id repeats")
                # A paragraph met again points back at one drawn on the page.
                back = re.findall(r'<div class="row again"><p class="t"><span class="stk"><a class="num" href="#([^"]+)"', body)
                self.assertTrue(set(back) <= set(ids), url)
                if url.endswith("/read"):
                    self.assertEqual(back, [], "book order draws each paragraph once")
            self.assertTrue(back, f"{slug} by theme meets no paragraph twice")

    def test_a_fold_holds_what_a_section_leaves_out(self):
        status, _, body = get("/i/prayer/read")
        folds = re.findall(r'<details class="gap">(.*?)</details>', body, re.S)
        self.assertTrue(folds)
        for f in folds:
            self.assertEqual(drawn(f), [], "a fold's copy has no id")
            self.assertEqual(f.count('class="gl"'), 2, "the line above and below")
            self.assertIn('<button type="button" class="foldup">', f)

    def test_a_range_is_captioned_at_its_first_paragraph(self):
        # An entry citing a range of two paragraphs of prose, in a headword
        # with a path, and naming the second nowhere on its own.
        r = self.con.execute(
            "SELECT h.slug, e.anchor, p.ref FROM citation_target t"
            " JOIN citation c ON c.id = t.citation_id JOIN index_entry e ON e.id = t.entry_id"
            " JOIN index_entry h ON h.id = e.root_id JOIN reading_path rp ON rp.root_id = h.id"
            " JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE NOT t.opens AND e.level > 1 AND c.n_targets = 2 AND p.src = 'vs'"
            "   AND c.canonical NOT LIKE '%,%'"
            "   AND NOT EXISTS (SELECT 1 FROM citation_target u WHERE u.entry_id = t.entry_id"
            "                   AND u.paragraph_id = t.paragraph_id AND u.opens)"
            " ORDER BY c.id LIMIT 1").fetchone()
        self.assertIsNotNone(r)
        status, _, body = get(f"/i/{r['slug']}/read")
        self.assertEqual(status, 200)
        rows = re.findall(r'<div class="row">(.*?)</div>', body, re.S)
        row = next(x for x in rows if f'id="{r["ref"]}"' in x)
        self.assertFalse(f'#{r["anchor"]}"' in row, f"{r['ref']} is captioned")
        self.assertTrue(f'#{r["anchor"]}"' in body, "the range is captioned nowhere")

    def test_a_section_cited_whole_is_drawn_whole(self):
        r = self.con.execute(
            "SELECT h.slug, t.paper, t.section FROM citation_target t"
            " JOIN index_entry e ON e.id = t.entry_id JOIN index_entry h ON h.id = e.root_id"
            " JOIN reading_path rp ON rp.root_id = h.id"
            " WHERE t.precision = 'sec' ORDER BY rp.n_paragraphs LIMIT 1").fetchone()
        status, _, body = get(f"/i/{r['slug']}/read")
        self.assertEqual(status, 200)
        refs = [x[0] for x in self.con.execute(
            "SELECT ref FROM paragraph WHERE paper_n = ? AND section_n = ?",
            (r["paper"], r["section"]))]
        self.assertTrue(set(refs) <= set(drawn(body)))
        self.assertTrue("the whole section" in body)

    def test_a_paper_cited_whole_is_a_signpost(self):
        r = self.con.execute(
            "SELECT h.slug, t.paper FROM citation_target t"
            " JOIN index_entry e ON e.id = t.entry_id JOIN index_entry h ON h.id = e.root_id"
            " JOIN reading_path rp ON rp.root_id = h.id"
            " WHERE t.precision = 'paper' ORDER BY rp.n_paragraphs LIMIT 1").fetchone()
        status, _, body = get(f"/i/{r['slug']}/read")
        self.assertEqual(status, 200)
        self.assertTrue(f'<p class="signpost">Paper {r["paper"]},' in body, r["slug"])

    def test_verse_is_set_as_verse(self):
        r = self.con.execute(
            "SELECT h.slug, p.ref FROM citation_target t"
            " JOIN index_entry e ON e.id = t.entry_id JOIN index_entry h ON h.id = e.root_id"
            " JOIN reading_path rp ON rp.root_id = h.id JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE p.src <> 'vs' ORDER BY rp.n_paragraphs LIMIT 1").fetchone()
        status, _, body = get(f"/i/{r['slug']}/read")
        self.assertEqual(status, 200)
        block = r'(?s)<div class="verse">(?:(?!</div>).)*id="' + re.escape(r["ref"]) + '"'
        self.assertTrue(re.search(block, body), f"{r['ref']} is not in a verse block")

    def test_no_1955_rings(self):
        status, _, body = get("/i/jesus/read")
        self.assertEqual(status, 200)
        self.assertFalse('class="fn"' in body, "a 1955 ring in a path")

    def test_who_has_a_path(self):
        # Two paragraphs are not enough; the concept page says nothing of one.
        slug, = self.con.execute(
            "SELECT e.slug FROM index_entry e JOIN para_citers c ON c.entry_id IN"
            " (SELECT id FROM index_entry WHERE root_id = e.id)"
            " WHERE e.level = 1 AND e.scope = 'az' AND c.precision IN ('para', 'sec')"
            " GROUP BY e.id HAVING COUNT(DISTINCT c.paragraph_id) = 2 LIMIT 1").fetchone()
        for url in (f"/i/{slug}/read", f"/i/{slug}/read/theme"):
            status, headers, _ = get(url)
            self.assertEqual((status, headers.get("location")), (307, f"/i/{slug}"), url)
        status, _, body = get(f"/i/{slug}")
        self.assertFalse(f'href="/i/{slug}/read"' in body, f"/i/{slug} offers a path")
        status, _, body = get("/i/humor")
        self.assertTrue('href="/i/humor/read"' in body, "/i/humor offers no path")
        # One chapter has nothing to read by theme.
        slug, = self.con.execute(
            "SELECT e.slug FROM reading_path r JOIN index_entry e ON e.id = r.root_id"
            " WHERE r.n_chapters = 1 LIMIT 1").fetchone()
        status, headers, _ = get(f"/i/{slug}/read/theme")
        self.assertEqual((status, headers.get("location")), (307, f"/i/{slug}/read"))
        status, _, body = get(f"/i/{slug}/read")
        self.assertEqual(status, 200)
        self.assertFalse('class="orders"' in body, f"/i/{slug}/read offers By theme")
        self.assertEqual(get("/i/no-such-headword/read")[0], 404)

    def test_visits_count_paths_apart(self):
        from ubsite.stats import page_kind
        self.assertEqual(page_kind("/i/prayer/read"), ("path", "prayer"))
        self.assertEqual(page_kind("/i/prayer/read/theme"), ("path", "prayer"))
        self.assertEqual(page_kind("/i/prayer"), ("concept", "prayer"))
