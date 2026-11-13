"""Gate the recordings: every section can be heard, and every segment is sound.

The checks that matter most are structural, as with the text.  Within each
file the segments must tile it exactly -- starting at 0, each beginning where
the last ended, the last ending at the file's end -- so a paragraph can never
be skipped or heard twice, and a boundary the aligner misplaced shows up as a
gap or an overlap rather than as a reader starting mid-sentence.
"""

from __future__ import annotations

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

QUERIES = [
    # One spoken heading per section, and every paragraph.
    ("speech units",        "SELECT COUNT(*) FROM speech", 1626 + 14586),
]
# Each voice's own: what verify/expectations.toml's [audio.<key>] says of it
# (`files`, `hours`), where it says anything; a voice it does not name, the AI
# voice until it is made, is counted and not held.
PER_VOICE = [
    ("files used", "files", "SELECT COUNT(*) FROM audio_file WHERE source_id = ?"),
    ("hours",      "hours", "SELECT CAST(ROUND(COALESCE(SUM(duration_ms), 0) / 3600000.0) AS INT)"
                            " FROM audio_file WHERE source_id = ?"),
    ("segments",   None,    "SELECT COUNT(*) FROM audio_segment WHERE source_id = ?"),
]
# The words of the paragraph a segment reads, in the text its voice reads: the
# English's, or the translation's, counted by its spaces.
WORDS_TR = "(LENGTH(t.text) - LENGTH(REPLACE(t.text, ' ', '')) + 1)"

