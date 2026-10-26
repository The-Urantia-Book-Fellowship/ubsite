"""The offline copy's gates: every page it answers is the page the server sends.

    python -m offline check        (make offline runs it after the build)

Node runs static/offline-core.js on the copy, as the service worker does
(offline/check.mjs), and this holds what it makes to what the app sends:

  - every stored page, byte for byte: the sha256 the build took of it as the
    server sent it, and what the core joins from the copy's pieces; and the
    text the browser's voice reads, section by section, as /speech/ sends it;
  - every section's translations, /tr/, with every translation kept, as the
    server sends them, and with none kept or one alone, the fragment's frame
    around what is kept;
  - every section with all its paragraphs marked (/101:4.1-N), and a sample of
    one paragraph each, which puts back each section's rail and marks;
  - addresses the server explains or redirects: a paragraph that is not there,
    a range that runs backwards, a paper or section there is none of, a
    reading path a headword does not have, or not by theme;
  - search: every query in tests/fixtures/offline-queries.txt and every one a
    reader has typed into this machine's dev server (var/visits.db), in each of
    its lists and a page past the first, byte for byte with app.search();
  - every link in every stored page lands somewhere the copy answers.

Then the copy's own consistency: each chunk's bytes hash to its name, and its
size is in the bands verify/expectations.toml sets.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tomllib
import urllib.parse

from . import pack, site

ROOT = pack.ROOT
QUERIES = ROOT / "tests" / "fixtures" / "offline-queries.txt"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def queries() -> list[str]:
    qs = [q for q in QUERIES.read_text(encoding="utf-8").splitlines() if q and not q.startswith("# ")]
    visits = ROOT / "var" / "visits.db"
    if visits.exists():
        con = sqlite3.connect(f"file:{visits}?mode=ro", uri=True)
        for (raw,) in con.execute("SELECT DISTINCT query FROM view WHERE path='/search' AND query IS NOT NULL"):
            q = urllib.parse.parse_qs(raw).get("q", [""])[-1]
            if q not in qs:
                qs.append(q)
        con.close()
    return qs


def extras(con: sqlite3.Connection, shell: dict) -> list[dict]:
    """The addresses beyond the stored pages, as the server answers them."""
    jobs: list[tuple[str, str, bool]] = []          # (path, query, send the body)
    lasts = shell["lasts"]
    rng = random.Random(1955)
    for here, n in lasts.items():
        jobs.append((f"/{here}.1-{n}", "", False))
    for here in rng.sample(sorted(lasts), 200):
        jobs.append((f"/{here}.{rng.randint(1, lasts[here])}", "", False))
    slugs, paths = shell["slugs"], shell["paths"]
    no_path = next(s for s in slugs if s not in paths)
    one_chapter = next(s for s, (n, _) in paths.items() if n < 2)
    for p in ["/0:0.0-1", "/86:5.18", "/86:5.15-14", "/39:3.9-8", "/300:1", "/1:99", "/300", "/101",
              "/0", "/007:1", "/i/no-such-headword", f"/i/{no_path}/read", f"/i/{one_chapter}/read/theme",
              "/index/q", "/index/QQ", "/index/a", "/appendix/a", "/appendix/G", "/appendix/AB",
              "/part/9", "/part/01", "/part/x", "/rail/300", "/rail/007", "/nothing", "/i/god/more",
              "/101:4.2:3", "/café", "/speech/01:4", "/speech/999:1", "/speech/1:99", "/speech/x",
              "/speech/1:4:5", "/tr/01:1", "/tr/999:1", "/tr/1:99", "/tr/x", "/tr/1:1:2"]:
        jobs.append((p, "", True))
    for q in queries():
        for scope in ("", "index", "text", "notes"):
            jobs.append(("/search", urllib.parse.urlencode({"q": q, **({"in": scope} if scope else {})}), True))
    for q in ("god", "prayer", "adjuster"):
        for scope, page in (("index", "2"), ("text", "3"), ("text", "999"), ("text", "0"), ("index", "x")):
            jobs.append(("/search", urllib.parse.urlencode({"q": q, "in": scope, "page": page}), True))
    out = []
    for (p, q, body), got in zip(jobs, site.get_many([(p, q) for p, q, _ in jobs])):
        x = {"path": p, "query": q, "status": got.status}
        if "location" in got.headers:
            x["location"] = got.headers["location"]
        elif got.status in (200, 404) and got.headers.get("content-type", "").startswith(("text/html",
                                                                                         "application/json")):
            x["sha"] = _sha(got.body)
            if body:
                x["body"] = got.text
        out.append(x)
    return out


def every(manifest: dict) -> list[dict]:
    """Every chunk the manifest names: the copy's, and each translation's."""
    return manifest["chunks"] + [c for t in manifest.get("translations", []) for c in t["chunks"]]


def consistent(copy: pathlib.Path, manifest: dict) -> list[str]:
    bad = []
    for c in every(manifest):
        f = copy / c["file"]
        if not f.is_file():
            bad.append(f"{c['name']}: {c['file']} is missing")
            continue
        data = f.read_bytes()
        if len(data) != c["bytes"] or len(gzip.decompress(data)) != c["raw"]:
            bad.append(f"{c['name']}: its size is not the manifest's")
    files = {c["file"].split("/")[1] for c in every(manifest)}
    stray = sorted(p.name for p in (copy / "c").iterdir() if p.name not in files)
    if stray:
        bad.append(f"files no chunk names: {stray[:5]}")
    return bad


RE_CSS_URL = re.compile(r"url\((/static/[^)\s]+)\)")
RE_SRC = re.compile(r'<script src="([^"]+)"')


def assets(copy: pathlib.Path, manifest: dict) -> list[str]:
    """What a page loads besides itself, held to the copy: every url(/static/…)
    in its stylesheet, a font among them, and every script the shell names.
    The link check reads href= alone, and a font missing from the copy would
    be drawn offline in whatever face the device had."""
    names = {c["name"] for c in manifest["chunks"]}
    read = lambda name: gzip.decompress((copy / next(c["file"] for c in manifest["chunks"]
                                                     if c["name"] == name)).read_bytes()).decode()
    css = [n for n in names if n.startswith("/static/ub.css?")]
    if len(css) != 1:
        return [f"the copy holds {len(css)} stylesheets"]
    shell = "".join(json.loads(read("shell"))["shell"])
    want = set(RE_CSS_URL.findall(read(css[0]))) | set(RE_SRC.findall(shell))
    return [f"{u}: named by the copy's pages, not in it" for u in sorted(want - names)]


def bands(manifest: dict, con: sqlite3.Connection) -> list[str]:
    exp = tomllib.loads((ROOT / "verify" / "expectations.toml").read_text())["offline"]
    bad = []
    for key, val in (("pages", manifest["counts"]["pages"]), ("paths", manifest["counts"]["paths"]),
                     ("spoken", manifest["counts"]["spoken"]), ("chunks", len(manifest["chunks"]))):
        if val != exp[key]:
            bad.append(f"{key}: {val:,}, expected {exp[key]:,}")
    for key, val in (("download_mb", manifest["bytes"] / 1e6), ("raw_mb", manifest["raw"] / 1e6)):
        lo, hi = exp[key]
        if not lo <= val <= hi:
            bad.append(f"{key}: {val:.2f}, expected {lo} to {hi}")
    # Each translation, a download of its own: a chunk to every twenty papers
    # it has, by the database, as ud's grow as it is written; its size in a band.
    got = {t["key"]: t for t in manifest.get("translations", [])}
    if set(got) != set(exp["translations"]):
        bad.append(f"translations: {sorted(got)}, expected {sorted(exp['translations'])}")
    for key, want in exp["translations"].items():
        t = got.get(key)
        if t is None:
            continue
        groups = {f"tr-{key}-{g}" for (g,) in con.execute(
            "SELECT DISTINCT p.paper_n / 20 FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE t.translation = ?", (key,))}
        if {c["name"] for c in t["chunks"]} != groups:
            bad.append(f"{key}: {len(t['chunks'])} chunks, for {len(groups)} twenties of papers")
        lo, hi = want["download_mb"]
        if not lo <= t["bytes"] / 1e6 <= hi:
            bad.append(f"{key}: {t['bytes'] / 1e6:.2f} MB, expected {lo} to {hi}")
    return bad


def run(con: sqlite3.Connection) -> int:
    copy = pack.OUT
    if not (copy / "manifest.json").exists():
        print("offline: no copy in var/offline/; run `python -m offline build`", file=sys.stderr)
        return 1
    node = shutil.which("node")
    if node is None:
        print("offline: the check needs Node (it runs the worker's own code)", file=sys.stderr)
        return 1
    manifest = json.loads((copy / "manifest.json").read_text())
    rc = 0
    for title, bad in (("the copy", consistent(copy, manifest)), ("what it loads", assets(copy, manifest)),
                       ("its size", bands(manifest, con))):
        print(f"{title}: {'ok' if not bad else 'FAILED'}")
        for b in bad:
            print(f"  {b}")
        rc |= bool(bad)
    shell = json.loads(gzip.decompress((copy / next(c["file"] for c in manifest["chunks"]
                                                     if c["name"] == "shell")).read_bytes()))
    xs = extras(con, shell)
    job = {"copy": str(copy), "engine": str(ROOT / "vendor" / "sqlite-wasm"),
           "core": str(ROOT / "ubsite" / "static" / "offline-core.js"),
           "pages": json.loads((copy / "expect.json").read_text()), "extras": xs,
           # Where the copy is read, as the worker's location.origin: the host
           # the pages it is held to were asked at.
           "origin": f"https://{site.HOST}"}
    r = subprocess.run([node, str(pathlib.Path(__file__).with_name("check.mjs"))],
                       input=json.dumps(job), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 1
    res = json.loads(r.stdout)
    searches = sum(1 for x in xs if x["path"] == "/search")
    print(f"stored: {res['pages']:,} pages, spoken texts and translations, {res['extras'] - searches:,} more addresses,"
          f" {searches:,} searches: {'ok' if not res['bad'] else f'{len(res['bad'])} FAILED'}")
    for b in res["bad"][:12]:
        print(f"  {b.get('path')}: " + ", ".join(f"{k} {v!r}" for k, v in b.items() if k != "path"))
    print(f"links: {res['links']:,} distinct, {'ok' if not res['broken'] else f'{len(res['broken'])} land nowhere'}")
    for b in res["broken"][:12]:
        print(f"  {b}")
    return rc | bool(res["bad"]) | bool(res["broken"])
