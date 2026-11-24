"""Place the model Search by meaning embeds with, held to its digests.

    .venv/bin/python -m tools.embed.fetch            place what is missing; check every file
    .venv/bin/python -m tools.embed.fetch --check    check alone, and fail where one is not as named

The model is named among the project's sources (build/config.py embed()): a
repository on Hugging Face at one revision, and the SHA-256 of each of its
three files.  They go to var/embed/bge-m3/, under the paths the repository
gives them, where tools/embed/build.py and ubsite/meaning.py read them and
from where deploy.sh ships them to the hosts.

A file is taken from Hugging Face's own cache on this machine where it is
there ($HF_HOME, which `make embed-fetch` sets: the cache keeps a file under
its digest), by a hard link where the two are on one filesystem, so that the
2.27 GB of weights are not kept twice; else it is fetched by its address.
Either way it is hashed where it lands, and other bytes are refused: a file
that is not the one named is removed, never left in place.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import shutil
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL = ROOT / "var" / "embed" / "bge-m3"

sys.path.insert(0, str(ROOT))


def config() -> dict:
    from build import config as cfg
    return cfg.embed()


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def cached(cfg: dict, sha: str) -> pathlib.Path | None:
    """The file in Hugging Face's cache, which names each by its digest."""
    home = os.environ.get("HF_HOME")
    if not home:
        return None
    blob = pathlib.Path(home) / "hub" / ("models--" + cfg["repo"].replace("/", "--")) / "blobs" / sha
    # The file itself: the cache's entry may be a link into its own store, and
    # a hard link made of a link is a link, which from here leads nowhere.
    return blob.resolve() if blob.is_file() else None


def place(cfg: dict, name: str, sha: str) -> str:
    """One file where it belongs; how it came there."""
    dest = MODEL / name
    if dest.is_file():
        if digest(dest) == sha:
            return "there"
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    if os.path.lexists(tmp):
        tmp.unlink()
    blob = cached(cfg, sha)
    if blob is not None:
        try:
            os.link(blob, tmp)
            how = "linked from Hugging Face's cache"
        except OSError:
            shutil.copyfile(blob, tmp)
            how = "copied from Hugging Face's cache"
    else:
        req = urllib.request.Request(cfg["base"] + name, headers={"User-Agent": "ubsite-build"})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as out:
            shutil.copyfileobj(r, out, 1 << 22)
        how = "fetched"
    got = digest(tmp)
    if got != sha:
        tmp.unlink()
        raise SystemExit(f"{name}: SHA-256 {got}, where the model named is {sha}")
    os.replace(tmp, dest)
    return how


def check(cfg: dict) -> list[str]:
    """What is wrong with the model as placed; nothing where it is as named."""
    wrong = []
    for name, sha in cfg["sha256"].items():
        p = MODEL / name
        if not p.is_file():
            wrong.append(f"{p.relative_to(ROOT)}: not there (python -m tools.embed.fetch)")
        elif digest(p) != sha:
            wrong.append(f"{p.relative_to(ROOT)}: not the file the model is named by")
    return wrong


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="check alone")
    a = ap.parse_args()
    cfg = config()
    if not a.check:
        for name, sha in cfg["sha256"].items():
            how = place(cfg, name, sha)
            print(f"{(MODEL / name).relative_to(ROOT)}: {(MODEL / name).stat().st_size:,} bytes, {how}")
    wrong = check(cfg)
    for w in wrong:
        print(w, file=sys.stderr)
    if not wrong:
        print(f"{cfg['repo']} at {cfg['rev'][:8]}: {len(cfg['sha256'])} files, each the digest it is named by")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
