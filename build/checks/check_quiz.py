"""What the quiz's review has done, and what the edition still has to mend.

Reported, not asserted: the build holds the quiz to its ledger and to
tests/known-quiz-slips.tsv (build/quiz.py), so a database that exists passed
both.  This says where the review stands, paper by paper, and lists the slips
for Tigran to mend in the study edition, with their lines.
"""

from __future__ import annotations

import collections
import sqlite3

from .. import quiz


def run(db) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT paper_n, state, COUNT(*) FROM quiz_question"
                       " GROUP BY paper_n, state ORDER BY paper_n").fetchall()
    if not rows:
        print("  no quiz in the database")
        return 0
    per = collections.defaultdict(collections.Counter)
    for n, state, c in rows:
        per[n][state] += c
    done = [n for n, c in per.items() if not c["-"]]
    part = [n for n, c in per.items() if c["-"] and sum(c.values()) > c["-"]]
    total = collections.Counter()
    for c in per.values():
        total.update(c)
    print(f"  {sum(total.values())} questions on {len(per)} papers;"
          f" reviewed {sum(total.values()) - total['-']}"
          f" (text {total['text']}, note {total['note']}, none {total['none']}, drop {total['drop']})")
    print(f"  papers reviewed whole: {', '.join(map(str, done)) or 'none yet'}"
          + (f"; in part: {', '.join(map(str, part))}" if part else ""))
    slips = collections.Counter(k for k, _, _ in quiz.load_slips(_Quiet()))
    print("  slips still to mend upstream (tests/known-quiz-slips.tsv): "
          + ", ".join(f"{k} {slips[k]}" for k in quiz.SLIP_KINDS if slips[k]))
    return 0


class _Quiet:
    def hard(self, *a):
        raise SystemExit(f"tests/known-quiz-slips.tsv: {a}")
