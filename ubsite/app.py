"""The annotated reader.

Server-rendered HTML.  A citable corpus must produce a correct document at a URL
with JavaScript disabled -- for archive.org, for a Kindle browser, for curl --
so JS only enhances.

There is one mode: the study apparatus is always on.  The individual elements
-- red letter, the margin index, paragraph numbers, the 1955 variants -- are
switches under Settings (ub.js, kept per browser), rather than one coarse lever
that hides them together.
"""

from __future__ import annotations

import functools
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

from ubsite import settings, stats, visits  # noqa: E402

DB = ROOT / "var" / "ub.db"
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "ubsite" / "static"), name="static")
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

# What a margin chip needs.  An appendix entry -- a Chronology event, a named
# being, person or place -- has no headword of its own and so no slug; it links
# to its line on the appendix page, named with its appendix, and an event with
# its date (chronology_event.label).
CHIP_COLS = ("e.path_plain AS path, e.level, e.anchor, e.scope, r.slug AS rslug,"
                 " a.title AS appendix, ev.label AS event")
CHIP_JOIN = (" LEFT JOIN appendix a ON a.letter=e.scope"
                 " LEFT JOIN chronology_event ev ON ev.entry_id=e.id")
# An Appendix B-F row beside a paragraph the A-Z already names it at -- by its
# headword or any subentry, at any precision -- says nothing the margin does not
# already say.  1,734 of the 1,865 did ("Abaddon" over "Celestial Beings,
# Individuals Named Abaddon"); the classification they carried is on the
# concept page instead.  Chronology events have no appendix_head and all stay.
CHIP_NEW = (" AND NOT EXISTS (SELECT 1 FROM appendix_head h"
            " JOIN para_citers c2 ON c2.paragraph_id = c.paragraph_id"
            " JOIN index_entry e2 ON e2.id = c2.entry_id"
            " WHERE h.entry_id = e.id AND e2.root_id = h.head_entry_id)")

# Search reaches an Appendix B-F row only when no A-Z headword has its name: the
# other 1,332 would come up twice, once as the headword and once as the row.
APP_OWN = (" OR (e.scope IN ('B','C','D','E','F')"
           " AND e.id NOT IN (SELECT entry_id FROM appendix_head))")

RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$")
RE_TERM = re.compile(r'"([^"]*)"?|(\S+)')

