"""Check the cuts by hearing them: does each paragraph start where mh.tsv says?

    make align-spotcheck              # 300 paragraphs, chosen at random (seeded)

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
    from build import config
    from build.speech import speak
    from faster_whisper import WhisperModel
    # --lists: every paragraph that opens with a list mark ("8. Simon Zelotes"),
    # where the pause after the number can outdo the pause before it.
    lists = "--lists" in argv
    argv = [a for a in argv if a != "--lists"]
    n = int(argv[0]) if argv else 300
    tsv = ROOT / "data" / "audio" / "mh.tsv"
    if not tsv.exists():
        tsv = ROOT / "var" / "align" / "mh-partial.tsv"   # while Whisper is still running
    rows = [l.split("\t") for l in tsv.read_text().splitlines() if l[:1].isdigit()]
    rows = [r for r in rows if "." in r[0]]          # paragraphs, not headings
    random.Random(7).shuffle(rows)
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    if lists:
        marked = {r for (r,) in con.execute("SELECT p.ref FROM span s JOIN paragraph p"
                                            " ON p.id = s.paragraph_id WHERE s.kind = 'listmark'")}
        rows = [r for r in rows if r[0] in marked]
        n = min(n, len(rows)) if argv else len(rows)
    text = dict(con.execute("SELECT p.ref, s.text FROM speech s JOIN paragraph p"
                            " ON p.id = s.paragraph_id"))
    root = config.audio()["mh"]["path"]
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    bad = []
    for ref, name, a, b, _m in rows[:n]:
        a = int(a) / 1000
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", "4", "-i",
                              str(root / name), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language="en",
                                   vad_filter=False, condition_on_previous_text=False)
        said = " ".join(s.text for s in segs)
        said = " ".join(speak(w) if any(c.isdigit() for c in w) else w for w in said.split())
        heard, want = tokens(said)[:3], tokens(text[ref])[:3]
        # Two of the first three words is a hit: Whisper may mishear a coined
        # name, and a list's "One." may come out as "1." or vanish.  So is the
        # same letters with the spaces moved: "super universe", "superuniverse".
        ok = (sum(1 for w in want if w in heard) >= 2
              or "".join(heard).startswith("".join(want[:2])))
        if not ok:
            bad.append((ref, name, a, " ".join(heard), " ".join(want)))
    for ref, name, a, h, w in bad:
        print(f"  {ref:10} at {a:8.2f}s  heard {h!r:36} text {w!r}")
    print(f"{n - len(bad)} of {n} paragraphs start where mh.tsv says ({(n - len(bad)) / n:.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
