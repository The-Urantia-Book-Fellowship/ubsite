"""Draft a paper's study notes for review: var/study/NNN.toml and NNN.md.

    .venv/bin/python tools/study/draft.py N

Never data/study/: a draft is where a review starts, and a reviewed copy must
never be overwritten by one.  The draft carries every note and source of the
paper as the edition has them, at the commit build/config.py pins, each with its
`origin`, and for each note a proposed `after`, the press words its marker
follows, found by aligning the two texts' words: the study text is British and
metricated, so the words may differ, and a proposal it could not make cleanly
says CHECK.  Hebrew is turned to logical order (study_macros.py).  Beside each
note, in comments: the press paragraph, the press's own 1955 readings in it,
and what Block's chart sets beside it.  At the head, the reviewed notes of other
papers that link into this one ("see the note at 103:8.6"), each to be read with
the comment above it in its file, which may say what the note here is to give.
NNN.md is the same, to read.

Reads var/ub.db for the press text, so `make data` first.
"""

from __future__ import annotations

import difflib
import json
import pathlib
import re
import sqlite3
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "study"))

import block  # noqa: E402

from build import config, study  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import study as reader  # noqa: E402

OUT = ROOT / "var" / "study"
RE_BIBREF = re.compile(r"\\bibref(?:\[[^\]]*\])?\{p(\d+) (\d+):(\d+)\}")
RE_WORDS = re.compile(r"[A-Za-z0-9’']+")
RE_HEB = re.compile(r"\\textheb\{([^{}]*)\}")


def plain(tex: str) -> str:
    """A study line, roughly as read: notes out, commands and braces gone."""
    out, i = [], 0
    while True:
        j = tex.find("\\fnst{", i)
        if j < 0:
            out.append(tex[i:])
            break
        out.append(tex[i:j])
        i = reader.brace_end(tex, j + 5)
    s = "".join(out)
    s = re.sub(r"\\textcolou?r\{[^{}]*\}", "", s)
    s = re.sub(r"\\[A-Za-z]+\*?|\\.", " ", s)
    return re.sub(r"[{}$~]", " ", s).replace("---", "—").replace("--", "–")


def words(s: str) -> list[tuple[str, int, int]]:
    return [(m.group().lower().replace("’", "'"), m.start(), m.end()) for m in RE_WORDS.finditer(s)]


def propose(before: str, line: str, press: str) -> tuple[str, bool]:
    """(after, sure): the press words the marker should follow."""
    sw = [w for w, _, _ in words(plain(line))]
    bw = words(plain(before))
    pw = words(press)
    if not bw or not pw:
        return "", False
    i = len(bw) - 1                                  # the study word the marker follows
    sm = difflib.SequenceMatcher(None, sw, [w for w, _, _ in pw], autojunk=False)
    j, sure = None, False
    for a, b, size in sm.get_matching_blocks():
        if a <= i < a + size:
            j, sure = b + i - a, True
            break
        if a + size <= i:
            j = b + size - 1 if size else j         # the nearest match before it
    if j is None:
        return "", False
    end = pw[j][2]
    tail = plain(before).rstrip()
    if tail and not tail[-1].isalnum():              # the marker follows punctuation
        while end < len(press) and not press[end].isspace() and not press[end].isalnum():
            end += 1
    k = j
    while True:
        cand = press[pw[k][1]:end]
        if (press.count(cand) == 1 and j - k >= 2) or k == 0:
            return cand, sure
        k -= 1


def toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def literal(s: str) -> str:
    if "'''" in s:
        raise SystemExit(f"a note holds ''': {s[:60]}")
    return f"'''{s}'''"


def comment(s: str, width: int = 0) -> str:
    return "\n".join("# " + line if line else "#" for line in s.splitlines())


def pointing_in(n: int) -> list[str]:
    """The reviewed notes of other papers that link into paper n, one line each."""
    out = []
    for path in sorted(study.DATA.glob("[0-9][0-9][0-9].toml")):
        with open(path, "rb") as fh:
            notes = tomllib.load(fh).get("note", [])
        for nt in notes:
            for m in RE_BIBREF.finditer(nt["tex"]):
                if int(m[1]) == n and nt["at"].split(":")[0] != str(n):
                    out.append(f"{int(m[1])}:{int(m[2])}.{int(m[3])} <- {path.name} {nt['at']}:"
                               f" {nt['tex']}")
    return out


