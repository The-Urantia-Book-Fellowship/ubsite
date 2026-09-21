"""Rebuild the comparison oracles, without writing to any sibling repo.

Both oracles are derived, gitignored, and regenerate in seconds -- and both
describe the press text, so a stale one silently describes an older book.  The
gate would then compare today's extraction against last week's evidence and
report agreement, which is worse than no check at all.

Neither tool takes an output path; both write relative to the current
directory:

    ../index/build_srt.py          TEXDIR = "../urantia-uversa-press-claude/tex"
                                   OUT    = "data/srt.jsonl"
    press tools/text-verify/extract_tex.py
                                   reads  tex/pNNN.tex (argv)
                                   writes artifacts/text-verify/tex/pNNN.jsonl

So each runs in a sandbox under var/ with its inputs symlinked into place.  The
tools are used exactly as their authors wrote them -- no edits, no patched
constants -- and everything they produce lands here.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _link(link: pathlib.Path, target: pathlib.Path) -> None:
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def build_srt(repos, report) -> pathlib.Path | None:
    """-> var/oracle/data/srt.jsonl, freshly built from the current press text."""
    index, press = repos["index"]["path"], repos["press"]["path"]
    script = index / "build_srt.py"
    if not script.exists():
        report.warn("oracle-missing", str(script), "build_srt.py not found")
        return None

    sandbox = ROOT / "var" / "oracle"
    (sandbox / "data").mkdir(parents=True, exist_ok=True)
    # TEXDIR is "../<press>/tex" relative to the CWD, so the press tree must
    # appear one level above the sandbox.
    _link(sandbox.parent / press.name, press)

    out = subprocess.run([sys.executable, "-B", str(script)],
                         cwd=sandbox, capture_output=True, text=True)
    produced = sandbox / "data" / "srt.jsonl"
    if out.returncode != 0 or not produced.exists():
        report.hard("oracle-build-failed", "build_srt.py",
                    (out.stderr or out.stdout).strip().splitlines()[-1:][0]
                    if (out.stderr or out.stdout).strip() else "no output")
        return None
    return produced


def build_italics(repos, report) -> pathlib.Path | None:
    """-> var/pressverify/artifacts/text-verify/tex/*.jsonl (italic offsets)."""
    press = repos["press"]["path"]
    script = press / "tools" / "text-verify" / "extract_tex.py"
    if not script.exists():
        report.warn("oracle-missing", str(script), "extract_tex.py not found")
        return None

    sandbox = ROOT / "var" / "pressverify"
    sandbox.mkdir(parents=True, exist_ok=True)
    _link(sandbox / "tex", press / "tex")          # it reads tex/pNNN.tex
    papers = sorted(f"tex/{p.name}" for p in (press / "tex").glob("p[0-9][0-9][0-9].tex"))

    out = subprocess.run([sys.executable, "-B", str(script), *papers],
                         cwd=sandbox, capture_output=True, text=True)
    produced = sandbox / "artifacts" / "text-verify" / "tex"
    n = len(list(produced.glob("p[0-9][0-9][0-9].jsonl"))) if produced.is_dir() else 0
    if n != len(papers):
        report.hard("oracle-build-failed", "extract_tex.py",
                    f"produced {n} of {len(papers)} papers")
        return None
    return produced


def freshness(repos) -> str:
    """A one-line note on whether the sources moved since the oracles were built."""
    press = repos["press"]["path"]
    newest = max((p.stat().st_mtime for p in (press / "tex").glob("p*.tex")),
                 default=0)
    srt = ROOT / "var" / "oracle" / "data" / "srt.jsonl"
    if not srt.exists():
        return "oracle absent"
    age = srt.stat().st_mtime - newest
    return ("built after the newest source" if age >= 0
            else f"STALE by {-age / 3600:.1f} h")
