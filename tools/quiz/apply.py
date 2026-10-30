"""Keep the quiz's ledgers, data/quiz/questions.tsv and references.tsv (data/quiz/README.md).

    .venv/bin/python tools/quiz/apply.py new
        Give each question of the edition that no line names its id: the next
        one, v 1, unreviewed.  Refuses while a line names a question the
        edition no longer has, which may be that question edited: rule on it
        first, with `same` or `gone`.
    .venv/bin/python tools/quiz/apply.py same ID LINE [--answers]
        Line ID is the question now at quiz.tex:LINE, as edited upstream: its
        origin moves to that question's.  With --answers, its answers changed
        (their number, order or which are right), so v moves on and an answer
        stored under the old layout is never marked against the new one.
        Its reference is reviewed again: the line goes back to unreviewed.
    .venv/bin/python tools/quiz/apply.py gone ID
        The edition deleted line ID's question: the id is kept, never reused.
    .venv/bin/python tools/quiz/apply.py rule N [N ...] [--accept] [--doubts]
        The rulings in var/quiz/review-NNN.md, made by tools/quiz/draft.py and
        ruled on by Tigran, written into the paper's lines.  A ruling may name
        several passages, in the order to show them: "13:1.1 and 13:2.7-8",
        "13:1.5 «words» and 13:1.6".  With --accept, a question he left unruled
        takes what is proposed, as he said in chat ("Accepted"); his file is
        not written, and his own rulings still stand.  With --doubts, a
        question that var/quiz/doubtful.md holds (made by tools/quiz/doubt.py
        from a second reading) is read from there instead, its candidates, its
        proposal and his ruling; `pending` in place of the numbers is every
        paper with a line still unreviewed, so `rule pending --accept --doubts`
        rules them all at once.
    .venv/bin/python tools/quiz/apply.py check N [N ...] [--doubts]
        Writes nothing: holds what each question of the reviews would get, its
        ruling or, where there is none yet, what is proposed, to what the build
        will require (a paragraph there is; its words once in it, whole; a note
        of the edition at that paragraph), says what would fail, and warns
        where over 1,000 characters would be shown.  `pending` and --doubts as
        for `rule`.

Reads the edition at the commit build/config.py pins; writes only the ledgers.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from build import config, quiz  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import quiz as reader  # noqa: E402

LEDGER = ROOT / "data" / "quiz" / "questions.tsv"
REFERENCES = quiz.REFERENCES
REVIEWS = ROOT / "var" / "quiz"
DOUBTS = REVIEWS / "doubtful.md"
HEAD = """\
# The quiz's questions, each with the id it keeps for ever: data/quiz/README.md.
# Kept by tools/quiz/apply.py; a ruling is written by `rule`, never by hand;
# what answers each is in references.tsv beside it.
id\tpaper\torigin\tv\tstate
"""
REF_HEAD = """\
# What answers each question of questions.tsv, in the order ruled: `ref` a
# paragraph or a run of one section's, `quote` its words, or ¶ for the
# paragraph(s) whole; for a note, its paragraph and the note's origin.
id\tn\tref\tquote
"""


def edition() -> list:
    st = config.load()["study"]
    r = Report()
    qs = reader.read(st["tex"], st["at"], r)
    if r.blocking or qs is None:
        raise SystemExit("\n".join(map(str, r.blocking)) or "the edition has no quiz.tex")
    return qs


def ledger() -> list[quiz.Line]:
    r = Report()
    lines = quiz.load_ledger(r, LEDGER) if LEDGER.exists() else []
    if r.blocking:
        raise SystemExit("\n".join(map(str, r.blocking)))
    return lines


def write(lines: list[quiz.Line]) -> None:
    """Both ledgers, each by way of a .tmp."""
    lines = sorted(lines, key=lambda x: x.id)
    rows = ["\t".join(map(str, (x.id, x.paper, x.origin, x.v, x.state))) for x in lines]
    refs = [f"{x.id}\t{n}\t{ref}\t{quote}" for x in lines for n, (ref, quote) in enumerate(x.refs, 1)]
    for path, body in ((LEDGER, HEAD + "".join(r + "\n" for r in rows)),
                       (REFERENCES, REF_HEAD + "".join(r + "\n" for r in refs))):
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
        tmp.replace(path)


def orphans(qs, lines):
    r = Report()
    got = quiz.reconcile(qs, lines, r)
    have = {id(x) for x in got if x is not None}
    return ([q for q, x in zip(qs, got) if x is None],
            [x for x in lines if x.state != "gone" and id(x) not in have])


def cmd_new() -> int:
    qs, lines = edition(), ledger()
    new, gone = orphans(qs, lines)
    if gone:
        print("Lines whose question the edition no longer has; rule on each first:")
        for x in gone:
            print(f"  id {x.id}, Paper {x.paper}: `same {x.id} LINE [--answers]` or `gone {x.id}`")
        for q in new:
            print(f"  new or edited: quiz.tex:{q.line}, Paper {q.paper}, question {q.ord}")
        return 1
    nxt = max((x.id for x in lines), default=0)
    for q in new:
        nxt += 1
        lines.append(quiz.Line(nxt, q.paper, q.origin, 1, "-", [], 0))
    write(lines)
    print(f"{len(new)} new: {len(lines)} lines in {LEDGER.relative_to(ROOT)}")
    return 0


def cmd_same(qid: int, lineno: int, answers: bool) -> int:
    qs, lines = edition(), ledger()
    x = next((x for x in lines if x.id == qid), None)
    q = next((q for q in qs if q.line == lineno), None)
    if x is None or q is None:
        raise SystemExit(f"no line {qid}, or no question at quiz.tex:{lineno}")
    if q.paper != x.paper:
        raise SystemExit(f"quiz.tex:{lineno} is Paper {q.paper}'s; line {qid} is Paper {x.paper}'s")
    x.origin, x.state, x.refs = q.origin, "-", []
    x.v += int(answers)
    write(lines)
    print(f"id {qid} is now quiz.tex:{lineno}, v {x.v}, to be reviewed again")
    return 0


def cmd_gone(qid: int) -> int:
    lines = ledger()
    x = next((x for x in lines if x.id == qid), None)
    if x is None:
        raise SystemExit(f"no line {qid}")
    x.state, x.refs = "gone", []
    write(lines)
    return 0


RE_Q = re.compile(r"^## Q(\d+) \(id (\d+)\b")
RE_RULING = re.compile(r"^Ruling:\s*(.*)$")
RE_PROPOSED = re.compile(r"^Proposed: (\d|none)\b")
# A candidate: the passages of the text, "text 13:1.1 «words» and 13:2.7-8",
# each a paragraph with its words, or a paragraph or a run of them shown whole;
# or a note, by its paragraph and origin.
RE_TEXT_CANDIDATE = re.compile(r"^(\d)\. (text .+)$")
RE_NOTE_CANDIDATE = re.compile(r"^(\d)\. (note \d+:\d+\.\d+ [0-9a-f]{16})$")
RE_NOTE_RULE = re.compile(r"^note (\d+:\d+\.\d+)(?: ([0-9a-f]{16}))?$")
RE_NOTE_WORDS = re.compile(r"^note (\d+:\d+\.\d+) «.+»$")
# A reference in a ruling's words, "No, the correct reference is 0:3.2-8",
# or several, "13:1.1 and 13:2.7-8" (Tigran, 2026-10-29), each with its
# «words» after it, or none for the paragraph(s) whole.
RE_REF_AT = re.compile(r"(?<![\d:.])(\d+:\d+\.\d+)(?:[-–](\d+))?(?![\d:]|\.\d)")
RE_QUOTE_AT = re.compile(r"«(.+?)»")
# Candidates by number alone: "1", "6 and 1", "2, 3"
RE_DIGITS = re.compile(r"^\d(?:\s*(?:,|;|and|&)\s*\d)*$")
# "No, the correct candidate is 1": a candidate named in words
RE_CANDIDATE_NAMED = re.compile(r"\bcandidate(?: is)?(?: number)? (\d)\b", re.I)
# "The correct reference is 12:5.6-9"
RE_REFERENCE_NAMED = re.compile(r"\breferences?\b", re.I)


def parse_review(path: pathlib.Path) -> dict[int, dict]:
    """{id: {proposed, candidates, ruling}} from a review file, or from
    var/quiz/doubtful.md, whose blocks are a review's with lines added."""
    out: dict[int, dict] = {}
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = RE_Q.match(raw)
        if m:
            cur = out.setdefault(int(m[2]), {"q": int(m[1]), "proposed": None,
                                              "candidates": {}, "ruling": None})
            continue
        if cur is None:
            continue
        if (m := RE_PROPOSED.match(raw)):
            cur["proposed"] = m[1]
        elif (m := RE_TEXT_CANDIDATE.match(raw.strip())) or (m := RE_NOTE_CANDIDATE.match(raw.strip())):
            cur["candidates"][m[1]] = m[2]
        elif (m := RE_RULING.match(raw)):
            cur["ruling"] = m[1].strip()
    return out


