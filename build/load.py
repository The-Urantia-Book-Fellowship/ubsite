"""dataclasses -> SQL, in a deterministic order.

Every loader iterates its source in sorted order and assigns ids from that
order, so the same inputs always produce the same ids.  That is what makes the
TSV export -- and therefore `git diff export/` -- a meaningful answer to "what
did this rebuild change".
"""

from __future__ import annotations

import pathlib
import sys

from .chronology import one_line, parse_year
from .index_macros import render_html
from . import variants
from .render import render, title as render_title

VENDOR = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "index"
sys.path.insert(0, str(VENDOR))
import cite   # noqa: E402
import xref   # noqa: E402

# The papers each part holds; its words come from the press style (read_parts).
PARTS = [(1, 1, 31), (2, 32, 56), (3, 57, 119), (4, 120, 196)]


def _part_of(n: int):
    for pn, lo, hi in PARTS:
        if lo <= n <= hi:
            return pn
    return None


def load_text(con, papers, parts, repo, hyphenator, report) -> dict:
    con.executemany("INSERT INTO part (n, title, first_paper, last_paper, label,"
                    " title_lines, sponsor) VALUES (?,?,?,?,?,?,?)",
                    [(n, parts[n]["title"], lo, hi, parts[n]["label"],
                      parts[n]["title_lines"], parts[n]["sponsor"])
                     for n, lo, hi in PARTS if n in parts])
    con.execute("INSERT INTO edition (id, code, title, variety, source_repo,"
                " source_commit, source_dirty) VALUES (1,'press',?,?,?,?,?)",
                ("The Urantia Book -- Uversa Press", "authoritative",
                 str(repo["path"]), repo["commit"], int(repo["dirty"])))

    pid = sid = qid = spid = fid = 0
    para_key = {}
    for p in papers:
        pid += 1
        con.execute("INSERT INTO paper VALUES (?,1,?,?,?,?,?)",
                    (pid, p.n, _part_of(p.n), p.title, p.author,
                     f"tex/p{p.n:03d}.tex"))
        # Only sections that actually hold paragraphs get a row.  A combined
        # heading (\usectiontwo) names two numbers but fills one.
        present = sorted({q.section for q in p.paragraphs})
        sec_id = {}
        for n in present:
            sid += 1
            sec_id[n] = sid
            combined = n + 1 if (n + 1) in p.sections and (n + 1) not in present \
                and p.sections.get(n) == p.sections.get(n + 1) else None
            plain, shown = render_title(p.sections[n]) if p.sections.get(n) else (None, None)
            con.execute("INSERT INTO section VALUES (?,1,?,?,?,?,?,?)",
                        (sid, pid, p.n, n, plain, shown, combined))
        for q in p.paragraphs:
            qid += 1
            para_key[(q.paper, q.section, q.n)] = qid
            # Rendered once, with a soft hyphen wherever the book lets a word
            # break; `html` is that without them, which is render() without
            # `shy` as long as the text holds no U+00AD of its own.
            if "\u00ad" in q.ex.text:
                report.hard("soft-hyphen-in-text", q.ref, "the text itself has a U+00AD")
            hy = render(q.ex.text, q.ex.spans, f"{q.paper}_{q.section}_{q.n}",
                        shy=hyphenator.points(q.ex.text, q.ex.spans))
            con.execute("INSERT INTO paragraph VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (qid, sec_id[q.section], q.paper, q.section, q.n, q.ref,
                         qid, q.src,
                         q.ex.flags.get("gap_before", 0.0), int(q.heading), q.sep_before,
                         int(q.verse_start), int(q.setoff), q.ex.text,
                         hy.replace("\u00ad", ""), hy,
                         len(q.ex.text.split()), q.line))
            for i, s in enumerate(q.ex.spans):
                spid += 1
                con.execute("INSERT INTO span VALUES (?,?,?,?,?,?,?)",
                            (spid, qid, s.start, s.end, s.kind, None, i))
            for i, nt in enumerate(q.ex.notes):
                fid += 1
                if nt.kind == "variant-1955" and variants.says_nothing(
                        q.ex.text, q.ex.spans, nt.offset, nt.text, nt.spans):
                    report.hard("variant-says-nothing", q.ref,
                                f"the 1955 note {nt.text!r} has the text's words"
                                " and its italics")
                # srt_item_id is filled by build/srt.py, once the Foundation's
                # numbering is in.
                # A study note comes rendered, its math in it (build/study.py).
                # Each also with the book's soft hyphens, for a card and an
                # endnote, set justified as the text is.
                if nt.html is not None:
                    h, h_hy = nt.html, nt.html_hy
                else:
                    h = render(nt.text, nt.spans)
                    h_hy = render(nt.text, nt.spans, shy=hyphenator.points(nt.text, nt.spans))
                con.execute("INSERT INTO footnote (id, edition_id, kind, paragraph_id,"
                            " anchor, ord, text, html, html_hy) VALUES (?,1,?,?,?,?,?,?,?)",
                            (fid, nt.kind, qid, nt.offset, i, nt.text, h, h_hy))
    return para_key


