"""The annotated reader.

Server-rendered HTML.  A citable corpus must produce a correct document at a URL
with JavaScript disabled -- for archive.org, for a Kindle browser, for curl --
so JS only enhances.

There is one mode: the study apparatus is always on.  The individual elements
-- red letter, paragraph numbers, the 1955 variants -- are switches under
Settings (ub.js, kept per browser), rather than one coarse lever that hides
them together; the margin index folds where it stands (templates/_fold.html).
"""

from __future__ import annotations

import functools
import gzip
import hashlib
import json
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "index"))

import cite  # noqa: E402
from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.exception_handlers import http_exception_handler  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from markupsafe import Markup, escape  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402

from ubsite import api, queries, settings, stats, visits  # noqa: E402

DB = ROOT / "var" / "ub.db"
STATIC = ROOT / "ubsite" / "static"
# The offline copy (offline/, `make offline`): its manifest and its chunks.
OFFLINE = ROOT / "var" / "offline"
# No /openapi.json: it described every HTML route by accident, and a site
# looking for the text API would have taken it for that.  /api documents it.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "ubsite" / "static"), name="static")
# The text API, /api/v1 (ubsite/api.py): before the catch-all /{ref} below.
app.include_router(api.router)
# Who reads what, from where: noted after each response, written by a thread
# (ubsite/visits.py).  The page carries nothing for it.
app.add_middleware(visits.Counter)
T = Jinja2Templates(directory=str(ROOT / "ubsite" / "templates"))


def entry_href(rslug: str, level: int, anchor: str) -> str:
    """Where an index entry lives: its headword's page, at the entry's own line.

    A headword is the page itself, so it takes no fragment; a subentry takes its
    anchor, and the concept page highlights it with :target.
    """
    return f"/i/{rslug}" + (f"#{anchor}" if level > 1 else "")


T.env.globals["entry_href"] = entry_href


@functools.lru_cache(maxsize=64)
def _asset(name: str, mtime_ns: int) -> str:
    return f"/static/{name}?v={hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]}"


def asset(name: str) -> str:
    """A static file's URL with a hash of its content: /static/ub.css?v=3f2a....

    So a page names the stylesheet and scripts it was made with.  An offline
    copy (sw.js) then always draws a page with its own build's, and a deploy
    reaches a browser that kept the old ones.  The server ignores the query.
    """
    return _asset(name, (STATIC / name).stat().st_mtime_ns)


T.env.globals["asset"] = asset


def _mark() -> Markup:
    """The site's mark, inline, from the one drawing in static/favicon.svg.

    Inline rather than <img> so that ub.css colours it from the theme tokens: an
    SVG image follows the operating system's dark mode, but not the site's own
    theme switch.  Its built-in colours are stripped; .logo rules supply them.
    """
    svg = (ROOT / "ubsite" / "static" / "favicon.svg").read_text()
    svg = re.sub(r"\s*<style>.*?</style>|\s*<!--.*?-->", "", svg, flags=re.S)
    return Markup(svg.replace("<svg ", '<svg class="logo" aria-hidden="true" focusable="false" ', 1))


T.env.globals["mark"] = _mark()


def appendix_href(scope: str, anchor: str) -> str:
    """Where an appendix entry lives: its line on the appendix's one page."""
    return f"/appendix/{scope}#{anchor}"


T.env.globals["appendix_href"] = appendix_href


def reading_time(words: int) -> str:
    """How long a reading path takes, at 230 words a minute: "about 12
    minutes", and in hours from an hour and a half."""
    minutes = max(1, round(words / 230))
    if minutes < 90:
        return f"about {minutes} minute{'s' if minutes > 1 else ''}"
    return f"about {round(minutes / 60)} hours"


T.env.globals["reading_time"] = reading_time

# Search reaches an Appendix B-F row only when no A-Z headword has its name: the
# other 1,332 would come up twice, once as the headword and once as the row.
APP_OWN = (" OR (e.scope IN ('B','C','D','E','F')"
           " AND e.id NOT IN (SELECT entry_id FROM appendix_head))")

RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$")
RE_TERM = re.compile(r'"([^"]*)"?|(\S+)')

# How many hits each list shows on the overview, and per page once a list is
# opened on its own with ?in=index, ?in=text or ?in=notes.
OVERVIEW = {"index": 25, "text": 40, "notes": 10}
PER_PAGE = 100


def _terms(q: str) -> list[tuple[str, bool]]:
    """The reader's terms, each (text, is a prefix): what fts_query quotes."""
    out = []
    for m in RE_TERM.finditer(q):
        text, star = m.group(1), False
        if text is None:
            text = m.group(2)
            if text.endswith("*"):
                text, star = text.rstrip("*"), True
        if any(c.isalnum() for c in text):
            out.append((text, star))
    return out


def fts_query(q: str) -> str | None:
    """The reader's words as an FTS5 query that cannot fail to parse.

    FTS5 has a syntax of its own -- `-` and `:` open a column filter, `"` and
    `'` delimit strings, AND/OR/NOT/NEAR are operators -- and passing the query
    through raw made "self-conscious" ask for a column called `conscious`: every
    hyphenated word in the book was a 500.  So every term is quoted.  The
    tokenizer then reads "self-conscious" as the two-word phrase it is, a
    double-quoted phrase stays one phrase, and only a trailing * survives, as a
    prefix.  A term with no letter or digit in it is dropped: FTS5 treats an
    empty phrase as matching nothing, and would empty the whole result.
    """
    return " ".join(_phrase(text, star) for text, star in _terms(q)) or None


def _phrase(text: str, star: bool) -> str:
    return '"' + text.replace('"', '""') + '"' + ("*" if star else "")


