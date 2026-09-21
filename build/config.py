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


def load() -> dict:
    """Return {key: {path, tex, rev, commit, dirty, describe}}."""
    with open(ROOT / "sources.toml", "rb") as fh:
        raw = tomllib.load(fh)

    repos = {}
    for key, cfg in raw.items():
        path = (ROOT / cfg["path"]).resolve()
        if not path.is_dir():
            raise SystemExit(f"config: source {key!r} not found at {path}\n"
                             f"        fix the path in sources.toml")
        rev = cfg.get("rev", "worktree")
        commit = _git(path, "rev-parse", "HEAD" if rev == "worktree" else rev)
        dirty = bool(_git(path, "status", "--porcelain")) if rev == "worktree" else False
        repos[key] = {
            "key": key,
            "path": path,
            "tex": path / cfg.get("tex", "tex"),
            "rev": rev,
            "commit": commit,
            "dirty": dirty,
            "subject": _git(path, "log", "-1", "--format=%s"),
            "date": _git(path, "log", "-1", "--format=%cd", "--date=short"),
        }
    return repos


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
