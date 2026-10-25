"""What a page shows, as rows: the selection, apart from the drawing.

A rule about what stands beside a paragraph is decided here once, and the
templates only draw it.  The EPUB read it too until it was retired
(2026-10-19, tag `epub-last`).

Every function takes an open connection whose row_factory is sqlite3.Row.
Nothing here knows about requests, URLs or FastAPI.
"""

from __future__ import annotations

import datetime
import re
import sqlite3

# What a margin chip needs.  An appendix entry -- a Chronology event, a named
# being, person or place -- has no headword of its own and so no slug; it links
# to its line on the appendix page, named with its appendix, and an event with
# its date (chronology_event.label), and its place in Appendix A (ev_ord) for
# its window (windows, below); and an entry its own id, its headword's and its
# parent's, for standing with the others of its headword (groups, below).
# Its words are HTML, an ordinal's suffix superior (index_entry.path_html).
CHIP_COLS = ("e.path_html AS path, e.level, e.anchor, e.scope, r.slug AS rslug,"
             " r.anchor AS ranchor, a.title AS appendix, ev.label_html AS event, ev.ord AS ev_ord,"
             " e.id AS eid, e.root_id AS root, e.parent_id AS parent")
CHIP_JOIN = (" LEFT JOIN appendix a ON a.letter=e.scope"
             " LEFT JOIN chronology_event ev ON ev.entry_id=e.id")
# An Appendix B-F row beside a paragraph the A-Z already names it at -- by its
# headword or any subentry, at any precision -- says nothing the margin does not
# already say.  1,734 of the 1,865 did ("Abaddon" over "Celestial Beings,
# Individuals Named Abaddon"); the classification they carried is on the
# concept page instead.  Chronology events have no appendix_head and all stay.
CHIP_NEW = (" AND NOT EXISTS (SELECT 1 FROM appendix_head h"
            " JOIN para_citers c2 ON c2.paragraph_id = c.paragraph_id"
            " JOIN index_entry e2 ON e2.id = c2.entry_id"
            " WHERE h.entry_id = e.id AND e2.root_id = h.head_entry_id)")
# An entry citing a range stands beside its first paragraph only: 44:0.20-21
# beside 44:0.20, not 44:0.21 too, and 0:0.1-4 once, not four times (Tigran,
# 2026-10-13).  Its citation on the concept page still opens /44:0.20-21, with
# both tinted.  A comma list is not a range: 61:5.3,7 stands beside both.
# citation_target.opens is the parser's, set at load.
CHIP_OPENS = (" AND EXISTS (SELECT 1 FROM citation_target t"
              " WHERE t.paragraph_id = c.paragraph_id AND t.entry_id = c.entry_id"
              " AND t.opens)")

# A Chronology event beside the text stands in a window onto Appendix A: the
# event printed just before it and the one just after, each with its citations,
# so that the margin says where the event falls in the book's chronology, not
# only what the reader has just read (Geoff Theiss and Tigran, 2026-10-19).
# The event keeps its words (Tigran).  Events of one list that follow each
# other in the appendix share a window, so that no window points at an event
# standing beside it: 121:8.8's three make one.
def windows(con: sqlite3.Connection, chips: list) -> list:
    """`chips`, one list of them, with each run of Chronology events made one
    window: {"window": True, "events": [chip, ...], "before": row or None,
    "after": row or None}, where the run's first event stood.  A neighbour
    is chronology_event's ord, label and line_html; the appendix's first
    event has none before it, and its last none after."""
    runs: list[list] = []
    for c in chips:
        if c["ev_ord"] is None:
            continue
        if runs and runs[-1][-1]["ev_ord"] + 1 == c["ev_ord"]:
            runs[-1].append(c)
        else:
            runs.append([c])
    if not runs:
        return chips
    want = sorted({r[0]["ev_ord"] - 1 for r in runs} | {r[-1]["ev_ord"] + 1 for r in runs})
    near = {v["ord"]: v for v in con.execute(
        "SELECT ord, label, line_html FROM chronology_event WHERE ord IN"
        f" ({','.join('?' * len(want))})", want)}
    first = {r[0]["ev_ord"]: r for r in runs}
    out: list = []
    for c in chips:
        if c["ev_ord"] is None:
            out.append(c)
        elif c["ev_ord"] in first:
            r = first[c["ev_ord"]]
            out.append({"window": True, "events": r, "before": near.get(r[0]["ev_ord"] - 1),
                        "after": near.get(r[-1]["ev_ord"] + 1)})
    return out