# How many hits each list shows on the overview, and per page once a list is
# opened on its own with ?in=index or ?in=text.
OVERVIEW = {"index": 25, "text": 40}
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
    return [Markup(str(escape(marked.get(i, t)))
                   .replace("\x02", "<mark>").replace("\x03", "</mark>"))
            for i, t in enumerate(texts)]


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
    # JSON {"detail": "Not Found"}.
    if exc.status_code == 404:
        return missing(request, "There is no page at this address.")
    return await http_exception_handler(request, exc)


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
        return {"ok": bool(n and n[0] == 14586), "paragraphs": n[0] if n else 0,
                "built_at": built[0] if built else None,
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
    """Index hits and text hits, kept apart.

    With no `in`, an overview: the first few of each list.  `in=index` or
    `in=text` opens that one list whole, a hundred to a page.  Either way the
    number beside a heading counts exactly what its list holds, so "Show all"
    always delivers the number it promised.
    """
    q = q.strip()
    con = db()
    jump = cite.parse(q) if q else None
    if jump is not None:
        tg = list(jump.expand())
        if tg:
            p, s, n = tg[0]
            return RedirectResponse(
                f"/{p}:{s}" + (f".{n}" if n is not None else ""), status_code=303)
    scope = scope if scope in ("index", "text") else ""
    number = int(page_no) if page_no.isdigit() and int(page_no) > 0 else 1
    fq = fts_query(q)
    heads, idx, txt = [], None, None
    if q and scope != "text":
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
    if fq and scope != "text":
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
    if fq and scope != "index":
        n = con.execute("SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?",
                        (fq,)).fetchone()[0]
        size, off = _window(scope == "text", "text", number, n)
        txt = _hits(n, off, con.execute(
            "SELECT p.ref, snippet(paragraph_fts, 0, '<mark>', '</mark>', '…', 24) AS s"
            " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid"
            " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT ? OFFSET ?",
            (fq, size, off)).fetchall())
    if q:
        # For the visit counter: a search that finds nothing is one the index might answer.
        request.state.hits = (len(heads) + (idx["n"] if idx else 0) + (txt["n"] if txt else 0))
    return page(request, "search.html", q=q, scope=scope, idx=idx, txt=txt, heads=heads,
                diagnose=cite.diagnose(q) if q else None)


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
    return page(request, "index_front.html", letters=letters, apps=appendices(con))


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
    tree = con.execute(
        "SELECT e.*, s.n_targets FROM index_entry e"
        " LEFT JOIN entry_stats s ON s.entry_id=e.id"
        " WHERE e.root_id=? ORDER BY e.ord", (root["id"],)).fetchall()
    # A q.v. is linked where it stands, in the tree; this list is See and See also.
    xrefs = con.execute(
        "SELECT x.kind, x.target, t.slug FROM xref x"
        " LEFT JOIN index_entry t ON t.id=x.head_entry_id"
        " WHERE x.entry_id IN (SELECT id FROM index_entry WHERE root_id=?)"
        "   AND x.kind IN ('see','seealso')"
        " ORDER BY x.kind, x.ord", (root["id"],)).fetchall()
    # The appendices that list this headword: what kind of thing it is -- a
    # being, a person, a place -- and its line there.
    listed = con.execute(
        "SELECT e.scope, e.anchor, a.title FROM appendix_head h"
        " JOIN index_entry e ON e.id=h.entry_id JOIN appendix a ON a.letter=e.scope"
        " WHERE h.head_entry_id=? ORDER BY e.scope", (root["id"],)).fetchall()
    near = con.execute(
        "SELECT o.slug, o.headword, c.shared,"
        "  (SELECT n_descendants FROM entry_stats WHERE entry_id=o.id) AS kids"
        " FROM cocitation c"
        " JOIN index_entry o ON o.id = CASE WHEN c.a_root_id=? THEN c.b_root_id"
        "                                   ELSE c.a_root_id END"
        " WHERE c.a_root_id=? OR c.b_root_id=? ORDER BY c.shared DESC LIMIT 8",
        (root["id"], root["id"], root["id"])).fetchall()
    return page(request, "concept.html", root=root, tree=tree, xrefs=xrefs, near=near,
                listed=listed)


def appendices(con) -> list:
    """The six appendices, for /appendix, /index and each appendix's own page."""
    return con.execute("SELECT letter, title, n_entries, n_events FROM appendix"
                       " ORDER BY letter").fetchall()


# The Chronology's jump bar.  The printed list has no divisions; these are only
# for finding one's place among 206 year headings.  The first three follow the
# book's own unit, which is "years ago" until Adam and B.C. from him on; the
# life of Jesus, from the announcements of 8 B.C. to 30 A.D., is half the list.
CHRON_BANDS = ["Billions of years ago", "Millions of years ago",
               "Thousands of years ago", "B.C.", "The life of Jesus", "A.D."]


def _band(label: str, year_sort: float) -> int:
    if "years ago" in label:
        n = int(label.split()[0].replace(",", ""))
        return 0 if n >= 10**9 else 1 if n >= 10**6 else 2
    return 3 if year_sort < -8 else 4 if year_sort <= 30 else 5


def _year_id(label: str) -> str:
    """'y-7-b-c' for 7 B.C.: from the label, so that it does not move."""
    return "y-" + re.sub(r"[^0-9a-z]+", "-", label.lower()).strip("-")


@app.get("/appendix", response_class=HTMLResponse)
def appendix_front(request: Request):
    return page(request, "appendices.html", apps=appendices(db()))


@app.get("/appendix/{letter}", response_class=HTMLResponse)
def appendix(request: Request, letter: str):
    if letter.upper() != letter and len(letter) == 1:
        return RedirectResponse(f"/appendix/{letter.upper()}", status_code=301)
    con = db()
    app_ = con.execute("SELECT * FROM appendix WHERE letter=?", (letter,)).fetchone()
    if app_ is None:
        return missing(request, "The appendices are lettered A to F.")
    if letter != "A":
        rows = con.execute(
            "SELECT e.anchor, e.headword, e.text_html FROM index_entry e"
            " WHERE e.scope=? ORDER BY e.ord", (letter,)).fetchall()
        # Where each initial begins, for the jump bar: the list is in the print's
        # order, which is alphabetical without regard to case.
        initials = []
        for r in rows:
            c = r["headword"][:1].upper()
            c = c if c.isalpha() else "#"
            if not initials or initials[-1][0] != c:
                initials.append((c, r["anchor"]))
        return page(request, "appendix.html", app=app_, apps=appendices(con),
                    rows=rows, initials=initials if len(rows) > 150 else [])
    # The Chronology: years, the months under some of them, and the events.  A
    # \chrontext hangs off its year and a \chronsubtext off its month, which is
    # what month_label records; within a year the former all come first.
    years, bands = [], []
    for r in con.execute(
            "SELECT e.anchor, e.text_html, v.year_label, v.month_label, v.year_sort"
            " FROM chronology_event v JOIN index_entry e ON e.id=v.entry_id"
            " ORDER BY v.ord"):
        if not years or years[-1]["label"] != r["year_label"]:
            years.append({"label": r["year_label"], "id": _year_id(r["year_label"]),
                          "items": []})
            b = _band(r["year_label"], r["year_sort"])
            if not bands or bands[-1]["n"] != b:
                bands.append({"n": b, "name": CHRON_BANDS[b], "id": years[-1]["id"],
                              "events": 0})
        bands[-1]["events"] += 1
        items = years[-1]["items"]
        if r["month_label"] is None:
            items.append({"event": r})
        else:
            if not items or items[-1].get("month") != r["month_label"]:
                items.append({"month": r["month_label"], "events": []})
            items[-1]["events"].append(r)
    return page(request, "chronology.html", app=app_, apps=appendices(con),
                years=years, bands=bands)


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
    paras = con.execute(
        "SELECT p.*, d.precise_citers, d.thin FROM paragraph p"
        " LEFT JOIN para_density d ON d.paragraph_id=p.id"
        " WHERE p.paper_n=? AND p.section_n=? ORDER BY p.para_n",
        (paper, sec)).fetchall()
    citers = {}
    for row in con.execute(
            "SELECT c.paragraph_id, " + CHIP_COLS +
            " FROM para_citers c JOIN index_entry e ON e.id=c.entry_id"
            " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
            " JOIN paragraph p ON p.id=c.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision='para'" + CHIP_NEW +
            " ORDER BY e.ord", (paper, sec)):
        citers.setdefault(row["paragraph_id"], []).append(row)
    blanket = con.execute(
        "SELECT DISTINCT " + CHIP_COLS +
        " FROM para_citers c"
        " JOIN index_entry e ON e.id=c.entry_id"
        " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
        " JOIN paragraph p ON p.id=c.paragraph_id"
        " WHERE p.paper_n=? AND p.section_n=? AND c.precision IN ('sec','paper')" + CHIP_NEW +
        " ORDER BY e.ord LIMIT 60", (paper, sec)).fetchall()
    notes = {}
    for f in con.execute(
            "SELECT f.* FROM footnote f JOIN paragraph p ON p.id=f.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? ORDER BY f.ord", (paper, sec)):
        notes.setdefault(f["paragraph_id"], []).append(f)
    nxt = con.execute("SELECT n, title FROM section WHERE paper_n=? AND n>? ORDER BY n LIMIT 1",
                      (paper, sec)).fetchone()
    prv = con.execute("SELECT n FROM section WHERE paper_n=? AND n<? ORDER BY n DESC LIMIT 1",
                      (paper, sec)).fetchone()
    # Where listening goes on to: the next section, or from a paper's last
    # section the next paper's first -- the pager stays within the paper.
    onward = None
    if nxt:
        onward = {"href": f"/{paper}:{nxt['n']}", "label": f"{nxt['n']}. {nxt['title']}"}
    else:
        np_ = con.execute("SELECT s.paper_n, s.n, p.title FROM section s JOIN paper p"
                          " ON p.id=s.paper_id WHERE s.paper_n>? ORDER BY s.paper_n, s.n LIMIT 1",
                          (paper,)).fetchone()
        if np_:
            onward = {"href": f"/{np_['paper_n']}:{np_['n']}", "label": f"Paper {np_['paper_n']}. {np_['title']}"}
    return page(request, "section.html", paper=p, section=s, paras=paras,
                citers=citers, blanket=blanket, notes=notes,
                focus=focus, last=last, nxt=nxt, prv=prv, onward=onward,
                audio=section_audio(con, s["id"]),
                all_sections=con.execute(
                    "SELECT n, title_html FROM section WHERE paper_n=? ORDER BY n",
                    (paper,)).fetchall())
