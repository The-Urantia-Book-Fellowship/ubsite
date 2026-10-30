"""The quiz's doubtful references, for Tigran's ruling: var/quiz/doubtful.md.

    .venv/bin/python tools/quiz/doubt.py make [--again]
        For every paper with a line still unreviewed, reads its review
        (var/quiz/review-NNN.md, tools/quiz/draft.py's, with the first
        reading's "Checked:" lines) and a second reading's grades
        (var/quiz/grades/NNN.tsv: id, grade, alt, reason), and writes the
        questions in doubt, whole, to var/quiz/doubtful.md, one file to rule in;
        the rest are taken as plain, and `apply.py rule pending --accept
        --doubts` accepts them as proposed.  Never overwrites it.
    .venv/bin/python tools/quiz/doubt.py calibrate N [N ...]
        Writes nothing: for papers already ruled, how the grades agree with
        the rulings, which is how the second reading is trusted.

A question is in doubt when the second reading grades it B (answered only by
inference, in part, with a wrong answer supported too, or with a better
passage found) or C (not answered), when its proposal is a note or none, or
when var/quiz/flags.md names it in its sections 2, 3 or 5.  A grade's `alt`,
in the vocabulary a ruling uses (text 13:1.2-8, text 15:7.7 «words», note
32:2.12, none, drop), becomes one more numbered candidate of the block, and
for a C the proposal.  Each block is the review's, verbatim, with those lines
added, so apply.py reads doubtful.md as it reads a review.

Reads var/ub.db and the edition at the commit build/config.py pins.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "quiz"))

from build import quiz  # noqa: E402

import apply  # noqa: E402

OUT = ROOT / "var" / "quiz"
GRADES = OUT / "grades"
FLAGS = OUT / "flags.md"
DB = ROOT / "var" / "ub.db"
GRADE = ("A", "B", "C", "P")      # P: proposed anew, its alt the proposal
# The first reading's own doubt, in its "Checked:" line.
RE_HEDGE = re.compile(r"\b(FLAG|closest|nearest|rest is|rest are|spread|no single|not stated"
                      r"|does not say|never says|not in the book|inference|infers?|implies|implied"
                      r"|may be|half|contradicts?|disagrees?|miscount|misfiled|general knowledge"
                      r"|paraphrase|edition's own|nowhere|does not name|not named|does not give"
                      r"|does not date|never dates|is not in|not found)\b", re.I)
RE_IDS = re.compile(r"\bids? ([\d, –-]+)")
FLAG_SECTIONS = {"2.": "a wrong answer has the book's words for it (flags §2)",
                 "3.": "the answer is the quiz's inference, not the book's words (flags §3)",
                 "5.": "every answer is marked right (flags §5)"}


def grades(n: int) -> dict[int, tuple[str, str, str]] | None:
    """{id: (grade, alt, reason)} of a paper's second reading, or None."""
    path = GRADES / f"{n:03d}.tsv"
    if not path.exists():
        return None
    out = {}
    for k, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.startswith("#") or raw.startswith("id\t"):
            continue
        f = raw.split("\t")
        if len(f) != 4 or not f[0].isdigit() or f[1] not in GRADE:
            raise SystemExit(f"{path.relative_to(ROOT)}:{k}: id<TAB>grade (A, B or C)<TAB>alt<TAB>reason")
        out[int(f[0])] = (f[1], f[2].strip(), f[3].strip())
    return out


def flagged() -> dict[int, list[str]]:
    """{id: [reason]} for the ids var/quiz/flags.md names in its §2, §3, §5."""
    out: dict[int, list[str]] = collections.defaultdict(list)
    if not FLAGS.exists():
        return out
    for section in re.split(r"^## ", FLAGS.read_text(encoding="utf-8"), flags=re.M):
        head = section.split("\n", 1)[0]
        why = next((w for k, w in FLAG_SECTIONS.items() if head.startswith(k)), None)
        if not why:
            continue
        for group in RE_IDS.findall(section):
            for part in re.split(r",\s*", group.strip()):
                part = part.strip()
                if (m := re.fullmatch(r"(\d+)[–-](\d+)", part)):
                    for i in range(int(m[1]), int(m[2]) + 1):
                        out[i].append(why)
                elif part.isdigit():
                    out[int(part)].append(why)
    return out