def references(s: str) -> list[tuple[str, str]] | str:
    """The passages a ruling or a candidate names, in order, each (ref, words
    or WHOLE): "13:1.1 «words» and 13:2.7-8"; or what is wrong with it."""
    quotes = [(m.start(), m.end(), m[1]) for m in RE_QUOTE_AT.finditer(s)]
    refs = [(m.start(), m.end(), m[1] + (f"-{m[2]}" if m[2] else "")) for m in RE_REF_AT.finditer(s)
            if not any(a <= m.start() < b for a, b, _ in quotes)]
    if not refs:
        return f"no reference in {s!r}"
    if re.search(r"\bor\b", RE_QUOTE_AT.sub(" ", s)):
        return f"says or, so decides nothing: {s!r}"
    if any(a < refs[0][0] for a, _, _ in quotes):
        return f"«words» before any reference in {s!r}"
    out = []
    for i, (a, b, ref) in enumerate(refs):
        until = refs[i + 1][0] if i + 1 < len(refs) else len(s)
        qs = [q for qa, _, q in quotes if b <= qa < until]
        if len(qs) > 1:
            return f"two «quotes» after {ref}: one, or another reference"
        if qs and "-" in ref:
            return f"{ref}: a run of paragraphs is shown whole, without «words»"
        out.append((ref, qs[0] if qs else quiz.WHOLE))
    return out


