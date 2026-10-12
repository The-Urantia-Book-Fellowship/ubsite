"""What a page shows, as rows: the queries the site and the EPUB share.

Two views read `var/ub.db` -- the site (app.py) and the book (epub/) -- and a
rule about what stands beside a paragraph must not exist twice, or the two
will drift.  So the selection lives here, and each view only draws it: the
site with its own hrefs and Jinja templates, the EPUB with its own.

Every function takes an open connection whose row_factory is sqlite3.Row.
Nothing here knows about requests, URLs or FastAPI, so the EPUB can import it
without starting the site.
"""

from __future__ import annotations

import re
import sqlite3

# What a margin chip needs.  An appendix entry -- a Chronology event, a named
# being, person or place -- has no headword of its own and so no slug; it links
# to its line on the appendix page, named with its appendix, and an event with
# its date (chronology_event.label).
CHIP_COLS = ("e.path_plain AS path, e.level, e.anchor, e.scope, r.slug AS rslug,"
             " r.anchor AS ranchor, a.title AS appendix, ev.label AS event")
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

# A section names at most this many blanket citations at its head.  None has
# more today; the cap is there so that a change upstream cannot bury the text.
BLANKET_MAX = 60


def section(con: sqlite3.Connection, paper: int, sec: int) -> dict:
    """One section's paragraphs and everything that stands beside them.

    paras    the paragraphs, in order, with para_density's precise_citers, thin,
             and page_1955, where the paragraph begins in the first printing
    citers   paragraph id -> its chips, the entries citing it precisely
    blanket  the entries citing the whole section or paper -- read_pack's rule:
             listed ONCE at the section's head, never repeated under every
             paragraph, or Paper 15's 470 citations print some entries forty
             times over and the eye stops reading
    notes    paragraph id -> its 1955 readings, as notes() gives them
    """
    paras = con.execute(
        "SELECT p.*, d.precise_citers, d.thin, u.page AS page_1955 FROM paragraph p"
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
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision='para'" + CHIP_NEW +
            " ORDER BY e.ord", (paper, sec)):
        citers.setdefault(row["paragraph_id"], []).append(row)
    blanket = con.execute(
        "SELECT DISTINCT " + CHIP_COLS +
        " FROM para_citers c"
        " JOIN index_entry e ON e.id=c.entry_id"
        " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
        " JOIN paragraph p ON p.id=c.paragraph_id"
        " WHERE p.paper_n=? AND p.section_n=? AND c.precision IN ('sec','paper')" + CHIP_NEW +
        f" ORDER BY e.ord LIMIT {BLANKET_MAX}", (paper, sec)).fetchall()
    by_para: dict[int, list] = {}
    for n in notes(con, "p.paper_n=? AND p.section_n=?", (paper, sec)):
        by_para.setdefault(n["paragraph_id"], []).append(n)
    return {"paras": paras, "citers": citers, "blanket": blanket, "notes": by_para}


def notes(con: sqlite3.Connection, where: str = "1", params: tuple = ()) -> list[dict]:
    """The 1955 readings `where` selects, in the order of the book.

    Each as the press gives it (the footnote's own columns), in its paragraph
    (para_ref, para_text, paper_n, section_n, para_n, paper_title), with the
    SRT Committee's reasons for the change where it gives them (verdict,
    srt_why, srt_href) and the note it refers to (see_*).  `key` is the note's
    in section.html, fn<key> and fnref<key>.  Never the committee's quotation
    of the 1955 text: its page misquotes it in places, and what 1955 said is
    the press's to say (Tigran).  A section, the List of 1955 readings and a
    search's hits all show a note through this, and the EPUB too.
    """
    out = []
    for f in con.execute(
            "SELECT f.*, p.ref AS para_ref, p.text AS para_text, p.paper_n, p.section_n,"
            " p.para_n, pa.title AS paper_title, s.verdict, s.why_html AS srt_why,"
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
        n["key"] = f'{n["paper_n"]}_{n["section_n"]}_{n["para_n"]}_{n["ord"]}'
        out.append(n)
    return out


def concept(con: sqlite3.Connection, root_id: int) -> dict:
    """A headword's page: its tree, its cross-references, what lists it, and
    the headwords most often cited beside it."""
    tree = con.execute(
        "SELECT e.*, s.n_targets FROM index_entry e"
        " LEFT JOIN entry_stats s ON s.entry_id=e.id"
        " WHERE e.root_id=? ORDER BY e.ord", (root_id,)).fetchall()
    # A q.v. is linked where it stands, in the tree; this list is See and See also.
    xrefs = con.execute(
        "SELECT x.kind, x.target, t.slug FROM xref x"
        " LEFT JOIN index_entry t ON t.id=x.head_entry_id"
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
        "SELECT o.slug, o.headword, c.shared,"
        "  (SELECT n_descendants FROM entry_stats WHERE entry_id=o.id) AS kids"
        " FROM cocitation c"
        " JOIN index_entry o ON o.id = CASE WHEN c.a_root_id=? THEN c.b_root_id"
        "                                   ELSE c.a_root_id END"
        " WHERE c.a_root_id=? OR c.b_root_id=? ORDER BY c.shared DESC LIMIT 8",
        (root_id, root_id, root_id)).fetchall()
    return {"tree": tree, "xrefs": xrefs, "listed": listed, "near": near}


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
