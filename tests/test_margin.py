"""The margin beside a paragraph: a range stands once, and nothing is said of none.

An entry citing a range, 44:0.20-21, stands beside its first paragraph alone,
and its citation on the concept page still opens the range with every
paragraph of it tinted (Tigran, 2026-10-13).  A paragraph that nothing cites
precisely has an empty margin, not "no entry cites this paragraph precisely".
Which ranges the index cites is edited daily, so the cases are asked of the
database.  Skipped when var/ub.db has not been built.

An entry citing a whole paper stands once, in the box above section 0, under
"Cited across this whole paper", and in no other section's box (Tigran,
2026-10-17); what cites a whole section stands in that section's.

The index folds (templates/_fold.html): a button at the head of a section page
and of a reading path, and in every box of entries a line saying how many it
holds, which is the box on a phone while the index is folded.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, get
from ubsite import queries


RE_AFOLD = re.compile(r'<button class="afold" type="button" aria-expanded="false">'
                      r'(\d+) index entr(y|ies)( across (?:this whole section|this whole paper'
                      r'|the whole paper and this section))?</button>')
# A box's line, by which of its two headings it has.
TAILS = {(False, True): " across this whole section", (True, False): " across this whole paper",
         (True, True): " across the whole paper and this section"}


def box(body: str) -> str:
    """The box of what the whole section, or paper, cites, or ""."""
    b = re.search(r'<aside class="blanket">(.*?)</aside>', body, re.S)
    return b[1] if b else ""


def box_chips(body: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", li) for li in re.findall(r"<li>(.*?)</li>", box(body), re.S)]


def entries(items: list) -> list:
    """queries.section's chips, each Chronology window's events and each
    group's entries among them."""
    return [e for c in items for e in (c["events"] if isinstance(c, dict) and c.get("window")
                                       else c["entries"] if isinstance(c, dict) else [c])]


def margin(body: str, ref: str) -> str:
    """What stands beside paragraph `ref` of a section page."""
    # Up to what follows the margin -- the next paragraph, a block of verse,
    # a separator, the grid's end -- since a Chronology window is a div too.
    m = re.search(r'id="' + re.escape(ref) + r'">.*?</p>\s*<div class="a">(.*?)</div>'
                  r'\s*(?=<p class="t|<div class="(?:verse|stars)"|</div>)', body, re.S)
    assert m, f"no margin after {ref}"
    return m.group(1)


