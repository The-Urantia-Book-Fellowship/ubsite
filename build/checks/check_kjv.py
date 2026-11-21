"""The King James Version, as var/kjv.db holds it (build/kjv.py).

Each count of the first table must be 0: that the database is the copy in
data/kjv/ as it is now, that every chapter numbers its verses 1..N with no gap
and no duplicate, as every section of the book does its paragraphs, that
every part's HTML says its text and nothing more (the round trip), that every
span lies inside its part, and that a note's mark stands where its note is.
Then the numbers verify/expectations.toml holds, [kjv]; and that data/kjv/ is
still the edition's KJV with its corrections and the witness's lines, and
nothing else (tools/kjv/convert.py --check), where the edition is on this
machine.
"""

from __future__ import annotations

import pathlib
import sqlite3
import tomllib

from .. import kjv
from ..render import strip_tags

ROOT = pathlib.Path(__file__).resolve().parents[2]


def expected() -> dict:
    with open(ROOT / "verify" / "expectations.toml", "rb") as fh:
        return tomllib.load(fh)["kjv"]


def run(db: pathlib.Path = kjv.OUT) -> int:
    if not db.exists():
        print("  var/kjv.db is missing (make kjv)")
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    rc = 0
    meta = dict(con.execute("SELECT key, value FROM kjv_meta"))
    gaps = 0
    for book, c, vs in con.execute("SELECT book, chapter, group_concat(verse) FROM"
                                   " (SELECT book, chapter, verse FROM kjv_verse ORDER BY id)"
                                   " GROUP BY book, chapter"):
        if [int(x) for x in vs.split(",")] != list(range(1, len(vs.split(",")) + 1)):
            gaps += 1
    chapters_gap = sum(1 for (b, n, cs) in con.execute(
        "SELECT b.id, b.chapters, group_concat(DISTINCT v.chapter) FROM kjv_book b"
        " JOIN kjv_verse v ON v.book = b.id GROUP BY b.id")
        if sorted(int(x) for x in cs.split(",")) != list(range(1, n + 1)))
    trips = 0
    for t, h, hy, ht, hh, at, ah in con.execute(
            "SELECT text, html, html_hy, head, head_html, after, after_html FROM kjv_verse"):
        trips += strip_tags(h) != t or strip_tags(hy).replace("­", "") != t
        trips += strip_tags(hh) != ht or strip_tags(ah) != at
    for t, h, hy in con.execute("SELECT text, html, html_hy FROM kjv_note"):
        trips += strip_tags(h) != t or strip_tags(hy).replace("­", "") != t
    outside = one("SELECT COUNT(*) FROM kjv_span s JOIN kjv_verse v ON v.id = s.verse_id"
                  " LEFT JOIN kjv_note n ON n.verse_id = s.verse_id WHERE s.\"end\" > length("
                  " CASE s.part WHEN 'text' THEN v.text WHEN 'head' THEN v.head"
                  " WHEN 'after' THEN v.after ELSE n.text END)")
    marks = one("SELECT COUNT(*) FROM kjv_verse v LEFT JOIN kjv_note n ON n.verse_id = v.id"
                " WHERE (n.verse_id IS NULL) != (instr(v.html, 'data-k=\"kjv\"') = 0)")
    gates = [
        ("var/kjv.db is not of data/kjv/ as it is (make kjv)", int(meta.get("data") != kjv.digest())),
        ("chapters whose verses are not 1..N", gaps),
        ("books whose chapters are not 1..N", chapters_gap),
        ("parts whose HTML says otherwise than their text", trips),
        ("spans outside their part", outside),
        ("verses whose note and mark disagree", marks),
    ]
    for label, n in gates:
        print(f"  {label:52} {n}")
        rc |= bool(n)
    want = expected()
    for k in ("books", "chapters", "verses", "notes", "pilcrows", "heads", "afters", "supplied", "sc"):
        got = int(meta.get(k, -1))
        ok = got == want[k]
        print(f"  {k:12} {got:>7,}" + ("" if ok else f"   EXPECTED {want[k]:,} (verify/expectations.toml [kjv])"))
        rc |= not ok
    con.close()
    lines = lambda name: sum(1 for x in (kjv.DATA / name).read_text(encoding="utf-8").split("\n")[1:] if x)
    for k, name in (("corrections", "corrections.tsv"), ("witness_lines", "witness.tsv")):
        ok = lines(name) == want[k]
        print(f"  {k:12} {lines(name):>7,}" + ("" if ok else f"   EXPECTED {want[k]:,}"))
        rc |= not ok
    # The copy is still the edition's, mended and merged as listed, and
    # nothing else: where the edition is here to read.
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "tools.kjv.convert", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    for line in (r.stdout + r.stderr).strip().split("\n"):
        print(f"  {line}")
    rc |= r.returncode != 0
    return rc
