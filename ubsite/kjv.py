"""The King James Version's pages: what they read from var/kjv.db (build/kjv.py).

A database of its own beside ub.db (Tigran, 2026-11-21), opened read-only by
these functions alone.  The pages (app.py kjv_*) are /kjv, the 66 books; /kjv/Mat,
a book's title and its chapters; /kjv/Mat/5, a chapter; /kjv/Mat/5:48 and
/kjv/Psa/104:1-2, the chapter with those verses tinted, as /101:4.2 tints a
paragraph.  An address's book is the edition's abbreviation (data/kjv/books.tsv),
for ever.
"""

from __future__ import annotations

import functools
import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "var" / "kjv.db"

# A chapter, a verse or a range of verses in it, after the book: 5, 5:48, 104:1-2.
RE_AT = re.compile(r"([0-9]{1,3})(?::([0-9]{1,3})(?:-([0-9]{1,3}))?)?")


def there() -> bool:
    return DB.exists()


def db() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


@functools.lru_cache(maxsize=2)
def _books(mtime_ns: int) -> tuple[dict, ...]:
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM kjv_book ORDER BY id")]
    for r in rows:
        r["title_lines"] = json.loads(r["title_lines"])
    return tuple(rows)


def books() -> tuple[dict, ...]:
    """The 66, in the KJV's order, each its row of kjv_book."""
    return _books(DB.stat().st_mtime_ns)


def book(abbr: str) -> dict | None:
    """A book by its abbreviation, exactly as written: Gen, 1Sa, Sol."""
    return next((b for b in books() if b["abbr"] == abbr), None)


def book_loosely(name: str) -> dict | None:
    """A book by its abbreviation in any case (gen, 1SA), or by its name as a
    reference writes it with or without its spaces (Genesis, 1 Samuel,
    1samuel, songofsolomon): the address to send such a reader on to."""
    key = re.sub(r"[\s_]+", "", name).lower()
    for b in books():
        if key in (b["abbr"].lower(), b["ref_name"].replace(" ", "").lower(),
                   b["name"].replace(" ", "").lower()):
            return b
    return None


def chapter(b: dict, c: int) -> dict:
    """A chapter's verses, each with its note, and where its neighbours are."""
    with db() as con:
        vs = [dict(r) for r in con.execute(
            "SELECT v.*, n.html AS note_html, n.html_hy AS note_hy FROM kjv_verse v"
            " LEFT JOIN kjv_note n ON n.verse_id = v.id"
            " WHERE v.book = ? AND v.chapter = ? ORDER BY v.verse", (b["id"], c))]
        first, last = vs[0]["id"], vs[-1]["id"]
        prev = con.execute("SELECT b.abbr, b.ref_name, v.chapter FROM kjv_verse v JOIN kjv_book b"
                           " ON b.id = v.book WHERE v.id < ? ORDER BY v.id DESC LIMIT 1", (first,)).fetchone()
        nxt = con.execute("SELECT b.abbr, b.ref_name, v.chapter FROM kjv_verse v JOIN kjv_book b"
                          " ON b.id = v.book WHERE v.id > ? ORDER BY v.id LIMIT 1", (last,)).fetchone()
    for v in vs:
        v["key"] = f"{b['abbr']}{c}_{v['verse']}"
        # A letter of Psalm 119 is a heading; a psalm's title is set small.
        v["letter"] = bool(re.fullmatch(r"[A-Z]+\.", v["head"]))
    i = b["id"] - 1
    return {"verses": vs, "prev": prev and dict(prev), "next": nxt and dict(nxt),
            "fb": books()[i - 1] if i else None, "ff": books()[i + 1] if i + 1 < len(books()) else None}


def name(b: dict, c: int | None = None, v: int | None = None, w: int | None = None) -> str:
    """A reference as the page writes it: Matthew 5, Matthew 5:48, Psalms 104:1–2.
    A book of one chapter by its verse alone is still Jude 1:24, as the KJV
    numbers it."""
    s = b["ref_name"]
    if c is not None:
        s += f" {c}"
    if v is not None:
        s += f":{v}" + (f"–{w}" if w and w != v else "")
    return s


def href(b: dict, c: int | None = None, v: int | None = None, w: int | None = None) -> str:
    s = f"/kjv/{b['abbr']}"
    if c is not None:
        s += f"/{c}"
    if v is not None:
        s += f":{v}" + (f"-{w}" if w and w != v else "")
    return s


# A Bible address typed in the search box, "John 3:16", "Gen 1:1", "1 John
# 4:8", "Psalm 23", "Jude 24": the book by any name book_loosely() knows, or
# Psalm, then a chapter, a verse, a range.  None where it is no such address,
# or names a chapter the book lacks, and the search goes on as words.
RE_JUMP = re.compile(r"\s*([1-3I]{0,3}\s*[A-Za-z][A-Za-z ]*?)\.?\s+([0-9]{1,3})"
                     r"(?::([0-9]{1,3})(?:\s*[-–]\s*([0-9]{1,3}))?)?\s*")


def jump(q: str) -> str | None:
    if not there():
        return None
    m = RE_JUMP.fullmatch(q)
    if m is None:
        return None
    name = m[1].strip()
    b = book_loosely("Psalms" if name.lower() == "psalm" else name)
    if b is None:
        return None
    c, v, w = int(m[2]), m[3] and int(m[3]), m[4] and int(m[4])
    if b["chapters"] == 1 and v is None:         # Jude 24: a book of one chapter, by its verse
        c, v = 1, c
    if not 1 <= c <= b["chapters"]:
        return None
    return href(b, c, v, w) if v else href(b, c)


def hits(fq: str, limit: int, offset: int) -> tuple[int, list[dict]]:
    """The verses whose words, or whose note's, the search found, in the
    Bible's order: (how many, this window of them), each with its reference,
    its address, and what was found in its words and in its note, as FTS5's
    snippet() marks it (app.py _snip makes the HTML)."""
    hit = ("SELECT rowid AS vid FROM kjv_verse_fts WHERE kjv_verse_fts MATCH ?"
           " UNION SELECT rowid FROM kjv_note_fts WHERE kjv_note_fts MATCH ?")
    with db() as con:
        n = con.execute(f"SELECT COUNT(*) FROM ({hit})", (fq, fq)).fetchone()[0]
        rows = [dict(r) for r in con.execute(
            f"SELECT h.vid, b.abbr, b.ref_name, v.chapter, v.verse FROM ({hit}) h"
            " JOIN kjv_verse v ON v.id = h.vid JOIN kjv_book b ON b.id = v.book"
            " ORDER BY v.id LIMIT ? OFFSET ?", (fq, fq, limit, offset))]
        ids = [r["vid"] for r in rows]
        within = ",".join("?" * len(ids))
        said = dict(con.execute(
            "SELECT rowid, snippet(kjv_verse_fts, 0, char(2), char(3), char(4), 24) FROM kjv_verse_fts"
            f" WHERE kjv_verse_fts MATCH ? AND rowid IN ({within})", (fq, *ids)))
        noted = dict(con.execute(
            "SELECT rowid, snippet(kjv_note_fts, 0, char(2), char(3), char(4), 24) FROM kjv_note_fts"
            f" WHERE kjv_note_fts MATCH ? AND rowid IN ({within})", (fq, *ids)))
    for r in rows:
        r["ref"] = f"{r['ref_name']} {r['chapter']}:{r['verse']}"
        r["href"] = f"/kjv/{r['abbr']}/{r['chapter']}:{r['verse']}"
        r["s"], r["note"] = said.get(r["vid"]), noted.get(r["vid"])
    return n, rows
