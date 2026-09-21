"""Read the Uversa Press papers into structured paragraphs.

Line-oriented, because the source is: one printed paragraph per physical line,
introduced by ``\\vs pNNN S:P``.  The exception is verse, which is set inside a
``quoting`` environment one line per ``\\par``, where only the first line of a
block prints its number (``\\printvssuper{N}``) and the rest are numbered by
position -- except in Paper 144, where every line carries an explicit
``\\vsmark{S}{P}`` that always wins.

Splitting on ``\\vs`` alone yields 14,442 paragraphs and silently swallows the
144 verses of 48:6.9-19, 122:9.5-27 and 144:5.2-101 into the preceding prose.
The real total is 14,586.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

from ..expand import Expander, Expanded
from ..press_macros import (ITALIC_OPENING_MACROS, KNOWN_ENVIRONMENTS, TABLE,
                            UNBRACED_LENGTH_MACROS, ITALIC_OPENING_MACROS)
from ._io import read_text

RE_VS       = re.compile(r"\\vs p(\d+) (\d+):(\d+) ?")
RE_UPAPER   = re.compile(r"^\\upaper\{(\d+)\}\{")
RE_AUTHOR   = re.compile(r"^\\author\{")
RE_USECTION = re.compile(r"^\\usection(two)?\b")
RE_SUPER    = re.compile(r"\\printvssuper\{(\d+)\}")
RE_MARK     = re.compile(r"\\vsmark\{(\d+)\}\{(\d+)\}")
RE_LAYOUT   = re.compile(r"\\hspace\*?\{[^{}]*\}|\\setlength\{[^{}]*\}\{[^{}]*\}"
                         r"|\\par\b|\\parindent|\\relax")


@dataclasses.dataclass(slots=True)
class Paragraph:
    paper: int
    section: int
    n: int
    src: str                # 'vs' | 'poetry' | 'vsmark'
    line: int
    ex: Expanded

    @property
    def ref(self) -> str:
        return f"{self.paper}:{self.section}.{self.n}"


@dataclasses.dataclass(slots=True)
class Paper:
    n: int
    title: str
    author: str | None
    sections: dict[int, str]       # section number -> title ('' for the introduction)
    paragraphs: list[Paragraph]


def _brace_arg(s: str, start: int) -> tuple[str, int]:
    """Read a balanced {...} beginning at s[start] == '{'."""
    depth, i = 0, start
    while i < len(s):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
        elif c == "\\":
            i += 1
        i += 1
    raise ValueError(f"unbalanced brace at {start}")


def _skip_optional(s: str, i: int) -> int:
    while i < len(s) and s[i] == "[":
        depth = 0
        while i < len(s):
            if s[i] == "[":
                depth += 1
            elif s[i] == "]":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
    return i


def read_paper(path: pathlib.Path, report) -> Paper:
    where = path.name
    exp = Expander(TABLE, KNOWN_ENVIRONMENTS, report, where,
                   UNBRACED_LENGTH_MACROS, ITALIC_OPENING_MACROS)
    src = read_text(path)

    paper_n, title, author = None, None, None
    sections: dict[int, str] = {}
    secnum = 0
    paras: list[Paragraph] = []
    in_block, counter, cur_sec = False, None, 0
    pending: list[str] = []

    def inline(text: str) -> Expanded:
        return exp.run(text)

    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue

        m = RE_UPAPER.match(line)
        if m:
            paper_n = int(m.group(1))
            i = line.index("{", line.index("}") + 1) if False else None
            _, j = _brace_arg(line, line.index("{"))
            title = inline(_brace_arg(line, j)[0]).text.strip()
            continue

        if RE_AUTHOR.match(line):
            author = inline(_brace_arg(line, line.index("{"))[0]).text.strip()
            continue

        m = RE_USECTION.match(line)
        if m:
            i = _skip_optional(line, m.end())
            body, j = _brace_arg(line, line.index("{", i - 1) if line[i:i+1] != "{" else i)
            if m.group(1):                      # \usectiontwo{L}{Title}: counter +2
                body, _ = _brace_arg(line, j)
                secnum += 2
                sections[secnum - 1] = sections[secnum] = \
                    inline(body.replace("\\\\", " ")).text.strip()
            else:
                secnum += 1
                sections[secnum] = re.sub(
                    r"\s+", " ", inline(body.replace("\\\\", " ")).text).strip()
            continue

        m = RE_VS.search(line)
        if m:
            p, s, n = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if paper_n is not None and p != paper_n:
                report.hard("paper-mismatch", f"{where}:{lineno}",
                            f"\\vs says paper {p}, file is {paper_n}")
            cur_sec = s
            prefix, body = line[:m.start()], line[m.end():]
            ex = inline(body)
            if prefix.strip():
                ex.flags.update(inline(prefix).flags)
            paras.append(Paragraph(p, s, n, "vs", lineno, ex))
            continue

        m = re.match(r"\\(begin|end)\{(\w+)\}", line)
        if m:
            env = m.group(2)
            if env not in KNOWN_ENVIRONMENTS:
                report.hard("unknown-environment", f"{where}:{lineno}",
                            f"\\{m.group(1)}{{{env}}} not in the table")
            elif env == "quoting":
                in_block = (m.group(1) == "begin")
                if in_block:
                    counter = None
            continue

        if line.startswith("\\makeatletter"):
            continue

        if in_block:
            body = line
            mm = RE_SUPER.search(body)
            if mm:
                counter = int(mm.group(1))
                body = body[:mm.start()] + body[mm.end():]
            mk = RE_MARK.search(body)
            if mk:
                sec, num, kind = int(mk.group(1)), int(mk.group(2)), "vsmark"
                body = body[:mk.start()] + body[mk.end():]
            else:
                sec, num, kind = cur_sec, counter, "poetry"
            body = RE_LAYOUT.sub("", body).strip()
            if not body:
                continue
            if num is None:
                report.hard("verse-unnumbered", f"{where}:{lineno}",
                            "verse text with no number in scope")
                continue
            paras.append(Paragraph(paper_n, sec, num, kind, lineno, inline(body)))
            counter = num + 1
            continue

        # Anything else is a layout line.  Nothing may be silently dropped.
        if RE_LAYOUT.fullmatch(line) or line.startswith((
                "\\vsetoff", "\\vspace", "\\clp", "\\need", "\\separator",
                "\\makeatletter", "\\makeatother", "\\write", "\\hsetoff",
                "%", "{\\setlength", "}")):
            continue
        pending.append(f"{where}:{lineno}: {line[:70]}")

    for p in pending:
        report.warn("unclaimed-line", p.split(":")[0] + ":" + p.split(":")[1],
                    p.split(": ", 1)[1])

    if not sections and paras:
        sections = {}
    sections.setdefault(0, "")
    return Paper(paper_n, title, author, sections, paras)


def read_all(texdir: pathlib.Path, report) -> list[Paper]:
    return [read_paper(f, report) for f in sorted(texdir.glob("p[0-9][0-9][0-9].tex"))]
