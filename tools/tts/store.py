"""Every chunk a voice has read, each try kept, with what was found wrong with it.

    var/tts/chunks/<voice>.json            {key: {"text": ..., "tries": {seed: {...}}}}
    var/tts/chunks/<voice>/<key>.<seed>.flac

A key names the words and how they were made -- the model, the reference clip,
the deploy config -- so a new reference or a corrected text is a new key and
never reuses old audio.  A try records `fault`, the synthesis check's verdict
(pace, a long pause, a cut-off end), and, once Whisper has listened, `problems`
(the words not heard as written) and `said`.  A chunk is done when one try has
neither fault nor problems.

Stdlib only: the synthesis venv writes it and the aligner's venv (Whisper)
reads and updates it, one after the other, never at once.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHUNKS = ROOT / "var" / "tts" / "chunks"
FIRST_SEED = 42                   # the deploy config's own
TRIES = 8                         # seeds per chunk before the best try is taken


def key(made: str, text: str) -> str:
    return hashlib.sha256(f"{made}\n{text}".encode()).hexdigest()[:16]


def fingerprint(*paths: pathlib.Path) -> str:
    """Short hashes of the files a reading depends on, for `made`."""
    return " ".join(f"{p.name}:{hashlib.sha256(p.read_bytes()).hexdigest()[:12]}" for p in paths)


class Store:
    def __init__(self, voice: str):
        self.voice = voice
        self.path = CHUNKS / f"{voice}.json"
        self.data: dict = json.loads(self.path.read_text()) if self.path.exists() else {}

    def audio(self, k: str, seed: int) -> pathlib.Path:
        return CHUNKS / self.voice / f"{k}.{seed}.flac"

    def add(self, k: str, text: str) -> None:
        self.data.setdefault(k, {"text": text, "tries": {}})

    def record(self, k: str, seed: int, **verdict) -> None:
        self.data[k]["tries"].setdefault(str(seed), {}).update(verdict)

    def tries(self, k: str) -> dict[int, dict]:
        return {int(s): t for s, t in self.data[k]["tries"].items()}

    def done(self, k: str) -> int | None:
        """The seed of a try with nothing wrong with it."""
        for seed, t in sorted(self.tries(k).items()):
            if t.get("fault") is None and t.get("problems") == []:
                return seed
        return None

    def waiting(self, k: str) -> bool:
        """A try that passed the synthesis check and that Whisper has not heard."""
        return any(t.get("fault") is None and "problems" not in t for t in self.tries(k).values())

    def next_seed(self, k: str) -> int | None:
        if self.done(k) is not None or self.waiting(k):
            return None
        tried = self.tries(k)
        return FIRST_SEED + len(tried) if len(tried) < TRIES else None

    def unheard(self) -> list[tuple[str, int]]:
        return [(k, s) for k in self.data for s, t in sorted(self.tries(k).items())
                if t.get("fault") is None and "problems" not in t]

    def best(self, k: str) -> int | None:
        """The try to use: one with nothing wrong, else the one Whisper found
        least wrong with, else None (every try failed the synthesis check)."""
        heard = [(len(t["problems"]), s) for s, t in self.tries(k).items()
                 if t.get("fault") is None and "problems" in t]
        return min(heard)[1] if heard else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        os.replace(tmp, self.path)
