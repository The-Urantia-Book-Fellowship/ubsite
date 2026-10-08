"""Merritt Horn's reading, cut at the paragraph: data/audio/mh.tsv.

    .venv/bin/python -m tools.align.align            # all files transcribed so far
    .venv/bin/python -m tools.align.align P001_01    # one, verbosely

The cheap half of the alignment; tools/align/transcribe.py is the expensive
one.  For each recording:

1.  What it holds comes from build/audio.py -- the spoken heading and the
    paragraphs, in order -- so the build and this cannot disagree.
2.  Whisper's words and ours are matched by difflib, as token sequences.  The
    matching is monotone by construction: a paragraph can never be found
    before the one it follows.
3.  Each boundary lies between the last word heard of one unit and the first
    of the next, and a reader pauses between paragraphs, so the cut goes into
    the longest silence in that window (ffmpeg silencedetect): a paragraph
    never starts mid-breath.  Whisper is good to a tenth of a second or so,
    except at a long pause, where it starts the first word too EARLY -- it
    put 0:1.1's "The" at 2.74 s with the pause running to 4.7 s.  So the
    window's end is the unit's SECOND word heard.  The cut is the middle of
    the pause, or 0.4 s before the voice resumes if that is later: a click on
    a paragraph should not start with a second of silence.
4.  Each unit's `match` is the share of its words that were heard.  A low one
    marks where the reading and today's text differ -- a correction made since
    the recording, or a word Whisper could not make out.

Runs under the site's own venv: stdlib and ffmpeg.  Reads var/ub.db, the
transcripts in var/align/mh/, and the recordings (through ffmpeg); writes
data/audio/mh.tsv and the silence cache in var/align/silence/.
"""

from __future__ import annotations

import concurrent.futures
import difflib
import json
import re
import sqlite3
import subprocess
import sys
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
WORDS = ROOT / "var" / "align" / "mh"
SILENCE = ROOT / "var" / "align" / "silence"
OUT = ROOT / "data" / "audio" / "mh.tsv"
# A pause, to the ear: 0.15 s below -38 dB.  The recordings sit at about -21 dB
# RMS; a breath between sentences is around 0.3 s, between paragraphs longer.
NOISE, MIN_SIL = "-38dB", 0.15
SLACK = 0.35          # seconds either side of Whisper's times to look for the pause
LEAD = 0.4            # at most this much silence before a paragraph's first word
TAIL = 3.0            # more than this after a file's last word is a tail, not the paragraph's
# Where the reading and today's text differ: build/audio.py's LOW_WORDS and
# LOW_MATCH, shared with the gate that holds the set to mh-low-match.tsv.

RE_SPLIT = re.compile(r"[\s—–/]+")
RE_STRIP = re.compile(r"[^a-z0-9']+")


def canon(t: str) -> str:
    """One spelling for both sides: Whisper writes 'counsellor', 'centre', and
    hears the Foreword as 'Forward'."""
    if t == "foreword":
        return "forward"
    t = t.replace("ll", "l")
    t = re.sub(r"our(s?)$", r"or\1", t)
    t = re.sub(r"tre(s?)$", r"ter\1", t)
    return t.replace("ement", "ment").replace("'", "")


def tokens(text: str) -> list[str]:
    out = []
    for w in RE_SPLIT.split(text.lower().replace("’", "'").replace("‘", "'")):
        for part in w.split("-"):
            t = RE_STRIP.sub("", part).strip("'")
            if t:
                out.append(canon(t))
    return out


def heard(words) -> tuple[list[str], list[tuple[float, float]]]:
    """Whisper's words as tokens, each with its time.  A word Whisper begins
    with a hyphen ('Super -Universes') continues the one before it; one with a
    digit in it is spoken as the build speaks the text's numbers."""
    from build.speech import speak
    toks, times = [], []
    for start, end, word, _p in words:
        if any(c.isdigit() for c in word):
            try:
                word = speak(word)
            except ValueError:
                pass
        if word.startswith("-") and toks:
            t = tokens(word)
            if t:
                toks[-1] += t[0]
                times[-1] = (times[-1][0], end)
                for x in t[1:]:
                    toks.append(x)
                    times.append((start, end))
            continue
        for x in tokens(word):
            toks.append(x)
            times.append((start, end))
    return toks, times


def silences(path: pathlib.Path, stem: str) -> list[tuple[float, float]]:
    cache = SILENCE / f"{stem}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text())]
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", str(path),
                          "-af", f"silencedetect=noise={NOISE}:d={MIN_SIL}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    out, start = [], None
    for line in err.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    cache.write_text(json.dumps(out))
    return out


