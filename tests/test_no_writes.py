"""Prove that no module can write to a source repository.

This is not a style check.  The three sibling repos are the masters for a print
edition; a stray write is not a bug that shows up in a test run, it is damage to
someone's book.  So the guarantee is mechanical: exactly one module may open a
source path, and it may only ever open it for reading.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Modules permitted a write-mode open, each with the file it writes and why.
# The guard exists to keep ubsite out of the SOURCE repos, not to forbid it its
# own directory -- so an entry here must also pass test_allowed_targets_are_ours.
ALLOWED = {
    "build/readers/_io.py": None,                  # reads only; asserted below
    "build/slugs.py": "data/slugs.tsv",            # the append-only slug ledger
    "build/versions.py": "data/text/",             # the append-only text-version ledger
    "build/vendorlib.py": "vendor/",               # the vendored copies + lock
    "build/fonts.py": "ubsite/static/fonts/",      # the UB Goudy subset (fontTools)
    "offline/pack.py": "var/offline/",             # the offline copy, by way of a .tmp
    "tools/study/draft.py": "var/study/",          # a paper's notes drafted for review
    "tools/quiz/draft.py": "var/quiz/",            # a paper's quiz drafted for review
    "tools/quiz/apply.py": "data/quiz/questions.tsv",  # the quiz's ledger, by ruling
    "tools/quiz/doubt.py": "var/quiz/",            # the references in doubt, for ruling
    "build/cli.py": "var/",                        # ub.db, built as ub.db.tmp and swapped in
    "build/db.py": "var/",                         # a database built afresh, the old one removed
    "build/oracle.py": "var/",                     # the oracles' sandboxes, their inputs linked in
}


class _WriteOpen:
    """A call to open() or a path's .open() that can write: a mode with w, a,
    x or +, given as a literal anywhere among its arguments, or os.open's
    flags.  Until 2026-11-09 a pattern read only up to the call's first ")"
    and took "w" and "a" alone: "wb", "r+", mode="wt", p.open("wb") and
    open(str(p), "w") went by unseen (review of 2026-11-09)."""

    CALL = re.compile(r"(?<![\w.])open\s*\(|\.open\s*\(")
    LITERAL = re.compile(r"""(['"])(.*?)\1""")
    MODE = re.compile(r"[rwxabt+U]{1,4}")
    FLAGS = re.compile(r"\bos\.O_(?:WRONLY|RDWR|CREAT|TRUNC|APPEND)\b")

    def finditer(self, src: str):
        for m in self.CALL.finditer(src):
            depth, i = 1, m.end()
            while i < len(src) and depth:
                depth += {"(": 1, ")": -1}.get(src[i], 0)
                i += 1
            args = src[m.end():i - 1]
            modes = [x.group(2) for x in self.LITERAL.finditer(args) if self.MODE.fullmatch(x.group(2))]
            if any(set(x) & set("wax+") for x in modes) or self.FLAGS.search(args):
                yield _Hit(m.start(), src[m.start():i])

    def findall(self, src: str) -> list[str]:
        return [h.group(0) for h in self.finditer(src)]


class _Hit:
    def __init__(self, start: int, text: str):
        self._start, self._text = start, text

    def start(self) -> int:
        return self._start

    def end(self) -> int:
        return self._start + len(self._text)

    def group(self, n: int = 0) -> str:
        return self._text


WRITE_OPEN = _WriteOpen()
# What moves, deletes or writes a file without open(): a Path's .replace(x) and
# .rename(x) take one argument, where str.replace takes two.
WRITERS = re.compile(r"\b(os\.remove|os\.unlink|os\.rename|os\.replace|os\.symlink|shutil\.(?:rmtree|move|copy\w*)"
                     r"|Path\.write_(?:text|bytes)|\.write_text\(|\.write_bytes\(|\.unlink\(|\.symlink_to\("
                     r"|\.touch\(|\.(?:replace|rename)\([^,()]+\))")

# Paths this project is allowed to write to.
OWN = ("var/", "export/", "data/", "vendor/", "build/cache/", "tests/fixtures/")


class NoWrites(unittest.TestCase):
    def _sources(self):
        # build/ reads the masters; offline/ only the database, and is held
        # to the same rule so that it never grows a reason to.
        # tools/study/ reads the study edition and Block's charts, tools/quiz/
        # the edition's quiz.
        for d in ("build", "offline", "tools/study", "tools/quiz"):
            for p in (ROOT / d).rglob("*.py"):
                yield p.relative_to(ROOT).as_posix(), p.read_text()

    def test_only_io_opens_for_write(self):
        offenders = []
        for rel, src in self._sources():
            if rel in ALLOWED:
                continue
            for m in WRITE_OPEN.finditer(src):
                line = src[:m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line}  {m.group(0)}")
            # Nor any other way of writing, moving or deleting a file
            # (2026-11-09: build/ was held to open() alone).
            for m in WRITERS.finditer(src):
                line = src[:m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line}  {m.group(0)}")
        self.assertEqual(offenders, [], "a write outside the IO chokepoint and the writers allowed:\n"
                                        + "\n".join(offenders))

    def test_the_pattern_sees_every_mode(self):
        for src in ('open(p, "w")', "open(p, 'a')", 'open(p, "wb")', 'open(p, "ab")', 'open(p, "xb")',
                    'open(p, "r+")', 'open(p, "rb+")', 'open(p, "w+b")', 'open(p, mode="wt")',
                    'p.open("wb")', 'open(str(p), "w")', 'open(f(a, b), "a", encoding="utf-8")',
                    "os.open(p, os.O_WRONLY | os.O_CREAT)"):
            self.assertTrue(WRITE_OPEN.findall(src), src)
        for src in ('open(p)', 'open(p, "r")', 'open(p, "rb")', 'p.open()', 'open(str(p), encoding="utf-8")',
                    'reopen(p, "w")', 'webbrowser.open_new(x)'):
            self.assertFalse(WRITE_OPEN.findall(src), src)
        for src in ("tmp.replace(out)", "p.rename(q)", "link.symlink_to(t)", "p.touch()"):
            self.assertRegex(src, WRITERS)
        self.assertNotRegex('s.replace("a", "b")', WRITERS)

    def test_io_module_never_writes(self):
        src = (ROOT / "build/readers/_io.py").read_text()
        self.assertEqual(WRITE_OPEN.findall(src), [], "_io.py must never open for writing")
        self.assertNotRegex(src, WRITERS, "_io.py must never mutate the filesystem")

    def test_allowed_targets_are_ours(self):
        """Every allowlisted writer must target a path inside this project."""
        import subprocess
        for rel, target in ALLOWED.items():
            if target is None:
                continue
            here = (ROOT / target).resolve()
            self.assertTrue(str(here).startswith(str(ROOT.resolve()) + "/"),
                            f"{rel} writes outside the project: {here}")

    def test_no_writer_targets_the_foundation_s_releases(self):
        """data/uf/ holds the Foundation's zips, a master like the repos though
        it lies inside the project (sources.toml): no allowlisted writer may
        target it, nor data/ whole."""
        for rel, target in ALLOWED.items():
            if target is None:
                continue
            here = (ROOT / target).resolve()
            self.assertNotEqual(here, (ROOT / "data").resolve(), f"{rel} writes into data/ whole")
            self.assertFalse(str(here).startswith(str((ROOT / "data" / "uf").resolve())),
                             f"{rel} writes into data/uf/: {target}")

    def test_offline_writes_only_var(self):
        """The offline copy is written by pack.py alone, into var/offline/, which
        it builds as var/offline.tmp/ and swaps in."""
        src = (ROOT / "offline/pack.py").read_text()
        writes = sorted(set(re.findall(WRITERS, src)))
        self.assertEqual(writes, [".write_bytes(", "os.replace", "shutil.rmtree"],
                         f"offline/pack.py writes: {writes}")
        self.assertIn('OUT = ROOT / "var" / "offline"', src)
        for rel, other in self._sources():
            if rel.startswith("offline/") and rel != "offline/pack.py":
                self.assertNotRegex(other, WRITERS, f"{rel} must not write; pack.py does")
                self.assertEqual(WRITE_OPEN.findall(other), [], f"{rel} must not write; pack.py does")

    def test_study_tools_write_only_var(self):
        """A draft goes to var/study/, never data/study/, where the reviewed
        copies are: a re-draft must not overwrite a review.  And pdftotext is
        always given `-`, or it writes NNN.txt beside the chart, in a master."""
        for rel, src in self._sources():
            if not rel.startswith("tools/study/"):
                continue
            self.assertNotRegex(src, WRITERS, f"{rel} must not move or delete files")
            if rel == "tools/study/draft.py":
                self.assertIn('OUT = ROOT / "var" / "study"', src)
                self.assertNotIn('"data"', src)
            else:
                self.assertEqual(WRITE_OPEN.findall(src), [], f"{rel} must not write")
        block = (ROOT / "tools/study/block.py").read_text()
        self.assertIn('["pdftotext", *args, str(pdf), "-"]', block)
        self.assertEqual(block.count("subprocess.run("), 1)

    def test_quiz_tools_write_only_their_own(self):
        """The quiz's draft goes to var/quiz/ and never overwrites a review,
        which holds Tigran's rulings; the ledger is written by apply.py alone,
        by way of a .tmp, and nothing in tools/quiz/ deletes."""
        for rel, src in self._sources():
            if not rel.startswith("tools/quiz/"):
                continue
            self.assertNotRegex(src, r"\.unlink\(|shutil\.|os\.remove", f"{rel} must not delete")
            if rel == "tools/quiz/draft.py":
                self.assertIn('OUT = ROOT / "var" / "quiz"', src)
                self.assertIn("if out.exists():", src)
                self.assertNotIn('"data"', src)
            elif rel == "tools/quiz/apply.py":
                self.assertIn('LEDGER = ROOT / "data" / "quiz" / "questions.tsv"', src)
                self.assertEqual(len(WRITE_OPEN.findall(src)), 1, "apply.py writes the ledger once")
            elif rel == "tools/quiz/doubt.py":
                self.assertIn('OUT = ROOT / "var" / "quiz"', src)
                self.assertIn("if out.exists():", src)
                self.assertNotIn('"data"', src)
            else:
                self.assertEqual(WRITE_OPEN.findall(src), [], f"{rel} must not write")

    def _everything(self):
        # Every module of the project, the tools for the audio, the hyphens and
        # the rest among them, which name the recordings and the press too.
        for d in ("build", "offline", "tools", "ubsite"):
            for p in (ROOT / d).rglob("*.py"):
                yield p.relative_to(ROOT).as_posix(), p.read_text()

    def test_no_writer_names_a_sibling(self):
        """No module may name a sibling repo path in a write context: an open()
        that writes, or anything else that writes, moves or deletes."""
        for rel, src in self._everything():
            # The recordings are masters too: Merritt Horn's reading, and
            # Григорий Войнер's.
            # And the translations: ud's name is too short to search for alone;
            # the Foundation's zips are inside the project, in data/uf/.
            for bad in ("urantia-uversa-press-claude", "../index",
                        "urantia-study-edition", "Urantia-MH-Audio", "RUS-Voyner", "block-sources",
                        "../ud", "urantia-ru", "data/uf"):
                for m in [*WRITE_OPEN.finditer(src), *WRITERS.finditer(src)]:
                    seg = src[max(0, m.start() - 200):m.end() + 200]
                    self.assertNotIn(bad, seg,
                                     f"{rel}: write near a sibling path {bad!r}")

    def test_source_paths_only_in_config(self):
        """sources.toml is read in exactly one place."""
        hits = [rel for rel, src in self._sources()
                if "sources.toml" in src and not rel.endswith("config.py")]
        self.assertEqual(hits, [], f"sources.toml read outside config.py: {hits}")


if __name__ == "__main__":
    unittest.main()
