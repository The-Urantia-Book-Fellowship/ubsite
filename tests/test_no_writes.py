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
    "build/vendorlib.py": "vendor/",               # the vendored copies + lock
    "build/fonts.py": "ubsite/static/fonts/",      # the UB Goudy subset (fontTools)
}

WRITE_OPEN = re.compile(r"""\bopen\s*\([^)]*['"][waxr]?\+?[wax]\+?['"]""")
WRITERS = re.compile(r"\b(os\.remove|os\.unlink|os\.rename|os\.replace|shutil\.(?:rmtree|move|copy\w*)"
                     r"|Path\.write_(?:text|bytes)|\.write_text\(|\.write_bytes\(|\.unlink\()")

# Paths this project is allowed to write to.
OWN = ("var/", "export/", "data/", "vendor/", "build/cache/", "tests/fixtures/")


class NoWrites(unittest.TestCase):
    def _sources(self):
        for p in (ROOT / "build").rglob("*.py"):
            yield p.relative_to(ROOT).as_posix(), p.read_text()

    def test_only_io_opens_for_write(self):
        offenders = []
        for rel, src in self._sources():
            if rel in ALLOWED:
                continue
            for m in WRITE_OPEN.finditer(src):
                line = src[:m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line}  {m.group(0)}")
        self.assertEqual(offenders, [], "write-mode open() outside the IO chokepoint:\n"
                                        + "\n".join(offenders))

    def test_io_module_never_writes(self):
        src = (ROOT / "build/readers/_io.py").read_text()
        self.assertNotRegex(src, WRITE_OPEN, "_io.py must never open for writing")
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

    def test_no_writer_names_a_sibling(self):
        """No module may name a sibling repo path in a write context."""
        for rel, src in self._sources():
            # The recordings are a master too: Merritt Horn's reading.
            for bad in ("urantia-uversa-press-claude", "../index",
                        "urantia-study-edition", "Urantia-MH-Audio"):
                for m in WRITE_OPEN.finditer(src):
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
