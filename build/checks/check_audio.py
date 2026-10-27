"""Gate the recordings: every section can be heard, and every segment is sound.

The checks that matter most are structural, as with the text.  Within each
file the segments must tile it exactly -- starting at 0, each beginning where
the last ended, the last ending at the file's end -- so a paragraph can never
be skipped or heard twice, and a boundary the aligner misplaced shows up as a
gap or an overlap rather than as a reader starting mid-sentence.
"""

from __future__ import annotations

QUERIES = [
    # 1,629 files: 1,626 sections, the Acknowledgment's own track (P000_13),
    # and two second encodes excluded by name in data/audio/mh-overrides.tsv.
    ("mh files used",       "SELECT COUNT(*) FROM audio_file f JOIN audio_source s"
                            " ON s.id=f.source_id WHERE s.key='mh'", 1627),
    ("mh hours",            "SELECT CAST(SUM(duration_ms)/3600000.0 AS INT) FROM audio_file f"
                            " JOIN audio_source s ON s.id=f.source_id WHERE s.key='mh'", 121),
    ("mh segments",         "SELECT COUNT(*) FROM audio_segment g JOIN audio_source s"
                            " ON s.id=g.source_id WHERE s.key='mh'", None),
    # One spoken heading per section, and every paragraph.
    ("speech units",        "SELECT COUNT(*) FROM speech", 1626 + 14586),
    # The AI voice, once made: a file per section, a segment per speech unit
    # (the invariants below require every section and paragraph of it).
    ("ai files",            "SELECT COUNT(*) FROM audio_file f JOIN audio_source s"
                            " ON s.id=f.source_id WHERE s.key='ai'", None),
    ("ai hours",            "SELECT CAST(COALESCE(SUM(duration_ms), 0)/3600000.0 AS INT) FROM audio_file f"
                            " JOIN audio_source s ON s.id=f.source_id WHERE s.key='ai'", None),
]

INVARIANTS = [
    ("every section can be heard, in every voice",
     """SELECT COUNT(*) FROM section x CROSS JOIN audio_source s
         WHERE NOT EXISTS (SELECT 1 FROM audio_segment g
                            WHERE g.section_id = x.id AND g.source_id = s.id)"""),
    ("every paragraph has its segment, where a voice is aligned",
     """SELECT COUNT(*) FROM paragraph p CROSS JOIN audio_source s
         WHERE s.granularity = 'paragraph'
           AND NOT EXISTS (SELECT 1 FROM audio_segment g
                            WHERE g.paragraph_id = p.id AND g.source_id = s.id)
           AND NOT EXISTS (SELECT 1 FROM audio_unread u
                            WHERE u.paragraph_id = p.id AND u.source_id = s.id)"""),
    ("a paragraph on record as unread has no segment",
     """SELECT COUNT(*) FROM audio_unread u JOIN audio_segment g
           ON g.paragraph_id = u.paragraph_id AND g.source_id = u.source_id"""),
    # A good reader keeps a steady pace: Merritt Horn's median is 2.4 words a
    # second, and 98% of paragraphs fall between 1.7 and 2.9.  Outside 1.0-4.0,
    # a segment holds too much or too little -- a misplaced cut -- unless it is
    # a known difference between the reading and the text.
    ("paragraphs of 15+ words read at 1.0-4.0 words a second",
     """SELECT COUNT(*) FROM audio_segment g JOIN paragraph p ON p.id = g.paragraph_id
         JOIN audio_source s ON s.id = g.source_id
         WHERE p.word_count >= 15 AND (s.kind = 'synthetic' OR g.match >= 0.6)
           AND (p.word_count * 1000.0 / (g.end_ms - g.start_ms) NOT BETWEEN 1.0 AND 4.0)"""),
    # A synthetic reading is of the spoken text as it was when it was made.
    # If the text has changed since -- a correction upstream, a change to
    # build/speech.py -- the voice reads words the page no longer says, and
    # `make tts` must make that paragraph again.
    ("an AI reading is of the spoken text as it is now",
     """SELECT COUNT(*) FROM audio_segment g JOIN audio_source s ON s.id = g.source_id
         LEFT JOIN speech x ON x.section_id = g.section_id AND x.paragraph_id IS g.paragraph_id
         WHERE s.kind = 'synthetic' AND (x.sha IS NULL OR g.speech_sha IS NOT x.sha)"""),
    ("a segment's paragraph is in the segment's section",
     """SELECT COUNT(*) FROM audio_segment g JOIN paragraph p ON p.id = g.paragraph_id
         WHERE p.section_id <> g.section_id"""),
    ("no more than one heading per section and voice",
     """SELECT COUNT(*) FROM (SELECT 1 FROM audio_segment WHERE paragraph_id IS NULL
         GROUP BY source_id, section_id HAVING COUNT(*) > 1)"""),
    # The tiling.  LAG over each file in time order: the first segment starts
    # at 0, every other starts where its predecessor ended.
    ("segments tile each file: no gap, no overlap",
     """SELECT COUNT(*) FROM (
          SELECT start_ms, LAG(end_ms, 1, 0) OVER (PARTITION BY file_id ORDER BY start_ms) AS prev
            FROM audio_segment) WHERE start_ms <> prev"""),
    # A file may run on after its last paragraph -- into silence, or, in
    # P105_05, into a second reading of 105:6 -- and that tail is nobody's.
    # But no segment may run past the end of its file.
    ("no segment runs past its file's end",
     """SELECT COUNT(*) FROM audio_segment g JOIN audio_file f ON f.id = g.file_id
         WHERE g.end_ms > f.duration_ms"""),
    # Playing order is reading order: a section's segments are consecutive in
    # `ord`, and their paragraphs ascend with it.
    ("playing order follows reading order",
     """SELECT COUNT(*) FROM (
          SELECT g.ord, p.ord AS pord,
                 LAG(p.ord) OVER (PARTITION BY g.source_id ORDER BY g.ord) AS prev
            FROM audio_segment g JOIN paragraph p ON p.id = g.paragraph_id)
         WHERE prev IS NOT NULL AND pord <= prev"""),
    ("a heading plays before its section's paragraphs",
     """SELECT COUNT(*) FROM audio_segment h JOIN audio_segment g
           ON g.source_id = h.source_id AND g.section_id = h.section_id
         WHERE h.paragraph_id IS NULL AND g.paragraph_id IS NOT NULL AND g.ord < h.ord"""),
]


