"""Higgs TTS 3 (Boson AI) through vLLM-Omni: the engine, a voice, and the checks
every chunk must pass before it is used.  The listening test
(tools/tts/bakeoff_higgs3.py) and the book (tools/tts/book.py) both read
through this, so what was chosen by ear is what the book is made with.

Higgs TTS 3 is a ~4B Qwen3 decoder over eight audio codebooks at 25 fps,
bosonai/higgs-tts-3-4b.  Its weights are under a research and non-commercial
licence whose Creator Use Grant covers audiobooks, provided the audio or the
page acknowledges "Boson AI's Higgs Audio".  It has no transformers code of its
own; vLLM-Omni (cloned to ~/Software/ml/src/vllm-omni, venv-vllm) serves it,
here offline, with tools/tts/higgs3.yaml.

A voice is cloned from a reference clip in var/tts/refs/ with its transcript
(tools/tts/refclip.py), or left to the model.  Text is read in chunks of a
sentence or two (tools/tts/chunk.py), and every chunk is checked twice before
it is used: here, for a drone, a dead pause or a cut-off end (`fault`), and by
Whisper, for its words (tools/tts/listen.py).  A chunk that fails either is
made again at the next seed (`make`).  Every try is kept in the chunk store
(tools/tts/store.py), so a second run makes only what is missing.

Import this before anything that imports vLLM: it sets vLLM's environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import time

# Whisper runs beside the engine in the aligner's venv, with the environment as
# it was before vLLM touched it -- CUDA_VISIBLE_DEVICES above all: the 3090 only.
ENV = dict(os.environ)
LISTEN = pathlib.Path(os.environ.get("ML", pathlib.Path.home() / "Software" / "ml")) / "venv-align" / "bin" / "python"

os.environ.setdefault("VLLM_USE_DEEP_GEMM", "0")
os.environ.setdefault("VLLM_MOE_USE_DEEP_GEMM", "0")
# vLLM's own top-k/top-p sampler, not FlashInfer's: FlashInfer ships no kernels
# for the 3090 (sm_86) and would compile them on the spot.
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")

import numpy as np

from tools.tts.store import Store, fingerprint

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MODEL = "bosonai/higgs-tts-3-4b"
DEPLOY = ROOT / "tools" / "tts" / "higgs3.yaml"
REFS = ROOT / "var" / "tts" / "refs"
RATE = 24000

WINDOW = 0.05                     # seconds: loudness is RMS over 50 ms
QUIET = -40                       # dB: below this a window is silence
PACE = (8, 25)                    # characters a second; Merritt Horn reads about 15
ALLOWANCE = 0.8                   # seconds of a chunk's pauses that are not reading
# Seconds of silence inside one chunk.  Within a reading the model pauses about
# 0.55 s after a sentence, and 99% of its pauses in the first trial were under
# 1.5 s; one longer is a hitch in the middle of a paragraph.
LONGEST_PAUSE = 1.5
BLIP, BLIP_GAP = 3, 6             # windows: a sound this short, after this much silence, ends nothing
FLAT = 10                         # samples at a chunk's own peak: the wave was cut flat there
ROUNDS = 8                        # synthesise, listen, re-make what failed; at most this often
SPEECH = -21.0                    # dB: every chunk's speech at this level before joining


def levels(pcm: np.ndarray, rate: int = RATE) -> np.ndarray:
    w = int(WINDOW * rate)
    n = len(pcm) // w
    return 20 * np.log10(np.sqrt((pcm[: n * w].reshape(n, w) ** 2).mean(axis=1) + 1e-12))


def trim(pcm: np.ndarray, rate: int = RATE) -> np.ndarray:
    """Cut the silence at both ends of a chunk.  One may run on into
    near-silence when the model fails to stop (0:0.1 once got 45 s of it), or
    begin with seconds of it (1:0.1 paused 3.5 s mid-paragraph).  Keeps 0.05 s
    before the first loud window and 0.15 s after the last.

    A stray sound at the very end goes too: the stream sometimes ends in a
    blip of 50-150 ms after the reading has finished and fallen silent ("Local
    systems, seven billion." then 0.4 s of silence, then a click at -15 dB) --
    20 of the first trial's 54 chunks that stopped while still sounding.  A
    real last word is longer, and were one ever cut, Whisper would miss it."""
    loud = np.nonzero(levels(pcm, rate) > QUIET)[0]
    if not len(loud):
        return pcm
    b = len(loud) - 1
    while b and loud[b - 1] == loud[b] - 1:
        b -= 1                                    # loud[b:] is the last loud run
    if b and loud[-1] - loud[b] + 1 <= BLIP and loud[b] - loud[b - 1] - 1 >= BLIP_GAP:
        loud = loud[:b]
    w = int(WINDOW * rate)
    return pcm[max(0, loud[0] * w - int(0.05 * rate)): min(len(pcm), (loud[-1] + 1) * w + int(0.15 * rate))]


def even(pcm: np.ndarray, rate: int = RATE) -> np.ndarray:
    """A chunk scaled so its speech -- the windows louder than QUIET -- sits at
    SPEECH.  Each chunk is a separate generation, and its level is the model's
    whim: most land within 1.5 dB of -21, but 15:2.10 once came out at -13.6,
    so the passage opened 8 dB louder than the rows that followed it."""
    lv = levels(pcm, rate)
    loud = lv > QUIET
    if not loud.any():
        return pcm
    now = 10 * np.log10(np.mean(10 ** (lv[loud] / 10)))
    return pcm * np.float32(10 ** ((SPEECH - now) / 20))


def fault(pcm: np.ndarray, text: str, rate: int = RATE) -> str | None:
    """Why a trimmed chunk cannot be a reading of `text`, or None.  Nothing in
    the waveform says a voice dropped or invented words, but the pace does:
    48:6.9's "The Gods are my caretakers; I shall not stray;" once came out
    as 42 s of steady drone, about one character a second.  Whisper's score
    for the passage was still 0.89, the rest being good, so this is checked
    per chunk, before Whisper.  The slowest pace allows for the pauses at a
    sentence's ends, which weigh most in the shortest: belinda took 2.3 s
    over "One. Supernaphim.", a list item read with care, not a fault."""
    took = len(pcm) / rate
    # Clipped: a real wave touches its peak at a sample or two; one cut flat
    # stays there.  The trial had 36 chunks at full scale, one with 313 samples
    # -- clipped by this script when it saved them (now `scaled`), not by the model.
    peak = float(np.abs(pcm).max()) if len(pcm) else 0.0
    if peak and int((np.abs(pcm) >= 0.999 * peak).sum()) >= FLAT:
        return f"clipped: {int((np.abs(pcm) >= 0.999 * peak).sum())} samples at its peak"
    slow, fast = len(text) / max(took - ALLOWANCE, 1e-3), len(text) / max(took, 1e-3)
    if slow < PACE[0] or fast > PACE[1]:
        return f"{fast:.1f} characters a second"
    # A reading ends in a moment of silence the model makes itself.  One that
    # stops while still sounding was cut off: in a word, in a drone (48:2.10
    # once ran on at -10 dB to the end), or just after starting a stray sound,
    # as "Constellations, seventy million" did -- a 130 ms blip, then nothing.
    if levels(pcm, rate)[-1] > QUIET:
        return "it stops while still sounding"
    run = longest = 0
    for quiet in levels(pcm, rate) <= QUIET:
        run = run + 1 if quiet else 0
        longest = max(longest, run)
    if longest * WINDOW > LONGEST_PAUSE:
        return f"a pause of {longest * WINDOW:.1f} s"
    return None


def scaled(pcm: np.ndarray) -> np.ndarray:
    """Within full scale, for saving as 16-bit: the model's output may pass 1.0,
    and np.clip would cut the wave flat.  Every chunk is brought to one level
    when joined (`even`), so turning one down here loses nothing."""
    peak = float(np.abs(pcm).max()) if len(pcm) else 0.0
    return pcm * np.float32(0.98 / peak) if peak > 0.98 else pcm


def made_by(ref: str | None) -> str:
    """What a chunk's audio depends on besides its words: the model, how it
    samples and how its codes become sound (the deploy config's sampling and
    connector settings -- not its batch sizes, which change only how fast),
    and the reference clip and its transcript."""
    import yaml
    deploy = yaml.safe_load(DEPLOY.read_text())
    how = {"connectors": deploy["connectors"], "async_chunk": deploy.get("async_chunk"),
           "sampling": [{k: v for k, v in s["default_sampling_params"].items() if k != "seed"}
                        for s in deploy["stages"]]}
    h = hashlib.sha256(json.dumps(how, sort_keys=True).encode()).hexdigest()[:12]
    return f"{MODEL} deploy:{h} " + fingerprint(*([REFS / f"{ref}.wav", REFS / f"{ref}.txt"] if ref else []))


class Engine:
    """The model, loaded once, and a voice: a reference clip and its transcript."""

    def __init__(self):
        from transformers import AutoTokenizer
        from vllm_omni import Omni
        from vllm_omni.model_executor.models.higgs_audio_v3.higgs_audio_v3_tokenizer import (
            HiggsAudioV3TokenizerAdapter)
        self.omni = Omni(model=MODEL, deploy_config=str(DEPLOY), trust_remote_code=True)
        self.default = list(self.omni.default_sampling_params_list)
        self.adapter = HiggsAudioV3TokenizerAdapter(AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True))
        self.codes = self.ref_text = None

    def close(self) -> None:
        """Stop the engine's stage processes.  Without this, an exception left
        them holding 17 GB of the 3090 and the script hung on exit."""
        self.omni.shutdown()

    def voice(self, ref: str | None) -> None:
        import soundfile as sf
        from vllm_omni.model_executor.models.higgs_audio_v3.higgs_audio_v3_tokenizer import (
            apply_delay_pattern, encode_reference_audio)
        self.codes = self.ref_text = None
        if ref:
            wav, sr = sf.read(REFS / f"{ref}.wav", always_2d=False)
            wav = wav.mean(axis=1) if wav.ndim == 2 else wav
            self.codes = apply_delay_pattern(encode_reference_audio(wav, int(sr)))
            self.ref_text = (REFS / f"{ref}.txt").read_text().strip()

    def _prompt(self, text: str) -> dict:
        import torch
        if self.codes is None:
            return {"prompt_token_ids": self.adapter.build_prompt(text)}
        ids = self.adapter.build_prompt(text, num_ref_tokens=int(self.codes.shape[0]), reference_text=self.ref_text)
        ids, where = self.adapter.prepare_prompt_for_engine(ids)
        return {"prompt_token_ids": ids, "additional_information": {
            "audio_input_ids": self.codes.to(torch.long),
            "audio_input_ids_mask": torch.ones(self.codes.shape[0], dtype=torch.bool),
            "audio_placeholder_positions": where}}

    def say(self, texts: list[str], seed: int) -> list[np.ndarray]:
        """Each text read at `seed`, trimmed, in the order given."""
        import torch
        talk = self.default[0].clone()
        talk.seed = seed
        outs = self.omni.generate([self._prompt(t) for t in texts], [talk, *self.default[1:]], use_tqdm=False)
        # They come back as they finish, not as sent; the request id begins
        # with the prompt's index ("3_<uuid>").  Unsorted, the chunks played out
        # of order and Whisper heard half the words.
        outs = sorted(outs, key=lambda o: int(str(o.request_id).split("_", 1)[0]))
        pcms = []
        for out in outs:
            mm = out.outputs[0].multimodal_output
            audio = mm.get("model_outputs", mm.get("audio"))
            if isinstance(audio, list):
                audio = torch.cat([torch.as_tensor(a).float().reshape(-1) for a in audio if a is not None])
            pcms.append(trim(torch.as_tensor(audio).float().cpu().reshape(-1).numpy()))
        return pcms


def make(engine: Engine, voice: str, keys: list[str], log=print, batch: int = 512) -> tuple[Store, float, float]:
    """Make every chunk in `keys` (already added to the voice's store) until
    each has a try with nothing wrong with it, or has used up its seeds.

    Rounds: every chunk due a try gets one at its next seed, those due the same
    seed together; a try at fault is made again at once; then Whisper hears
    every try that passed, and a chunk with words not heard as written is due
    again.  Returns the store, the seconds of audio made and the seconds taken.
    """
    import soundfile as sf
    store = Store(voice)
    made = took = 0.0
    for rnd in range(1, ROUNDS + 1):
        t0 = time.time()
        while True:
            due: dict[int, list[str]] = {}
            for k in keys:
                seed = store.next_seed(k)
                if seed is not None:
                    due.setdefault(seed, []).append(k)
            if not due:
                break
            for seed, ks in sorted(due.items()):
                for i in range(0, len(ks), batch):
                    part = ks[i:i + batch]
                    for k, pcm in zip(part, engine.say([store.data[k]["text"] for k in part], seed)):
                        pcm = scaled(pcm)
                        made += len(pcm) / RATE
                        why = fault(pcm, store.data[k]["text"])
                        path = store.audio(k, seed)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        sf.write(path, pcm, RATE, subtype="PCM_16")
                        store.record(k, seed, fault=why)
                        if why:
                            log(f"  seed {seed}: {why} -- {store.data[k]['text'][:60]!r}")
                    store.save()
        took += time.time() - t0
        if store.unheard():
            subprocess.run([str(LISTEN), "-m", "tools.tts.listen", voice], check=True, cwd=ROOT, env=ENV)
            store = Store(voice)
        open_ = [k for k in keys if store.done(k) is None]
        log(f"  round {rnd}: {len(keys) - len(open_)} of {len(keys)} chunks heard as written"
            f"  ({made / 3600:.2f} h made in {took / 3600:.2f} h)")
        if not any(store.next_seed(k) is not None for k in open_):
            break
    for k in open_:                   # every seed used, and still not right
        best = store.best(k)
        why = store.tries(k)[best].get("problems") if best is not None else ["every try at fault"]
        log(f"    unsettled {k} {store.data[k]['text'][:60]!r}: {'; '.join(why)}")
    return store, made, took