# Entries of one headword beside one paragraph stand together, run on: the
# part they share said once, as deep as they share it, then each entry's own
# words, separated by semicolons -- "Elijah (Prophet) › John the Baptist ›
# adopted dress and method of Elijah; held back 2 years by expectation of
# return of" at 135:4.2, where each stood whole (Geoff Theiss and Tigran,
# 2026-10-19).  The shared part links to its own line, each entry's words to
# theirs.
def groups(con: sqlite3.Connection, chips: list) -> list:
    """`chips`, one list of them, with the A-Z entries of each headword made
    one group: {"group": True, "rslug", "head": {label, level, anchor},
    "tails": [{label, level, anchor}, ...], "entries": [chip, ...]}, where the
    first stood.  `head` is the entries' deepest common part, itself an entry
    of the index; an entry that is that part is the head's link and has no
    tail.  A headword with one entry here stays a chip."""
    by_root: dict[int, list] = {}
    for c in chips:
        if not isinstance(c, dict) and c["scope"] == "az":
            by_root.setdefault(c["root"], []).append(c)
    out: list = []
    for c in chips:
        es = [] if isinstance(c, dict) or c["scope"] != "az" else by_root[c["root"]]
        if len(es) < 2:
            out.append(c)
            continue
        if c is not es[0]:
            continue
        parts = [e["path"].split(SEP) for e in es]
        depth = 1
        while all(len(q) > depth for q in parts) and len({q[depth] for q in parts}) == 1:
            depth += 1
        tails = [{"label": SEP.join(q[depth:]), "level": e["level"], "anchor": e["anchor"]}
                 for e, q in zip(es, parts) if e["level"] > depth]
        if not tails:
            out += es
            continue
        head = (es[0]["parent"], es[0]["level"], es[0]["anchor"])
        while head[1] > depth:
            head = tuple(con.execute("SELECT parent_id, level, anchor FROM index_entry WHERE id=?",
                                     (head[0],)).fetchone())
        out.append({"group": True, "rslug": c["rslug"], "entries": es, "tails": tails,
                    "head": {"label": SEP.join(parts[0][:depth]), "level": head[1],
                             "anchor": head[2]}})
    return out


# The appendices first, in the volume's order -- the Chronology, then B-F --
# then the A-Z in the index's (Tigran, 2026-10-19): the Chronology's window
# heads the margin, and the A-Z's list stands unbroken under it.  Until then
# both were sorted by index_entry.ord, which numbers the appendices 1-1787 and
# the A-Z 1-32963 apart, so an appendix entry fell among the A-Z's A's by
# accident of number: at 121:8.8 the Chronology after "Acts, Book of".
CHIP_ORDER = " e.scope = 'az', e.ord"

# A section names at most this many blanket citations at its head.  None has
# more today; the cap is there so that a change upstream cannot bury the text.
BLANKET_MAX = 60


