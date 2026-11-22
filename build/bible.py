"""The Bible: data/kjv/ and data/rsb/ -> var/bible.db.

    python -m build bible        build var/bible.db (make bible)

Two copies, each the master (their READMEs): the King James Version, converted
once from The British Study Edition with what Tigran ruled taken from the 1769
witness, and the Russian Synodal Bible, converted once from Tigran's own
edition.  This reads them, data/rsb/versification.tsv and data/bible.toml, and
nothing else, no source repository, so the database is the same wherever it is
built: a database of its own beside ub.db (Tigran, 2026-11-21: "a single
bible.db"; the KJV's was kjv.db from that morning until then).

A chapter of the site is a list of rows, each the verses of the two that are
the same words (build/versify.py): every verse is stored as its version
numbers it, with the row it stands in, keyed in the KJV's numbering.  A KJV
psalm's title, which its copy sets apart above verse 1, is a row 0 of its own,
beside the Synodal's title, which that numbers as a verse.

Each verse, its heading, subscription and notes are set by the one expander
with a closed table of each copy's macros, and by the one renderer: the KJV's
`\\bibemph` (the words supplied, `supplied`) and `\\textsc` (the LORD, `sc`),
hyphenated by Knuth's hyphen.tex, the book's patterns; the Synodal's
`\\bibemph`, `\\fns` (a note, where it stands) and `\\rsbpar` (a paragraph
opening inside a verse, `pilcrow`), hyphenated by hyph-ru, as the translations
are, a word with a stress mark left whole.

`make data` asks `ensure()` first: ub.db's build holds the study notes' Bible
references to this database, so it builds it where it is missing or was built
from other data (bible_meta's `data`, the copies' digest), and else reads the
one there.  Nothing in it moves with a build that changes nothing (trap 29):
no date, no path, only the data's digest.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3
import tomllib

from . import versify
from .expand import Expander
from .hyphen import ENGLISH, RUSSIAN, Hyphenator
from .render import render, strip_tags
from .spec import MARK, NOTE, SPAN, Spec

ROOT = pathlib.Path(__file__).resolve().parent.parent
KJV = ROOT / "data" / "kjv"
RSB = ROOT / "data" / "rsb"
VERSIONS = ROOT / "data" / "bible.toml"
TABLE_FILE = RSB / "versification.tsv"
OUT = ROOT / "var" / "bible.db"
SCHEMA = ROOT / "build" / "schema_bible" / "bible.sql"

KJV_TABLE: dict[str, Spec] = {
    "bibemph": Spec(SPAN, args=1, kind="supplied", note="the words the translators supplied, set in italic"),
    "textsc": Spec(SPAN, args=1, kind="sc", note="the LORD, in small capitals"),
}
# TeX's: an apostrophe is ’, Exo 32:32's "sin--;" the 1769's dash; and a
# note's "the light from...:" an ellipsis.
KJV_SUBS = [("...", "…"), ("--", "—"), ("'", "’")]
RSB_TABLE: dict[str, Spec] = {
    "bibemph": Spec(SPAN, args=1, kind="supplied", note="the words supplied, set in italic"),
    "fns": Spec(NOTE, args=1, kind="rsb", note="a note of the edition's, where it stands"),
    # Its own words' space follows the mark, which TeX's tokenizer took with the
    # control word: «…огорчением].¶ Сынов».
    "rsbpar": Spec(MARK, kind="pilcrow", text=" ", note="a paragraph opening inside a verse"),
}
# The copy writes every character as the character (tools/rsb/convert.py).
RSB_SUBS: list[tuple[str, str]] = []

KJV_BOOK = ["n", "abbr", "testament", "name", "ref_name", "head", "title", "end"]
KJV_VERSE = ["chapter", "verse", "pilcrow", "head", "text", "after", "note"]
RSB_BOOK = ["n", "abbr", "group", "name", "ref", "title"]
RSB_VERSE = ["chapter", "verse", "pilcrow", "head", "text"]
RE_MAIN = re.compile(r"\\bibtitlemain\{([^{}]*)\}")
RE_LETTER = re.compile(r"[A-Z]+\.")             # a letter of Psalm 119: ALEPH.
RE_ALT = re.compile(r"\((\d+)\)")              # 3 Ezra 7:(36)
RE_FNS = re.compile(r"\\fns\{([^{}]*(?:\\bibemph\{[^{}\\]*\}[^{}]*)*)\}")
YO = str.maketrans("ёЁ", "еЕ")


class Span:
    """A span of the renderer's kind (render() reads start, end, kind, attr)."""
    __slots__ = ("start", "end", "kind", "attr")

    def __init__(self, start, end, kind, attr=None):
        self.start, self.end, self.kind, self.attr = start, end, kind, attr


