"""Write the copy: var/offline/manifest.json and var/offline/c/<hash>.gz.

The only module of offline/ that writes, and only under var/offline/, which it
builds as var/offline.tmp/ and swaps in whole, so a failed build leaves the
last one standing, as `make data` does with ub.db.

Each chunk is named by the hash of what it holds, before it is gzipped, so a
chunk that did not change keeps its name from build to build, and a browser
that has it need not fetch it again.  The manifest lists them all, and its
`build` is a hash of their names and hashes: it moves only when something the
copy holds does.  `format` is the shape of the chunks; a worker that cannot
read a copy's format fetches the whole of a new one.  `news` is what changed
on the site, for the cloud's "What's new" (news.py), and not in `build`.
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3

from . import news, pages, searchdb, site

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "var" / "offline"
FORMAT = 1

# What a page loads besides itself, and the tab's icons, each by the address a
# page names it with.  The scripts a stored page names carry their hash, as
# base.html writes them.  Not sw.js and what it imports: the browser keeps a
# worker's own scripts with the worker.  Not the app's manifest, the touch icon
# or the icons the manifest names, which differ by host (app.py SITES) while the
# copy is one for every host (offline-core.js HOSTED); until 2026-10-15 they
# were in it.
ASSETS = ["ub.css", "ub.js", "listen.js", "offline.js"]
PLAIN = ["/static/favicon.svg", "/static/fonts/UBGoudy.woff2", "/static/fonts/UBGoudy-Italic.woff2",
         "/static/fonts/OFL.txt", "/favicon.ico"]


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def build(con: sqlite3.Connection) -> dict:
    """Build the copy into var/offline/; return its manifest."""
    from ubsite import app as A
    chunks, expect, counts = pages.build(con)
    entries: list[dict] = []
    files: dict[str, bytes] = {}

    def add(name: str, kind: str, data: bytes, **more):
        h = _hash(data)
        gz = gzip.compress(data, 9, mtime=0)
        files[f"{h}.gz"] = gz
        entries.append({"name": name, "kind": kind, "file": f"c/{h}.gz", "hash": h,
                        "bytes": len(gz), "raw": len(data), **more})

    for name, obj in chunks.items():
        add(name, "pages", _json(obj))
    add("text.db", "db", searchdb.text_db(con))
    add("index.db", "db", searchdb.index_db(con))
    for url in [A.asset(a) for a in ASSETS] + PLAIN:
        path, _, query = url.partition("?")
        got = site.get(path, query)
        if got.status != 200:
            raise pages.Shape(f"{url} answered {got.status}")
        add(url, "asset", got.body, type=got.headers.get("content-type", "application/octet-stream"))

    src = {r[0]: {"commit": r[1], "date": r[2]} for r in con.execute(
        "SELECT repo, commit_id, committed_at FROM build_source WHERE repo IN ('press', 'index')")}
    manifest = {
        "format": FORMAT,
        "build": _hash("\n".join(sorted(f"{e['name']} {e['hash']}" for e in entries)).encode()),
        "made": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": src.get("press", {}), "index": src.get("index", {}),
        "bytes": sum(e["bytes"] for e in entries), "raw": sum(e["raw"] for e in entries),
        "counts": counts, "news": news.news(), "chunks": entries,
    }
    write(files, json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"), _json(expect))
    return manifest


def write(files: dict[str, bytes], manifest: bytes, expect: bytes) -> None:
    """var/offline/ whole, by way of var/offline.tmp/.  expect.json is the
    sha256 of every stored page as the server sent it, for the check; deploy.sh
    ships only manifest.json and c/."""
    tmp, old = OUT.with_name("offline.tmp"), OUT.with_name("offline.old")
    for d in (tmp, old):
        if d.exists():
            shutil.rmtree(d)
    (tmp / "c").mkdir(parents=True)
    # Each write through a named path: tests/test_no_writes.py finds a write by
    # the word before ".write_bytes(".
    for name, data in [*((f"c/{n}", d) for n, d in files.items()),
                       ("expect.json", expect), ("manifest.json", manifest)]:
        target = tmp / name
        target.write_bytes(data)
    if OUT.exists():
        os.replace(OUT, old)
    os.replace(tmp, OUT)
    if old.exists():
        shutil.rmtree(old)
