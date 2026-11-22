"""The quiz, converted once from The British Study Edition into data/quiz/.

    .venv/bin/python -m tools.quiz.convert              write data/quiz/NNN.toml
    .venv/bin/python -m tools.quiz.convert --out DIR    write them into DIR instead

The site's quiz began as the edition's Cosmic Citizenship Quiz, tex/quiz.tex,
read at each build from 2026-10-28, its spelling made American by a table and
each question held to a ledger of ids and rulings kept here.  On 2026-11-22
Tigran gave the edition up: "we don't need to import questions from that
quiz.tex anymore, as I no longer wish to maintain the British Study Edition --
its essence will migrate into ubsite."  So the quiz was converted once, as the
KJV was (tools/kjv/convert.py), and data/quiz/ has been the master since:
build/quiz.py reads it alone, and quiz.tex is never read again.

What it reads, both fixed here so that the conversion can be run again and
come out the same:

  * quiz.tex at QUIZ_AT, the edition's last commit, through build/readers/_io
    (the only module that may open a source path);
  * this repository's own ledger as it stood at LEDGER_AT, the last commit
    that built the quiz from quiz.tex, by `git show`: data/quiz/questions.tsv
    (each question's id, paper, v and state, matched to its question by the
    SHA-256 of the question as written), references.tsv (what answers it) and
    american.tsv (the British spellings and the book's).

What it writes, a file to each paper that has a question or had one: each
question as the site showed it, in the order quiz.tex gives them, its spelling
made American by the table, its dates put in the book's order ("25 March 7
B.C." is "March 25, 7~B.C."), and its quotation marks and apostrophes the
Unicode ones TeX's `` '' ` ' made (outside math), so that every string is a
plain TOML literal; with its id, its v where not 1, its right answers by
their words, and its references in the words of a ruling, `1:1.2 «quoted
words»` or `0:3.2-8` shown whole.  The ids of the five questions deleted
upstream stay taken, in their papers' `gone`.  data/quiz/README.md says what
each field means.

It proves itself before writing: every question and answer, expanded as the
build expands it, gives the text and HTML the build made from quiz.tex, byte
for byte; every file parses back to what was meant; and nothing is written
where a file is already.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sqlite3
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import config, quiz, quiz_macros, study  # noqa: E402
from build.problems import Report              # noqa: E402
from build.readers import _io                  # noqa: E402
from build.spec import EMIT_TEXT, Spec         # noqa: E402
from build.readers.study import brace_end, digest, unescaped  # noqa: E402

QUIZ_AT = "0a1f055"          # the study edition's quiz.tex, as last read (2026-11-18)
LEDGER_AT = "0696b8d"        # this repository, the last commit to build the quiz from it
OUT = ROOT / "data" / "quiz"
DB = ROOT / "var" / "ub.db"

# -- quiz.tex, as build/readers/quiz.py read it until the conversion -------------

PAPERS = range(0, 197)
RE_QPAPER = re.compile(r"\\qpaper\{(\d+)\}\{(.*)\}")
RE_FLAG = re.compile(r"\{([01])\}")


class Question:
    __slots__ = ("paper", "line", "tex", "answers", "raw")

    def __init__(self, paper, line, tex, answers, raw):
        self.paper, self.line, self.tex, self.answers, self.raw = paper, line, tex, answers, raw

    @property
    def origin(self) -> str:
        """16 hex digits of the SHA-256 of the question as written, whitespace
        collapsed: what the ledger matched a question by."""
        return digest(" ".join(self.raw.split()))


def parse(src: str, report) -> list[Question]:
    """quiz.tex's questions, each as written: every line one of its shapes,
    or blank, and anything else fails."""
    out: list[Question] = []
    papers: list[int] = []
    q: dict | None = None
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        at = f"quiz.tex:{lineno}"
        if not line or line == "\\quizheader":
            continue
        if unescaped(line, "%"):
            report.hard("quiz-comment", at, "a % TeX would read as a comment")
            continue
        m = RE_QPAPER.fullmatch(line)
        if m and not q:
            papers.append(int(m[1]))
            continue
        if line.startswith("\\qstart") and not q and papers:
            e = brace_end(line, len("\\qstart"))
            if line[e:].strip():
                report.hard("quiz-stray", at, line)
            q = {"line": lineno, "tex": line[len("\\qstart") + 1:e - 1], "answers": [], "raw": [line]}
            continue
        if line == "\\qstop" and q:
            q["raw"].append(line)
            out.append(Question(papers[-1], q["line"], q["tex"], tuple(q["answers"]), "\n".join(q["raw"])))
            q = None
            continue
        if line.startswith("{") and q:
            e = brace_end(line, 0)
            f = RE_FLAG.fullmatch(line[e:])
            if f:
                q["answers"].append((line[1:e - 1], f[1] == "1"))
                q["raw"].append(line)
                continue
        report.hard("quiz-stray", at, f"a line nothing claims: {line[:60]}")
    if papers != list(PAPERS) or q:
        report.hard("quiz-papers", "quiz.tex", "every paper, 0 to 196, in order, each question closed")
    return out


# -- the rewrites the build made of it ------------------------------------------

MONTHS = ("January|February|March|April|May|June|July|August|September|October"
          "|November|December")
WEEKDAY = r"(?:Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)day"
_SEP = r"(?:\\,|~| )"
_ORD = r"(\d{1,2})(?:\\ts\{(?:st|nd|rd|th)\})?"
_YEAR = r"(\d{1,3}(?:,\d{3})+|\d+)"
# A day, its month and a year, with the era: "25 March 7 B.C.", "Tuesday 4
# April 30 A.D.", "11\ts{th} February, 2\,B.C.".
RE_DAY_DATE = re.compile(rf"(?:({WEEKDAY}),? )?{_ORD} ({MONTHS}),? {_YEAR}{_SEP}(B\.C\.|A\.D\.)")
# A year alone: "300 A.D.", "76\,A.D.", "37,000 B.C.".
RE_YEAR = re.compile(rf"(?<![\d,]){_YEAR}{_SEP}(B\.C\.|A\.D\.)")


def americanize(tex: str, table: dict[str, str], used: set[str]) -> str:
    """Each British word or phrase of the table, whole, in any case, the case
    kept: Centre is Center.  Never a command's name: \\centre is not a word."""
    for brit, am in table.items():
        rx = re.compile(r"(?<![\\A-Za-z])" + re.escape(brit).replace(r"\ ", "[ ~]") + r"(?![A-Za-z])",
                        re.IGNORECASE)

        def sub(m, am=am, brit=brit):
            used.add(brit)
            w = m.group()
            if w.isupper() and len(w) > 1:
                return am.upper()
            if w[0].isupper():
                return am[0].upper() + am[1:]
            return am
        tex = rx.sub(sub, tex)
    return tex


