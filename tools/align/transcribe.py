"""Transcribe Merritt Horn's reading, word by word, for the paragraph aligner.

    make align-transcribe          # both GPUs, resumable

The recordings' path comes from sources.toml through build/config.py, like
every other source path; run from the project root (`python -m`) so that
module can be imported.

One JSON per MP3 in var/align/mh/, holding every recognised word with its start,
end and probability.  This is the expensive half of the alignment -- about 80x
real time on the 3090, so the 121 hours take an hour or two -- and it is kept
apart from the cheap half (tools/align/align.py, which matches these words to
our paragraphs and can be rerun in seconds as often as it needs tuning).

--repair is the second pass.  The batched pipeline is fast but now and then
drops a whole stretch of speech: it heard only "Intellectual cross-
fertilization" of 52:6.4's 69 words, though all 30 seconds of them are there.
So every unit the aligner found mostly unheard is transcribed again, alone and
unbatched, and its words replace the batch's in that window.  What is still
unheard after that was not read.

Runs in its own venv (tools/align/requirements.in), never the site's.  Several
processes may run at once, one per GPU: each claims a file by creating its
.lock with O_EXCL, so no file is transcribed twice and a killed run resumes
where it stopped (after --clean-locks).

The recordings are a master, like the three source repos: opened for reading,
by ffmpeg, and never written.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "var" / "align" / "mh"
MODEL = "large-v3"


def decode(path: pathlib.Path):
    """16 kHz mono float32, decoded by ffmpeg.  faster-whisper's own decoder
    goes through PyAV, whose API moved under it (`metadata_errors`)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-locks", action="store_true",
                    help="remove .lock files left by a killed run, then exit")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--repair", action="store_true",
                    help="re-transcribe, unbatched, every unit the aligner found mostly unheard")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.clean_locks:
        for f in OUT.glob("*.lock"):
            f.unlink()
        return 0

    if args.repair:
        return repair()

    from build import config
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    files = sorted(config.audio()["mh"]["path"].glob("paper*/*.mp3"))
    todo = [f for f in files if not (OUT / f"{f.stem}.json").exists()]
    print(f"{len(files)} files, {len(todo)} to do", flush=True)
    if not todo:
        return 0
    model = WhisperModel(MODEL, device="cuda", compute_type="float16")
    pipe = BatchedInferencePipeline(model=model)
    done = secs = 0.0
    t0 = time.time()
    for f in todo:
        out = OUT / f"{f.stem}.json"
        lock = out.with_suffix(".lock")
        if out.exists():
            continue
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue                                # another GPU has it
        try:
            segs, info = pipe.transcribe(decode(f), language="en",
                                         word_timestamps=True, batch_size=args.batch)
            words = [[round(w.start, 3), round(w.end, 3), w.word.strip(),
                      round(w.probability, 3)]
                     for s in segs for w in (s.words or [])]
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"file": f"{f.parent.name}/{f.name}",
                                       "model": MODEL,
                                       "duration": round(info.duration, 3),
                                       "words": words}, ensure_ascii=False))
            tmp.replace(out)
            done += 1
            secs += info.duration
            rate = secs / (time.time() - t0)
            print(f"{f.stem}  {info.duration/60:5.1f} min  {len(words):5} words"
                  f"   [{int(done)} done, {rate:.0f}x]", flush=True)
        finally:
            lock.unlink(missing_ok=True)
    return 0


def repair(threshold: float = 0.6, min_words: int = 5) -> int:
    """Second pass over the units the aligner found mostly unheard."""
    import sqlite3
    from build import config
    from faster_whisper import WhisperModel
    tsv = ROOT / "data" / "audio" / "mh.tsv"
    if not tsv.exists():
        tsv = ROOT / "var" / "align" / "mh-partial.tsv"
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    words = dict(con.execute("SELECT ref, word_count FROM paragraph"))
    todo = {}
    for line in tsv.read_text().splitlines():
        if not line[:1].isdigit():
            continue
        ref, name, a, b, m = line.split("\t")
        if float(m) < threshold and words.get(ref, 0) >= min_words:
            todo.setdefault(name, []).append((int(a) / 1000, int(b) / 1000, ref))
    print(f"{sum(map(len, todo.values()))} units in {len(todo)} files to re-hear", flush=True)
    model = WhisperModel(MODEL, device="cuda", compute_type="float16")
    root = config.audio()["mh"]["path"]
    for name, spans in sorted(todo.items()):
        out = OUT / f"{pathlib.Path(name).stem}.json"
        d = json.loads(out.read_text())
        audio = decode(root / name)
        done = {tuple(x) for x in d.get("repaired", [])}
        for a, b, ref in spans:
            # Fifteen seconds either side.  A segment found mostly unheard may
            # itself be cut wrong -- 120:0.1 came out 25 s long for its 119
            # words -- and re-hearing only inside it would miss the rest.
            lo, hi = max(0.0, a - 15.0), min(d["duration"], b + 15.0)
            if (round(lo, 3), round(hi, 3)) in done:
                continue
            segs, _ = model.transcribe(audio[int(lo * 16000):int(hi * 16000)], language="en",
                                       word_timestamps=True, vad_filter=False,
                                       condition_on_previous_text=False)
            new = [[round(w.start + lo, 3), round(w.end + lo, 3), w.word.strip(),
                    round(w.probability, 3)] for s in segs for w in (s.words or [])]
            keep = [w for w in d["words"] if not lo <= w[0] < hi]
            d["words"] = sorted(keep + new)
            d.setdefault("repaired", []).append([round(lo, 3), round(hi, 3)])
            print(f"{ref:10} {name}  {lo:7.1f}-{hi:7.1f}  now {len(new)} words", flush=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        tmp.replace(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
