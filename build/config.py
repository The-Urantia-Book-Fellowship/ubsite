"""Resolve sources.toml.  The ONLY module that knows where the sources live.

Every other module takes paths from here, so re-pointing a source is a one-line
edit in one file -- which matters, because the study edition alone has three
trees on this machine and the one named "-latest" is the oldest of them.
"""

from __future__ import annotations

import pathlib
import subprocess
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _git(repo: pathlib.Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args],
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _dirty(path: pathlib.Path, tex: str) -> bool:
    """Do the inputs differ from the commit?

    Any change to a tracked file, or an untracked file under tex/, where the
    reader globs for papers.  Untracked files elsewhere are not inputs: press
    carries an untracked tools/press/Lakeside/ that no build reads, and counting
    it would mark every build from that tree as modified.
    """
    return bool(_git(path, "status", "--porcelain", "--untracked-files=no")
                or _git(path, "ls-files", "--others", "--exclude-standard", "--", tex))


def dirty_files(path: pathlib.Path, tex: str) -> list[str]:
    """What makes it dirty, as `git status --short` writes it: each tracked file
    with uncommitted changes, and each untracked file under tex/ ('?? ...')."""
    def lines(*args: str) -> list[str]:
        out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=30)
        return out.stdout.splitlines() if out.returncode == 0 else []
    return (lines("status", "--short", "--untracked-files=no")
            + ["?? " + f for f in lines("ls-files", "--others", "--exclude-standard", "--", tex)])


def load() -> dict:
    """Return {key: {path, tex, rev, at, commit, dirty, commit_url, pushed, subject, date}}.

    ``at`` is what the readers read: 'worktree', or the commit ``rev`` resolved
    to, resolved here ONCE.  The index session can commit while a build runs;
    reading at a fixed SHA means the build reads exactly the commit it records.
    """
    with open(ROOT / "sources.toml", "rb") as fh:
        raw = tomllib.load(fh)

    repos = {}
    for key, cfg in raw.items():
        if key in ("audio", "srt", "texlive", "sqlite_wasm", "sbl_greek", "sbl_hebrew", "block"):
            continue                                # not repositories: see audio(), srt(), texlive(), sqlite_wasm(), sbl(), block()
        path = (ROOT / cfg["path"]).resolve()
        if not path.is_dir():
            raise SystemExit(f"config: source {key!r} not found at {path}\n"
                             f"        fix the path in sources.toml")
        rev = cfg.get("rev", "worktree")
        tex = cfg.get("tex", "tex")
        commit = _git(path, "rev-parse", "HEAD" if rev == "worktree" else f"{rev}^{{commit}}")
        if rev != "worktree" and commit is None:
            raise SystemExit(f"config: {key}: cannot resolve rev {rev!r} in {path}")
        dirty = _dirty(path, tex) if rev == "worktree" else False
        url = cfg.get("url")
        repos[key] = {
            "key": key,
            "path": path,
            "tex": path / tex,
            "rev": rev,
            "at": "worktree" if rev == "worktree" else commit,
            "commit": commit,
            "dirty": dirty,
            # The commit's page on the repository's host, or None.  `pushed` is
            # as of the last fetch: an unpushed commit's page is a 404 until it is.
            "commit_url": f"{url.rstrip('/')}/commit/{commit}" if url and commit else None,
            "pushed": bool(commit and _git(path, "branch", "-r", "--contains", commit)),
            "subject": _git(path, "log", "-1", "--format=%s", commit or "HEAD"),
            "date": _git(path, "log", "-1", "--format=%cd", "--date=short", commit or "HEAD"),
        }
    return repos