def merged(sil, gap: float = 0.08) -> list[tuple[float, float]]:
    """silencedetect splits one long pause into abutting pieces; rejoin them."""
    out = []
    for s, e in sil:
        if out and s - out[-1][1] < gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def unit_text(con, ref: str) -> str:
    """What is spoken for a unit: the build's spoken text (build/speech.py), the
    same words a synthetic voice reads -- numbers in words, the heading as he
    reads it, "Two. The Reality of God."  Whisper's own digits go through the
    same speak(), so "1934" and "nineteen thirty-four" meet as equals."""
    if "." in ref:
        return con.execute("SELECT s.text FROM speech s JOIN paragraph p"
                           " ON p.id = s.paragraph_id WHERE p.ref=?", (ref,)).fetchone()[0]
    p, n = map(int, ref.split(":"))
    return con.execute("SELECT s.text FROM speech s JOIN section x ON x.id = s.section_id"
                       " WHERE s.paragraph_id IS NULL AND x.paper_n=? AND x.n=?",
                       (p, n)).fetchone()[0]


def align(con, name: str, units: list[str], words, duration: float, sil) -> list[tuple]:
    """[(ref, start_s, end_s, match)] for one file."""
    hyp, times = heard(words)
    ref, owner = [], []
    for u, r in enumerate(units):
        t = tokens(unit_text(con, r))
        ref += t
        owner += [u] * len(t)
    # Whisper's spelling of a coined name -- "Supernophim", "Nevadon" -- is
    # mapped to the closest word of this file's text, when it is close.
    vocab = set(ref)
    near = {}
    for t in set(hyp) - vocab:
        m = difflib.get_close_matches(t, vocab, n=1, cutoff=0.75)
        if m and len(t) >= 4:
            near[t] = m[0]
    hyp = [near.get(t, t) for t in hyp]
    sm = difflib.SequenceMatcher(None, hyp, ref, autojunk=False)
    hit = {}                                        # ref token -> hyp token
    for a, b, size in sm.get_matching_blocks():
        for i in range(size):
            hit[b + i] = a + i
    n = len(units)
    total = [0] * n
    got = [0] * n
    first = [None] * n                              # where each unit is surely under way
    early = [None] * n                              # its first word heard, as Whisper times it
    firstend = [None] * n                           # ... and where that word ends
    last = [None] * n
    seen = [[] for _ in range(n)]                   # (token index in unit, start time)
    lastidx = [None] * n                            # the last word heard, by index in its unit
    for j, u in enumerate(owner):
        if j in hit:
            got[u] += 1
            s, e = times[hit[j]]
            if firstend[u] is None:
                firstend[u] = e
            seen[u].append((total[u], s))
            last[u] = e
            lastidx[u] = total[u]
        total[u] += 1
    for u in range(n):
        if seen[u]:
            early[u] = seen[u][0][1]
            # The second word heard, when it comes early in the unit: the first
            # is the one Whisper misplaces after a pause.
            first[u] = seen[u][1][1] if len(seen[u]) > 1 and seen[u][1][0] < 4 else seen[u][0][1]
    sil = merged(sil)
    # Boundary k separates unit k-1 from unit k.  Its window runs from the
    # last word heard in units < k to the first heard in units >= k.  A unit
    # nobody heard shares its window with its neighbour; the window is then
    # divided by word count before the cut is moved into a pause.
    cuts = [0.0]
    k = 1
    while k < n:
        lo = max((last[u] for u in range(k) if last[u] is not None), default=0.0)
        m = k
        while m < n and first[m] is None:
            m += 1                                  # units k..m-1 unheard
        hi = first[m] if m < n else duration
        lo, hi = min(lo, hi), max(lo, hi)
        if m == k:                                  # the usual case: one cut
            # With no pause in the window -- a table row read straight on, or a
            # paragraph run into the next -- cut just before the first word.
            guess = (lo + max(lo, min(early[k], hi))) / 2
            # Never after the unit's first word heard has ended.  In 138:10.9
            # a breath filled the pause before "Eight." and the pause after it
            # won, so a click there began "Simon Zelotes" without its number.
            cap = firstend[k] if firstend[k] is not None and firstend[k] > lo else None
            cuts.append(pause(sil, lo - SLACK, hi + SLACK, min(guess, cap or guess), cuts[-1], cap))
            k += 1
            continue
        # Units k..m-1 unheard: cuts k..m (to n-1 at the file's end), placed
        # in proportion to their words, each moved to a pause near its place.
        span = list(range(k, min(m, n - 1) + 1))
        whole = sum(total[k:m]) or 1
        reach = max(SLACK, (hi - lo) / (2 * len(span)))
        for u in span:
            guess = lo + (hi - lo) * sum(total[k:u]) / whole
            cuts.append(pause(sil, guess - reach, guess + reach, guess, cuts[-1]))
        k = span[-1] + 1
    # The file's end, or shortly after its last paragraph's last word.  A file
    # may run on: P130_08 into 40 s of silence, P105_05 into a second reading
    # of all of 105:6.  That tail belongs to no paragraph, and the player moves
    # on when the paragraph ends instead of playing it.  Only when the last word
    # is surely heard -- one of the paragraph's last three -- is it trimmed.
    end = duration
    if (last[n - 1] is not None and lastidx[n - 1] >= total[n - 1] - 3
            and duration - last[n - 1] > TAIL):
        end = min(duration, last[n - 1] + LEAD * 2)
    cuts = cuts[:n] + [max(end, cuts[n - 1] + 0.001)] if len(cuts) >= n else cuts + [end]
    return [(units[u], cuts[u], cuts[u + 1], got[u] / total[u] if total[u] else 0.0)
            for u in range(n)]


