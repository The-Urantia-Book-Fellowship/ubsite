"""Carry the transcripts over to another copy of the same recordings.

    ~/Software/ml/venv-align/bin/python -m tools.align.rebase OLD_DIR

Whisper heard the 1.7 GB set -- 32 kbps mono, 22.05 kHz.  That set turned out
to be the Uversa Press DVD's 128 kbps stereo MP3s re-encoded: the same 1,629
files, every one 0.08-0.20 s longer, and correlating at 0.95-1.00 with the disc
at its start and four-fifths of the way in.  Our copies lag the disc by the
encoder's delay -- 50.1 ms, 1,105 samples at 22.05 kHz, for nearly all of them --
with no drift.  So nothing needs hearing again: each file's lag is measured,
here, by cross-correlating 20 s of both, and its word times are moved by it.

The old transcripts are kept in var/align/mh-transcode/; the silence cache is
emptied, since pauses are measured on the audio actually served.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
WORDS = ROOT / "var" / "align" / "mh"
KEEP = ROOT / "var" / "align" / "mh-transcode"
SR = 8000


def pcm(path: pathlib.Path, at: float, dur: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-t", str(dur), "-i", str(path),
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def lag(old: np.ndarray, new: np.ndarray) -> tuple[float, float]:
    """How much later `old` is than `new`, in seconds, and how well they agree."""
    n = len(old) + len(new)
    c = np.fft.irfft(np.fft.rfft(old, n) * np.conj(np.fft.rfft(new, n)), n)
    k = int(np.argmax(c))
    k = k - n if k > n // 2 else k
    return k / SR, float(c.max() / (np.linalg.norm(old) * np.linalg.norm(new)))


def main(argv: list[str]) -> int:
    from build import config
    old_root = pathlib.Path(argv[0])
    new_root = config.audio()["mh"]["path"]
    if old_root.resolve() == new_root.resolve():
        raise SystemExit("rebase: sources.toml still points at the old recordings")
    if not KEEP.exists():
        shutil.copytree(WORDS, KEEP)                # the transcripts as Whisper made them
    worst = 1.0
    for src in sorted(KEEP.glob("*.json")):
        d = json.loads(src.read_text())
        name = d["file"]
        off, r = lag(pcm(old_root / name, 5.0, 20.0), pcm(new_root / name, 5.0, 20.0))
        worst = min(worst, r)
        if r < 0.8:
            raise SystemExit(f"rebase: {name} agrees only {r:.2f} with the new copy -- not the same audio?")
        d["words"] = [[round(s - off, 3), round(e - off, 3), w, p] for s, e, w, p in d["words"]]
        d["repaired"] = [[round(a - off, 3), round(b - off, 3)] for a, b in d.get("repaired", [])]
        d["rebased"] = {"from": str(old_root / name), "shift_ms": round(-off * 1000, 1),
                        "correlation": round(r, 3)}
        (WORDS / src.name).write_text(json.dumps(d, ensure_ascii=False))
    shutil.rmtree(ROOT / "var" / "align" / "silence", ignore_errors=True)
    print(f"{len(list(KEEP.glob('*.json')))} transcripts moved onto {new_root};"
          f" weakest correlation {worst:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