def section(con: sqlite3.Connection, paper: int, sec: int) -> dict:
    """One section's paragraphs and everything that stands beside them.

    paras    the paragraphs, in order, with para_density's precise_citers,
             and page_1955, where the paragraph begins in the first printing
    citers   paragraph id -> its chips, the entries citing it precisely, a
             range beside its first paragraph only (CHIP_OPENS)
    blanket  the entries citing the whole section -- read_pack's rule: listed
             ONCE at the section's head, never repeated under every paragraph,
             or Paper 15's 470 citations print some entries forty times over
             and the eye stops reading
    paperwide  the entries citing the whole paper: the same rule a level up,
             listed once, above section 0, and in no other section's box, as
             a range stands beside its first paragraph only (Tigran,
             2026-10-17).  Empty after section 0.  An entry citing the paper
             and section 0 alike is listed here only
             In all three a Chronology event stands in its window (windows),
             and the entries of one headword together (groups)
    nciters  paragraph id -> how many entries cite it, a window counting as
             its events; nwhole, the same for blanket and paperwide together
    notes    paragraph id -> its 1955 readings, as notes() gives them
    study    paragraph id -> its study notes, as study() gives them
    rows     the paragraphs as the page sets them: {"p": a paragraph}, or
             {"lines": [...]} for a block of verse, set as one (paragraph.verse_start),
             with the entries citing its lines gathered beside it
    """
    paras = con.execute(
        "SELECT p.*, d.precise_citers, u.page AS page_1955 FROM paragraph p"
        " LEFT JOIN para_density d ON d.paragraph_id=p.id"
        " LEFT JOIN uf_paragraph u ON u.paragraph_id=p.id"
        " WHERE p.paper_n=? AND p.section_n=? ORDER BY p.para_n",
        (paper, sec)).fetchall()
    citers: dict[int, list] = {}
    for row in con.execute(
            "SELECT c.paragraph_id, " + CHIP_COLS +
            " FROM para_citers c JOIN index_entry e ON e.id=c.entry_id"
            " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
            " JOIN paragraph p ON p.id=c.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision='para'" + CHIP_NEW + CHIP_OPENS +
            " ORDER BY" + CHIP_ORDER, (paper, sec)):
        citers.setdefault(row["paragraph_id"], []).append(row)
    def whole(precision: str, also: str = "") -> list:
        return con.execute(
            "SELECT DISTINCT " + CHIP_COLS +
            " FROM para_citers c"
            " JOIN index_entry e ON e.id=c.entry_id"
            " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
            " JOIN paragraph p ON p.id=c.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision=?" + CHIP_NEW + also +
            " ORDER BY" + CHIP_ORDER + f" LIMIT {BLANKET_MAX}", (paper, sec, precision)).fetchall()
    paperwide = whole("paper") if sec == 0 else []
    blanket = whole("sec", " AND NOT EXISTS (SELECT 1 FROM para_citers c3"
                           " WHERE c3.paragraph_id = c.paragraph_id"
                           " AND c3.entry_id = c.entry_id AND c3.precision = 'paper')")
    # The entries counted before their windows are drawn: what a fold says.
    nciters = {pid: len(cs) for pid, cs in citers.items()}
    nwhole = len(paperwide) + len(blanket)
    citers = {pid: groups(con, windows(con, cs)) for pid, cs in citers.items()}
    paperwide = groups(con, windows(con, paperwide))
    blanket = groups(con, windows(con, blanket))
    by_para: dict[int, list] = {}
    for n in notes(con, "p.paper_n=? AND p.section_n=?", (paper, sec)):
        by_para.setdefault(n["paragraph_id"], []).append(n)
    by_para_st: dict[int, list] = {}
    for n in study(con, "p.paper_n=? AND p.section_n=?", (paper, sec)):
        by_para_st.setdefault(n["paragraph_id"], []).append(n)
    rows: list[dict] = []
    for q in paras:
        if q["src"] == "vs":
            rows.append({"p": q})
        elif q["verse_start"] or not rows or "lines" not in rows[-1]:
            rows.append({"lines": [q]})
        else:
            rows[-1]["lines"].append(q)
    return {"paras": paras, "rows": rows, "citers": citers, "blanket": blanket,
            "paperwide": paperwide, "nciters": nciters, "nwhole": nwhole,
            "notes": by_para, "study": by_para_st}


