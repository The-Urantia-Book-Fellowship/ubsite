"""The annotated reader.

Server-rendered HTML.  A citable corpus must produce a correct document at a URL
with JavaScript disabled -- for archive.org, for a Kindle browser, for curl --
so JS only enhances.

There is one mode: the study apparatus is always on.  The individual elements
-- red letter, the margin index, paragraph numbers, the 1955 variants -- become
switches under Settings, rather than one coarse lever that hides them together.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "index"))

import cite  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

DB = ROOT / "var" / "ub.db"
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "ubsite" / "static"), name="static")
T = Jinja2Templates(directory=str(ROOT / "ubsite" / "templates"))

RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$")


def db() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


# There is one mode, and it is the study apparatus.  What used to be Reading
# mode becomes a set of switches under Settings later -- red letter on or off,
# apparatus in the margin or below, paragraph numbers shown or not -- rather
# than one coarse lever that hides everything at once.
def mode_of(request: Request) -> str:
    return "study"


def page(request, template, **ctx):
    ctx.setdefault("mode", mode_of(request))
    return T.TemplateResponse(request, template, ctx)


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
def search(request: Request, q: str = ""):
    con = db()
    jump = cite.parse(q.strip()) if q.strip() else None
    if jump is not None:
        tg = list(jump.expand())
        if tg:
            p, s, n = tg[0]
            return RedirectResponse(
                f"/{p}:{s}" + (f".{n}" if n is not None else ""), status_code=303)
    idx, txt, heads = [], [], []
    if q:
        # An exact headword match must win.  Full-text rank cannot deliver that
        # -- bm25 scores term statistics and has no notion that the query names
        # an entry -- so searching "Jesus" put Joshua, parables and Amos above
        # it and the 796-entry article never appeared. Headwords are therefore
        # resolved separately: exact first, then prefix, then everything else.
        heads = con.execute(
            "SELECT e.slug, e.headword,"
            "  (SELECT n_descendants FROM entry_stats WHERE entry_id=e.id) AS kids"
            " FROM index_entry e"
            " WHERE e.scope='az' AND e.level=1"
            "   AND (LOWER(RTRIM(e.headword,'.')) = LOWER(?)"
            "        OR LOWER(e.headword) LIKE LOWER(?) || '%')"
            " ORDER BY LOWER(RTRIM(e.headword,'.')) = LOWER(?) DESC, e.ord"
            " LIMIT 12",
            (q, q, q)).fetchall()
        seen = {h["slug"] for h in heads}
        idx = [r for r in con.execute(
            "SELECT e.id, e.slug, e.path_plain AS path, e.level, e.headword,"
            "  (SELECT n_descendants FROM entry_stats WHERE entry_id=e.root_id) AS kids"
            " FROM index_entry_fts f JOIN index_entry e ON e.id=f.rowid"
            " WHERE index_entry_fts MATCH ? AND e.scope='az'"
            " ORDER BY rank LIMIT 60", (q,)).fetchall()
            if r["slug"] not in seen][:25]
        txt = con.execute(
            "SELECT p.ref, snippet(paragraph_fts, 0, '<mark>', '</mark>', '…', 24) AS s"
            " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid"
            " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT 40", (q,)).fetchall()
    n_idx = con.execute("SELECT COUNT(*) FROM index_entry_fts WHERE index_entry_fts MATCH ?",
                        (q,)).fetchone()[0] if q else 0
    n_txt = con.execute("SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?",
                        (q,)).fetchone()[0] if q else 0
    return page(request, "search.html", q=q, idx=idx, txt=txt, heads=heads,
                n_idx=n_idx, n_txt=n_txt, diagnose=cite.diagnose(q) if q else None)


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
    return page(request, "index_letter.html", letter=letter.upper(), rows=rows)


@app.get("/i/{slug}", response_class=HTMLResponse)
def concept(request: Request, slug: str):
    con = db()
    root = con.execute("SELECT * FROM index_entry WHERE slug=?", (slug,)).fetchone()
    if root is None:
        return HTMLResponse("not found", 404)
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
        return HTMLResponse("no such paper", 404)
    return RedirectResponse(f"/{paper}:{first}", status_code=307)


@app.get("/{ref}", response_class=HTMLResponse)
def read(request: Request, ref: str):
    m = RE_REF.match(ref)
    if not m:
        return HTMLResponse("not a citation", 404)
    paper, sec = int(m.group(1)), int(m.group(2))
    focus = int(m.group(3)) if m.group(3) else None
    last = int(m.group(4)) if m.group(4) else focus
    con = db()
    p = con.execute("SELECT * FROM paper WHERE n=?", (paper,)).fetchone()
    s = con.execute("SELECT * FROM section WHERE paper_n=? AND n=?",
                    (paper, sec)).fetchone()
    if p is None or s is None:
        return HTMLResponse("no such section", 404)
    paras = con.execute(
        "SELECT p.*, d.precise_citers, d.thin FROM paragraph p"
        " LEFT JOIN para_density d ON d.paragraph_id=p.id"
        " WHERE p.paper_n=? AND p.section_n=? ORDER BY p.para_n",
        (paper, sec)).fetchall()
    citers = {}
    for row in con.execute(
            "SELECT c.paragraph_id, e.slug, e.path_plain AS path, e.root_id, r.slug AS rslug"
            " FROM para_citers c JOIN index_entry e ON e.id=c.entry_id"
            " JOIN index_entry r ON r.id=e.root_id"
            " JOIN paragraph p ON p.id=c.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? AND c.precision='para'"
            " ORDER BY e.ord", (paper, sec)):
        citers.setdefault(row["paragraph_id"], []).append(row)
    blanket = con.execute(
        "SELECT DISTINCT e.path_plain AS path, r.slug AS rslug FROM para_citers c"
        " JOIN index_entry e ON e.id=c.entry_id"
        " JOIN index_entry r ON r.id=e.root_id JOIN paragraph p ON p.id=c.paragraph_id"
        " WHERE p.paper_n=? AND p.section_n=? AND c.precision IN ('sec','paper')"
        " ORDER BY e.ord LIMIT 60", (paper, sec)).fetchall()
    notes = {}
    for f in con.execute(
            "SELECT f.* FROM footnote f JOIN paragraph p ON p.id=f.paragraph_id"
            " WHERE p.paper_n=? AND p.section_n=? ORDER BY f.ord", (paper, sec)):
        notes.setdefault(f["paragraph_id"], []).append(f)
    nxt = con.execute("SELECT n FROM section WHERE paper_n=? AND n>? ORDER BY n LIMIT 1",
                      (paper, sec)).fetchone()
    prv = con.execute("SELECT n FROM section WHERE paper_n=? AND n<? ORDER BY n DESC LIMIT 1",
                      (paper, sec)).fetchone()
    return page(request, "section.html", paper=p, section=s, paras=paras,
                citers=citers, blanket=blanket, notes=notes,
                focus=focus, last=last, nxt=nxt, prv=prv,
                all_sections=con.execute(
                    "SELECT n, title FROM section WHERE paper_n=? ORDER BY n",
                    (paper,)).fetchall())
