"""Gate: the two editions must agree on (paper, section, paragraph).

They are separate editorial objects -- the study edition is metricated, Oxford
British and science-corrected -- but they address the *same* book, and the Index
resolves its 50,758 citations against the press numbering.  A paragraph key that
exists in one edition and not the other is therefore a defect in whichever one
drifted, not a fact to be accommodated.

Every surviving divergence must be declared in verify/exceptions.toml with a
reason and a date.  An undeclared one fails the build.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

RE_VS = re.compile(r"^\\vs p(\d+) (\d+):(\d+) ?(.*)$")


def study_keys(texdir: pathlib.Path, rev: str = "worktree") -> dict[tuple[int, int, int], str]:
    """Each paragraph of the study edition, at the commit the build reads it at."""
    from ..readers._io import read_tex_many
    out = {}
    names = [f"p{n:03d}.tex" for n in range(197)]
    for name, src in read_tex_many(texdir, names, rev).items():
        if src is None:
            continue
        paper = int(name[1:4])
        for ln, raw in enumerate(src.splitlines(), 1):
            m = RE_VS.match(raw.strip())
            if m:
                out[(paper, int(m.group(2)), int(m.group(3)))] = f"{name}:{ln}"
    return out


def press_keys(oracle: pathlib.Path) -> dict[tuple[int, int, int], str]:
    return {(r["p"], r["s"], r["n"]): r["src"]
            for r in (json.loads(l) for l in oracle.open(encoding="utf-8"))}


def run(study_tex: pathlib.Path, oracle: pathlib.Path, exceptions: dict,
        rev: str = "worktree") -> int:
    s, p = study_keys(study_tex, rev), press_keys(oracle)
    so, po = sorted(set(s) - set(p)), sorted(set(p) - set(s))
    print(f"press {len(p)}   study {len(s)}")
    bad = 0
    for k in so:
        key = "study-only@%d:%d.%d" % k
        if key in exceptions:
            print(f"  declared  {key}  -- {exceptions[key]}")
        else:
            print(f"  UNDECLARED study-only  {k[0]}:{k[1]}.{k[2]}  {s[k]}", file=sys.stderr)
            bad += 1
    for k in po:
        key = "press-only@%d:%d.%d" % k
        if key in exceptions:
            print(f"  declared  {key}  -- {exceptions[key]}")
        else:
            print(f"  UNDECLARED press-only  {k[0]}:{k[1]}.{k[2]}", file=sys.stderr)
            bad += 1
    print(f"\nalignment: {len(so)} study-only, {len(po)} press-only, {bad} undeclared")
    return 1 if bad else 0


if __name__ == "__main__":
    import tomllib
    exc_path = pathlib.Path(__file__).resolve().parent.parent.parent / "verify" / "exceptions.toml"
    exc = {}
    if exc_path.exists():
        with open(exc_path, "rb") as fh:
            exc = {k: v.get("reason", "") for k, v in tomllib.load(fh).get("alignment", {}).items()}
    raise SystemExit(run(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), exc))
