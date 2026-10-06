"""Read Appendices A-F.

Two shapes in one directory.

**Appendix A is the chronology and contains not one ``\\iapp``.** It is built
from four macros -- ``\\chronyear``, ``\\chronmonth``, ``\\chrontext``,
``\\chronsubtext``.  An appendix reader that keys on ``\\iapp`` imports A as
empty; that is exactly the bug that hid its 470 citations from every check in the
index project until 2026-09-13, so it is worth stating twice.

**The macro is the parentage signal, not document position.**  A ``\\chrontext``
hangs off its year even when it comes after a ``\\chronmonth`` -- which happens,
e.g. under ``7 B.C.``  Deriving parentage from "the most recent heading seen"
silently files those events under a month they do not belong to.

**Appendices B-F are flat**: one level, one ``\\iapp`` per line, no sub-entries.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

from ..index_macros import (CHRON_MACROS, RE_CIT, RE_XREF, balanced, label,
                            render, unescape)
from ._io import read_tex
from .index_az import Entry

APPENDICES = "abcdef"
RE_LINE = re.compile(r"^\\([a-zA-Z@]+)")
RE_DEF_NAME = re.compile(r"^\\def\\iappendixname\{")


@dataclasses.dataclass(slots=True)
class ChronEvent:
    where: str
    year_label: str
    month_label: str | None      # None for a \chrontext -- it hangs off the year
    text: str
    src_text: str
    label: str                   # the event without its citations: the chip
    cites: list[str]
    ord: int


@dataclasses.dataclass(slots=True)
class Appendix:
    letter: str
    name: str                    # \def\iappendixname{...}
    title: str                   # \iapptitle{Appendix B}{Celestial Beings, Types}
    entries: list[Entry]
    events: list[ChronEvent]


def read_appendices(texdir: pathlib.Path, report,
                    letters: str = APPENDICES, rev: str = "worktree") -> list[Appendix]:
    """``rev`` is 'worktree' or the commit to read at -- see config's ``at``."""
    out = []
    ordinal = 0
    for letter in letters:
        fname = f"app-{letter}.tex"
        src_file = read_tex(texdir, fname, rev)
        if src_file is None:
            report.hard("index-missing-file", f"{texdir / fname} at {rev}", f"{fname} absent")
            continue
        name = title = ""
        entries: list[Entry] = []
        events: list[ChronEvent] = []
        year = month = None
        for lineno, raw in enumerate(src_file.splitlines(), 1):
            where = f"{fname}:{lineno}"
            line = raw.rstrip()
            if not line.strip() or line.startswith("%"):
                continue
            m = RE_LINE.match(line)
            if not m:
                report.hard("index-unparsed-line", where, line[:70])
                continue
            macro = m.group(1)

            if RE_DEF_NAME.match(line):
                name = balanced(line, line.index("{", line.index("iappendixname")))[0]
                continue
            if macro == "iapptitle":
                a, i = balanced(line, line.index("{"))
                title = render(balanced(line, i)[0], where, report)
                continue
            if macro in ("begin", "end", "def"):
                continue

            if macro in CHRON_MACROS:
                raw_arg = balanced(line, line.index("{"))[0]
                text = render(raw_arg, where, report)
                if macro == "chronyear":
                    year, month = text, None
                    continue
                if macro == "chronmonth":
                    if year is None:
                        report.hard("chron-month-before-year", where, text)
                    month = text
                    continue
                if year is None:
                    report.hard("chron-event-before-year", where, text)
                ordinal += 1
                events.append(ChronEvent(
                    where=where, year_label=year or "",
                    # chrontext hangs off the year; only chronsubtext takes the month
                    month_label=month if macro == "chronsubtext" else None,
                    text=text, src_text=raw_arg, label=label(raw_arg, where, report),
                    cites=RE_CIT.findall(line), ord=ordinal))
                continue

            if macro != "iapp":
                report.hard("index-unknown-macro", where, f"\\{macro} in {fname}")
                continue

            src, i = balanced(line, line.index("{"))
            if line[i:].strip():
                report.hard("index-trailing-content", where, line[i:][:50])
            text = render(src, where, report)
            xrefs = []
            for kind, targets in RE_XREF.findall(line):
                for t in targets.split(";"):
                    t = unescape(t).strip()
                    if t:
                        xrefs.append((kind, t))
            ordinal += 1
            entries.append(Entry(
                where=where, scope=letter.upper(), letter=letter.upper(), level=1,
                headword=text.rstrip("."), text=text, text_expanded=text,
                chain=[text], path=text, path_plain=label(src, where, report),
                cites=RE_CIT.findall(line), xrefs=xrefs,
                qv=bool(re.search(r"\\qv\b", line)), raw=line, src_text=src,
                ord=ordinal))

        out.append(Appendix(letter.upper(), name, title, entries, events))
    return out
