"""A separator between two paragraphs is kept, and shown.

The press sets eleven: `\\separatorline` (five stars) before the closing notes of
Parts I-III, `\\separatorshort` (three) in 120:3, 134:6 and six times in 144:5.
Until 2026-10-12 the reader skipped them as layout and the site showed none.
Proved on throwaway files for the reader's cases, then on the built database
and the section page (skipped when var/ub.db has not been built).
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

HEAD = "\\upaper{134}{The Transition Years}\n\\author{A Midwayer}\n"


def read(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "p134.tex"
        path.write_text(HEAD + body, encoding="utf-8")
        report = Report()
        paper = read_paper(path, report)
    seps = {q.ref: q.sep_before for q in paper.paragraphs}
    return seps, [p.code for p in report.problems if p.severity != "warn"]


class Reader(unittest.TestCase):
    def test_each_kind_goes_on_the_paragraph_after_it(self):
        seps, problems = read("\\vs p134 6:13 Before.\n\\separatorshort[\\bodybaselineskip]\n"
                              "\\vs p134 6:14 After.\n\\separatorline\n\\vs p134 6:15 Last.\n")
        self.assertEqual(seps, {"134:6.13": None, "134:6.14": "* * *", "134:6.15": "* * * * *"})
        self.assertEqual(problems, [])

    def test_a_verse_after_it_takes_it(self):
        seps, problems = read("\\vs p134 6:13 Before.\n\\separatorshort\n"
                              "\\begin{quoting}\n\\printvssuper{14}A line.\\par\n\\end{quoting}\n")
        self.assertEqual(seps, {"134:6.13": None, "134:6.14": "* * *"})
        self.assertEqual(problems, [])

    def test_an_unknown_separator_fails(self):
        _, problems = read("\\vs p134 6:13 Before.\n\\separatorfancy\n\\vs p134 6:14 After.\n")
        self.assertEqual(problems, ["unknown-separator"])

    def test_two_in_a_row_fail(self):
        _, problems = read("\\separatorshort\n\\separatorline\n\\vs p134 6:14 After.\n")
        self.assertEqual(problems, ["separator-twice"])

    def test_one_with_nothing_after_it_fails(self):
        _, problems = read("\\vs p134 6:13 Before.\n\\separatorshort\n")
        self.assertEqual(problems, ["separator-at-end"])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Built(unittest.TestCase):
    def test_the_eleven(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        got = dict(con.execute("SELECT ref, sep_before FROM paragraph"
                               " WHERE sep_before IS NOT NULL"))
        five, three = "* * * * *", "* * *"
        self.assertEqual(got, {
            "31:10.22": five, "56:10.23": five, "119:8.9": five,
            "120:3.12": three, "134:6.14": three,
            **{f"144:5.{n}": three for n in (11, 24, 36, 51, 69, 82)}})

    def test_the_section_page_draws_it_before_its_paragraph(self):
        status, _, body = get("/134:6")
        self.assertEqual(status, 200)
        self.assertRegex(body, r'<div class="stars" role="separator" data-stars="\* \* \*">'
                               r'</div>\s*<p class="t"\s+id="134:6\.14">')
        self.assertEqual(len(re.findall(r'class="stars"', body)), 1)
        status, _, body = get("/144:5")
        self.assertEqual(len(re.findall(r'class="stars"', body)), 6)


if __name__ == "__main__":
    unittest.main()