def load_index(con, az, apps, para_key, report) -> None:
    eid = cid = tid = xid = evid = 0
    by_where = {}
    stack: dict[int, int] = {}
    root_of: dict[int, int] = {}

    def insert(e, scope):
        nonlocal eid
        eid += 1
        parent = stack.get(e.level - 1) if e.level > 1 else None
        root = eid if e.level == 1 else root_of.get(stack.get(1), eid)
        if e.level == 1:
            stack.clear()
        stack[e.level] = eid
        root_of[eid] = root
        for deeper in [k for k in list(stack) if k > e.level]:
            del stack[deeper]
        con.execute("INSERT INTO index_entry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (eid, scope, parent, root, e.level, e.letter, e.headword,
                     e.text, render_html(e.src_text), e.text_expanded, e.path, e.path_plain, xref.fold(e.path),
                     int(e.qv), e.where.split(":")[0], int(e.where.split(":")[1]),
                     e.ord))
        by_where[e.where] = eid
        return eid

    def cites_of(entry_id, where, cites):
        nonlocal cid, tid
        for i, raw in enumerate(cites):
            c = cite.parse(raw)
            if c is None:
                continue
            targets = list(c.expand())
            # The paragraphs that open a printed span: a range's first, or a
            # single number.  The rest of a range only continues it, and the
            # margin shows the entry at its first paragraph alone.  Both ends
            # of an inverted span (39:3.9-8, a defect) stay visible.
            opens = ({lo for lo, hi in c.spans} | {hi for lo, hi in c.spans if hi < lo}
                     if c.kind == "para" else None)
            cid += 1
            con.execute("INSERT INTO citation VALUES (?,?,?,?,?,?,?)",
                        (cid, entry_id, i, raw, cite.fmt(c), c.kind, len(targets)))
            for p, s, n in targets:
                tid += 1
                prec = "para" if n is not None else ("sec" if s is not None else "paper")
                con.execute("INSERT INTO citation_target VALUES (?,?,?,?,?,?,?,?,?)",
                            (tid, cid, entry_id, p, s, n, prec,
                             para_key.get((p, s, n)), int(opens is None or n in opens)))

    for e in az:
        i = insert(e, "az")
        cites_of(i, e.where, e.cites)

    for a in apps:
        con.execute("INSERT INTO appendix VALUES (?,?,?,?,?)",
                    (a.letter, a.name, a.title, len(a.entries), len(a.events)))
        stack.clear()
        for e in a.entries:
            i = insert(e, a.letter)
            cites_of(i, e.where, e.cites)
        for v in a.events:
            eid += 1
            con.execute("INSERT INTO index_entry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (eid, a.letter, None, eid, 1, None, None, v.text,
                         render_html(v.src_text), v.text, v.text, v.label, xref.fold(v.text), 0,
                         v.where.split(":")[0], int(v.where.split(":")[1]), v.ord))
            ysort, approx = parse_year(v.year_label)
            if ysort is None:
                report.hard("chron-unparsed-year", v.where, v.year_label)
            evid += 1
            line, reads_on = one_line(v.year_label, v.month_label, v.label)
            con.execute("INSERT INTO chronology_event VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (evid, eid, v.ord, v.year_label, ysort, int(approx),
                         v.month_label, v.text, line, int(reads_on)))
            cites_of(eid, v.where, v.cites)

    # Cross-references, resolved once the whole tree exists.
    heads = {}
    paths = {}
    for row in con.execute("SELECT id, level, headword, path FROM index_entry"
                           " WHERE scope='az' ORDER BY id"):
        i, level, head, path = row
        if level == 1 and head:
            heads.setdefault(xref.fold(head), i)
        paths.setdefault(_path_key(path), i)

    for e in list(az) + [x for a in apps for x in a.entries]:
        src = by_where.get(e.where)
        for i, (kind, target) in enumerate(e.xrefs):
            xid += 1
            route, head_id = _resolve(target, heads)
            if route is None:
                report.hard("xref-unresolved", e.where,
                            f"\\{kind}{{...}} -> {target!r}")
            con.execute("INSERT INTO xref VALUES (?,?,?,?,?,?,?,?,?)",
                        (xid, src, kind, i, target, xref.fold(target), route,
                         head_id, paths.get(_path_key_target(target))))

    # A q.v.: the entry's own text names a headword.  The same routes as a See,
    # and the same failure if it reaches none -- the print gate's `dead q.v.'.
    qv_head = {}
    for e in list(az) + [x for a in apps for x in a.entries]:
        if e.qv_target is None:
            continue
        xid += 1
        route, head_id = _resolve(e.qv_target, heads)
        if route is None:
            report.hard("qv-unresolved", e.where, f"{e.qv_target!r} q.v. names no headword")
        qv_head[e.where] = head_id
        con.execute("INSERT INTO xref VALUES (?,?,?,?,?,?,?,?,?)",
                    (xid, by_where[e.where], "qv", len(e.xrefs), e.qv_target,
                     xref.fold(e.qv_target), route, head_id, None))

    # Which A-Z headword each Appendix B-F row names: by its q.v., or by being
    # the same name.  Only an exact name counts here -- no list marker to strip,
    # no conjunction -- because a row with citations of its own is not pointing
    # anywhere, and a looser match would file it under a headword it is not.
    for a in apps:
        for e in a.entries:
            if e.where in qv_head:
                head, via = qv_head[e.where], "qv"
            else:
                head, via = heads.get(xref.fold(e.headword)), "name"
            if head is not None:
                con.execute("INSERT INTO appendix_head VALUES (?,?,?)",
                            (by_where[e.where], head, via))