def pause(sil, lo: float, hi: float, guess: float, floor: float,
          cap: float | None = None) -> float:
    """The middle of the longest silence overlapping [lo, hi], nearest `guess`
    on a tie; `guess` itself when there is none.  Never before `floor`.

    `lo` carries SLACK below the last word heard; a silence must end above it
    by more than that.  Whisper's word ENDS are reliable where its starts are
    not, so a pause that is over before the last word heard has finished is
    the pause before that word -- in 30:2, the one before "One. Supernaphim",
    which took the cut that belonged after it."""
    best, key = None, None
    if cap is not None:
        hi = min(hi, cap)
    for s, e in sil:
        if e < lo + SLACK + 0.05 or s > hi:
            continue
        a, b = max(s, lo), min(e, hi)
        k = (b - a, -abs((a + b) / 2 - guess))
        if key is None or k > key:
            best, key = (a + b) / 2, k
    t = guess if best is None else best
    if best is not None:
        for s, e in sil:
            if s <= best <= e:
                t = max(best, e - LEAD)
                break
    if cap is not None:
        t = min(t, cap - 0.02)
    return max(t, floor + 0.001)


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT))
    from build import audio, config
    from build.audio import LOW_MATCH, LOW_WORDS
    from build.problems import Report
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    files = audio.mh_files()
    report = Report()
    claims = audio.mh_claims(con, files, report)
    units = audio.mh_units(con, claims)
    if report.problems:
        print(*report.problems, sep="\n")
        return 1
    # Paragraphs the recording does not contain (data/audio/mh-unread.tsv): left
    # out of what each file is expected to hold, so their silence is nobody's.
    unread = {r for r, _ in (l.split("\t", 1) for l in
              (ROOT / "data" / "audio" / "mh-unread.tsv").read_text().splitlines()
              if l[:1].isdigit())}
    units = {n: [r for r in u if r not in unread] for n, u in units.items()}
    root = config.audio()["mh"]["path"]
    only = set(argv)
    todo = [n for n in sorted(units)
            if (WORDS / f"{pathlib.Path(n).stem}.json").exists()
            and (not only or pathlib.Path(n).stem in only)]
    print(f"{len(todo)} of {len(units)} files transcribed")
    SILENCE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        sils = dict(zip(todo, ex.map(lambda n: silences(root / n, pathlib.Path(n).stem), todo)))
    print(f"silences in {time.time() - t0:.0f}s")
    rows = []
    for name in todo:
        d = json.loads((WORDS / f"{pathlib.Path(name).stem}.json").read_text())
        dur = files[name][1] / 1000                 # the manifest's duration, as the build has it
        for ref, a, b, match in align(con, name, units[name], d["words"], dur, sils[name]):
            rows.append((ref, name, round(a * 1000), round(b * 1000), match))
        if only:
            for r in rows[-len(units[name]):]:
                print(f"  {r[0]:10} {r[2]/1000:8.2f} {r[3]/1000:8.2f}  {r[4]:.2f}")
    if only:
        return 0
    out = OUT
    if len(todo) < len(units):
        # Not the record until every file is in: a partial alignment goes to
        # var/, where the listening test can use what there is.
        out = ROOT / "var" / "align" / "mh-partial.tsv"
        print(f"{len(units) - len(todo)} files not yet transcribed: writing {out.relative_to(ROOT)}")
    with out.open("w", encoding="utf-8") as fh:
        fh.write("# faster-whisper large-v3 word times, matched to the text by difflib;"
                 f" each cut at the middle of the longest pause ({NOISE}, >= {MIN_SIL}s)."
                 " tools/align/align.py\n")
        fh.write("ref\tfile\tstart_ms\tend_ms\tmatch\n")
        for ref, name, a, b, match in rows:
            fh.write(f"{ref}\t{name}\t{a}\t{b}\t{match:.3f}\n")
    low = sum(1 for r in rows if r[4] < 0.8)
    print(f"{out.relative_to(ROOT)}: {len(rows)} segments, {low} below 0.8 match,"
          f" in {time.time() - t0:.0f}s")
    # What a person should look at: the paragraphs the build's gate will
    # hold to data/audio/mh-low-match.tsv and mh-unread.tsv.
    wc = dict(con.execute("SELECT ref, word_count FROM paragraph"))
    review = ROOT / "var" / "align" / "mh-review.tsv"
    with review.open("w", encoding="utf-8") as fh:
        for ref, name, a, b, m in rows:
            if "." in ref and wc[ref] >= LOW_WORDS and m < LOW_MATCH:
                fh.write(f"{ref}\t{m:.3f}\t{wc[ref]}\t{name}\t{a}\t{b}\n")
    print(f"{review.relative_to(ROOT)}: paragraphs of {LOW_WORDS}+ words below {LOW_MATCH} match")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
