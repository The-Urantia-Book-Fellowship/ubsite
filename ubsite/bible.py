"""The Bible's pages: what they read from var/bible.db (build/bible.py).

A database of its own beside ub.db (Tigran, 2026-11-21: "a single bible.db"),
opened read-only by these functions alone: the King James Version and the
Russian Synodal Bible, a verse of each to a row.  The pages (app.py bible_*)
are /bible, the 77 books, the KJV's and the Synodal's eleven non-canonical
between the testaments; /bible/Mat, a book's title and its chapters;
/bible/Mat/5, a chapter; /bible/Mat/5:48 and /bible/Psa/104:1-2, the chapter
with those verses tinted, as /101:4.2 tints a paragraph.  An address's book is
the copies' abbreviation, for ever, and its numbers the KJV's: a verse the
KJV has not is named in its chapter by its own number (`s3-24`, Daniel 3:24
of the Synodal), and in a book or chapter only the Synodal has its numbers
are the address.  /bible/rsb/Psa/22:1 names a verse as the Synodal numbers it.

A page carries each row's base line, the KJV's where the row has one, else
the Synodal's; the other version's lines are /bible/tr/<Abbr>/<c>, which
ub.js fetches (bibFetch) and draws first, in columns or in folds, as the
reader's setting `bible` orders them.  No setting reaches the server.
"""

from __future__ import annotations

import functools
import hashlib
import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "var" / "bible.db"

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
def _data(mtime_ns: int) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    with db() as con:
        versions = tuple(dict(r) for r in con.execute("SELECT * FROM bible_version ORDER BY n"))
        books = [dict(r) for r in con.execute("SELECT * FROM bible_book ORDER BY id")]
        texts = {}
        for r in con.execute("SELECT * FROM bible_book_text"):
            r = dict(r)
            r["title_lines"] = json.loads(r["title_lines"])
            texts[(r["book"], r["version"])] = r
    for b in books:
        b["kjv"], b["rsb"] = texts.get((b["id"], "kjv")), texts.get((b["id"], "rsb"))
        # The name a reference writes, English: the KJV's, or English Bibles'
        # for the eleven it has not; and the Synodal's.
        b["ref_name"] = b["en"]
        b["ru"] = b["rsb"]["name"] if b["rsb"] else ""
    return tuple(books), versions


def books() -> tuple[dict, ...]:
    """The 77, in the Contents' order, each its row of bible_book with its
    versions' texts as `kjv` and `rsb` (None where it has not that one)."""
    return _data(DB.stat().st_mtime_ns)[0]


def versions() -> tuple[dict, ...]:
    return _data(DB.stat().st_mtime_ns)[1]


def book(abbr: str) -> dict | None:
    """A book by its abbreviation, exactly as written: Gen, 1Sa, Sol, Tob."""
    return next((b for b in books() if b["abbr"] == abbr), None)


def _key(name: str) -> str:
    return re.sub(r"[\s_. -]+", "", name).lower().replace("ё", "е")


def book_loosely(name: str) -> dict | None:
    """A book by its abbreviation in any case (gen, 1SA), or by a name a
    reference writes, with or without its spaces: the KJV's (Genesis, 1 Samuel,
    songofsolomon), English Bibles' for the eleven (Tobit), the Synodal's
    (Бытие, Быт, 1 Цар, 1-я Царств): the address to send such a reader on to."""
    key = _key(name)
    for b in books():
        names = [b["abbr"], b["en"]]
        if b["kjv"]:
            names += [b["kjv"]["name"], b["kjv"]["ref_name"]]
        if b["rsb"]:
            names += [b["rsb"]["name"], b["rsb"]["ref_name"]]
        if key in {_key(x) for x in names}:
            return b
    return None


def _verse(r: sqlite3.Row) -> dict:
    v = dict(r)
    v["ref"] = (f"{v['chapter']}:" + (f"({v['verse']})" if v["alt"] else str(v["verse"]))
                if v["kind"] == "verse" else "")
    v["notes"] = []
    return v


