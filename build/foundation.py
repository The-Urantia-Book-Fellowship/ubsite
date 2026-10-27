"""The Foundation's numbering beside ours.

Every other site, and every translation, numbers paragraphs as the Urantia
Foundation's SRT does.  The press numbers 106 of them differently:

  - the SRT gives the `* * *` separator in 134:6, and each of the six in 144:5,
    a number of its own, and the press numbers no separator, so 134:6.14 here is
    134:6.15 there, and 144:5 runs up to six ahead by its end;
  - it files 139's one heading over sections 9 and 10 under 10, so 139:9.1 here
    is 139:10.1 there.

A site that joins our English to its Russian by reference would pair those
paragraphs wrongly, so the API carries both.  Theirs is read from the
Foundation's own HTML (SRT v1.22), which the press repo keeps as a zip, at the
revision config pins -- never misc/html/, an extraction that may be stale.

Each paragraph's reference there carries its 1955 page as well, "101:4.2
(1109.3)": the page of the first printing, and the paragraph on that page.  It
is taken with the reference.

Eleven entries there are printed without a reference, each marked by an F after
its id (`U0_12_10F`): the SRT's ten separators, and 0:12.10 ACKNOWLEDGMENT.
Seven of the separators take a number of their own (those above); the other
three, after 31:10.21, 56:10.22 and 120:3.11, repeat the number before them.
None is a paragraph.  Each is kept with the paragraph after it, and must stand
before the same paragraph as one of the press's (paragraph.sep_before), with the
same stars, but where tests/known-separator-deltas.tsv says otherwise.  The
ACKNOWLEDGMENT is 0:12.10 there as it is here, so it is read as a paragraph.  Its page, which is not printed either, is the one place
its neighbours leave: 0:12.9 is (16.6) and 0:12.11 is (16.8), so 16.7, as the
1955 printing itself shows (the Guardian plates, page 16).  Until 2026-10-12 all
eleven were skipped, and the API said the Foundation did not number it.

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
import pathlib

from .readers import _io
from .readers import uf_html
from .readers.uf_html import fmt

ZIP = "misc/uf-eng-001-1955-1.22-html.zip"
SIMILAR = 0.9           # a pair matched despite different words must be this alike

Key = tuple[int, int, int]


def _norm(t: str) -> str:
    return "".join(c for c in t.casefold() if c.isalnum())


def read(repo, report, pages: dict[Key, str] | None = None,
         seps: list[tuple[Key, str]] | None = None) -> dict[int, list[tuple[Key, str]]]:
    """{paper: [((paper, section, n), text), ...]} in the Foundation's order.

    Each paragraph's 1955 page goes into `pages`, by its key there, and each
    separator into `seps`, as the key of the paragraph after it and its stars.
    The zip is read by build/readers/uf_html.py, which reads every language's.
    """
    papers = uf_html.read(_io.read_bytes_at_rev(repo["path"], ZIP, repo["at"]), report)
    out = collections.defaultdict(list)
    found: dict[Key, str] = {}
    bare: list[tuple[str, Key]] = []        # numbered, but printed without the number
    stars: list[tuple[Key, str]] = []
    for paper in papers.values():
        for q in paper.paras:
            out[q.key[0]].append((q.key, q.text))
            if q.page:
                found[q.key] = q.page
            if q.bare:
                bare.append((q.name, q.key))
        stars += [(k, s) for k, s, _ in paper.seps]
    # A paragraph printed without its number has no page beside it either.  It
    # takes the one place its neighbours leave on their page, or none.
    for name, k in bare:
        keys = [key for key, _ in out[k[0]]]
        i = keys.index(k)
        near = [found.get(keys[j]) if 0 <= j < len(keys) else None for j in (i - 1, i + 1)]
        if None not in near:
            (pb, nb), (pa, na) = (tuple(map(int, x.split("."))) for x in near)
            if pb == pa and na == nb + 2:
                found[k] = f"{pb}.{nb + 1}"
                continue
        report.hard("uf-paragraph-no-page", fmt(k),
                    f"{name}: printed without a number, between pages {near[0]} and"
                    f" {near[1]}, which leave no one place for it")
    if pages is not None:
        pages.update(found)
    if seps is not None:
        seps.extend(stars)
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


def load(con, repo, report, known: pathlib.Path, known_seps: pathlib.Path) -> int:
    """Fill uf_paragraph and uf_section.  Returns how many paragraphs it numbers otherwise."""
    ours = collections.defaultdict(list)
    ids = {}
    for pid, p, s, n, text in con.execute(
            "SELECT id, paper_n, section_n, para_n, text FROM paragraph ORDER BY ord"):
        ours[p].append(((p, s, n), text))
        ids[(p, s, n)] = pid
    pages: dict[Key, str] = {}
    seps: list[tuple[Key, str]] = []
    match = align(ours, read(repo, report, pages, seps), report)

    got, want = runs(match), load_known(known)
    for r in sorted(set(got) - set(want)):
        report.hard("uf-numbering-undeclared", r[0],
                    f"{r[0]}–{r[1]} are the Foundation's {r[2]}–{r[3]}:"
                    f" not in {known.name}")
    for r in sorted(set(want) - set(got)):
        report.hard("uf-numbering-gone", r[0],
                    f"{known.name} declares {r[0]}–{r[1]} as {r[2]}–{r[3]}, and it is not")

    # The Foundation's separators, on our paragraphs, against the press's.
    back = {u: o for o, u in match.items() if u is not None}
    theirs: dict[str, str] = {}
    for u, stars in seps:
        if u in back:
            theirs[fmt(back[u])] = stars
        else:
            report.hard("uf-separator-unplaced", fmt(u),
                        "the Foundation's separator stands before a paragraph we do not have")
    press = dict(con.execute("SELECT ref, sep_before FROM paragraph WHERE sep_before IS NOT NULL"))
    got = {(r, press.get(r, "-"), theirs.get(r, "-")) for r in press.keys() | theirs.keys()
           if press.get(r) != theirs.get(r)}
    want = set(load_known(known_seps))
    for r in sorted(got - want):
        report.hard("uf-separator-undeclared", r[0],
                    f"the press has {r[1]!r} before {r[0]}, the Foundation {r[2]!r}:"
                    f" not in {known_seps.name}")
    for r in sorted(want - got):
        report.hard("uf-separator-gone", r[0],
                    f"{known_seps.name} declares {r[1]!r} against {r[2]!r} before {r[0]},"
                    " and it is not")

    con.executemany("INSERT INTO uf_paragraph VALUES (?, ?, ?)",
                    [(ids[k], None if u is None else fmt(u), pages.get(u))
                     for k, u in match.items()])
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
