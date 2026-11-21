"""The King James Version: data/kjv/ -> var/kjv.db.

    python -m build kjv          build var/kjv.db (make kjv)

The copy in data/kjv/ is the master (its README): converted once from The
British Study Edition, its slips mended, and what Tigran ruled taken from the
1769 witness.  This reads it and nothing else, no source repository, so the
database is the same wherever it is built, and builds it beside ub.db as a
database of its own (Tigran, 2026-11-21: "best kept separate -- kjv.db").

Each verse, its title or letter, its subscription and its note are set by the
one expander with a closed table of the copy's two macros, `\\bibemph` (the
words the translators supplied, italic: the span kind `supplied`) and
`\\textsc` (the LORD in small capitals, `sc`), and by the one renderer;
hyphenated by Knuth's hyphen.tex, the book's patterns, with no list of its own.

`make data` asks `ensure()` first: ub.db's build holds the study notes' Bible
references to this database, so it builds it where it is missing or was
built from other data (kjv_meta's `data`, the copy's digest), and else reads
the one there.  Nothing in it moves with a build that changes nothing (trap
29): no date, no path, only the data's digest.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3

from .expand import Expander
from .hyphen import ENGLISH, Hyphenator
from .render import render, strip_tags
from .spec import SPAN, Spec

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "kjv"
OUT = ROOT / "var" / "kjv.db"
SCHEMA = ROOT / "build" / "schema_kjv" / "kjv.sql"

TABLE: dict[str, Spec] = {
    "bibemph": Spec(SPAN, args=1, kind="supplied", note="the words the translators supplied, set in italic"),
    "textsc": Spec(SPAN, args=1, kind="sc", note="the LORD, in small capitals"),
}
# TeX's: an apostrophe is ’, Exo 32:32's "sin--;" the 1769's dash; and a
# note's "the light from...:" an ellipsis.
SUBS = [("...", "…"), ("--", "—"), ("'", "’")]

BOOK_FIELDS = ["n", "abbr", "testament", "name", "ref_name", "head", "title", "end"]
VERSE_FIELDS = ["chapter", "verse", "pilcrow", "head", "text", "after", "note"]
RE_MAIN = re.compile(r"\\bibtitlemain\{([^{}]*)\}")


class Span:
    """A span of the renderer's kind (render() reads start, end, kind, attr)."""
    __slots__ = ("start", "end", "kind", "attr")

    def __init__(self, start, end, kind, attr=None):
        self.start, self.end, self.kind, self.attr = start, end, kind, attr


def files() -> list[pathlib.Path]:
    """What the database is built from, in the order its digest reads them."""
    books = DATA / "books.tsv"
    abbrs = [line.split("\t")[1] for line in books.read_text(encoding="utf-8").split("\n")[1:] if line]
    return [books] + [DATA / f"{a}.tsv" for a in abbrs]


def digest() -> str:
    h = hashlib.sha256()
    for p in files():
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def _rows(path: pathlib.Path, fields: list[str], report) -> list[dict]:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0].split("\t") != fields:
        report.hard("kjv-format", path.name, f"header {lines[0]!r}, not {fields}")
        return []
    out = []
    for k, line in enumerate(lines[1:], 2):
        if not line:
            continue
        cells = line.split("\t")
        if len(cells) != len(fields):
            report.hard("kjv-format", f"{path.name}:{k}", f"{len(cells)} fields, not {len(fields)}")
            continue
        out.append(dict(zip(fields, cells), line=k))
    return out


def read(report) -> tuple[list[dict], dict[str, list[dict]]]:
    books = _rows(DATA / "books.tsv", BOOK_FIELDS, report)
    verses = {}
    for b in books:
        rows = _rows(DATA / f"{b['abbr']}.tsv", VERSE_FIELDS, report)
        for r in rows:
            r["chapter"], r["verse"] = int(r["chapter"]), int(r["verse"])
            if r["pilcrow"] not in ("", "¶"):
                report.hard("kjv-format", f"{b['abbr']}.tsv:{r['line']}", f"pilcrow {r['pilcrow']!r}")
        verses[b["abbr"]] = rows
    return books, verses


def expand(tex: str, where: str, report) -> tuple[str, list]:
    """The copy's TeX -> (text, spans): an unknown macro fails (expand.py)."""
    ex = Expander(TABLE, set(), report, where, subs=SUBS, forbid_comments=True).run(tex)
    return ex.text, [Span(s.start, s.end, s.kind) for s in ex.spans]


def title_lines(tex: str) -> list[list]:
    """`line \\\\ line \\\\ \\bibtitlemain{main}` -> [[line, main], ...]."""
    out = []
    for part in tex.split("\\\\"):
        part = part.strip()
        m = RE_MAIN.fullmatch(part)
        out.append([m[1], True] if m else [part, False])
    return out


def verse_key(abbr: str, c: int, v: int) -> str:
    """A verse's name in a page's ids: the note fnGen1_4, its mark fnrefGen1_4."""
    return f"{abbr}{c}_{v}"


