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
# \\ in a section title is a printed line break.  It may carry a star and an
# optional vertical skip, \\[1ex], which is spacing and never text.
RE_NEWLINE  = re.compile(r"\\\\\*?(?:\[[^\]]*\])?")
RE_LAYOUT   = re.compile(r"\\hspace\*?\{[^{}]*\}|\\setlength\{[^{}]*\}\{[^{}]*\}"
                         r"|\\par\b|\\parindent|\\relax")
# A \pc the press source took out for its own page and says so in a comment:
# "\end{quoting}% The \pc at 48:6.20 has been removed to avoid double-line
# vskip".  The blank line is the 1955 printing's, not the press layout's, so the
# web gives it back.  (144:3.13 met the same clash and kept its \pc, cancelling
# the extra space with \vspace{-\baselineskip} instead.)
RE_PC_REMOVED = re.compile(r"%.*\\pc at (\d+):(\d+)\.(\d+) has been removed")
# A \vs whose body is one group pushed in by a fraction of the column is a
# heading within the text, not prose: 0:12.10 "{\hspace*{0.15\columnwidth}\itshape
# ACKNOWLEDGMENT}", which heads the Acknowledgment.  The press indents it; the
# site and the EPUB centre it, as they do a section's title.
RE_HEADING  = re.compile(r"\{\\hspace\*\{[\d.]+\\columnwidth\}")
# A separator, on a line of its own between two paragraphs: the stars as the
# press style prints them, `\separatorshort` three and `\separatorline` five,
# the line's set wider.  Its optional argument is the press's spacing.  It is
# kept on the paragraph after it (paragraph.sep_before).  Until 2026-10-12 the
# reader skipped it as layout, and the site showed none of the eleven.
RE_SEPARATOR = re.compile(r"\\separator(short|line)(?:\[[^\]]*\])?")
STARS = {"short": "* * *", "line": "* * * * *"}
# Verse is set in a quoting block, one line to a paragraph: the press indents the
# block and hangs each line's wrapped part.  The first line of each block is kept
# (verse_start), and so is a line the press sets in further with a leading
# \hsetoff (setoff: the Lord's Prayer's second lines, 144:3).  Anywhere else an
# \hsetoff would be dropped unseen, so it fails.
HSETOFF = "\\hsetoff"


@dataclasses.dataclass(slots=True)
class Paragraph:
    paper: int
    section: int
    n: int
    src: str                # 'vs' | 'poetry' | 'vsmark'
    line: int
    ex: Expanded
    heading: bool = False
    sep_before: str | None = None   # the stars of a separator standing before it
    verse_start: bool = False       # the first line of a block of verse
    setoff: bool = False            # a verse line set in further (\hsetoff)

    @property
    def ref(self) -> str:
        return f"{self.paper}:{self.section}.{self.n}"


@dataclasses.dataclass(slots=True)
class Paper:
    n: int
    title: str
    author: str | None
    # section number -> title ('' for the introduction), its printed line
    # breaks kept as "\n": the book sets some titles on two or three lines.
    sections: dict[int, str]
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
    restore: dict[tuple[int, int, int], int] = {}     # (paper, section, n) -> line
    sep: tuple[str, int] | None = None                # a separator awaiting its paragraph
    block = False                                     # a block of verse awaiting its first line

    def place(q: Paragraph) -> None:
        nonlocal sep, block
        paras.append(q)
        if sep:
            q.sep_before, sep = sep[0], None
        if block and q.src != "vs":
            q.verse_start, block = True, False

    def inline(text: str) -> Expanded:
        return exp.run(text)

    def title_of(body: str) -> str:
        # Each printed line expanded on its own.  Replacing \\ with a space ran
        # the lines together, and left the [1ex] of a \\[1ex] behind as text.
        lines = [re.sub(r"\s+", " ", inline(part).text).strip()
                 for part in RE_NEWLINE.split(body)]
        return "\n".join(x for x in lines if x)

    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        for m in RE_PC_REMOVED.finditer(line):
            restore[tuple(map(int, m.groups()))] = lineno

        if HSETOFF in line and not (in_block and line.startswith(HSETOFF)
                                    and HSETOFF not in line[len(HSETOFF):]):
            report.hard("hsetoff-unplaced", f"{where}:{lineno}",
                        "an \\hsetoff that does not begin a line of verse")

        if line.startswith("\\separator"):
            m = RE_SEPARATOR.fullmatch(line)
            if not m:
                report.hard("unknown-separator", f"{where}:{lineno}", line[:70])
            elif sep:
                report.hard("separator-twice", f"{where}:{lineno}",
                            f"a second separator, with the one on line {sep[1]} still"
                            " waiting for its paragraph")
            else:
                sep = (STARS[m.group(1)], lineno)
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
                sections[secnum - 1] = sections[secnum] = title_of(body)
            else:
                secnum += 1
                sections[secnum] = title_of(body)
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
            place(Paragraph(p, s, n, "vs", lineno, ex, bool(RE_HEADING.match(body))))
            continue

        m = re.match(r"\\(begin|end)\{(\w+)\}", line)
        if m:
            env = m.group(2)
            if env not in KNOWN_ENVIRONMENTS:
                report.hard("unknown-environment", f"{where}:{lineno}",
                            f"\\{m.group(1)}{{{env}}} not in the table")
            elif env == "quoting":
                in_block = block = (m.group(1) == "begin")
                if in_block:
                    counter = None
            continue

        if line.startswith("\\makeatletter"):
            continue

        if in_block:
            body, setoff = line, line.startswith(HSETOFF)
            if setoff:
                body = body[len(HSETOFF):]
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
            place(Paragraph(paper_n, sec, num, kind, lineno, inline(body), setoff=setoff))
            counter = num + 1
            continue

        # Anything else is a layout line.  Nothing may be silently dropped.
        if RE_LAYOUT.fullmatch(line) or line.startswith((
                "\\vsetoff", "\\vspace", "\\clp", "\\need",
                "\\makeatletter", "\\makeatother", "\\write", "\\hsetoff",
                "%", "{\\setlength", "}")):
            continue
        pending.append(f"{where}:{lineno}: {line[:70]}")

    if sep:
        report.hard("separator-at-end", f"{where}:{sep[1]}",
                    "a separator with no paragraph after it")

    for key, at in restore.items():
        q = next((q for q in paras if (q.paper, q.section, q.n) == key), None)
        if q is None:
            report.hard("pc-restore-nowhere", f"{where}:{at}",
                        "a comment says the \\pc at %d:%d.%d was removed, and there is"
                        " no such paragraph" % key)
        elif q.ex.flags.get("gap_before"):
            report.hard("pc-restore-stale", f"{where}:{at}",
                        f"{q.ref} has its \\pc again, so the comment saying it was"
                        " removed is out of date")
        else:
            q.ex.flags["gap_before"] = 1.0

    for p in pending:
        report.warn("unclaimed-line", p.split(":")[0] + ":" + p.split(":")[1],
                    p.split(": ", 1)[1])

    if not sections and paras:
        sections = {}
    sections.setdefault(0, "")
    return Paper(paper_n, title, author, sections, paras)