def blocks(path: pathlib.Path) -> dict[int, list[str]]:
    """{id: the lines of its block}, "## Q" through its "Ruling:" line."""
    out: dict[int, list[str]] = {}
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if (m := apply.RE_Q.match(raw)):
            cur = out[int(m[2])] = []
        if cur is not None:
            cur.append(raw)
            if apply.RE_RULING.match(raw):
                cur = None
    return out


def candidate_line(k: int, state: str, refs: list[tuple[str, str]]) -> str:
    if state == "note":
        return f"{k}. note {refs[0][0]} {refs[0][1]}"
    return f"{k}. text " + " and ".join(ref if quote == quiz.WHOLE else f"{ref} «{quote}»" for ref, quote in refs)


def with_second_reading(lines: list[str], item: dict, grade: str, alt: str, reason: str,
                        why: list[str], decided, faults: list[str]) -> list[str]:
    """The block with the second reading's lines in it."""
    out = list(lines)
    k = max((int(c) for c in item["candidates"]), default=0) + 1
    said = f"Second reading: {grade}" + (f" — {reason}" if reason else "")
    proposed = None
    if decided is not None:
        state, refs = decided
        if state in ("text", "note"):
            if not faults:
                same = next((c for c, v in item["candidates"].items()
                             if v == candidate_line(0, state, refs)[3:]), None)
                if same:
                    k = int(same)                     # a candidate the review has already
                else:
                    # at the blank line that ends the list, past the last
                    # candidate's second line, a score or a note's sentence
                    start = next(i for i, s in enumerate(out) if s == "Candidates:")
                    end = next(i for i in range(start + 1, len(out)) if not out[i].strip())
                    out.insert(end, candidate_line(k, state, refs))
                said += f" (candidate {k})"
                if grade in ("C", "P"):
                    proposed = str(k)
            else:
                said += " (its proposal fails: " + "; ".join(faults) + ")"
        elif state == "none" and grade in ("C", "P"):
            proposed = "none"
        elif state == "drop":
            said += " (it would drop the question)"
    elif alt:
        said += f" (its proposal cannot be read: {alt!r})"
    i = next((i for i, s in enumerate(out) if s.startswith("Checked:")), None)
    if i is None:
        i = next(i for i, s in enumerate(out) if s.startswith("Proposed:")) - 1
    out.insert(i + 1, said)
    out.insert(i + 2, "Why here: " + "; ".join(why))
    if proposed is not None:
        j = next(i for i, s in enumerate(out) if s.startswith("Proposed:"))
        was = out[j].split(":", 1)[1].strip()
        out[j] = f"Proposed: {proposed} (was {was})"
    return out


