"""Read a translation of the book, one paper to a file, as written.

Pure: file -> dataclasses, through _io only.  Both Russian translations write a
paragraph to a line, `\\vs pNNN S:P text`, as the press does, with `\\pc` after
the address where the press puts it before.  Around the paragraphs, a paper has
its title (`\\upaper`, or urantia-ru's `\\uforeword` for the Foreword), its
author, a title to each section (`\\usection`, which stands before its first
paragraph), and lines that are the printed page's alone: ud's mini contents
(`\\uminitoc`), its link to the quiz (`\\quizlink`), `\\vsetoff`, `\\vspace`, a
`quote` around a list, and a bibliography after the text, kept for the notes.

The section a title belongs to is the next paragraph's, never a count of
`\\usection`: both have one more than the press, the Acknowledgment's heading,
which stands in 0:12 before 0:12.11 (build/translation.py), and 139's "9 и 10"
is one.  A separator is a line of its own (`\\separatorline`), or in ud a
numbered paragraph: `\\vs p031 10:22 \\separatorline`, and nine left empty.

Anything else on a line fails the build: a reader that skips what it does not
know would lose a paragraph without a word.
"""

from __future__ import annotations

import dataclasses
import re

from ._io import read_tex_many

RE_VS = re.compile(r"\\vs p(\d{3}) (\d+):(\d+)(?: |$)")
RE_UPAPER = re.compile(r"\\upaper\{(\d+)\}\{")
SEPARATOR = "\\separatorline"
# What a line may be that carries no words of the book.
LAYOUT = re.compile(r"\\vsetoff|\\vspace\*?\{[^{}]*\}|\\quizlink|\\(?:begin|end)\{quote\}")
RE_BIB_OPEN = re.compile(r"\\begin\{thebibliography\}\{\d+\}$")
RE_BIBITEM = re.compile(r"\\bibitem\{([^{}]+)\}")
RE_HYPHENRULES = re.compile(r"\\begin\{hyphenrules\}\{russian\}(.*?)\\end\{hyphenrules\}", re.S)
RE_HYPH_ENTRY = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
PAPERS = range(0, 197)


@dataclasses.dataclass(slots=True)
class Para:
    section: int
    n: int
    line: int
    body: str                     # after the address, as written, stripped

    @property
    def key(self) -> tuple[int, int]:
        return (self.section, self.n)


@dataclasses.dataclass(slots=True)
class Heading:
    line: int
    body: str                     # the title's TeX, as written
    before: tuple[int, int] | None  # the paragraph it stands before


@dataclasses.dataclass(slots=True)
class Paper:
    n: int
    title: Heading | None
    author: Heading | None
    sections: list[Heading]
    paras: list[Para]
    # A separator on a line of its own, by the paragraph after it (None at the end).
    seps: list[tuple[int, tuple[int, int] | None]]
    sources: list[tuple[str, str]]    # its bibliography: (key, the entry as written)


