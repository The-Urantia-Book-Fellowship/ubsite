"""The whole book in the AI voice: every heading and paragraph of the spoken
text (table `speech`), made, checked and assembled into one MP3 per section.

    make tts                    make what is missing, then assemble (GPU, resumable)
    make tts-assemble           assemble only, from what has been made (no GPU)

Making.  Each unit's text is cut into chunks (tools/tts/chunk.py), and each
chunk is made and checked by tools/tts/higgs3.py `make` -- the synthesis check,
then Whisper -- and made again at another seed until it passes or its seeds
are used up.  The book goes through in blocks of BLOCK chunks in reading order,
so a fault that would spoil every block shows up in the first hour, not the
last.  Every try is kept (tools/tts/store.py, var/tts/chunks/), keyed by its
words and by what made it, so stopping and starting again loses nothing and a
corrected paragraph costs only its own chunks.

Assembling.  A section is one file, its heading then its paragraphs, as
Merritt Horn's are: within a file the browser plays straight on, where a file
per paragraph would load one at every paragraph and leave a gap of its own.
Each chunk's best try is brought to one speech level (`even`) and the chunks
joined with the pause their last character calls for; the file is measured and
brought to Merritt Horn's loudness, -18 LUFS, so switching voices does not jump.
A file is named by what went into it, so an unchanged section is never encoded
twice and a changed one never served stale.  Out:

    var/audio/ai/<voice>/paperNNN/NNN_SS.<hash>.mp3
    data/audio/ai.tsv           ref, file, start_ms, end_ms, speech_sha
    data/audio/ai-files.tsv     file, bytes, duration_ms, sha256
    data/audio/ai-unsettled.tsv the chunks used though no try was heard as written
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
import subprocess
import sys

from tools.tts.higgs3 import RATE, ROOT, even, made_by   # first: it sets vLLM's environment

import numpy as np

from tools.tts.chunk import chunks
from tools.tts.store import Store, key

VOICE, REF = "higgs3_mature", "higgs2_mature_clean"
BLOCK = 2000                      # chunks: about five hours of reading
OUT = ROOT / "var" / "audio" / "ai" / VOICE
DATA = ROOT / "data" / "audio"
LOUDNESS = -18.0                  # LUFS: Merritt Horn's, measured on P001_00, P050_03, P150_05
CEILING = 10 ** (-1.5 / 20)
BITRATE = "64k"                   # CBR, mono, 24 kHz: a browser seeks a CBR file exactly
# Pauses, in seconds, added to what each chunk keeps of its own (0.05 s
# before, 0.15 s after).  Within a paragraph, by how the chunk ends: a
# sentence, a clause at a comma or dash, or a long sentence halved where it has
# no punctuation, which wants no more pause than a breath.
AFTER_SENTENCE, AFTER_COMMA, AFTER_NOTHING = 0.3, 0.15, 0.05
AFTER_PARAGRAPH, AFTER_HEADING = 0.7, 1.0
LEAD, TAIL = 0.2, 0.5             # silence at a file's start and end
EARLY = 0.2                       # a segment starts this much before its first word, so a seek never clips it


def units(con, papers: set[int] | None = None) -> list[tuple]:
    """(section_id, paper, section, ref, text, sha) in reading order; ref None for a heading."""
    rows = con.execute(
        "SELECT s.section_id, x.paper_n, x.n, p.ref, s.text, s.sha FROM speech s"
        " JOIN section x ON x.id = s.section_id LEFT JOIN paragraph p ON p.id = s.paragraph_id"
        " ORDER BY s.section_id, COALESCE(p.ord, -1)").fetchall()
    return [r for r in rows if papers is None or r[1] in papers]


def pause(chunk: str) -> float:
    c = chunk.rstrip().rstrip("”’\")")
    return AFTER_SENTENCE if c[-1:] in ".!?;:" else AFTER_COMMA if c[-1:] in ",—" else AFTER_NOTHING


def make_all(con, papers, block: int) -> int:
    from tools.tts.higgs3 import Engine, make
    by = made_by(REF)
    store = Store(VOICE)
    keys = []
    for *_, text, _sha in units(con, papers):
        for c in chunks(text):
            k = key(by, c)
            store.add(k, c)
            keys.append(k)
    store.save()
    keys = list(dict.fromkeys(keys))
    todo = [k for k in keys if store.next_seed(k) is not None or store.waiting(k)]
    print(f"{len(keys):,} chunks, {len(todo):,} to make or hear", flush=True)
    if not todo:
        return 0
    engine = Engine()
    try:
        engine.voice(REF)
        made = took = 0.0
        for i in range(0, len(todo), block):
            part = todo[i:i + block]
            print(f"block {i // block + 1} of {-(-len(todo) // block)}: {len(part)} chunks,"
                  f" from {store.data[part[0]]['text'][:50]!r}", flush=True)
            store, m, t = make(engine, VOICE, part, log=lambda s: print(s, flush=True))
            made, took = made + m, took + t
            print(f"  so far {made / 3600:.1f} h of audio in {took / 3600:.1f} h,"
                  f" {made / took if took else 0:.2f}x real time", flush=True)
    finally:
        engine.close()
    return 0


def recheck(con, papers) -> int:
    """The synthesis check as it is now, over every try made that passed it as
    it was: when `fault` changes, the chunks already made are held to it too.
    A try that fails now is recorded so, and `make tts` makes its chunk again."""
    import soundfile as sf
    from tools.tts.higgs3 import fault
    by = made_by(REF)
    store = Store(VOICE)
    keys = {key(by, c) for *_, text, _sha in units(con, papers) for c in chunks(text)}
    n = 0
    for k in sorted(keys & store.data.keys()):
        for seed, t in store.tries(k).items():
            if t.get("fault") is None:
                why = fault(sf.read(store.audio(k, seed), dtype="float32")[0], store.data[k]["text"])
                if why:
                    store.record(k, seed, fault=why)
                    n += 1
                    print(f"  {why}: seed {seed} {store.data[k]['text'][:60]!r}", flush=True)
    store.save()
    print(f"{n} tries now at fault", flush=True)
    return 0


def rehear(con, papers) -> int:
    """Forget what Whisper made of every try that passed it, so `make tts`
    hears them again: when the listener changes, the chunks already passed
    are held to it too."""
    by = made_by(REF)
    store = Store(VOICE)
    keys = {key(by, c) for *_, text, _sha in units(con, papers) for c in chunks(text)}
    n = 0
    for k in sorted(keys & store.data.keys()):
        for seed, t in store.tries(k).items():
            if t.get("fault") is None and t.get("problems") == []:
                t.pop("problems")
                t.pop("on_sheet", None)
                n += 1
    store.save()
    print(f"{n} tries to be heard again", flush=True)
    return 0


def leveled(pcm: np.ndarray) -> str:
    """The filter that brings `pcm` to LOUDNESS: one gain, measured, and a
    limiter for the peaks (tools/tts/bakeoff.py `leveled`, which found that a
    single-pass loudnorm rides the gain)."""
    import json
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(RATE), "-ac", "1",
                          "-i", "-", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         input=pcm.astype(np.float32).tobytes(), capture_output=True, check=True).stderr.decode()
    measured = float(json.loads(err[err.rindex("{"):err.rindex("}") + 1])["input_i"])
    return f"volume={LOUDNESS - measured:.2f}dB,alimiter=limit={CEILING:.4f}:level=false"


def assemble(con, papers) -> int:
    import soundfile as sf
    by = made_by(REF)
    store = Store(VOICE)
    sections: dict[int, list[tuple]] = {}
    for u in units(con, papers):
        sections.setdefault(u[0], []).append(u)
    segs, files, unsettled, missing = [], [], [], []
    for sid, us in sections.items():
        paper, n = us[0][1], us[0][2]
        plan = []                                   # (ref, sha, [(key, chunk)])
        for _sid, _p, _n, ref, text, sha in us:
            plan.append((ref, sha, [(key(by, c), c) for c in chunks(text)]))
        best = {k: store.best(k) if k in store.data else None for _r, _s, ks in plan for k, _c in ks}
        gone = [c for _r, _s, ks in plan for k, c in ks if best[k] is None]
        if gone:
            missing.append((f"{paper}:{n}", len(gone)))
            continue
        for ref, _sha, ks in plan:
            for k, c in ks:
                if store.done(k) is None:
                    unsettled.append((ref or f"{paper}:{n}", c, store.tries(k)[best[k]].get("problems")))
        # The file's name is a hash of everything that goes into it, so an
        # unchanged section is not encoded again.
        recipe = repr([(ref, [(k, best[k]) for k, _c in ks]) for ref, _s, ks in plan]) + \
            repr((AFTER_SENTENCE, AFTER_COMMA, AFTER_NOTHING, AFTER_PARAGRAPH, AFTER_HEADING,
                  LEAD, TAIL, EARLY, LOUDNESS, BITRATE))
        name = f"paper{paper:03d}/{paper:03d}_{n:02d}.{hashlib.sha256(recipe.encode()).hexdigest()[:10]}.mp3"
        parts, starts, t = [np.zeros(int(LEAD * RATE), np.float32)], [], LEAD
        for ui, (ref, _sha, ks) in enumerate(plan):
            starts.append(t)
            for ci, (k, c) in enumerate(ks):
                pcm, _ = sf.read(store.audio(k, best[k]), dtype="float32")
                pcm = even(pcm)
                last = ci == len(ks) - 1
                gap = (TAIL if ui == len(plan) - 1 else AFTER_HEADING if ref is None else AFTER_PARAGRAPH) \
                    if last else pause(c)
                parts += [pcm, np.zeros(int(gap * RATE), np.float32)]
                t += (len(pcm) + int(gap * RATE)) / RATE
        wav = np.concatenate(parts)
        total = len(wav) / RATE
        out = OUT / name
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp.mp3")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                            "-af", leveled(wav), "-ar", str(RATE), "-c:a", "libmp3lame", "-b:a", BITRATE,
                            str(tmp)], input=np.clip(wav, -1, 1).astype(np.float32).tobytes(), check=True)
            tmp.replace(out)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", str(out)], capture_output=True, text=True, check=True).stdout)
        data = out.read_bytes()
        files.append((name, len(data), int(dur * 1000), hashlib.sha256(data).hexdigest()))
        # Segments tile the file: each starts EARLY before its first word (the
        # first at 0) and ends where the next starts (the last at the end of
        # the audio made).
        bounds = [0.0] + [max(s - EARLY, 0.0) for s in starts[1:]] + [min(total, int(dur * 1000) / 1000)]
        for (ref, sha, _ks), a, b in zip(plan, bounds, bounds[1:]):
            segs.append((ref or f"{paper}:{n}", name, int(round(a * 1000)), int(round(b * 1000)), sha))
        print(f"  {paper}:{n} {total / 60:5.1f} min  {name}", flush=True)
    if missing:
        print(f"not assembled, chunks never made: {missing[:10]}{' ...' if len(missing) > 10 else ''}")
    if papers is None and not missing:
        write(segs, files, unsettled, by)
    elif papers is not None:
        # A trial: the same three files, beside its audio, never in data/.
        write(segs, files, unsettled, by, where=ROOT / "var" / "tts" / "trial", prune=False)
    print(f"{len(files)} files, {sum(f[2] for f in files) / 3600000:.1f} h;"
          f" {len(unsettled)} chunks used though not heard as written", flush=True)
    return 1 if missing else 0


def write(segs, files, unsettled, by, where: pathlib.Path = DATA, prune: bool = True) -> None:
    where.mkdir(parents=True, exist_ok=True)

    def tsv(path: pathlib.Path, comment: str, header: str, rows) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(f"# {comment}\n{header}\n" + "".join("\t".join(map(str, r)) + "\n" for r in rows),
                       encoding="utf-8")
        tmp.replace(path)
    tsv(where / "ai.tsv", f"{VOICE}: {by}. tools/tts/book.py", "ref\tfile\tstart_ms\tend_ms\tspeech_sha", segs)
    tsv(where / "ai-files.tsv", f"under var/audio/ai/{VOICE}", "file\tbytes\tduration_ms\tsha256", files)
    tsv(where / "ai-unsettled.tsv", "chunks used though no try was heard as written, with what Whisper heard",
        "ref\tchunk\tproblems", [(r, c, "; ".join(p or [])) for r, c, p in unsettled])
    if not prune:
        return
    # A section made again has a new name; the file it replaces is listed
    # nowhere now, and the build fails on an unlisted file.
    listed = {name for name, *_ in files}
    for f in sorted(OUT.glob("paper*/*.mp3")):
        if f.relative_to(OUT).as_posix() not in listed:
            print(f"  removed {f.relative_to(OUT)}, replaced", flush=True)
            f.unlink()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", help="e.g. 1,30,118 or 0-5: these only (a trial); nothing in data/ is written")
    ap.add_argument("--assemble", action="store_true", help="assemble only; no GPU")
    ap.add_argument("--recheck", action="store_true",
                    help="apply the synthesis check as it is now to every try made; no GPU")
    ap.add_argument("--rehear", action="store_true",
                    help="have Whisper hear again every try that passed it; then run without it")
    ap.add_argument("--block", type=int, default=BLOCK)
    args = ap.parse_args(argv)
    papers = None
    if args.papers:
        papers = set()
        for part in args.papers.split(","):
            a, _, b = part.partition("-")
            papers |= set(range(int(a), int(b or a) + 1))
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    if args.recheck:
        return recheck(con, papers)
    if args.rehear:
        return rehear(con, papers)
    if not args.assemble:
        make_all(con, papers, args.block)
    return assemble(con, papers)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
