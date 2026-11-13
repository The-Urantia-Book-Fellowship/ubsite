"""What a page shows, as rows: the selection, apart from the drawing.

A rule about what stands beside a paragraph is decided here once, and the
templates only draw it.  The EPUB read it too until it was retired
(2026-10-19, tag `epub-last`).

Every function takes an open connection whose row_factory is sqlite3.Row.
Nothing here knows about requests, URLs or FastAPI.
"""

from __future__ import annotations

import re
import sqlite3

from markupsafe import escape

from ubsite import l10n

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


def translated(con: sqlite3.Connection, paper: int, sec: int) -> dict:
    """What the translations have of one section (build/translation.py), for
    the fold under each paragraph (ROADMAP item 15, step 2).

    has    paragraph id -> the keys of the translations that have it, in
           Settings' order, separated by spaces: the fold's data-has
    heads  its titles there, each translation's, for Compare's columns, as its
           style sets them: its word for a Paper and the paper's number
           ('paper', not over the Foreword), the paper's title and author, and
           the section's title, its number added where its style adds it
           (translation.numbers).  A translation with no paragraph here has none
    rows   every translation's paragraphs of the section, each with its key, our
           reference, its language and its notes: the translator's, each with
           its number in the paper, the works it cites, and the translation's
           title and short name, for its card (_note.html tnote)

    The fragment /tr/<paper>:<section> sends is these drawn
    (templates/tr_section.html), and its version their hash (app.py).
    """
    rows = [dict(r, notes=[]) for r in con.execute(
        "SELECT t.translation AS k, p.id AS pid, p.ref, t.html_hy, r.lang FROM tr_paragraph t"
        " JOIN paragraph p ON p.id = t.paragraph_id JOIN translation r ON r.key = t.translation"
        " WHERE p.paper_n = ? AND p.section_n = ? ORDER BY r.ord, p.para_n", (paper, sec))]
    has: dict[int, list[str]] = {}
    for r in rows:
        has.setdefault(r["pid"], []).append(r["k"])
    keys = list(dict.fromkeys(r["k"] for r in rows))
    # A paper's title written in capitals, as ud's \upaper sets them, as its
    # printed contents give it, where they do, as the left rail has it (Tigran,
    # 2026-10-27: "Print it in proper case, like all the others"); any other
    # stays as the paper writes it (the two must agree but for case, which
    # build/translation.py slips() holds them to).  A title written only in capitals, a
    # paper's or a section's, is set in small capitals, as the rail sets it
    # (tr_toc.caps).
    toc = {(t["k"], t["kind"]): (t["html"], t["caps"]) for t in con.execute(
        "SELECT translation AS k, kind, html, caps FROM tr_toc WHERE n = ?"
        " AND (kind = 'paper' OR kind = 'section' AND section_n = ?)", (paper, sec))}

    def cased(k: str, kind: str, html: str) -> str:
        own, caps = toc.get((k, kind), (None, 0))
        text = re.sub(r"<[^>]+>", "", html)
        if kind == "paper" and own is not None and text == text.upper():
            html = own
        return f'<span class="caps">{html}</span>' if caps else html
    heads = []
    for h in con.execute(
            "SELECT h.translation AS k, h.kind, h.html, r.lang, r.paper, r.numbers FROM tr_heading h"
            " JOIN translation r ON r.key = h.translation"
            " WHERE h.paper_n = ? AND (h.section_n IS NULL OR h.section_n = ?)"
            " ORDER BY r.ord, h.section_n IS NOT NULL, h.kind DESC", (paper, sec)):
        if h["k"] not in keys:
            continue
        if h["kind"] == "title" and paper:
            heads.append({"k": h["k"], "kind": "paper", "html": f"{escape(h['paper'])} {paper}", "lang": h["lang"]})
        html = h["html"]
        if h["kind"] == "title":
            html = cased(h["k"], "paper", html)
        elif h["kind"] == "section":
            html = cased(h["k"], "section", html)
            if h["numbers"]:
                html = f"{sec}. {html}"
        heads.append({"k": h["k"], "kind": h["kind"], "html": html, "lang": h["lang"]})
    row_of = {(r["k"], r["pid"]): r for r in rows}
    for n in con.execute(
            "SELECT n.id, n.translation AS k, n.paragraph_id AS pid, n.num, n.key, n.html_hy,"
            " p.ref, r.lang, r.title, r.label FROM tr_note n JOIN paragraph p ON p.id = n.paragraph_id"
            " JOIN translation r ON r.key = n.translation"
            " WHERE p.paper_n = ? AND p.section_n = ? ORDER BY n.num", (paper, sec)):
        row_of[(n["k"], n["pid"])]["notes"].append(dict(n, sources=[
            {"html": h, "url": None} for (h,) in con.execute(
                "SELECT x.html FROM tr_cite c JOIN tr_source x ON x.id = c.source_id"
                " WHERE c.note_id = ? ORDER BY c.ord", (n["id"],))]))
    return {"has": {pid: " ".join(ks) for pid, ks in has.items()}, "heads": heads, "rows": rows}


