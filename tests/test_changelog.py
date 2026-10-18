"""ChangeLog.md: what changed, for readers and for developers, in one file.

Its entries for readers are the site's What's new (offline/news.py), so the
file must read as news.py reads it; a release is a version in it and a tag
`vX.Y.Z` on main, each with the other (Tigran, 2026-10-18).
"""

import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from offline import news  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