def cmd_make(again: bool = False) -> int:
    """With `again`, the file is made anew from the grades as they are now,
    every ruling in it carried over by id, and the old one kept as
    doubtful.prev.md: for a second reading's new proposals."""
    out = OUT / "doubtful.md"
    carried: dict[int, str] = {}
    if out.exists() and not again:
        print(f"{out.relative_to(ROOT)} exists, with rulings in it: never overwritten."
              " `make --again` makes it anew and carries the rulings over.", file=sys.stderr)
        return 1
    if out.exists():
        carried = {qid: it["ruling"] for qid, it in apply.parse_review(out).items() if (it["ruling"] or "").strip()}
    lines = apply.ledger()
    papers = apply.pending_papers(lines)
    missing = [n for n in papers if grades(n) is None or not (OUT / f"review-{n:03d}.md").exists()]
    if missing:
        print("No grades or no review yet for Paper " + ", ".join(map(str, missing)), file=sys.stderr)
        return 1
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    text = dict(con.execute("SELECT ref, text FROM paragraph"))
    titles = dict(con.execute("SELECT n, title FROM paper"))
    notes_at = apply._notes_at()
    flags = flagged()
    body: list[str] = []
    appendix: list[str] = []
    count = collections.Counter()
    doubtful = plain = 0
    for n in papers:
        review = OUT / f"review-{n:03d}.md"
        items, blk, gr = apply.parse_review(review), blocks(review), grades(n)
        pending_ids = {x.id for x in lines if x.paper == n and x.state == "-"}
        ungraded = sorted(pending_ids - gr.keys())
        if ungraded:
            raise SystemExit(f"Paper {n}: no grade for id {', '.join(map(str, ungraded))}")
        paper_lines: list[str] = []
        for qid in sorted(pending_ids, key=lambda i: items[i]["q"] if i in items else 0):
            if qid not in items:
                raise SystemExit(f"Paper {n}: id {qid} is not in {review.relative_to(ROOT)}")
            item, grade, alt, reason = items[qid], *gr[qid]
            why = []
            if grade in ("B", "C", "P"):
                why.append({"B": "the second reading finds it doubtful", "C": "the second reading finds it wrong",
                            "P": "the second reading proposes the passages anew"}[grade])
            if item["proposed"] == "none":
                why.append("nothing is proposed")
            elif item["candidates"].get(item["proposed"], "").startswith("note "):
                why.append("a study note is proposed")
            why += flags.get(qid, [])
            decided, faults = None, []
            if alt:
                got = apply.decide({"proposed": None, "candidates": {}, "ruling": alt}, notes_at)
                if isinstance(got, str):
                    why.append(f"the second reading's proposal cannot be read: {got}")
                else:
                    decided = got
                    faults, warns = apply.hold(text, *got, f"Paper {n} Q{item['q']}")
                    if faults:
                        why.append("the second reading's proposal fails the build's check")
                    if warns:
                        reason = (reason + " " if reason else "") + f"[{warns[0]}]"
            checked = next((s for s in blk[qid] if s.startswith("Checked:")), "")
            if not why:
                plain += 1
                if RE_HEDGE.search(checked):
                    count["appendix"] += 1
                    right = [s[4:] for s in blk[qid] if s.startswith("- ✓ ")]
                    ref = item["candidates"].get(item["proposed"], "").split(" ")[1:2]
                    appendix.append(f"- **{n} Q{item['q']}** (id {qid}) ✓ {' / '.join(right)} — "
                                    f"{ref[0] if ref else '?'}. First: {checked[9:]} Second: {reason or grade}")
                continue
            doubtful += 1
            count[grade] += 1
            for w in why[1:] if grade in ("B", "C", "P") else why:
                count[w] += 1
            block = with_second_reading(blk[qid], item, grade, alt, reason, why, decided, faults)
            if qid in carried:
                j = next(i for i, s in enumerate(block) if apply.RE_RULING.match(s))
                block[j] = f"Ruling: {carried.pop(qid)}"
            paper_lines += block
            paper_lines.append("")
        if paper_lines:
            body += [f"# Paper {n}, {titles[n]}", ""] + paper_lines
    pending = sum(1 for x in lines if x.state == "-")
    reasons = "; ".join(f"{v} {k}" for k, v in count.items() if k not in ("appendix", "A", "B", "C"))
    head = [
        "# The quiz: the references in doubt, for ruling", "",
        f"Of the {pending} questions of {len(papers)} papers not yet ruled, these {doubtful} are in doubt after a"
        f" second reading (tools/quiz/doubt.py): {count['C']} it finds wrong, {count['B']} doubtful,"
        f" {count['P']} proposed anew as several passages"
        + (f"; {reasons}" if reasons else "") + f". The other {plain} it finds plain, and they will be"
        " accepted as proposed; those the first reading hedged over are listed at the end, one line each.", "",
        "Each block is the question as its review file has it, with the second reading's lines added: its"
        " grade and reason, a further candidate where it proposes one, and `Why here:`. On each `Ruling:` line"
        " write:", "",
        "- nothing: the `Proposed:` candidate stands (for a C or a P, the second reading's)",
        "- `1`, `2`, `3`: that candidate instead, or several, `6 and 1`; \"No, the correct candidate is 1\" says the same",
        "- `text 32:2.11 «words»`: another paragraph, and the words quoted from it, as the text has them",
        "- `text 0:3.2-8`: a paragraph, or a run of one section's paragraphs, shown whole; \"No, the correct"
        " reference is 0:3.2-8\" says the same",
        "- several passages, in the order to show them: `13:1.1 and 13:2.7-8`, `13:1.5 «words» and 13:1.6`;"
        " no length is refused, over 1,000 characters is warned of",
        "- `note 32:2.12`: the study note there",
        "- `none`: neither the text nor a note answers it",
        "- `drop`: leave the question out", "",
        "Anything else under a question is read by me, not by the tool. Then"
        " `.venv/bin/python tools/quiz/apply.py rule pending --accept --doubts`.", ""]
    tail = []
    if appendix:
        tail = ["# Hedged by the first reading, plain on the second", "",
                "A ruling on one of these goes on its `Ruling:` line in its review file.", ""] + appendix + [""]
    OUT.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.replace(out.with_name("doubtful.prev.md"))
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(head + body + tail))
    tmp.replace(out)
    print(f"{out.relative_to(ROOT)}: {doubtful} in doubt of {pending}"
          f" ({dict(count)}), {plain} plain, {count['appendix']} in the appendix")
    if carried:
        print(f"rulings carried nowhere (their questions are no longer in doubt): {sorted(carried)}")
    return 0


