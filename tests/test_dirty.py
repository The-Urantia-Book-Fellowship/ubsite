"""A dirty build is refused by deploy.sh unless asked for (Tigran, 2026-10-18).

What counts as dirty (build/config.py _dirty): a tracked file anywhere with
uncommitted changes, or an untracked file under tex/, which the reader globs;
an untracked file elsewhere is not an input.  `python -m build dirty <db>`
says whether a built database was dirty, as its build_source records, with
3 for dirty, so that a failure (1) is never taken for one.  Proved on a
throwaway repository, so the press repository is never touched.
"""

import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import config  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                           "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout


class Dirty(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name)
        git(self.repo, "init", "-q")
        (self.repo / "tex").mkdir()
        (self.repo / "tools").mkdir()
        for name in ("tex/p001.tex", "tools/build.py"):
            path = self.repo / name
            path.write_text("one\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "first")

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        return config._dirty(self.repo, "tex"), config.dirty_files(self.repo, "tex")

    def test_clean(self):
        self.assertEqual(self.state(), (False, []))

    def test_an_untracked_file_elsewhere_is_not_an_input(self):
        path = self.repo / "tools" / "Lakeside.txt"
        path.write_text("x\n")
        self.assertEqual(self.state(), (False, []))

    def test_a_new_file_under_tex_is(self):
        path = self.repo / "tex" / "p002.tex"
        path.write_text("x\n")
        self.assertEqual(self.state(), (True, ["?? tex/p002.tex"]))

    def test_any_changed_tracked_file_is(self):
        for name in ("tex/p001.tex", "tools/build.py"):
            path = self.repo / name
            path.write_text("two\n")
        self.assertEqual(self.state(), (True, [" M tex/p001.tex", " M tools/build.py"]))


class Command(unittest.TestCase):
    """`python -m build dirty <db>`: 3 and the source for a dirty build, 0 for a clean one."""

    def run_on(self, dirty: int):
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "ub.db"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE build_source (repo TEXT, dirty INTEGER)")
                con.executemany("INSERT INTO build_source VALUES (?, ?)", [("press", dirty), ("index", 0)])
            con.close()
            return subprocess.run([sys.executable, "-m", "build", "dirty", str(db)], cwd=ROOT,
                                  capture_output=True, text=True)

    def test_clean(self):
        out = self.run_on(0)
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_dirty(self):
        out = self.run_on(1)
        self.assertEqual(out.returncode, 3)
        self.assertTrue(out.stdout.startswith("  press, "), out.stdout)


if __name__ == "__main__":
    unittest.main()