def books_of(data: pathlib.Path) -> list[str]:
    return [line.split("\t")[1] for line in (data / "books.tsv").read_text(encoding="utf-8").split("\n")[1:]
            if line]


def files() -> list[pathlib.Path]:
    """What the database is built from, in the order its digest reads them."""
    out = [VERSIONS, KJV / "books.tsv"] + [KJV / f"{a}.tsv" for a in books_of(KJV)]
    return out + [RSB / "books.tsv"] + [RSB / f"{a}.tsv" for a in books_of(RSB)] + [TABLE_FILE]


def digest() -> str:
    h = hashlib.sha256()
    for p in files():
        h.update(p.parent.name.encode() + b"/" + p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def _rows(path: pathlib.Path, fields: list[str], report) -> list[dict]:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0].split("\t") != fields:
        report.hard("bible-format", f"{path.parent.name}/{path.name}", f"header {lines[0]!r}, not {fields}")
        return []
    out = []
    for k, line in enumerate(lines[1:], 2):
        if not line:
            continue
        cells = line.split("\t")
        if len(cells) != len(fields):
            report.hard("bible-format", f"{path.parent.name}/{path.name}:{k}",
                        f"{len(cells)} fields, not {len(fields)}")
            continue
        out.append(dict(zip(fields, cells), line=k))
    return out


def read(report) -> tuple[list[dict], dict, list[dict], dict, dict]:
    """(KJV books, {abbr: verses}, Synodal books, {abbr: verses}, versions)."""
    kb = _rows(KJV / "books.tsv", KJV_BOOK, report)
    kv = {}
    for b in kb:
        rows = _rows(KJV / f"{b['abbr']}.tsv", KJV_VERSE, report)
        for r in rows:
            r["chapter"], r["verse"] = int(r["chapter"]), int(r["verse"])
            if r["pilcrow"] not in ("", "¶"):
                report.hard("bible-format", f"kjv/{b['abbr']}.tsv:{r['line']}", f"pilcrow {r['pilcrow']!r}")
        kv[b["abbr"]] = rows
    rb = _rows(RSB / "books.tsv", RSB_BOOK, report)
    rv = {}
    for b in rb:
        if b["group"] not in ("OT", "DC", "NT"):
            report.hard("bible-format", f"rsb/books.tsv:{b['line']}", f"group {b['group']!r}")
        rows = _rows(RSB / f"{b['abbr']}.tsv", RSB_VERSE, report)
        for r in rows:
            r["chapter"] = int(r["chapter"])
            m = RE_ALT.fullmatch(r["verse"])
            r["alt"], r["verse"] = (1, int(m[1])) if m else (0, int(r["verse"]))
            if r["pilcrow"] not in ("", "¶"):
                report.hard("bible-format", f"rsb/{b['abbr']}.tsv:{r['line']}", f"pilcrow {r['pilcrow']!r}")
        rv[b["abbr"]] = rows
    with open(VERSIONS, "rb") as fh:
        versions = tomllib.load(fh)
    names = versions.pop("names", {})
    if list(versions) != ["kjv", "rsb"]:
        report.hard("bible-format", "data/bible.toml", f"versions {list(versions)}, not kjv and rsb")
    dc = [b["abbr"] for b in rb if b["group"] == "DC"]
    if sorted(names) != sorted(dc):
        report.hard("bible-format", "data/bible.toml", f"[names] names {sorted(names)}, not the eleven {sorted(dc)}")
    for b in rb:
        b["en"] = names.get(b["abbr"], "")
    return kb, kv, rb, rv, versions


