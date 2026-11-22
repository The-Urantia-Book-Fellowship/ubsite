"""The compact copy of a human reading, every file the site uses: Opus, mono, in WebM.

    .venv/bin/python -m tools.audio.compact [key ...]      (mh and voyner with none)
    JOBS=12 .venv/bin/python -m tools.audio.compact voyner  (6 at once by default)

At the rate the config gives the reading (`compact`, Tigran's by ear on
2026-11-21: Merritt Horn 16 kbps, Григорий Войнер 14), into the directory it
names, var/audio/compact/<key>/, each file made from its master as
data/audio/<key>-files.tsv lists it and named as the master is, .webm for
.mp3.  A file data/audio/<key>-overrides.tsv leaves out ('-') is not made.

Each copy is held to its master: the master's SHA-256 checked against the
list first; a stereo master's mix to mono required to keep every band of
each channel (mono_keeps); and the copy's length required to be the
master's to 80 ms, so that the cuts in data/audio/<key>.tsv, made on the
master, hold for it.  Measured on 2026-11-21, every copy is the master's
length to the sample, 0.02 ms apart.

Resumable: a file already made is skipped, and a file is written as .part
and renamed whole.  Writes data/audio/<key>-compact.tsv, each copy's size,
length, SHA-256 and its master's SHA-256, which the build checks the
directory against by size (build/audio.py), and the offline list gives a
browser to hold a kept copy to.  The masters are read, never written.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import os
import re
import subprocess
import sys
import time

from build import audio, config

# libopus: speech at a low rate (voip and audio modes measured alike here),
# frames of 60 ms, nothing of the master's tags.
SETTINGS = ["-ac", "1", "-c:a", "libopus", "-vbr", "on", "-application", "voip",
            "-frame_duration", "60", "-map_metadata", "-1", "-f", "webm"]
JOBS = int(os.environ.get("JOBS", 6))       # half the cores: other work goes on here too
TOLERANCE_MS = 80


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for piece in iter(lambda: fh.read(1 << 20), b""):
            h.update(piece)
    return h.hexdigest()


def probe(path, entries: str) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def compact_name(name: str) -> str:
    """The copy's name: the master's, .webm for .mp3 (build/audio.py holds it so)."""
    if not name.endswith(".mp3"):
        raise SystemExit(f"compact: {name} is not an MP3")
    return name[:-4] + ".webm"


def mono_keeps(key: str, name: str, src) -> None:
    """A stereo master mixed to mono must keep every band's level: the mix's
    RMS, over the whole file and above 2 kHz and 6 kHz, no more than 1.5 dB
    under the quieter channel's.  A channel in opposite phase, or a delay
    between them, which cancels in the mix, fails it; a level differing
    between them, or hiss that is each channel's own, which the mix averages
    down (Merritt Horn's 148 files whose channels differ, 2026-11-21), does
    not.  One decode: the channels and their mix as three, each band an astats."""
    hp = lambda f: f"highpass=f={f}:poles=2,highpass=f={f}:poles=2,"   # noqa: E731
    stat = "astats=measure_overall=none:measure_perchannel=RMS_level"
    graph = (f"[0:a]pan=3c|c0=c0|c1=c1|c2=0.5*c0+0.5*c1,asplit=3[a][b][c];"
             f"[a]{stat},anullsink;[b]{hp(2000)}{stat},anullsink;[c]{hp(6000)}{stat}[out]")
    err = subprocess.run(["nice", "-n", "19", "ffmpeg", "-hide_banner", "-nostdin", "-i", str(src),
                          "-filter_complex", graph, "-map", "[out]", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    levels: dict[int, dict[int, float]] = {}
    for inst, ch, db in re.findall(r"\[Parsed_astats_(\d+) @ [^]]+\] Channel: (\d)\n.*?RMS level dB: (-?[\d.]+|-inf)",
                                   err, re.S):
        levels.setdefault(int(inst), {})[int(ch)] = float(db)
    if len(levels) != 3 or any(len(v) != 3 for v in levels.values()):
        raise SystemExit(f"{key} {name}: could not measure its channels\n{err[-2000:]}")
    for band, (_inst, v) in zip(("whole", "above 2 kHz", "above 6 kHz"), sorted(levels.items())):
        if v[3] < min(v[1], v[2]) - 1.5:
            raise SystemExit(f"{key} {name}: mono {band} is {v[3]} dB, the channels {v[1]} and {v[2]}")


def one(key: str, kbps: int, src_root, out_root, name: str, listed: tuple[int, int, str]) -> dict:
    """One master's copy, made where it is not, and measured."""
    _bytes, duration, master_sha = listed
    src, dst = src_root / name, out_root / compact_name(name)
    if not dst.exists():
        got = sha256(src)
        if got != master_sha:
            raise SystemExit(f"{key} {name}: the master's digest is {got}, the list's {master_sha}")
        if probe(src, "stream=channels").splitlines()[0] == "2":
            mono_keeps(key, name, src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src),
                        "-map", "0:a:0", "-b:a", f"{kbps}k", *SETTINGS, str(part)], check=True)
        d = float(probe(part, "format=duration"))
        if abs(d * 1000 - duration) > TOLERANCE_MS:
            part.unlink()
            raise SystemExit(f"{key} {name}: the copy is {d:.3f} s, the master {duration / 1000:.3f} s")
        part.replace(dst)
    d = round(float(probe(dst, "format=duration")) * 1000)
    if abs(d - duration) > TOLERANCE_MS:
        raise SystemExit(f"{key} {dst.name}: {d} ms, the master {duration} ms: delete it and make it again")
    return dict(file=compact_name(name), bytes=dst.stat().st_size, duration_ms=d,
                sha256=sha256(dst), master_sha256=master_sha)


