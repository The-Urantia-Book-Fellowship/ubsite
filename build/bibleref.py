"""The Bible references a study note makes, found in its text and made links.

The notes cite the Bible as plain words, as a reviewed note is written:
`Psalms~104:1--2`, `1~John~4:8`, `Isaiah~40:12, 22 and~26`.  None is marked,
and none is to be (the notes stay as written: data/study/README.md), so this
reads the note's text as build/study.py expand() has set it (a tie is U+00A0,
`--` an en dash) and makes each reference a `link` span over its own words,
to the verse in the King James Version (var/bible.db, build/bible.py), so that the
note's text, and the round trip, are as they were (Tigran, 2026-11-21: "so
that our references to the Bible can point directly there").

What it reads:

  a book's name as a reference writes it (data/kjv/books.tsv `ref_name`:
  Genesis, 1 Samuel, Song of Solomon; Psalm as well as Psalms), then a
  chapter, a chapter and verse, a range of verses or of chapter and verse:
  `John~1:1--3`, `Psalm~23`, `Jude~24` (a book of one chapter, by its verse);

  and after one, a list that goes on: ", 22", " and 14" (a verse of the same
  chapter: `John~1:1 and 14` is John 1:14), ", 145:8", " or 10:13", "; again
  at 7:13", never taking a numbered book's numeral for a verse (`Luke~23:43,
  2~Corinthians~12:4`);

  and a chapter and verse with no book named (`(22:37--38)`, after
  `Matthew~22:39`), linked only as tests/known-bible-carried.tsv lists it, by
  its note, its words and which time they stand there, with the verse it is
  (most often in the book the note named last before it, but Zechariah's
  "(2:12)" after Hebrews at 11:3.1) or "-" for no link (another author's
  words): a new one fails the build until it is looked at and listed, and so
  does a listed one no note makes, as tests/known-oracle-deltas.tsv works.  Never in a note's `corrects`, whose
  numbers are Block's slips ("Psalms~145:17 for his 145:7").

Fails loudly: a verse or chapter the KJV lacks (study-bible-ref); a book's
name and a number it cannot read, as `John~3.16` (study-bible-unread); a
link across another span's edge, which render() cannot nest
(study-bible-cross).  An abbreviation in another author's words (Knudson's
"Num. 23. 19") is no name it knows, and stays as he wrote it.
"""

from __future__ import annotations

import pathlib
import re

from . import bible

ROOT = pathlib.Path(__file__).resolve().parent.parent
KNOWN = ROOT / "tests" / "known-bible-carried.tsv"
SP = "[  ]"                       # a space, or a tie
DASH = "[–-]"                          # an en dash (`--`), or a hyphen


