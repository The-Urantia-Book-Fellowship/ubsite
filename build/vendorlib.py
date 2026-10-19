"""Vendoring by value, with a digest lock.

The sibling repos are live working trees.  Press has 710 commits and rewrites
paragraph wrappers on every build; the index repo is edited in another session.
A ``sys.path`` insert into either would make this build a function of somebody
else's unsaved editor buffer, so every borrowed module is COPIED here and its
sha256 recorded in ``vendor/UPSTREAM.lock``.

``check()`` re-hashes the originals and fails with a unified diff if upstream
moved.  It is a prerequisite of every build target.  Refreshing a vendored file
is a deliberate, reviewed commit -- never a silent side effect of `make`.

A release (SQLite's WebAssembly build) is not a tree here but a zip, by its
address and digest in its [sqlite_wasm] entry.  It cannot move, so ``check()``
holds our copy to the lock alone, and to the release that entry names;
``sync()`` fetches the zip only when it names one the lock does not record.
A single file by its address and digest (the SBL fonts) is taken the same way,
the file being the release.
"""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import pathlib
import sys
import urllib.request
import zipfile

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
    # The face a study note's math is set in, subset by build/fonts.py: OFL 1.1,
    # drawn to match EB Garamond, the nearest of TeX Live's math fonts to Goudy.
    ("texlive", "fonts/opentype/public/garamond-math/Garamond-Math.otf", "fonts/Garamond-Math.otf"),
    # SQLite's WebAssembly build, which searches the offline copy in a reader's
    # browser (ubsite/static/sw.js): the classic script and its binary.
    ("sqlite_wasm", "jswasm/sqlite3.js",               "sqlite-wasm/sqlite3.js"),
    ("sqlite_wasm", "jswasm/sqlite3.wasm",             "sqlite-wasm/sqlite3.wasm"),
    # The fonts a study note's Greek and Hebrew are set in: not OFL, and served
    # as published, never subset (config.sbl()).
    ("sbl_greek", "SBL_grk.ttf",                       "fonts/SBL_grk.ttf"),
    ("sbl_hebrew", "SBL_Hbrw.ttf",                     "fonts/SBL_Hbrw.ttf"),
]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _src(repos, key, rel):
    return (pathlib.Path(repos[key]["path"]) / rel).resolve()


def _release(src: dict) -> zipfile.ZipFile | bytes | None:
    """The release its entry names, fetched and held to its digest: a zip, or
    a single file, which is returned as it is."""
    try:
        # Named: SBL's server refuses urllib's own User-Agent with a 403.
        req = urllib.request.Request(src["url"], headers={"User-Agent": "ubsite vendor-sync"})
        with urllib.request.urlopen(req, timeout=60) as r:
            blob = r.read()
    except OSError as e:
        print(f"vendor: could not fetch {src['url']}: {e}", file=sys.stderr)
        return None
    if sha256(blob) != src["sha256"]:
        print(f"vendor: {src['url']} is not the release [{src['key']}] names "
              f"(sha256 {sha256(blob)})", file=sys.stderr)
        return None
    return zipfile.ZipFile(io.BytesIO(blob)) if src["url"].endswith(".zip") else blob


def _member(z: zipfile.ZipFile | bytes, rel: str) -> bytes | None:
    """A file of the release by its path under the zip's one top directory,
    which is named for the release (sqlite-wasm-3530400/jswasm/sqlite3.js);
    a single file is its own release."""
    if isinstance(z, bytes):
        return z
    names = [n for n in z.namelist() if n.split("/", 1)[-1] == rel]
    return z.read(names[0]) if len(names) == 1 else None


def sync(repos) -> int:
    """Copy every manifest file and (re)write the lock."""
    old = {e["dest"]: e for e in json.loads(LOCK.read_text())} if LOCK.exists() else {}
    entries, zips = [], {}
    for key, rel, dest in MANIFEST:
        src = repos[key]
        out = ROOT / "vendor" / dest
        if "url" in src:
            was = old.get(dest)
            if (was and was.get("commit") == src["sha256"] and out.exists()
                    and sha256(out.read_bytes()) == was["sha256"]):
                data = out.read_bytes()                # this release, already ours
            else:
                if key not in zips:
                    zips[key] = _release(src)
                data = zips[key] and _member(zips[key], rel)
                if data is None:
                    print(f"vendor: MISSING {rel} in {src['url']}", file=sys.stderr)
                    return 1
            where = src["url"]
        else:
            path = _src(repos, key, rel)
            if not path.exists():
                print(f"vendor: MISSING {path}", file=sys.stderr)
                return 1
            data = path.read_bytes()
            where = f"{key}:{rel}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        entries.append({
            "repo": key, "path": rel, "dest": dest,
            "sha256": sha256(data), "bytes": len(data),
            "commit": src.get("commit"),
        })
        print(f"vendor: {where} -> vendor/{dest}  ({len(data)} bytes)")
    LOCK.write_text(json.dumps(entries, indent=2) + "\n")
    return 0


def check(repos) -> int:
    """Fail loudly if an upstream file no longer matches what we vendored."""
    if not LOCK.exists():
        print("vendor: no UPSTREAM.lock; run `make vendor-sync`", file=sys.stderr)
        return 1
    bad = 0
    for e in json.loads(LOCK.read_text()):
        src = repos[e["repo"]]
        ours = ROOT / "vendor" / e["dest"]
        if "url" in src:
            if e.get("commit") != src["sha256"]:
                bad += 1
                print(f"\nvendor: ANOTHER RELEASE  [{src['key']}] names {src['url']}, "
                      f"but vendor/{e['dest']} is from another", file=sys.stderr)
                continue
        else:
            path = _src(repos, e["repo"], e["path"])
            if not path.exists():
                print(f"vendor: MISSING upstream {path}", file=sys.stderr)
                bad += 1
                continue
            up = path.read_bytes()
            if sha256(up) != e["sha256"]:
                bad += 1
                print(f"\nvendor: UPSTREAM MOVED  {e['repo']}:{e['path']}", file=sys.stderr)
                if e["dest"].endswith(".wasm"):
                    continue                       # a binary: a diff would say nothing
                diff = difflib.unified_diff(
                    ours.read_text(errors="replace").splitlines(True),
                    up.decode(errors="replace").splitlines(True),
                    fromfile=f"vendor/{e['dest']}", tofile=str(path), n=2)
                sys.stderr.writelines(list(diff)[:60])
                continue
        if not ours.exists() or sha256(ours.read_bytes()) != e["sha256"]:
            bad += 1
            print(f"vendor: LOCAL EDIT to vendor/{e['dest']} -- vendored files "
                  f"are copies, not forks", file=sys.stderr)
    if bad:
        print(f"\nvendor: {bad} file(s) out of sync. Review, then "
              f"`make vendor-sync` to adopt.", file=sys.stderr)
        return 1
    print(f"vendor: {len(MANIFEST)} files match upstream")
    return 0
