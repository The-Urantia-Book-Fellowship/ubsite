"""Where each verse of the Synodal stands among the KJV's: data/rsb/versification.tsv.

A chapter of the Bible's pages is a list of rows, each a verse of the KJV and
the Synodal's verse that is the same words, the KJV's address the row's (Tigran,
2026-11-21: the verses joined "by the KJV's address and the numbering table").
The two number alike but in 188 chapters, most of them Psalms (the Synodal
numbers them as the Greek does, and counts a psalm's title as its verse 0 or
1).  The table says only where they differ, a line to a run:

    Psa 9:22-39    Psa 10:1-18     moved: the Synodal's verses, the KJV's, one to one
    Psa 3:1        Psa 3:0         a psalm's title: the KJV sets it apart, row 0
    2Co 11:32      2Co 11:32-33    joined: one Synodal verse is two of the KJV's
    Isa 64:1       Isa 63:19       ... or two of the Synodal one of the KJV's
    Dan 3:24-90    + Dan 3:23      the Synodal's alone, rows after the KJV's 3:23
    Psa 151:0-7    own             the Synodal's alone, a chapter of its own
    -              Act 8:37        the KJV's alone, no Synodal verse its words

and every other verse of a book both have is the same address in both, which
place() requires.  A book only the Synodal has (Tob, Sir) is its own numbering
throughout and needs no line.  Read by build/bible.py and made by
tools/rsb/versify.py from SIL's versification files, as ruled by Tigran.

Rows: place() gives each verse of either text the row it stands in, a key
(chapter, verse, s) in the KJV's numbering: s 0 for a row with a KJV verse, or
a title's row (verse 0); s 1, 2 ... for the Synodal's own after the KJV's
(chapter, verse), or after (chapter, 0), at the head of a chapter: a title
the KJV has not (Psa 1:0), a prologue (Est 0:0); in a chapter of its own, its
own (chapter, verse, 0).
"""

from __future__ import annotations

import pathlib
import re

RE_ONE = re.compile(r"([1-3]?[A-Z][a-z]{1,2}) (\d+):(\d+)(?:-(\d+))?")
FIELDS = ("synodal", "kjv", "why")


def addresses(ref: str, where: str) -> tuple[str, list[tuple[int, int]]]:
    """`Psa 9:22-39` -> ('Psa', [(9, 22), ..., (9, 39)])."""
    m = RE_ONE.fullmatch(ref)
    if not m:
        raise SystemExit(f"{where}: no reference {ref!r}")
    c, v, w = int(m[2]), int(m[3]), int(m[4] or m[3])
    if w < v:
        raise SystemExit(f"{where}: a range backwards: {ref!r}")
    return m[1], [(c, x) for x in range(v, w + 1)]


def read(path: pathlib.Path) -> list[dict]:
    """The table's lines: {kind, book, syn, kjv, line}; kind moved, after, own
    or kjvonly.  `syn` and `kjv` lists of (chapter, verse)."""
    rows = path.read_text(encoding="utf-8").split("\n")
    if rows[0].split("\t") != list(FIELDS):
        raise SystemExit(f"{path.name}: header {rows[0]!r}")
    out = []
    for k, r in enumerate(rows[1:], 2):
        if not r or r.startswith("#"):
            continue
        where = f"{path.name}:{k}"
        f = r.split("\t")
        if len(f) != 3:
            raise SystemExit(f"{where}: {len(f)} fields")
        syn, kjv, _ = f
        if syn == "-":
            b, ks = addresses(kjv, where)
            out.append({"kind": "kjvonly", "book": b, "syn": [], "kjv": ks, "line": k})
            continue
        b, ss = addresses(syn, where)
        if kjv == "own":
            out.append({"kind": "own", "book": b, "syn": ss, "kjv": [], "line": k})
        elif kjv.startswith("+ "):
            b2, at = addresses(kjv[2:], where)
            if b2 != b or len(at) != 1:
                raise SystemExit(f"{where}: `+` names one verse of the same book")
            out.append({"kind": "after", "book": b, "syn": ss, "kjv": at, "line": k})
        else:
            b2, ks = addresses(kjv, where)
            if b2 != b:
                raise SystemExit(f"{where}: two books")
            if len(ss) != len(ks) and 1 not in (len(ss), len(ks)):
                raise SystemExit(f"{where}: {len(ss)} verses to {len(ks)}: one to one, one to many or many to one")
            out.append({"kind": "moved", "book": b, "syn": ss, "kjv": ks, "line": k})
    return out