def decide(item: dict, notes_at) -> tuple[str, list[tuple[str, str]]] | str:
    """(state, [(ref, quote)]) from a ruling, or what is wrong with it: the
    passages of the text in order; a note's paragraph and origin; none."""
    r = (item["ruling"] or "").strip()
    if not r:
        return "no ruling"
    word = r.split()[0].lower().rstrip(".,;:")
    cands = item["candidates"]
    if word in ("yes", "y"):
        if item["proposed"] in (None, "none"):
            return "yes, to no proposal"
        r = cands[item["proposed"]]
    elif RE_DIGITS.fullmatch(r):
        ks = re.findall(r"\d", r)
        missing = [k for k in ks if k not in cands]
        if missing:
            return f"no candidate {missing[0]}"
        picked = [cands[k] for k in ks]
        if len(picked) > 1 and any(c.startswith("note ") for c in picked):
            return "a note answers alone"
        r = " and ".join(picked)
    elif (m := RE_CANDIDATE_NAMED.search(r)):
        if m[1] not in cands:
            return f"no candidate {m[1]}"
        r = cands[m[1]]
    elif word in ("none", "drop"):
        return word, []
    elif not (word in ("no", "text", "ref", "note") or RE_REF_AT.match(r) or RE_REFERENCE_NAMED.search(r)):
        return f"cannot read {r!r}"
    if (m := RE_NOTE_RULE.match(r)):
        origins = notes_at(m[1])
        if m[2]:
            if m[2] not in origins:
                return f"no note {m[2]} at {m[1]}"
            return "note", [(m[1], m[2])]
        if len(origins) != 1:
            return f"{len(origins)} notes at {m[1]}: name one by its origin"
        return "note", [(m[1], origins[0])]
    if (m := RE_NOTE_WORDS.match(r)):
        origins = notes_at(m[1])
        return ("note", [(m[1], origins[0])]) if len(origins) == 1 else f"{len(origins)} notes at {m[1]}"
    got = references(r)
    return got if isinstance(got, str) else ("text", got)


def accepted(item: dict) -> dict:
    """The item with a blank ruling read as `yes` to its proposal, or `none`
    where nothing is proposed: Tigran's "Accepted" in chat (2026-10-28), and
    his blank rulings since (2026-10-29)."""
    if (item["ruling"] or "").strip():
        return item
    return {**item, "ruling": "yes" if item["proposed"] not in (None, "none") else "none"}


def pending_papers(lines: list[quiz.Line]) -> list[int]:
    """Every paper with a line still unreviewed."""
    return sorted({x.paper for x in lines if x.state == "-"})


def doubts() -> dict[int, dict]:
    """var/quiz/doubtful.md's questions, by id."""
    if not DOUBTS.exists():
        raise SystemExit(f"--doubts: no {DOUBTS.relative_to(ROOT)}: tools/quiz/doubt.py make writes it")
    return parse_review(DOUBTS)


def reviewed(papers: list[int], doubtful: dict[int, dict] | None):
    """Each question of each paper's review, in order: (paper, id, item), the
    item taken whole from doubtful.md where that holds the question; or a
    (paper, None, message) where a review is missing."""
    for n in papers:
        path = REVIEWS / f"review-{n:03d}.md"
        if not path.exists():
            yield n, None, f"no {path.relative_to(ROOT)}: tools/quiz/draft.py {n} makes it"
            continue
        items = parse_review(path)
        if doubtful:
            for qid in items.keys() & doubtful.keys():
                items[qid] = doubtful[qid]
        for qid, item in sorted(items.items(), key=lambda kv: kv[1]["q"]):
            yield n, qid, item


