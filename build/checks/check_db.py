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
    # The SRT Committee's page (build/srt.py): every change it considered, and the
    # notes it gives a reason; the 13 without are in tests/known-srt-deltas.tsv.
    ("SRT changes considered", "SELECT COUNT(*) FROM srt_item", 319),
    ("  1955 notes with their reason",
     "SELECT COUNT(*) FROM footnote WHERE srt_item_id IS NOT NULL", 167),
    ("index entries",       "SELECT COUNT(*) FROM index_entry", None),
    ("citations",           "SELECT COUNT(*) FROM citation", None),
    ("citation targets",    "SELECT COUNT(*) FROM citation_target", None),
    # 436 since the index's 6cd4d19 (2026-10-01): `29 A.D. > May 8 > death of
    # Salome' dropped by ruling -- 154:2.4 sends her to bed, not to her death.
    ("chronology events",   "SELECT COUNT(*) FROM chronology_event", 436),
    # The index's own check_tex.py asserts these same counts on the master.
    ("appendix B entries",  "SELECT COUNT(*) FROM index_entry WHERE scope='B'", 308),
    ("appendix C entries",  "SELECT COUNT(*) FROM index_entry WHERE scope='C'", 86),
    ("appendix D entries",  "SELECT COUNT(*) FROM index_entry WHERE scope='D'", 429),
    ("appendix E entries",  "SELECT COUNT(*) FROM index_entry WHERE scope='E'", 72),
    ("appendix F entries",  "SELECT COUNT(*) FROM index_entry WHERE scope='F'", 456),
    # The Foundation numbers these otherwise (build/foundation.py,
    # tests/known-uf-refs.tsv): 134:6.14-16, 139:9.1-11, 144:5.11-102, 0:12.10.
    ("renumbered by the Foundation",
     "SELECT COUNT(*) FROM paragraph p JOIN uf_paragraph u ON u.paragraph_id = p.id"
     " WHERE u.ref IS NOT p.ref", 107),
    ("  sections renumbered",
     "SELECT COUNT(*) FROM section s JOIN uf_section u ON u.section_id = s.id"
     " WHERE u.ref IS NOT s.paper_n || ':' || s.n", 1),
    # 0:12.10, which the Foundation does not number.
    ("  without a 1955 page", "SELECT COUNT(*) FROM uf_paragraph WHERE page IS NULL", 1),
    ("text version",        "SELECT MAX(n) FROM text_version", None),
    # Reported, not asserted: they move as the index is edited.
    ("B-F rows naming an A-Z headword", "SELECT COUNT(*) FROM appendix_head", None),
    ("events finished by their date",   "SELECT COUNT(*) FROM chronology_event WHERE reads_on", None),
]