# As build/schema/004_fts.sql declares it; tests/test_search.py holds them equal.
TOKENIZE = "unicode61 remove_diacritics 2"


def mark_terms(texts: list[str], q: str) -> list[Markup]:
    """Each text with what the search matched in <mark>, as snippet() marks a paragraph.

    An index hit is shown by its chip -- `path_plain`, or a Chronology event's
    dated label -- which is not a column FTS5 indexes, so snippet() cannot reach
    it.  Rather than copy the tokenizer's rules (Unicode 6.1's idea of a letter,
    diacritics folded, a prefix, a phrase), the texts go into a throwaway table
    with the same tokenizer and FTS5's own highlight() marks them.  The terms are
    OR'd: a hit can match one of them only in a citation, and its chip should
    still show the others.  The marks go in as control characters and become
    tags only after the text is escaped, so "6. & 7." stays text.
    """
    terms = _terms(q)
    if not terms or not texts:
        return [escape(t) for t in texts]
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE VIRTUAL TABLE t USING fts5(x, tokenize='{TOKENIZE}')")
    con.executemany("INSERT INTO t(rowid, x) VALUES (?, ?)", enumerate(texts))
    anyq = " OR ".join(_phrase(t, star) for t, star in terms)
    marked = dict(con.execute(
        "SELECT rowid, highlight(t, 0, char(2), char(3)) FROM t WHERE t MATCH ?", (anyq,)))
    con.close()
    return [_marked(marked.get(i, t)) for i, t in enumerate(texts)]


def _marked(s: str) -> Markup:
    """Text with FTS5's marks, \\x02 and \\x03, as <mark> tags, escaped first."""
    return Markup(str(escape(s)).replace("\x02", "<mark>").replace("\x03", "</mark>"))


RE_WORD = re.compile(r"\S+")
RE_GLUE = re.compile(r"(.*?)(\S*)\Z", re.S)


def _around(text: str, at: int, before: int = 8, after: int = 6) -> tuple[str, str, str, str]:
    """Today's words on either side of a 1955 note's ring, `at` in `text`.

    The ring stands after the words that changed, so what shows is what
    replaced the 1955 reading, and enough on each side to read it by: so many
    words, cut where a word ends, with an ellipsis only where something was cut.
    As (lead, word, glue, rest): `word` and `glue` touch the ring on either
    side -- "forgo" and "", "mussels" and "," -- and the page keeps them on
    one line with it, which the browser would otherwise break around it.
    """
    head, tail = text[:at], text[at:]
    hw, tw = list(RE_WORD.finditer(head)), list(RE_WORD.finditer(tail))
    left = "…" + head[hw[-before].start():] if len(hw) > before else head
    right = tail[:tw[after - 1].end()] + "…" if len(tw) > after else tail
    lead, word = RE_GLUE.match(left).groups()
    glue = re.match(r"\S*", right).group(0)
    return lead, word, glue, right[len(glue):]


def db() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


# There is one mode, and it is the study apparatus.  What used to be Reading
# mode is now a set of switches under Settings -- red letter, the index in the
# margin, paragraph numbers, the 1955 readings -- kept in the browser and
# applied by base.html before first paint, rather than one coarse lever.
def mode_of(request: Request) -> str:
    return "study"


def page(request, template, status_code=200, **ctx):
    ctx.setdefault("mode", mode_of(request))
    return T.TemplateResponse(request, template, ctx, status_code=status_code)


def missing(request, msg: str):
    """A 404 that is still a page of the site, with its header and search box."""
    return page(request, "notfound.html", status_code=404, msg=msg,
                path=request.url.path)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    # Routes nothing matches, such as /i/foo/bar, would otherwise get FastAPI's
    # JSON {"detail": "Not Found"}.  Under /api/ a program is asking, and JSON
    # is what it can read.
    if request.url.path.startswith("/api/"):
        return api.error(exc.status_code, "There is no such endpoint." if exc.status_code == 404
                         else str(exc.detail))
    if exc.status_code == 404:
        return missing(request, "There is no page at this address.")
    return await http_exception_handler(request, exc)


@app.exception_handler(api.Unbuilt)
async def api_unbuilt(request: Request, exc: api.Unbuilt):
    return api.error(503, "This database was built before the text API.")


@functools.lru_cache(maxsize=4)
def _sources(mtime_ns: int) -> dict:
    try:
        rows = db().execute(
            "SELECT repo, commit_id, dirty, committed_at, commit_url"
            " FROM build_source").fetchall()
    except sqlite3.Error:
        # A database from before build_source or its commit_url -- a --no-data
        # deploy of this code over an older ub.db.  The footer then omits the
        # commits; every page turning into a 500 would be the worse failure.
        return {}
    return {r["repo"]: {"commit": r["commit_id"], "dirty": bool(r["dirty"]),
                        "date": r["committed_at"], "url": r["commit_url"]} for r in rows}


def sources() -> dict:
    """The commits this database was built from, keyed by repo.

    Cached on the file's mtime, so a database swapped in under a running server
    is re-read, and an unchanged one is not queried once per page.
    """
    try:
        return _sources(DB.stat().st_mtime_ns)
    except OSError:
        return {}


T.env.globals["sources"] = sources


@functools.lru_cache(maxsize=4)
def _voices(mtime_ns: int) -> list[dict]:
    try:
        return [dict(r) for r in db().execute(
            "SELECT key, label, kind, granularity, credit, credit_url FROM audio_source ORDER BY id")]
    except sqlite3.Error:
        return []                                  # a database from before 005_audio.sql