INVARIANTS = [
    # A translation's reading owes what that translation has: every section
    # it has a paragraph of, and each of those paragraphs.  A section with no
    # segment is one whose every paragraph is on the record as unread, and no
    # other: Григорий Войнер's has no 19:0 and no 50:0 (voyner-unread.tsv).
    ("every section can be heard, in every voice, but one on record as unread",
     """SELECT COUNT(*) FROM section x CROSS JOIN audio_source s
         WHERE NOT EXISTS (SELECT 1 FROM audio_segment g
                            WHERE g.section_id = x.id AND g.source_id = s.id)
           AND EXISTS (SELECT 1 FROM paragraph p
                        WHERE p.section_id = x.id
                          AND (s.translation IS NULL OR EXISTS (
                                 SELECT 1 FROM tr_paragraph t
                                  WHERE t.translation = s.translation AND t.paragraph_id = p.id))
                          AND NOT EXISTS (SELECT 1 FROM audio_unread u
                                           WHERE u.paragraph_id = p.id AND u.source_id = s.id))"""),
    # A file sent with an Info frame (build/mp3.py) is listed with the length
    # that frame gives a player, to the millisecond: the cuts were made on it.
    ("a file's Info frame says the length listed for it",
     """SELECT COUNT(*) FROM audio_file WHERE head IS NOT NULL AND (
          substr(head, 1, 1) <> x'FF' OR instr(head, CAST('Info' AS BLOB)) = 0 OR head_at < 0
          OR head_at > bytes)"""),
    ("every paragraph has its segment, where a voice is aligned",
     """SELECT COUNT(*) FROM paragraph p CROSS JOIN audio_source s
         WHERE s.granularity = 'paragraph'
           AND NOT EXISTS (SELECT 1 FROM audio_segment g
                            WHERE g.paragraph_id = p.id AND g.source_id = s.id)
           AND NOT EXISTS (SELECT 1 FROM audio_unread u
                            WHERE u.paragraph_id = p.id AND u.source_id = s.id)
           AND (s.translation IS NULL OR EXISTS (
                  SELECT 1 FROM tr_paragraph t
                   WHERE t.translation = s.translation AND t.paragraph_id = p.id))"""),
    ("a translation's reading has no paragraph that translation lacks",
     """SELECT COUNT(*) FROM audio_segment g JOIN audio_source s ON s.id = g.source_id
         WHERE s.translation IS NOT NULL AND g.paragraph_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM tr_paragraph t
                            WHERE t.translation = s.translation AND t.paragraph_id = g.paragraph_id)"""),
    ("a paragraph on record as unread has no segment",
     """SELECT COUNT(*) FROM audio_unread u JOIN audio_segment g
           ON g.paragraph_id = u.paragraph_id AND g.source_id = u.source_id"""),
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


def expected() -> dict:
    """verify/expectations.toml's [audio.<key>], by key."""
    with open(ROOT / "verify" / "expectations.toml", "rb") as fh:
        return tomllib.load(fh).get("audio", {})


def _words(translation):
    """(the join that reaches the paragraph a segment reads, its word count),
    in the text the voice reads."""
    if translation:
        return ("JOIN tr_paragraph t ON t.paragraph_id = g.paragraph_id AND t.translation = :tr"
                " JOIN paragraph p ON p.id = g.paragraph_id", WORDS_TR)
    return "JOIN paragraph p ON p.id = g.paragraph_id", "p.word_count"


def pace(con, source_id: int, key: str, kind: str, translation, band, report_to=print) -> int:
    """A good reader keeps a steady pace: Merritt Horn's median is 2.4 words a
    second, and 98% of paragraphs fall between 1.7 and 2.9.  Outside the band
    expectations.toml gives the voice (1.0-4.0 with none), a segment holds too
    much or too little -- a misplaced cut -- unless it is a known difference
    between the reading and the text.  The words are those of the text read: a
    Russian word is longer than an English one, and a Russian reading's band
    is its own."""
    lo, hi = band or (1.0, 4.0)
    join, words = _words(translation)
    got = con.execute(
        f"SELECT COUNT(*) FROM audio_segment g {join}"
        f" WHERE g.source_id = :id AND {words} >= 15 AND (:kind = 'synthetic' OR g.match >= 0.6)"
        f"   AND ({words} * 1000.0 / (g.end_ms - g.start_ms) NOT BETWEEN :lo AND :hi)",
        {"id": source_id, "tr": translation, "kind": kind, "lo": lo, "hi": hi}).fetchone()[0]
    name = f"{key}: paragraphs of 15+ words read at {lo}-{hi} words a second"
    report_to(f"  {name:56} {got}{'' if not got else '   FAIL'}")
    if got:
        for ref, w, ms in con.execute(
                f"SELECT p.ref, {words}, g.end_ms - g.start_ms FROM audio_segment g {join}"
                f" WHERE g.source_id = :id AND {words} >= 15 AND (:kind = 'synthetic' OR g.match >= 0.6)"
                f"   AND ({words} * 1000.0 / (g.end_ms - g.start_ms) NOT BETWEEN :lo AND :hi)"
                " ORDER BY p.id LIMIT 8",
                {"id": source_id, "tr": translation, "kind": kind, "lo": lo, "hi": hi}):
            report_to(f"      {ref:10} {w} words in {ms / 1000:.1f} s")
    return bool(got)


def low_match(con, source_id: int, key: str, translation, report_to=print) -> int:
    """The paragraphs whose reading differs from the text must be exactly the
    set data/audio/<key>-low-match.tsv records: a new one fails, and so does
    one that has silently gone (the rule of tests/known-oracle-deltas.tsv)."""
    from ..audio import LOW_MATCH, LOW_WORDS
    tsv = ROOT / "data" / "audio" / f"{key}-low-match.tsv"
    known = {l.split("\t")[0] for l in tsv.read_text().splitlines() if l[:1].isdigit()} \
        if tsv.exists() else set()
    join, words = _words(translation)
    found = {r for (r,) in con.execute(
        f"SELECT p.ref FROM audio_segment g {join}"
        f" WHERE g.source_id = :id AND {words} >= :w AND g.match < :m",
        {"id": source_id, "tr": translation, "w": LOW_WORDS, "m": LOW_MATCH})}
    new, gone = sorted(found - known), sorted(known - found)
    report_to(f"  {f'{key}: reading differs from the text: exactly {key}-low-match.tsv':56} "
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
    voices = con.execute("SELECT id, key, label, kind, granularity, revision, translation"
                         " FROM audio_source ORDER BY id").fetchall()
    for _id, key, label, _kind, gran, rev, tr in voices:
        print(f"  {key:6} {label:16} by {gran}" + (f", of {tr}" if tr else "")
              + (f"   ({rev})" if rev else ""))
    print("counts")
    want = expected()
    for name, q, expect in QUERIES:
        got = con.execute(q).fetchone()[0]
        mark = ""
        if expect is not None:
            mark = "  OK" if got == expect else f"  EXPECTED {expect:,}"
            bad += got != expect
        print(f"  {name:24} {got:>9,}{mark}")
    for sid, key, *_ in voices:
        for name, field, q in PER_VOICE:
            got = con.execute(q, (sid,)).fetchone()[0]
            expect = want.get(key, {}).get(field) if field else None
            mark = ""
            if expect is not None:
                mark = "  OK" if got == expect else f"  EXPECTED {expect:,}"
                bad += got != expect
            print(f"  {key + ' ' + name:24} {got:>9,}{mark}")
    # A voice expectations.toml names must be there: a reading dropped from
    # the config would otherwise pass by being counted nowhere.
    for key in sorted(set(want) - {v[1] for v in voices}):
        bad += 1
        print(f"  {key + ' files used':24} {'none':>9}  EXPECTED {want[key].get('files', 0):,}")
    print("\ninvariants (all must be 0)")
    for name, q in INVARIANTS:
        got = con.execute(q).fetchone()[0]
        bad += bool(got)
        print(f"  {name:56} {got}{'' if not got else '   FAIL'}")
    for sid, key, _label, kind, gran, _rev, tr in voices:
        if gran != "paragraph":
            continue
        bad += pace(con, sid, key, kind, tr, want.get(key, {}).get("pace"))
        if kind != "human":
            continue
        bad += low_match(con, sid, key, tr)
        tails = con.execute(
            "SELECT f.name, (f.duration_ms - MAX(g.end_ms)) / 1000.0 AS t FROM audio_file f"
            " JOIN audio_segment g ON g.file_id = f.id WHERE f.source_id = ?"
            " GROUP BY f.id HAVING t > 10 ORDER BY t DESC", (sid,)).fetchall()
        print(f"  {f'{key}: files that run on 10 s past their last paragraph':56} {len(tails)}   (shown, not failed)")
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
