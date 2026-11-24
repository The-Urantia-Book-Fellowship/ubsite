"""The units Search by meaning searches: what each is, and its text.

A unit is a piece of what the site knows, of a size a question can be set
beside: a paragraph of the book, an entry of the index, a study note, a
passage of the King James Version.  Each has a text,
which the model turns into a vector (tools/embed/build.py), and a name, by
which the site finds the paragraphs to show for it (ubsite/meaning.py).

This module composes them, from var/ub.db and var/bible.db alone, in one
order, with nothing in them that moves when nothing has changed: no date, no
row id but an index entry's, which is held by the entry's path beside it.  A
unit's `hash` is the SHA-256 of its text; a text that has not changed keeps
its vector, and the gate (build/checks/check_embed.py) holds var/embed.db to
exactly the units composed here today.

Not build/units.py, which is Unit conversions.

The kinds, in the order they stand:

  para   a paragraph, under its paper's and section's titles.  Named by its
         reference, 101:4.2.
  entry  an entry of the index that cites something: its path from its
         headword down, each level's abbreviations written out (the index
         writes "T.A." under Thought Adjusters), without its citations.
         Named by its path as the index shows it; its target is its id.
  note   a study note on the site, its words.  Named by its key; its target
         is its paragraph.
  kjv    a passage of the King James Version, under its book and chapter:
         the 1769 paragraphs (a chapter's start or a pilcrow, to the next),
         which end at Acts 20:36, and a chapter where there are none; one of
         more than KJV_WHOLE verses in runs of KJV_RUN, each beginning
         KJV_STEP on.  A psalm's title stands with its first verses.  Named
         by its verses, Gen 1:1-5.

Two things were tried on 2026-11-24 and are not here, the retrieval test
(tools/embed/bench.py) having counted against them.  Windows, three
paragraphs running in a section at every step, for an answer that lies across
a paragraph's end: found by meaning they were right in the first ten for 70.6%
of the edition's 773 questions where the paragraphs alone were for 84.7%, and
fused with the paragraphs they brought those down to 78.0%, in Russian as in
English, whether a window stood for its three paragraphs or for its best one.
And a list's lead before a short item ("5. Associate Transcendental Master
Force Organizers." under the paragraph that opens its list): 84.7% with it,
85.4% without.  The titles stay: without them 84.1%, and in Russian 78.1% for
79.5%.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3

# Raised when what a unit's text is made of changes in a way its hash would
# not show (nothing yet: a new text is a new hash).  Recorded in embed_meta.
RECIPE = 1

KINDS = ("para", "entry", "note", "kjv")

KJV_WHOLE = 8         # verses: a paragraph of the KJV up to this long is one unit
KJV_RUN = 5           # verses to a run of a longer one
KJV_STEP = 3          # each run begins this many verses after the last
SEP = " › "      # between the levels of an entry's path, as path_plain has it


@dataclasses.dataclass(frozen=True)
class Unit:
    kind: str
    label: str
    target: str
    text: str

    @property
    def hash(self) -> bytes:
        return hashlib.sha256(self.text.encode("utf-8")).digest()


def _titles(paper_title: str, section_title: str | None) -> str:
    return f"{paper_title}: {section_title}" if section_title else paper_title


def _text(ub: sqlite3.Connection) -> list[Unit]:
    """The paragraphs, in the book's order."""
    rows = ub.execute(
        "SELECT p.ref, p.text, k.title AS paper_title, s.title AS section_title"
        "  FROM paragraph p JOIN section s ON s.id = p.section_id JOIN paper k ON k.id = s.paper_id"
        " ORDER BY p.ord").fetchall()
    return [Unit("para", r["ref"], "", _titles(r["paper_title"], r["section_title"]) + "\n" + r["text"])
            for r in rows]