import re  # noqa: E402
_RE_PAREN = re.compile(r"\s*\([^)]*\)")
_RE_SEE = re.compile(r"\s*\bSee(?: also)?\b.*$")


# Keys for resolving cross-references, never for display.  Both sides of a
# lookup are cleaned alike, so dropping every parenthesis is harmless here; what
# a reader sees is index_macros.label(), which keeps them.
def _clean(s: str) -> str:
    return _RE_PAREN.sub("", _RE_SEE.sub("", s)).strip()


def _path_key(path: str) -> str:
    return xref.fold(" ".join(_clean(p) for p in path.split(" > ")))


_RE_CONJ = re.compile(r"\s+and\s+|\s*,\s*")


def _resolve(target: str, heads: dict):
    """Which of xref.resolves()'s routes got there, and the head entry if one.

    Mirrors that function's order so the recorded route is the one the print
    gate would have taken.
    """
    for reading in xref.readings(target):
        h = heads.get(xref.fold(reading.split(":")[0]))
        if h is not None:
            return "head", h
        parts = [p for p in _RE_CONJ.split(reading) if p.strip()]
        if len(parts) > 1 and all(xref.fold(p) in heads for p in parts):
            return "conjunction", heads[xref.fold(parts[0])]
    members = xref.expand_range(target)
    if members and all(xref.fold(m) in heads for m in members):
        return "range", heads[xref.fold(members[0])]
    return None, None


def _path_key_target(target: str) -> str:
    return xref.fold(" ".join(_clean(p) for p in target.split(":")))
