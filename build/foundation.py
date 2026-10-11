"""The Foundation's numbering beside ours.

Every other site, and every translation, numbers paragraphs as the Urantia
Foundation's SRT does.  The press numbers 107 of them differently:

  - the SRT numbers each `* * *` separator in 134:6 and 144:5 as a paragraph,
    and the press does not, so 134:6.14 here is 134:6.15 there, and 144:5 runs
    up to six ahead by its end;
  - it files 139's one heading over sections 9 and 10 under 10, so 139:9.1 here
    is 139:10.1 there;
  - and it does not number 0:12.10 ACKNOWLEDGMENT at all.

A site that joins our English to its Russian by reference would pair those
paragraphs wrongly, so the API carries both.  Theirs is read from the
Foundation's own HTML (SRT v1.22), which the press repo keeps as a zip, at the
revision config pins -- never misc/html/, an extraction that may be stale.

Paragraphs are matched by their words, paper by paper (139:9 and 139:10 cross a
section), with difflib over a normalisation that keeps letters and digits only.
The press departs from the SRT in a few accepted places -- a capital after a
drop cap, an ellipsis, a comma -- and the normalisation absorbs most of them;
what it does not must still pair one to one and be nearly the same words.
Anything left over on either side is a hard failure, and the differences must be
exactly those declared in tests/known-uf-refs.tsv.
"""

from __future__ import annotations

import collections
import difflib
import html
import io
import pathlib
import re
import zipfile

from .readers import _io

ZIP = "misc/uf-eng-001-1955-1.22-html.zip"
RE_FILE = re.compile(r"Paper(\d{3})\.html$")
RE_P = re.compile(r'<p id="U(\d+)_(\d+)_(\d+)"[^>]*>(.*?)</p>', re.S)
RE_SMALL = re.compile(r"\s*<small>([^<]*)</small>\s*")
RE_TAG = re.compile(r"<[^>]+>")
SIMILAR = 0.9           # a pair matched despite different words must be this alike

Key = tuple[int, int, int]


def fmt(k: Key | None) -> str:
    return "-" if k is None else f"{k[0]}:{k[1]}.{k[2]}"


def _norm(t: str) -> str:
    return "".join(c for c in t.casefold() if c.isalnum())


def read(repo, report) -> dict[int, list[tuple[Key, str]]]:
    """{paper: [((paper, section, n), text), ...]} in the Foundation's order."""
    data = _io.read_bytes_at_rev(repo["path"], ZIP, repo["at"])
    out = collections.defaultdict(list)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in sorted(z.namelist()):
            if not RE_FILE.search(name):
                continue
            for m in RE_P.finditer(z.read(name).decode("utf-8")):
                k = tuple(map(int, m.group(1, 2, 3)))
                body = m.group(4)
                small = RE_SMALL.match(body)
                if not small or not small.group(1).startswith(fmt(k) + " "):
                    report.hard("uf-paragraph-unlabelled", fmt(k),
                                f"{name}: no <small>{fmt(k)} …</small> before the text")
                    continue
                text = html.unescape(RE_TAG.sub("", body[small.end():])).strip()
                out[k[0]].append((k, text))
    return out


def align(ours: dict[int, list[tuple[Key, str]]], theirs: dict[int, list[tuple[Key, str]]],
          report) -> dict[Key, Key | None]:
    """Each of our paragraphs -> the Foundation's, or None where it has none."""
    match: dict[Key, Key | None] = {}
    for paper in sorted(set(ours) | set(theirs)):
        a, b = ours.get(paper, []), theirs.get(paper, [])
        sm = difflib.SequenceMatcher(None, [_norm(t) for _, t in a],
                                     [_norm(t) for _, t in b], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    if op == "replace":
                        r = difflib.SequenceMatcher(None, a[i][1], b[j][1]).ratio()
                        if r < SIMILAR:
                            report.hard("uf-paragraph-differs", fmt(a[i][0]),
                                        f"paired with the Foundation's {fmt(b[j][0])},"
                                        f" but only {r:.2f} alike")
                    match[a[i][0]] = b[j][0]
                continue
            for i in range(i1, i2):
                match[a[i][0]] = None
            for j in range(j1, j2):
                report.hard("uf-paragraph-unmatched", fmt(b[j][0]),
                            f"the Foundation's paragraph matches none of ours: {b[j][1][:60]!r}")
    return match


def runs(match: dict[Key, Key | None]) -> list[tuple[str, str, str, str]]:
    """The differences as runs: (our first, our last, their first, their last)."""
    out: list[list] = []
    for o in sorted(match):
        u = match[o]
        if u == o:
            continue
        last = out[-1] if out else None
        if (last and last[1][:2] == o[:2] and last[1][2] + 1 == o[2]
                and (u is None) == (last[3] is None)
                and (u is None or (last[3][:2] == u[:2] and last[3][2] + 1 == u[2]))):
            last[1], last[3] = o, u
        else:
            out.append([o, o, u, u])
    return [(fmt(a), fmt(b), fmt(c), fmt(d)) for a, b, c, d in out]


def load_known(path: pathlib.Path) -> list[tuple[str, str, str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            out.append(tuple(line.split("\t")))
    return out


def load(con, repo, report, known: pathlib.Path) -> int:
    """Fill uf_paragraph and uf_section.  Returns how many paragraphs differ."""
    ours = collections.defaultdict(list)
    ids = {}
    for pid, p, s, n, text in con.execute(
            "SELECT id, paper_n, section_n, para_n, text FROM paragraph ORDER BY ord"):
        ours[p].append(((p, s, n), text))
        ids[(p, s, n)] = pid
    match = align(ours, read(repo, report), report)

    got, want = runs(match), load_known(known)
    for r in sorted(set(got) - set(want)):
        report.hard("uf-numbering-undeclared", r[0],
                    f"{r[0]}–{r[1]} are the Foundation's {r[2]}–{r[3]}:"
                    f" not in {known.name}")
    for r in sorted(set(want) - set(got)):
        report.hard("uf-numbering-gone", r[0],
                    f"{known.name} declares {r[0]}–{r[1]} as {r[2]}–{r[3]}, and it is not")

    con.executemany("INSERT INTO uf_paragraph VALUES (?, ?)",
                    [(ids[k], None if u is None else fmt(u)) for k, u in match.items()])
    # A section's is the one Foundation section all its paragraphs are in.
    secs = collections.defaultdict(set)
    for (p, s, _), u in match.items():
        if u is not None:
            secs[(p, s)].add(f"{u[0]}:{u[1]}")
    rows = []
    for sid, p, s in con.execute("SELECT id, paper_n, n FROM section"):
        theirs = secs.get((p, s), set())
        if len(theirs) > 1:
            report.hard("uf-section-split", f"{p}:{s}",
                        f"its paragraphs are in the Foundation's {sorted(theirs)}")
        rows.append((sid, min(theirs) if theirs else None))
    con.executemany("INSERT INTO uf_section VALUES (?, ?)", rows)
    return sum(1 for k, u in match.items() if u != k)