def _entries(ub: sqlite3.Connection) -> list[Unit]:
    """The index's entries that cite something, in the index's order."""
    rows = ub.execute(
        "SELECT e.id, e.parent_id, e.text, e.text_expanded, e.path_plain,"
        "       EXISTS (SELECT 1 FROM citation c WHERE c.entry_id = e.id) AS cites"
        "  FROM index_entry e ORDER BY e.ord, e.id").fetchall()
    by_id = {r["id"]: r for r in rows}
    own: dict[int, str] = {}

    def words(r: sqlite3.Row) -> str:
        """An entry's own words with its abbreviations written out, without
        its citations: what `text` has after the last level of its path is
        its citations, and `text_expanded` ends with the same."""
        last = r["path_plain"].split(SEP)[-1]
        if r["text"].startswith(last):
            tail = r["text"][len(last):]
            if r["text_expanded"].endswith(tail):
                return r["text_expanded"][:len(r["text_expanded"]) - len(tail)].strip() if tail else r["text_expanded"].strip()
        return last

    def path(i: int) -> str:
        if i not in own:
            r = by_id[i]
            up = path(r["parent_id"]) + SEP if r["parent_id"] is not None else ""
            own[i] = up + words(r)
        return own[i]

    return [Unit("entry", r["path_plain"], str(r["id"]), path(r["id"])) for r in rows if r["cites"]]


def _notes(ub: sqlite3.Connection) -> list[Unit]:
    """The study notes on the site, in the book's order."""
    rows = ub.execute(
        "SELECT s.key, p.ref, f.text FROM footnote f JOIN study_note s ON s.footnote_id = f.id"
        "  JOIN paragraph p ON p.id = f.paragraph_id WHERE f.kind = 'study'"
        " ORDER BY p.ord, f.anchor, f.ord, f.id").fetchall()
    return [Unit("note", r["key"], r["ref"], r["text"]) for r in rows]


def _kjv(bible: sqlite3.Connection) -> list[Unit]:
    """The King James Version's passages, in its order."""
    books = {r["id"]: r for r in bible.execute("SELECT id, abbr, en FROM bible_book")}
    rows = bible.execute(
        "SELECT book, chapter, verse, kind, pilcrow, text FROM bible_verse"
        " WHERE version = 'kjv' ORDER BY id").fetchall()
    out: list[Unit] = []

    def passage(vs: list[sqlite3.Row]) -> None:
        """One paragraph: whole, or in runs."""
        title = [v for v in vs if v["kind"] != "verse"]
        verses = [v for v in vs if v["kind"] == "verse"]
        if not verses:
            return
        b = books[verses[0]["book"]]
        head = f"{b['en']} {verses[0]['chapter']}"
        if len(verses) <= KJV_WHOLE:
            runs = [verses]
        else:
            runs, i = [], 0
            while True:
                runs.append(verses[i:i + KJV_RUN])
                if i + KJV_RUN >= len(verses):
                    break
                i += KJV_STEP
        for n, run in enumerate(runs):
            a, z = run[0]["verse"], run[-1]["verse"]
            label = f"{b['abbr']} {run[0]['chapter']}:{a}" + (f"-{z}" if z != a else "")
            lines = [v["text"] for v in (title if n == 0 else [])] + [v["text"] for v in run]
            out.append(Unit("kjv", label, "", head + "\n" + " ".join(lines)))

    cur: list[sqlite3.Row] = []
    for r in rows:
        if cur and ((r["book"], r["chapter"]) != (cur[0]["book"], cur[0]["chapter"]) or r["pilcrow"]):
            passage(cur)
            cur = []
        cur.append(r)
    if cur:
        passage(cur)
    return out


def units(ub: sqlite3.Connection, bible: sqlite3.Connection) -> list[Unit]:
    """Every unit, in the order var/embed.db holds them.  The connections are
    read-only; their row factory is set here."""
    ub.row_factory = bible.row_factory = sqlite3.Row
    out = _text(ub) + _entries(ub) + _notes(ub) + _kjv(bible)
    seen: set[tuple[str, str]] = set()
    for u in out:
        if u.kind != "entry" and (u.kind, u.label) in seen:
            raise ValueError(f"two units named {u.kind} {u.label}")
        seen.add((u.kind, u.label))
    return out


def digest(us: list[Unit]) -> str:
    """The list as one digest: what var/embed.db says it was made from."""
    h = hashlib.sha256()
    h.update(f"recipe {RECIPE}\n".encode())
    for u in us:
        h.update(f"{u.kind}\t{u.label}\t{u.target}\t{u.hash.hex()}\n".encode("utf-8"))
    return h.hexdigest()