def low_match(con, report_to=print) -> int:
    """The paragraphs whose reading differs from the text must be exactly the
    set data/audio/mh-low-match.tsv records: a new one fails, and so does one
    that has silently gone (the rule of tests/known-oracle-deltas.tsv)."""
    import pathlib
    from ..audio import LOW_MATCH, LOW_WORDS
    tsv = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "audio" / "mh-low-match.tsv"
    known = {l.split("\t")[0] for l in tsv.read_text().splitlines() if l[:1].isdigit()} \
        if tsv.exists() else set()
    found = {r for (r,) in con.execute(
        "SELECT p.ref FROM audio_segment g JOIN paragraph p ON p.id = g.paragraph_id"
        " JOIN audio_source s ON s.id = g.source_id"
        " WHERE s.key = 'mh' AND p.word_count >= ? AND g.match < ?", (LOW_WORDS, LOW_MATCH))}
    new, gone = sorted(found - known), sorted(known - found)
    report_to(f"  {'reading differs from the text: exactly mh-low-match.tsv':56} "
              f"{len(found)} found, {len(known)} known"
              + ("" if not (new or gone) else f"   FAIL  new {new[:6]}  gone {gone[:6]}"))
    return bool(new or gone)


def run(con) -> int:
    from ..speech import ALLOWED
    bad = 0
    try:
        con.execute("SELECT 1 FROM audio_source").fetchall()
    except Exception:                                   # noqa: BLE001
        print("  no audio tables -- a database from before 005_audio.sql   FAIL")
        return 1
    for key, label, gran, rev in con.execute(
            "SELECT key, label, granularity, revision FROM audio_source ORDER BY id"):
        print(f"  {key:4} {label:16} by {gran}" + (f"   ({rev})" if rev else ""))
    print("counts")
    for name, q, expect in QUERIES:
        got = con.execute(q).fetchone()[0]
        mark = ""
        if expect is not None:
            mark = "  OK" if got == expect else f"  EXPECTED {expect:,}"
            bad += got != expect
        print(f"  {name:24} {got:>9,}{mark}")
    print("\ninvariants (all must be 0)")
    for name, q in INVARIANTS:
        got = con.execute(q).fetchone()[0]
        bad += bool(got)
        print(f"  {name:56} {got}{'' if not got else '   FAIL'}")
    if con.execute("SELECT granularity FROM audio_source WHERE key='mh'").fetchone() == ("paragraph",):
        bad += low_match(con)
        tails = con.execute(
            "SELECT f.name, (f.duration_ms - MAX(g.end_ms)) / 1000.0 AS t FROM audio_file f"
            " JOIN audio_segment g ON g.file_id = f.id GROUP BY f.id HAVING t > 10"
            " ORDER BY t DESC").fetchall()
        print(f"  {'files that run on 10 s past their last paragraph':56} {len(tails)}   (shown, not failed)")
        for name, t in tails[:8]:
            print(f"      {name:28} {t:6.1f} s")
    # The spoken text: a voice must never be left to guess at a digit or a
    # symbol.  ALLOWED is the whole alphabet it may meet (build/speech.py).
    odd = [(r, t) for r, t in con.execute(
        "SELECT COALESCE(p.ref, x.paper_n || ':' || x.n), s.text FROM speech s"
        " JOIN section x ON x.id = s.section_id LEFT JOIN paragraph p ON p.id = s.paragraph_id")
        if not ALLOWED.match(t)]
    bad += bool(odd)
    print(f"  {'nothing but words and punctuation in the spoken text':56} {len(odd)}"
          f"{'' if not odd else '   FAIL'}")
    for ref, t in odd[:8]:
        print(f"      {ref:10} {sorted(set(c for c in t if not ALLOWED.match(c)))}  {t[:70]!r}")
    bad += translations(con)
    return 1 if bad else 0


