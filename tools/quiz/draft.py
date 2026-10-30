"""Draft a paper's quiz for review: var/quiz/review-NNN.md.

    .venv/bin/python tools/quiz/draft.py N

Each of the paper's questions, Q1... in quiz.tex's order, as the site shows it
(its spelling made American and its dates put in the book's order, each
change marked), its right answers, the slips the build lists for it, and what
might answer it: up to three paragraphs of the text and the edition's study
notes, each with the sentence that matched, and one of them proposed.  quiz.tex
names no paragraph, and a trial found only 306 of its 819 right answers word
for word in the text, so the draft only proposes: Tigran rules under each
question, on its `Ruling:` line, and `tools/quiz/apply.py rule N` writes the
rulings into data/quiz/questions.tsv.

A paragraph is ranked by the right answer's distinctive words it has, twice
over, and the question's, first in the question's own paper and then in the
whole book; a study note of the edition likewise, reviewed or not, since a
question may be answered by one (Excalibur, by 32:2.12's).  The quote proposed
is the sentence that matched, as the paragraph has it.

Never overwrites a review: his rulings are in it.  Reads var/ub.db, so
`make data` first, and the edition at the commit build/config.py pins.
"""

from __future__ import annotations

import collections
import math
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from build import config, quiz, study  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import quiz as reader  # noqa: E402
from build.readers import study as sreader  # noqa: E402

OUT = ROOT / "var" / "quiz"
DB = ROOT / "var" / "ub.db"
RE_WORD = re.compile(r"\d[\d,]*\d|\d|[^\W\d_]+(?:[’'][^\W\d_]+)*")
RE_SENTENCE = re.compile(r"(?<=[.!?])[”’)]?\s+(?=[“‘(]?[A-Z0-9])")
# A full stop that ends no sentence: "c. 1136", "p. 225", "St. Paul".
RE_ABBREV = re.compile(r"(?:^|\s)(?:c|ca|cf|p|pp|vol|no|St|Dr|Mr|Mrs|vs|e\.g|i\.e|ff)\.$")
RE_CLAUSE = re.compile(r"[,;:] | — ")
STOP = frozenset("""a an and are as at be been but by can could did do does for from had has have he her
his how i in into is it its may might no not of on one or our so such than that the their them then
there these they this those through to two us was we were what when where which who whom whose why will
with would you your yes ever every all any many much more most some other others only also own same
very each upon""".split())
QUOTE_MAX = 320          # the sentence cut for a draft; the build refuses no length (2026-10-29)


def words(s: str) -> set[str]:
    out = set()
    for w in RE_WORD.findall(s.lower()):
        w = w.replace(",", "").replace("’", "'")
        if w.endswith("'s"):
            w = w[:-2]
        if w not in STOP and (len(w) > 2 or w.isdigit()):
            out.add(w)
    return out


def sentences(text: str) -> list[str]:
    """The text's sentences, each its own substring, whole words."""
    out, i = [], 0
    for m in RE_SENTENCE.finditer(text):
        end = m.start() + len(m.group()) - len(m.group().lstrip("”’)"))
        piece = text[i:end].rstrip()
        if RE_ABBREV.search(piece):
            continue
        out.append(text[i:end].strip())
        i = m.end()
    out.append(text[i:].strip())
    return [s for s in out if s]


class Weights:
    """How telling a word is: rare in the book, telling (its inverse document
    frequency in the search index); a word the book lacks, most telling."""

    def __init__(self, con):
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.wv USING fts5vocab(main, paragraph_fts, row)")
        self.df = {t: d for t, d in con.execute("SELECT term, doc FROM temp.wv")}
        self.n = con.execute("SELECT COUNT(*) FROM paragraph").fetchone()[0]

    def __call__(self, ws) -> float:
        return sum(math.log(self.n / self.df.get(w, 1)) for w in ws)


def score(w: set[str], aw: set[str], qw: set[str], weigh) -> float:
    return 2 * weigh(w & aw) + weigh(w & qw)


def best_sentence(text: str, aw: set[str], qw: set[str], weigh) -> tuple[float, str]:
    """The sentence most like the answer, cut at a clause if it is too long."""
    best = (-1.0, "")
    for s in sentences(text):
        sc = score(words(s), aw, qw, weigh)
        if sc > best[0]:
            best = (sc, s)
    sc, s = best
    if len(s) > QUOTE_MAX:
        cuts = [m.start() for m in RE_CLAUSE.finditer(s) if m.start() <= QUOTE_MAX]
        for c in reversed(cuts):
            if score(words(s[:c]), aw, qw, weigh) >= sc - 1e-9:
                return sc, s[:c]
    return best


def fts_query(ws: set[str]) -> str:
    return " OR ".join(f'"{w}"' for w in sorted(ws))


def candidates(con, paper: int, aw: set[str], qw: set[str], weigh) -> list[tuple]:
    """(score, ref, sentence, in_paper) of the paragraphs most like the answer."""
    q = fts_query(aw | qw)
    if not q:
        return []
    seen, out = set(), []
    for where, args in (("AND p.paper_n = ?", (q, paper)), ("", (q,))):
        for ref, text, pn in con.execute(
                "SELECT p.ref, p.text, p.paper_n FROM paragraph_fts f JOIN paragraph p ON p.id = f.rowid"
                f" WHERE paragraph_fts MATCH ? {where} ORDER BY bm25(paragraph_fts) LIMIT 12", args):
            if ref in seen:
                continue
            seen.add(ref)
            sc = score(words(text), aw, qw, weigh) * (1.2 if pn == paper else 1)
            out.append((sc, ref, best_sentence(text, aw, qw, weigh)[1], pn == paper))
    out.sort(key=lambda c: -c[0])
    return out[:3]