def _notes_at():
    from build.readers import study as sreader
    st = config.load()["study"]
    notes = sreader.read(st["tex"], st["at"], range(0, 197), Report())

    def notes_at(ref):
        return [nt.origin for p in notes.values() for nt in p.notes if nt.ref == ref]
    return notes_at


def cmd_rule(papers: list[int], accept: bool = False, from_doubts: bool = False) -> int:
    lines = ledger()
    by_id = {x.id: x for x in lines}
    if papers == ["pending"]:
        papers = pending_papers(lines)
    doubtful = doubts() if from_doubts else None
    notes_at = _notes_at()
    bad, done, taken = [], 0, set()
    for n, qid, item in reviewed(papers, doubtful):
        if qid is None:
            bad.append(f"Paper {n}: {item}")
            continue
        x = by_id.get(qid)
        if x is None or x.paper != n:
            bad.append(f"Paper {n} Q{item['q']}: id {qid} is no question of Paper {n}")
            continue
        if doubtful and qid in doubtful:
            taken.add(qid)
        if accept:
            item = accepted(item)
        got = decide(item, notes_at)
        if isinstance(got, str):
            bad.append(f"Paper {n} Q{item['q']} (id {qid}): {got}")
            continue
        x.state, x.refs = got
        done += 1
    if bad:
        print("Not written, until each of these is ruled or mended:")
        for b in bad:
            print(f"  {b}")
        return 1
    write(lines)
    print(f"{done} rulings of {len(papers)} paper{'s' * (len(papers) > 1)} written to"
          f" {LEDGER.relative_to(ROOT)} and {REFERENCES.relative_to(ROOT)}; `make data` holds them")
    if doubtful:
        print(f"{len(taken)} of {DOUBTS.relative_to(ROOT)}'s {len(doubtful)} questions among them")
    return 0


class _Collect:
    def __init__(self):
        self.said = []

    def hard(self, code, where, msg):
        self.said.append(msg)

    def warn(self, *a):
        pass


def hold(text: dict[str, str], state: str, refs: list[tuple[str, str]], where: str) -> tuple[list[str], list[str]]:
    """What the build would say of a text reference: (faults, warnings)."""
    if state != "text":
        return [], []
    faults, shown = [], 0
    for ref, quote in refs:
        r = _Collect()
        if quote == quiz.WHOLE:
            got = quiz._whole(text, ref, where, r)
            shown += sum(len(text[x]) for x in got) if got else 0
        elif ref not in text:
            r.said.append("no such paragraph")
        else:
            quiz._anchor(text[ref], quote, where, r)
            shown += len(quote)
        faults += [f"{ref}: {msg}" for msg in r.said]
    warnings = ([f"{shown} characters shown under the question, over {quiz.SHOWN_WARN}"]
                if shown > quiz.SHOWN_WARN else [])
    return faults, warnings


def cmd_check(papers: list[int], from_doubts: bool = False) -> int:
    import sqlite3
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    text = dict(con.execute("SELECT ref, text FROM paragraph"))
    if papers == ["pending"]:
        papers = pending_papers(ledger())
    doubtful = doubts() if from_doubts else None
    notes_at = _notes_at()
    bad = 0
    for n, qid, item in reviewed(papers, doubtful):
        if qid is None:
            print(f"Paper {n}: {item}")
            bad += 1
            continue
        got = decide(accepted(item), notes_at)
        where = f"Paper {n} Q{item['q']} (id {qid})"
        if isinstance(got, str):
            print(f"{where}: {got}")
            bad += 1
            continue
        faults, warnings = hold(text, *got, where)
        for msg in faults:
            print(f"{where}: {msg}")
        for msg in warnings:
            print(f"{where}: warning: {msg}")
        bad += len(faults)
    print("ok" if not bad else f"{bad} to mend")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["new"] and len(argv) == 1:
        return cmd_new()
    if argv[:1] == ["same"] and len(argv) in (3, 4) and argv[1].isdigit() and argv[2].isdigit():
        return cmd_same(int(argv[1]), int(argv[2]), argv[3:] == ["--answers"])
    if argv[:1] == ["gone"] and len(argv) == 2 and argv[1].isdigit():
        return cmd_gone(int(argv[1]))
    if argv[:1] in (["check"], ["rule"]):
        flags = {x for x in argv[1:] if x.startswith("--")}
        nums = [x for x in argv[1:] if not x.startswith("--")]
        papers = ["pending"] if nums == ["pending"] else [int(x) for x in nums if x.isdigit()]
        if papers and len(papers) == len(nums):
            if argv[0] == "check" and flags <= {"--doubts"}:
                return cmd_check(papers, "--doubts" in flags)
            if argv[0] == "rule" and flags <= {"--accept", "--doubts"}:
                return cmd_rule(papers, "--accept" in flags, "--doubts" in flags)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
