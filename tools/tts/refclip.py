"""Cut a reference clip for voice cloning: the first sentences of a passage some
synthetic voice has already read, with their exact transcript.

    ~/Software/ml/venv-align/bin/python -m tools.tts.refclip VOICE [PASSAGE] [SENTENCES]
    -> var/tts/refs/VOICE.wav and VOICE.txt
    python3 -m tools.tts.refclip --clean VOICE
    -> var/tts/refs/VOICE_clean.wav and VOICE_clean.txt

A cloning model wants a clip of a few seconds and the words in it.  The words
come from the build's spoken text, split into sentences; where the Nth
sentence ends in the audio, from Whisper's word times.  Only synthetic voices
are cut this way -- the clip is the voice the next model will imitate, and it
must imitate nobody.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys

import numpy as np

from tools.tts.bakeoff import OUT, ROOT

REFS = ROOT / "var" / "tts" / "refs"
# A clone copies the room as well as the voice.  higgs2_mature's pauses carry a
# 120 Hz hum, 16 dB over its neighbours, over a floor at -58 dB, and Higgs TTS 3
# reproduced it: a hum in one pause in five, heard under "designated by these
# numerous" in 0:0.1.  A narrow notch and FFT denoising take the hum to +2 dB.
CLEAN = "bandreject=f=120:width_type=q:w=8,afftdn=nf=-58:nr=18:tn=1"


def clean(voice: str) -> None:
    """VOICE.wav without its hum and with less of its noise, as VOICE_clean."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REFS / f"{voice}.wav"), "-af", CLEAN,
                    "-ac", "1", "-ar", "24000", str(REFS / f"{voice}_clean.wav")], check=True)
    (REFS / f"{voice}_clean.txt").write_text((REFS / f"{voice}.txt").read_text())
    print(f"{voice}_clean: {CLEAN}")


def main(argv: list[str]) -> int:
    if argv[:1] == ["--clean"]:
        clean(argv[1])
        return 0
    from faster_whisper import WhisperModel
    voice = argv[0]
    spec = argv[1] if len(argv) > 1 else "1:0.1"
    n = int(argv[2]) if len(argv) > 2 else 2
    src = OUT / voice / f"{spec.replace(':', '_')}.mp3"
    text = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True).execute(
        "SELECT s.text FROM speech s JOIN paragraph p ON p.id = s.paragraph_id WHERE p.ref = ?",
        (spec,)).fetchone()[0]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language="en",
                               word_timestamps=True, vad_filter=False)
    ends = [w.end for s in segs for w in s.words if w.word.strip().endswith((".", "!", "?"))]
    cut = ends[n - 1] + 0.25
    REFS.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{cut:.2f}",
                    "-ac", "1", "-ar", "24000", str(REFS / f"{voice}.wav")], check=True)
    (REFS / f"{voice}.txt").write_text(" ".join(sentences[:n]) + "\n")
    print(f"{voice}: {cut:.1f} s -> {REFS / voice}.wav | {' '.join(sentences[:n])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
