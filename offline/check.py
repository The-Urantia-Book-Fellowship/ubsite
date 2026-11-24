"""The offline copy's gates: every page it answers is the page the server sends.

    python -m offline check        (make offline runs it after the build)

Node runs static/offline-core.js on the copy, as the service worker does
(offline/check.mjs), and this holds what it makes to what the app sends:

  - every stored page, byte for byte: the sha256 the build took of it as the
    server sent it, and what the core joins from the copy's pieces; and the
    text the browser's voice reads, section by section, as /speech/ sends it,
    each translation's too, with it kept and not;
  - every section's translations, /tr/, with every translation kept, as the
    server sends them, and with none kept or one alone, the fragment's frame
    around what is kept;
  - every section with all its paragraphs marked (/101:4.1-N), and a sample of
    one paragraph each, which puts back each section's rail and marks; and
    every whole paper, /101, joined from its sections' pieces, among the
    stored pages;
  - addresses the server explains or redirects: a paragraph that is not there,
    a range that runs backwards, a paper or section there is none of, a
    reading path a headword does not have, or not by theme, and Compare's
    old address, a section's page with /compare after it, which goes to the
    page's own since Compare became a setting (2026-11-08);
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
    no_quiz = next(int(p) for p in shell["papers"] if int(p) not in shell["quiz"])
    for p in ["/0:0.0-1", "/86:5.18", "/86:5.15-14", "/39:3.9-8", "/300:1", "/1:99", "/300",
              "/007:1", "/i/no-such-headword", f"/i/{no_path}/read", f"/i/{one_chapter}/read/theme",
              "/index/q", "/index/QQ", "/index/a", "/appendix/a", "/appendix/G", "/appendix/AB",
              "/part/9", "/part/01", "/part/x", "/part/1/compare", "/part/9/compare", "/part/1/compare/x", "/rail/300", "/rail/007", "/rail/xx", "/rail/UF-RUS", "/nothing", "/i/god/more",
              "/101:4.2:3", "/café", "/speech/01:4", "/speech/999:1", "/speech/1:99", "/speech/x",
              "/speech/1:4:5", "/speech/ud/01:1", "/speech/ud/100:1", "/speech/x/1:1", "/speech/ud/1:99",
              "/speech/ud/x", "/speech/ud/1:1:2", "/tr/01:1", "/tr/999:1", "/tr/1:99", "/tr/x", "/tr/1:1:2",
              "/1:1/compare", "/1:1.3-4/compare", "/1/compare", "/300/compare", "/1:99/compare",
              "/x/compare", "/1:1/compare/x", "/search/compare", "/i/god/compare",
              # The quiz: a paper without questions, a paper there is not, a number
              # written otherwise, a word, Compare's address after it.
              f"/quiz/{no_quiz}", "/quiz/197", "/quiz/01", "/quiz/x", "/quiz/-1", "/quiz/compare",
              "/quiz/1/compare", "/quiz/1/x",
              # The chart of the personalities has one address.
              "/cosmology/", "/cosmology/x", "/cosmology/compare", "/Cosmology", "/cosmology/michael",
              # The charts and Unit conversions, one address each.
              "/charts/", "/charts/x", "/Charts", "/units/", "/units/x", "/units/time", "/Units",
              # Search by meaning's page, one address; what it asks is a POST, the server's alone.
              "/meaning/", "/meaning/x", "/Meaning",
              # Digits other than 0-9 (app.py RE_REF, 2026-11-09).  Not a newline
              # after an address, which both answer 404 (tests/test_addresses.py)
              # but name differently: Starlette's URL drops it.
              "/１:１", "/١:１", "/１"]:
        jobs.append((p, "", True))
    # The Bible (app.py bible_*): its addresses written otherwise, sent on or
    # explained; a verse, a run of verses and every chapter's last verse
    # marked, which the copy makes from the chapter's stored page; the
    # Synodal's addresses by its own numbers, sent on to their rows, every
    # chapter's first and last; and the jumps of the search box, by either
    # version's names and numbers.
    if shell.get("bible"):
        for p in ["/bible/", "/bible/Gen/", "/bible/Gen/1/", "/bible/gen", "/bible/GEN/1:1", "/bible/Genesis",
                  "/bible/genesis/50", "/bible/1samuel/3", "/bible/IJohn/4:8", "/bible/Song%20of%20Solomon",
                  "/bible/SongofSolomon/2:1", "/bible/Xyz", "/bible/Xyz/1", "/bible/Gen/51", "/bible/Gen/0",
                  "/bible/Gen/01", "/bible/Gen/1:40", "/bible/Gen/1:0", "/bible/Gen/1:5-3", "/bible/Gen/1:3-40",
                  "/bible/Gen/x", "/bible/Gen/1:x", "/bible/Gen/1/x", "/bible/Gen/1:1-1", "/bible/Gen/1:01",
                  "/bible/compare", "/bible/Gen/compare", "/bible/Jud/24", "/bible/Psa/119:9-16", "/bible/Psa/3:1",
                  "/bible/Rom/16:27", "/bible/Exo/32:32", "/bible/Gen/1:1", "/bible/Mat/1:1-2", "/bible/Gen/2:1",
                  "/bible/Бытие", "/bible/Быт/1", "/bible/tobit", "/bible/Tob/1:3", "/bible/3Ez/7:36",
                  "/bible/Psa/151", "/bible/Psa/151:1", "/bible/Psa/152", "/bible/2Co/13:13", "/bible/Dan/14:1",
                  "/bible/tr/Gen/1", "/bible/tr/Gen/01", "/bible/tr/Gen/0", "/bible/tr/Gen/51", "/bible/tr/Tob/1",
                  "/bible/tr/Psa/151", "/bible/tr/Xyz/1", "/bible/tr/Gen/x", "/bible/tr/Gen/1/",
                  "/bible/rsb/Psa/22", "/bible/rsb/Psa/22:1", "/bible/rsb/Psa/22:0", "/bible/rsb/Psa/22:99",
                  "/bible/rsb/Psa/9:22", "/bible/rsb/Dan/3:24", "/bible/rsb/Tob/1:3", "/bible/rsb/Tob/1:1-2",
                  "/bible/rsb/Xyz/1:1", "/bible/rsb/psa/22:1", "/bible/rsb/Psa/x", "/bible/rsb/Est/0:0",
                  "/bible/rsb/Psa/114", "/bible/rsb/Psa/115:1", "/bible/tr", "/bible/rsb"]:
            jobs.append((p, "", True))
        for abbr, _, _, _, _, _, lasts, _, spans, _ in shell["bible"]:
            for c, n in enumerate(lasts, 1):
                jobs.append((f"/bible/{abbr}/{c}:{n}", "", False))
            for c, (lo, hi) in spans.items():
                jobs.append((f"/bible/rsb/{abbr}/{c}:{lo}", "", False))
                jobs.append((f"/bible/rsb/{abbr}/{c}:{hi}", "", False))
        for q in ("John 3:16", "john 3:16", "Gen 1:1", "Genesis 1", "psalm 23", "Psalms 104:1-2", "Jude 24",
                  "1 John 4:8", "1John 4:8", "I John 4:8", "Song of Solomon 2:1", "Gen 99:1", "Gen 1:0",
                  "Gen 1:5-3", "Mark 5", "Xyz 1:1", "Gen.  1:1", "Rev 22:21", "Tobit 1:3", "Sirach 1",
                  "Ин 3:16", "Быт 1:1", "Пс 22", "Пс 22:1", "Псалом 22", "1 Цар 2:2", "1-я Царств 2:2",
                  "Иуд 24", "Дан 3:24", "Пс 151", "Пс 9:22", "Быт 99:1", "Пс 22:99", "Тов 1:3", "От Иоанна 3:16"):
            jobs.append(("/search", urllib.parse.urlencode({"q": q}), True))
    # Every list a search has, by its `in`: each translation's too, by its key.
    keys = [t["key"] for t in shell["tr"]["order"]]
    for q in queries():
        for scope in ("", "index", "text", "notes", "study", "kjv", "rsb", *keys):
            jobs.append(("/search", urllib.parse.urlencode({"q": q, **({"in": scope} if scope else {})}), True))
    for q in ("god", "prayer", "adjuster"):
        for scope, page in (("index", "2"), ("text", "3"), ("text", "999"), ("text", "0"), ("index", "x"),
                            ("text", "²"), ("text", "٢"), ("text", "1" + "0" * 5000), ("text", "0" * 30 + "2")):
            jobs.append(("/search", urllib.parse.urlencode({"q": q, "in": scope, "page": page}), True))
    for q in ("бог", "все"):
        for scope, page in ((keys[0], "2"), (keys[-1], "3"), (keys[-1], "999")):
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
    """Every chunk the manifest names: the copy's, each translation's, and
    each version of the Bible's."""
    return manifest["chunks"] + [c for t in manifest.get("translations", []) + manifest.get("bible", [])
                                 for c in t["chunks"]]


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
# A picture in a stored page, as the chunk has it, a JSON string, and the
# addresses its src and srcset name.
RE_IMG = re.compile(rb"<img\b[^>]*>")
RE_IMG_URL = re.compile(rb'/static/[^\s,"\\]+')