class Recognizer:
    def __init__(self, books: list[dict], verses: dict[str, dict[int, int]], known: dict):
        self.verses = verses
        self.abbr: dict[str, str] = {}
        for b in books:
            self.abbr[b["ref_name"]] = b["abbr"]
        self.abbr["Psalm"] = "Psa"
        names = sorted(self.abbr, key=len, reverse=True)
        alt = "|".join(re.escape(n).replace("\\ ", SP) for n in names)
        # What follows a numbered book's numeral: ", 2~Corinthians" is no verse 2.
        rest = "|".join(sorted({re.escape(n.split(" ", 1)[1]) for n in names if n[0].isdigit()}))
        self.name = f"(?<![\\w])(?P<book>{alt})"
        self.re_ref = re.compile(
            self.name + SP + r"(?P<c>\d{1,3})(?::(?P<v>\d{1,3}))?"
            r"(?:" + DASH + r"(?P<c2>\d{1,3})(?::(?P<v2>\d{1,3}))?)?")
        # What goes on after a reference: a separator, then a number or a
        # chapter and verse, or a range of either, never a numbered book's numeral.
        self.re_more = re.compile(
            r"(?P<sep>," + SP + "|" + SP + "(?:and|or)" + SP + r"|;" + SP + "again" + SP + "at" + SP + r")"
            r"(?P<a>\d{1,3})(?::(?P<b>\d{1,3}))?(?:" + DASH + r"(?P<a2>\d{1,3})(?::(?P<b2>\d{1,3}))?)?"
            r"(?!\d|" + SP + "(?:" + rest + r")\b|\.\d|:\d)")
        self.re_bare = re.compile(r"(?<![\w.:–-])(\d{1,3}):(\d{1,3})(?:" + DASH + r"(\d{1,3}))?(?![\w]|\.\d|:\d)")
        self.re_name_num = re.compile(self.name + SP + r"\d")
        self.known = known
        self.seen: set = set()

    @classmethod
    def load(cls) -> "Recognizer | None":
        """From var/bible.db and data/kjv/books.tsv, or None where the Bible
        is not built (make bible)."""
        if not bible.OUT.exists():
            return None
        books = [dict(zip(bible.KJV_BOOK, line.split("\t")))
                 for line in (bible.KJV / "books.tsv").read_text(encoding="utf-8").split("\n")[1:] if line]
        return cls(books, bible.verses_of(), read_known())

    # -- one reference ------------------------------------------------------
    def _href(self, abbr: str, c: int, v: int | None, c2: int | None, v2: int | None,
              where: str, words: str, report) -> str | None:
        chs = self.verses[abbr]
        if len(chs) == 1 and v is None:         # Jude~24: a book of one chapter, by its verse
            c, v, c2, v2 = 1, c, c2, None
        if c not in chs:
            report.hard("study-bible-ref", where, f"{words!r}: {abbr} has no chapter {c}")
            return None
        if v is None:
            if c2 is not None and (c2 not in chs or c2 < c):
                report.hard("study-bible-ref", where, f"{words!r}: no such run of chapters")
                return None
            return f"/bible/{abbr}/{c}"
        if not 1 <= v <= chs[c]:
            report.hard("study-bible-ref", where, f"{words!r}: {abbr} {c} has no verse {v}")
            return None
        if c2 is not None and v2 is None:       # 1:1--3, verses of one chapter
            if not v < c2 <= chs[c]:
                report.hard("study-bible-ref", where, f"{words!r}: no such run of verses")
                return None
            return f"/bible/{abbr}/{c}:{v}-{c2}"
        if c2 is not None:                      # 7:9--8:2, across a chapter's end: its first verse
            if c2 not in chs or not 1 <= v2 <= chs[c2] or (c2, v2) <= (c, v):
                report.hard("study-bible-ref", where, f"{words!r}: no such run of verses")
                return None
        return f"/bible/{abbr}/{c}:{v}"

    def find(self, text: str, spans, where: str, at: str, report, carry: bool = True) -> list[tuple]:
        """[(start, end, href)] for every reference in a note's `text`: `at`
        is the note's paragraph, for the list of references carried."""
        out: list[tuple] = []
        named: list[tuple[int, str]] = []       # (where a named reference ends, its book)
        taken: list[tuple[int, int]] = []
        links = [(s.start, s.end) for s in spans if s.kind == "link"]
        for m in self.re_ref.finditer(text):
            abbr = self.abbr[re.sub(SP, " ", m["book"])]
            n = lambda k: int(m[k]) if m[k] else None
            words = m[0]
            # John~3.16, or a chapter written with a colon but no verse: unread.
            if re.match(r"[.:]\d", text[m.end():]):
                report.hard("study-bible-unread", where, f"{text[m.start():m.end() + 4]!r}: not read as a reference")
                continue
            h = self._href(abbr, n("c"), n("v"), n("c2"), n("v2"), where, words, report)
            if h:
                out.append((m.start(), m.end(), h))
            end, c = m.end(), n("c2") if n("v2") is not None else n("c")
            chapter_only = m["v"] is None and len(self.verses[abbr]) > 1
            while (more := self.re_more.match(text, end)) is not None:
                a, b = int(more["a"]), more["b"] and int(more["b"])
                a2, b2 = more["a2"] and int(more["a2"]), more["b2"] and int(more["b2"])
                s0 = more.start("a")
                piece = text[s0:more.end()]
                if b is not None:               # , 145:8
                    h = self._href(abbr, a, b, a2, b2, where, piece, report)
                    c = a2 if b2 is not None else a
                elif chapter_only:              # Psalm~23, 24: chapters
                    h = self._href(abbr, a, None, a2, None, where, piece, report)
                else:                           # , 22 and 26: verses of the chapter
                    h = self._href(abbr, c, a, a2, None, where, piece, report)
                if h:
                    out.append((s0, more.end(), h))
                end = more.end()
            named.append((end, abbr))
            taken.append((m.start(), end))
        if carry:
            count: dict = {}
            for m in self.re_bare.finditer(text):
                if any(a <= m.start() < b for a, b in taken + links):
                    continue
                before = [abbr for e, abbr in named if e <= m.start()]
                if not before:
                    continue
                words = m[0].replace("\u2013", "--")
                count[words] = count.get(words, 0) + 1
                key = (at, words, count[words])
                self.seen.add(key)
                listed = self.known.get(key)
                guess = f"{before[-1]} {m[1]}:{m[2]}" + (f"-{m[3]}" if m[3] else "")
                if listed is None:
                    report.hard("study-bible-carried", where,
                                f"{m[0]!r} names no book, and the note named {before[-1]} last: list it in "
                                f"{KNOWN.name} as '{at}\t{words}\t{count[words]}\t{guess}', or '-' for no link")
                    continue
                if listed == "-":
                    continue
                r = re.fullmatch(r"([1-3]?[A-Z][a-z]{1,2}) (\d+):(\d+)(?:-(\d+))?", listed)
                if r is None or r[1] not in self.verses:
                    report.hard("study-bible-carried", where, f"{KNOWN.name}: {listed!r} is no verse")
                    continue
                h = self._href(r[1], int(r[2]), int(r[3]), int(r[4]) if r[4] else None, None,
                               where, m[0], report)
                if h:
                    out.append((m.start(), m.end(), h))
        for a, b, _ in out:
            for s in spans:
                if s.start < a < s.end < b or a < s.start < b < s.end:
                    report.hard("study-bible-cross", where, f"{text[a:b]!r} crosses a {s.kind} span")
        return out

    def stale(self) -> list[tuple]:
        """What the list of references carried names, and no note made."""
        return sorted(set(self.known) - self.seen)


def read_known() -> dict[tuple[str, str, int], str]:
    """tests/known-bible-carried.tsv: {(note's paragraph, words, which time
    in the note): the verse it links, or '-' for none}."""
    if not KNOWN.exists():
        return {}
    out = {}
    for line in KNOWN.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        at, words, n, verse = line.split("\t")[:4]
        out[(at, words, int(n))] = verse
    return out


RE_HREF = re.compile(r'href="/bible/([1-3]?[A-Z][a-z]{1,2})/(\d+)(?::(\d+)(?:-(\d+))?)?"')


def store(con) -> int:
    """bible_cite (build/schema/014_bible_cite.sql): every verse a study note
    links to, from the note's own HTML, where these links were made.  The
    Bible's page reads it, to name beside a verse the paragraphs whose notes
    cite it."""
    rows = []
    for fid, pid, html in con.execute("SELECT id, paragraph_id, html FROM footnote WHERE kind = 'study' ORDER BY id"):
        for m in RE_HREF.finditer(html):
            v = int(m[3]) if m[3] else None
            rows.append((fid, pid, m[1], int(m[2]), v, int(m[4]) if m[4] else v))
    con.executemany("INSERT INTO bible_cite VALUES (?,?,?,?,?,?)", rows)
    return len(rows)
