"""The Bible, as var/bible.db holds it (build/bible.py): the KJV and the Synodal.

Each count of the first table must be 0: that the database is the copies in
data/kjv/ and data/rsb/ as they are now; that every chapter numbers its verses
as its version does, with no gap and no duplicate (the KJV 1..N, the Synodal
from 0 or 1, 3 Ezra 7's bracketed series apart), as every section of the book
does its paragraphs; that every part's HTML says its text and nothing more
(the round trip), every span lies inside its part, and every note has its
mark, a KJV note's before the first letter of a word; that every verse of both stands in a row, the Synodal's own rows never
on a KJV verse's number; and that in every chapter the rows compare by their
words' lengths better than the same texts shifted one verse either way, but
for the psalms tests/known-rsb-lengths.tsv lists, read and found right.  Then
the numbers verify/expectations.toml holds, [bible]; and that each copy is
still its edition's with its corrections, and nothing else (tools/kjv/convert.py
and tools/rsb/convert.py --check), where the edition is on this machine.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sqlite3
import statistics
import subprocess
import sys
import tomllib

from .. import bible
from ..render import strip_tags

ROOT = pathlib.Path(__file__).resolve().parents[2]
KNOWN = ROOT / "tests" / "known-rsb-lengths.tsv"


def expected() -> dict:
    with open(ROOT / "verify" / "expectations.toml", "rb") as fh:
        return tomllib.load(fh)["bible"]


def known() -> set[tuple[str, int]]:
    out = set()
    for line in KNOWN.read_text(encoding="utf-8").split("\n"):
        if line and not line.startswith("#"):
            b, c, _ = line.split("\t")
            out.add((b, int(c)))
    return out


def gaps(con) -> int:
    """Chapters whose verses are not as their version numbers them."""
    bad = 0
    for version, book, c, alt, vs in con.execute(
            "SELECT version, book, chapter, alt, group_concat(verse) FROM"
            " (SELECT * FROM bible_verse WHERE kind = 'verse' ORDER BY id)"
            " GROUP BY version, book, chapter, alt"):
        got = [int(x) for x in vs.split(",")]
        first = got[0] if version == "rsb" and got[0] in (0, 1) or alt else 1
        bad += got != list(range(first, first + len(got)))
    return bad


def shifted(con) -> list[tuple[str, int, float]]:
    """Chapters where the rows' lengths correlate no better than shifted by one."""
    plain = lambda t: len(re.sub(r"\[[^\[\]]*\]", "", t))
    rows: dict = collections.defaultdict(lambda: [0, 0])
    for b, rc, rv, rs, ver, t in con.execute("SELECT b.abbr, rc, rv, rs, version, text FROM bible_verse v"
                                             " JOIN bible_book b ON b.id = v.book"):
        rows[(b, rc, rv, rs)][ver == "rsb"] += plain(t)
    by: dict = collections.defaultdict(list)
    for (b, rc, rv, rs), (k, s) in sorted(rows.items(), key=lambda x: x[0][1:]):
        if k and s and rs == 0:
            by[(b, rc)].append((k, s))
    out = []
    for (b, c), xs in by.items():
        if len(xs) < 6:
            continue
        k, s = [a for a, _ in xs], [x for _, x in xs]
        try:
            here = statistics.correlation(k, s)
            near = max(statistics.correlation(k[1:], s[:-1]), statistics.correlation(k[:-1], s[1:]))
        except statistics.StatisticsError:
            continue
        if here <= near:
            out.append((b, c, here))
    return out