def build(report, out: pathlib.Path = OUT) -> dict:
    books, verses = read(report)
    if report.blocking:
        return {}
    hy = Hyphenator((), ENGLISH)
    tmp = out.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    vid = 0
    stats = {"books": 0, "chapters": 0, "verses": 0, "notes": 0, "pilcrows": 0, "heads": 0,
             "afters": 0, "supplied": 0, "sc": 0}
    for b in books:
        abbr = b["abbr"]
        rows = verses[abbr]
        chapters = sorted({r["chapter"] for r in rows})
        lines = title_lines(b["title"])
        con.execute("INSERT INTO kjv_book VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (int(b["n"]), abbr, b["testament"], b["name"], b["ref_name"],
                     " ".join(x for x, _ in lines), json.dumps(lines, ensure_ascii=False),
                     b["end"], len(chapters), len(rows)))
        stats["books"] += 1
        stats["chapters"] += len(chapters)
        for r in rows:
            vid += 1
            c, v = r["chapter"], r["verse"]
            where = f"{abbr} {c}:{v}"
            key = verse_key(abbr, c, v)
            text, spans = expand(r["text"], where, report)
            head, hspans = expand(r["head"], where + " (title)", report) if r["head"] else ("", [])
            after, aspans = expand(r["after"], where + " (subscription)", report) if r["after"] else ("", [])
            marks = list(spans)
            if r["note"]:
                marks.append(Span(len(text), len(text), "fnref", {"kind": "kjv", "key": key}))
            html = render(text, marks)
            html_hy = render(text, marks, shy=hy.points(text, spans))
            for part, t, h in (("text", text, html), ("head", head, None), ("after", after, None)):
                if h is not None and strip_tags(h) != t:
                    report.hard("kjv-roundtrip", where, f"the {part}'s HTML says otherwise than its text")
            con.execute("INSERT INTO kjv_verse VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (vid, int(b["n"]), c, v, 1 if r["pilcrow"] else 0,
                         head, render(head, hspans), text, html, html_hy, after, render(after, aspans)))
            for part, sp in (("text", marks), ("head", hspans), ("after", aspans)):
                con.executemany("INSERT INTO kjv_span VALUES (?,?,?,?,?)",
                                [(vid, part, s.start, s.end, s.kind) for s in sp])
                stats["supplied"] += sum(s.kind == "supplied" for s in sp)
                stats["sc"] += sum(s.kind == "sc" for s in sp)
            con.execute("INSERT INTO kjv_verse_fts (rowid, text) VALUES (?, ?)",
                        (vid, " ".join(x for x in (head, text, after) if x)))
            if r["note"]:
                ntext, nspans = expand(r["note"], where + " (note)", report)
                nhtml = render(ntext, nspans)
                if strip_tags(nhtml) != ntext:
                    report.hard("kjv-roundtrip", where, "the note's HTML says otherwise than its text")
                con.execute("INSERT INTO kjv_note VALUES (?,?,?,?)",
                            (vid, ntext, nhtml, render(ntext, nspans, shy=hy.points(ntext, nspans))))
                con.executemany("INSERT INTO kjv_span VALUES (?,?,?,?,?)",
                                [(vid, "note", s.start, s.end, s.kind) for s in nspans])
                con.execute("INSERT INTO kjv_note_fts (rowid, text) VALUES (?, ?)", (vid, ntext))
                stats["notes"] += 1
            stats["verses"] += 1
            stats["pilcrows"] += bool(r["pilcrow"])
            stats["heads"] += bool(r["head"])
            stats["afters"] += bool(r["after"])
    con.executemany("INSERT INTO kjv_meta VALUES (?, ?)",
                    [("data", digest())] + [(k, str(v)) for k, v in stats.items()])
    con.commit()
    if report.blocking:
        con.close()
        tmp.unlink(missing_ok=True)
        return {}
    con.execute("VACUUM")
    con.close()
    tmp.replace(out)
    return stats


def built(path: pathlib.Path = OUT) -> str | None:
    """The data digest the database at `path` was built from, or None."""
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM kjv_meta WHERE key = 'data'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def ensure(report) -> bool:
    """var/kjv.db built from the copy as it is: True if it was built now."""
    if built() == digest():
        return False
    stats = build(report)
    if stats:
        print(f"  var/kjv.db: {stats['books']} books, {stats['chapters']:,} chapters, "
              f"{stats['verses']:,} verses, {stats['notes']:,} notes")
    return True


def verses_of(path: pathlib.Path = OUT) -> dict[str, dict[int, int]]:
    """{abbr: {chapter: its last verse}}: what a reference may name."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out: dict[str, dict[int, int]] = {}
        for abbr, c, n in con.execute("SELECT b.abbr, v.chapter, max(v.verse) FROM kjv_verse v"
                                      " JOIN kjv_book b ON b.id = v.book GROUP BY v.book, v.chapter"):
            out.setdefault(abbr, {})[c] = n
        return out
    finally:
        con.close()
