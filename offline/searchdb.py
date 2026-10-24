"""The two databases offline search runs on, cut from ub.db.

Each holds what app.py's search() reads and nothing more: everything a page
shows is already in its stored page, so the database is only for finding.
Two, because they change apart: the text's (its paragraphs and the 1955
readings) moves when the text does, and the index's whenever the index is
edited, which is most deploys.  The worker attaches the second to the first
as `ix`; search's queries name no schema, and SQLite finds each table in the
one that has it.

The full-text tables are declared as ub.db declares them, read from its
schema, so the tokenizer cannot drift.  One difference: the index's is
contentless.  Search ranks and counts by it but never takes a snippet of it,
so the text it indexes need not be stored a second time (4.5 MB).

Where a hit's text has superscripts, "611,121st", their places in it are
stored beside it as "start-end start-end" (app.py sups()), and the worker sets
them as the server does (app.py _snip, offline-core.js snip).

A 1955 reading among the results is a list line (templates/_old.html) around
the reading and the committee's words, which a search marks.  Each line is
rendered here by the site's own macros with placeholders where those go, \x01
for the reading and \x02 for the reasons, and the worker fills them in.
"""

from __future__ import annotations

import re
import sqlite3

from markupsafe import Markup


def _at(ranges) -> str:
    """Where a text's superscripts stand (app.py sups()), as the worker reads it."""
    return " ".join(f"{a}-{b}" for a, b in ranges)


def _declared(con: sqlite3.Connection, name: str) -> str:
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
    if sql is None:
        raise LookupError(f"ub.db has no {name}")
    return sql[0]


def _done(out: sqlite3.Connection) -> bytes:
    out.commit()
    out.execute("VACUUM")
    data = out.serialize()
    out.close()
    return data


def text_db(con: sqlite3.Connection) -> bytes:
    """The paragraphs, their full-text index, and the 1955 readings'."""
    from ubsite import app as A, queries
    out = sqlite3.connect(":memory:")
    out.executescript("""
        CREATE TABLE paragraph (id INTEGER PRIMARY KEY, ref TEXT NOT NULL,
                                ord INTEGER NOT NULL, text TEXT NOT NULL, sups TEXT NOT NULL);
        CREATE TABLE footnote (id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                               paragraph_id INTEGER NOT NULL, ord INTEGER NOT NULL);
        -- A 1955 reading's line among the results: pre + reading + post, or
        -- with the committee's words, pre + reading + mid + reasons + tail.
        -- card is its note, which the line's ring opens; reading_sups and
        -- reasons_sups, where the superscripts stand in footnote_fts's columns.
        CREATE TABLE note_html (id INTEGER PRIMARY KEY, pre TEXT NOT NULL, post TEXT NOT NULL,
                                mid TEXT NOT NULL, tail TEXT NOT NULL, card TEXT NOT NULL,
                                reading_sups TEXT NOT NULL, reasons_sups TEXT NOT NULL);
    """)
    out.execute(_declared(con, "paragraph_fts"))
    out.execute(_declared(con, "footnote_fts"))
    out.executemany("INSERT INTO paragraph VALUES (?,?,?,?,?)",
                    ((i, ref, o, t, _at(A.sups(h))) for i, ref, o, t, h in
                     con.execute("SELECT id, ref, ord, text, html FROM paragraph ORDER BY id")))
    out.execute("INSERT INTO paragraph_fts(paragraph_fts) VALUES('rebuild')")
    out.executemany("INSERT INTO footnote VALUES (?,?,?,?)",
                    con.execute("SELECT id, kind, paragraph_id, ord FROM footnote ORDER BY id"))
    out.executemany("INSERT INTO footnote_fts(rowid, reading, reasons) VALUES (?,?,?)",
                    con.execute("SELECT rowid, reading, reasons FROM footnote_fts ORDER BY rowid"))
    old = A.T.env.get_template("_old.html").module
    card = A.T.env.get_template("_note.html").module
    at = {i: (_at(A.sups(h)), _at(A._reasons_at(a_text, a_html, b_text, b_html)))
          for i, h, a_text, a_html, b_text, b_html in con.execute(
              "SELECT f.id, f.html, s.why_text, s.why_html, t.why_text, t.why_html FROM footnote f"
              " LEFT JOIN srt_item s ON s.id = f.srt_item_id LEFT JOIN srt_item t ON t.id = s.see_id")}
    rows = []
    for n in queries.notes(con):
        one = str(old.old_hit(A._old_hit(n, Markup("\x01"))))
        two = str(old.old_hit(A._old_hit(n, Markup("\x01"), reasons=Markup("\x02"))))
        pre, post = one.split("\x01")
        pre2, rest = two.split("\x01")
        mid, tail = rest.split("\x02")
        if pre2 != pre or "\x01" in post + tail or "\x02" in post:
            raise ValueError(f"a 1955 reading's line does not cut: {n['key']}")
        rows.append((n["id"], pre, post, mid, tail, str(card.note(n)), *at[n["id"]]))
    out.executemany("INSERT INTO note_html VALUES (?,?,?,?,?,?,?,?)", rows)
    for t in ("paragraph_fts", "footnote_fts"):
        out.execute(f"INSERT INTO {t}({t}) VALUES('optimize')")
    return _done(out)


