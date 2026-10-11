"""The only module in this project permitted to open a source path.

The three repos are masters.  Funnelling every read through one function -- and
forbidding any mode but 'r' -- turns "we must not write to the sources" from an
intention into something a test can prove.  See tests/test_no_writes.py and
`make paranoid`.
"""

from __future__ import annotations

import pathlib
import subprocess

_READ: dict[str, int] = {}


def read_text(path: pathlib.Path) -> str:
    """Read a source file.  UTF-8, never anything but read-only."""
    p = pathlib.Path(path)
    _READ[str(p)] = _READ.get(str(p), 0) + 1
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def read_bytes(path: pathlib.Path) -> bytes:
    """Read a binary source file -- the press project's fonts -- read-only."""
    p = pathlib.Path(path)
    _READ[str(p)] = _READ.get(str(p), 0) + 1
    with open(p, "rb") as fh:
        return fh.read()


def read_at_rev(repo: pathlib.Path, rel: str, rev: str) -> str:
    """Read a file at a git revision, never touching the working tree.

    The index repo is edited in another session; a site build that reads its
    worktree cannot say afterwards which index a page was built from.
    """
    if rev == "worktree":
        return read_text(pathlib.Path(repo) / rel)
    out = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(f"_io: cannot read {rel} at {rev} in {repo}:\n{out.stderr}")
    _READ[f"{repo}:{rev}:{rel}"] = 1
    return out.stdout


def read_bytes_at_rev(repo: pathlib.Path, rel: str, rev: str) -> bytes:
    """A binary file at a git revision -- the Foundation's HTML, zipped -- read-only."""
    if rev == "worktree":
        return read_bytes(pathlib.Path(repo) / rel)
    out = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{rel}"], capture_output=True)
    if out.returncode != 0:
        raise SystemExit(f"_io: cannot read {rel} at {rev} in {repo}:\n"
                         f"{out.stderr.decode('utf-8', 'replace')}")
    _READ[f"{repo}:{rev}:{rel}"] = 1
    return out.stdout


def read_tex(texdir: pathlib.Path, name: str, rev: str = "worktree") -> str | None:
    """One file of a source's tex/ directory, at the revision config pins.

    ``rev`` is 'worktree' or a commit.  None if the file is absent there, so a
    reader can report the missing file rather than die on it.  At a commit the
    path is given as ``./name``, which git resolves against ``-C texdir``: the
    reader never needs to know where the repository root is.
    """
    if rev == "worktree":
        p = pathlib.Path(texdir) / name
        return read_text(p) if p.exists() else None
    there = subprocess.run(["git", "-C", str(texdir), "cat-file", "-e", f"{rev}:./{name}"],
                           capture_output=True)
    if there.returncode != 0:
        return None
    return read_at_rev(texdir, f"./{name}", rev)


def files_read() -> dict[str, int]:
    return dict(_READ)
