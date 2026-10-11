"""Text versions compose: from any version a site holds, the reply brings it to the newest.

build/versions.py on synthetic states, in a ledger in a temporary directory --
never data/text/ itself -- and what /api/v1/text would select for each version
ever made, applied to that version's state.  Edits, additions, a removal, the
same record coming back, and a build that changes nothing.  Then the checked-in
ledger itself: append-only, against the last commit.
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import versions  # noqa: E402

PRESS = {"commit": "0" * 40, "dirty": False}


def p(ref):
    return ("paragraph", ref)


STATES = [
    {p("1:0.1"): "a", p("1:0.2"): "b", ("section", "1:0"): "s", ("paper", "1"): "P"},
    {p("1:0.1"): "a2", p("1:0.2"): "b", ("section", "1:0"): "s", ("paper", "1"): "P"},
    {p("1:0.1"): "a2", p("1:0.2"): "b", p("1:0.3"): "c", ("section", "1:0"): "s",
     ("paper", "1"): "P"},
    {p("1:0.1"): "a2", p("1:0.3"): "c", ("section", "1:0"): "s", ("paper", "1"): "P"},
    {p("1:0.1"): "a2", p("1:0.3"): "c", ("section", "1:0"): "s", ("paper", "1"): "P"},
    {p("1:0.1"): "a2", p("1:0.2"): "b", p("1:0.3"): "c", ("section", "1:0"): "s2",
     ("paper", "1"): "P"},
    {p("1:0.2"): "b3", p("1:0.3"): "c", ("section", "1:0"): "s2", ("paper", "1"): "P2"},
]


class Compose(unittest.TestCase):
    def test_every_reply_lands_on_the_newest(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = pathlib.Path(d)
            held: dict[int, dict] = {0: {}}
            for i, cur in enumerate(STATES):
                st = versions.advance(versions.fold(ledger), cur, PRESS, ledger, "2026-10-11")
                if st.pending:
                    st.pending.append()
                held.setdefault(st.n, dict(cur))
                for v, had in held.items():
                    sent = {k: cur[k] for k, ver in st.since.items() if ver > v}
                    gone = {k for k, ver in st.gone.items() if ver > v}
                    got = {k: h for k, h in had.items() if k not in gone} | sent
                    self.assertEqual(got, cur, f"state {i}: a site at version {v}")
            # The unchanged build (state 4) made no version.
            self.assertEqual(st.n, len(STATES) - 1)
            led = versions.fold(ledger)
            self.assertEqual([v[0] for v in led.versions], list(range(1, len(STATES))))
            self.assertEqual({k: h for k, (h, _) in led.latest.items() if h != "-"}, STATES[-1])

    def test_the_first_version_is_everything(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = pathlib.Path(d)
            st = versions.advance(versions.fold(ledger), STATES[0], PRESS, ledger, "2026-10-11")
            self.assertEqual(st.n, 1)
            self.assertEqual(set(st.since.values()), {1})
            self.assertEqual(st.pending.version, (1, "2026-10-11", "0" * 40, 4, 0))

    def test_a_dirty_tree_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = pathlib.Path(d)
            st = versions.advance(versions.fold(ledger), STATES[0],
                                  {"commit": "abc", "dirty": True}, ledger, "2026-10-11")
            self.assertEqual(st.pending.version[2], "abc+dirty")

    def test_a_gap_in_the_versions_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = pathlib.Path(d)
            (ledger / "versions.tsv").write_text("1\t2026-10-11\tx\t1\t0\n3\t2026-10-12\tx\t1\t0\n")
            with self.assertRaises(SystemExit):
                versions.fold(ledger)

    def test_a_unit_of_an_unmade_version_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = pathlib.Path(d)
            (ledger / "versions.tsv").write_text("1\t2026-10-11\tx\t1\t0\n")
            (ledger / "units.tsv").write_text("1\tparagraph\t1:0.1\taaaa\n"
                                              "2\tparagraph\t1:0.1\tbbbb\n")
            with self.assertRaises(SystemExit):
                versions.fold(ledger)


class Ledger(unittest.TestCase):
    """data/text/ is only ever appended to: a version that reached a site is never rewritten."""

    def test_append_only_since_the_last_commit(self):
        for name in ("versions.tsv", "units.tsv"):
            path = ROOT / "data" / "text" / name
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:data/text/{name}"],
                                 capture_output=True, text=True)
            if old.returncode != 0:
                continue                           # not committed yet
            self.assertTrue(path.read_text(encoding="utf-8").startswith(old.stdout),
                            f"data/text/{name} differs from HEAD's other than by appending")


if __name__ == "__main__":
    unittest.main()
