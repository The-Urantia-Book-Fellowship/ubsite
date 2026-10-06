"""Read the A-Z index into a tree of entries.

Line-oriented, and the source really is one entry per line: across all 35,084
lines of ``tex/idx-*.tex`` and ``tex/app-*.tex`` there are no blank lines, no
mid-file comments, no entry spanning two lines and nothing after the final
closing brace.  That is cheap to assert, so it is asserted -- if ``emit_tex.py``
ever wraps a long line this must stop rather than mis-read it.

Two behaviours of the upstream reader are deliberately inverted here: it skips
any line it does not recognise, and it skips missing files.  Both are silent, and
both are the opposite of what an importer wants.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

from ..index_macros import (CHRON_MACROS, ENTRY_MACROS, LEVEL_OF, OTHER_MACROS,
                            RE_AB, RE_CIT, RE_XREF, balanced, label, render,
                            unescape)
from ._io import read_tex

LETTERS = ["numbers"] + [chr(c) for c in range(ord("a"), ord("z") + 1)]
RE_LINE = re.compile(r"^\\([a-zA-Z@]+)")


@dataclasses.dataclass(slots=True)
class Entry:
    where: str                 # 'idx-a.tex:1410' -- the edit address, and the identity
    scope: str                 # 'az' or an appendix letter
    letter: str | None         # the \idivider this falls under
    level: int
    headword: str | None       # level 1 only
    text: str                  # rendered printed text
    text_expanded: str         # with \ab{} expanded against the headword
    chain: list[str]           # ancestor texts, shallowest first, then this entry
    path: str                  # ' > '.join(chain)
    # The chip: each level's label -- the headword, or an entry without its
    # citations and cross-references -- joined by ' › '.
    path_plain: str
    cites: list[str]           # raw \cit{} arguments, in order
    xrefs: list[tuple[str, str]]   # ('see'|'seealso', target) after ';' splitting
    qv: bool
    raw: str
    src_text: str
    ord: int


def _expand_ab(text_src: str, headword: str | None) -> str:
    """Expand \\ab{c.} against its headword so the entry is searchable.

    3,025 entries abbreviate their own headword; left alone, 'c. belonged to
    mother' cannot be found by searching for 'children'.
    """
    if not headword:
        return text_src
    return RE_AB.sub(lambda m: headword, text_src)


def read_az(texdir: pathlib.Path, report, rev: str = "worktree") -> list[Entry]:
    """``rev`` is 'worktree' or the commit to read at -- see config's ``at``."""
    out: list[Entry] = []
    ordinal = 0
    for letter in LETTERS:
        fname = f"idx-{letter}.tex"
        src_file = read_tex(texdir, fname, rev)
        if src_file is None:
            report.hard("index-missing-file", f"{texdir / fname} at {rev}",
                        f"{fname} is not present")
            continue
        stack: dict[int, str] = {}          # reset per file, unlike upstream
        stack_head: dict[int, str] = {}
        stack_label: dict[int, str] = {}
        current_letter = None
        prev_level = 0
        for lineno, raw in enumerate(src_file.splitlines(), 1):
            where = f"{fname}:{lineno}"
            line = raw.rstrip()
            if not line.strip():
                report.hard("index-blank-line", where, "blank line in a generated file")
                continue
            if line.startswith("%"):
                if lineno != 1:
                    report.hard("index-stray-comment", where,
                                "comment outside line 1")
                continue
            m = RE_LINE.match(line)
            if not m:
                report.hard("index-unparsed-line", where, line[:70])
                continue
            macro = m.group(1)

            if macro == "idivider":
                current_letter, _ = balanced(line, line.index("{"))
                stack.clear(); stack_head.clear(); stack_label.clear(); prev_level = 0
                continue
            if macro in OTHER_MACROS:
                continue
            if macro not in ENTRY_MACROS:
                report.hard("index-unknown-macro", where,
                            f"\\{macro} is not an entry macro")
                continue

            level = LEVEL_OF[macro]
            head, i = balanced(line, line.index("{"))
            if macro == "iA":
                rest, j = balanced(line, i)
                if line[j:].strip():
                    report.hard("index-trailing-content", where, line[j:][:50])
                src = (head + " " + rest).strip()
                headword = render(head, where, report).rstrip(".")
            else:
                if line[i:].strip():
                    report.hard("index-trailing-content", where, line[i:][:50])
                src, rest = head, head
                headword = None

            if level > prev_level + 1:
                report.hard("index-level-jump", where,
                            f"level {level} follows level {prev_level}")
            prev_level = level

            text = render(src, where, report)
            root_head = stack_head.get(1)
            expanded = render(_expand_ab(src, headword or root_head), where, report)

            stack[level] = text
            stack_head[level] = headword if macro == "iA" else text
            stack_label[level] = headword if macro == "iA" else label(src, where, report)
            for deeper in [k for k in stack if k > level]:
                del stack[deeper]
                stack_head.pop(deeper, None)
                stack_label.pop(deeper, None)

            # Ancestors contribute their HEAD only -- a level-1 parent's own
            # citations and See-also list restated in front of each of its
            # descendants buries the entry the reader came for.
            chain = [stack_head[k] for k in sorted(stack_head) if k < level] + [text]
            xrefs = []
            for kind, targets in RE_XREF.findall(line):
                for t in targets.split(";"):
                    t = unescape(t).strip()
                    if t:
                        xrefs.append((kind, t))
            ordinal += 1
            out.append(Entry(
                where=where, scope="az", letter=current_letter, level=level,
                headword=headword, text=text, text_expanded=expanded,
                chain=chain, path=" > ".join(chain),
                path_plain=" \u203a ".join(stack_label[k] for k in sorted(stack_label)),
                cites=RE_CIT.findall(line), xrefs=xrefs,
                qv=bool(re.search(r"\\qv\b", line)), raw=line, src_text=src,
                ord=ordinal))
    return out
