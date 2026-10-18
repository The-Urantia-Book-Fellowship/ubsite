"""ChangeLog.md: what changed, for readers and for developers, in one file.

Its entries for readers are the site's What's new (offline/news.py), and the
whole file below its first `##` is the page /changelog (build/changelog.py),
so the file must read as both read it; a release is a version in it and a tag
`vX.Y.Z` on main, each with the other (Tigran, 2026-10-18).
"""

import datetime
import html
import pathlib
import re
import sqlite3
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from offline import news  # noqa: E402
from build import changelog  # noqa: E402
from test_appendix_pages import DB, get  # noqa: E402

CHANGELOG = changelog.CHANGELOG

RE_VERSION = re.compile(r"^## \[(Unreleased|(\d+)\.(\d+)\.(\d+))\](?: - (\d{4}-\d\d-\d\d))?$")


class ChangeLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = news.CHANGELOG.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def test_news_can_read_it(self):
        news.entries(self.text)   # raises on what What's new could not show

    def test_versions(self):
        versions = [RE_VERSION.match(l) for l in self.lines if l.startswith("## [")]
        self.assertTrue(all(versions), "a version heading out of form")
        self.assertEqual(versions[0][1], "Unreleased")
        self.assertIsNone(versions[0][5], "Unreleased has no date")
        released = [(tuple(map(int, m.group(2, 3, 4))), m[5]) for m in versions[1:]]
        self.assertTrue(all(d for _, d in released), "a release without its date")
        self.assertEqual(released, sorted(released, reverse=True), "versions not newest first")
        self.assertEqual(len({v for v, _ in released}), len(released))
        try:
            tags = subprocess.run(["git", "-C", str(ROOT), "tag", "--list", "v*"],
                                  capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git")
        self.assertEqual(sorted(f"v{a}.{b}.{c}" for (a, b, c), _ in released), sorted(tags))

    def test_one_line_to_a_paragraph(self):
        # Read full width (Obsidian, MarkText): never wrapped by hand.
        for i in range(1, len(self.lines)):
            a, b = self.lines[i - 1], self.lines[i]
            if a.strip() and b.strip() and not a.startswith("#") and not b.startswith("- "):
                self.fail(f"ChangeLog.md:{i + 1} continues the line before it")

    def test_whats_new_is_the_entries_for_readers(self):
        n = news.news()
        if not n["items"]:
            self.skipTest("no git")
        ours = {w for _, w in news.entries(self.text)}
        for x in n["items"]:
            self.assertEqual(set(x), {"t", "d", "s"})
        # Never what is for developers, nor where the file began.
        beyond = [l[2:].strip() for l in self.lines if l.startswith("- ")]
        self.assertFalse({x["s"] for x in n["items"]} & (set(beyond) - ours))


class Page(unittest.TestCase):
    """/changelog: the file as written, and nothing else but each entry's date."""

    def test_every_line_is_parsed(self):
        # Every non-blank line is a block the page shows: none is dropped unseen.
        text = CHANGELOG.read_text(encoding="utf-8")
        shown = {x.line for x in changelog.parse(text)}
        for i, l in enumerate(text.splitlines(), 1):
            if l.strip():
                self.assertIn(i, shown, f"ChangeLog.md:{i} is not on the page")

    def test_markdown(self):
        self.assertEqual(changelog.inline("`a<b` and *The Urantia Book*, [here](/api) & **so**"),
                         '<code>a&lt;b</code> and <i>The Urantia Book</i>, <a href="/api">here</a>'
                         ' &amp; <strong>so</strong>')
        # Goudy draws a straight " as a closing quote: curled, but never in code.
        self.assertEqual(changelog.inline('The README\'s "Updating the site" (`"x"`)'),
                         'The README’s “Updating the site” (<code>"x"</code>)')
        # A bare URL is a link, without the full stop after it.
        self.assertEqual(changelog.inline("at https://ubsite.ddns.net."),
                         'at <a href="https://ubsite.ddns.net">https://ubsite.ddns.net</a>.')
        for bad in ("a `b", "an *open", "[a link](", "a ] b"):
            with self.assertRaises(ValueError, msg=bad):
                changelog.inline(bad)

    def test_a_release_names_its_day(self):
        h = changelog.parse("## [1.0.0] - 2026-10-30\n\n### Fixed\n\n- A fix.\n")[0]
        self.assertEqual((h.kind, h.version, h.released, h.words),
                         ("h2", "1.0.0", "2026-10-30", "1.0.0 \u2013 October 30, 2026"))

    def test_refuses_what_it_cannot_place(self):
        for text in ("## [Unreleased]\n\n- an entry under no heading\n",
                     "## [Unreleased]\n\n### Changed\n\nA paragraph in a version.\n",
                     "## [Unreleased]\n\n### Improved\n\n- not a heading of Keep a Changelog\n",
                     "## [Unreleased]\n\n### Fixed\n\n- Markdown for readers: `code`\n",
                     "## Began\n\n- an entry above every heading\n"):
            with self.assertRaises(ValueError, msg=text):
                changelog.parse(text)

    @unittest.skipUnless(DB.exists(), "var/ub.db not built")
    def test_the_page_is_the_file(self):
        status, _, body = get("/changelog")
        self.assertEqual(status, 200)
        main = body[body.index("<main"):body.index("</main>")]
        lines = changelog.parse(CHANGELOG.read_text(encoding="utf-8"))
        with sqlite3.connect(DB) as con:
            rows = con.execute("SELECT line, text, version, kind, written FROM changelog ORDER BY line").fetchall()
        self.assertEqual([r[0] for r in rows], [x.line for x in lines], "var/ub.db is older than ChangeLog.md")
        # Each entry in a version carries the day it was written, in the American order.
        days = re.findall(r'<small class="day">([^<]*)</small>', main)
        dated = [r for r in rows if r[2] and r[3] == "entry"]
        self.assertEqual(len(days), len(dated))
        for d, r in zip(days, dated):
            self.assertEqual(datetime.datetime.strptime(d, "%B %d, %Y").date().isoformat(), r[4])
        # Its words are the file's, block by block, in order, and nothing more;
        # spaces aside, which the markup between blocks adds.
        words = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r'<small class="day">[^<]*</small>', "", main)))
        words = re.sub(r"\s+", "", words)
        at = 0
        for line, text, *_ in rows:
            text = re.sub(r"\s+", "", text)
            i = words.find(text, at)
            self.assertGreaterEqual(i, 0, f"ChangeLog.md:{line} is not on the page, in its place")
            self.assertEqual(words[at:i].strip(), "", f"words the file does not have: {words[at:i].strip()!r}")
            at = i + len(text)
        self.assertEqual(words[at:].strip(), "")

    @unittest.skipUnless(DB.exists(), "var/ub.db not built")
    def test_every_page_links_it(self):
        for url in ("/", "/101:4", "/changelog"):
            _, _, body = get(url)
            self.assertIn('<a href="/changelog">Changelog</a>', body[body.rindex("<footer>"):], url)


if __name__ == "__main__":
    unittest.main()