def expand(tex: str, where: str, report, table, subs) -> tuple[str, list, list]:
    """A copy's TeX -> (text, spans, notes): an unknown macro fails (expand.py)."""
    ex = Expander(table, set(), report, where, subs=subs, forbid_comments=True).run(tex)
    return ex.text, [Span(s.start, s.end, s.kind, s.attr) for s in ex.spans], ex.notes


def title_lines(tex: str) -> tuple[list[list], str, int]:
    """`line \\\\ \\bibtitlemain{main}\\fns{note}` -> ([[line, main], ...], the
    note's TeX, the line it follows (-1 if none))."""
    out, note, at = [], "", -1
    for i, part in enumerate(tex.split("\\\\")):
        part = part.strip()
        if m := RE_FNS.search(part):
            note, at, part = m[1], i, part[:m.start()] + part[m.end():]
        m = RE_MAIN.fullmatch(part)
        out.append([m[1], True] if m else [part, False])
    return out, note, at


def verse_key(abbr: str, c: int, v: int) -> str:
    """A KJV verse's note in a page's ids: fnGen1_4, its mark fnrefGen1_4."""
    return f"{abbr}{c}_{v}"


def rsb_key(abbr: str, c: int, v: int, alt: int, n: int) -> str:
    """A Synodal note in a page's ids: fnrGen1_4_1, its mark fnrefrGen1_4_1."""
    return f"r{abbr}{c}_{'p' if alt else ''}{v}_{n}"


def contents(kb: list[dict], rb: list[dict]) -> list[tuple[str, str]]:
    """(abbr, group) for the 77 in the Contents' order: the KJV's Old Testament,
    the Synodal's non-canonical books in its own order, the KJV's New."""
    dc = [b["abbr"] for b in rb if b["group"] == "DC"]
    return ([(b["abbr"], "OT") for b in kb if b["testament"] == "OT"] + [(a, "DC") for a in dc]
            + [(b["abbr"], "NT") for b in kb if b["testament"] == "NT"])


def rows_of(abbr: str, kv: list[dict] | None, rv: list[dict] | None, rules, report) -> tuple[dict, dict]:
    """Each verse's row: ({kjv (c, v): row}, {synodal (c, v, alt): row}), a
    KJV title as (c, 0).  A book both have is placed by the table; a book of
    the Synodal's alone by its own numbers, a chapter 0 at the head of chapter
    1 and 3 Ezra's bracketed series after the verse before it."""
    if kv is not None and rv is not None:
        kjv = []
        for r in kv:
            if r["head"] and not RE_LETTER.fullmatch(r["head"]):
                if r["verse"] != 1:
                    report.hard("bible-format", f"kjv/{abbr}.tsv:{r['line']}", "a title over a verse not 1")
                kjv.append((r["chapter"], 0))
            kjv.append((r["chapter"], r["verse"]))
        syn = [(r["chapter"], r["verse"]) for r in rv]
        if any(r["alt"] for r in rv):
            report.hard("bible-format", f"rsb/{abbr}.tsv", "a bracketed verse in a book the KJV has")
        try:
            sr, kr = versify.place(abbr, syn, kjv, rules)
        except SystemExit as e:
            report.hard("bible-versify", abbr, str(e))
            return {}, {}
        return kr, {(c, v, 0): r for (c, v), r in sr.items()}
    out, prev, n = {}, None, {}
    for r in rv or ():
        c, v = r["chapter"], r["verse"]
        if r["alt"]:
            anchor = prev
        elif c == 0:
            anchor = (1, 0)
        else:
            out[(c, v, 0)] = prev = (c, v, 0)
            continue
        n[anchor] = n.get(anchor, 0) + 1
        out[(c, v, r["alt"])] = (*anchor[:2], n[anchor])
    return {}, out