def notes(con: sqlite3.Connection, where: str = "1", params: tuple = ()) -> list[dict]:
    """The 1955 readings `where` selects, in the order of the book.

    Each as the press gives it (the footnote's own columns), in its paragraph
    (para_ref, para_text, para_html, paper_n, section_n, para_n, paper_title), with the
    SRT Committee's reasons for the change where it gives them (verdict,
    srt_why, srt_href) and the note it refers to (see_*).  `key` is the note's
    in section.html, fn<key> and fnref<key>.  Never the committee's quotation
    of the 1955 text: its page misquotes it in places, and what 1955 said is
    the press's to say (Tigran).  A section, the List of 1955 readings and a
    search's hits all show a note through this.
    """
    out = []
    for f in con.execute(
            "SELECT f.*, p.ref AS para_ref, p.text AS para_text, p.html AS para_html,"
            " p.paper_n, p.section_n,"
            " p.para_n, pa.title AS paper_title, s.verdict, s.why_html AS srt_why,"
            " s.why_html_hy AS srt_why_hy, t.why_html_hy AS see_why_hy,"
            " (SELECT commit_url FROM build_source WHERE repo='srt') || '#' || s.name AS srt_href,"
            " t.verdict AS see_verdict, t.why_html AS see_why, tp.ref AS see_ref"
            " FROM footnote f JOIN paragraph p ON p.id=f.paragraph_id"
            " JOIN paper pa ON pa.n=p.paper_n"
            " LEFT JOIN srt_item s ON s.id=f.srt_item_id"
            " LEFT JOIN srt_item t ON t.id=s.see_id"
            " LEFT JOIN paragraph tp ON tp.id=t.paragraph_id"
            " WHERE f.kind='variant-1955' AND (" + where + ")"
            " ORDER BY p.ord, f.ord", params):
        n = dict(f)
        # A change that says only "Adopted" shares the reasons given for the
        # first under its anchor, in the same paragraph (134:3.3): they are its
        # own.  A note referred to elsewhere stays apart, named by its paragraph.
        if n["see_why"] and not n["srt_why"] and n["see_ref"] == n["para_ref"]:
            n["srt_why"], n["see_why"] = n["see_why"], None
            n["srt_why_hy"], n["see_why_hy"] = n["see_why_hy"], None
        n["key"] = f'{n["paper_n"]}_{n["section_n"]}_{n["para_n"]}_{n["ord"]}'
        out.append(n)
    return out


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def study(con: sqlite3.Connection, where: str = "1", params: tuple = ()) -> list[dict]:
    """The study notes `where` selects, in the order of the book.

    Each as reviewed (build/study.py): its number in the paper (num), its HTML,
    the sources it cites, in full and in the order of its [1], [2] (sources:
    each its html, and its url where it can be read freely), and its credit.
    Credit goes only where a note rests on someone's research (Tigran,
    2026-10-18): Block's chart for the paper, by its own date (Tigran,
    2026-10-19: the address's month is when it was uploaded) and with
    its address (block, block_url), and what the note corrects in it from the
    original (corrects, HTML), or a contributor's line as written (credit).
    `key` is the note's in section.html, fn<key> and fnref<key>.  A section
    and the List of study notes show a note through this.
    """
    out = []
    for f in con.execute(
            "SELECT f.id, f.html, f.html_hy, f.paragraph_id, f.anchor, f.ord, s.num, s.key, s.credit, s.corrects,"
            " s.human_source, p.ref AS para_ref, p.text AS para_text, p.paper_n, p.section_n,"
            " p.para_n, pa.title AS paper_title, x.block_url, x.block_date"
            " FROM study_note s JOIN footnote f ON f.id = s.footnote_id"
            " JOIN paragraph p ON p.id = f.paragraph_id JOIN paper pa ON pa.n = p.paper_n"
            " JOIN study_paper x ON x.paper_n = s.paper_n"
            " WHERE (" + where + ") ORDER BY p.ord, f.anchor, f.ord", params):
        n = dict(f)
        n["sources"] = [{"html": h, "url": u} for h, u in con.execute(
            "SELECT x.html, x.url FROM study_cite c JOIN study_source x ON x.id = c.source_id"
            " WHERE c.footnote_id = ? ORDER BY c.ord", (n["id"],))]
        n["block"] = None
        if n["credit"] == "block" and n["block_date"]:
            d = datetime.date.fromisoformat(n["block_date"])
            n["block"] = f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
            n["credit"] = None
        out.append(n)
    return out


