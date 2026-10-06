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