def chapter(b: dict, c: int) -> dict:
    """A chapter's rows, in order, each {key, id, base, kjv: [verses], rsb:
    [verses]}, with each verse's notes; and where its neighbours are."""
    with db() as con:
        vs = [_verse(r) for r in con.execute(
            "SELECT * FROM bible_verse WHERE book = ? AND rc = ? ORDER BY rv, rs, version, chapter, alt, verse",
            (b["id"], c))]
        by_id = {v["id"]: v for v in vs}
        if vs:
            for n in con.execute(f"SELECT * FROM bible_note WHERE verse_id IN ({','.join('?' * len(vs))})"
                                 " ORDER BY verse_id, n", [v["id"] for v in vs]):
                by_id[n["verse_id"]]["notes"].append(dict(n))
    kjv_page = any(v["version"] == "kjv" for v in vs)
    rows: dict = {}
    for v in vs:
        row = rows.setdefault((v["rv"], v["rs"]), {"key": (v["rv"], v["rs"]), "kjv": [], "rsb": []})
        row[v["version"]].append(v)
    out = []
    # A Synodal line that opens a second chapter of it on the page shows its
    # chapter (.newc): the KJV's Psalm 116 is the Synodal's 114 and 115.
    prev_c = None
    for row in rows.values():
        for v in row["rsb"]:
            v["newc"] = prev_c is not None and v["chapter"] != prev_c and kjv_page
            prev_c = v["chapter"]
    for row in rows.values():
        row["base"] = "kjv" if row["kjv"] else "rsb"
        first = row[row["base"]][0]
        if row["kjv"]:
            row["id"] = f"v{first['verse']}"
        elif kjv_page:
            row["id"] = f"s{first['chapter']}-{'x' if first['alt'] else ''}{first['verse']}"
        else:
            row["id"] = f"{'x' if first['alt'] else 'v'}{first['verse']}"
        for k in ("kjv", "rsb"):
            for v in row[k]:
                v["line_id"] = row["id"] if v is first else (
                    f"v{v['verse']}" if k == "kjv" else row["id"] + f"-{v['verse']}")
        out.append(row)
    order = books()
    i = next(k for k, x in enumerate(order) if x["id"] == b["id"])
    prev = (b, c - 1) if c > 1 else (order[i - 1], order[i - 1]["chapters"]) if i else None
    nxt = (b, c + 1) if c < b["chapters"] else (order[i + 1], 1) if i + 1 < len(order) else None
    return {"rows": out, "kjv": kjv_page, "prev": prev, "next": nxt,
            "fb": order[i - 1] if i else None, "ff": order[i + 1] if i + 1 < len(order) else None,
            "has": sorted({k for r in out for k in ("kjv", "rsb") if r[k]}),
            "first_chapter": c == 1}


def synodal_head(b: dict, rows: list[dict]) -> str:
    """The Synodal's chapter or chapters on this page, as its head says them:
    «Глава 5», «Псалом 22», «Псалом 9:22–39», «Псалмы 114–115»."""
    if not b["rsb"]:
        return ""
    by: dict[int, list[int]] = {}
    for r in rows:
        for v in r["rsb"]:
            if v["kind"] == "verse" and not v["alt"] and v["chapter"]:
                by.setdefault(v["chapter"], []).append(v["verse"])
    if not by:
        return ""
    with db() as con:
        last = dict(con.execute("SELECT chapter, max(verse) FROM bible_verse WHERE version = 'rsb' AND book = ?"
                                " AND alt = 0 GROUP BY chapter", (b["id"],)).fetchall())
    parts, whole = [], True
    for ch, vs in sorted(by.items()):
        lo, hi = min(vs), max(vs)
        if lo <= 1 and hi == last[ch]:
            parts.append(str(ch))
        else:
            whole = False
            parts.append(f"{ch}:{max(lo, 1)}–{hi}" if hi > max(lo, 1) else f"{ch}:{hi}")
    psa = b["abbr"] == "Psa"
    word = ("Псалом" if len(parts) == 1 else "Псалмы") if psa else ("Глава" if len(parts) == 1 else "Главы")
    if whole and len(parts) == 2 and int(parts[1]) == int(parts[0]) + 1:
        return f"{word} {parts[0]}–{parts[1]}"
    return f"{word} {', '.join(parts)}"


def name(b: dict, c: int | None = None, v: int | None = None, w: int | None = None) -> str:
    """A reference as the page writes it: Matthew 5, Matthew 5:48, Psalms 104:1–2."""
    s = b["ref_name"]
    if c is not None:
        s += f" {c}"
    if v is not None:
        s += f":{v}" + (f"–{w}" if w and w != v else "")
    return s


def href(b: dict, c: int | None = None, v: int | None = None, w: int | None = None) -> str:
    s = f"/bible/{b['abbr']}"
    if c is not None:
        s += f"/{c}"
    if v is not None:
        s += f":{v}" + (f"-{w}" if w and w != v else "")
    return s