def run(db: pathlib.Path = bible.OUT) -> int:
    if not db.exists():
        print("  var/bible.db is missing (make bible)")
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    rc = 0
    meta = dict(con.execute("SELECT key, value FROM bible_meta"))
    trips = 0
    for t, h, hy, ht, hh, at, ah in con.execute(
            "SELECT text, html, html_hy, head, head_html, after, after_html FROM bible_verse"):
        trips += strip_tags(h) != t or strip_tags(hy).replace("­", "") != t
        trips += strip_tags(hh) != ht or strip_tags(ah) != at
    for t, h, hy in con.execute("SELECT text, html, html_hy FROM bible_note"):
        trips += strip_tags(h) != t or strip_tags(hy).replace("­", "") != t
    outside = one("SELECT COUNT(*) FROM bible_span s JOIN bible_verse v ON v.id = s.verse_id"
                  " WHERE s.part != 'note' AND s.\"end\" > length("
                  " CASE s.part WHEN 'text' THEN v.text WHEN 'head' THEN v.head ELSE v.after END)")
    # A note's mark in its verse's HTML or its heading's, one to each note.
    marks = 0
    for vid, html, head_html, n in con.execute(
            "SELECT v.id, v.html, v.head_html, (SELECT COUNT(*) FROM bible_note n WHERE n.verse_id = v.id)"
            " FROM bible_verse v"):
        keys = [k for (k,) in con.execute("SELECT key FROM bible_note WHERE verse_id = ? ORDER BY n", (vid,))]
        found = re.findall(r'id="fnref([^"]+)"', head_html + html)
        marks += found != keys
    # A KJV note's mark stands before the first letter of a word it glosses
    # (build/kjvnotes.py, data/kjv/marks.tsv), never inside a word or after one.
    astray = 0
    for t, start in con.execute("SELECT v.text, s.start FROM bible_span s JOIN bible_verse v ON v.id = s.verse_id"
                                " WHERE v.version = 'kjv' AND s.kind = 'fnref' AND s.part = 'text'"):
        astray += not (start < len(t) and t[start].isalpha() and (start == 0 or not t[start - 1].isalnum()))
    lone = one("SELECT COUNT(*) FROM (SELECT book, rc, rv FROM bible_verse WHERE rs = 0"
               " GROUP BY book, rc, rv HAVING sum(version = 'kjv') = 0) r"
               " WHERE EXISTS (SELECT 1 FROM bible_verse k WHERE k.version = 'kjv'"
               " AND k.book = r.book AND k.rc = r.rc)")
    bad_shift = [(b, c) for b, c, _ in shifted(con)]
    gates = [
        ("var/bible.db is not of data/ as it is (make bible)", int(meta.get("data") != bible.digest())),
        ("chapters whose verses are not as their version numbers them", gaps(con)),
        ("parts whose HTML says otherwise than their text", trips),
        ("spans outside their part", outside),
        ("verses whose notes and marks disagree", marks),
        ("KJV notes' marks not before a word", astray),
        ("the Synodal's own rows on a KJV verse's number", lone),
        ("chapters fitting a shift, not in known-rsb-lengths.tsv", len(set(bad_shift) - known())),
        ("known-rsb-lengths.tsv lines that fit as placed now", len(known() - set(bad_shift))),
    ]
    for label, n in gates:
        print(f"  {label:60} {n}")
        rc |= bool(n)
    want = expected()
    for k, v in want.items():
        if k in ("measured_on", "source_commit", "kjv_corrections", "kjv_witness_lines", "kjv_marks_lines",
                 "rsb_table_lines"):
            continue
        got = int(meta.get(k, -1))
        ok = got == v
        print(f"  {k:16} {got:>7,}" + ("" if ok else f"   EXPECTED {v:,} (verify/expectations.toml [bible])"))
        rc |= not ok
    con.close()
    lines = lambda path: sum(1 for x in path.read_text(encoding="utf-8").split("\n")[1:] if x)
    for k, path in (("kjv_corrections", bible.KJV / "corrections.tsv"),
                    ("kjv_witness_lines", bible.KJV / "witness.tsv"),
                    ("kjv_marks_lines", bible.MARKS),
                    ("rsb_table_lines", bible.TABLE_FILE)):
        ok = lines(path) == want[k]
        print(f"  {k:16} {lines(path):>7,}" + ("" if ok else f"   EXPECTED {want[k]:,}"))
        rc |= not ok
    # Each copy is still its edition's, mended and merged as listed, and
    # nothing else, where the edition is here to read; and the table places
    # every verse of both.
    for tool in ("tools.kjv.convert", "tools.rsb.convert", "tools.rsb.versify"):
        r = subprocess.run([sys.executable, "-m", tool, "--check"], cwd=ROOT, capture_output=True, text=True)
        for line in (r.stdout + r.stderr).strip().split("\n"):
            print(f"  {line}")
        rc |= r.returncode != 0
    return rc