def dates(tex: str) -> str:
    """A date in the book's order, its era beside the year with a tie, as the
    book sets it (122:8.1 "August 21, 7 B.C.", 124:6.1 "April 9, A.D. 7")."""
    def day(m):
        weekday, d, month, year, era = m.groups()
        when = f"{year}~B.C." if era == "B.C." else f"A.D.~{year}"
        return (f"{weekday}, " if weekday else "") + f"{month} {int(d)}, {when}"

    def year(m):
        y, era = m.groups()
        return f"{y}~B.C." if era == "B.C." else f"A.D.~{y}"
    return RE_YEAR.sub(year, RE_DAY_DATE.sub(day, tex))


# The macros quiz.tex used, as build/quiz_macros.py had them when it was read:
# the build's table has lost \textasciitilde since, its one "~" mended.
TABLE = {**quiz_macros.TABLE,
         "textasciitilde": Spec(EMIT_TEXT, text="~", note="\"~135 million\", id 479")}


def expand(tex: str, where: str, report) -> tuple[str, str]:
    """As build/quiz.py expanded a question, with the table it had then."""
    text, html, _ = study.expand(tex, {}, {}, where, report, table=TABLE,
                                 subs=quiz_macros.SUBS, ties=False)
    return text, html


def curly(tex: str) -> str:
    """TeX's quotation marks and apostrophes as the characters they make,
    outside math: `` '' ` ' are “ ” ‘ ’."""
    parts = re.split(r"(\$[^$]*\$)", tex)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("``", "“").replace("''", "”").replace("`", "‘").replace("'", "’")
    return "".join(parts)


# -- the ledger, at LEDGER_AT -----------------------------------------------------

