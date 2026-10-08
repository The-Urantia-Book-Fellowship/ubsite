"""Did the voice say the words?  Whisper listens back, and each clip is scored
against the text it was made from: the share of the text's words heard.

    make tts-hear                       # the listening test's clips

A synthetic voice can skip a phrase, repeat one, or invent one, and nothing in
the waveform says so.  This is the check.  Coined names score low for every
voice -- Whisper does not know "Nebadon" either -- so the number compares
voices on the same passage; it is not an absolute grade.

Runs in the aligner's venv (it is Whisper); scores with the aligner's own
tokens, so "1934" and "nineteen thirty-four" count as the same words.
"""

from __future__ import annotations

import difflib
import json
import pathlib
import subprocess
import sys

import numpy as np

from tools.align.align import tokens
from tools.tts.bakeoff import OUT, SAMPLES

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def heard_share(said: str, text: str) -> float:
    from build.speech import speak
    # Whisper writes "993,408" where the voice said the words; speak it back.
    said = " ".join(speak(w) if any(c.isdigit() for c in w) else w for w in said.split())
    a, b = tokens(said), tokens(text)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / max(1, len(b))


def main() -> int:
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    pipe = BatchedInferencePipeline(WhisperModel("large-v3", device="cuda", compute_type="float16"))
    meta = json.loads((OUT / "bakeoff.json").read_text())
    texts = {s["id"]: " ".join(s["text"]) for s in meta["samples"]}
    scores = {}
    for voice in ["mh"] + meta["voices"]:
        for spec, _ in SAMPLES:
            f = OUT / voice / f"{spec.replace(':', '_')}.mp3"
            if not f.exists():
                continue
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", "16000",
                                  "-f", "f32le", "-"], capture_output=True, check=True).stdout
            segs, _ = pipe.transcribe(np.frombuffer(raw, dtype=np.float32), language="en",
                                      batch_size=8)
            said = " ".join(s.text for s in segs)
            scores.setdefault(voice, {})[spec] = round(heard_share(said, texts[spec]), 3)
        v = scores.get(voice, {})
        print(f"{voice:12} " + " ".join(f"{v.get(s, 0):.2f}" for s, _ in SAMPLES)
              + f"   mean {sum(v.values()) / max(1, len(v)):.3f}", flush=True)
    meta["heard"] = scores
    (OUT / "bakeoff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