def note_candidates(notes, paper: int, aw: set[str], qw: set[str], weigh) -> list[tuple]:
    out = []
    for nt, text in notes:
        w = words(text)
        if not w & aw:
            continue
        sc = score(w, aw, qw, weigh) * (1.2 if nt.paper == paper else 1)
        out.append((sc, nt, best_sentence(text, aw, qw, weigh)[1]))
    out.sort(key=lambda c: -c[0])
    return out[:2]


def edition_notes(st) -> list[tuple]:
    """Every note of the edition, as plain text, reviewed or not."""
    r = Report()
    papers = sreader.read(st["tex"], st["at"], range(0, 197), r)
    out = []
    for p in papers.values():
        for nt in p.notes:
            text, _, _ = study.expand(nt.body, {}, {}, nt.ref, Report(), ties=False)
            out.append((nt, text))
    return out


def shown_changes(tex: str, table: dict) -> list[str]:
    used: set[str] = set()
    out = quiz.americanize(tex, table, used)
    changes = [f"{b} → {table[b]}" for b in sorted(used)]
    if quiz.dates(out) != out:
        changes.append("a date put in the book's order")
    return changes


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    n = int(argv[0])
    out = OUT / f"review-{n:03d}.md"
    if out.exists():
        print(f"{out.relative_to(ROOT)} exists, with rulings in it: never overwritten."
              " Move it away to draft again.", file=sys.stderr)
        return 1
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    title = con.execute("SELECT title FROM paper WHERE n = ?", (n,)).fetchone()
    qs = con.execute("SELECT id, ord, line, text, multi, state FROM quiz_question"
                     " WHERE paper_n = ? ORDER BY ord", (n,)).fetchall()
    if not title or not qs:
        print(f"Paper {n} has no questions in the quiz.", file=sys.stderr)
        return 1
    st = config.load()["study"]
    raw = {q.line: q for q in reader.read(st["tex"], st["at"], Report())}
    table = quiz.load_american(Report())
    slips = collections.defaultdict(list)
    for kind, qid, what in quiz.load_slips(Report()):
        slips[qid].append(f"{kind} «{what}»")
    notes = edition_notes(st)
    weigh = Weights(con)
    lines = [f"# Paper {n}, {title[0]}: the quiz, for review", "",
             f"Drafted by tools/quiz/draft.py from the edition at {st['at'][:7]}. Each question as the site"
             " shows it, its right answers marked ✓, and what might answer it. On each `Ruling:` line write:", "",
             "- `yes`: the proposal stands",
             "- `1`, `2`, `3`: that candidate instead; \"No, the correct candidate is 1\" says the same",
             "- `text 32:2.11 «words»`: another paragraph, and the words quoted from it, as the text has them",
             "- `text 0:3.2-8`: a paragraph, or a run of one section's paragraphs, shown whole, 320 characters"
             " at most, a run 640 together; \"No, the correct reference is 0:3.2-8\" says the same",
             "- `note 32:2.12`: the study note there",
             "- `none`: neither the text nor a note answers it",
             "- `drop`: leave the question out", "",
             "Anything else under a question is read by me, not by the tool. Then"
             f" `.venv/bin/python tools/quiz/apply.py rule {n}`.", ""]
    for qid, ord_, line, text, multi, state in qs:
        q = raw.get(line)
        answers = con.execute("SELECT text, right FROM quiz_answer WHERE question_id = ? ORDER BY n",
                              (qid,)).fetchall()
        right = [a for a, r in answers if r]
        aw = set().union(*(words(a) for a in right)) - {"yes", "no"}
        qw = words(text) - aw
        lines += [f"## Q{ord_} (id {qid}, quiz.tex:{line})", "", text, ""]
        lines += [f"- {'✓' if r else '·'} {a}" for a, r in answers]
        lines.append("")
        changes = shown_changes(q.tex + " " + " ".join(a for a, _ in q.answers), table) if q else []
        if changes:
            lines.append("Changed from quiz.tex: " + "; ".join(changes))
        if slips.get(qid):
            lines.append("Slips: " + "; ".join(slips[qid]))
        if multi:
            lines.append("More than one answer is right.")
        if state != "-":
            lines.append(f"Already ruled: {state}")
        cands = candidates(con, n, aw, qw, weigh)
        ncands = note_candidates(notes, n, aw, qw, weigh)
        lines += ["", "Candidates:"]
        k, best, best_score = 0, None, 0
        for sc_, ref, sent, here in cands:
            k += 1
            long = f" (too long by {len(sent) - QUOTE_MAX}: shorten it)" if len(sent) > QUOTE_MAX else ""
            lines.append(f"{k}. text {ref} «{sent}»")
            lines.append(f"   score {sc_:.0f}{'' if here else ', outside this paper'}{long}")
            if sc_ > best_score:
                best, best_score = k, sc_
        for sc_, nt, sent in ncands:
            k += 1
            lines.append(f"{k}. note {nt.ref} {nt.origin}")
            lines.append(f"   «{sent}» score {sc_:.0f}{'' if nt.paper == n else ', outside this paper'}")
            if sc_ > best_score:
                best, best_score = k, sc_
        if not k:
            lines.append("(none found)")
        lines += ["", f"Proposed: {best if best else 'none'}", "", "Ruling: ", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    tmp.replace(out)
    print(f"{out.relative_to(ROOT)}: {len(qs)} questions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
