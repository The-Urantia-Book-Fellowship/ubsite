"""Hold the site's line breaks to the printed book's.

    .venv/bin/python tools/hyphen_print.py [BOOK.pdf]

Every word the press's PDF breaks at a line's end must break at the same place
in var/ub.db, as one of the soft hyphens of paragraph.html_hy (build/hyphen.py).
The default PDF is the one built in the press tree, urantia-uversa-press.pdf.

A printed break is read as tools/hyphen_audit.py in the press repository reads
it: `pdftotext -raw`, a line ending in letters and a hyphen, and the letters
that begin the next.  It counts only words the text contains whole, and not a
compound's own hyphen (`well-|known').  A word is matched in lower case, and
its breaks are those of all its occurrences, so a \\- in one use allows its
point in the count for every use: the same leniency as the audit's.

Not a gate.  The PDF is built, not kept, and may describe an older or a newer
book than the one this database was read from (CLAUDE.md §5).  Exit status 1 if
any printed break is not offered here; each must be explained, never waved away.
"""

from __future__ import annotations

import collections
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import config, db                          # noqa: E402
from build.checks.check_hyphen import _offsets        # noqa: E402

_WORD = re.compile(r"[A-Za-z]+")
_COMPOUND = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)+")


def printed_breaks(pdf: pathlib.Path):
    raw = subprocess.run(["pdftotext", "-raw", str(pdf), "-"], capture_output=True,
                         text=True, check=True).stdout.split("\n")
    for a, b in zip(raw, raw[1:]):
        m = re.search(r"([A-Za-z]+)-$", a.rstrip())
        mb = re.match(r"\s*([A-Za-z]+)", b)
        if m and mb and not a.rstrip().endswith("--"):
            yield m.group(1), mb.group(1)


def offered(con):
    """{word: the points it breaks at somewhere}, {joined compound: its hyphens}."""
    words: dict[str, set[int]] = collections.defaultdict(set)
    joined: dict[str, set[int]] = collections.defaultdict(set)
    for text, hy in con.execute("SELECT text, html_hy FROM paragraph"):
        at = set(_offsets(hy))
        for m in _WORD.finditer(text):
            a, b = m.span()
            words[m.group().lower()] |= {p - a for p in at if a < p < b}
        for m in _COMPOUND.finditer(text):
            parts = m.group().lower().split("-")
            joined["".join(parts)] |= {len("".join(parts[:k])) for k in range(1, len(parts))}
    return words, joined


def main(argv: list[str]) -> int:
    pdf = pathlib.Path(argv[0]) if argv else (
        config.load()["press"]["path"] / "urantia-uversa-press.pdf")
    if not pdf.exists():
        print(f"hyphen_print: no PDF at {pdf}; build the book there, or name one", file=sys.stderr)
        return 2
    words, joined = offered(db.connect(ROOT / "var" / "ub.db"))
    n = 0
    missed = collections.Counter()
    for h, t in printed_breaks(pdf):
        w, p = (h + t).lower(), len(h)
        if w not in words or p in joined.get(w, ()):
            continue
        n += 1
        if p not in words[w]:
            missed[f"{w[:p]}-{w[p:]}"] += 1
    print(f"{pdf}\n  {n:,} printed breaks in words of the text;"
          f" {sum(missed.values())} not offered by var/ub.db")
    for b, c in missed.most_common():
        print(f"    {c:4d}  {b}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