def at_ledger(name: str) -> list[list[str]]:
    """A TSV of data/quiz/ as it stood at LEDGER_AT: its rows, past comments and header."""
    src = subprocess.run(["git", "-C", str(ROOT), "show", f"{LEDGER_AT}:data/quiz/{name}"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    rows = [r.split("\t") for r in src.splitlines() if r.strip() and not r.startswith("#")]
    return rows[1:]


# -- TOML ---------------------------------------------------------------------------

def lit(s: str) -> str:
    """A TOML string: a literal, '...', wherever it can be one."""
    if "'" not in s and "\n" not in s and not any(ord(c) < 32 for c in s):
        return f"'{s}'"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def array(key: str, items: list[str]) -> str:
    if len(items) == 1 and key != "a":
        return f"{key} = [{lit(items[0])}]\n"
    return f"{key} = [\n" + "".join(f"  {lit(x)},\n" for x in items) + "]\n"


def ref_words(ref: str, quote: str) -> str:
    return ref if quote == quiz.WHOLE else f"{ref} «{quote}»"


FIGURE = range(40, 47)       # the Foreword's Q40-Q46, the Existential Flower


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    args = ap.parse_args(argv)
    report = Report()

    st = config.load()["study"]
    src = _io.read_tex(st["tex"], "quiz.tex", QUIZ_AT)
    qs = parse(src, report)
    american = {b: a for b, a in at_ledger("american.tsv")}
    lines = [(int(i), int(p), o, int(v), s) for i, p, o, v, s in at_ledger("questions.tsv")]
    refs = collections.defaultdict(list)
    for i, n, ref, quote in at_ledger("references.tsv"):
        refs[int(i)].append((int(n), ref, quote))

    # Each question its line, by origin, in order: two questions of 137 are one
    # question asked twice, ids 749 and 750.
    live = collections.defaultdict(collections.deque)
    gone = collections.defaultdict(list)
    for i, p, o, v, s in lines:
        (gone[p].append(i) if s == "gone" else live[o].append((i, p, v, s)))
    used: set[str] = set()
    papers: dict[int, list[dict]] = collections.defaultdict(list)
    for q in qs:
        i, p, v, s = live[q.origin].popleft()
        assert p == q.paper, (i, p, q.paper)

        def setting(tex):
            old = expand(dates(americanize(tex, american, used)), f"quiz.tex:{q.line}", report)
            new_tex = curly(dates(americanize(tex, american, set())))
            if expand(new_tex, f"quiz.tex:{q.line}", report) != old:
                report.hard("convert-differs", f"quiz.tex:{q.line}", new_tex)
            return new_tex
        answers = [(setting(t), r) for t, r in q.answers]
        texts = [t for t, _ in answers]
        if len(set(texts)) != len(texts):
            report.hard("convert-answers", f"quiz.tex:{q.line}", "two answers with the same words")
        rows = [(ref, quote) for _, ref, quote in sorted(refs.pop(i, []))]
        papers[p].append({"id": i, "v": v, "state": s, "q": setting(q.tex), "a": texts,
                          "right": [t for t, r in answers if r], "refs": rows})
    leftover = [x for xs in live.values() for x in xs]
    if leftover or refs or set(american) - used:
        report.hard("convert-leftover", "ledger", f"{leftover} {dict(refs)} {set(american) - used}")
    if report.blocking:
        for p in report.blocking:
            print(f"  {p.code} {p.where}: {p.message}")
        return 1

    titles = {}
    if DB.exists():
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        titles = dict(con.execute("SELECT n, title FROM paper"))
    args.out.mkdir(parents=True, exist_ok=True)
    files = {}
    for p in sorted(set(papers) | set(gone)):
        out = [f"# Paper {p}, {titles.get(p, '')}: its questions in the quiz (data/quiz/README.md).\n",
               f"# Converted from the British Study Edition's quiz.tex at {QUIZ_AT} on 2026-11-22\n",
               "# (tools/quiz/convert.py); the master since.\n\n",
               f"paper = {p}\n"]
        if gone[p]:
            out.append(f"gone = [{', '.join(map(str, sorted(gone[p])))}]       # deleted, their ids kept for ever\n")
        for x in papers[p]:
            out.append("\n[[question]]\n")
            if x["id"] in FIGURE:
                out.append("# Dropped until the figure it asks about, 0:3.10's, is on the site.\n")
            out.append(f"id = {x['id']}\n")
            if x["v"] != 1:
                out.append(f"v = {x['v']}\n")
            out.append(f"q = {lit(x['q'])}\n")
            out.append(array("a", x["a"]))
            out.append(array("right", x["right"]))
            if x["state"] == "text":
                out.append(array("refs", [ref_words(r, w) for r, w in x["refs"]]))
            elif x["state"] == "note":
                (r, o), = x["refs"]
                out.append(f"note = {lit(f'{r} {o}')}\n")
            elif x["state"] in ("none", "drop"):
                out.append(f"state = {lit(x['state'])}\n")
            else:
                raise SystemExit(f"id {x['id']}: state {x['state']!r}")
        files[f"{p:03d}.toml"] = "".join(out)

    # What was meant, read back.
    for name, text in files.items():
        d = tomllib.loads(text)
        p = int(name[:3])
        want = papers[p]
        got = d.get("question", [])
        assert [g["id"] for g in got] == [x["id"] for x in want], name
        for g, x in zip(got, want):
            assert (g["q"], g["a"], g["right"]) == (x["q"], x["a"], x["right"]), (name, x["id"])
            assert g.get("v", 1) == x["v"], (name, x["id"])
        assert d.get("gone", []) == sorted(gone[p]), name
    there = [n for n in files if (args.out / n).exists()]
    if there:
        print(f"refused: {args.out} has {', '.join(there[:5])}{' ...' * (len(there) > 5)} already")
        return 1
    for name, text in files.items():
        target = args.out / name
        target.write_text(text, encoding="utf-8")
    n_q = sum(len(v) for v in papers.values())
    print(f"{len(files)} files, {n_q} questions, {sum(map(len, gone.values()))} ids gone -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
