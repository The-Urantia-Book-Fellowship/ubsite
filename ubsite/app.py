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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from markupsafe import Markup  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402

from ubsite import settings  # noqa: E402

DB = ROOT / "var" / "ub.db"
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "ubsite" / "static"), name="static")
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

# What a margin chip needs.  An appendix entry -- a Chronology event, a named
# being, person or place -- has no page yet and so no slug; it is shown by
# name with its appendix, and an event with its date, rather than linked.
CHIP_COLS = ("e.path_plain AS path, e.level, e.anchor, r.slug AS rslug,"
                 " a.title AS appendix, ev.year_label AS year")
CHIP_JOIN = (" LEFT JOIN appendix a ON a.letter=e.scope"
                 " LEFT JOIN chronology_event ev ON ev.entry_id=e.id")

RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$")
RE_TERM = re.compile(r'"([^"]*)"?|(\S+)')

# How many hits each list shows on the overview, and per page once a list is
# opened on its own with ?in=index or ?in=text.
OVERVIEW = {"index": 25, "text": 40}
PER_PAGE = 100


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
    terms = []
    for m in RE_TERM.finditer(q):
        text, star = m.group(1), ""
        if text is None:
            text = m.group(2)
            if text.endswith("*"):
                text, star = text.rstrip("*"), "*"
        if any(c.isalnum() for c in text):
            terms.append('"' + text.replace('"', '""') + '"' + star)
    return " ".join(terms) or None


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


# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    con = db()
    stats = dict(con.execute("SELECT key, value FROM stat").fetchall())
    # The A-Z only: index_entries in `stat` also counts the appendices and the
    # chronology, which /index does not show.
    stats["headwords"] = con.execute(
        "SELECT COUNT(*) FROM index_entry WHERE scope='az' AND level=1").fetchone()[0]
    stats["az_entries"] = con.execute(
        "SELECT COUNT(*) FROM index_entry WHERE scope='az'").fetchone()[0]
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
        heads = con.execute(
            "SELECT e.id, e.slug, e.headword,"
            "  (SELECT n_descendants FROM entry_stats WHERE entry_id=e.id) AS kids"
            " FROM index_entry e"
            " WHERE e.scope='az' AND e.level=1"
            "   AND (LOWER(RTRIM(e.headword,'.')) = LOWER(?)"
            "        OR LOWER(e.headword) LIKE LOWER(?) || '%')"
            " ORDER BY LOWER(RTRIM(e.headword,'.')) = LOWER(?) DESC, e.ord"
            " LIMIT 12",
            (q, q, q)).fetchall()
    if fq and scope != "text":
        # The headwords listed above are left out of this list, by entry id.
        # Not by slug: a subentry links through its headword's slug, so that
        # would drop every subentry of a headword already shown.
        shown = [h["id"] for h in heads]
        where = (" FROM index_entry_fts f JOIN index_entry e ON e.id=f.rowid"
                 " WHERE index_entry_fts MATCH ? AND e.scope='az'"
                 + (f" AND e.id NOT IN ({','.join('?' * len(shown))})" if shown else ""))
        n = con.execute("SELECT COUNT(*)" + where, (fq, *shown)).fetchone()[0]
        size, off = _window(scope == "index", "index", number, n)
        idx = _hits(n, off, con.execute(
            "SELECT e.path_plain AS path, e.level, e.anchor,"
            "  (SELECT slug FROM index_entry WHERE id=e.root_id) AS rslug"
            + where + " ORDER BY rank LIMIT ? OFFSET ?",
            (fq, *shown, size, off)).fetchall())
    if fq and scope != "index":
        n = con.execute("SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?",
                        (fq,)).fetchone()[0]
        size, off = _window(scope == "text", "text", number, n)
        txt = _hits(n, off, con.execute(
            "SELECT p.ref, snippet(paragraph_fts, 0, '<mark>', '</mark>', '…', 24) AS s"
            " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid"
            " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT ? OFFSET ?",
            (fq, size, off)).fetchall())
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
    return page(request, "index_front.html", letters=letters)


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
    xrefs = con.execute(
        "SELECT x.kind, x.target, t.slug FROM xref x"
        " LEFT JOIN index_entry t ON t.id=x.head_entry_id"
        " WHERE x.entry_id IN (SELECT id FROM index_entry WHERE root_id=?)"
        " ORDER BY x.kind, x.ord", (root["id"],)).fetchall()
    near = con.execute(
        "SELECT o.slug, o.headword, c.shared,"
        "  (SELECT n_descendants FROM entry_stats WHERE entry_id=o.id) AS kids"
        " FROM cocitation c"
        " JOIN index_entry o ON o.id = CASE WHEN c.a_root_id=? THEN c.b_root_id"
        "                                   ELSE c.a_root_id END"
        " WHERE c.a_root_id=? OR c.b_root_id=? ORDER BY c.shared DESC LIMIT 8",
        (root["id"], root["id"], root["id"])).fetchall()
    return page(request, "concept.html", root=root, tree=tree, xrefs=xrefs, near=near)


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
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision='para'"
            " ORDER BY e.ord", (paper, sec)):
        citers.setdefault(row["paragraph_id"], []).append(row)
    blanket = con.execute(
        "SELECT DISTINCT " + CHIP_COLS +
        " FROM para_citers c"
        " JOIN index_entry e ON e.id=c.entry_id"
        " JOIN index_entry r ON r.id=e.root_id" + CHIP_JOIN +
        " JOIN paragraph p ON p.id=c.paragraph_id"
        " WHERE p.paper_n=? AND p.section_n=? AND c.precision IN ('sec','paper')"
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
