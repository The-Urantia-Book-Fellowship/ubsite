"""Verse is set as the book sets it.

The press sets the psalm in 48:6, the song in 122:9, the Lord's Prayer in 144:3
and the seven prayers of 144:5 in quoting blocks, one line to a paragraph, and
sets in four lines of the Lord's Prayer with \\hsetoff.  The reader keeps each
block's first line (verse_start) and the set-in lines (setoff); the section
page indents each block as one and gathers the entries citing its lines beside
it.  Proved on throwaway files for the reader's cases, then on the built
database and the section page (skipped when var/ub.db has not been built).
"""

import pathlib
import re
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.problems import Report  # noqa: E402
from build.readers.press import read_paper  # noqa: E402
from test_appendix_pages import DB, get  # noqa: E402

HEAD = "\\upaper{144}{At Gilboa and in the Decapolis}\n\\author{A Midwayer}\n"
OPEN = "\\begin{quoting}[vskip=\\baselineskip,leftmargin=4ex,rightmargin=2ex]\n"


def read(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "p144.tex"
        path.write_text(HEAD + body, encoding="utf-8")
        report = Report()
        paper = read_paper(path, report)
    lines = {q.ref: (q.src != "vs", q.verse_start, q.setoff, q.ex.text) for q in paper.paragraphs}
    return lines, [p.code for p in report.problems if p.severity != "warn"]


class Reader(unittest.TestCase):
    def test_a_block_and_its_set_in_line(self):
        lines, problems = read(
            "\\vs p144 3:2 Before.\n" + OPEN +
            "\\hspace*{-1.2em}\\printvssuper{3}\nOur Father who is in heaven,\\par\n"
            "\\hsetoff Hallowed be your name.\\par\n\\end{quoting}\n\\vs p144 3:5 After.\n")
        self.assertEqual(lines, {
            "144:3.2": (False, False, False, "Before."),
            "144:3.3": (True, True, False, "Our Father who is in heaven,"),
            "144:3.4": (True, False, True, "Hallowed be your name."),
            "144:3.5": (False, False, False, "After.")})
        self.assertEqual(problems, [])

    def test_each_block_begins_anew(self):
        lines, _ = read(OPEN + "\\printvssuper{1}\nOne.\\par\nTwo.\\par\n\\end{quoting}\n"
                        "\\separatorshort\n" + OPEN + "\\printvssuper{3}\nThree.\\par\n"
                        "\\end{quoting}\n")
        self.assertEqual({r: v[1] for r, v in lines.items()},
                         {"144:0.1": True, "144:0.2": False, "144:0.3": True})

    def test_an_hsetoff_elsewhere_fails(self):
        _, problems = read("\\vs p144 3:2 Before \\hsetoff after.\n")
        self.assertEqual(problems, ["hsetoff-unplaced"])
        _, problems = read(OPEN + "\\printvssuper{3}\nOne \\hsetoff two.\\par\n\\end{quoting}\n")
        self.assertEqual(problems, ["hsetoff-unplaced"])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Built(unittest.TestCase):
    def test_the_ten_blocks_and_the_four_lines(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        starts = [r for (r,) in con.execute(
            "SELECT ref FROM paragraph WHERE verse_start ORDER BY ord")]
        self.assertEqual(starts, ["48:6.9", "122:9.5", "144:3.3", "144:5.2", "144:5.11",
                                  "144:5.24", "144:5.36", "144:5.51", "144:5.69", "144:5.82"])
        setoff = {r for (r,) in con.execute("SELECT ref FROM paragraph WHERE setoff")}
        self.assertEqual(setoff, {"144:3.4", "144:3.6", "144:3.8", "144:3.10"})

    def test_the_section_page_sets_a_block_as_one(self):
        status, _, body = get("/144:3")
        self.assertEqual(status, 200)
        blocks = re.findall(r'<div class="verse">(.*?)</div>', body, re.S)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(re.findall(r'id="(144:3\.\d+)"', blocks[0]),
                         [f"144:3.{n}" for n in range(3, 13)])
        self.assertEqual(len(re.findall(r'class="t verse setoff', blocks[0])), 4)
        # Its lines' entries beside it, each line's under its reference, and no
        # "no entry cites" for a line.
        side = body[body.index('<div class="verse">'):body.index('id="144:3.13"')]
        self.assertEqual(re.findall(r'<p class="at"><a href="/(144:3\.\d+)">', side),
                         ["144:3.6", "144:3.9", "144:3.10"])
        self.assertNotIn("no entry cites this paragraph", side)
        status, _, body = get("/144:5")
        self.assertEqual(len(re.findall(r'<div class="verse">', body)), 7)
        self.assertRegex(body, r'data-stars="\* \* \*"></div>\s*<div class="verse">\s*'
                               r'<p class="t verse"\s+id="144:5\.11">')


if __name__ == "__main__":
    unittest.main()
