"""Uncommitted index work cannot reach the site.

The index is edited in another session, and the build reads it at a commit,
not from the working tree.  Before read_tex the readers read the working tree
while sources.toml and the build both said HEAD: an edit in progress would have
shipped under a clean commit id, and the footer would have named that commit.
Proved here on a throwaway repository, so ../index is never touched.
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.readers._io import read_tex  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                           "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class ReadTex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name)
        git(self.repo, "init", "-q")
        self.tex = self.repo / "tex"
        self.tex.mkdir()
        (self.tex / "idx-k.tex").write_text("\\iB{committed \\cit{2:5.12}}\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "v1")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        # The other session's edit in progress: in the worktree, not committed.
        (self.tex / "idx-k.tex").write_text("\\iB{half-edited — ’}\n", encoding="utf-8")
        (self.tex / "idx-z.tex").write_text("untracked\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_commit_ignores_the_worktree(self):
        self.assertEqual(read_tex(self.tex, "idx-k.tex", self.commit),
                         "\\iB{committed \\cit{2:5.12}}\n")

    def test_worktree_reads_the_worktree(self):
        self.assertEqual(read_tex(self.tex, "idx-k.tex"), "\\iB{half-edited — ’}\n")

    def test_absent_at_the_commit_is_none(self):
        self.assertIsNone(read_tex(self.tex, "idx-z.tex", self.commit))
        self.assertIsNone(read_tex(self.tex, "idx-q.tex", self.commit))
        self.assertIsNone(read_tex(self.tex, "idx-q.tex"))

    def test_utf8_at_a_commit(self):
        git(self.repo, "commit", "-qam", "v2")
        self.assertEqual(read_tex(self.tex, "idx-k.tex", git(self.repo, "rev-parse", "HEAD")),
                         "\\iB{half-edited — ’}\n")


if __name__ == "__main__":
    unittest.main()
