"""List a recording directory, file by file: data/audio/<key>-files.tsv.

    .venv/bin/python -m tools.audio.manifest mh

The list pins the recordings the way a commit pins a repo: every MP3 with its
size, duration and SHA-256.  `make data` checks the directory against it on
every build -- by size, which is cheap -- and refuses a file the list does not
name, or a listed file that has gone or changed size.  Rerun this only when the
recordings really have changed, and review the diff.

Durations are ffprobe's, in milliseconds: what a player takes the file's
length to be.  Where that is not its length -- a file with no Xing/Info frame
whose frames are never padded, so that the bit rate they name overstates them,
as in 1,358 of Григорий Войнер's 1,627 -- the duration listed is the frames',
counted (build/mp3.py), and the file goes into data/audio/<key>-frames.tsv
too: where its ID3v2 tag ends, how many frames there are, in how many bytes,
and the first one's header, from which the build makes the Info frame the file is
served with, and the SHA-256 of the file so served.  A reading with no such
file has no such list.

The files are read, never written.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def probe(path: pathlib.Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return round(float(out) * 1000)


FRAMES_HEAD = """\
# The files of this reading that a player would take for shorter than they are:
# no Xing/Info frame, and frames never padded, so that their bytes at the bit rate
# they name are not their length (build/mp3.py).  Each is served with an Info frame
# made by the build from this line: where it is put, which is where the ID3v2 tag
# ends, how many frames there are, their bytes, and the first one's header; and
# the SHA-256 of the file as it is then sent, which a browser keeping it offline
# holds it to.  The duration <key>-files.tsv lists for it is these frames'.
# tools/audio/manifest.py
"""


def main(argv: list[str]) -> int:
    from build import config, mp3
    key = argv[0] if argv else "mh"
    src = config.audio()[key]
    files = sorted(src["path"].glob(src["glob"]))
    out = ROOT / "data" / "audio" / f"{key}-files.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = ["file\tbytes\tduration_ms\tsha256"]
    frames = []
    for i, f in enumerate(files, 1):
        name = f.relative_to(src["path"]).as_posix()
        with open(f, "rb") as fh:
            data = fh.read()
        s = mp3.scan(data)
        if mp3.misjudged(s):
            # Found by proportion, a place is the place only where the frames
            # are all of a size and nothing stands between them.
            if s.sizes != 1 or s.junk:
                raise SystemExit(f"manifest: {name} needs a length frame, and its frames are of"
                                 f" {s.sizes} sizes with {s.junk} bytes between them: look at it")
            duration = round(s.samples * 1000 / s.hz)
            head = mp3.info_frame(s.header, s.frames, s.end - s.at)
            sent = hashlib.sha256(data[:s.head] + head + data[s.head:]).hexdigest()
            frames.append(f"{name}\t{s.head}\t{s.frames}\t{s.end - s.at}\t{s.header.hex()}\t{sent}")
        else:
            duration = probe(f)
        rows.append(f"{name}\t{len(data)}\t{duration}\t{hashlib.sha256(data).hexdigest()}")
        if i % 200 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    out.write_text("\n".join(rows) + "\n")
    print(f"{out.relative_to(ROOT)}: {len(files)} files")
    listed = out.with_name(f"{key}-frames.tsv")
    if frames:
        listed.write_text(FRAMES_HEAD + "\n".join(["file\tat\tframes\tbytes\theader\tsent_sha256"] + frames) + "\n")
        print(f"{listed.relative_to(ROOT)}: {len(frames)} files to be served with an Info frame")
    elif listed.exists():
        raise SystemExit(f"manifest: no file of {key} needs a length frame now, and {listed.name} lists some: review it")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
