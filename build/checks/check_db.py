"""Gate the built database against the invariants and show what it can now answer."""

from __future__ import annotations

import sys

QUERIES = [
    ("papers",              "SELECT COUNT(*) FROM paper", 197),
    ("sections",            "SELECT COUNT(*) FROM section", 1626),
    ("combined headings",   "SELECT COUNT(*) FROM section WHERE combined_with IS NOT NULL", 1),
    ("paragraphs",          "SELECT COUNT(*) FROM paragraph", 14586),
    ("red-letter spans",    "SELECT COUNT(*) FROM span WHERE kind='redletter'", 1267),
    ("em spans",            "SELECT COUNT(*) FROM span WHERE kind='em'", 2295),
    ("1955 variant notes",  "SELECT COUNT(*) FROM footnote WHERE kind='variant-1955'", 180),
    ("index entries",       "SELECT COUNT(*) FROM index_entry", None),
    ("citations",           "SELECT COUNT(*) FROM citation", None),
    ("citation targets",    "SELECT COUNT(*) FROM citation_target", None),
    # 436 since the index's 6cd4d19 (2026-10-01): `29 A.D. > May 8 > death of
    # Salome' dropped by ruling -- 154:2.4 sends her to bed, not to her death.
    ("chronology events",   "SELECT COUNT(*) FROM chronology_event", 436),
]

INVARIANTS = [
    ("every span lies inside its paragraph",
     """SELECT COUNT(*) FROM span s JOIN paragraph p ON p.id = s.paragraph_id
         WHERE s.start < 0 OR s."end" > LENGTH(p.text)"""),
    ("no paragraph-precision citation is unresolved",
     "SELECT COUNT(*) FROM citation_target WHERE precision='para' AND paragraph_id IS NULL"),
    ("every See/See also resolves by some route",
     "SELECT COUNT(*) FROM xref WHERE route IS NULL"),
    ("every entry's root is a level-1 entry",
     """SELECT COUNT(*) FROM index_entry e JOIN index_entry r ON r.id = e.root_id
         WHERE r.level <> 1"""),
    ("every chronology event has a sortable year",
     "SELECT COUNT(*) FROM chronology_event WHERE year_sort IS NULL"),
    ("every index entry has an anchor",
     "SELECT COUNT(*) FROM index_entry WHERE anchor IS NULL"),
    ("no two entries of one headword share an anchor",
     """SELECT COUNT(*) FROM (SELECT 1 FROM index_entry
         GROUP BY root_id, anchor HAVING COUNT(*) > 1)"""),
    # Nothing a reader sees may still be LaTeX.  The 1955 notes were stored
    # raw, and seven of them showed "\bibemph {the}" on the page.
    ("no backslash in any text a reader sees",
     """SELECT (SELECT COUNT(*) FROM paragraph WHERE text GLOB '*\\*')
             + (SELECT COUNT(*) FROM footnote WHERE text GLOB '*\\*')
             + (SELECT COUNT(*) FROM section WHERE title GLOB '*\\*')
             + (SELECT COUNT(*) FROM paper WHERE title GLOB '*\\*')
             + (SELECT COUNT(*) FROM index_entry WHERE text GLOB '*\\*'
                                                    OR path_plain GLOB '*\\*')"""),
    ("no orphan paragraph in para_density",
     "SELECT COUNT(*) FROM paragraph p LEFT JOIN para_density d ON d.paragraph_id=p.id WHERE d.paragraph_id IS NULL"),
]


def run(con) -> int:
    bad = 0
    from ..render import strip_tags
    n = off = 0
    for text, h in con.execute("SELECT text, html FROM paragraph"):
        n += 1
        if strip_tags(h) != text:
            off += 1
    print(f"html cache: {n - off}/{n} paragraphs round-trip to the stored text"
          + ("" if not off else f"   {off} FAIL"))
    if off:
        bad += 1
    m = ioff = 0
    for text, h in con.execute("SELECT text, text_html FROM index_entry"):
        m += 1
        if strip_tags(h) != text:
            ioff += 1
    print(f"            {m - ioff}/{m} index entries round-trip"
          + ("" if not ioff else f"   {ioff} FAIL"))
    if ioff:
        bad += 1
    k = foff = 0
    for text, h in con.execute("SELECT text, html FROM footnote"):
        k += 1
        if strip_tags(h) != text:
            foff += 1
    print(f"            {k - foff}/{k} notes round-trip"
          + ("" if not foff else f"   {foff} FAIL"))
    if foff:
        bad += 1
    k = toff = 0
    for text, h in con.execute("SELECT title, title_html FROM section WHERE n > 0"):
        k += 1
        if strip_tags(h) != text:
            toff += 1
    print(f"            {k - toff}/{k} section titles round-trip"
          + ("" if not toff else f"   {toff} FAIL"))
    if toff:
        bad += 1

    # The chip must keep the editor's words.  Every "(" in an entry's printed
    # text is one of its citations, or inside a See target, or in its chip --
    # the old chip text dropped them all, and "Adam (village)" became "Adam".
    cits = dict(con.execute("SELECT entry_id, COUNT(*) FROM citation GROUP BY 1"))
    refs = {}
    for eid, target in con.execute("SELECT entry_id, target FROM xref"):
        refs[eid] = refs.get(eid, 0) + target.count("(")
    j = lost = 0
    for eid, text, path in con.execute("SELECT id, text, path_plain FROM index_entry"):
        j += 1
        chip = path.split(" \u203a ")[-1]
        if text.count("(") != chip.count("(") + cits.get(eid, 0) + refs.get(eid, 0):
            lost += 1
    print(f"chips:      {j - lost}/{j} keep every parenthesis that is not a citation"
          + ("" if not lost else f"   {lost} FAIL"))
    if lost:
        bad += 1

    print("counts")
    for name, q, expect in QUERIES:
        got = con.execute(q).fetchone()[0]
        mark = ""
        if expect is not None:
            mark = "  OK" if got == expect else f"  EXPECTED {expect:,}"
            if got != expect:
                bad += 1
        print(f"  {name:24} {got:>9,}{mark}")
    print("\ninvariants (all must be 0)")
    for name, q in INVARIANTS:
        got = con.execute(q).fetchone()[0]
        if got:
            bad += 1
        print(f"  {name:48} {got}{'' if not got else '   FAIL'}")
    return 1 if bad else 0
