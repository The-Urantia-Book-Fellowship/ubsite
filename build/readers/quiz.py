"""Read the British Study Edition's quiz, tex/quiz.tex, as written.

Pure: file -> dataclasses, through _io only.  Nothing here expands, rewrites or
judges a question; build/quiz.py does, and holds each to its line in
data/quiz/questions.tsv by the hash this reader gives it.

The file is the Cosmic Citizenship Quiz the edition's PDF sets at its end,
each question on a page of its own:

    \\quizheader
    \\qpaper{0}{Foreword}
    \\qstart{What is the name of our own world?}
    {Mars}{0}
    {Urantia}{1}
    \\qstop

`\\qpaper` names every paper, 0 to 196 in order, those without questions too;
its title is the edition's, British, and the site gives the press's instead.
Every line is one of those shapes, or blank: anything else fails, and so does
a `%`, which TeX would read as a comment where a reader might not.  An
argument's braces are counted, never matched with `[^}]+` (trap 12).
"""

from __future__ import annotations

import dataclasses
import re

from ._io import read_tex
from .study import brace_end, digest, unescaped

PAPERS = range(0, 197)
RE_QPAPER = re.compile(r"\\qpaper\{(\d+)\}\{(.*)\}")
RE_FLAG = re.compile(r"\{([01])\}")


@dataclasses.dataclass(frozen=True, slots=True)
class Question:
    paper: int
    ord: int                       # its place among the paper's questions, from 1
    line: int                      # of its \qstart in quiz.tex
    tex: str                       # the question, between the braces, as written
    answers: tuple[tuple[str, bool], ...]    # (TeX as written, right), in order
    raw: str                       # \qstart ... \qstop as written

    @property
    def origin(self) -> str:
        """16 hex digits of the SHA-256 of the question as written, whitespace
        collapsed: an edit upstream moves it, a change to our own tables never."""
        return digest(" ".join(self.raw.split()))

    @property
    def mask(self) -> int:
        return sum(1 << i for i, (_, r) in enumerate(self.answers) if r)


def parse(src: str, report, where: str = "quiz.tex") -> list[Question]:
    out: list[Question] = []
    papers: list[int] = []
    header = 0
    q: dict | None = None
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        at = f"{where}:{lineno}"
        if not line:
            continue
        if unescaped(line, "%"):
            report.hard("quiz-comment", at, "a % TeX would read as a comment")
            continue
        if line == "\\quizheader":
            header += 1
            if header > 1 or papers or q:
                report.hard("quiz-header", at, "\\quizheader once, before everything else")
            continue
        m = RE_QPAPER.fullmatch(line)
        if m:
            if q:
                report.hard("quiz-unclosed", at, f"the question at line {q['line']} has no \\qstop")
                q = None
            n = int(m[1])
            if n != (papers[-1] + 1 if papers else 0):
                report.hard("quiz-paper-order", at, f"\\qpaper{{{n}}} after {papers[-1:] or 'none'}")
            papers.append(n)
            continue
        if line.startswith("\\qstart"):
            if q:
                report.hard("quiz-unclosed", at, f"the question at line {q['line']} has no \\qstop")
            if not papers:
                report.hard("quiz-no-paper", at, "a question before any \\qpaper")
                q = None
                continue
            try:
                e = brace_end(line, len("\\qstart"))
            except ValueError:
                report.hard("quiz-unbalanced", at, line[:60])
                q = None
                continue
            if line[e:].strip():
                report.hard("quiz-stray", at, f"after the question: {line[e:][:40]!r}")
            q = {"line": lineno, "tex": line[len("\\qstart") + 1:e - 1], "answers": [],
                 "raw": [line]}
            continue
        if line == "\\qstop":
            if not q:
                report.hard("quiz-stray", at, "\\qstop with no question open")
                continue
            q["raw"].append(line)
            n = papers[-1]
            prev = [x for x in out if x.paper == n]
            wq = f"{where}:{q['line']}"
            if len(q["answers"]) < 2:
                report.hard("quiz-answers", wq, f"{len(q['answers'])} answers: a question has two or more")
            if not any(r for _, r in q["answers"]):
                report.hard("quiz-no-right", wq, "no answer marked right")
            out.append(Question(n, len(prev) + 1, q["line"], q["tex"], tuple(q["answers"]),
                                "\n".join(q["raw"])))
            q = None
            continue
        if line.startswith("{") and q:
            try:
                e = brace_end(line, 0)
            except ValueError:
                report.hard("quiz-unbalanced", at, line[:60])
                continue
            f = RE_FLAG.fullmatch(line[e:])
            if not f:
                report.hard("quiz-answer", at, f"an answer is {{text}}{{0}} or {{text}}{{1}}: {line[:60]}")
                continue
            q["answers"].append((line[1:e - 1], f[1] == "1"))
            q["raw"].append(line)
            continue
        report.hard("quiz-stray", at, f"a line nothing claims: {line[:60]}")
    if q:
        report.hard("quiz-unclosed", f"{where}:{q['line']}", "the last question has no \\qstop")
    if papers != list(PAPERS):
        report.hard("quiz-papers", where, f"\\qpaper for {len(papers)} papers, not 0 to 196 in order")
    if header != 1:
        report.hard("quiz-header", where, f"{header} \\quizheader, not one")
    return out


def read(texdir, rev: str, report) -> list[Question] | None:
    """Every question of the quiz at `rev`, or None if the edition has none."""
    src = read_tex(texdir, "quiz.tex", rev)
    if src is None:
        return None
    return parse(src, report)