# The four parts, from the press style's own definitions, one line each:
#   \def\partitxt{PART I}   \def\partiup{The Central\\and Superuniverses}
#   \def\partimix{The Central and Superuniverses}   \def\partisub{Sponsored by ...}
# txt and up are what its divider page prints (\part{i}), with sub beneath;
# mix is the title on one line, as the book's page of Parts sets it.
STYLE = "urantia-uversa-press.sty"
ROMAN = ("i", "ii", "iii", "iv")
RE_PARTDEF = re.compile(r"\\def\\part(i|ii|iii|iv)(txt|up|mix|sub)\{(.*)\}$")


def read_parts(repo: pathlib.Path, report) -> dict[int, dict]:
    """{n: {label, title, title_lines, sponsor}} for the four parts."""
    found: dict[tuple[int, str], tuple[str, int]] = {}
    for lineno, line in enumerate(read_text(pathlib.Path(repo) / STYLE).splitlines(), 1):
        m = RE_PARTDEF.match(line.strip())
        if m:
            found[(ROMAN.index(m.group(1)) + 1, m.group(2))] = (m.group(3), lineno)
    parts = {}
    for n, r in enumerate(ROMAN, 1):
        lines = {}
        for field in ("txt", "up", "mix", "sub"):
            if (n, field) not in found:
                report.hard("part-undefined", STYLE, f"no \\part{r}{field}")
                continue
            value, at = found[(n, field)]
            # \\ is a printed line break, and nothing else is expected here.
            lines[field] = [x.strip() for x in RE_NEWLINE.split(value)]
            if any(c in x for x in lines[field] for c in "\\{}$%&~"):
                report.hard("part-markup", f"{STYLE}:{at}",
                            f"\\part{r}{field} holds TeX this reader does not know: {value[:60]}")
        if len(lines) == 4:
            parts[n] = {"label": " ".join(lines["txt"]), "title": " ".join(lines["mix"]),
                        "title_lines": "\n".join(lines["up"]), "sponsor": " ".join(lines["sub"])}
    return parts


def read_all(texdir: pathlib.Path, report) -> list[Paper]:
    return [read_paper(f, report) for f in sorted(texdir.glob("p[0-9][0-9][0-9].tex"))]


HYPHENATION = "urantia-hyphen-en.tex"
RE_HYPH_ENTRY = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")


def read_hyphenation(texdir: pathlib.Path, report) -> list[str]:
    """The press's \\hyphenation list, its entries as written, in file order.

    The press style inputs this one file (urantia-uversa-press.sty); build/hyphen.py
    applies it.  The whole file is a single \\hyphenation{%...} group of one or
    more entries to a line, with % comments between: anything else is a hard
    failure, since TeX would have read it differently from us.
    """
    src = read_text(pathlib.Path(texdir) / HYPHENATION)
    out: list[str] = []
    state = "before"
    for lineno, line in enumerate(src.splitlines(), 1):
        t = re.sub(r"(?<!\\)%.*", "", line).strip()
        if state == "before":
            if not t:
                continue
            if not t.startswith("\\hyphenation{"):
                report.hard("hyphenation-unread", f"{HYPHENATION}:{lineno}", t[:60])
                return out
            state, t = "in", t[len("\\hyphenation{"):].strip()
        if state == "after":
            if t:
                report.hard("hyphenation-unread", f"{HYPHENATION}:{lineno}",
                            f"after the list closed: {t[:60]}")
            continue
        if t.endswith("}"):
            state, t = "after", t[:-1].strip()
        for raw in t.split():
            if not RE_HYPH_ENTRY.fullmatch(raw):
                report.hard("hyphenation-entry", f"{HYPHENATION}:{lineno}",
                            f"{raw!r} is not letters and hyphens")
                continue
            out.append(raw)
    if state != "after":
        report.hard("hyphenation-unread", HYPHENATION, "the list never closes")
    if not out:
        report.hard("hyphenation-unread", HYPHENATION, "no entries")
    return out