def classes(body: str, ref: str) -> list[str]:
    m = re.search(r'<p class="([^"]*)"\s+id="' + re.escape(ref) + '"', body)
    assert m, f"no paragraph {ref}"
    return m.group(1).split()


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Margin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def test_a_range_stands_beside_its_first_paragraph(self):
        from ubsite.app import entry_href
        # An A-Z entry citing two paragraphs of prose as a range, and naming the
        # second nowhere on its own.
        r = self.con.execute(
            "SELECT c.canonical, r.slug, e.level, e.anchor, p.paper_n, p.section_n,"
            "       p.para_n - 1 AS first, p.para_n AS cont"
            " FROM citation_target t JOIN citation c ON c.id = t.citation_id"
            " JOIN index_entry e ON e.id = t.entry_id JOIN index_entry r ON r.id = e.root_id"
            " JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE NOT t.opens AND e.scope = 'az' AND c.n_targets = 2"
            "   AND c.canonical NOT LIKE '%,%' AND p.src = 'vs'"
            "   AND NOT EXISTS (SELECT 1 FROM citation_target u WHERE u.entry_id = t.entry_id"
            "                   AND u.paragraph_id = t.paragraph_id AND u.opens)"
            " ORDER BY c.id LIMIT 1").fetchone()
        self.assertIsNotNone(r)
        sec = f"{r['paper_n']}:{r['section_n']}"
        first, cont = f"{sec}.{r['first']}", f"{sec}.{r['cont']}"
        self.assertEqual(r["canonical"], f"{first}-{r['cont']}")
        href = f'href="{entry_href(r["slug"], r["level"], r["anchor"])}"'

        status, _, body = get(f"/{sec}")
        self.assertEqual(status, 200)
        self.assertIn(href, margin(body, first))
        self.assertNotIn(href, margin(body, cont))

        # The concept page still cites the range, and the range tints both.
        status, _, page = get(f"/i/{r['slug']}")
        self.assertEqual(status, 200)
        self.assertIn(f'href="/{r["canonical"]}"', page)
        status, _, body = get(f"/{r['canonical']}")
        self.assertEqual(status, 200)
        self.assertIn("hit", classes(body, first))
        self.assertIn("hit", classes(body, cont))

    def test_a_paragraph_nothing_cites_has_an_empty_margin(self):
        ref, = self.con.execute(
            "SELECT p.ref FROM paragraph p JOIN para_density d ON d.paragraph_id = p.id"
            " WHERE d.thin AND p.src = 'vs' ORDER BY p.ord LIMIT 1").fetchone()
        status, _, body = get("/" + ref.split(".")[0])
        self.assertEqual(status, 200)
        self.assertEqual(margin(body, ref), "")
        self.assertNotIn("no entry cites", body)

    def test_the_index_folds_from_the_head_of_the_page(self):
        head = '<div class="marginhead"><button class="indexfold" type="button" aria-expanded="true">'
        for url in ("/1:0", "/144:3", "/i/ice-ages/read", "/i/prayer/read/theme"):
            body = get(url)[2]
            self.assertEqual(body.count(head), 1, url)
        self.assertRegex(get("/1:0")[2], r"<article>\s*" + re.escape(head))
        self.assertNotIn("marginhead", get("/part/4")[2])          # a part's page has no index

    def test_each_box_says_how_many_entries_it_holds(self):
        # Entries, not lines: a group of one headword's entries is one line.
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for url in ("/1:0", "/144:3", "/15:4", "/135:4"):
            body = get(url)[2]
            rows = queries.section(con, *map(int, url[1:].split(":")))
            want = [n for n in (sum(rows["nciters"].get(q["id"], 0) for q in ([r["p"]] if "p" in r else r["lines"]))
                                for r in rows["rows"]) if n]
            got = []
            for a in re.findall(r'<div class="a">(.*?)</div>\s*(?=<p class="t|<div class="(?:verse|stars)"|</div>)',
                                body, re.S):
                if not a:
                    continue
                m = RE_AFOLD.match(a.strip())
                self.assertTrue(m, f"{url}: {a[:80]}")
                self.assertLessEqual(a.count("<li>"), int(m[1]), url)
                self.assertEqual(m[2], "y" if m[1] == "1" else "ies")
                got.append(int(m[1]))
            self.assertEqual(got, want, url)
            b = box(body)
            if b:
                m = RE_AFOLD.match(b.strip())
                heads = ("<h3>Cited across this whole paper</h3>" in b,
                         "<h3>Cited across this whole section</h3>" in b)
                self.assertEqual((int(m[1]), m[3]), (rows["nwhole"], TAILS[heads]), url)

    def test_a_whole_paper_is_cited_once_above_section_0(self):
        b = box(get("/1:0")[2])
        self.assertIn("<h3>Cited across this whole paper</h3>", b)
        self.assertNotIn("<h3>Cited across this whole section</h3>", b)
        self.assertEqual(box_chips(get("/1:0")[2]), ["God", "Universal Father"])
        later = box_chips(get("/1:1")[2])
        self.assertTrue(later)                      # Universal Father › also known as › ...
        self.assertNotIn("God", later)
        self.assertNotIn("Universal Father", later)
        # Both kinds above 133:0, the paper's first, in one box.
        b = box(get("/133:0")[2])
        self.assertLess(b.index("<h3>Cited across this whole paper</h3>"),
                        b.index("<h3>Cited across this whole section</h3>"))
        self.assertEqual(RE_AFOLD.match(b.strip())[3], TAILS[True, True])
        self.assertNotIn("<h3>Cited across this whole paper</h3>", box(get("/133:1")[2]))

    def test_every_paper_wide_entry_stands_above_its_section_0(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        want: dict[int, set] = {}
        for n, path in con.execute(
                "SELECT DISTINCT p.paper_n, e.path_plain FROM para_citers c"
                " JOIN index_entry e ON e.id=c.entry_id JOIN paragraph p ON p.id=c.paragraph_id"
                " WHERE c.precision='paper' AND p.section_n=0" + queries.CHIP_NEW):
            want.setdefault(n, set()).add(path)
        self.assertGreater(len(want), 150)
        for paper, sec in con.execute("SELECT paper_n, n FROM section"):
            rows = queries.section(con, paper, sec)
            got = {r["path"] for r in entries(rows["paperwide"])}
            self.assertEqual(got, want.get(paper, set()) if sec == 0 else set(), f"{paper}:{sec}")
            self.assertFalse(got & {r["path"] for r in entries(rows["blanket"])}, f"{paper}:{sec}")

    def test_each_caption_on_a_reading_path_says_how_many(self):
        for url in ("/i/ice-ages/read", "/i/prayer/read/theme", "/i/thirst/read"):   # thirst: verse
            body = get(url)[2]
            rows = re.findall(r'<div class="row[^"]*">(<button class="afold"[^>]*>(\d+) index entr(?:y|ies)</button>)?'
                              r'(<ul class="cites">.*?</ul>|<div class="cites">.*?</div>)', body, re.S)
            self.assertTrue(rows, url)
            for button, n, cites in rows:
                self.assertTrue(button, f"{url}: a caption without its line")
                self.assertEqual(int(n), cites.count("<li>"), url)


def is_window(c) -> bool:
    return isinstance(c, dict) and bool(c.get("window"))


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class ChronologyWindow(unittest.TestCase):
    """A Chronology event beside the text stands in its window onto Appendix A
    (queries.windows): the event printed just before it, with its citations,
    the event itself, with its words, linking to its line in the appendix, and
    the event just after (Geoff Theiss and Tigran, 2026-10-19).  Events of one
    list that follow each other in the appendix share one window."""

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def windows(self, ref: str) -> list[dict]:
        paper, sec = map(int, ref.split(".")[0].split(":"))
        rows = queries.section(self.con, paper, sec)
        pid = next(p["id"] for p in rows["paras"] if p["ref"] == ref)
        return [c for c in rows["citers"].get(pid, []) if is_window(c)]

    def test_andronover(self):
        m = margin(get("/57:1")[2], "57:1.6")
        before, here, after = (m.index('href="/57:1.4"'),
                               m.index('">875,000,000,000 years ago: Andronover initiated</a>'),
                               m.index('href="/57:2.2"'))
        self.assertLess(before, here)
        self.assertLess(here, after)
        self.assertIn('<a class="here" href="/appendix/A#', m)
        self.assertEqual(RE_AFOLD.search(m)[1], "4")     # entries, not windows

    def test_no_heading(self):
        """A window opens onto its slice of the timeline, under no heading
        (Tigran, 2026-10-20): its dashed rule marks it, and the margin keeps
        the line.  136:2.8 has three windows one after another."""
        self.assertIn('<div class="win"><span class="nb">', margin(get("/57:1")[2], "57:1.6"))
        m = margin(get("/136:2")[2], "136:2.8")
        wins = re.findall(r'<div class="win">(.*?)</div>', m, re.S)
        self.assertEqual(len(wins), 3)
        for w in wins:
            self.assertNotIn('class="lbl"', w)

    def test_where_the_neighbours_are_told_elsewhere(self):
        [w] = self.windows("135:4.1")
        self.assertEqual([e["event"] for e in w["events"]], ["August 17, 22 A.D.: Elizabeth dies"])
        self.assertIn("Jesus left Jerusalem for Rome", w["before"]["label"])
        self.assertIn("Jesus leaves Ganid at Charax", w["after"]["label"])

    def test_a_run_is_one_window(self):
        self.assertEqual([len(w["events"]) for w in self.windows("121:8.8")], [3])
        self.assertEqual([len(w["events"]) for w in self.windows("122:8.7")], [1, 2])

    def test_the_ends_of_the_appendix(self):
        last = self.con.execute("SELECT MAX(ord) FROM chronology_event").fetchone()[0]
        for ord_, side in ((1, "before"), (last, "after")):
            ref = self.con.execute(
                "SELECT p.ref FROM chronology_event v JOIN citation_target t ON t.entry_id=v.entry_id"
                " JOIN paragraph p ON p.id=t.paragraph_id WHERE v.ord=? AND t.opens", (ord_,)).fetchone()[0]
            [w] = [w for w in self.windows(ref) if any(e["ev_ord"] == ord_ for e in w["events"])]
            self.assertIsNone(w[side], f"{ref}: nothing stands {side} the appendix's {side} event")

    def test_appendices_first(self):
        """In every margin and box the appendices stand first, the Chronology
        before B-F, then the A-Z (Tigran, 2026-10-19): 121:8.8's window stood
        after "Acts, Book of" by an accident of numbering until then."""
        rank = {"A": 0, "az": 2}
        for paper, sec in self.con.execute("SELECT paper_n, n FROM section"):
            rows = queries.section(self.con, paper, sec)
            for items in [*rows["citers"].values(), rows["paperwide"], rows["blanket"]]:
                r = [0 if is_window(c) else 2 if isinstance(c, dict) else rank.get(c["scope"], 1)
                     for c in items]
                self.assertEqual(r, sorted(r), f"{paper}:{sec}")
        m = margin(get("/121:8")[2], "121:8.8")
        self.assertLess(m.index('<div class="win">'), m.index("Acts, Book of"))

    def test_a_section_box(self):
        b = box(get("/127:2")[2])
        self.assertIn('<div class="win">', b)
        self.assertIn(">11 A.D.: Jesus declines to join Zealots</a>", b)

    def test_every_window(self):
        """Every event beside the text is in a window; a window's neighbours
        are the events either side of it in the appendix, neither of them
        beside the same paragraph; and a fold counts entries, not windows."""
        secs = self.con.execute(
            "SELECT DISTINCT t.paper, COALESCE(t.section, 0) FROM chronology_event v"
            " JOIN citation_target t ON t.entry_id=v.entry_id").fetchall()
        self.assertGreater(len(secs), 200)
        n = 0
        for paper, sec in secs:
            rows = queries.section(self.con, paper, sec)
            lists = list(rows["citers"].items()) + [("box", rows["paperwide"] + rows["blanket"])]
            for pid, items in lists:
                where = f"{paper}:{sec} {pid}"
                self.assertFalse([c for c in items if not isinstance(c, dict) and c["ev_ord"] is not None],
                                 where)
                here = {e["ev_ord"] for w in items if is_window(w) for e in w["events"]}
                for w in filter(is_window, items):
                    n += 1
                    o = [e["ev_ord"] for e in w["events"]]
                    self.assertEqual(o, list(range(o[0], o[0] + len(o))), where)
                    for side, k in (("before", o[0] - 1), ("after", o[-1] + 1)):
                        if w[side] is not None:
                            self.assertEqual(w[side]["ord"], k, where)
                            self.assertNotIn(k, here, where)
                if pid != "box":
                    self.assertEqual(rows["nciters"][pid], len(entries(items)), where)
            self.assertEqual(rows["nwhole"], len(entries(rows["paperwide"] + rows["blanket"])))
        self.assertGreater(n, 400)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Together(unittest.TestCase):
    """Entries of one headword beside one paragraph stand together, run on:
    the part they share said once, as deep as they share it, linking to its
    own line, then each entry's own words, linking to theirs, separated by
    semicolons (queries.groups; Geoff Theiss and Tigran, 2026-10-19)."""

    def items(self, body: str, ref: str) -> list[str]:
        return [re.sub(r"<[^>]+>", "", li) for li in re.findall(r"<li>(.*?)</li>", margin(body, ref), re.S)]

    def test_elijah_and_john(self):
        body = get("/135:4")[2]
        self.assertEqual(self.items(body, "135:4.2")[:2], [
            "Elijah (Prophet) › John the Baptist › adopted dress and method of Elijah;"
            " held back 2 years by expectation of return of",
            "John the Baptist › presented flock to Nazarites; religion of repentance,"
            " self-examination, and self-denial"])
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        head = con.execute(
            "SELECT e.anchor FROM index_entry e JOIN index_entry r ON r.id=e.root_id"
            " WHERE r.slug='elijah-prophet' AND e.path_plain='Elijah (Prophet) › John the Baptist'").fetchone()[0]
        self.assertIn(f'<span class="grp"><a href="/i/elijah-prophet#{head}">Elijah (Prophet) › John the Baptist</a> ›',
                      margin(body, "135:4.2"))

    def test_a_headword_shared(self):
        m = margin(get("/57:1")[2], "57:1.6")
        self.assertIn('<a href="/i/andronover-nebula">Andronover nebula</a> ›', m)
        self.assertIn("Andronover nebula › initiated 875 billion years ago; nebula #876,926",
                      self.items(get("/57:1")[2], "57:1.6"))

    def test_every_list(self):
        """No list holds two items of one headword, and every entry beside a
        paragraph is still linked to its own line, as a tail or as the head."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        n = 0
        for paper, sec in con.execute("SELECT paper_n, n FROM section"):
            rows = queries.section(con, paper, sec)
            for items in [*rows["citers"].values(), rows["paperwide"], rows["blanket"]]:
                roots = [c["root"] if not isinstance(c, dict) else c["entries"][0]["root"]
                         for c in items if not (isinstance(c, dict) and c.get("window"))
                         and (isinstance(c, dict) or c["scope"] == "az")]
                self.assertEqual(len(roots), len(set(roots)), f"{paper}:{sec}")
                for g in items:
                    if not (isinstance(g, dict) and g.get("group")):
                        continue
                    n += 1
                    linked = {g["head"]["anchor"]} | {t["anchor"] for t in g["tails"]}
                    for e in g["entries"]:
                        self.assertIn(e["anchor"], linked, f"{paper}:{sec} {e['path']}")
                        self.assertTrue(e["path"].startswith(g["head"]["label"]), e["path"])
        self.assertGreater(n, 3000)


if __name__ == "__main__":
    unittest.main()