def voices() -> list[dict]:
    """The readings this database carries, in the order Settings lists them."""
    try:
        return _voices(DB.stat().st_mtime_ns)
    except OSError:
        return []


T.env.globals["voices"] = voices


def db_version() -> int:
    """Which database this is: its mtime, which every cache here keys on."""
    try:
        return DB.stat().st_mtime_ns
    except OSError:
        return 0


ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


@functools.lru_cache(maxsize=4)
def _book(mtime_ns: int) -> dict:
    con = db()
    sections: dict[int, list[dict]] = {}
    for r in con.execute("SELECT paper_n, n, title_html, combined_with FROM section"
                         " ORDER BY paper_n, n"):
        sections.setdefault(r["paper_n"], []).append(dict(r))
    papers = [dict(r) for r in con.execute("SELECT n, title, part_n FROM paper ORDER BY n")]
    parts = [dict(r, roman=ROMAN[r["n"]],
                  papers=[p for p in papers if p["part_n"] == r["n"]])
             for r in con.execute("SELECT n, title FROM part ORDER BY n")]
    # What the rail draws, hashed: the rail asks for a paper's sections under
    # it (/rail/N?v=...), so a browser may keep the answer for good and still
    # never show a stale one.  Not the database's mtime, which every build
    # moves: every section page carries it, and the offline copy would change
    # every paper's chunk with each deploy, the book unchanged.
    v = hashlib.sha256(json.dumps([papers, sections], sort_keys=True).encode()).hexdigest()[:12]
    return {"foreword": [p for p in papers if p["part_n"] is None],
            "parts": parts, "sections": sections, "v": v}


def book() -> dict:
    """The whole book as the left rail draws it: the Foreword, the four parts
    with their papers, and every paper's sections.  Cached on the database's
    mtime, as sources() is."""
    return _book(db_version())


T.env.globals["book"] = book
T.env.globals["settings_groups"] = settings.groups
T.env.globals["settings_defaults"] = settings.defaults()


# Asked for by fixed name at the root, with or without a <link>: browsers try
# /favicon.ico, iOS /apple-touch-icon.png.  Both are drawn from favicon.svg by
# tools/make_icons.py.  Without these they fell through to the {ref} route and
# got the not-found page, as HTML.
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(ROOT / "ubsite" / "static" / "favicon.ico", media_type="image/x-icon")


@app.get("/apple-touch-icon.png", include_in_schema=False)
def touch_icon():
    return FileResponse(ROOT / "ubsite" / "static" / "apple-touch-icon.png")


@app.get("/audio/{key}/{name:path}", include_in_schema=False)
def audio_file(key: str, name: str):
    """A recording, by the name the database lists -- and only such a name.

    Nothing is resolved from the URL alone: the file must be a row of
    audio_file, so no path the build did not check can be served.  Starlette
    answers a Range request with 206, which Safari needs before it will seek.
    The names never change content (the MH files are pinned by SHA-256 in
    data/audio/mh-files.tsv, the synthetic ones carry their hash), so a browser
    may keep them for good.
    """
    try:
        row = db().execute(
            "SELECT s.root FROM audio_file f JOIN audio_source s ON s.id=f.source_id"
            " WHERE s.key=? AND f.name=?", (key, name)).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        raise HTTPException(status_code=404)
    # A relative root is the project's own (the AI voice, under var/).
    return FileResponse(ROOT / row["root"] / name, media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


def section_audio(con, section_id: int) -> dict:
    """Every voice's segments for one section, as listen.js wants them.

    {key: {label, kind, by, files: [url, ...], segs: [[ref, file, start, end], ...]}}
    A segment's ref is its paragraph's, or null for the spoken heading.
    """
    out = {}
    try:
        rows = con.execute(
            "SELECT s.key, s.label, s.kind, s.granularity, s.credit, s.credit_url,"
            "  f.name, g.start_ms, g.end_ms,"
            "  p.ref FROM audio_segment g JOIN audio_source s ON s.id=g.source_id"
            " JOIN audio_file f ON f.id=g.file_id"
            " LEFT JOIN paragraph p ON p.id=g.paragraph_id"
            " WHERE g.section_id=? ORDER BY s.id, g.ord", (section_id,)).fetchall()
    except sqlite3.Error:
        return {}
    for r in rows:
        v = out.setdefault(r["key"], {"label": r["label"], "kind": r["kind"],
                                      "by": r["granularity"], "credit": r["credit"],
                                      "credit_url": r["credit_url"], "files": [], "segs": []})
        url = f"/audio/{r['key']}/{r['name']}"
        if url not in v["files"]:
            v["files"].append(url)
        v["segs"].append([r["ref"], v["files"].index(url), r["start_ms"], r["end_ms"]])
    return out


@app.get("/speech/{ref}", include_in_schema=False)
def speech(ref: str):
    """A section's text as a voice reads it (build/speech.py), for the
    browser's own voice: {"segs": [[ref, text], ...]} in reading order, the
    heading first with ref null.  listen.js fetches it only when that voice is
    chosen, so a page carries its text once.
    """
    m = re.fullmatch(r"(\d+):(\d+)", ref)
    rows = db().execute(
        "SELECT p.ref, x.text FROM speech x JOIN section s ON s.id=x.section_id"
        " LEFT JOIN paragraph p ON p.id=x.paragraph_id"
        " WHERE s.paper_n=? AND s.n=? ORDER BY p.para_n IS NOT NULL, p.para_n",
        (int(m[1]), int(m[2]))).fetchall() if m else []
    if not rows:
        raise HTTPException(status_code=404)
    return JSONResponse({"segs": [[r["ref"], r["text"]] for r in rows]},
                        headers={"Cache-Control": "no-cache"})


# --------------------------------------------------------------------------
# Work offline.  A reader who turns it on in Settings registers /sw.js, which
# downloads the copy that `make offline` built (offline/, var/offline/) and
# answers from it when the network does not.  Nobody else runs the worker.

# SQLite's WebAssembly build (vendor/sqlite-wasm/), which searches the copy.
ENGINE = {"sqlite3.js": "text/javascript", "sqlite3.wasm": "application/wasm"}
RE_CHUNK = re.compile(r"[0-9a-f]{16}\.gz")


@functools.lru_cache(maxsize=4)
def _engine(name: str, mtime_ns: int) -> tuple[bytes, str]:
    data = (ROOT / "vendor" / "sqlite-wasm" / name).read_bytes()
    return gzip.compress(data, 9, mtime=0), hashlib.sha256(data).hexdigest()[:10]


def engine(name: str) -> tuple[bytes, str]:
    """A file of the engine, gzipped once, and the hash its URL carries."""
    return _engine(name, (ROOT / "vendor" / "sqlite-wasm" / name).stat().st_mtime_ns)


def _etagged(request: Request, body: bytes, media_type: str, salt: str = "", **headers) -> Response:
    """`body`, or a bodiless 304 when the browser holds it already.  A browser
    with Work offline on asks again for the worker and the scripts it imports
    after every page it loads, to see whether the worker has changed."""
    tag = '"' + hashlib.sha256(body).hexdigest()[:16] + salt + '"'
    headers = {"ETag": tag, "Cache-Control": "no-cache", **headers}
    if tag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=media_type, headers=headers)