def pictures(copy: pathlib.Path, manifest: dict) -> set[str]:
    """Every /static/ address an <img> names, in the shell and in every stored
    page, a translation's too: its src and each address of its srcset."""
    found: set[str] = set()
    for c in every(manifest):
        if c["kind"] in ("pages", "tr") or c["name"] == "shell":
            data = gzip.decompress((copy / c["file"]).read_bytes())
            for tag in RE_IMG.findall(data):
                found.update(u.decode() for u in RE_IMG_URL.findall(tag))
    return found


def assets(copy: pathlib.Path, manifest: dict) -> list[str]:
    """What a page loads besides itself, held to the copy: every url(/static/…)
    in its stylesheet, a font among them, every script the shell names, and
    every picture a stored page shows, at each width its srcset offers (since
    2026-11-18, the home page's part cards).  The link check reads href=
    alone: a font missing from the copy would be drawn offline in whatever
    face the device had, and a picture not at all."""
    names = {c["name"] for c in manifest["chunks"]}
    read = lambda name: gzip.decompress((copy / next(c["file"] for c in manifest["chunks"]
                                                     if c["name"] == name)).read_bytes()).decode()
    css = [n for n in names if n.startswith("/static/ub.css?")]
    if len(css) != 1:
        return [f"the copy holds {len(css)} stylesheets"]
    shell = "".join(json.loads(read("shell"))["shell"])
    want = set(RE_CSS_URL.findall(read(css[0]))) | set(RE_SRC.findall(shell)) | pictures(copy, manifest)
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
    # it has, by the database, as ud's grow as it is written, and one of its
    # spoken text to each of those, its database for search, and its contents
    # for the rail; its size in a band.
    got = {t["key"]: t for t in manifest.get("translations", [])}
    if set(got) != set(exp["translations"]):
        bad.append(f"translations: {sorted(got)}, expected {sorted(exp['translations'])}")
    for key, want in exp["translations"].items():
        t = got.get(key)
        if t is None:
            continue
        twenties = [g for (g,) in con.execute(
            "SELECT DISTINCT p.paper_n / 20 FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
            " WHERE t.translation = ?", (key,))]
        groups = ({f"tr-{key}-{g}" for g in twenties} | {f"tr-{key}-speech-{g}" for g in twenties}
                  | {f"tr-{key}.db", f"tr-{key}-toc"})
        if {c["name"] for c in t["chunks"]} != groups:
            bad.append(f"{key}: {len(t['chunks'])} chunks, for {len(twenties)} twenties of papers, their"
                       " spoken text, search and its contents")
        lo, hi = want["download_mb"]
        if not lo <= t["bytes"] / 1e6 <= hi:
            bad.append(f"{key}: {t['bytes'] / 1e6:.2f} MB, expected {lo} to {hi}")
    # The Bible: the KJV's pages in Base, as the book's English is (Tigran,
    # 2026-11-21: "Pages in Base, like the book"), /bible a chunk and each of
    # its 66 books one, with its database for search; the Synodal a download
    # of its own, a chunk to each book it has and its database for search,
    # counted apart from the copy's, its size in a band.
    got_b = {x["key"]: x for x in manifest.get("bible", [])}
    want_b = exp.get("bible", {})
    if set(got_b) != set(want_b):
        bad.append(f"bible: {sorted(got_b)} in the manifest, {sorted(want_b)} expected")
    elif got_b:
        from ubsite import bible as B
        base = {"bible-toc", "bible-kjv.db"} | {f"bible-{b['abbr']}" for b in B.books() if b["kjv"]}
        names = {"rsb": {f"bible-rsb-{b['abbr']}" for b in B.books() if b["rsb"]} | {"bible-rsb.db"}}
        for key, x in got_b.items():
            if {c["name"] for c in x["chunks"]} != names[key]:
                bad.append(f"bible {key}: {len(x['chunks'])} chunks, expected {len(names[key])}")
            lo, hi = want_b[key]["download_mb"]
            if not lo <= x["bytes"] / 1e6 <= hi:
                bad.append(f"bible {key}: {x['bytes'] / 1e6:.2f} MB, expected {lo} to {hi}")
        if missing := base - {c["name"] for c in manifest["chunks"]}:
            bad.append(f"bible: {len(missing)} of the KJV's chunks not among the copy's own: {sorted(missing)[:5]}")
        if manifest["counts"].get("bible_pages") != exp["bible_pages"]:
            bad.append(f"bible: {manifest['counts'].get('bible_pages')} pages and fragments,"
                       f" expected {exp['bible_pages']:,}")
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
