"""Whisper listens to every chunk a voice has made and not yet been heard, and
records which of its words were not heard as written.

    ~/Software/ml/venv-align/bin/python -m tools.tts.listen VOICE...

The synthesis check (tools/tts/higgs3.py `fault`) catches a drone, a
dead pause, a cut-off end -- nothing that needs the words.  This catches the
words: Mature once dropped "great" from "there exists great confusion" and read
"designated" as "delegated", with every pace and pause in order.

Whisper is not the text's equal, so four differences are not held against a
reading, because Merritt Horn gets them too: a coined name spelled by ear
("Orvonton" as "orvantan"), a number written in digits ("1934" for "nineteen
thirty-four"), a compound split in two ("super universe"), and a word that
sounds like the text's ("corps" as "core", "Son" as "sun"), which no listener
could tell apart.  A word in the dictionary that is left out, changed or added
is a problem.

Batched Whisper drops stretches of speech it plainly heard (CLAUDE.md §7.13):
in the first trial it missed "the immensity" and "today and as you are" in
readings that held them.  So a try with a problem is heard again on its own,
unbatched, and that hearing decides.  It cannot supply a word the voice left
out -- the word is not in the audio -- only take back one Whisper lost.

Chunks are heard several to a sheet, a second of silence between them, which
lets the batched pipeline run at its speed rather than one short clip at a time.

What Whisper heard is kept as well, word by word with its times and
confidence, in var/tts/chunks/<voice>.words.jsonl, one line per try: the
review (tools/tts/review.py) looks there for what a word check cannot see, a
word dragged out or a pause where the text has none.
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys

import numpy as np

from tools.align.align import canon, heard, tokens
from tools.tts.store import Store

RATE = 16000
GAP = 1.0                         # seconds of silence between chunks on a sheet
SHEET = 120.0                     # seconds of audio per sheet
NAME_LIKENESS = 0.5               # a coined name heard this close counts as said
# Words a listener cannot tell apart, and Whisper's other spellings, mapped to
# one form on both sides before comparing.  Each was heard in the first trial
# (Papers 1, 30, 144): "the Corps of Mortal Finaliters" as "core", 15 times.
ALIKE = {"core": "corps", "sun": "son", "suns": "sons", "sensors": "censors", "aides": "aids",
         "ought": "aught", "affect": "effect", "roles": "rols", "role": "rol",
         "advisors": "advisers", "sunfused": "sonfused",
         # A list's letter, as it sounds: "C. Trinitized Sons." was heard "see".
         "see": "c", "sea": "c", "bee": "b", "be": "b", "dee": "d"}


def dictionary() -> set[str]:
    with open("/usr/share/dict/words", encoding="utf-8") as f:
        return {canon(w.strip().lower().replace("'s", "")) for w in f if w.strip()}


def numbers() -> set[str]:
    from build.speech import ONES, SCALES, TENS
    return {w for w in ONES + TENS + SCALES + ["hundred", "and", "a"] if w and w != "_"}


def sound(t: str) -> str:
    """A token as it sounds, near enough: ALIKE, "residents" and "residence"
    as one, and a doubled letter as one ("nonplussed", "worshipping")."""
    t = ALIKE.get(t, t)
    t = re.sub(r"nts$", "nce", t)
    return re.sub(r"(.)\1", r"\1", t)


def differences(want: list[str], said: list[str], known: set[str], number: set[str]):
    """(i1, i2, j1, j2, what) for each difference between the text's tokens and
    Whisper's that is not Whisper's own doing."""
    sw, ss = [sound(w) for w in want], [sound(w) for w in said]
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sw, ss, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        a, b = want[i1:i2], said[j1:j2]
        if a and b and sound("".join(a)) == sound("".join(b)):
            continue                                  # "superuniverse" / "super universe"
        if a and b and all(w in number for w in a + b):
            continue                                  # "nineteen" / "one thousand nine hundred"
        if (a and b and not any(w in known for w in a)
                and difflib.SequenceMatcher(None, "".join(a), "".join(b)).ratio() >= NAME_LIKENESS):
            continue                                  # "orvonton" / "orvantan"
        yield i1, i2, j1, j2, f"{' '.join(a) or '-'} -> {' '.join(b) or '-'}"


def problems(text: str, said: list[str], known: set[str], number: set[str]) -> list[str]:
    return [what for *_, what in differences(tokens(text), said, known, number)]


def whole_numbers(words: list[tuple]) -> list[tuple]:
    """Whisper writes "993,408" as two words, "993" and ",408"; spoken one by
    one they lose their "thousand", and "70,000,000" became "seventy zero
    zero".  A word that begins with a comma or point and a digit continues the
    number before it."""
    out: list[tuple] = []
    for start, end, word, p in words:
        w = word.strip()
        if out and w[:1] in ",." and w[1:2].isdigit() and out[-1][2].strip()[-1:].isdigit():
            s0, _e, w0, p0 = out[-1]
            out[-1] = (s0, end, w0.rstrip() + w, min(p0, p))
        else:
            out.append((start, end, word, p))
    return out


def hear_alone(model, path, text: str, known: set[str], number: set[str]) -> list[str]:
    """The try heard by itself: unbatched, beam search, half a second of
    silence either side, nothing carried over from a previous text."""
    pad = np.zeros(RATE // 2, np.float32)
    segs, _ = model.transcribe(np.concatenate([pad, load(path), pad]), language="en", beam_size=5,
                               condition_on_previous_text=False, word_timestamps=True)
    said, _times = heard(whole_numbers([(w.start, w.end, w.word, w.probability)
                                        for s in segs for w in s.words]))
    return problems(text, said, known, number)


def load(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def main(voices: list[str]) -> int:
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    known, number = dictionary(), numbers()
    pipe = None
    for voice in voices:
        store = Store(voice)
        todo = store.unheard()
        if not todo:
            continue
        if pipe is None:
            pipe = BatchedInferencePipeline(WhisperModel("large-v3", device="cuda", compute_type="float16"))
        failed, rescued, n = 0, 0, len(todo)
        while todo:
            # A sheet: chunks end to end, a second of silence between, and
            # where each one lies on it.
            # Never two tries of one chunk on a sheet: against its text twice
            # over, the alignment matched words across the copies, and a try
            # that left out "great" was passed while the next, whole, was failed.
            parts, spans, t, sheet, later = [], [], 0.0, [], []
            while todo and (not sheet or t < SHEET):
                k, seed = todo.pop(0)
                if any(k == k2 for k2, _ in sheet):
                    later.append((k, seed))
                    continue
                x = load(store.audio(k, seed))
                parts += [x, np.zeros(int(GAP * RATE), np.float32)]
                spans.append((t, t + len(x) / RATE))
                sheet.append((k, seed))
                t += len(x) / RATE + GAP
            todo = later + todo
            segs, _ = pipe.transcribe(np.concatenate(parts), language="en", batch_size=8,
                                      word_timestamps=True)
            segs = list(segs)             # a generator: read twice below
            # The sheet's words against the sheet's text, as one: Whisper times
            # a chunk's first word into the silence before it, so words placed
            # by their times landed in the wrong chunk ("which" at the end of
            # one and missing from the next).  A difference belongs to every
            # chunk its text is in.  A word with no text to it belongs to the
            # chunks either side of where it falls, both: in the trial an added
            # "Could" ("Could beings who could know God ... in return?") was
            # timed into the pause before its chunk, blamed on the chunk before,
            # which was made again while the one at fault passed.  Each chunk
            # blamed is then heard alone, which clears the innocent one.
            said, _times = heard(whole_numbers([(w.start, w.end, w.word, w.probability)
                                               for s in segs for w in s.words]))
            want, owner = [], []
            for i, (k, _seed) in enumerate(sheet):
                t = tokens(store.data[k]["text"])
                want += t
                owner += [i] * len(t)
            found = [[] for _ in sheet]
            for i1, i2, j1, j2, what in differences(want, said, known, number):
                at = range(i1, i2) if i2 > i1 else [i for i in (i1 - 1, i1) if 0 <= i < len(want)]
                for o in sorted({owner[i] for i in at}):
                    found[o].append(what)
            # Whisper's own words, each given to the chunk its end falls in or
            # nearest: a word's end is where Whisper is sure (CLAUDE.md §7.14).
            words = [[] for _ in sheet]
            for s in segs:
                for w in s.words:
                    i = min(range(len(spans)), key=lambda i: max(spans[i][0] - w.end, w.end - spans[i][1], 0))
                    words[i].append([w.word.strip(), round(w.start - spans[i][0], 2),
                                     round(w.end - spans[i][0], 2), round(w.probability, 3)])
            with open(store.path.with_suffix(".words.jsonl"), "a", encoding="utf-8") as f:
                for i, (k, seed) in enumerate(sheet):
                    f.write(json.dumps({"k": k, "seed": seed, "words": words[i]}, ensure_ascii=False) + "\n")
            for i, (k, seed) in enumerate(sheet):
                if found[i]:
                    alone = hear_alone(pipe.model, store.audio(k, seed), store.data[k]["text"], known, number)
                    store.record(k, seed, problems=alone, on_sheet=found[i])
                    rescued += not alone
                else:
                    store.record(k, seed, problems=[])
                failed += bool(store.tries(k)[seed]["problems"])
            store.save()
        print(f"{voice}: heard {n} chunks, {failed} with words not heard as written"
              f" ({rescued} more heard right only when heard alone)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