INVARIANTS = [
    ("every span lies inside its paragraph",
     """SELECT COUNT(*) FROM span s JOIN paragraph p ON p.id = s.paragraph_id
         WHERE s.start < 0 OR s."end" > LENGTH(p.text)"""),
    ("no paragraph-precision citation is unresolved",
     "SELECT COUNT(*) FROM citation_target WHERE precision='para' AND paragraph_id IS NULL"),
    ("every See, See also and q.v. resolves by some route",
     "SELECT COUNT(*) FROM xref WHERE route IS NULL"),
    ("every q.v. is recorded as a cross-reference",
     """SELECT COUNT(*) FROM index_entry e WHERE e.qv = 1 AND NOT EXISTS
         (SELECT 1 FROM xref x WHERE x.entry_id = e.id AND x.kind = 'qv')"""),
    ("every q.v. names its headword with a link",
     """SELECT COUNT(*) FROM index_entry WHERE qv = 1
         AND text_html NOT LIKE '%<a class="hw" href="/i/%</a> <i>q.v.</i>'"""),
    ("every entry's root is a level-1 entry",
     """SELECT COUNT(*) FROM index_entry e JOIN index_entry r ON r.id = e.root_id
         WHERE r.level <> 1"""),
    ("every chronology event has a sortable year",
     "SELECT COUNT(*) FROM chronology_event WHERE year_sort IS NULL"),
    ("every index entry has an anchor",
     "SELECT COUNT(*) FROM index_entry WHERE anchor IS NULL"),
    # A page's anchors: a concept page holds one headword's tree, an appendix
    # page the whole appendix.
    ("no two entries on one page share an anchor",
     """SELECT COUNT(*) FROM (SELECT 1 FROM index_entry
         GROUP BY CASE scope WHEN 'az' THEN root_id ELSE scope END, anchor
         HAVING COUNT(*) > 1)"""),
    # Nothing a reader sees may still be LaTeX.  The 1955 notes were stored
    # raw, and seven of them showed "\bibemph {the}" on the page.
    ("no backslash in any text a reader sees",
     """SELECT (SELECT COUNT(*) FROM paragraph WHERE text GLOB '*\\*')
             + (SELECT COUNT(*) FROM footnote WHERE text GLOB '*\\*')
             + (SELECT COUNT(*) FROM section WHERE title GLOB '*\\*')
             + (SELECT COUNT(*) FROM paper WHERE title GLOB '*\\*')
             + (SELECT COUNT(*) FROM index_entry WHERE text GLOB '*\\*'
                                                    OR path_plain GLOB '*\\*')"""),
    # The footer and /healthz name these commits; a build that cannot is not shipped.
    ("press and index commits recorded (missing)",
     "SELECT 2 - COUNT(*) FROM build_source WHERE repo IN ('press','index')"),
    ("the SRT snapshot recorded (missing)",
     "SELECT 1 - COUNT(*) FROM build_source WHERE repo = 'srt'"),
    # A note's marker stands in its paragraph, and each marker has its note.
    ("every note's anchor lies inside its paragraph",
     """SELECT COUNT(*) FROM footnote f JOIN paragraph p ON p.id = f.paragraph_id
         WHERE f.anchor < 0 OR f.anchor > LENGTH(p.text)"""),
    ("paragraphs whose markers and notes differ in number",
     """SELECT COUNT(*) FROM paragraph p
         WHERE (SELECT COUNT(*) FROM span s WHERE s.paragraph_id = p.id AND s.kind = 'fnref')
            <> (SELECT COUNT(*) FROM footnote f WHERE f.paragraph_id = p.id)"""),
    ("a 1955 note's reason is about its own paragraph",
     """SELECT COUNT(*) FROM footnote f JOIN srt_item s ON s.id = f.srt_item_id
         WHERE s.paragraph_id IS NOT f.paragraph_id"""),
    # Search finds a note by what its card says: the reading, and the reasons
    # exactly when the card gives some.
    ("notes without their search row, or with another's words",
     """SELECT COUNT(*) FROM footnote f
         LEFT JOIN footnote_fts x ON x.rowid = f.id
         LEFT JOIN srt_item s ON s.id = f.srt_item_id
         LEFT JOIN srt_item t ON t.id = s.see_id
         WHERE x.rowid IS NULL OR x.reading IS NOT f.text
            OR (x.reasons <> '') <> (COALESCE(s.why_text, '') || COALESCE(t.why_text, '') <> '')"""),
    ("search rows without their note",
     "SELECT COUNT(*) FROM footnote_fts x LEFT JOIN footnote f ON f.id = x.rowid WHERE f.id IS NULL"),
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
    k = soff = 0
    for text, h in con.execute("SELECT then_text, then_html FROM srt_item"
                               " UNION ALL SELECT why_text, why_html FROM srt_item"):
        k += 1
        if strip_tags(h) != text:
            soff += 1
    print(f"            {k - soff}/{k} SRT texts round-trip"
          + ("" if not soff else f"   {soff} FAIL"))
    if soff:
        bad += 1
    # Every link the build rewrote to the book lands on a place in it.
    import re
    places = {r for (r,) in con.execute("SELECT ref FROM paragraph")}
    places |= {f"{p}:{n}" for p, n in con.execute("SELECT paper_n, n FROM section")}
    places |= {str(n) for (n,) in con.execute("SELECT n FROM paper")}
    k = loff = 0
    for (h,) in con.execute("SELECT then_html || why_html FROM srt_item"):
        for to in re.findall(r'href="/([^"]*)"', h):
            k += 1
            if to not in places:
                loff += 1
                print(f"            SRT link to nowhere: /{to}")
    print(f"            {k - loff}/{k} SRT links into the book land"
          + ("" if not loff else f"   {loff} FAIL"))
    if loff:
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

    # Every stored fragment is well-formed XML, because the EPUB is XML and
    # carries these fragments as they are.  A browser forgives a bare & or an
    # unclosed <br>; an e-reader may refuse the whole file.
    import xml.etree.ElementTree as ET
    k = xoff = 0
    for where, h in con.execute(
            "SELECT 'paragraph ' || ref, html FROM paragraph"
            " UNION ALL SELECT 'note ' || id, html FROM footnote"
            " UNION ALL SELECT 'SRT ' || name, then_html || why_html FROM srt_item"
            " UNION ALL SELECT 'section ' || paper_n || ':' || n, title_html FROM section"
            "  WHERE title_html IS NOT NULL"
            " UNION ALL SELECT 'entry ' || id, text_html FROM index_entry"):
        k += 1
        try:
            ET.fromstring(f"<x>{h}</x>")
        except ET.ParseError as e:
            xoff += 1
            if xoff <= 5:
                print(f"            not XML: {where}: {e}")
    print(f"            {k - xoff}/{k} stored HTML fragments are well-formed XML"
          + ("" if not xoff else f"   {xoff} FAIL"))
    if xoff:
        bad += 1

    # The chip must keep the editor's words.  Every "(" in an entry's printed
    # text is one of its citations, or inside a See target, or in its chip --
    # the old chip text dropped them all, and "Adam (village)" became "Adam".
    cits = dict(con.execute("SELECT entry_id, COUNT(*) FROM citation GROUP BY 1"))
    refs = {}
    # A q.v.'s target is the entry's own name, already counted in its chip.
    for eid, target in con.execute("SELECT entry_id, target FROM xref"
                                   " WHERE kind IN ('see', 'seealso')"):
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

    bad += _text_api(con)

    # The 1955 pages run forward through the book, and no two paragraphs begin
    # at one place: a paragraph matched to the wrong one of the Foundation's
    # would break the run.
    prev, back = None, []
    for ref, page in con.execute(
            "SELECT p.ref, u.page FROM paragraph p JOIN uf_paragraph u"
            " ON u.paragraph_id = p.id WHERE u.page IS NOT NULL ORDER BY p.ord"):
        at = tuple(map(int, page.split(".")))
        if prev and at <= prev[1]:
            back.append(f"{prev[0]} ({'.'.join(map(str, prev[1]))}) then {ref} ({page})")
        prev = (ref, at)
    print(f"1955 pages: run forward through the book"
          + ("" if not back else f"   {len(back)} FAIL: {back[:3]}"))
    bad += bool(back)

    print("counts")
    for name, q, expect in QUERIES:
        got = con.execute(q).fetchone()[0]
        mark = ""
        if expect is not None:
            mark = "  OK" if got == expect else f"  EXPECTED {expect:,}"
            if got != expect:
                bad += 1
        print(f"  {name:32} {got:>9,}{mark}")
    print("\ninvariants (all must be 0)")
    for name, q in INVARIANTS:
        got = con.execute(q).fetchone()[0]
        if got:
            bad += 1
        print(f"  {name:52} {got}{'' if not got else '   FAIL'}")
    return 1 if bad else 0


def _text_api(con) -> int:
    """What /api/v1/text serves: one record for each thing, each true to the text.

    The route sends these bodies as they are stored, so this is the API's own
    round-trip gate, and the ledger in data/text/ must describe this database.
    """
    import json

    from .. import versions
    from ..render import strip_tags

    bad = 0
    want = dict(con.execute(
        "SELECT 'part', COUNT(*) FROM part UNION ALL SELECT 'paper', COUNT(*) FROM paper"
        " UNION ALL SELECT 'section', COUNT(*) FROM section"
        " UNION ALL SELECT 'paragraph', COUNT(*) FROM paragraph"))
    got = dict(con.execute("SELECT kind, COUNT(*) FROM text_unit GROUP BY kind"))
    texts = dict(con.execute("SELECT ref, text FROM paragraph"))
    n = off = 0
    for kind, key, body, h in con.execute("SELECT kind, key, body, hash FROM text_unit"):
        n += 1
        rec = json.loads(body)
        ok = rec.pop("hash") == h == versions.digest(rec)
        if kind == "paragraph":
            ok = (ok and rec["ref"] == key and strip_tags(rec["html"]) == texts.get(key)
                  and 'class="fn"' not in rec["html"])
        if not ok:
            off += 1
            if off <= 5:
                print(f"            text API record wrong: {kind} {key}")
    print(f"text API:   {n - off}/{n} records hash true, and every paragraph's HTML strips to its text"
          + ("" if not off else f"   {off} FAIL"))
    if off or got != want:
        bad += 1
        if got != want:
            print(f"            records {got}, expected one for each of {want}   FAIL")

    led = versions.fold()
    stored = {(k, key): (h, v) for k, key, h, v in con.execute(
        "SELECT kind, key, hash, version FROM text_unit")}
    stored.update({(k, key): ("-", v) for k, key, v in con.execute(
        "SELECT kind, key, version FROM text_removed")})
    vers = [tuple(r) for r in con.execute("SELECT * FROM text_version ORDER BY n")]
    same = stored == led.latest and vers == led.versions
    print(f"            data/text/ is the history this database carries"
          f" (version {led.n})" + ("" if same else "   FAIL: rebuild, or the ledger was edited"))
    return bad + (not same)