def logical_hebrew(tex: str) -> str:
    return RE_HEB.sub(lambda m: "\\textheb{" + " ".join(reversed(m[1].split())) + "}", tex)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    n = int(argv[0])
    repo = config.load()["study"]
    report = Report()
    paper = reader.read(repo["tex"], repo["at"], [n], report).get(n)
    if report.emit() or paper is None:
        return 1
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    press = dict(con.execute("SELECT ref, text FROM paragraph WHERE paper_n = ?", (n,)))
    readings: dict[str, list[str]] = {}
    for ref, text, anchor, ptext in con.execute(
            "SELECT p.ref, f.text, f.anchor, p.text FROM footnote f JOIN paragraph p"
            " ON p.id = f.paragraph_id WHERE f.kind = 'variant-1955' AND p.paper_n = ?"
            " ORDER BY p.ord, f.anchor", (n,)):
        readings.setdefault(ref, []).append(f"…{ptext[max(0, anchor - 40):anchor]}◦ 1955: {text}")
    b = config.block()
    row = (b["charts"] or {}).get(n)
    chart, col, front = "none", {}, ""
    if row:
        pdf = b["path"] / f"{n:03d}.pdf"
        bad = block.verify(pdf, row)
        if bad:
            print(f"warning: {bad}; refresh ../block-sources", file=sys.stderr)
        chart, col, front = row["url"], block.column(pdf, n), block.sources_page(pdf)

    toml = [f"# Paper {n}: a DRAFT for review, made by tools/study/draft.py from the study edition",
            f"# at {repo['at'][:7]}.  Edit, then save as data/study/{n:03d}.toml.", "",
            f"paper = {n}", f"chart = {toml_str(chart)}", ""]
    md = [f"# Paper {n}: the study edition's notes, for review", "",
          f"The edition at `{repo['at'][:7]}`; Block's chart: {chart}.", ""]
    pointing = pointing_in(n)
    if pointing:
        toml += [comment("Reviewed notes that link here, with the comment above each in its file:\n"
                         + "\n".join(pointing)), ""]
        md += ["## Reviewed notes that link here", "",
               "Read each with the comment above it in its file.", ""]
        md += [f"- {line}" for line in pointing] + [""]
    if front:
        toml += [comment(front), ""]
        md += ["## Block's chart, page 1", "", "```", front, "```", ""]
    for s in paper.sources:
        toml += ["[[source]]", f"key = {toml_str(s.key)}", f"origin = {toml_str(s.origin)}",
                 f"tex = {literal(s.body)}", ""]
        md += [f"## Source {s.key}", "", "```tex", s.body, "```", ""]
    for i, nt in enumerate(paper.notes, 1):
        text = press.get(nt.ref, "")
        after, sure = propose(nt.before, paper.lines[(nt.section, nt.n)], text) if text else ("", False)
        tex = logical_hebrew(nt.body)
        ctx = [f"press {nt.ref}: {text}"]
        ctx += [f"press 1955 reading: {r}" for r in readings.get(nt.ref, [])]
        if col.get(nt.ref):
            ctx.append("Block: " + " / ".join(col[nt.ref]))
        toml += [f"# ---- {i}. {nt.ref}" + ("" if sure else "   CHECK the anchor"),
                 comment("\n".join(ctx)), "[[note]]", f"at = {toml_str(nt.ref)}",
                 f"after = {toml_str(after)}", f"origin = {toml_str(nt.origin)}",
                 f"tex = {literal(tex)}", ""]
        md += [f"## {i}. {nt.ref}" + ("" if sure else " (CHECK the anchor)"), "",
               f"After “{after}”.", "", f"> {text}", "", "```tex", nt.body, "```", ""]
        md += [f"- The press's 1955 reading: {r}" for r in readings.get(nt.ref, [])]
        if col.get(nt.ref):
            md += ["", "Block: " + " / ".join(col[nt.ref])]
        md.append("")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{n:03d}.toml", "w", encoding="utf-8") as fh:
        fh.write("\n".join(toml) + "\n")
    with open(OUT / f"{n:03d}.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print(f"{OUT / f'{n:03d}.toml'}: {len(paper.notes)} notes, {len(paper.sources)} sources,"
          f" chart {chart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