def synodal_row(b: dict, c: int, v: int | None) -> tuple | None:
    """The row the Synodal's c:v of a book stands in, (rc, rv, rs), or with no
    verse its chapter's first; None where it has no such verse."""
    with db() as con:
        if v is None:
            r = con.execute("SELECT rc, rv, rs FROM bible_verse WHERE version = 'rsb' AND book = ? AND chapter = ?"
                            " AND alt = 0 ORDER BY verse LIMIT 1", (b["id"], c)).fetchone()
        else:
            r = con.execute("SELECT rc, rv, rs FROM bible_verse WHERE version = 'rsb' AND book = ? AND chapter = ?"
                            " AND verse = ? AND alt = 0 AND kind = 'verse'", (b["id"], c, v)).fetchone()
    return tuple(r) if r else None


def _rows_of(con, b: dict) -> tuple[dict, dict, set]:
    """A book's Synodal verses' rows {(c, v): (rc, rv, rs)}, each row's first
    KJV verse {(rc, rv, rs): v}, and the pages the KJV has a verse on."""
    rows = {(c, v): (rc, rv, rs) for c, v, rc, rv, rs in con.execute(
        "SELECT chapter, verse, rc, rv, rs FROM bible_verse WHERE version = 'rsb' AND book = ?"
        " AND alt = 0 AND kind = 'verse'", (b["id"],))}
    first = {(rc, rv, rs): v for rc, rv, rs, v in con.execute(
        "SELECT rc, rv, rs, min(verse) FROM bible_verse WHERE version = 'kjv' AND book = ? GROUP BY rc, rv, rs",
        (b["id"],))}
    pages = {rc for (rc,) in con.execute("SELECT DISTINCT rc FROM bible_verse WHERE version = 'kjv' AND book = ?",
                                         (b["id"],))}
    return rows, first, pages


def _synodal_href(b: dict, c: int, v: int, row: tuple, first: dict, pages: set) -> str:
    """The rule: a row with a KJV verse, that verse's address with the
    Synodal's fold open (#tr-rsb); a title's row, its chapter's #v0; a row of
    the Synodal's alone, its chapter with the line's id, s<c>-<v> on a page
    of the KJV's, else its own numbers, v<v>."""
    k = first.get(row)
    if k:
        return href(b, row[0], k) + "#tr-rsb"
    if k is not None:
        return href(b, row[0]) + "#v0"
    return href(b, row[0]) + (f"#s{c}-{v}" if row[0] in pages else f"#v{v}")


def synodal(b: dict, c: int, v: int) -> str | None:
    """The address of the Synodal's verse c:v of a book, in the page's
    numbering (_synodal_href); None where it has no such verse."""
    with db() as con:
        rows, first, pages = _rows_of(con, b)
    row = rows.get((c, v))
    return _synodal_href(b, c, v, row, first, pages) if row else None


@functools.lru_cache(maxsize=16)
def _numbers(mtime_ns: int, abbr: str) -> dict | None:
    b = book(abbr)
    if not (b and b["kjv"] and b["rsb"]):
        return None
    with db() as con:
        rows, first, pages = _rows_of(con, b)
        kjv: dict[tuple, list[int]] = {}
        for rc, rv, rs, v in con.execute("SELECT rc, rv, rs, verse FROM bible_verse WHERE version = 'kjv'"
                                         " AND book = ? AND kind = 'verse'", (b["id"],)):
            kjv.setdefault((rc, rv, rs), []).append(v)
    starts: dict[int, int] = {}
    for (c, v) in rows:
        if c >= 1:
            starts[c] = min(starts.get(c, v), v)
    out, here, verses = [], {}, {}
    for (c, v), row in sorted(rows.items(), key=lambda x: (x[1][1], x[1][2], x[0])):
        if c >= 1:
            here.setdefault(row[0], c)
            verses.setdefault(c, set()).update((row[0], kv) for kv in kjv.get(row, ()))
    # A chapter to its page, and to its first verse's row where the page
    # opens with another (the Synodal's Psalm 115 on the KJV's 116, its 13th
    # of Numbers the last verse of the KJV's 12th); a page it opens, at its
    # top, over a prologue or a title of the KJV's alone (Esther 1, Song 1).
    for s in sorted(starts):
        v0 = starts[s]
        row = rows[(s, v0)]
        rc, k = row[0], first.get(row)
        if here[rc] == s:
            at = ""
        elif k is not None:
            at = f"#v{k}"
        else:
            at = f"#s{s}-{v0}" if rc in pages else f"#v{v0}"
        out.append((s, href(b, rc) + at))
    if all(h == href(b, s) for s, h in out) and all(here[rc] == rc for rc in here) and len(out) == b["chapters"]:
        return None
    return {"list": out, "here": here, "verses": {s: sorted(x) for s, x in verses.items()}}