# The translations' spoken text (build/speech.py derive_tr), which the browser's
# voice reads: every paragraph a translation has, in its section, at most one
# heading to a section, and nothing in it but its language's words, digits and
# punctuation (speech.ALLOWED_TR).
TR_INVARIANTS = [
    ("every translated paragraph has its spoken text",
     """SELECT COUNT(*) FROM tr_paragraph t LEFT JOIN tr_speech x
           ON x.translation = t.translation AND x.paragraph_id = t.paragraph_id
         WHERE x.id IS NULL"""),
    ("a spoken paragraph is one the translation has",
     """SELECT COUNT(*) FROM tr_speech x LEFT JOIN tr_paragraph t
           ON t.translation = x.translation AND t.paragraph_id = x.paragraph_id
         WHERE x.paragraph_id IS NOT NULL AND t.id IS NULL"""),
    ("a spoken paragraph is in its row's section",
     """SELECT COUNT(*) FROM tr_speech x JOIN paragraph p ON p.id = x.paragraph_id
         WHERE p.section_id <> x.section_id"""),
    ("a spoken heading is over a section the translation has",
     """SELECT COUNT(*) FROM tr_speech x WHERE x.paragraph_id IS NULL AND NOT EXISTS (
          SELECT 1 FROM tr_speech y WHERE y.translation = x.translation
             AND y.section_id = x.section_id AND y.paragraph_id IS NOT NULL)"""),
    ("no more than one spoken heading per section and translation",
     """SELECT COUNT(*) FROM (SELECT 1 FROM tr_speech WHERE paragraph_id IS NULL
         GROUP BY translation, section_id HAVING COUNT(*) > 1)"""),
]


def translations(con) -> int:
    from ..speech import ALLOWED_TR
    try:
        rows = con.execute("SELECT key, lang FROM translation ORDER BY ord").fetchall()
        con.execute("SELECT 1 FROM tr_speech").fetchone()
    except Exception:                                   # noqa: BLE001
        print("  no tr_speech -- a database from before the translations were spoken   FAIL")
        return 1
    bad = 0
    print("\nthe translations, spoken (all must be 0)")
    for key, lang in rows:
        n, h = con.execute("SELECT COUNT(paragraph_id), SUM(paragraph_id IS NULL) FROM tr_speech"
                           " WHERE translation = ?", (key,)).fetchone()
        print(f"  {key:12} {n:>9,} paragraphs, {h or 0:,} headings")
    for name, q in TR_INVARIANTS:
        got = con.execute(q).fetchone()[0]
        bad += bool(got)
        print(f"  {name:56} {got}{'' if not got else '   FAIL'}")
    odd = []
    for key, lang in rows:
        ok = ALLOWED_TR.get(lang)
        odd += [(key, ok, r, t) for r, t in con.execute(
            "SELECT COALESCE(p.ref, s.paper_n || ':' || s.n), x.text FROM tr_speech x"
            " JOIN section s ON s.id = x.section_id LEFT JOIN paragraph p ON p.id = x.paragraph_id"
            " WHERE x.translation = ?", (key,)) if not ok or not ok.match(t)]
    bad += bool(odd)
    print(f"  {'nothing but words, digits and punctuation in them':56} {len(odd)}"
          f"{'' if not odd else '   FAIL'}")
    for key, ok, ref, t in odd[:8]:
        print(f"      {key} {ref:10} {sorted(set(c for c in t if not ok or not ok.match(c)))}  {t[:70]!r}")
    return bad
