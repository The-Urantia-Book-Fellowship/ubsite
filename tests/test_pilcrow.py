"""A pilcrow the press source took out for its own page is given back.

48:6.20 follows a verse block, and the press project removed its \\pc to avoid
a doubled space there, recording the fact in a comment on the line before
(build/readers/press.py, RE_PC_REMOVED).  The blank line is the 1955
printing's, so the site marks it.  Proved on throwaway files for the reader's
three cases, then on the built database for 48:6.20 itself (skipped when
var/ub.db has not been built).
"""

import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB = ROOT / "var" / "ub.db"

from build.problems import Report  # noqa: E402
from build.readers.press import read_paper  # noqa: E402

HEAD = "\\upaper{48}{The Morontia Life}\n\\author{A Mighty Messenger}\n"
COMMENT = "\\end{quoting}% The \\pc at 48:6.20 has been removed to avoid double-line vskip\n"


def read(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "p048.tex"
        path.write_text(HEAD + body, encoding="utf-8")
        report = Report()
        paper = read_paper(path, report)
    gaps = {q.ref: q.ex.flags.get("gap_before", 0.0) for q in paper.paragraphs}
    return gaps, [p.code for p in report.problems]


class Reader(unittest.TestCase):
    def test_the_comment_gives_the_pilcrow_back(self):
        gaps, problems = read("\\vs p048 6:19 Before.\n" + COMMENT +
                              "\\vs p048 6:20 That is the story.\n\\vs p048 6:21 After.\n")
        self.assertEqual(gaps, {"48:6.19": 0.0, "48:6.20": 1.0, "48:6.21": 0.0})
        self.assertEqual(problems, [])

    def test_a_pilcrow_put_back_upstream_makes_the_comment_stale(self):
        _, problems = read(COMMENT + "\\pc \\vs p048 6:20 That is the story.\n")
        self.assertEqual(problems, ["pc-restore-stale"])

    def test_a_comment_naming_no_paragraph_fails(self):
        _, problems = read(COMMENT + "\\vs p048 6:21 After.\n")
        self.assertEqual(problems, ["pc-restore-nowhere"])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Built(unittest.TestCase):
    def test_48_6_20_carries_its_pilcrow(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        (gap,) = con.execute("SELECT gap_before FROM paragraph WHERE ref = '48:6.20'").fetchone()
        self.assertEqual(gap, 1.0)


if __name__ == "__main__":
    unittest.main()