def _brace(s: str, i: int) -> tuple[str, int]:
    """The group opening at s[i] == '{': its inside, and the index after it."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces")


def read_paper(key: str, n: int, src: str, report, foreword: str | None = None) -> Paper:
    where = f"{key}:p{n:03d}.tex"
    title = author = None
    sections: list[Heading] = []
    paras: list[Para] = []
    seps: list[tuple[int, tuple[int, int] | None]] = []
    sources: list[tuple[str, str]] = []
    waiting: list[Heading] = []          # titles, and separators, awaiting their paragraph
    sep_waiting: list[int] = []
    bib: list[str] | None = None         # inside a bibliography: its lines
    rows = src.splitlines()
    for lineno, raw in enumerate(rows, 1):
        line = raw.strip()
        if bib is not None:
            if line == "\\end{thebibliography}":
                sources.extend(_bibliography(bib, f"{where}:{lineno}", report))
                bib = None
            else:
                bib.append(line)
            continue
        if not line or line.startswith("%"):
            continue
        m = RE_VS.match(line)
        if m:
            p, s, q = map(int, m.groups())
            if p != n:
                report.hard("tr-paper-mismatch", f"{where}:{lineno}",
                            f"\\vs says paper {p}, the file is paper {n}")
                continue
            para = Para(s, q, lineno, line[m.end():].strip())
            paras.append(para)
            for h in waiting:
                h.before = para.key
            for at in sep_waiting:
                seps.append((at, para.key))
            waiting, sep_waiting = [], []
            continue
        if line == SEPARATOR:
            sep_waiting.append(lineno)
            continue
        m = RE_UPAPER.match(line)
        if m:
            if int(m.group(1)) != n:
                report.hard("tr-paper-mismatch", f"{where}:{lineno}",
                            f"\\upaper says paper {m.group(1)}, the file is paper {n}")
            body, j = _brace(line, m.end() - 1)
            if line[j:].strip():
                report.hard("tr-line-unread", f"{where}:{lineno}", line[j:][:60])
            title = Heading(lineno, body, None)
            continue
        if line == "\\uforeword":
            if n != 0 or foreword is None:
                report.hard("tr-line-unread", f"{where}:{lineno}",
                            "\\uforeword outside the Foreword, or with no title to it")
            title = Heading(lineno, foreword or "", None)
            continue
        if line.startswith(("\\author{", "\\usection{", "\\uminitoc{")):
            cmd = line[1:line.index("{")]
            try:
                body, j = _brace(line, line.index("{"))
            except ValueError:
                report.hard("tr-line-unread", f"{where}:{lineno}", f"\\{cmd} never closes")
                continue
            if line[j:].strip():
                report.hard("tr-line-unread", f"{where}:{lineno}", line[j:][:60])
            if cmd == "author":
                author = Heading(lineno, body, None)
            elif cmd == "usection":
                sections.append(h := Heading(lineno, body, None))
                waiting.append(h)
            continue                      # \uminitoc: the printed page's mini contents
        if RE_BIB_OPEN.match(line):
            bib = []
            continue
        if LAYOUT.fullmatch(line):
            continue
        report.hard("tr-line-unread", f"{where}:{lineno}", line[:70])
    if bib is not None:
        report.hard("tr-bibliography-unclosed", where, "a bibliography that never closes")
    for h in waiting:
        report.hard("tr-heading-at-end", f"{where}:{h.line}", "a section title with no paragraph after it")
    for at in sep_waiting:
        seps.append((at, None))
    return Paper(n, title, author, sections, paras, seps, sources)


def _bibliography(lines: list[str], where: str, report) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    cur: tuple[str, list[str]] | None = None
    for line in lines:
        m = RE_BIBITEM.match(line)
        if m:
            if cur:
                out.append((cur[0], "\n".join(cur[1]).strip()))
            cur = (m.group(1), [line[m.end():]])
        elif cur:
            cur[1].append(line)
        elif line:
            report.hard("tr-bibliography-stray", where, line[:60])
    if cur:
        out.append((cur[0], "\n".join(cur[1]).strip()))
    return out


def read(key: str, texdir, rev: str, report, foreword: str | None = None) -> dict[int, Paper]:
    """{n: Paper} for each paper the translation's tex/ has at `rev`."""
    got = read_tex_many(texdir, [f"p{n:03d}.tex" for n in PAPERS], rev)
    out = {}
    for n in PAPERS:
        src = got[f"p{n:03d}.tex"]
        if src is None:
            report.hard("tr-paper-missing", f"{key}:p{n:03d}.tex", "no such file at the commit read")
            continue
        out[n] = read_paper(key, n, src, report, foreword)
    return out


def read_hyphenation(src: str, where: str, report) -> list[str]:
    """The translation's own \\hyphenation list, inside its one
    \\begin{hyphenrules}{russian} ... \\end{hyphenrules}, entries in file order.

    The list may be preceded there by urantia-ru's \\lccode`\\==`\\-, which lets
    an entry write a compound's hyphen as `=`; none does, so an entry with one
    fails.  Anything else in the block fails too.
    """
    blocks = RE_HYPHENRULES.findall(src)
    if len(blocks) != 1:
        report.hard("tr-hyphenation-unread", where, f"{len(blocks)} hyphenrules blocks for russian, not one")
        return []
    body = re.sub(r"(?<!\\)%.*", "", blocks[0])
    body = body.replace("\\lccode`\\==`\\-", "", 1).strip()
    if not (body.startswith("\\hyphenation{") and body.endswith("}")):
        report.hard("tr-hyphenation-unread", where, body[:60])
        return []
    out = []
    for raw in body[len("\\hyphenation{"):-1].split():
        if not RE_HYPH_ENTRY.fullmatch(raw):
            report.hard("tr-hyphenation-entry", where, f"{raw!r} is not letters and hyphens")
            continue
        out.append(raw)
    if not out:
        report.hard("tr-hyphenation-unread", where, "no entries")
    return out