def audio() -> dict:
    """Return {key: {key, path, root, label, kind}} for each [audio.<key>] in sources.toml.

    A recording directory has no git and no revision: what pins it is the
    per-file list in data/audio/<key>-files.tsv.  A human reading's is a master
    like the repos, at an absolute path that pi5 shares.  The AI voice's is made
    here (tools/tts/book.py), under var/, so its path is relative to the
    project: `root` is the path as written, which the database records and the
    app resolves against its own tree, here or on pi5.
    """
    with open(ROOT / "sources.toml", "rb") as fh:
        raw = tomllib.load(fh).get("audio", {})
    out = {}
    for key, cfg in raw.items():
        path = pathlib.Path(cfg["path"]).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        out[key] = {"key": key, "path": path, "root": cfg["path"], "label": cfg["label"],
                    "kind": cfg["kind"], "credit": cfg.get("credit"),
                    "credit_url": cfg.get("credit_url"), "present": path.is_dir()}
    return out


def srt() -> dict:
    """Return {url, path} for the SRT Committee's page and its snapshot here.

    The page is the Fellowship's; the snapshot of its two tables, under data/,
    is what the build reads (build/srt.py), and only tools/srt/snapshot.py
    writes it.
    """
    with open(ROOT / "sources.toml", "rb") as fh:
        cfg = tomllib.load(fh)["srt"]
    return {"url": cfg["url"], "path": ROOT / cfg["path"]}


def texlive() -> dict:
    """Return {key, path} for the TeX Live tree that hyphen.tex is vendored from.

    Shaped like a repository entry so that vendorlib can take it beside them;
    it has no commit, and `make paranoid` does not fingerprint it, because the
    build never reads it.
    """
    with open(ROOT / "sources.toml", "rb") as fh:
        cfg = tomllib.load(fh)["texlive"]
    return {"key": "texlive", "path": pathlib.Path(cfg["path"]), "commit": None}


def sqlite_wasm() -> dict:
    """Return {key, url, sha256, commit} for the SQLite WASM release that
    vendor/sqlite-wasm/ is copied from: a zip, by its address and digest, with
    no path on this machine.  vendorlib takes it beside the repositories, the
    digest standing where a repository's commit does, and the build never
    reads it."""
    with open(ROOT / "sources.toml", "rb") as fh:
        cfg = tomllib.load(fh)["sqlite_wasm"]
    return {"key": "sqlite_wasm", "url": cfg["url"], "sha256": cfg["sha256"], "commit": cfg["sha256"]}


def sbl() -> dict[str, dict]:
    """{key: {key, url, sha256, commit}} for the SBL fonts vendor/fonts/ holds:
    each a single file, by its address and digest, taken by vendorlib as a
    release is.  Served as published, never modified (sources.toml)."""
    with open(ROOT / "sources.toml", "rb") as fh:
        raw = tomllib.load(fh)
    return {k: {"key": k, "url": raw[k]["url"], "sha256": raw[k]["sha256"], "commit": raw[k]["sha256"]}
            for k in ("sbl_greek", "sbl_hebrew")}


def block() -> dict:
    """Return {path, manifest, sha256, charts} for Matthew Block's parallel charts.

    A directory of PDFs, one per paper, kept by ../explore-tools/block_fetch.py,
    and no repository.  What the build reads is its MANIFEST.tsv: `charts` maps
    a paper's number to its row (url, uploaded, sha256, ...).  A chart is
    revised under a new address, so the url is the chart's version, and a paper
    without a chart has no row.  None for each if the directory is absent.
    """
    import csv
    import hashlib

    from .readers._io import read_bytes

    with open(ROOT / "sources.toml", "rb") as fh:
        cfg = tomllib.load(fh)["block"]
    path = (ROOT / cfg["path"]).resolve()
    manifest = path / "MANIFEST.tsv"
    if not manifest.is_file():
        return {"key": "block", "path": path, "manifest": None, "sha256": None, "charts": None}
    raw = read_bytes(manifest)
    rows = csv.DictReader(raw.decode("utf-8").splitlines(), delimiter="\t")
    return {"key": "block", "path": path, "manifest": manifest,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "charts": {int(r["paper"]): r for r in rows}}


def describe(repos: dict) -> str:
    lines = []
    for r in repos.values():
        mark = " +dirty" if r["dirty"] else ""
        rel = r["path"]
        lines.append(f"  {r['key']:<6} {str(rel):<52} "
                     f"{(r['commit'] or '-')[:8]} {r['date'] or ''}{mark}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe(load()))