def main(keys: list[str]) -> int:
    sources = config.audio()
    version = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    for key in keys:
        src = sources[key]
        if not src["compact"]:
            raise SystemExit(f"compact: the config gives {key} no compact copy")
        kbps, out_root = src["compact"]["kbps"], src["compact"]["path"]
        listed = audio.files(key)
        left_out = {name for name, start, _why in audio._optional(audio.DATA / f"{key}-overrides.tsv")
                    if start == "-"}
        names = sorted(set(listed) - left_out)
        # A copy no master here asks for: a master gone, or one left out since.
        stray = sorted(p.relative_to(out_root).as_posix() for p in out_root.rglob("*.webm")
                       if p.relative_to(out_root).as_posix() not in {compact_name(n) for n in names}) \
            if out_root.exists() else []
        if stray:
            raise SystemExit(f"compact: {key} has copies of no master it uses, in {out_root}:\n  "
                             + "\n  ".join(stray[:10]) + "\ndelete them, and run this again")
        t0, done, made = time.time(), 0, []
        with cf.ThreadPoolExecutor(JOBS) as ex:
            futs = [ex.submit(one, key, kbps, src["path"], out_root, n, listed[n]) for n in names]
            for f in cf.as_completed(futs):
                made.append(f.result())
                done += 1
                if done % 200 == 0 or done == len(names):
                    print(f"{key}: {done}/{len(names)} in {time.time() - t0:.0f} s", flush=True)
        made.sort(key=lambda m: m["file"])
        total = sum(m["bytes"] for m in made)
        hours = sum(m["duration_ms"] for m in made) / 3.6e6
        out = audio.DATA / f"{key}-compact.tsv"
        lines = [f"# {key}: the compact copy, Opus {kbps} kbps mono in WebM (tools/audio/compact.py)",
                 f"# ffmpeg -i MASTER -map 0:a:0 -b:a {kbps}k {' '.join(SETTINGS)}",
                 f"# {version}",
                 f"# {len(made)} files, {total / 1e9:.3f} GB, {hours:.2f} h, {total * 8 / hours / 3.6e6:.2f} kbps",
                 "\t".join(made[0])]
        lines += ["\t".join(str(m[c]) for c in made[0]) for m in made]
        out.write_text("\n".join(lines) + "\n")
        print(f"{out.relative_to(config.ROOT)}: {len(made)} files, {total / 1e9:.3f} GB, {hours:.2f} h,"
              f" in {time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [k for k, v in config.audio().items() if v["compact"]]))