@app.get("/sw.js", include_in_schema=False)
def service_worker(request: Request):
    """The offline copy's service worker, at the root so that its scope is the
    whole site.  The scripts it loads are named with their hashes, put in place
    of __VERSIONS__ here, so that a change to any of them is a change to this
    file, which is what makes a browser install the worker again."""
    v = {"core": asset("offline-core.js"),
         **{k.split(".")[1]: f"/offline/{k}?v={engine(k)[1]}" for k in ENGINE}}
    src = (STATIC / "sw.js").read_text()
    if src.count("var V = __VERSIONS__;") != 1:
        raise RuntimeError("static/sw.js has lost its `var V = __VERSIONS__;`")
    body = src.replace("var V = __VERSIONS__;", f"var V = {json.dumps(v)};")
    return _etagged(request, body.encode(), "text/javascript")


@app.get("/offline/manifest.json", include_in_schema=False)
def offline_manifest(request: Request):
    """What the copy holds: every chunk, by the hash of its bytes.  A worker
    asks for it to learn whether its copy is still the site's, and its ETag
    makes the usual answer a 304 of a few hundred bytes."""
    try:
        body = (OFFLINE / "manifest.json").read_bytes()
    except OSError:
        return Response("No offline copy has been built.\n", status_code=404, media_type="text/plain")
    return _etagged(request, body, "application/json")


