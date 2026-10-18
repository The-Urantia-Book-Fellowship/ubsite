"""Read the British Study Edition's notes and bibliographies, as written.

Pure: file -> dataclasses, through _io only.  Nothing here expands or judges a
note; build/study.py takes the reviewed copies in data/study/ and holds each to
the note it was made from, by the hash this reader gives the original.

The study edition's own extractors read a note with `\\\\fnst{([^}]+)}` and lose
the end of every note with a brace inside it, about two in three (trap 12).
This one counts braces, skips each escaped character (`\\\\{`, `\\\\}`, `\\\\%`), and
refuses what it cannot be sure of: a `%` on a line with a note, which TeX
would read as a comment and a reader might not; a note anywhere but on a
`\\\\vs` line; a bibliography in anything but the one wrapper all nineteen
share.  A note never spans a line: `\\\\fnst` is not `\\\\long`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re

from ._io import read_tex_many

RE_VS = re.compile(r"(?:\\pc\s+)?\\vs p(\d+) (\d+):(\d+) ?")
RE_FNST = re.compile(r"\\fnst(?![A-Za-z])")
RE_BIBITEM = re.compile(r"\\bibitem\{([^{}]+)\}")
WRAP_OPEN = "\\tunemarkuptwo{nobiblio}{}{%"
BIB_OPEN = "\\begin{thebibliography}{100}"
BIB_CLOSE = "\\end{thebibliography}"
PAPERS = range(0, 197)


def digest(s: str) -> str:
    """The name a reviewed copy gives its original: 16 hex digits of SHA-256."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


@dataclasses.dataclass(frozen=True, slots=True)
class Note:
    paper: int
    section: int
    n: int
    line: int
    k: int              # the note's place among the notes of its line, from 0
    body: str           # between the braces, exactly as written
    before: str         # the line before the marker, from just after \vs p S:P

    @property
    def ref(self) -> str:
        return f"{self.paper}:{self.section}.{self.n}"

    @property
    def origin(self) -> str:
        return digest(self.body)


@dataclasses.dataclass(frozen=True, slots=True)
class Source:
    key: str
    body: str           # the lines after \bibitem{key}, as written, joined by \n
    line: int

    @property
    def origin(self) -> str:
        return digest(f"{self.key}\n{self.body}")


@dataclasses.dataclass(slots=True)
class Paper:
    n: int
    notes: list[Note]
    sources: list[Source]
    # (section, n) -> the paragraph's line as written, notes and all: what
    # tools/study/ aligns with the press text to propose where a marker goes.
    lines: dict[tuple[int, int], str]


def brace_end(s: str, i: int) -> int:
    """The index just after the group that opens at s[i] == '{'."""
    if s[i] != "{":
        raise ValueError(f"no group at {i}")
    depth = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


def unescaped(s: str, ch: str) -> list[int]:
    """Where `ch` stands in s, not escaped by a backslash."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == ch:
            out.append(i)
        i += 1
    return out


def read_paper(n: int, src: str, report) -> Paper:
    where = f"p{n:03d}.tex"
    notes: list[Note] = []
    lines: dict[tuple[int, int], str] = {}
    rows = src.splitlines()
    for lineno, raw in enumerate(rows, 1):
        line = raw.strip()
        m = RE_VS.match(line)
        has = bool(RE_FNST.search(line))
        if m:
            p, s, q = map(int, m.groups())
            if p != n:
                report.hard("study-paper-mismatch", f"{where}:{lineno}",
                            f"\\vs says paper {p}, the file is paper {n}")
                continue
            lines[(s, q)] = line[m.end():]
        if not has:
            continue
        if not m:
            report.hard("study-note-unplaced", f"{where}:{lineno}",
                        f"a \\fnst on a line that is no \\vs paragraph: {line[:60]}")
            continue
        if unescaped(line, "%"):
            report.hard("study-note-comment", f"{where}:{lineno}",
                        "a % on a line with a note: TeX would read the rest as a comment")
            continue
        body_at = m.end()
        k = 0
        for f in RE_FNST.finditer(line):
            j = f.end()
            while j < len(line) and line[j] == " ":
                j += 1
            if j >= len(line) or line[j] != "{":
                report.hard("study-note-unbraced", f"{where}:{lineno}",
                            "\\fnst not followed by its argument in braces")
                break
            try:
                e = brace_end(line, j)
            except ValueError:
                report.hard("study-note-unbalanced", f"{where}:{lineno}",
                            f"the note at column {f.start() + 1} never closes")
                break
            body = line[j + 1:e - 1]
            if RE_FNST.search(body):
                report.hard("study-note-in-note", f"{where}:{lineno}", body[:60])
            notes.append(Note(p, s, q, lineno, k, body, line[body_at:f.start()]))
            k += 1
    return Paper(n, notes, _sources(where, rows, report), lines)


def _sources(where: str, rows: list[str], report) -> list[Source]:
    """The paper's bibliography: each \\bibitem inside the one wrapper.

        \\tunemarkuptwo{nobiblio}{}{%
        \\begin{thebibliography}{100}
        \\bibitem{key}
        ...
        \\end{thebibliography}
        }
    """
    out: list[Source] = []
    strip = [r.strip() for r in rows]
    opens = [i for i, r in enumerate(strip) if "thebibliography" in r and r.startswith("\\begin")]
    closes = [i for i, r in enumerate(strip) if r.startswith(BIB_CLOSE)]
    inside: set[int] = set()
    if len(opens) != len(closes):
        report.hard("study-bibliography-unclosed", where,
                    f"{len(opens)} \\begin{{thebibliography}}, {len(closes)} \\end")
        return out
    for a, b in zip(opens, closes):
        ok = (strip[a] == BIB_OPEN and a > 0 and strip[a - 1] == WRAP_OPEN
              and b + 1 < len(strip) and strip[b] == BIB_CLOSE and strip[b + 1] == "}" and a < b)
        if not ok:
            report.hard("study-bibliography-wrapper", f"{where}:{a + 1}",
                        "a bibliography not in \\tunemarkuptwo{nobiblio}{}{% ... } as the others are")
            continue
        inside.update(range(a, b + 1))
        cur: tuple[str, int, list[str]] | None = None
        for i in range(a + 1, b + 1):
            m = RE_BIBITEM.match(strip[i])
            if m or i == b:
                if cur:
                    out.append(Source(cur[0], "\n".join(cur[2]).strip(), cur[1]))
                cur = (m.group(1), i + 1, [strip[i][m.end():]]) if m else None
            elif cur:
                cur[2].append(strip[i])
            elif strip[i]:
                report.hard("study-bibliography-stray", f"{where}:{i + 1}", strip[i][:60])
    for i, r in enumerate(strip):
        if "\\bibitem" in r and i not in inside:
            report.hard("study-bibitem-unwrapped", f"{where}:{i + 1}", r[:60])
    return out


def read(texdir, rev: str, papers, report) -> dict[int, Paper]:
    """{n: Paper} for each of `papers` the edition has at `rev`."""
    got = read_tex_many(texdir, [f"p{n:03d}.tex" for n in papers], rev)
    return {n: read_paper(n, got[f"p{n:03d}.tex"], report)
            for n in papers if got[f"p{n:03d}.tex"] is not None}