def index_db(con: sqlite3.Connection) -> bytes:
    """The index's entries as search lists them, and their full-text index."""
    from ubsite import app as A
    out = sqlite3.connect(":memory:")
    out.executescript("""
        CREATE TABLE index_entry (id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
                                  root_id INTEGER NOT NULL, level INTEGER NOT NULL,
                                  headword TEXT, headword_html TEXT,
                                  path_plain TEXT NOT NULL, path_sups TEXT NOT NULL,
                                  ord INTEGER NOT NULL, slug TEXT, anchor TEXT);
        CREATE TABLE entry_stats (entry_id INTEGER PRIMARY KEY, n_descendants INTEGER NOT NULL);
        CREATE TABLE appendix_head (entry_id INTEGER PRIMARY KEY);
        CREATE TABLE chronology_event (entry_id INTEGER NOT NULL, label TEXT NOT NULL,
                                       label_sups TEXT NOT NULL);
        CREATE INDEX chronology_event_entry ON chronology_event(entry_id);
        CREATE TABLE appendix (letter TEXT PRIMARY KEY, title TEXT NOT NULL);
    """)
    decl = _declared(con, "index_entry_fts")
    contentless, n = re.subn(r"content\s*=\s*'index_entry'\s*,\s*content_rowid\s*=\s*'id'",
                             "content=''", decl)
    if n != 1:
        raise ValueError(f"index_entry_fts is not declared as offline/searchdb.py expects: {decl}")
    out.execute(contentless)
    out.executemany("INSERT INTO index_entry VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
        (*r[:7], _at(A.sups(r[7])), *r[8:]) for r in con.execute(
            "SELECT id, scope, root_id, level, headword, headword_html, path_plain, path_html,"
            " ord, slug, anchor FROM index_entry ORDER BY id")))
    out.executemany("INSERT INTO index_entry_fts(rowid, text_expanded, path) VALUES (?,?,?)",
                    con.execute("SELECT id, text_expanded, path FROM index_entry ORDER BY id"))
    out.executemany("INSERT INTO entry_stats VALUES (?,?)",
                    con.execute("SELECT entry_id, n_descendants FROM entry_stats ORDER BY entry_id"))
    out.executemany("INSERT INTO appendix_head VALUES (?)",
                    con.execute("SELECT entry_id FROM appendix_head ORDER BY entry_id"))
    out.executemany("INSERT INTO chronology_event VALUES (?,?,?)",
                    ((i, label, _at(A.sups(h))) for i, label, h in con.execute(
                        "SELECT entry_id, label, label_html FROM chronology_event ORDER BY id")))
    out.executemany("INSERT INTO appendix VALUES (?,?)",
                    con.execute("SELECT letter, title FROM appendix ORDER BY letter"))
    out.execute("INSERT INTO index_entry_fts(index_entry_fts) VALUES('optimize')")
    return _done(out)