def bibliography(con: sqlite3.Connection) -> list[dict]:
    """Every work the study notes on the site cite, once, in the order of its
    key, the author's surname (Tigran, 2026-10-19): its entry as reviewed
    (html), its page where it can be read freely (url, Tigran's library, or
    None), and the notes citing it (cited_by), in the order of the book, each
    with its paragraph (para_ref), its number in its paper (num) and its key.
    A key names one work in every paper (build/study.py one_work_one_key)."""
    works: dict[str, dict] = {}
    for key, html, url, ref, num, note in con.execute(
            "SELECT x.key, x.html, x.url, p.ref, s.num, s.key FROM study_source x"
            " JOIN study_cite c ON c.source_id = x.id"
            " JOIN study_note s ON s.footnote_id = c.footnote_id"
            " JOIN footnote f ON f.id = s.footnote_id JOIN paragraph p ON p.id = f.paragraph_id"
            " ORDER BY p.ord, f.anchor, f.ord"):
        w = works.setdefault(key, {"key": key, "html": html, "url": url, "cited_by": []})
        w["cited_by"].append({"para_ref": ref, "num": num, "key": note})
    return sorted(works.values(), key=lambda w: w["key"].casefold())


def concept(con: sqlite3.Connection, root_id: int) -> dict:
    """A headword's page: its tree, its cross-references, what lists it, and
    the headwords most often cited beside it."""
    tree = con.execute(
        "SELECT e.*, s.n_targets FROM index_entry e"
        " LEFT JOIN entry_stats s ON s.entry_id=e.id"
        " WHERE e.root_id=? ORDER BY e.ord", (root_id,)).fetchall()
    # Every See, See also and q.v. is linked where it stands, in the tree; this
    # list gathers the See and See also, each by the link it has there.
    xrefs = con.execute(
        "SELECT x.kind, x.target_html, x.href FROM xref x"
        " WHERE x.entry_id IN (SELECT id FROM index_entry WHERE root_id=?)"
        "   AND x.kind IN ('see','seealso')"
        " ORDER BY x.kind, x.ord", (root_id,)).fetchall()
    # The appendices that list this headword: what kind of thing it is -- a
    # being, a person, a place -- and its line there.
    listed = con.execute(
        "SELECT e.scope, e.anchor, a.title FROM appendix_head h"
        " JOIN index_entry e ON e.id=h.entry_id JOIN appendix a ON a.letter=e.scope"
        " WHERE h.head_entry_id=? ORDER BY e.scope", (root_id,)).fetchall()
    near = con.execute(
        "SELECT o.slug, o.headword_html, c.shared,"
        "  (SELECT n_descendants FROM entry_stats WHERE entry_id=o.id) AS kids"
        " FROM cocitation c"
        " JOIN index_entry o ON o.id = CASE WHEN c.a_root_id=? THEN c.b_root_id"
        "                                   ELSE c.a_root_id END"
        " WHERE c.a_root_id=? OR c.b_root_id=? ORDER BY c.shared DESC LIMIT 8",
        (root_id, root_id, root_id)).fetchall()
    # Its reading path, if it cites enough paragraphs to have one (derive.py).
    path = con.execute("SELECT * FROM reading_path WHERE root_id=?", (root_id,)).fetchone()
    return {"tree": tree, "xrefs": xrefs, "listed": listed, "near": near, "path": path}


# ---- reading paths -----------------------------------------------------------

# A 1955 reading's ring, which is empty.  A path is read for its topic, and the
# reader keeps the readings; By theme can also draw a paragraph twice, folded
# and cited, and the ring's id would repeat.
RING = re.compile(r'<a class="fn"[^>]*></a>')
BR = re.compile(r"\s*<br\s*/?>\s*")
SEP = " › "


def _label(e, depth: int) -> str:
    """An entry named from where it stands: its path less the first `depth`
    parts.  Under prayer, "prayer › private prayer" is "private prayer".  As
    HTML, an ordinal's suffix superior (index_entry.path_html)."""
    return SEP.join(e["path_html"].split(SEP)[depth:])


def _add(d: dict, k, e) -> None:
    lst = d.setdefault(k, [])
    if e not in lst:
        lst.append(e)


