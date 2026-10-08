"""The listening test's Higgs Audio v2 voices (Boson AI), through transformers.

    make tts-bakeoff-higgs                 # 0:0.1 in each voice below
    ... -m tools.tts.bakeoff_higgs 0:0.1 1:0.1

Higgs Audio v2 is a 3.6B LLM with a 2.2B audio adapter, pretrained on ten
million hours of audio; native in transformers since 5.3, as
bosonai/higgs-tts-2-3b-base.  Its weights are under the Boson Higgs Audio 2
Community Licence (Llama 3 style: free below 100,000 annual active users, with
an attribution notice).  It reads text, not phonemes: a lexicon would be
respellings.

A voice is either described in words in the "scene" -- which imitates nobody --
or cloned from one of the generic prompt clips in Boson's repository (cloned to
~/Software/ml/src/higgs-audio for them).  Never from a real person's
recording, and never from Merritt Horn.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

from tools.tts.bakeoff import OUT, ROOT, encode

MODEL = "bosonai/higgs-tts-2-3b-base"
CLIPS = pathlib.Path.home() / "Software" / "ml" / "src" / "higgs-audio" / "examples" / "voice_prompts"
ROOM = "Audio is recorded in a quiet studio. A single narrator reads a book aloud."
# Described voices: the words are the voice.
DESCRIBED = {
    "higgs2_mature": "A mature man with a warm, deep American voice reads calmly and"
                     " reverently, at a measured pace, with excellent articulation.",
    "higgs2_story": "She speaks with a calm, gentle, and informative tone at a measured pace,"
                    " with excellent articulation and very clear audio.",
    "higgs2_british": "He speaks with a clear British accent, articulate and unhurried,"
                      " in the manner of a seasoned audiobook narrator.",
    "higgs2_male": "Male, American accent, moderate speaking rate, moderate pitch,"
                   " friendly tone, and very clear audio.",
}
# Cloned voices: Boson's generic prompt clips, with their transcripts.
CLONED = {"higgs2_en_man": "en_man", "higgs2_en_woman": "en_woman", "higgs2_belinda": "belinda"}


def conversation(text: str, voice: str) -> list[dict]:
    system = {"role": "system", "content": [{"type": "text", "text": "Generate audio following instruction."}]}
    if voice in DESCRIBED:
        scene = {"role": "scene", "content": [{"type": "text", "text": f"{ROOM} {DESCRIBED[voice]}"}]}
        return [system, scene, {"role": "user", "content": [{"type": "text", "text": text}]}]
    clip = CLIPS / CLONED[voice]
    return [system,
            {"role": "scene", "content": [{"type": "text", "text": ROOM}]},
            {"role": "user", "content": [{"type": "text", "text": clip.with_suffix(".txt").read_text().strip()}]},
            {"role": "assistant", "content": [{"type": "audio", "path": str(clip.with_suffix(".wav"))}]},
            {"role": "user", "content": [{"type": "text", "text": text}]}]


def main(argv: list[str]) -> int:
    import sqlite3
    import torch
    from transformers import AutoProcessor, HiggsAudioV2ForConditionalGeneration
    passages = argv or ["0:0.1"]
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    speech = dict(con.execute("SELECT p.ref, s.text FROM speech s JOIN paragraph p"
                              " ON p.id = s.paragraph_id"))
    processor = AutoProcessor.from_pretrained(MODEL, device_map="cuda")   # its audio decoder too
    model = HiggsAudioV2ForConditionalGeneration.from_pretrained(
        MODEL, device_map="cuda", dtype=torch.bfloat16)
    rate = 24000
    meta = json.loads((OUT / "bakeoff.json").read_text())
    for voice in list(DESCRIBED) + list(CLONED):
        made = took = 0.0
        for spec in passages:
            torch.manual_seed(7)
            inputs = processor.apply_chat_template(
                conversation(speech[spec], voice), add_generation_prompt=True, tokenize=True,
                return_dict=True, sampling_rate=rate, return_tensors="pt").to(model.device)
            t0 = time.time()
            out = model.generate(**inputs, max_new_tokens=2048, do_sample=True,
                                 temperature=0.3, top_p=0.95, top_k=50)
            took += time.time() - t0
            path = OUT / voice / f"{spec.replace(':', '_')}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            processor.save_audio(processor.batch_decode(out), str(path))
            import soundfile as sf
            audio, sr = sf.read(path, dtype="float32")
            audio = audio.mean(axis=1) if audio.ndim > 1 else audio
            made += len(audio) / sr
            encode(np.asarray(audio), path.with_suffix(".mp3"), sr)
            path.unlink()
        if voice not in meta["voices"]:
            meta["voices"].append(voice)
        meta["rtf"][voice] = round(made / took, 2)
        meta.setdefault("engines", {})[voice] = f"{MODEL} (transformers)"
        (OUT / "bakeoff.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        print(f"{voice:16} {made:5.0f} s of audio, {made / took:5.2f}x real time", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
