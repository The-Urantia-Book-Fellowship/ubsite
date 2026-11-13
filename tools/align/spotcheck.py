"""Check the cuts by hearing them: does each paragraph start where <key>.tsv says?

    make align-spotcheck              # 300 paragraphs, chosen at random (seeded)
    make align-spotcheck VOICE=voyner # another reading's (--voice)
    make align-spotcheck N=20000      # every paragraph (an hour and a half for 14,575)
    make align-spotcheck LISTS=1      # every list paragraph (--lists)
    make align-spotcheck REFS="2:5.5 142:7.9"   # these alone (--refs), after a repair

The aligner's own numbers say how much of a paragraph Whisper heard inside its
segment.  This asks a different question, the one a listener asks on clicking
a paragraph: are the first words heard the paragraph's first words?  For each
sampled paragraph it cuts the first four seconds of the segment, has Whisper
hear that clip alone -- no context, no timestamps of its own -- and compares
the first three words heard with the first three of the text.

A clip that opens with the end of the previous paragraph, or misses the first
word, fails.  Runs in the aligner's venv.
"""

from __future__ import annotations

import pathlib
import random
import sqlite3
import subprocess
import sys

import numpy as np

from tools.align.align import tokens

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def main(argv: list[str]) -> int:
    from build.speech import speak
    from faster_whisper import WhisperModel
    from tools.align.voice import take
    voice, argv = take(argv)
    lang = voice.lang
    # --lists: every paragraph that opens with a list mark ("8. Simon Zelotes"),
    # where the pause after the number can outdo the pause before it.
    lists = "--lists" in argv
    argv = [a for a in argv if a != "--lists"]
    # --refs 2:5.5 142:7.9: these paragraphs and no others, after a repair.
    named = None
    if "--refs" in argv:
        i = argv.index("--refs")
        named, argv = set(argv[i + 1:]), argv[:i]
    n = int(argv[0]) if argv else 300
    tsv = voice.cuts()                              # the partial, while Whisper is still running
    rows = [l.split("\t") for l in tsv.read_text().splitlines() if l[:1].isdigit()]
    rows = [r for r in rows if "." in r[0]]          # paragraphs, not headings
    random.Random(7).shuffle(rows)
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    if lists:
        marked = {r for (r,) in con.execute("SELECT p.ref FROM span s JOIN paragraph p"
                                            " ON p.id = s.paragraph_id WHERE s.kind = 'listmark'")}
        rows = [r for r in rows if r[0] in marked]
        n = min(n, len(rows)) if argv else len(rows)
    if named is not None:
        rows = [r for r in rows if r[0] in named]
        if len(rows) != len(named):
            raise SystemExit(f"spotcheck: not paragraphs of {tsv.name}: " + " ".join(sorted(named - {r[0] for r in rows})))
        n = len(rows)
    n = min(n, len(rows))
    text = voice.text(con)
    root = voice.path
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    # Each miss is said as it is found, and the count now and then: a pass over
    # every paragraph is an hour and a half, and one that was stopped on
    # 2026-11-12 had kept its findings for the end and left none.
    bad = []
    for i, (ref, name, a, b, _m) in enumerate(rows[:n]):
        if i and i % 1000 == 0:
            print(f"# {i} of {n} heard, {len(bad)} not as the text", flush=True)
        a = int(a) / 1000
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", "4", "-i",
                              str(root / name), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language=lang,
                                   vad_filter=False, condition_on_previous_text=False)
        said = " ".join(s.text for s in segs)
        if lang == "en":
            said = " ".join(speak(w) if any(c.isdigit() for c in w) else w for w in said.split())
        heard, want = tokens(said, lang)[:3], tokens(text[ref], lang)[:3]
        # Two of the first three words is a hit: Whisper may mishear a coined
        # name, and a list's "One." may come out as "1." or vanish.  So is the
        # same letters with the spaces moved: "super universe", "superuniverse".
        ok = (sum(1 for w in want if w in heard) >= 2
              or "".join(heard).startswith("".join(want[:2])))
        if not ok:
            bad.append(ref)
            print(f"  {ref:10} at {a:8.2f}s  heard {' '.join(heard)!r:36} text {' '.join(want)!r}", flush=True)
    print(f"{n - len(bad)} of {n} paragraphs start where {tsv.name} says ({(n - len(bad)) / n:.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