def tr_parts(con: sqlite3.Connection, n: int) -> list[dict]:
    """Each translation's divider of part n (build/translation.py _parts), for
    the part's own page (templates/part.html; Tigran, 2026-11-07): its key,
    language, title and short name, which name it over its divider as Compare
    names a column; and the divider's own word and number, its title and the
    sponsors' note, a list of its paragraphs.  Every translation's, in
    Settings' order, since no setting reaches the server."""
    try:
        rows = con.execute(
            "SELECT p.translation AS key, r.lang, r.title, r.label, p.label AS word, p.title AS head, p.sponsor"
            " FROM tr_part p JOIN translation r ON r.key = p.translation WHERE p.n = ? ORDER BY r.ord",
            (n,)).fetchall()
    except sqlite3.Error:
        return []                                # a database from before tr_part
    return [dict(r, sponsor=r["sponsor"].split("\n")) for r in rows]


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
            n["block"] = l10n.date(n["block_date"])
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
    """An Appendix B-F's rows, in the print's order, each with the address of
    its headword in the A-Z, where it has one: what the chart of the
    personalities is found by (cosmo_marks)."""
    return con.execute(
        "SELECT e.anchor, e.headword, e.text_html, a.slug AS head_slug FROM index_entry e"
        " LEFT JOIN appendix_head h ON h.entry_id = e.id LEFT JOIN index_entry a ON a.id = h.head_entry_id"
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


# ---- the quiz -------------------------------------------------------------------

def quiz(con: sqlite3.Connection, paper: int | None = None) -> list[dict]:
    """The quiz's questions, one paper's or all, in the order of the book
    (build/quiz.py): what /quiz/N and /quiz send the browser, which asks them.

    Each: its id and the layout of its answers (v), by which the browser keeps
    an answer; `m`, the right answers as bits, for the browser to mark them,
    offline too; the question and its answers as HTML; and what answers it,
    where the review has said (`s`): the passages of the text (`k` "text"),
    `p`, each a paragraph's words or a run of paragraphs whole, its `ref` then
    "0:3.2-8", in the order ruled, with `ref` the first's; a study note
    (`k` "note"); or, for a note whose paper's notes are not yet reviewed, the
    paragraph itself (`k` "para"), without its rings and markers, since no
    card of theirs is on the page.  A question kept out (`drop`) is not sent.
    """
    where, args = ("WHERE q.paper_n = ?", (paper,)) if paper is not None else ("", ())
    try:
        rows = con.execute(
            "SELECT q.id, q.paper_n, q.ord, q.v, q.mask, q.html, q.state, f.html AS note_html"
            f" FROM quiz_question q LEFT JOIN footnote f ON f.id = q.footnote_id {where}"
            " ORDER BY q.paper_n, q.ord", args).fetchall()
        passages: dict[int, list[dict]] = {}
        for qid, ref, last, h in con.execute(
                "SELECT r.question_id, p.ref, l.para_n, r.quote_html FROM quiz_ref r"
                " JOIN quiz_question q ON q.id = r.question_id"
                " JOIN paragraph p ON p.id = r.paragraph_id LEFT JOIN paragraph l ON l.id = r.paragraph_last_id"
                f" {where} ORDER BY r.question_id, r.n", args):
            passages.setdefault(qid, []).append({"ref": ref + (f"-{last}" if last else ""), "h": h})
    except sqlite3.Error:
        return []                  # a database from before the quiz
    answers: dict[int, list[str]] = {}
    for qid, html in con.execute("SELECT question_id, html FROM quiz_answer ORDER BY question_id, n"
                                 if paper is None else
                                 "SELECT a.question_id, a.html FROM quiz_answer a JOIN quiz_question q"
                                 " ON q.id = a.question_id WHERE q.paper_n = ? ORDER BY a.question_id, a.n",
                                 () if paper is None else (paper,)):
        answers.setdefault(qid, []).append(html)
    out = []
    for r in rows:
        s, ps = None, passages.get(r["id"], [])
        if r["state"] == "drop":
            continue
        if r["state"] == "text" and ps:
            s = {"k": "text", "ref": ps[0]["ref"], "p": ps}
        elif r["state"] == "note" and r["note_html"] and ps:
            s = {"k": "note", "ref": ps[0]["ref"], "h": r["note_html"]}
        elif r["state"] == "note" and ps:
            s = {"k": "para", "ref": ps[0]["ref"], "h": ps[0]["h"]}
        out.append({"id": r["id"], "p": r["paper_n"], "v": r["v"], "m": r["mask"],
                    "q": r["html"], "a": answers.get(r["id"], []), "s": s})
    return out


def quiz_papers(con: sqlite3.Connection) -> list[dict]:
    """Every paper that has questions, with its part and how many: /quiz's
    list, the invitation at a paper's end, the way on from a paper's quiz."""
    try:
        return [dict(r) for r in con.execute(
            "SELECT q.paper_n AS n, q.n AS count, p.title, p.part_n AS part FROM quiz_paper q"
            " JOIN paper p ON p.n = q.paper_n ORDER BY q.paper_n")]
    except sqlite3.Error:
        return []


def quiz_count(con: sqlite3.Connection, paper: int) -> int:
    """How many questions the quiz asks on a paper: 0 for none, or for a
    database from before the quiz."""
    try:
        r = con.execute("SELECT n FROM quiz_paper WHERE paper_n = ?", (paper,)).fetchone()
    except sqlite3.Error:
        return 0
    return r[0] if r else 0


# ---- the chart of the personalities (build/cosmo.py) -------------------------

# A dot to each Deity a personality comes of, as his engine colours them, and
# the evolutionary; and what each letter of `origin` is called, in the chart's
# own words: the personality, the unit or the class of that id (his engine
# knows `father`, `son`, `spirit` and `trinity` by name too).
COSMO_ORIGIN = {"F": ("#e53935", ("person", "father")), "S": ("#1e63d6", ("person", "son")),
                "D": ("#f2b705", ("person", "spirit")), "E": ("#43a047", ("class", "E")),
                "A": (None, ("class", "A")), "T": (None, ("unit", "trinity"))}
# Where a sign's dots stand, from its middle: lower in a triangle that points
# up, higher in one that points down, as his engine sets them.
COSMO_DOTS_AT = {"ascender": (3, 1.0), "descending": (-3, 1.0), "angel": (3, 0.9), "spirit": (0, 1.0),
                 "local": (0, 1.0)}


def _cosmo_dots(glyph: str, origin: str) -> list[dict]:
    """The dots in a card's sign: one to each Deity of its origin, the three
    for the Trinity's.  None in a Deity's own sign, an Absolute's, or the
    Trinity's."""
    if glyph not in COSMO_DOTS_AT:
        return []
    dy, s = COSMO_DOTS_AT[glyph]
    ks = [k for k in ("FSD" if origin == "T" else origin) if COSMO_ORIGIN.get(k, (None,))[0]]
    r, d = (4.2 if len(ks) == 1 else 2.8) * s, 3.6 * s
    at = {1: [(0, 0)], 2: [(-d, 0), (d, 0)], 3: [(0, -d), (-d, d * .8), (d, d * .8)]}.get(len(ks), [])
    return [{"x": round(x, 2), "y": round(y + dy, 2), "r": round(r, 2), "color": COSMO_ORIGIN[k][0]}
            for k, (x, y) in zip(ks, at)]


def cosmo(con: sqlite3.Connection) -> dict | None:
    """The chart of the personalities, as its page draws it (cosmology.html):
    the canvas, the units' boxes, the cards, the lines in each language, the
    legend's keys, and an entry to every unit and personality, with what the
    lines say of it in words, where the book speaks of it and its headwords in
    the index.  None where the database has no chart."""
    try:
        meta = dict(con.execute("SELECT key, value FROM cosmo_meta").fetchall())
    except sqlite3.Error:
        return None
    if not meta:
        return None
    words: dict[tuple, dict[str, list[str]]] = {}
    for kind, key, field, lang, text in con.execute(
            "SELECT kind, key, field, lang, text FROM cosmo_text ORDER BY kind, key, field, lang, ord"):
        words.setdefault((kind, key, field), {}).setdefault(lang, []).append(text)

    def say(kind, key, field, sep=None) -> l10n.L | None:
        """A text in each language; where one has none, the English."""
        w = words.get((kind, key, field))
        if not w:
            return None
        en = w.get("en") or next(iter(w.values()))
        by = {lang: (w.get(lang) or en) for lang in l10n.LANGS}
        return l10n.L({lang: escape(v[0] if sep is None else sep.join(v)) for lang, v in by.items()})

    keys = {}
    for kind in ("class", "group", "func"):
        keys[kind] = {r["key"]: {"key": r["key"], "color": r["color"], "name": say(kind, r["key"], "name"), "n": 0}
                      for r in con.execute("SELECT * FROM cosmo_key WHERE kind=? ORDER BY ord", (kind,))}
    units = {r["id"]: dict(r) for r in con.execute("SELECT * FROM cosmo_unit ORDER BY ord")}
    for r in con.execute("SELECT unit, lang, w FROM cosmo_title"):
        units[r["unit"]]["title_" + r["lang"]] = r["w"]
    persons = {r["id"]: dict(r) | {"groups": [], "funcs": [], "fuse": []}
               for r in con.execute("SELECT * FROM cosmo_person ORDER BY ord")}
    for r in con.execute("SELECT person, kind, key FROM cosmo_tag ORDER BY person, kind, ord"):
        p = persons[r["person"]]
        if r["kind"] == "fuse":
            p["fuse"].append(r["key"])
        else:
            which = "group" if r["kind"] == "group" else "func"
            p["groups" if which == "group" else "funcs"].append(keys[which][r["key"]])
            keys[which][r["key"]]["n"] += 1
    for p in persons.values():
        keys["class"][p["class"]]["n"] += 1
    refs: dict[tuple, list[dict]] = {}
    for r in con.execute("SELECT * FROM cosmo_ref ORDER BY kind, key, ord"):
        s = r["section_n"]
        refs.setdefault((r["kind"], r["key"]), []).append(
            {"href": f"/{r['paper_n']}" + (f":{s}" if s is not None else ""),
             "label": l10n.L.same(f"{r['paper_n']}:{s}") if s is not None
             else l10n.tr("Paper {n}", n=r["paper_n"])})
    heads: dict[tuple, list[dict]] = {}
    for r in con.execute("SELECT h.kind, h.key, h.slug, e.headword_html FROM cosmo_head h"
                         " JOIN index_entry e ON e.slug = h.slug AND e.scope='az' AND e.level=1"
                         " ORDER BY h.kind, h.key, h.ord"):
        heads.setdefault((r["kind"], r["key"]), []).append({"slug": r["slug"], "html": r["headword_html"]})

    places = [dict(r) for r in con.execute("SELECT * FROM cosmo_place ORDER BY y, x")]
    at = {pl["id"]: pl for pl in places}
    cw, ch = int(meta["card_w"]), int(meta["card_h"])

    def name_of(end: str) -> l10n.L:
        return say("unit", end, "name") if end in units else say("person", end.lstrip("~"), "name")

    def anchor(end: str) -> str:
        return end.lstrip("~")

    def chain(unit: str) -> list[dict]:
        out = []
        while unit:
            out.append({"id": unit, "name": say("unit", unit, "name")})
            unit = units[unit]["parent"]
        return out[::-1]

    cards = []
    for pl in places:
        p = persons[pl["person"]]
        there = say("person", p["id"], "there") if pl["ghost"] else None
        cards.append({
            "dom": ("g-" if pl["ghost"] else "c-") + p["id"], "id": p["id"], "ghost": pl["ghost"],
            "unit": pl["unit"], "x": pl["x"], "y": pl["y"], "name": there or say("person", p["id"], "name"),
            "class": p["class"], "color": keys["class"][p["class"]]["color"],
            "groups": p["groups"], "funcs": p["funcs"], "glyph": p["glyph"],
            "glyph_color": keys["group"][p["glyph_group"]]["color"],
            # A Deity's disc is the colour of its dot in the others' signs, or
            # where it has none (the Supreme Being), of its class.
            "disc": COSMO_ORIGIN.get(p["origin"], (None,))[0] or keys["class"][p["class"]]["color"],
            "dots": _cosmo_dots(p["glyph"], p["origin"])})

    links = []
    routes: dict[int, dict[str, str]] = {}
    for r in con.execute("SELECT link_id, lang, d FROM cosmo_route"):
        routes.setdefault(r["link_id"], {})[r["lang"]] = r["d"]
    for r in con.execute("SELECT * FROM cosmo_link ORDER BY id"):
        links.append(dict(r) | {"d": routes[r["id"]]})

    # A pair is drawn in one frame, where both stand, and again where both serve.
    pairs = []
    for p in persons.values():
        if not p["pair"] or p["id"] > p["pair"]:
            continue
        for pre in ("", "~"):
            both = [at.get(pre + i) for i in (p["id"], p["pair"])]
            if not all(both):
                continue
            x0, y0 = min(b["x"] for b in both) - 12, min(b["y"] for b in both) - 12
            x1, y1 = max(b["x"] for b in both) + cw + 12, max(b["y"] for b in both) + ch + (24 if pre else 12)
            pairs.append({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "ghost": bool(pre)})

    def relations(me: str) -> dict:
        """What the lines say of a unit or a personality, in words: what it
        comes of and what comes of it, what serves it or it serves, and the
        way up through it."""
        mine = {me, "~" + me}
        out = {"parents": [], "children": [], "service": [], "ascent": []}

        def add(to, end, arrow=None):
            item = {"id": anchor(end), "name": name_of(end), "arrow": arrow}
            if (item["id"], arrow) not in [(x["id"], x["arrow"]) for x in out[to]]:
                out[to].append(item)

        for l in links:
            if l["a"] not in mine and l["b"] not in mine:
                continue
            other, mine_is_b = (l["a"], True) if l["b"] in mine else (l["b"], False)
            if l["type"] == "origin":
                add("parents" if mine_is_b else "children", other)
            elif l["type"] == "service":
                add("service", other)
            else:
                add("ascent", other, "from" if mine_is_b else "to")
        return out

    entries = []
    by_unit: dict[str, list[str]] = {}
    for pl in sorted((x for x in places if not x["ghost"]), key=lambda x: (x["row"], x["col"])):
        by_unit.setdefault(pl["unit"], []).append(pl["person"])
    for u in units.values():
        u["name"] = say("unit", u["id"], "name")
        entries.append({
            "kind": "unit", "id": u["id"], "name": u["name"], "desc": say("unit", u["id"], "desc"),
            "color": u["color"], "chain": chain(u["parent"]) if u["parent"] else [],
            "members": [{"id": i, "name": say("person", i, "name")} for i in by_unit.get(u["id"], [])],
            "refs": refs.get(("unit", u["id"]), []), "heads": heads.get(("unit", u["id"]), []),
            "search": " ".join(x for lang in l10n.LANGS for x in words[("unit", u["id"], "name")].get(lang, [])),
            **relations(u["id"])})
        for pid in by_unit.get(u["id"], []):
            p = persons[pid]
            ghost = at.get("~" + pid)
            origin = [{"color": COSMO_ORIGIN[k][0], "name": say(*COSMO_ORIGIN[k][1], "name")}
                      for k in p["origin"] if k in COSMO_ORIGIN and say(*COSMO_ORIGIN[k][1], "name")]
            entries.append({
                "kind": "person", "id": pid, "name": say("person", pid, "name"),
                "aka": say("person", pid, "aka", ", "), "desc": say("person", pid, "desc"),
                "color": keys["class"][p["class"]]["color"],
                "class": keys["class"][p["class"]], "groups": p["groups"], "funcs": p["funcs"], "origin": origin,
                "chain": chain(u["id"]),
                "serves": {"unit": {"id": ghost["unit"], "name": say("unit", ghost["unit"], "name")},
                           "how": say("person", pid, "serves"),
                           "as": say("person", pid, "there")} if ghost else None,
                "pair": {"id": p["pair"], "name": say("person", p["pair"], "name")} if p["pair"] else None,
                "fuse": [{"id": i, "name": say("person", i, "name")} for i in p["fuse"]],
                "refs": refs.get(("person", pid), []), "heads": heads.get(("person", pid), []),
                "search": " ".join(x for f in ("name", "aka") for lang in l10n.LANGS
                                   for x in words.get(("person", pid, f), {}).get(lang, [])),
                **relations(pid)})

    return {"meta": meta, "w": int(meta["w"]), "h": int(meta["h"]), "card": (cw, ch),
            "units": list(units.values()), "cards": cards, "links": links, "pairs": pairs,
            "legend": {k: list(v.values()) for k, v in keys.items()}, "entries": entries,
            # The legend's key to the dots: each Deity, and the evolutionary.
            "origins": [{"color": COSMO_ORIGIN[k][0], "name": say(*COSMO_ORIGIN[k][1], "name")}
                        for k in "FSDE" if say(*COSMO_ORIGIN[k][1], "name")],
            "counts": {"persons": len(persons), "units": len(units), "links": len(links)}}


def cosmo_marks(con: sqlite3.Connection, slugs: list[str]) -> dict[str, list[dict]]:
    """{slug: [{id, name}]}: what on the chart of the personalities has a
    headword for its own, so that the headword's page can show it there."""
    if not slugs:
        return {}
    try:
        rows = con.execute(
            "SELECT h.slug, h.key, h.kind FROM cosmo_head h WHERE h.slug IN (%s) ORDER BY h.kind, h.key"
            % ",".join("?" * len(slugs)), slugs).fetchall()
    except sqlite3.Error:
        return {}
    out: dict[str, list[dict]] = {}
    for r in rows:
        w = {lang: [t for (t,) in con.execute(
            "SELECT text FROM cosmo_text WHERE kind=? AND key=? AND field='name' AND lang=? ORDER BY ord",
            (r["kind"], r["key"], lang))] for lang in l10n.LANGS}
        en = w["en"] or w["ru"]
        out.setdefault(r["slug"], []).append(
            {"id": r["key"], "name": l10n.L({lang: escape((w[lang] or en)[0]) for lang in l10n.LANGS})})
    return out