def pairs(rule: dict) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """A moved line's (synodal, kjv) pairs."""
    ss, ks = rule["syn"], rule["kjv"]
    if len(ss) == len(ks):
        return list(zip(ss, ks))
    if len(ss) == 1:
        return [(ss[0], k) for k in ks]
    return [(s, ks[0]) for s in ss]


def place(book: str, syn: list[tuple[int, int]], kjv: list[tuple[int, int]],
          rules: list[dict]) -> tuple[dict, dict]:
    """Each verse's row: ({synodal (c, v): (c, v, s)}, {kjv (c, v): (c, v, s)}).

    `syn` the Synodal's verses of the book in its order, `kjv` the KJV's, a
    psalm's title among them as (c, 0).  Fails unless every verse of each
    stands in exactly one row, each by a line of the table or by having the
    same address in the other."""
    mine = [r for r in rules if r["book"] == book]
    sset, kset = set(syn), set(kjv)
    links: dict[tuple, set] = {s: set() for s in syn}
    told_s: dict[tuple, int] = {}
    told_k: dict[tuple, int] = {}

    def tell(d, key, line):
        if key in d:
            raise SystemExit(f"versification.tsv:{line}: {book} {key[0]}:{key[1]} also on line {d[key]}")
        d[key] = line

    after: dict[tuple, tuple] = {}
    own: set = set()
    kjvonly: set = set()
    for r in mine:
        for s in r["syn"]:
            if s not in sset:
                raise SystemExit(f"versification.tsv:{r['line']}: the Synodal has no {book} {s[0]}:{s[1]}")
        for k in (r["kjv"] if r["kind"] in ("moved", "kjvonly", "after") else ()):
            if k not in kset and not (r["kind"] == "after" and k[1] == 0 and (k[0], 1) in kset):
                raise SystemExit(f"versification.tsv:{r['line']}: the KJV has no {book} {k[0]}:{k[1]}")
        if r["kind"] == "moved":
            for s, k in pairs(r):
                links[s].add(k)
            for s in set(r["syn"]):
                tell(told_s, s, r["line"])
            for k in set(r["kjv"]):
                tell(told_k, k, r["line"])
        elif r["kind"] == "after":
            for s in r["syn"]:
                tell(told_s, s, r["line"])
                after[s] = r["kjv"][0]
        elif r["kind"] == "own":
            for s in r["syn"]:
                tell(told_s, s, r["line"])
                own.add(s)
        else:
            for k in r["kjv"]:
                tell(told_k, k, r["line"])
                kjvonly.add(k)
    for s in syn:
        if s in told_s:
            continue
        if s not in kset or s in told_k:
            raise SystemExit(f"versification.tsv: the Synodal's {book} {s[0]}:{s[1]} has no line, "
                             f"and the KJV's {s[0]}:{s[1]} is {'another line' if s in told_k else 'no verse'}")
        links[s].add(s)
    hit = {k for s in syn for k in links[s]}
    for k in kjv:
        if k not in hit and k not in kjvonly:
            raise SystemExit(f"versification.tsv: the KJV's {book} {k[0]}:{k[1]} is no Synodal verse's, "
                             f"and no line says it is the KJV's alone")
        if k in hit and k in kjvonly:
            raise SystemExit(f"versification.tsv: the KJV's {book} {k[0]}:{k[1]} is said to be its own and is linked")
    # Rows: the components of the links, each keyed by its first KJV verse.
    kjv_row: dict[tuple, tuple] = {}
    syn_row: dict[tuple, tuple] = {}
    order = {k: i for i, k in enumerate(kjv)}
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s in syn:
        for k in links[s]:
            parent[find(("s", s))] = find(("k", k))
    comp: dict = {}
    for k in kjv:
        comp.setdefault(find(("k", k)), []).append(k)
    for ks in comp.values():
        first = min(ks, key=order.__getitem__)
        if [order[k] for k in sorted(ks, key=order.__getitem__)] != list(range(order[first], order[first] + len(ks))):
            raise SystemExit(f"versification.tsv: {book}: a row joins KJV verses that are not neighbours: {sorted(ks)}")
        for k in ks:
            kjv_row[k] = (*first, 0)
    for s in syn:
        if links[s]:
            syn_row[s] = kjv_row[next(iter(links[s]))]
    # The Synodal's own, after a KJV verse or a chapter of its own; a chapter 0
    # at the head of chapter 1.
    n_after: dict[tuple, int] = {}
    for s in syn:
        if s in after:
            a = after[s]
            n_after[a] = n_after.get(a, 0) + 1
            syn_row[s] = (*a, n_after[a])
        elif s in own:
            syn_row[s] = (*s, 0)
    return syn_row, kjv_row