@app.get("/offline/c/{name}", include_in_schema=False)
def offline_chunk(name: str):
    """A chunk of the copy, gzipped, named by its hash, so kept for good."""
    f = OFFLINE / "c" / name
    if not RE_CHUNK.fullmatch(name) or not f.is_file():
        return Response("No such chunk.\n", status_code=404, media_type="text/plain")
    return FileResponse(f, media_type="application/octet-stream",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/offline/{name}", include_in_schema=False)
def offline_engine(name: str, request: Request):
    if name not in ENGINE:
        return Response("No such file.\n", status_code=404, media_type="text/plain")
    body, _ = engine(name)
    if "gzip" not in request.headers.get("accept-encoding", ""):
        return _etagged(request, gzip.decompress(body), ENGINE[name], Vary="Accept-Encoding")
    return _etagged(request, body, ENGINE[name], "-gz", Vary="Accept-Encoding", **{"Content-Encoding": "gzip"})


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    """What lets a reader install the site as an app: a Home Screen icon, and on
    an iPhone the only way an offline copy is kept for good (Safari deletes a
    site's stored data after seven days of use without a visit)."""
    return JSONResponse({
        "name": "The Urantia Book", "short_name": "Urantia Book",
        "description": "The Uversa Press text read together with its index.",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#f8f5f0", "theme_color": "#f8f5f0",  # --paper
        "icons": [{"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@app.get("/healthz")
def healthz():
    """What deploy.sh polls, and what a restart must satisfy before it counts.

    Touches the database rather than just returning 200, so a deploy that ships
    a missing or truncated ub.db fails at the push instead of at a reader.  The
    source commits say which text and index the site carries, so whether it is
    behind is one comparison with `git rev-parse HEAD` in each repo.
    """
    try:
        con = db()
        n = con.execute("SELECT value FROM stat WHERE key='paragraphs'").fetchone()
        built = con.execute("SELECT built_at FROM build").fetchone()
        tv = con.execute("SELECT value FROM stat WHERE key='text_version'").fetchone()
        return {"ok": bool(n and n[0] == 14586), "paragraphs": n[0] if n else 0,
                "built_at": built[0] if built else None,
                "text_version": tv[0] if tv else None,
                "sources": {k: {"commit": v["commit"], "dirty": v["dirty"]}
                            for k, v in sources().items()}}
    except Exception as exc:                       # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.get("/stats", include_in_schema=False)
def stats_page(request: Request, days: str = "30", me: str = ""):
    """Who visits, from where, and what they read: the owner's page.

    Behind HTTP Basic auth (ubsite/stats.py); without var/stats.passwd it does
    not exist.  It marks the browser that opens it with the cookie ub_me=1, so
    that the owner's own reading is not counted; ?me=count says count it after
    all (ub_me=0), and ?me=skip goes back.
    """
    ok = stats.allowed(request.headers.get("authorization"))
    if ok is None:
        return missing(request, "There is no page at this address.")
    if not ok:
        return Response("The password is wrong, or was not given.", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="ubsite stats", charset="UTF-8"'})
    period = days if days in stats.PERIODS else "30"
    skip = {"count": "0", "skip": "1"}.get(me, request.cookies.get("ub_me", "1"))
    resp = page(request, "stats.html", r=stats.report(db(), stats.PERIODS[period]),
                period=period, periods=stats.PERIODS, counted=skip == "0")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex"
    resp.set_cookie("ub_me", skip, max_age=10 * 365 * 86400, path="/", secure=True,
                    httponly=True, samesite="lax")
    return resp


# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    con = db()
    stats = dict(con.execute("SELECT key, value FROM stat").fetchall())
    # The A-Z alone: index_entries in `stat` also counts the appendices and the
    # chronology, which the home page counts on a line of their own.
    stats["headwords"] = con.execute(
        "SELECT COUNT(*) FROM index_entry WHERE scope='az' AND level=1").fetchone()[0]
    stats["az_entries"] = con.execute(
        "SELECT COUNT(*) FROM index_entry WHERE scope='az'").fetchone()[0]
    stats["app_events"], stats["app_names"] = con.execute(
        "SELECT SUM(n_events), SUM(n_entries) FROM appendix").fetchone()
    parts = con.execute("SELECT * FROM part ORDER BY n").fetchall()
    papers = con.execute("SELECT * FROM paper ORDER BY n").fetchall()
    return page(request, "home.html", stats=stats, parts=parts, papers=papers)


@app.get("/read", response_class=HTMLResponse)
def contents(request: Request):
    con = db()
    parts = con.execute("SELECT * FROM part ORDER BY n").fetchall()
    papers = con.execute("SELECT * FROM paper ORDER BY n").fetchall()
    return page(request, "contents.html", parts=parts, papers=papers)


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", scope: str = Query("", alias="in"),
           page_no: str = Query("1", alias="page")):
    """Index hits, text hits and the 1955 readings, kept apart.

    With no `in`, an overview: the first few of each list.  `in=index`,
    `in=text` or `in=notes` opens that one list whole, a hundred to a page.
    Either way the number beside a heading counts exactly what its list holds,
    so "Show all" always delivers the number it promised.
    """
    q = q.strip()
    con = db()
    jump = cite.parse(q) if q else None
    if jump is not None:
        tg = list(jump.expand())
        if tg:
            p, s, n = tg[0]
            # A range of paragraphs opens whole, /86:5.14-15, as the address
            # takes it, and the address says what is wrong with one that
            # cannot be.  Only the first span: an address holds one range, not
            # a list, so 86:5.14,16 opens at 14 as before.
            if jump.kind == "para" and jump.spans[0][1] != n:
                n = f"{n}-{jump.spans[0][1]}"
            to = (f"/{p}" if s is None else f"/{p}:{s}"
                  + (f".{n}" if n is not None else ""))
            return RedirectResponse(to, status_code=303)
    scope = scope if scope in ("index", "text", "notes") else ""
    number = int(page_no) if page_no.isdigit() and int(page_no) > 0 else 1
    fq = fts_query(q)
    heads, idx, txt, old = [], None, None, None
    if q and scope in ("", "index"):
        # An exact headword match must win.  Full-text rank cannot deliver that
        # -- bm25 scores term statistics and has no notion that the query names
        # an entry -- so searching "Jesus" put Joshua, parables and Amos above
        # it and the 796-entry article never appeared. Headwords are therefore
        # resolved separately: exact first, then prefix, then everything else.
        #
        # An Appendix B-F name counts as a headword when the A-Z has none by that
        # name -- 'Sumeria', 'widow in Rome' -- and links to its appendix line.
        heads = con.execute(
            "SELECT e.id, e.slug, e.headword, e.scope, e.anchor, a.title AS appendix,"
            "  (SELECT n_descendants FROM entry_stats WHERE entry_id=e.id) AS kids"
            " FROM index_entry e LEFT JOIN appendix a ON a.letter=e.scope"
            " WHERE (e.scope='az' AND e.level=1" + APP_OWN + ")"
            "   AND (LOWER(RTRIM(e.headword,'.')) = LOWER(?)"
            "        OR LOWER(e.headword) LIKE LOWER(?) || '%')"
            " ORDER BY LOWER(RTRIM(e.headword,'.')) = LOWER(?) DESC,"
            "          e.scope<>'az', e.ord"
            " LIMIT 12",
            (q, q, q)).fetchall()
    if fq and scope in ("", "index"):
        # The headwords listed above are left out of this list, by entry id.
        # Not by slug: a subentry links through its headword's slug, so that
        # would drop every subentry of a headword already shown.
        shown = [h["id"] for h in heads]
        where = (" FROM index_entry_fts f JOIN index_entry e ON e.id=f.rowid"
                 " WHERE index_entry_fts MATCH ? AND (e.scope IN ('az','A')" + APP_OWN + ")"
                 + (f" AND e.id NOT IN ({','.join('?' * len(shown))})" if shown else ""))
        n = con.execute("SELECT COUNT(*)" + where, (fq, *shown)).fetchone()[0]
        size, off = _window(scope == "index", "index", number, n)
        rows = con.execute(
            "SELECT e.path_plain AS path, e.level, e.anchor, e.scope,"
            "  (SELECT slug FROM index_entry WHERE id=e.root_id) AS rslug,"
            "  (SELECT title FROM appendix WHERE letter=e.scope) AS appendix,"
            "  (SELECT label FROM chronology_event WHERE entry_id=e.id) AS event"
            + where + " ORDER BY rank LIMIT ? OFFSET ?",
            (fq, *shown, size, off)).fetchall()
        # What each hit shows, with the reader's words marked as in the text hits.
        marked = mark_terms([r["event"] or r["path"] for r in rows], q)
        idx = _hits(n, off, [dict(r, marked=m) for r, m in zip(rows, marked)])
    if fq and scope in ("", "text"):
        n = con.execute("SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?",
                        (fq,)).fetchone()[0]
        size, off = _window(scope == "text", "text", number, n)
        txt = _hits(n, off, con.execute(
            "SELECT p.ref, snippet(paragraph_fts, 0, '<mark>', '</mark>', '…', 24) AS s"
            " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid"
            " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT ? OFFSET ?",
            (fq, size, off)).fetchall())
    if fq and scope in ("", "notes"):
        # What the 1955 cards say: the reading, and the committee's reasons beneath
        # it.  Always looked up, and shown only when Settings asks (ub.css
        # .by1955, off by default), for settings never reach the server.
        where = (" FROM footnote_fts x JOIN footnote f ON f.id=x.rowid"
                 " JOIN paragraph p ON p.id=f.paragraph_id"
                 " WHERE footnote_fts MATCH ? AND f.kind='variant-1955'")
        n = con.execute("SELECT COUNT(*)" + where, (fq,)).fetchone()[0]
        size, off = _window(scope == "notes", "notes", number, n)
        hits = con.execute(
            "SELECT f.id, highlight(footnote_fts, 0, char(2), char(3)) AS reading,"
            "  snippet(footnote_fts, 1, char(2), char(3), '…', 20) AS reasons"
            + where + " ORDER BY p.ord, f.ord LIMIT ? OFFSET ?", (fq, size, off)).fetchall()
        found = {n["id"]: n for n in queries.notes(
            con, f"f.id IN ({','.join('?' * len(hits))})", tuple(h["id"] for h in hits))}
        old = _hits(n, off, [
            _old_hit(found[h["id"]], _marked(h["reading"]),
                     # Only where the search found something in them.
                     reasons=_marked(h["reasons"]) if "\x02" in h["reasons"] else None)
            for h in hits])
    if q:
        # For the visit counter: a search that finds nothing is one the index might
        # answer.  So the 1955 readings, which most readers never see, count only
        # where a reader asked for them alone.
        request.state.hits = (len(heads) + (idx["n"] if idx else 0) + (txt["n"] if txt else 0)
                              + (old["n"] if old and scope == "notes" else 0))
    return page(request, "search.html", q=q, scope=scope, idx=idx, txt=txt, old=old,
                heads=heads, diagnose=cite.diagnose(q) if q else None)


def _old_hit(n: dict, reading: Markup, **more) -> dict:
    """One 1955 reading for a list (templates/_old.html), on the List of 1955
    readings and among the search results: its note (queries.notes), the
    reading as that list shows it, and today's words around its ring.  `more`
    is what that list alone shows -- `dec`, the verdict on the line, and
    `reasons`, a search's snippet -- under keys of their own: the note's
    columns are what its card is made from."""
    return {**n, "reading": reading, "now": _around(n["para_text"], n["anchor"]), **more}


def _window(whole: bool, kind: str, number: int, n: int) -> tuple[int, int]:
    """(LIMIT, OFFSET) for one list: its overview slice, or one page of it whole.
    A page past the end is read as the last page."""
    if not whole:
        return OVERVIEW[kind], 0
    last = max(1, -(-n // PER_PAGE))
    return PER_PAGE, (min(number, last) - 1) * PER_PAGE


def _hits(n: int, off: int, rows) -> dict:
    return {"n": n, "rows": rows, "first": off + 1, "last": off + len(rows),
            "page": off // PER_PAGE + 1, "more": off + len(rows) < n}


@app.get("/index", response_class=HTMLResponse)
def index_front(request: Request):
    con = db()
    letters = con.execute(
        "SELECT letter, COUNT(*) n FROM index_entry WHERE scope='az' AND level=1"
        " GROUP BY letter ORDER BY letter='NUMBERS' DESC, letter").fetchall()
    return page(request, "index_front.html", letters=letters, apps=queries.appendices(con))


@app.get("/index/{letter}", response_class=HTMLResponse)
def index_letter(request: Request, letter: str):
    con = db()
    rows = con.execute(
        "SELECT e.slug, e.headword, e.text, s.n_descendants"
        " FROM index_entry e JOIN entry_stats s ON s.entry_id=e.id"
        " WHERE e.scope='az' AND e.level=1 AND e.letter=? ORDER BY e.ord",
        (letter.upper(),)).fetchall()
    if not rows:
        return missing(request, f"The index has no section headed “{letter}”.")
    return page(request, "index_letter.html", letter=letter.upper(), rows=rows)


@app.get("/i/{slug}", response_class=HTMLResponse)
def concept(request: Request, slug: str):
    con = db()
    root = con.execute("SELECT * FROM index_entry WHERE slug=?", (slug,)).fetchone()
    if root is None:
        return missing(request, "No headword in the index has this address.")
    return page(request, "concept.html", root=root, **queries.concept(con, root["id"]))


# A headword's reading path: every paragraph it cites, read as one text, in the
# order of the book or by the index's own groups (queries.reading_path).  A
# headword citing too few paragraphs to have one goes to its concept page, and
# one whose citations all fall in one group has nothing to read by theme.
@app.get("/i/{slug}/read", response_class=HTMLResponse)
def reading_path(request: Request, slug: str):
    return _reading_path(request, slug, "book")


@app.get("/i/{slug}/read/theme", response_class=HTMLResponse)
def reading_path_theme(request: Request, slug: str):
    return _reading_path(request, slug, "theme")


def _reading_path(request: Request, slug: str, by: str):
    con = db()
    root = con.execute("SELECT * FROM index_entry WHERE slug=?", (slug,)).fetchone()
    if root is None:
        return missing(request, "No headword in the index has this address.")
    c = queries.concept(con, root["id"])
    if c["path"] is None:
        return RedirectResponse(f"/i/{slug}", status_code=307)
    if by == "theme" and c["path"]["n_chapters"] < 2:
        return RedirectResponse(f"/i/{slug}/read", status_code=307)
    return page(request, "path.html", path=c["path"], xrefs=c["xrefs"], near=c["near"],
                **queries.reading_path(con, root["id"], by))


@app.get("/appendix", response_class=HTMLResponse)
def appendix_front(request: Request):
    return page(request, "appendices.html", apps=queries.appendices(db()))


@app.get("/appendix/{letter}", response_class=HTMLResponse)
def appendix(request: Request, letter: str):
    if letter.upper() != letter and len(letter) == 1:
        return RedirectResponse(f"/appendix/{letter.upper()}", status_code=301)
    con = db()
    app_ = con.execute("SELECT * FROM appendix WHERE letter=?", (letter,)).fetchone()
    if app_ is None:
        return missing(request, "The appendices are lettered A to F.")
    if letter != "A":
        rows = queries.appendix_rows(con, letter)
        # Where each initial begins, for the jump bar: the list is in the print's
        # order, which is alphabetical without regard to case.
        initials = []
        for r in rows:
            c = r["headword"][:1].upper()
            c = c if c.isalpha() else "#"
            if not initials or initials[-1][0] != c:
                initials.append((c, r["anchor"]))
        return page(request, "appendix.html", app=app_, apps=queries.appendices(con),
                    rows=rows, initials=initials if len(rows) > 150 else [])
    years, bands = queries.chronology(con)
    return page(request, "chronology.html", app=app_, apps=queries.appendices(con),
                years=years, bands=bands)


# The edition's lists, as a book's front matter names them: the 1955 readings
# now, the illustrations and the study notes with Phase 6 (Tigran, 2026-10-12).
@app.get("/lists", response_class=HTMLResponse)
def lists(request: Request):
    stats = dict(db().execute("SELECT key, value FROM stat").fetchall())
    return page(request, "lists.html", stats=stats)


@app.get("/lists/1955", response_class=HTMLResponse)
def list_1955(request: Request):
    """Every 1955 reading in one list, by paper, in the order of the book.

    The reading as the press gives it (footnote.html, which keeps its italics),
    today's words around the ring, and the committee's verdict.  The ring opens
    the card in place, as in the text; the reference opens the paragraph.
    """
    groups: list[dict] = []
    for n in queries.notes(db()):
        if not groups or groups[-1]["n"] != n["paper_n"]:
            groups.append({"n": n["paper_n"], "title": n["paper_title"], "rows": []})
        groups[-1]["rows"].append(_old_hit(n, Markup(n["html"]), dec=n["verdict"]))
    return page(request, "list_1955.html", groups=groups,
                n=sum(len(g["rows"]) for g in groups))


# The passage /api shows a reply for: across a section's end, so that the reply
# has two sections in it.
PASSAGE = "101:4.7-5.2"


@app.get("/api", response_class=HTMLResponse)
def api_docs(request: Request):
    """How another site keeps its copy of the text in step with ours (ubsite/api.py)."""
    meta = api.about_meta()
    con = db()
    # The red letter, an italic and a list mark; a paragraph and a section the
    # Foundation numbers otherwise; a 1955 reading.
    example = {}
    for kind, key in (("paragraph", "147:4.4"), ("paragraph", "144:5.11"), ("section", "139:9"),
                      ("paragraph", "112:1.7")):
        row = con.execute("SELECT body FROM text_unit WHERE kind=? AND key=?",
                          (kind, key)).fetchone()
        if row:
            example[key] = json.dumps(json.loads(row[0]), ensure_ascii=False, indent=1)
    base = str(request.base_url)
    since, reply = api.example(base)
    return page(request, "api.html", base=base, meta=meta, example=example,
                api_licence=api.licence(base), reply=reply, reply_since=since,
                passage=api.example_selection(base, PASSAGE), passage_refs=PASSAGE)


@app.get("/rail/{paper:int}", include_in_schema=False)
def rail_sections(request: Request, paper: int, v: str = ""):
    """One paper's sections, for the left rail when a reader opens that paper.

    A section page carries the tree only down to the papers, and its own
    paper's sections: all 1,626 inline would add 111 KB to a page of about 20.
    Asked for under the rail's version (book()["v"]), the answer is kept for good.
    """
    secs = book()["sections"].get(paper)
    if secs is None:
        return Response("No such paper.\n", status_code=404, media_type="text/plain")
    cache = "public, max-age=31536000, immutable" if v == book()["v"] else "no-cache"
    return T.TemplateResponse(request, "rail_sections.html",
                              {"paper_n": paper, "secs": secs},
                              headers={"Cache-Control": cache})


@app.get("/part/{n:int}", response_class=HTMLResponse)
def part_page(request: Request, n: int):
    """A part's own page: its divider, as the book prints it, and nothing more.

    The rail's part titles link here, so a part opens on its title page rather
    than only unfolding in the rail.
    """
    con = db()
    part = con.execute("SELECT * FROM part WHERE n=?", (n,)).fetchone()
    if part is None:
        return missing(request, "There are four parts, I to IV.")
    # Its one way on is the transport bar's ⏭, to its first paper's first
    # section (Tigran, 2026-10-14).
    fp = part["first_paper"]
    first = con.execute("SELECT MIN(n) FROM section WHERE paper_n=?", (fp,)).fetchone()[0]
    nxt = {"href": f"/{fp}:{first}", "label": f"Next section: {fp}:{first}"}
    return page(request, "part.html", part=part, roman=ROMAN[n], nxt=nxt)


@app.get("/{paper:int}")
def paper_page(request: Request, paper: int):
    """A paper number opens the paper, not a table of its sections.

    Every paper begins with an unnumbered introduction, so /101 lands on
    101:0 -- the first words of the text.  The section list is always in the
    left rail, so a separate page for it was a click that bought nothing.
    """
    con = db()
    first = con.execute(
        "SELECT MIN(n) FROM section WHERE paper_n=?", (paper,)).fetchone()[0]
    if first is None:
        return missing(request, f"There is no Paper {paper}. The Foreword is Paper 0,"
                                " and the papers run to 196.")
    return RedirectResponse(f"/{paper}:{first}", status_code=307)


@app.get("/{ref}", response_class=HTMLResponse)
def read(request: Request, ref: str):
    m = RE_REF.match(ref)
    if not m:
        return missing(request, "There is no page at this address.")
    paper, sec = int(m.group(1)), int(m.group(2))
    focus = int(m.group(3)) if m.group(3) else None
    last = int(m.group(4)) if m.group(4) else focus
    con = db()
    p = con.execute("SELECT * FROM paper WHERE n=?", (paper,)).fetchone()
    s = con.execute("SELECT * FROM section WHERE paper_n=? AND n=?",
                    (paper, sec)).fetchone()
    if p is None:
        return missing(request, f"There is no Paper {paper}. The Foreword is Paper 0,"
                                " and the papers run to 196.")
    if s is None:
        return missing(request, f"Paper {paper} has no section {sec}.")
    # The paragraphs named must exist and a range run forwards, as the API
    # requires: /0:0.0-1 or /86:5.15-14 once opened the section with nothing
    # marked and nothing said.  Every section numbers its paragraphs 1..N.
    if focus is not None:
        here = f"{paper}:{sec}"
        n = con.execute("SELECT MAX(para_n) FROM paragraph WHERE paper_n=? AND section_n=?",
                        (paper, sec)).fetchone()[0]
        # What the message offers instead is a link to it.
        go = Markup('<a href="/{0}">{0}</a>').format
        for k in (focus, last):
            if not 1 <= k <= n:
                return missing(request, Markup("There is no paragraph {}: {} runs from {} to {}.")
                               .format(f"{here}.{k}", here, go(f"{here}.1"), go(f"{here}.{n}")))
        if last < focus:
            return missing(request, Markup("A range runs forwards, in the order of the book:"
                                           " {}, not {}.")
                           .format(go(f"{here}.{last}-{focus}"), f"{here}.{focus}-{last}"))
    rows = queries.section(con, paper, sec)
    go = transport(con, paper, sec)
    # Where listening goes on to: the next section, or from a paper's last
    # section the next paper's first, as the transport bar's ⏭ does.
    onward = None
    if go["next"]:
        n = go["next"]
        onward = {"href": n["href"], "label": f"{n['n']}. {n['title']}" if n["paper_n"] == paper
                  else f"Paper {n['paper_n']}. {n['ptitle']}"}
    return page(request, "section.html", paper=p, section=s, **rows,
                focus=focus, last=last, go=go, onward=onward,
                audio=section_audio(con, s["id"]))


def transport(con, paper: int, sec: int) -> dict:
    """The transport bar at a section's end: a paper back (fb), a section back
    (prev), a section on (next), a paper on (ff), in the order of the book.

    A section steps across a paper's edge, 101:0 back to 100's last section;
    a paper goes to its first section, never the /N redirect.  Part pages are
    not stops.  None at the book's ends.  The label is the tooltip and the
    accessible name alike (Tigran, 2026-10-14).
    """
    def paper_name(n):
        return "the Foreword" if n == 0 else str(n)

    def at(row, label):
        return row and {**dict(row), "href": f"/{row['paper_n']}:{row['n']}", "label": label}
    here = (paper, sec)
    prev = con.execute("SELECT paper_n, n FROM section WHERE (paper_n, n) < (?, ?)"
                       " ORDER BY paper_n DESC, n DESC LIMIT 1", here).fetchone()
    nxt = con.execute("SELECT s.paper_n, s.n, s.title, p.title AS ptitle FROM section s"
                      " JOIN paper p ON p.id=s.paper_id WHERE (s.paper_n, s.n) > (?, ?)"
                      " ORDER BY s.paper_n, s.n LIMIT 1", here).fetchone()
    fb = con.execute("SELECT paper_n, MIN(n) AS n FROM section WHERE paper_n < ?"
                     " GROUP BY paper_n ORDER BY paper_n DESC LIMIT 1", (paper,)).fetchone()
    ff = con.execute("SELECT paper_n, MIN(n) AS n FROM section WHERE paper_n > ?"
                     " GROUP BY paper_n ORDER BY paper_n LIMIT 1", (paper,)).fetchone()
    return {"fb": at(fb, fb and f"Previous paper: {paper_name(fb['paper_n'])}"),
            "prev": at(prev, prev and f"Previous section: {prev['paper_n']}:{prev['n']}"),
            "next": at(nxt, nxt and f"Next section: {nxt['paper_n']}:{nxt['n']}"),
            "ff": at(ff, ff and f"Next paper: {paper_name(ff['paper_n'])}")}