def cmd_calibrate(papers: list[int]) -> int:
    """How the grades agree with Tigran's rulings on papers already ruled."""
    caught, missed, alarms, failing, plain, total = [], [], [], [], 0, 0
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    text = dict(con.execute("SELECT ref, text FROM paragraph"))
    notes_at = apply._notes_at()
    for n in papers:
        gr = grades(n)
        if gr is None:
            print(f"Paper {n}: no {GRADES.relative_to(ROOT)}/{n:03d}.tsv")
            return 1
        for qid, item in apply.parse_review(OUT / f"review-{n:03d}.md").items():
            if qid not in gr:
                print(f"Paper {n} Q{item['q']} (id {qid}): not graded")
                continue
            total += 1
            if gr[qid][1]:
                got = apply.decide({"proposed": None, "candidates": {}, "ruling": gr[qid][1]}, notes_at)
                faults = [got] if isinstance(got, str) else apply.hold(text, *got, f"{n} Q{item['q']}")[0]
                failing += [f"{n} Q{item['q']} (id {qid}) {gr[qid][1][:60]!r}: {f}" for f in faults]
            r = (item["ruling"] or "").strip()
            changed = bool(r) and r.lower().rstrip(".") not in ("yes", "y") and not r.startswith("drop until")
            grade = gr[qid][0]
            where = f"{n} Q{item['q']} (id {qid}) {grade}: {gr[qid][2][:90]}"
            if changed and grade != "A":
                caught.append(where + f"  [ruled: {r[:60]}]")
            elif changed:
                missed.append(where + f"  [ruled: {r[:60]}]")
            elif grade != "A":
                alarms.append(where)
            else:
                plain += 1
    print(f"{total} questions: {len(caught)} changed rulings caught, {len(missed)} missed,"
          f" {len(alarms)} graded B or C where the ruling accepted, {plain} plain and accepted")
    for name, rows in (("caught", caught), ("missed", missed), ("alarms", alarms), ("alts that fail", failing)):
        if rows:
            print(f"\n{name}:")
            for row in rows:
                print(f"  {row}")
    return 0


def main(argv: list[str]) -> int:
    if argv in (["make"], ["make", "--again"]):
        return cmd_make(len(argv) == 2)
    if argv[:1] == ["calibrate"] and len(argv) > 1 and all(x.isdigit() for x in argv[1:]):
        return cmd_calibrate([int(x) for x in argv[1:]])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