class _Sel:
    """What a set of citations draws: paragraphs cited precisely (`cited`), and
    the entries opening a citation at each (`opens`); sections cited whole
    (`secs`) and papers cited whole (`papers`), with their entries."""

    def __init__(self, targets, by_id):
        self.cited: set = set()
        self.opens: dict = {}
        self.secs: dict = {}
        self.papers: dict = {}
        for t in targets:
            e = by_id[t["entry_id"]]
            if t["precision"] == "para":
                self.cited.add(t["paragraph_id"])
                if t["opens"]:
                    _add(self.opens, t["paragraph_id"], e)
            elif t["precision"] == "sec":
                _add(self.secs, (t["paper"], t["section"]), e)
            else:
                _add(self.papers, t["paper"], e)


def reading_path(con: sqlite3.Connection, root_id: int, by: str = "book") -> dict:
    """A headword's citations, read as one text: /i/<slug>/read.

    by        "book", one run in the order of the book; or "theme", the
              headword's own citations and then each level-2 subentry's
              subtree, in the index's order, each in the order of the book
    chapters  each {id, entry, name, own, n_full, n_again, rows}; book order
              is one chapter with no name
    rows      in the order of the book, each a dict with a `kind`:
              head   where the section changes: its paper's and its own title,
                     and the entries citing it whole (`why`)
              sign   a paper cited whole: a pointer into the reader, not its text
              stars  a separator the book prints between two paragraphs drawn
              p      a paragraph, and the entries whose citation opens there
                     (`why`): a range beside its first paragraph only, the
                     margin's rule (CHIP_OPENS)
              lines  lines of one block of verse, drawn as one, each line's
                     entries under its reference (`why`, [(ref, entries)])
              again  a paragraph drawn in full above: one line, with the
                     `anchor` it was drawn at and `where`, its chapter
              fold   what a section has between two paragraphs drawn and does
                     not cite here: `rows` as above, without entries
    A paragraph is drawn in full once on the page, `id` true, where it takes
    its reference as its id; a fold's copy of one cited elsewhere has none.
    An entry in `why` is {label, whole, level, anchor}, named from where it
    stands.  Also: n_full and n_words (what reading_path counts), n_again,
    n_folds, and refw, the longest reference drawn.
    """
    root = con.execute("SELECT * FROM index_entry WHERE id=?", (root_id,)).fetchone()
    entries = con.execute(
        "SELECT id, parent_id, level, anchor, path_html FROM index_entry"
        " WHERE root_id=? ORDER BY ord", (root_id,)).fetchall()
    by_id = {e["id"]: e for e in entries}
    level2: dict[int, int] = {}                     # in print order, a parent first
    for e in entries:
        level2[e["id"]] = e["id"] if e["level"] <= 2 else level2[e["parent_id"]]
    targets = con.execute(
        "SELECT t.entry_id, t.precision, t.paragraph_id, t.paper, t.section, t.opens"
        " FROM citation_target t JOIN citation c ON c.id=t.citation_id"
        " JOIN index_entry e ON e.id=t.entry_id"
        " WHERE e.root_id=? ORDER BY e.ord, c.ord, t.id", (root_id,)).fetchall()
    # Every paragraph of every section the headword touches, for the folds.
    P: dict[int, dict] = {}
    by_sec: dict[tuple, list] = {}
    for r in con.execute(
            "WITH s(pn, sn) AS ("
            "  SELECT q.paper_n, q.section_n FROM citation_target t"
            "  JOIN index_entry e ON e.id=t.entry_id JOIN paragraph q ON q.id=t.paragraph_id"
            "  WHERE e.root_id=:r AND t.precision='para'"
            "  UNION SELECT t.paper, t.section FROM citation_target t"
            "  JOIN index_entry e ON e.id=t.entry_id WHERE e.root_id=:r AND t.precision='sec')"
            " SELECT p.id, p.ref, p.paper_n, p.section_n, p.para_n, p.ord, p.src, p.gap_before,"
            "  p.heading, p.sep_before, p.verse_start, p.setoff, p.html_hy, p.word_count,"
            "  u.page AS page_1955"
            " FROM paragraph p JOIN s ON s.pn=p.paper_n AND s.sn=p.section_n"
            " LEFT JOIN uf_paragraph u ON u.paragraph_id=p.id ORDER BY p.ord", {"r": root_id}):
        q = dict(r)
        q["html_hy"] = RING.sub("", q["html_hy"])
        sec = by_sec.setdefault((q["paper_n"], q["section_n"]), [])
        q["pos"] = len(sec)
        sec.append(q)
        P[q["id"]] = q
    papers = dict(con.execute("SELECT n, title FROM paper").fetchall())
    titles = {(r["paper_n"], r["n"]): r for r in con.execute(
        "SELECT paper_n, n, title_html, combined_with FROM section")}
    first_ord = {}
    if any(t["precision"] == "paper" for t in targets):
        first_ord = dict(con.execute(
            "SELECT paper_n, MIN(ord) FROM paragraph GROUP BY paper_n").fetchall())

    seen: dict[int, tuple] = {}                     # paragraph id -> (anchor, where)
    tally = {"n_full": 0, "n_words": 0, "n_again": 0, "n_folds": 0, "refw": 1}

    def why(es, depth, whole=""):
        out = []
        for e in es:
            label = _label(e, depth) or (e["path_html"] if e["level"] == 1 else "")
            if label or whole:
                out.append({"label": label, "whole": whole, "level": e["level"],
                            "anchor": e["anchor"]})
        return out

    def head(p, whole):
        t = titles[(p["paper_n"], p["section_n"])]
        return {"kind": "head", "paper": p["paper_n"], "paper_title": papers[p["paper_n"]],
                "section": p["section_n"], "combined": t["combined_with"],
                "title": BR.sub(" ", t["title_html"] or ""), "why": whole}

    def draw(items, p, es, prev, where, fold):
        tally["refw"] = max(tally["refw"], len(p["ref"]))
        if p["sep_before"] and prev is not None and p["pos"] == prev["pos"] + 1:
            items.append({"kind": "stars", "stars": p["sep_before"]})
        if p["id"] in seen:
            anchor, w = seen[p["id"]]
            items.append({"kind": "again", "p": p, "anchor": anchor, "where": w})
            tally["n_again"] += not fold
            return
        line = {"p": p, "id": not fold}
        last = items[-1] if items else None
        if p["src"] == "vs":
            items.append({"kind": "p", **line, "why": es})
        elif (last and last["kind"] == "lines" and not p["verse_start"]
              and last["lines"][-1]["p"]["pos"] + 1 == p["pos"]
              and last["lines"][-1]["p"]["section_n"] == p["section_n"]):
            last["lines"].append(line)
            if es:
                last["why"].append((p["ref"], es))
        else:
            items.append({"kind": "lines", "lines": [line],
                          "why": [(p["ref"], es)] if es else []})
        if not fold:
            seen[p["id"]] = (p["ref"], where)
            tally["n_full"] += 1
            tally["n_words"] += p["word_count"]

    def run(sel, depth, where):
        shown = set(sel.cited)
        for k in sel.secs:
            shown.update(q["id"] for q in by_sec[k])
        events = sorted([(P[i]["ord"], 1, P[i]) for i in shown]
                        + [(first_ord[n], 0, n) for n in sel.papers],
                        key=lambda x: (x[0], x[1]))
        items: list = []
        last = prev = None
        for _, kind, x in events:
            if kind == 0:
                items.append({"kind": "sign", "paper": x, "title": papers[x],
                              "why": why(sel.papers[x], depth, "the whole paper")})
                last = prev = None
                continue
            p, k = x, (x["paper_n"], x["section_n"])
            if k != last:
                items.append(head(p, why(sel.secs.get(k, []), depth, "the whole section")))
                last, prev = k, None
            elif p["pos"] > prev["pos"] + 1:
                between = by_sec[k][prev["pos"] + 1:p["pos"]]
                inner: list = []
                for q in between:
                    draw(inner, q, [], prev, where, True)
                    prev = q
                items.append({"kind": "fold", "first": between[0], "last": between[-1],
                              "n": len(between), "rows": inner})
                tally["n_folds"] += 1
            draw(items, p, why(sel.opens.get(p["id"], []), depth), prev, where, False)
            prev = p
        return items

    if by == "theme":
        groups = [(root, [t for t in targets if t["entry_id"] == root_id])]
        groups += [(e, [t for t in targets if t["entry_id"] != root_id
                        and level2[t["entry_id"]] == e["id"]])
                   for e in entries if e["level"] == 2]
        groups = [g for g in groups if g[1]]
    else:
        groups = [(None, targets)]
    chapters = []
    for i, (e, ts) in enumerate(groups):
        own = e is None or e["id"] == root_id
        name = "" if e is None else root["headword_html"] if own else _label(e, 1)
        full, again = tally["n_full"], tally["n_again"]
        items = run(_Sel(ts, by_id), 1 if own else 2, name)
        chapters.append({"id": f"ch{i + 1}", "entry": e, "name": name, "own": own,
                         "n_full": tally["n_full"] - full,
                         "n_again": tally["n_again"] - again, "rows": items})
    return {"root": root, "by": by, "chapters": chapters, **tally}


