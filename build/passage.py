"""The passages of the moment: data/passages.tsv into the `passage` table.

The home page shows one passage of the text at each visit (Tigran, 2026-11-17,
on the design's canvas: "Passage of the moment", from a list he reviews, as
the study notes are, a new one each visit).  The list is data/passages.tsv,
kept by tools/passages/apply.py from his rulings in var/passages/review.md and
never by hand:

    ref<TAB>quote

`ref` is a paragraph; `quote` the words of it that are shown, which occur
there once and are whole words, as the quiz's quoted passages are
(build/quiz.py), or ¶ for the paragraph whole.

Held, each a hard failure, since the home page is what a visitor sees first:
the paragraph is there; the words are in it, once, and whole; they begin a
sentence and end one, so that nothing shown is cut out of the middle of a
thought; they are no longer than LONGEST, which is what the page's card holds
without becoming the page; and no passage is listed twice.  The words are
stored as the paragraph sets them, its red letter and its italics
(quiz._quote_html), so that stripping the tags gives the words byte for byte,
as for every paragraph.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3

from .quiz import WHOLE, _quote_html
from .render import strip_tags

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "passages.tsv"
# The longest passage, in characters: 12:7.9's sentence on the love of the
# Father is 195, the canvas's longest, 159:3.12, 263.
LONGEST = 480
ENDS = (".", "!", "?")
CLOSERS = "”’"
RE_END = re.compile(r"[.!?][”’]*$")


def rows(path: pathlib.Path = LIST):
    """(line number, ref, quote) of the list, past its comments and its header."""
    if not path.exists():
        return
    header = True
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.startswith("#"):
            continue
        if header:
            header = False
            continue
        f = raw.split("\t")
        yield n, f[0], (f[1] if len(f) > 1 else ""), len(f)


def anchor(text: str, quote: str) -> tuple[int | None, str]:
    """Where `quote` begins in the paragraph, or None and why not: there once,
    whole words, a sentence's beginning and a sentence's end."""
    if not quote or quote != quote.strip():
        return None, "no words, or a space before or after them"
    i = text.find(quote)
    if i < 0:
        return None, "the words are not in the paragraph"
    if text.find(quote, i + 1) >= 0:
        return None, "the words occur more than once: say more"
    e = i + len(quote)
    if (i > 0 and text[i - 1].isalnum() and quote[0].isalnum()) or \
            (e < len(text) and text[e - 1].isalnum() and text[e].isalnum()):
        return None, "the words begin or end inside a word"
    first = quote.lstrip("“‘")[:1]
    if not (first.isupper() or first.isdigit()):
        return None, "the words do not begin a sentence"
    if not RE_END.search(quote):
        return None, "the words do not end a sentence"
    # Not the middle of one either: before them the paragraph's start, a
    # sentence's end, or the label of a list's item ("3. "); after them its end
    # or a space.
    before = text[:i].rstrip().rstrip("“‘").rstrip()
    if before and not RE_END.search(before) and not before.endswith((":", "—")):
        return None, "the words begin in the middle of a sentence"
    # After them the paragraph's end or a space; or the mark that closes a
    # quotation they were said in, which the passage may leave out.
    after = text[e:].lstrip(CLOSERS)
    if after and not after[0].isspace():
        return None, "the words end in the middle of a sentence"
    return i, ""


def load(con: sqlite3.Connection, report) -> int:
    """Store the list; return how many passages it has."""
    para = {r: (i, t, p) for i, r, t, p in con.execute("SELECT id, ref, text, paper_n FROM paragraph")}
    title = dict(con.execute("SELECT n, title FROM paper"))
    seen: set[tuple[int, int]] = set()
    out = []
    for line, ref, quote, fields in rows():
        at = f"data/{LIST.name}:{line}"
        if fields != 2:
            report.hard("passage-list", at, "ref<TAB>quote, the words quoted or ¶ for the paragraph whole")
            continue
        if ref not in para:
            report.hard("passage-ref", at, f"{ref}: no such paragraph")
            continue
        pid, text, paper = para[ref]
        words = text if quote == WHOLE else quote
        start, why = anchor(text, words)
        if start is None:
            report.hard("passage-quote", at, f"{ref} {words[:50]!r}...: {why}")
            continue
        if len(words) > LONGEST:
            report.hard("passage-long", at, f"{ref}: {len(words)} characters, and the card holds {LONGEST}")
            continue
        if (pid, start) in seen:
            report.hard("passage-twice", at, f"{ref} {words[:50]!r}... is listed twice")
            continue
        seen.add((pid, start))
        html = _quote_html(con, pid, text, start, words)
        if strip_tags(html) != words:
            report.hard("passage-roundtrip", at, f"{ref}: its tags stripped are not its words")
            continue
        out.append((len(out) + 1, pid, ref, paper, title[paper], start, words, html))
    con.executemany("INSERT INTO passage VALUES (?,?,?,?,?,?,?,?)", out)
    return len(out)


def check(db) -> int:
    """What was stored, each count of which must be 0, and the list's size by
    part of the book."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    n = one("SELECT COUNT(*) FROM passage")
    listed = sum(1 for _ in rows())
    by_part = con.execute("SELECT COALESCE(p.part_n, 0), COUNT(*) FROM passage x JOIN paper p ON p.n = x.paper_n"
                          " GROUP BY 1 ORDER BY 1").fetchall()
    print(f"  {n} passages" + (": " + ", ".join(f"{c} of Part {'I II III IV'.split()[k - 1]}" if k else f"{c} of the Foreword"
                                                 for k, c in by_part) if n else ""))
    checks = [
        ("the database holds every line of data/passages.tsv", abs(n - listed)),
        ("every passage is words of its paragraph, where the table says",
         one("SELECT COUNT(*) FROM passage x JOIN paragraph p ON p.id = x.paragraph_id"
             " WHERE substr(p.text, x.start + 1, length(x.text)) != x.text OR p.ref != x.ref")),
        ("every passage names its paper by its title",
         one("SELECT COUNT(*) FROM passage x JOIN paper p ON p.n = x.paper_n WHERE p.title != x.title")),
        ("every passage's tags, stripped, are its words",
         sum(strip_tags(h) != t for h, t in con.execute("SELECT html, text FROM passage"))),
        ("they are numbered from 1 with no gap", one("SELECT COALESCE(MAX(n), 0) - COUNT(*) FROM passage")),
    ]
    rc = 0
    for what, bad in checks:
        print(f"  {what:<62} {bad}")
        rc |= bool(bad)
    return rc
