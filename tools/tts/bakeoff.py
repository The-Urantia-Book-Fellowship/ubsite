"""The voice listening test: the same hard passages in every candidate voice,
beside Merritt Horn reading them.

    make tts-bakeoff                      # -> var/tts/bakeoff/

Each passage is synthesised paragraph by paragraph from the build's spoken text
(table `speech`) and joined with the pause the real recording will have, so
what is heard here is what the site would play.  His clip is cut from his
recording at the aligner's boundaries (data/audio/mh.tsv).  The page is for
choosing by ear; nothing here is used by the site.

Runs in the TTS venv (tools/tts/requirements.in).  Pronunciation is the
model's own here -- the lexicon (data/pronounce.tsv) comes after the choice.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "var" / "tts" / "bakeoff"
RATE = 24000
PAUSE = 0.6                       # seconds between paragraphs
# Every clip, his and the voices', at one loudness: in a listening test the
# louder of two otherwise equal voices is heard as the better one.  One gain
# per clip, measured first, then a limiter for the peaks -- not loudnorm in a
# single pass, which rides the gain: Belinda's 0:0.1 opened at -13 dB and sank
# to -23 for the rest of the clip.
LOUDNESS = -18.0                  # LUFS, integrated
CEILING = 10 ** (-1.5 / 20)       # the limiter's ceiling, -1.5 dBFS as a linear level
# A model may fail to stop: Higgs TTS 3 read 0:0.1 in 37 s and then made 45 s
# of near-silence until it reached its token limit.  Trim trailing quiet
# (reversed, so silenceremove's leading trim acts on the end) before measuring
# loudness, so the silence neither plays nor drags the level down.
TRIM = ("areverse,silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.4"
        ":detection=rms:window=0.05,areverse")   # RMS over 50 ms: the tail had clicks

# What each passage tests.
SAMPLES = [
    ("0:0.1", "The Foreword's opening"),
    ("1:0.1", "The first words of Paper 1"),
    ("79:0.1", "Names: Andites, Nodites, Sangik, Badonan"),
    ("62:7.7", "Numbers and a date: 993,408 years ago, A.D. 1934"),
    ("140:3.3-6", "Red letter: the Beatitudes"),
    ("48:6.9-14", "Verse: the morontia twenty-third psalm"),
    ("1:7.9", "An attribution: [Presented by ...]"),
    ("15:2.10-16", "A dot-leader table"),
    ("30:2.81-86", "A list of coined names"),
]
# Kokoro v1.0's English voices worth hearing: (voice, lang_code).  The first
# letter is the accent (a American, b British), the second the voice's sex.
VOICES = [("af_heart", "a"), ("af_bella", "a"), ("am_michael", "a"), ("am_fenrir", "a"),
          ("am_puck", "a"), ("bf_emma", "b"), ("bm_george", "b"), ("bm_fable", "b")]


def refs(spec: str) -> list[str]:
    m = re.fullmatch(r"(\d+:\d+)\.(\d+)(?:-(\d+))?", spec)
    a, b = int(m.group(2)), int(m.group(3) or m.group(2))
    return [f"{m.group(1)}.{n}" for n in range(a, b + 1)]


def leveled(inputs: list[str], before: str = "", data: bytes | None = None) -> str:
    """The filter chain that brings what `inputs` decode to LOUDNESS: `before`,
    then one fixed gain, then the limiter.  Measures it first, with loudnorm's
    analysis pass."""
    chain = f"{before}," if before else ""
    run = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *inputs,
                          "-af", f"{chain}loudnorm=print_format=json", "-f", "null", "-"],
                         input=data, capture_output=True, check=True)
    err = run.stderr.decode()
    measured = float(json.loads(err[err.rindex("{"):err.rindex("}") + 1])["input_i"])
    return (f"{chain}volume={LOUDNESS - measured:.2f}dB,"
            f"alimiter=limit={CEILING:.4f}:level=false")


def encode(wav: np.ndarray, out: pathlib.Path, rate: int = RATE) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    data = wav.astype(np.float32).tobytes()
    inputs = ["-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "-"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-af", leveled(inputs, TRIM, data),
                    "-ar", str(rate), "-c:a", "libmp3lame", "-b:a", "48k", str(out)],
                   input=data, check=True)


def mh_clip(spec: str, out: pathlib.Path) -> bool:
    """His reading of the passage, at the aligner's boundaries -- from the full
    alignment, or the partial one align.py leaves while Whisper is still running."""
    rows = {}
    tsv = ROOT / "data" / "audio" / "mh.tsv"
    if not tsv.exists():
        tsv = ROOT / "var" / "align" / "mh-partial.tsv"
    if not tsv.exists():
        return False
    for line in tsv.read_text().splitlines():
        if line and not line.startswith(("#", "ref\t")):
            ref, name, a, b, _m = line.split("\t")
            rows[ref] = (name, int(a), int(b))
    rs = refs(spec)
    if rs[0] not in rows or rs[-1] not in rows:
        return False
    name, a, _ = rows[rs[0]]
    _, _, b = rows[rs[-1]]
    sys.path.insert(0, str(ROOT))
    from build import config
    src = config.audio()["mh"]["path"] / name
    out.parent.mkdir(parents=True, exist_ok=True)
    inputs = ["-ss", f"{a / 1000:.3f}", "-to", f"{b / 1000:.3f}", "-i", str(src)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-af", leveled(inputs), "-ac", "1",
                    "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", str(out)], check=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", default=",".join(v for v, _ in VOICES))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--mh-only", action="store_true", help="only (re)cut Merritt Horn's clips")
    args = ap.parse_args()
    from kokoro import KPipeline
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    speech = dict(con.execute("SELECT p.ref, s.text FROM speech s JOIN paragraph p"
                              " ON p.id = s.paragraph_id"))
    langs = dict(VOICES)
    pipes = {}
    old = OUT / "bakeoff.json"
    meta = json.loads(old.read_text()) if old.exists() else {"voices": [], "rtf": {}}
    meta["samples"] = []
    for spec, what in SAMPLES:
        has = mh_clip(spec, OUT / "mh" / f"{spec.replace(':', '_')}.mp3")
        meta["samples"].append({"id": spec, "what": what, "mh": has,
                                "text": [speech[r] for r in refs(spec)]})
    print(f"Merritt Horn: {sum(s['mh'] for s in meta['samples'])} of {len(SAMPLES)} passages aligned")
    for voice in ([] if args.mh_only else args.voices.split(",")):
        lang = langs[voice]
        if lang not in pipes:
            pipes[lang] = KPipeline(lang_code=lang, device=args.device,
                                    repo_id="hexgrad/Kokoro-82M")
        made = took = 0.0
        for spec, _ in SAMPLES:
            parts = []
            for r in refs(spec):
                t0 = time.time()
                for res in pipes[lang](speech[r], voice=voice):
                    parts.append(res.audio.numpy())
                took += time.time() - t0
                parts.append(np.zeros(int(PAUSE * RATE), dtype=np.float32))
            wav = np.concatenate(parts[:-1])
            made += len(wav) / RATE
            encode(wav, OUT / voice / f"{spec.replace(':', '_')}.mp3")
        if voice not in meta["voices"]:
            meta["voices"].append(voice)
        meta["rtf"][voice] = round(made / took, 1)
        print(f"{voice:12} {made:6.0f} s of audio, {made / took:5.1f}x real time", flush=True)
    (OUT / "bakeoff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
