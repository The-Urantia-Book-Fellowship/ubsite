"""List a recording directory, file by file: data/audio/<key>-files.tsv.

    .venv/bin/python -m tools.audio.manifest mh

The list pins the recordings the way a commit pins a repo: every MP3 with its
size, duration and SHA-256.  `make data` checks the directory against it on
every build -- by size, which is cheap -- and refuses a file the list does not
name, or a listed file that has gone or changed size.  Rerun this only when the
recordings really have changed, and review the diff.

Durations are ffprobe's, in milliseconds.  The files are read, never written.
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


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    from build import config
    key = argv[0] if argv else "mh"
    src = config.audio()[key]
    files = sorted(src["path"].glob("paper*/*.mp3"))
    out = ROOT / "data" / "audio" / f"{key}-files.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = ["file\tbytes\tduration_ms\tsha256"]
    for i, f in enumerate(files, 1):
        rows.append(f"{f.relative_to(src['path']).as_posix()}\t{f.stat().st_size}"
                    f"\t{probe(f)}\t{sha256(f)}")
        if i % 200 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    out.write_text("\n".join(rows) + "\n")
    print(f"{out.relative_to(ROOT)}: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