def numbers(b: dict) -> dict | None:
    """Where a book's chapters stand as the Synodal numbers them, for the
    Contents to list them so where it is the first text (Tigran, 2026-11-21:
    "if it is the first (or especially if it is the only one) then it makes
    sense to match the Contents to the actual books"): {"list": [(its chapter,
    the address of its first verse's row, the page's own where the row is the
    page's first)], "here": {page: the chapter of its first Synodal verse},
    "verses": {its chapter: [the KJV's (chapter, verse) in its rows]}}; None
    where the two number the book's chapters alike, the pages being its
    chapters (Psalms above all, 137 of them otherwise; Numbers, 1 Samuel, the
    Song, Hosea and Jonah a chapter starting a verse before its page)."""
    return _numbers(DB.stat().st_mtime_ns, b["abbr"])


def synodal_table(b: dict) -> dict:
    """What the offline copy needs to send /bible/rsb/<Abbr>/… on as the
    server does (offline-core.js biblePage): the Synodal's chapters of a book,
    {c: [its first verse, its last]}; where a verse's row is not the address
    its numbers make (/bible/Psa/22:1#tr-rsb in a book the KJV has,
    /bible/Tob/1#v3 in one it has not), that row's address; and where a
    chapter's first verse is not on its own chapter's page, that page."""
    with db() as con:
        rows, first, pages = _rows_of(con, b)
    span: dict[int, list[int]] = {}
    for (c, v) in rows:
        lo, hi = span.get(c, [v, v])
        span[c] = [min(lo, v), max(hi, v)]
    moved, starts = {}, {}
    for c, (lo, hi) in span.items():
        if rows[(c, lo)][0] != c:
            starts[str(c)] = rows[(c, lo)][0]
        for v in range(lo, hi + 1):
            to = _synodal_href(b, c, v, rows[(c, v)], first, pages)
            plain = (href(b, c, v) + "#tr-rsb") if b["kjv"] else href(b, c) + f"#v{v}"
            if to != plain:
                moved[f"{c}:{v}"] = to
    return {"chapters": {str(c): x for c, x in sorted(span.items())}, "moved": moved, "pages": starts}


# A Bible address typed in the search box, "John 3:16", "Gen 1:1", "1 John
# 4:8", "Psalm 23", "Jude 24", and the Synodal's, by its names and numbers,
# «Ин 3:16», «Быт 1:1», «Пс 22», «1 Цар 2:2»: the book by any name
# book_loosely() knows, or Psalm, Псалом; then a chapter, a verse, a range.
# None where it is no such address, or names a chapter the book lacks, and the
# search goes on as words.
RE_JUMP = re.compile(r"\s*([1-4I]{0,3}[\s-]*(?:я|е)?\s*[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё .]*?)\.?\s+([0-9]{1,3})"
                     r"(?::([0-9]{1,3})(?:\s*[-–]\s*([0-9]{1,3}))?)?\s*")
CYR = re.compile(r"[А-Яа-яЁё]")


def jump(q: str) -> str | None:
    if not there():
        return None
    m = RE_JUMP.fullmatch(q)
    if m is None:
        return None
    nm = m[1].strip()
    low = nm.lower()
    b = book_loosely("Psalms" if low == "psalm" else "Пс" if low in ("псалом", "псалмы", "псалтирь") else nm)
    if b is None:
        return None
    c, v, w = int(m[2]), m[3] and int(m[3]), m[4] and int(m[4])
    russian = bool(CYR.search(nm))
    if russian and b["rsb"]:
        # By the Synodal's numbers, its address /bible/rsb/…, which sends the
        # reader on to its row (app.py bible_synodal), as the offline copy
        # does from the Synodal's download.
        if b["rsb"]["chapters"] == 1 and v is None:   # Иуд 24
            c, v = 1, c
        if synodal_row(b, c, v if v is not None else None) is None:
            return None
        return f"/bible/rsb/{b['abbr']}/{c}" + (f":{v}" if v is not None else "")
    if not b["kjv"] and not russian:                 # Tobit 1:3: its own numbers are the address
        if not 1 <= c <= b["chapters"]:
            return None
        return href(b, c, v, w) if v else href(b, c)
    if b["kjv"] and b["kjv"]["chapters"] == 1 and v is None:   # Jude 24: a book of one chapter, by its verse
        c, v = 1, c
    if not 1 <= c <= b["chapters"]:
        return None
    return href(b, c, v, w) if v else href(b, c)


