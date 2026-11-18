"""Keep the list of the home page's passages of the moment, data/passages.tsv
(build/passage.py; DECISIONS.md, The home page).

    .venv/bin/python tools/passages/apply.py check FILE [FILE ...]
        Writes nothing: holds each line of a file of candidates, ref<TAB>words,
        to the build's rules (the paragraph is there; the words are in it once,
        whole, a sentence's beginning to a sentence's end, no longer than the
        card holds), and says which fail and why.
    .venv/bin/python tools/passages/apply.py draft FILE [FILE ...]
        var/passages/review.md, for Tigran to rule on: every candidate of the
        files that passes, in the book's order, none twice, each with a
        `Ruling:` line.  It never overwrites a review.
    .venv/bin/python tools/passages/apply.py add FILE [FILE ...]
        More candidates for the same review, as a part of their own at its
        end, numbered on from its last: those of the files that pass and are
        not in it yet.  Nothing above them is changed.
    .venv/bin/python tools/passages/apply.py rule [--accept]
        The rulings of var/passages/review.md written into data/passages.tsv:
        `yes` takes the passage as proposed, `no` leaves it out, and other
        words of the same paragraph between « » are the passage instead.  A
        line he left empty is not ruled and is left out; with --accept it takes
        what is proposed, for a look at the page before he has ruled, and the
        list then says so in its first line and is not to be committed.  Lists
        what it cannot read or the build would refuse, and then writes nothing.

A part of the review (a `# ` heading and the candidates under it) that he took
whole says so before its first candidate, in a line of its own that quotes him:

    Taken as proposed: Tigran, 2026-11-18: "..."

Its lines left empty are then taken as proposed, and a `no` or his own words
on any of them still rule that one.  The line is his word, written down; it is
never added for him.

Reads var/ub.db for the paragraphs; writes only var/passages/review.md and
data/passages.tsv.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from build import passage  # noqa: E402
from build.quiz import WHOLE  # noqa: E402

DB = ROOT / "var" / "ub.db"
REVIEW = ROOT / "var" / "passages" / "review.md"
HEAD = """\
# The home page's passages of the moment: build/passage.py, DECISIONS.md.
# Kept by tools/passages/apply.py from Tigran's rulings in var/passages/review.md,
# never by hand: each a paragraph and the words of it shown, or ¶ for it whole.
"""
UNRULED = "# NOT YET RULED: made with --accept, for a look at the page; not to be committed.\n"
RE_BLOCK = re.compile(r"^## (\d+)\. (\d+:\d+\.\d+)\b.*$", re.M)
RE_PART = re.compile(r"^# .*$", re.M)
RE_TAKEN = re.compile(r"^Taken as proposed: *\S.*$", re.M)
PARTS = {None: "Foreword", 1: "Part I", 2: "Part II", 3: "Part III", 4: "Part IV"}


def texts() -> dict:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return {r: (o, t, p, title, part) for r, o, t, p, title, part in con.execute(
        "SELECT g.ref, g.ord, g.text, g.paper_n, p.title, p.part_n FROM paragraph g JOIN paper p ON p.n = g.paper_n")}


def held(para: dict, ref: str, words: str) -> str:
    """Why the build would refuse these words of this paragraph, or ''."""
    if ref not in para:
        return "no such paragraph"
    text = para[ref][1]
    full = text if words == WHOLE else words
    start, why = passage.anchor(text, full)
    if start is None:
        return why
    if len(full) > passage.LONGEST:
        return f"{len(full)} characters, and the card holds {passage.LONGEST}"
    return ""


def candidates(files: list[str], para: dict) -> tuple[list[tuple[str, str]], list[str]]:
    good, bad, seen = [], [], set()
    for name in files:
        for n, raw in enumerate(pathlib.Path(name).read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip() or raw.startswith("#"):
                continue
            f = raw.split("\t")
            if len(f) < 2 or not f[0].strip() or not f[1].strip():
                bad.append(f"{name}:{n}: ref<TAB>words")
                continue
            ref, words = f[0].strip(), f[1].strip()
            why = held(para, ref, words)
            if why:
                bad.append(f"{name}:{n}: {ref} {words[:60]!r}...: {why}")
            elif (ref, words) not in seen:
                seen.add((ref, words))
                good.append((ref, words))
    return good, bad


def check(files: list[str]) -> int:
    good, bad = candidates(files, texts())
    for b in bad:
        print(b)
    print(f"{len(good)} hold, {len(bad)} do not")
    return 1 if bad else 0


def draft(files: list[str]) -> int:
    if REVIEW.exists():
        print(f"{REVIEW.relative_to(ROOT)} is there, and is never overwritten", file=sys.stderr)
        return 1
    para = texts()
    good, bad = candidates(files, para)
    for b in bad:
        print(b, file=sys.stderr)
    good.sort(key=lambda g: (para[g[0]][0], para[g[0]][1].find(g[1])))
    out = ["# Passages of the moment: candidates for your ruling\n",
           "The home page shows one of these at each visit. On each `Ruling:` line write `yes` or `no`; or, to show other"
           " words of the same paragraph, write them between « and ». A line left empty is not ruled, and its passage is"
           " not shown. Each passage is whole sentences of one paragraph, as the text has them.\n",
           f"{len(good)} candidates, in the book's order.\n"]
    for i, (ref, words) in enumerate(good, 1):
        _, text, paper, title, part = para[ref]
        shown = text if words == WHOLE else words
        out.append(f"## {i}. {ref} · {title} ({PARTS[part]})\n\n> {shown}\n\nRuling: \n")
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(good)} candidates written to {REVIEW.relative_to(ROOT)}; {len(bad)} left out, which do not hold")
    return 0


def blocks(src: str):
    """Each candidate of a review: its heading's match, what is under it, and
    whether its part was taken as proposed."""
    heads = list(RE_BLOCK.finditer(src))
    parts = [m.start() for m in RE_PART.finditer(src)]
    for k, m in enumerate(heads):
        end = min([heads[k + 1].start() if k + 1 < len(heads) else len(src)] + [p for p in parts if p > m.end()])
        part = max((p for p in parts if p < m.start()), default=0)
        first = next(h.start() for h in heads if h.start() > part)
        yield m, src[m.end():end], bool(RE_TAKEN.search(src, part, first))


def proposed_of(body: str) -> str:
    return " ".join(l[2:].strip() for l in body.splitlines() if l.startswith("> "))


def add(files: list[str]) -> int:
    if not REVIEW.exists():
        print(f"no {REVIEW.relative_to(ROOT)}: `draft` makes it", file=sys.stderr)
        return 1
    para = texts()
    src = REVIEW.read_text(encoding="utf-8")
    have, last = set(), 0
    for m, body, _ in blocks(src):
        have.add((m[2], proposed_of(body)))
        last = max(last, int(m[1]))
    good, bad = candidates(files, para)
    for b in bad:
        print(b, file=sys.stderr)
    shown = lambda g: para[g[0]][1] if g[1] == WHOLE else g[1]
    new = sorted((g for g in good if (g[0], shown(g)) not in have), key=lambda g: (para[g[0]][0], para[g[0]][1].find(shown(g))))
    if not new:
        print("nothing to add: every candidate that holds is in the review")
        return 1 if bad else 0
    out = [f"\n# More candidates, added {datetime.date.today().isoformat()}\n",
           f"{len(new)} candidates, in the book's order, ruled as those above are.\n"]
    for i, g in enumerate(new, last + 1):
        _, _, _, title, part = para[g[0]]
        out.append(f"## {i}. {g[0]} · {title} ({PARTS[part]})\n\n> {shown(g)}\n\nRuling: \n")
    REVIEW.write_text(src.rstrip("\n") + "\n" + "\n".join(out), encoding="utf-8")
    print(f"{len(new)} candidates added to {REVIEW.relative_to(ROOT)}, {last + 1} to {last + len(new)};"
          f" {len(good) - len(new)} were in it, {len(bad)} do not hold")
    return 0


def rule(accept: bool) -> int:
    if not REVIEW.exists():
        print(f"no {REVIEW.relative_to(ROOT)}: `draft` makes it", file=sys.stderr)
        return 1
    para = texts()
    src = REVIEW.read_text(encoding="utf-8")
    rows, bad, counts = [], [], {"yes": 0, "no": 0, "his words": 0, "whole": 0, "unruled": 0}
    for m, body, whole in blocks(src):
        ref, at = m[2], f"review.md, {m[1]}. {m[2]}"
        proposed = proposed_of(body)
        got = re.findall(r"^Ruling:(.*)$", body, re.M)
        if len(got) != 1 or not proposed:
            bad.append(f"{at}: one passage after '> ' and one Ruling: line")
            continue
        said = got[0].strip()
        own = re.fullmatch(r"«(.+)»\.?", said)
        if own:
            words, kind = own[1].strip(), "his words"
        elif re.fullmatch(r"yes\b.*", said, re.I):
            words, kind = proposed, "yes"
        elif re.fullmatch(r"no\b.*", said, re.I):
            counts["no"] += 1
            continue
        elif not said and whole:
            words, kind = proposed, "whole"
        elif not said:
            counts["unruled"] += 1
            if not accept:
                continue
            words, kind = proposed, None
        else:
            bad.append(f"{at}: {said[:50]!r} is neither yes, no, nor words between « and »")
            continue
        why = held(para, ref, words)
        if why:
            bad.append(f"{at}: {words[:60]!r}...: {why}")
            continue
        if kind:
            counts[kind] += 1
        rows.append((para[ref][0], para[ref][1].find(words), ref, WHOLE if words == para[ref][1] else words))
    if bad:
        for b in bad:
            print(b, file=sys.stderr)
        print("nothing written", file=sys.stderr)
        return 1
    rows = sorted(set(rows))
    lines = "".join(f"{ref}\t{words}\n" for _, _, ref, words in rows)
    taken = accept and counts["unruled"]
    passage.LIST.write_text(HEAD + (UNRULED if taken else "") + "ref\tquote\n" + lines, encoding="utf-8")
    print(f"{len(rows)} passages written to data/{passage.LIST.name}: {counts['yes']} ruled yes, {counts['whole']} in a part"
          f" taken as proposed, {counts['his words']} in his own words, {counts['no']} ruled no, {counts['unruled']} not ruled"
          + (", taken as proposed: NOT to be committed" if taken else ", left out"))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "check":
        return check(argv[1:])
    if len(argv) >= 2 and argv[0] == "draft":
        return draft(argv[1:])
    if len(argv) >= 2 and argv[0] == "add":
        return add(argv[1:])
    if argv and argv[0] == "rule" and set(argv[1:]) <= {"--accept"}:
        return rule("--accept" in argv)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
