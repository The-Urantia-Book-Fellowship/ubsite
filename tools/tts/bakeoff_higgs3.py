"""The listening test's Higgs TTS 3 voices (Boson AI), through vLLM-Omni.

    make tts-bakeoff-higgs3                 # 0:0.1 in each voice below

The engine, the voices and the checks every chunk passes are in
tools/tts/higgs3.py, shared with the book (tools/tts/book.py).  Each voice is
cloned from a reference clip in var/tts/refs/ -- Kokoro's Michael, Higgs v2's
described "mature" voice (cleaned of its hum), Boson's generic belinda clip --
or left to the model.
"""

from __future__ import annotations

import json
import sys

from tools.tts.higgs3 import MODEL, RATE, Engine, even, made_by, make   # first: it sets vLLM's environment

import numpy as np

from tools.tts.bakeoff import OUT, ROOT, encode

VOICES = {"higgs3_auto": None, "higgs3_michael": "am_michael",
          "higgs3_mature": "higgs2_mature_clean", "higgs3_belinda": "belinda"}


def main(argv: list[str]) -> int:
    import argparse
    import sqlite3
    import soundfile as sf
    from tools.tts.bakeoff import SAMPLES
    ap = argparse.ArgumentParser()
    ap.add_argument("passages", nargs="*", default=["0:0.1"],
                    help='refs such as 1:0.1 or 48:6.9-14, or "all" for the nine test passages')
    ap.add_argument("--voices", help="comma-separated, from VOICES")
    args = ap.parse_args(argv)
    passages = [s for s, _ in SAMPLES] if args.passages == ["all"] else args.passages
    voices = {v: r for v, r in VOICES.items() if not args.voices or v in args.voices.split(",")}
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    speech = dict(con.execute("SELECT p.ref, s.text FROM speech s JOIN paragraph p"
                              " ON p.id = s.paragraph_id"))
    engine = Engine()
    meta = json.loads((OUT / "bakeoff.json").read_text())
    from tools.tts.bakeoff import refs as expand
    from tools.tts.chunk import chunks
    from tools.tts.store import Store, key
    for voice, ref in voices.items():
        engine.voice(ref)
        by = made_by(ref)
        plan = {spec: [(r, key(by, c), c) for r in expand(spec) for c in chunks(speech[r])]
                for spec in passages}
        store = Store(voice)
        for pieces in plan.values():
            for _r, k, c in pieces:
                store.add(k, c)
        store.save()
        keys = list(dict.fromkeys(k for pieces in plan.values() for _r, k, _c in pieces))
        store, made, took = make(engine, voice, keys, log=lambda m: print(f"  {voice}{m}", flush=True))

        # Each passage from its chunks' best tries, each at one speech level,
        # joined with the pauses the site will have.
        for spec, pieces in plan.items():
            parts, prev, short = [], None, []
            for r, k, c in pieces:
                seed = store.best(k)
                if seed is None:
                    raise SystemExit(f"{voice} {r}: no try of {c[:50]!r} passed the synthesis check")
                if store.done(k) is None:
                    short.append(f"{r} {store.tries(k)[seed]['problems']}")
                pcm, _ = sf.read(store.audio(k, seed), dtype="float32")
                if prev is not None:
                    parts.append(np.zeros(int((0.7 if r != prev else 0.3) * RATE), dtype=np.float32))
                parts.append(even(pcm))
                prev = r
            wav = np.concatenate(parts)
            name = spec.replace(":", "_")
            # The joined passage too, so a change in how clips are encoded
            # never needs the GPU again.
            raw = OUT / "raw" / voice / f"{name}.wav"
            raw.parent.mkdir(parents=True, exist_ok=True)
            sf.write(raw, wav, RATE, subtype="FLOAT")
            encode(np.clip(wav, -1, 1), OUT / voice / f"{name}.mp3", RATE)
            print(f"  {voice} {spec}: {len(pieces)} chunks" +
                  (f"; kept despite Whisper: {short}" if short else ""), flush=True)
        if voice not in meta["voices"]:
            meta["voices"].append(voice)
        if made > 120:                # a few retries are no measure of speed
            meta["rtf"][voice] = round(made / took, 2)
        meta.setdefault("engines", {})[voice] = f"{MODEL} (vLLM-Omni), ref {ref or 'none'}"
        (OUT / "bakeoff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        print(f"{voice:16} {made:5.0f} s of audio made, {made / took if took else 0:5.2f}x real time", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
