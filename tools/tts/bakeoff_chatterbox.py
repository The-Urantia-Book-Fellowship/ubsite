"""The listening test's Chatterbox voices (Resemble AI, MIT): the same passages
as tools/tts/bakeoff.py, in Chatterbox's stock voice.

    make tts-bakeoff-chatterbox

A separate venv: Chatterbox pins its own torch.  Its stock voice only -- it can
clone any voice from a few seconds of audio, and Merritt Horn's must never be
one of them.  It takes text, not phonemes, so a lexicon would have to be
respellings ("you-RAN-sha") rather than IPA.  It generates a sentence or two at
a time; longer and it starts to drift, so each paragraph goes in sentences.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time

import numpy as np

from tools.tts.bakeoff import OUT, PAUSE, ROOT, SAMPLES, encode, refs

SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[\"“‘A-Z])")


def chunks(text: str, limit: int = 280) -> list[str]:
    out = []
    for s in SENTENCE.split(text):
        if out and len(out[-1]) + len(s) < limit:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def main() -> int:
    from chatterbox.tts import ChatterboxTTS
    model = ChatterboxTTS.from_pretrained(device="cuda")
    rate = model.sr
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    speech = dict(con.execute("SELECT p.ref, s.text FROM speech s JOIN paragraph p"
                              " ON p.id = s.paragraph_id"))
    voice = "chatterbox"
    made = took = 0.0
    for spec, _ in SAMPLES:
        parts = []
        for r in refs(spec):
            for c in chunks(speech[r]):
                t0 = time.time()
                parts.append(model.generate(c).squeeze(0).cpu().numpy())
                took += time.time() - t0
                parts.append(np.zeros(int(0.25 * rate), dtype=np.float32))
            parts[-1] = np.zeros(int(PAUSE * rate), dtype=np.float32)
        wav = np.concatenate(parts[:-1])
        made += len(wav) / rate
        encode(wav, OUT / voice / f"{spec.replace(':', '_')}.mp3", rate)
        print(f"  {spec:12} {len(wav) / rate:5.0f} s", flush=True)
    meta = json.loads((OUT / "bakeoff.json").read_text())
    if voice not in meta["voices"]:
        meta["voices"].append(voice)
    meta["rtf"][voice] = round(made / took, 1)
    (OUT / "bakeoff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"{voice:12} {made:6.0f} s of audio, {made / took:5.1f}x real time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
