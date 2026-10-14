"""Vendoring by value, with a digest lock.

The sibling repos are live working trees.  Press has 710 commits and rewrites
paragraph wrappers on every build; the index repo is edited in another session.
A ``sys.path`` insert into either would make this build a function of somebody
else's unsaved editor buffer, so every borrowed module is COPIED here and its
sha256 recorded in ``vendor/UPSTREAM.lock``.

``check()`` re-hashes the originals and fails with a unified diff if upstream
moved.  It is a prerequisite of every build target.  Refreshing a vendored file
is a deliberate, reviewed commit -- never a silent side effect of `make`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCK = ROOT / "vendor" / "UPSTREAM.lock"

# (source repo key, path within that repo, destination under vendor/)
MANIFEST = [
    ("press", "tools/text-verify/latex_tokenizer.py", "press/latex_tokenizer.py"),
    ("press", "tools/text-verify/macros.py",          "press/macros.py"),
    ("press", "tools/text-verify/normalize.py",       "press/normalize.py"),
    ("index", "cite.py",                              "index/cite.py"),
    ("index", "xref.py",                              "index/xref.py"),
    # Data, not code: the patterns the book is hyphenated with (build/hyphen.py).
    ("texlive", "tex/generic/hyphen/hyphen.tex",      "tex/hyphen.tex"),
    # SQLite's WebAssembly build, which searches the offline copy in a reader's
    # browser (ubsite/static/sw.js): the classic script and its binary.
    ("sqlite_wasm", "jswasm/sqlite3.js",               "sqlite-wasm/sqlite3.js"),
    ("sqlite_wasm", "jswasm/sqlite3.wasm",             "sqlite-wasm/sqlite3.wasm"),
]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _src(repos, key, rel):
    return (pathlib.Path(repos[key]["path"]) / rel).resolve()


def sync(repos) -> int:
    """Copy every manifest file and (re)write the lock."""
    entries = []
    for key, rel, dest in MANIFEST:
        src = _src(repos, key, rel)
        if not src.exists():
            print(f"vendor: MISSING {src}", file=sys.stderr)
            return 1
        data = src.read_bytes()
        out = ROOT / "vendor" / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        entries.append({
            "repo": key, "path": rel, "dest": dest,
            "sha256": sha256(data), "bytes": len(data),
            "commit": repos[key].get("commit"),
        })
        print(f"vendor: {key}:{rel} -> vendor/{dest}  ({len(data)} bytes)")
    LOCK.write_text(json.dumps(entries, indent=2) + "\n")
    return 0


def check(repos) -> int:
    """Fail loudly if an upstream file no longer matches what we vendored."""
    if not LOCK.exists():
        print("vendor: no UPSTREAM.lock; run `make vendor-sync`", file=sys.stderr)
        return 1
    bad = 0
    for e in json.loads(LOCK.read_text()):
        src = _src(repos, e["repo"], e["path"])
        ours = ROOT / "vendor" / e["dest"]
        if not src.exists():
            print(f"vendor: MISSING upstream {src}", file=sys.stderr)
            bad += 1
            continue
        up = src.read_bytes()
        if sha256(up) != e["sha256"]:
            bad += 1
            print(f"\nvendor: UPSTREAM MOVED  {e['repo']}:{e['path']}", file=sys.stderr)
            if e["dest"].endswith(".wasm"):
                continue                           # a binary: a diff would say nothing
            diff = difflib.unified_diff(
                ours.read_text(errors="replace").splitlines(True),
                up.decode(errors="replace").splitlines(True),
                fromfile=f"vendor/{e['dest']}", tofile=str(src), n=2)
            sys.stderr.writelines(list(diff)[:60])
        elif sha256(ours.read_bytes()) != e["sha256"]:
            bad += 1
            print(f"vendor: LOCAL EDIT to vendor/{e['dest']} -- vendored files "
                  f"are copies, not forks", file=sys.stderr)
    if bad:
        print(f"\nvendor: {bad} file(s) out of sync. Review, then "
              f"`make vendor-sync` to adopt.", file=sys.stderr)
        return 1
    print(f"vendor: {len(MANIFEST)} files match upstream")
    return 0
