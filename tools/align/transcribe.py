"""Transcribe a reading, word by word, for the paragraph aligner.

    make align-transcribe                  # Merritt Horn's; resumable
    make align-transcribe VOICE=voyner     # another's (--voice), in its language

The recordings' path comes from sources.toml through build/config.py, like
every other source path; run from the project root (`python -m`) so that
module can be imported.

One JSON per MP3 in var/align/<key>/, holding every recognised word with its start,
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

--repair --short re-hears the short units too, a list's items of two or three
words and the spoken headings, which the first leaves alone: of Григорий
Войнер's reading the batch dropped the six items of 42:12.2-7, twenty-four
seconds of speech between two sentences it heard, and the heading that opens
184:4.  A window reaches over any silence of the transcript's that it touches,
since the cuts of what was not heard stand wherever the aligner left them.

--repair --near REF ... hears the 26 seconds round the start of each unit
named, in one piece, and twice more in less, keeping of the three hearings the
one with the most words at the seam: Whisper does not hear a stretch the same
way twice.  Whisper works in pieces of thirty seconds, and a longer
window is several, at whose seams it can drop words again: of 161:1.7 it lost
the same ten seconds twice in windows of a minute, and heard them in one of
four seconds.  And at a paragraph's seam the batch now and then loses the last
word or two before a list's number and times the number early ("... воровством.
9." for "... воровством или мошенничеством. 9.", 132:5.10), or loses a short
label whole ("6. Дисциплина и ограничения.", 142:7.9), which leaves the cut a
second or five off with nothing in the match to show it.  `make
align-spotcheck LISTS=1` finds such a place by hearing it; name it here.

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
    ap.add_argument("--short", action="store_true",
                    help="with --repair: the units of fewer than five words and the headings too")
    ap.add_argument("--near", nargs="+", metavar="REF",
                    help="with --repair: only the 26 s round the start of each of these units, in one piece")
    ap.add_argument("--voice", default="mh",
                    help="the reading, a key of sources.toml's [audio.<key>] (tools/align/voice.py)")
    args = ap.parse_args()
    from tools.align.voice import Voice
    voice = Voice(args.voice)
    OUT = voice.words
    OUT.mkdir(parents=True, exist_ok=True)

    if args.clean_locks:
        for f in OUT.glob("*.lock"):
            f.unlink()
        return 0

    if args.repair:
        return repair(voice, min_words=0 if args.short else 5, near=args.near)

    from faster_whisper import BatchedInferencePipeline, WhisperModel
    files = voice.files()
    todo = [f for f in files if not (OUT / f"{f.stem}.json").exists()]
    print(f"{voice.key} ({voice.lang}): {len(files)} files, {len(todo)} to do", flush=True)
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
            segs, info = pipe.transcribe(decode(f), language=voice.lang,
                                         word_timestamps=True, batch_size=args.batch)
            words = [[round(w.start, 3), round(w.end, 3), w.word.strip(),
                      round(w.probability, 3)]
                     for s in segs for w in (s.words or [])]
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"file": voice.name(f),
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


GAP = 3.0                 # a silence of the transcript's this long may hold dropped speech


def window(words: list, a: float, b: float, duration: float, pad: float = 15.0) -> tuple[float, float]:
    """The stretch to hear again for a unit cut at a..b: fifteen seconds either
    side, and the whole of any silence of the transcript's that reaches into
    it, with a second beyond.  A segment found mostly unheard may itself be cut
    wrong -- 120:0.1 came out 25 s long for its 119 words -- and what the batch
    dropped lies in such a silence, wherever the unit's cut was left: 42:12.2-7
    stood at 61.3-62.0 s, and were read from 37 s to 61 s."""
    lo, hi = max(0.0, a - pad), min(duration, b + pad)
    ends = [0.0] + [w[1] for w in words]
    starts = [w[0] for w in words] + [duration]
    for e, s in zip(ends, starts):
        if s - e >= GAP and e < hi and s > lo:
            lo, hi = min(lo, max(0.0, e - 1.0)), max(hi, min(duration, s + 1.0))
    return lo, hi


# Before and after a unit's start: 26 s, one piece of Whisper's, and two
# shorter.  Whisper does not hear one stretch the same way twice: the 26 s
# round 2:5.5 gave 19 words, the seam's among those lost, and minutes later 40.
# So a place is heard in each of these, and the hearing kept is the one with
# the most words in the ten seconds round the seam, which all three hold.
NEAR = ((12.0, 14.0), (6.0, 8.0), (4.0, 6.0))


def repair(voice, threshold: float = 0.6, min_words: int = 5, near: list[str] | None = None) -> int:
    """Second pass over the units the aligner found mostly unheard: those of
    min_words words or more; with 0, every one, the spoken headings too.  Or,
    with `near`, over the start of each unit it names and nothing else."""
    import sqlite3
    from faster_whisper import WhisperModel
    OUT = voice.words
    tsv = voice.cuts()
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    words = voice.word_counts(con)
    todo = {}
    for line in tsv.read_text().splitlines():
        if not line[:1].isdigit():
            continue
        ref, name, a, b, m = line.split("\t")
        if near is not None:
            if ref in near:
                todo.setdefault(name, []).append((int(a) / 1000, int(a) / 1000, ref))
        elif float(m) < threshold and (not min_words or words.get(ref, 0) >= min_words):
            todo.setdefault(name, []).append((int(a) / 1000, int(b) / 1000, ref))
    if near is not None and sum(map(len, todo.values())) != len(set(near)):
        raise SystemExit(f"repair: not units of {tsv.name}: "
                         + " ".join(sorted(set(near) - {r for v in todo.values() for _a, _b, r in v})))
    print(f"{sum(map(len, todo.values()))} units in {len(todo)} files to re-hear", flush=True)
    model = WhisperModel(MODEL, device="cuda", compute_type="float16")
    root = voice.path
    for name, spans in sorted(todo.items()):
        out = OUT / f"{pathlib.Path(name).stem}.json"
        d = json.loads(out.read_text())
        audio = decode(root / name)
        done = {tuple(x) for x in d.get("repaired", [])}
        def hear(lo: float, hi: float) -> list:
            segs, _ = model.transcribe(audio[int(lo * 16000):int(hi * 16000)], language=voice.lang,
                                       word_timestamps=True, vad_filter=False,
                                       condition_on_previous_text=False)
            return [[round(w.start + lo, 3), round(w.end + lo, 3), w.word.strip(),
                     round(w.probability, 3)] for s in segs for w in (s.words or [])]

        for a, b, ref in spans:
            if near is not None:
                best = None
                for before, after in NEAR:
                    lo, hi = max(0.0, a - before), min(d["duration"], a + after)
                    got = hear(lo, hi)
                    at_seam = sum(1 for w in got if a - NEAR[-1][0] + 0.5 <= w[0] < a + NEAR[-1][1] - 0.5)
                    if best is None or at_seam > best[0]:
                        best = (at_seam, lo, hi, got)
                _n, lo, hi, new = best
            else:
                lo, hi = window(d["words"], a, b, d["duration"])
                # Heard again already, in this run or an earlier one: a window
                # inside one that was is not worth a second hearing.
                if any(x <= round(lo, 3) and round(hi, 3) <= y for x, y in done):
                    continue
                new = hear(lo, hi)
            keep = [w for w in d["words"] if not lo <= w[0] < hi]
            d["words"] = sorted(keep + new)
            d.setdefault("repaired", []).append([round(lo, 3), round(hi, 3)])
            done.add((round(lo, 3), round(hi, 3)))
            print(f"{ref:10} {name}  {lo:7.1f}-{hi:7.1f}  now {len(new)} words", flush=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        tmp.replace(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