def appendices(con: sqlite3.Connection) -> list:
    """The six appendices, for /appendix, /index and each appendix's own page."""
    return con.execute("SELECT letter, title, n_entries, n_events FROM appendix"
                       " ORDER BY letter").fetchall()


def appendix_rows(con: sqlite3.Connection, letter: str) -> list:
    """An Appendix B-F's rows, in the print's order."""
    return con.execute(
        "SELECT e.anchor, e.headword, e.text_html FROM index_entry e"
        " WHERE e.scope=? ORDER BY e.ord", (letter,)).fetchall()


# The Chronology's jump bar.  The printed list has no divisions; these are only
# for finding one's place among 206 year headings.  The first three follow the
# book's own unit, which is "years ago" until Adam and B.C. from him on; the
# life of Jesus, from the announcements of 8 B.C. to 30 A.D., is half the list.
CHRON_BANDS = ["Billions of years ago", "Millions of years ago",
               "Thousands of years ago", "B.C.", "The life of Jesus", "A.D."]


def band(label: str, year_sort: float) -> int:
    if "years ago" in label:
        n = int(label.split()[0].replace(",", ""))
        return 0 if n >= 10**9 else 1 if n >= 10**6 else 2
    return 3 if year_sort < -8 else 4 if year_sort <= 30 else 5


