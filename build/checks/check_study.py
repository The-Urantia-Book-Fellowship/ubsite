"""The study edition as a whole, at the commit the build reads: what is there,
what the site has taken of it, and what a paper still to come would need.

The build gates each admitted paper (build/study.py).  This looks at all 197,
so that a command the macro table lacks, or math the converter cannot set, is
seen in `make check` before the paper that holds it is reviewed, not after.
Warnings, not failures: an unreviewed paper is no defect of the site.
"""

from __future__ import annotations

import collections
import sys

from .. import study, texmath
from ..readers import study as reader
from ..study_macros import ITALIC_OPENERS, TABLE

sys.path.insert(0, str(study.ROOT / "vendor" / "press"))
from latex_tokenizer import tokenize  # noqa: E402


def _macros(tex: str) -> tuple[set[str], list[str]]:
    """The commands in `tex` outside its math, and its math."""
    at = reader.unescaped(tex, "$")
    maths = [tex[a + 1:b] for a, b in zip(at[::2], at[1::2])]
    plain, last = [], 0
    for a, b in zip(at[::2], at[1::2]):
        plain.append(tex[last:a])
        last = b + 1
    plain.append(tex[last:])
    names = {t.value for t in tokenize(" ".join(plain)) if t.kind == "MACRO"}
    return names, maths


def run(repo: dict, block: dict, report) -> int:
    papers = reader.read(repo["tex"], repo["at"], reader.PAPERS, report)
    notes = [n for p in papers.values() for n in p.notes]
    sources = [s for p in papers.values() for s in p.sources]
    with_notes = sorted(n for n, p in papers.items() if p.notes)
    print(f"  the edition at {repo['at'][:7]}: {len(notes)} notes in {len(with_notes)} papers,"
          f" {len(sources)} sources in {sum(1 for p in papers.values() if p.sources)}")
    bibrefs = sum(n.body.count("\\bibref") for n in notes)
    with_math = [n for n in notes if len(reader.unescaped(n.body, "$")) >= 2]
    print(f"  {bibrefs} \\bibref in the notes; {len(with_math)} notes hold math")

    unknown: dict[str, list[str]] = collections.defaultdict(list)
    unset: list[str] = []
    for n in notes:
        names, maths = _macros(n.body)
        for m in sorted(names - set(TABLE)):
            unknown[m].append(n.ref)
        for m in maths:
            try:
                texmath.convert(m)
            except texmath.MathError as e:
                unset.append(f"{n.ref} ${m}$: {e}")
    for s in sources:
        names, _ = _macros(s.body)
        for m in sorted(names - set(TABLE) - ITALIC_OPENERS):
            unknown[m].append(s.key)
    for m, where in sorted(unknown.items()):
        report.warn("study-macro-new", f"\\{m}",
                    f"not in build/study_macros.py: {', '.join(where[:5])}"
                    + (f" and {len(where) - 5} more" if len(where) > 5 else ""))
    for u in unset:
        report.warn("study-math-new", u.split(" ")[0], u)
    print(f"  {len(unknown)} commands outside the study table,"
          f" {len(unset)} expressions outside the math set")

    curated = study.load_curated(report)
    done = sorted(curated)
    left = [n for n in with_notes if n not in curated]
    print(f"  on the site: {len(done)} papers ({', '.join(map(str, done)) or 'none yet'});"
          f" {len(left)} with notes still to review")
    if block["charts"] is None:
        print("  Block's charts: no MANIFEST.tsv")
    else:
        print(f"  Block's charts: {len(block['charts'])} papers, manifest {block['sha256'][:12]}")
    return 0
