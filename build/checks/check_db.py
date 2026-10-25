"""Gate the built database against the invariants and show what it can now answer."""

from __future__ import annotations

import sys

QUERIES = [
    ("papers",              "SELECT COUNT(*) FROM paper", 197),
    ("sections",            "SELECT COUNT(*) FROM section", 1626),
    ("combined headings",   "SELECT COUNT(*) FROM section WHERE combined_with IS NOT NULL", 1),
    ("paragraphs",          "SELECT COUNT(*) FROM paragraph", 14586),
    # 0:12.10 ACKNOWLEDGMENT, centred like a section's title (readers/press.py).
    ("  headings in the text", "SELECT COUNT(*) FROM paragraph WHERE heading", 1),
    # \separatorline before the closing notes of Parts I-III, \separatorshort in
    # 120:3, 134:6 and six times in 144:5 (readers/press.py; the Foundation's ten
    # are held against them in build/foundation.py).
    ("  separators before", "SELECT COUNT(*) FROM paragraph WHERE sep_before IS NOT NULL", 11),
    ("    of five stars", "SELECT COUNT(*) FROM paragraph WHERE sep_before = '* * * * *'", 3),
    # The psalm in 48:6, the song in 122:9, the Lord's Prayer in 144:3 and the
    # seven prayers of 144:5, one block each, as the press sets them in quoting.
    ("  verse lines",       "SELECT COUNT(*) FROM paragraph WHERE src <> 'vs'", 144),
    ("    blocks of verse", "SELECT COUNT(*) FROM paragraph WHERE verse_start", 10),
    ("    set in further (\\hsetoff)", "SELECT COUNT(*) FROM paragraph WHERE setoff", 4),
    ("red-letter spans",    "SELECT COUNT(*) FROM span WHERE kind='redletter'", 1267),
    ("em spans",            "SELECT COUNT(*) FROM span WHERE kind='em'", 2295),
    # Where a word may break at a line's end, as the book lets it (build/hyphen.py):
    # the source's own \- and, in paragraph.html_hy, every soft hyphen.
    ("discretionary hyphens (\\-)", "SELECT COUNT(*) FROM span WHERE kind='shy'", 1392),
    ("soft hyphens",        "SELECT SUM(LENGTH(html_hy) - LENGTH(REPLACE(html_hy, char(173), '')))"
                            " FROM paragraph", 530865),
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
    # tests/known-uf-refs.tsv): 134:6.14-16, 139:9.1-11, 144:5.11-102.  It was
    # 107, with 0:12.10, until 2026-10-12: the Foundation numbers it too.
    ("renumbered by the Foundation",
     "SELECT COUNT(*) FROM paragraph p JOIN uf_paragraph u ON u.paragraph_id = p.id"
     " WHERE u.ref IS NOT p.ref", 106),
    ("  sections renumbered",
     "SELECT COUNT(*) FROM section s JOIN uf_section u ON u.section_id = s.id"
     " WHERE u.ref IS NOT s.paper_n || ':' || s.n", 1),
    ("  without a Foundation reference", "SELECT COUNT(*) FROM uf_paragraph WHERE ref IS NULL", 0),
    # 0:12.10's, 16.7, is not printed: it is the place its neighbours leave.
    ("  without a 1955 page", "SELECT COUNT(*) FROM uf_paragraph WHERE page IS NULL", 0),
    ("text version",        "SELECT MAX(n) FROM text_version", None),
    # Reported, not asserted: they move as the index is edited.
    ("B-F rows naming an A-Z headword", "SELECT COUNT(*) FROM appendix_head", None),
    ("events finished by their date",   "SELECT COUNT(*) FROM chronology_event WHERE reads_on", None),
    ("paragraphs continuing a range",   "SELECT COUNT(*) FROM citation_target WHERE NOT opens", None),
]