def build(report, out: pathlib.Path = OUT) -> dict:
    kb, kv, rb, rv, versions = read(report)
    rules = versify.read(TABLE_FILE)
    if report.blocking:
        return {}
    order = contents(kb, rb)
    if len(order) != 77:
        report.hard("bible-format", "books", f"{len(order)} books in the Contents, not 77")
    hy = {"kjv": Hyphenator((), ENGLISH), "rsb": Hyphenator((), RUSSIAN)}
    tmp = out.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    for n, (key, v) in enumerate(versions.items(), 1):
        con.execute("INSERT INTO bible_version VALUES (?,?,?,?,?,?,?)",
                    (key, n, v["lang"], v["title"], v["label"], v["by"]["en"], v["by"]["ru"]))
    kbook = {b["abbr"]: b for b in kb}
    rbook = {b["abbr"]: b for b in rb}
    stats = {f"{k}_{x}": 0 for k in ("kjv", "rsb")
             for x in ("books", "chapters", "verses", "titles", "notes", "pilcrows", "supplied", "sc")}
    stats.update(rows=0, rows_both=0, books=0, chapters=0)
    vid = nid = 0
    for bid, (abbr, grp) in enumerate(order, 1):
        kr, sr = rows_of(abbr, kv.get(abbr), rv.get(abbr), rules, report)
        allrows = set(kr.values()) | set(sr.values())
        pages = sorted({r[0] for r in allrows})
        en = kbook[abbr]["ref_name"] if abbr in kbook else rbook[abbr]["en"]
        con.execute("INSERT INTO bible_book VALUES (?,?,?,?,?)", (bid, abbr, grp, len(pages), en))
        stats["books"] += 1
        stats["chapters"] += len(pages)
        stats["rows"] += len(allrows)
        stats["rows_both"] += len(set(kr.values()) & set(sr.values()))
        for version, b, rows in (("kjv", kbook.get(abbr), kv.get(abbr)), ("rsb", rbook.get(abbr), rv.get(abbr))):
            if b is None:
                continue
            table, subs = (KJV_TABLE, KJV_SUBS) if version == "kjv" else (RSB_TABLE, RSB_SUBS)
            lines, note_tex, note_at = title_lines(b["title"])
            tnote = ""
            if note_tex:
                tnote, _, _ = expand(note_tex, f"{abbr} title (note)", report, table, subs)
            chapters = sorted({r["chapter"] for r in rows if r["chapter"]})
            con.execute("INSERT INTO bible_book_text VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (version, bid, int(b["n"]), b["name"], b["ref_name"] if version == "kjv" else b["ref"],
                         " ".join(x for x, _ in lines), json.dumps(lines, ensure_ascii=False),
                         tnote, note_at, b.get("end", ""), len(chapters), len(rows)))
            stats[f"{version}_books"] += 1
            stats[f"{version}_chapters"] += len(chapters)
            for r in rows:
                c, v, alt = r["chapter"], r["verse"], r.get("alt", 0)
                where = f"{version} {abbr} {c}:{'(%d)' % v if alt else v}"
                rkey = (c, v) if version == "kjv" else (c, v, alt)
                row = (kr if version == "kjv" else sr).get(rkey)
                if row is None:
                    report.hard("bible-versify", where, "stands in no row")
                    continue
                head, hspans, hnotes = ("", [], [])
                if r["head"]:
                    head, hspans, hnotes = expand(r["head"], where + " (heading)", report, table, subs)
                after, aspans = ("", [])
                if r.get("after"):
                    after, aspans, _ = expand(r["after"], where + " (subscription)", report, table, subs)
                text, spans, tnotes = expand(r["text"], where, report, table, subs)
                title = version == "kjv" and r["head"] and not RE_LETTER.fullmatch(r["head"])
                if title:                           # a KJV psalm's title: a row 0 of its own
                    vid += 1
                    con.execute("INSERT INTO bible_verse VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (vid, version, bid, c, 0, 0, "title", *kr[(c, 0)], 0, "", "",
                                 head, render(head, hspans), render(head, hspans, shy=hy[version].points(head, hspans)),
                                 "", ""))
                    insert_spans(con, vid, "text", hspans, stats, version)
                    con.execute(f"INSERT INTO bible_{version}_fts (rowid, text) VALUES (?, ?)", (vid, head))
                    stats[f"{version}_titles"] += 1
                    head, hspans = "", []
                vid += 1
                # The notes: the KJV's one at the verse's end; the Synodal's where they stand,
                # its heading's first.
                notes = []
                if version == "kjv":
                    if r["note"]:
                        key = verse_key(abbr, c, v)
                        spans.append(Span(len(text), len(text), "fnref", {"kind": "kjv", "key": key}))
                        ntext, nspans, _ = expand(r["note"], where + " (note)", report, table, subs)
                        notes.append(("text", key, ntext, nspans))
                else:
                    for part, sp, ns in (("head", hspans, hnotes), ("text", spans, tnotes)):
                        marks = [s for s in sp if s.kind == "fnref"]
                        for s, note in zip(marks, ns):
                            key = rsb_key(abbr, c, v, alt, len(notes) + 1)
                            s.attr = {"kind": "rsb", "key": key}
                            notes.append((part, key, note.text, [Span(x.start, x.end, x.kind, x.attr)
                                                                 for x in note.spans]))
                html = render(text, spans)
                html_hy = render(text, spans, shy=hy[version].points(text, spans))
                for part, t, h in (("text", text, html), ("head", head, render(head, hspans)),
                                   ("after", after, render(after, aspans))):
                    if strip_tags(h) != t:
                        report.hard("bible-roundtrip", where, f"the {part}'s HTML says otherwise than its text")
                con.execute("INSERT INTO bible_verse VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (vid, version, bid, c, v, alt, "verse", *row, 1 if r["pilcrow"] else 0,
                             head, render(head, hspans), text, html, html_hy, after, render(after, aspans)))
                for part, sp in (("text", spans), ("head", hspans), ("after", aspans)):
                    insert_spans(con, vid, part, sp, stats, version)
                fts = " ".join(x for x in (head, text, after) if x)
                con.execute(f"INSERT INTO bible_{version}_fts (rowid, text) VALUES (?, ?)",
                            (vid, fts.translate(YO)))
                for n, (part, key, ntext, nspans) in enumerate(notes, 1):
                    nid += 1
                    nhtml = render(ntext, nspans)
                    if strip_tags(nhtml) != ntext:
                        report.hard("bible-roundtrip", where, "a note's HTML says otherwise than its text")
                    con.execute("INSERT INTO bible_note VALUES (?,?,?,?,?,?,?,?)",
                                (nid, vid, part, n, key, ntext, nhtml,
                                 render(ntext, nspans, shy=hy[version].points(ntext, nspans))))
                    insert_spans(con, vid, "note", nspans, stats, version)
                    con.execute(f"INSERT INTO bible_{version}_note_fts (rowid, text) VALUES (?, ?)",
                                (nid, ntext.translate(YO)))
                    stats[f"{version}_notes"] += 1
                stats[f"{version}_verses"] += 1
                stats[f"{version}_pilcrows"] += bool(r["pilcrow"])
    con.executemany("INSERT INTO bible_meta VALUES (?, ?)",
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


def insert_spans(con, vid: int, part: str, spans, stats: dict, version: str) -> None:
    con.executemany("INSERT INTO bible_span VALUES (?,?,?,?,?)",
                    [(vid, part, s.start, s.end, s.kind) for s in spans])
    stats[f"{version}_supplied"] += sum(s.kind == "supplied" for s in spans)
    stats[f"{version}_sc"] += sum(s.kind == "sc" for s in spans)


def built(path: pathlib.Path = OUT) -> str | None:
    """The data digest the database at `path` was built from, or None."""
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM bible_meta WHERE key = 'data'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def ensure(report) -> bool:
    """var/bible.db built from the copies as they are: True if it was built now."""
    if built() == digest():
        return False
    stats = build(report)
    if stats:
        print(f"  var/bible.db: {stats['books']} books, {stats['chapters']:,} chapters, {stats['rows']:,} rows; "
              f"KJV {stats['kjv_verses']:,} verses, {stats['kjv_notes']:,} notes; "
              f"Synodal {stats['rsb_verses']:,} verses, {stats['rsb_notes']:,} notes")
    return True


def verses_of(path: pathlib.Path = OUT, version: str = "kjv") -> dict[str, dict[int, int]]:
    """{abbr: {chapter: its last verse}} of a version: what a reference may name."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out: dict[str, dict[int, int]] = {}
        for abbr, c, n in con.execute(
                "SELECT b.abbr, v.chapter, max(v.verse) FROM bible_verse v JOIN bible_book b ON b.id = v.book"
                " WHERE v.version = ? AND v.kind = 'verse' AND v.alt = 0 GROUP BY v.book, v.chapter",
                (version,)):
            out.setdefault(abbr, {})[c] = n
        return out
    finally:
        con.close()