def year_id(label: str) -> str:
    """'y-7-b-c' for 7 B.C.: from the label, so that it does not move."""
    return "y-" + re.sub(r"[^0-9a-z]+", "-", label.lower()).strip("-")


def chronology(con: sqlite3.Connection) -> tuple[list, list]:
    """Appendix A as printed: years, the months under some of them, the events.

    A \\chrontext hangs off its year and a \\chronsubtext off its month, which
    is what month_label records; within a year the former all come first.
    Returns (years, bands): each year {label, id, items}, an item either
    {event} or {month, events}; each band {n, name, id, events}.
    """
    years, bands = [], []
    for r in con.execute(
            "SELECT e.anchor, e.text_html, v.year_label, v.month_label, v.year_sort"
            " FROM chronology_event v JOIN index_entry e ON e.id=v.entry_id"
            " ORDER BY v.ord"):
        if not years or years[-1]["label"] != r["year_label"]:
            years.append({"label": r["year_label"], "id": year_id(r["year_label"]),
                          "items": []})
            b = band(r["year_label"], r["year_sort"])
            if not bands or bands[-1]["n"] != b:
                bands.append({"n": b, "name": CHRON_BANDS[b], "id": years[-1]["id"],
                              "events": 0})
        bands[-1]["events"] += 1
        items = years[-1]["items"]
        if r["month_label"] is None:
            items.append({"event": r})
        else:
            if not items or items[-1].get("month") != r["month_label"]:
                items.append({"month": r["month_label"], "events": []})
            items[-1]["events"].append(r)
    return years, bands