FTS = {"kjv": ("bible_kjv_fts", "bible_kjv_note_fts"), "rsb": ("bible_rsb_fts", "bible_rsb_note_fts")}
YO = str.maketrans("ёЁ", "еЕ")


def hits(version: str, fq: str, limit: int, offset: int) -> tuple[int, list[dict]]:
    """The verses of a version whose words, or whose notes', the search found,
    in the Bible's order: (how many, this window of them), each with its
    reference, its address, and what was found in its words and in its notes,
    as FTS5's snippet() marks it (app.py _snip makes the HTML).  The
    Synodal's are searched with ё read as е, as its index holds them."""
    vt, nt = FTS[version]
    if version == "rsb":
        fq = fq.translate(YO)
    hit = (f"SELECT rowid AS vid FROM {vt} WHERE {vt} MATCH ?"
           f" UNION SELECT n.verse_id FROM {nt} JOIN bible_note n ON n.id = {nt}.rowid WHERE {nt} MATCH ?")
    with db() as con:
        n = con.execute(f"SELECT COUNT(*) FROM ({hit})", (fq, fq)).fetchone()[0]
        rows = [dict(r) for r in con.execute(
            f"SELECT h.vid, b.abbr, b.id AS book, v.chapter, v.verse, v.alt, v.kind, v.rc, v.rv, v.rs,"
            f" trim(v.head || ' ' || v.text || ' ' || v.after) AS full"
            f" FROM ({hit}) h JOIN bible_verse v ON v.id = h.vid JOIN bible_book b ON b.id = v.book"
            " ORDER BY b.id, v.rc, v.rv, v.rs, v.id LIMIT ? OFFSET ?", (fq, fq, limit, offset))]
        ids = [r["vid"] for r in rows]
        within = ",".join("?" * len(ids))
        said = dict(con.execute(
            f"SELECT rowid, snippet({vt}, 0, char(2), char(3), char(4), 24) FROM {vt}"
            f" WHERE {vt} MATCH ? AND rowid IN ({within})", (fq, *ids)))
        noted: dict = {}
        for vid, s, nt_text in con.execute(
                f"SELECT n.verse_id, snippet({nt}, 0, char(2), char(3), char(4), 24), n.text FROM {nt}"
                f" JOIN bible_note n ON n.id = {nt}.rowid WHERE {nt} MATCH ? AND n.verse_id IN ({within})"
                " ORDER BY n.id",
                (fq, *ids)):
            noted.setdefault(vid, _unfold(s, nt_text) if version == "rsb" else s)
    for r in rows:
        b = book(r["abbr"])
        if version == "kjv":
            r["ref"] = f"{b['ref_name']} {r['chapter']}:{r['verse']}" if r["kind"] == "verse" else f"{b['ref_name']} {r['chapter']}"
            r["href"] = href(b, r["chapter"], r["verse"]) if r["kind"] == "verse" else href(b, r["chapter"]) + "#v0"
        else:
            num = f"({r['verse']})" if r["alt"] else str(r["verse"])
            r["ref"] = f"{b['rsb']['ref_name']} {r['chapter']}:{num}"
            # By its own numbers, which the server and the offline copy send
            # on to its row (app.py bible_synodal); 3 Ezra's bracketed series,
            # its page and the line's id.
            r["href"] = (f"/bible/rsb/{b['abbr']}/{r['chapter']}:{r['verse']}" if not r["alt"]
                         else href(b, r["rc"]) + f"#x{r['verse']}")
        r["s"], r["note"] = said.get(r["vid"]), noted.get(r["vid"])
        if version == "rsb" and r["s"]:
            r["s"] = _unfold(r["s"], r["full"])
    return n, rows


def _unfold(s: str, text: str) -> str:
    """What snippet() made of the Synodal's words read with ё as е, in its own
    letters: folded one letter for one, the snippet's stretch stands at the
    same place in `text`, and FTS5's marks \x02 \x03 \x04 stay where they
    are (app.py _unfold does the same for the translations)."""
    if "ё" not in text and "Ё" not in text:
        return s
    core = s.replace("\x02", "").replace("\x03", "").strip("\x04")
    i = text.translate(YO).find(core)
    if i < 0:
        raise ValueError(f"a search hit is not in its text: {core[:60]!r}")
    out = []
    for c in s:
        if c in "\x02\x03\x04":
            out.append(c)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)