INVARIANTS = [
    # So a consumer of the API, which sends kind and separator_before, can find
    # each block of verse without a field of its own.
    ("a block of verse begins after prose or a separator, and only there",
     """SELECT COUNT(*) FROM (SELECT src, verse_start, sep_before, section_id,
           LAG(src) OVER (ORDER BY ord) AS prev, LAG(section_id) OVER (ORDER BY ord) AS psec
           FROM paragraph)
         WHERE src <> 'vs' AND verse_start IS NOT (prev IS NULL OR prev = 'vs'
           OR sep_before IS NOT NULL OR psec <> section_id)"""),
    ("a block's first line or a set-in line that is not verse",
     "SELECT COUNT(*) FROM paragraph WHERE (verse_start OR setoff) AND src = 'vs'"),
    ("the one heading in the text is 0:12.10",
     "SELECT COUNT(*) FROM paragraph WHERE heading AND ref <> '0:12.10'"),
    ("every span lies inside its paragraph",
     """SELECT COUNT(*) FROM span s JOIN paragraph p ON p.id = s.paragraph_id
         WHERE s.start < 0 OR s."end" > LENGTH(p.text)"""),
    ("no paragraph-precision citation is unresolved",
     "SELECT COUNT(*) FROM citation_target WHERE precision='para' AND paragraph_id IS NULL"),
    # A range stands once in the margin, beside its first paragraph
    # (queries.CHIP_OPENS): what continues one is the next paragraph of it.
    ("a paragraph continuing a range follows the one before, in its citation",
     """SELECT COUNT(*) FROM citation_target t WHERE NOT t.opens AND NOT EXISTS
         (SELECT 1 FROM citation_target u WHERE u.citation_id = t.citation_id
           AND u.para = t.para - 1)"""),
    ("only a paragraph continues a range",
     "SELECT COUNT(*) FROM citation_target WHERE NOT opens AND precision <> 'para'"),
    ("every See, See also and q.v. resolves by some route",
     "SELECT COUNT(*) FROM xref WHERE route IS NULL"),
    ("every q.v. is recorded as a cross-reference",
     """SELECT COUNT(*) FROM index_entry e WHERE e.qv = 1 AND NOT EXISTS
         (SELECT 1 FROM xref x WHERE x.entry_id = e.id AND x.kind = 'qv')"""),
    ("every q.v. names its headword with a link",
     """SELECT COUNT(*) FROM index_entry WHERE qv = 1
         AND text_html NOT LIKE '%<a class="hw" href="/i/%</a> <i>q.v.</i>'"""),
    ("every See and See also has its link",
     "SELECT COUNT(*) FROM xref WHERE kind IN ('see', 'seealso') AND href IS NULL"),
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
    # The section page splits a dot-leader row at its leader (section.html), and
    # each half is whole HTML only if no other span is open there.
    ("a dot leader inside another span, or two in a paragraph",
     """SELECT (SELECT COUNT(*) FROM span d JOIN span s ON s.paragraph_id = d.paragraph_id
                 WHERE d.kind = 'dotleader' AND s.kind NOT IN ('dotleader', 'fnref', 'shy')
                   AND s.start < d.start AND s."end" > d.start)
            + (SELECT COUNT(*) FROM (SELECT paragraph_id FROM span WHERE kind = 'dotleader'
                                      GROUP BY 1 HAVING COUNT(*) > 1))"""),
    # The study edition's notes, one reviewed paper at a time (build/study.py).
    ("study notes without their study_note row, or rows without their note",
     """SELECT (SELECT COUNT(*) FROM footnote f LEFT JOIN study_note s ON s.footnote_id = f.id
                 WHERE f.kind = 'study' AND s.footnote_id IS NULL)
            + (SELECT COUNT(*) FROM study_note s LEFT JOIN footnote f ON f.id = s.footnote_id
                 WHERE f.id IS NULL OR f.kind <> 'study')"""),
    ("a study note filed under another paper than its paragraph's",
     """SELECT COUNT(*) FROM study_note s JOIN footnote f ON f.id = s.footnote_id
         JOIN paragraph p ON p.id = f.paragraph_id WHERE p.paper_n <> s.paper_n"""),
    ("study notes not numbered 1.. in each paper in the order of the text",
     """SELECT COUNT(*) FROM (SELECT s.num, ROW_NUMBER() OVER (PARTITION BY s.paper_n
           ORDER BY p.ord, f.anchor, f.ord) AS rn
         FROM study_note s JOIN footnote f ON f.id = s.footnote_id
         JOIN paragraph p ON p.id = f.paragraph_id) WHERE num <> rn"""),
    ("a reviewed paper whose count of notes is not its notes'",
     """SELECT COUNT(*) FROM study_paper x
         WHERE n_notes <> (SELECT COUNT(*) FROM study_note s WHERE s.paper_n = x.paper_n)"""),
    ("a study source no note cites, or one cited from another paper",
     """SELECT (SELECT COUNT(*) FROM study_source x
                 WHERE NOT EXISTS (SELECT 1 FROM study_cite c WHERE c.source_id = x.id))
            + (SELECT COUNT(*) FROM study_cite c JOIN study_note s ON s.footnote_id = c.footnote_id
                 JOIN study_source x ON x.id = c.source_id WHERE x.paper_n <> s.paper_n)"""),
    ("a study source's page not https, or a work with two pages",
     """SELECT (SELECT COUNT(*) FROM study_source WHERE url NOT LIKE 'https://%')
            + (SELECT COUNT(*) FROM (SELECT key FROM study_source GROUP BY key
                 HAVING COUNT(DISTINCT COALESCE(url, '')) > 1))"""),
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
    # What the site shows of the index as words -- a headword, a chip, a See
    # target, a Chronology label -- has its HTML beside it, with an ordinal's
    # suffix superior: the same words, a chip in as many parts.
    m = soff = 0
    for where, text, h in con.execute(
            "SELECT 'headword ' || id, headword, headword_html FROM index_entry"
            "  WHERE headword IS NOT NULL"
            " UNION ALL SELECT 'chip ' || id, path_plain, path_html FROM index_entry"
            " UNION ALL SELECT 'xref ' || id, target, target_html FROM xref"
            " UNION ALL SELECT 'event ' || id, label, label_html FROM chronology_event"):
        m += 1
        if strip_tags(h) != text or h.count(" \u203a ") != text.count(" \u203a "):
            soff += 1
            if soff <= 5:
                print(f"            {where}: {h!r} is not {text!r}")
    print(f"            {m - soff}/{m} headwords, chips, targets and events round-trip"
          + ("" if not soff else f"   {soff} FAIL"))
    if soff:
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
    # A card's copies with the book's soft hyphens (footnote.html_hy,
    # srt_item.why_html_hy): the same HTML but for them, and each inside a word.
    import re
    k = hoff = 0
    for where, h, hy in con.execute(
            "SELECT 'note ' || id, html, html_hy FROM footnote"
            " UNION ALL SELECT 'SRT ' || name || ' ' || n, why_html, why_html_hy FROM srt_item"):
        k += 1
        plain = strip_tags(hy)
        if hy.replace("\u00ad", "") != h or re.search(r"(?<![A-Za-z])\u00ad|\u00ad(?![A-Za-z])", plain):
            hoff += 1
            if hoff <= 5:
                print(f"            {where}: its soft hyphens are not only the book's")
    print(f"            {k - hoff}/{k} notes and reasons hyphenated as the text is, and only so"
          + ("" if not hoff else f"   {hoff} FAIL"))
    if hoff:
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
    # An index citation may link a range, /48:6.2-4, which the page opens only
    # when both ends are there and it runs forwards.
    k = loff = 0
    for (h,) in con.execute("SELECT text_html FROM index_entry"):
        for to in re.findall(r'<a class="cit" href="/([^"]*)"', h):
            k += 1
            m = re.fullmatch(r"(\d+:\d+)\.(\d+)-(\d+)", to)
            if not (to in places if m is None else
                    f"{m[1]}.{m[2]}" in places and f"{m[1]}.{m[3]}" in places
                    and int(m[2]) < int(m[3])):
                loff += 1
                print(f"            index link to nowhere: /{to}")
    print(f"            {k - loff}/{k} index links into the book land"
          + ("" if not loff else f"   {loff} FAIL"))
    if loff:
        bad += 1
    # A Chronology event on one line (chronology_event.line_html) is its label
    # and then its printed citations, the very links of its line in Appendix A,
    # in order; so those links land too.
    cit = re.compile(r' <a class="cit" href="[^"]*">\([^<]*\)</a>')
    k = coff = 0
    for label, lh, h in con.execute(
            "SELECT v.label, v.line_html, e.text_html FROM chronology_event v"
            " JOIN index_entry e ON e.id = v.entry_id"):
        k += 1
        cites = cit.findall(h)
        if not cites or cit.findall(lh) != cites or strip_tags(lh) != label + strip_tags("".join(cites)):
            coff += 1
            if coff <= 5:
                print(f"            {label}: its line is not its label and its citations")
    print(f"            {k - coff}/{k} Chronology events on one line with their citations"
          + ("" if not coff else f"   {coff} FAIL"))
    if coff:
        bad += 1
    # A headword link -- a q.v., a See, an appendix name -- opens a concept
    # page, and one to a line of it names a line that page holds.
    under = {(s, a) for s, a in con.execute(
        "SELECT r.slug, e.anchor FROM index_entry e JOIN index_entry r ON r.id = e.root_id"
        " WHERE e.scope = 'az'")}
    slugs = {s for s, _ in under}
    k = hoff = 0
    for (h,) in con.execute("SELECT text_html FROM index_entry"):
        for s, a in re.findall(r'<a class="hw" href="/i/([^"#]*)(?:#([^"]*))?"', h):
            k += 1
            if s not in slugs or (a and (s, a) not in under):
                hoff += 1
                print(f"            headword link to nowhere: /i/{s}" + (f"#{a}" if a else ""))
    print(f"            {k - hoff}/{k} headword links in the index land"
          + ("" if not hoff else f"   {hoff} FAIL"))
    if hoff:
        bad += 1
    # Each See and See also is linked where it stands, in the order written,
    # by the link the concept page's Cross-references gives it.
    want: dict[int, list[str]] = {}
    for eid, target, href in con.execute(
            "SELECT entry_id, target_html, href FROM xref"
            " WHERE kind IN ('see', 'seealso') ORDER BY entry_id, ord"):
        want.setdefault(eid, []).append(f'<a class="hw" href="{href}">{target}</a>')
    k = woff = 0
    for eid, h in con.execute("SELECT id, text_html FROM index_entry"):
        if eid not in want:
            continue
        k += 1
        p = 0
        for link in want[eid]:
            p = h.find(link, p)
            if p < 0:
                break
            p += len(link)
        if p < 0:
            woff += 1
    print(f"            {k - woff}/{k} entries link each See where it stands"
          + ("" if not woff else f"   {woff} FAIL"))
    if woff:
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

    # Every stored fragment is well-formed XML, so that whatever reads it --
    # the API's sites among them -- may parse it as XML.  A browser forgives a
    # bare & or an unclosed <br>; an XML reader refuses the whole document.
    # (It began for the EPUB, retired on 2026-10-19.)
    import xml.etree.ElementTree as ET
    k = xoff = 0
    for where, h in con.execute(
            "SELECT 'paragraph ' || ref, html FROM paragraph"
            " UNION ALL SELECT 'hyphenated ' || ref, html_hy FROM paragraph"
            " UNION ALL SELECT 'note ' || id, html FROM footnote"
            " UNION ALL SELECT 'study source ' || paper_n || ' ' || key, html FROM study_source"
            " UNION ALL SELECT 'SRT ' || name, then_html || why_html FROM srt_item"
            " UNION ALL SELECT 'section ' || paper_n || ':' || n, title_html FROM section"
            "  WHERE title_html IS NOT NULL"
            " UNION ALL SELECT 'entry ' || id, text_html FROM index_entry"
            " UNION ALL SELECT 'headword ' || id, headword_html FROM index_entry"
            "  WHERE headword_html IS NOT NULL"
            " UNION ALL SELECT 'chip ' || id, path_html FROM index_entry"
            " UNION ALL SELECT 'xref ' || id, target_html FROM xref"
            " UNION ALL SELECT 'event ' || id, label_html FROM chronology_event"):
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
    bad += _study(con, places)

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


def _study(con, places: set[str]) -> int:
    """The study notes as the pages show them: each marker numbered as its
    note, standing after its words, its links landing, its text the edition's
    words set as TeX sets them."""
    import re

    from ..render import strip_tags

    bad = 0
    want = {k: n for k, n in con.execute("SELECT key, num FROM study_note")}
    marker = re.compile(r'<a class="fn" href="#fn(st[0-9_]+)" id="fnref\1" data-k="st"'
                        r' data-n="(\d+)"(?: data-hs="1")? aria-label="Note \2"></a>')
    got_html: dict[str, int] = {}
    got_hy: dict[str, int] = {}
    n_html = n_hy = 0
    for h, hy in con.execute("SELECT html, html_hy FROM paragraph WHERE html LIKE '%data-k=\"st\"%'"):
        n_html += h.count('data-k="st"')
        n_hy += hy.count('data-k="st"')
        got_html.update((k, int(n)) for k, n in marker.findall(h))
        got_hy.update((k, int(n)) for k, n in marker.findall(hy))
    ok = got_html == want == got_hy and n_html == n_hy == len(want)
    print(f"study:      {len(want)} notes, each marker numbered as its note"
          + ("" if ok else f"   FAIL: {n_html} markers, {len(got_html)} well formed, {len(want)} notes"))
    bad += not ok
    k = aoff = 0
    for ref, text, anchor, after in con.execute(
            "SELECT p.ref, p.text, f.anchor, s.after FROM study_note s"
            " JOIN footnote f ON f.id = s.footnote_id JOIN paragraph p ON p.id = f.paragraph_id"):
        k += 1
        if text[anchor - len(after):anchor] != after or text.count(after) != 1:
            aoff += 1
            print(f"            study note at {ref} is not after {after!r}")
    print(f"            {k - aoff}/{k} stand after the words they name, which occur once"
          + ("" if not aoff else f"   {aoff} FAIL"))
    bad += bool(aoff)
    k = loff = 0
    for (h,) in con.execute("SELECT f.html FROM footnote f WHERE f.kind = 'study'"
                            " UNION ALL SELECT html FROM study_source"):
        for to in re.findall(r'href="/([^"]*)"', h):
            k += 1
            m = re.fullmatch(r"(\d+:\d+)\.(\d+)-(\d+)", to)
            if not (to in places if m is None else
                    f"{m[1]}.{m[2]}" in places and f"{m[1]}.{m[3]}" in places
                    and int(m[2]) < int(m[3])):
                loff += 1
                print(f"            study link to nowhere: /{to}")
    print(f"            {k - loff}/{k} links in the study notes land"
          + ("" if not loff else f"   {loff} FAIL"))
    bad += bool(loff)
    k = coff = 0
    for where, text, h in con.execute(
            "SELECT 'note ' || s.key, f.text, f.html FROM study_note s JOIN footnote f"
            " ON f.id = s.footnote_id"
            " UNION ALL SELECT 'source ' || paper_n || ' ' || key, text, html FROM study_source"):
        k += 1
        odd = sorted({c for c in text if c in "`'\"" or 0xE000 <= ord(c) <= 0xF8FF})
        if odd or strip_tags(h) != text:
            coff += 1
            print(f"            study {where}: {odd or 'does not round-trip'}")
    print(f"            {k - coff}/{k} notes and sources round-trip, with TeX's quotes set"
          + ("" if not coff else f"   {coff} FAIL"))
    bad += bool(coff)
    return bad


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
    before = {ref: (sep, bool(gap), kind, bool(setoff)) for ref, sep, gap, kind, setoff in con.execute(
        "SELECT ref, sep_before, gap_before, CASE WHEN heading THEN 'heading'"
        " WHEN src = 'vs' THEN 'prose' ELSE 'verse' END, setoff FROM paragraph")}
    # Each 1955 reading: an empty marker at its note's offset, its reading in
    # readings_1955, in the same order (build/versions.py).
    readings = {}
    for ref, anchor, html in con.execute(
            "SELECT p.ref, f.anchor, f.html FROM footnote f JOIN paragraph p ON p.id = f.paragraph_id"
            " WHERE f.kind = 'variant-1955' ORDER BY p.ref, f.anchor, f.ord"):
        readings.setdefault(ref, []).append((anchor, html))
    mark = '<span class="v1955"></span>'
    marks = 0
    n = off = 0
    for kind, key, body, h in con.execute("SELECT kind, key, body, hash FROM text_unit"):
        n += 1
        rec = json.loads(body)
        ok = rec.pop("hash") == h == versions.digest(rec)
        if kind == "paragraph":
            ok = (ok and rec["ref"] == key and strip_tags(rec["html"]) == texts.get(key)
                  and 'class="fn"' not in rec["html"]
                  and (rec.get("separator_before", "?"), rec.get("group_before"),
                       rec.get("kind"), rec.get("setoff")) == before.get(key))
            notes = readings.get(key, [])
            pieces = rec["html"].split(mark)
            marks += len(pieces) - 1
            ok = (ok and rec.get("readings_1955") == [r for _, r in notes]
                  and len(pieces) - 1 == len(notes)
                  and all(len(strip_tags(mark.join(pieces[:i + 1]).replace(mark, ""))) == a
                          for i, (a, _) in enumerate(notes)))
        if not ok:
            off += 1
            if off <= 5:
                print(f"            text API record wrong: {kind} {key}")
    print(f"text API:   {n - off}/{n} records hash true, and every paragraph's HTML strips to its text,"
          f" with how the book sets it, and {marks} 1955 readings each in its place"
          + ("" if not off else f"   {off} FAIL"))
    nreadings = sum(len(v) for v in readings.values())
    if off or got != want or marks != nreadings:
        bad += 1
        if got != want:
            print(f"            records {got}, expected one for each of {want}   FAIL")
        if marks != nreadings:
            print(f"            {marks} 1955 markers sent, for {nreadings} readings   FAIL")

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
