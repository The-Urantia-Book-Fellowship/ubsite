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

import datetime
import functools
import gzip
import hashlib
import html
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

from ubsite import api, l10n, queries, settings, stats, visits  # noqa: E402

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
# Every word around the book in English and Russian (ubsite/l10n.py, ru.toml).
l10n.install(T.env)


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


# The scripts' words (ubsite/l10n.js): the entries of ru.toml the scripts name,
# and the voices' names, which a page's player draws (listen.js), put in its
# place of __CATALOG__.  Made again when any of them changes, as the dev
# server runs; named by a hash of what it sends, so a build that changes
# nothing moves nothing (CLAUDE.md trap 29).
L10N_SCRIPTS = ("ub.js", "listen.js", "offline.js", "sw.js", "offline-core.js")
L10N_JS = ROOT / "ubsite" / "l10n.js"


@functools.lru_cache(maxsize=4)
def _l10n_js(stamp: tuple) -> tuple[bytes, bytes, str]:
    keys = l10n.script_keys([(STATIC / n).read_text() for n in L10N_SCRIPTS])
    keys |= {v[k] for v in voices() for k in ("label", "credit") if v[k]}
    src = L10N_JS.read_text()
    if src.count("var L10N = __CATALOG__;") != 1:
        raise RuntimeError("ubsite/l10n.js has lost its `var L10N = __CATALOG__;`")
    data = src.replace("var L10N = __CATALOG__;", f"var L10N = {l10n.script_catalog(keys)};").encode()
    return data, gzip.compress(data, 9, mtime=0), hashlib.sha256(data).hexdigest()[:10]


def l10n_js() -> tuple[bytes, bytes, str]:
    """/l10n.js: (its bytes, gzipped, the hash its address carries)."""
    files = [L10N_JS, l10n.CATALOG, DB, *(STATIC / n for n in L10N_SCRIPTS)]
    return _l10n_js((l10n.BILINGUAL, *(f.stat().st_mtime_ns if f.exists() else 0 for f in files)))


def l10n_url() -> str:
    return f"/l10n.js?v={l10n_js()[2]}"


T.env.globals["l10n_url"] = l10n_url


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


def reading_time(words: int) -> l10n.L:
    """How long a reading path takes, at 230 words a minute: "about 12
    minutes", and in hours from an hour and a half."""
    minutes = max(1, round(words / 230))
    if minutes < 90:
        return l10n.tr("about {n} minutes", n=minutes)
    return l10n.tr("about {n} hours", n=round(minutes / 60))


T.env.globals["reading_time"] = reading_time

# Search reaches an Appendix B-F row only when no A-Z headword has its name: the
# other 1,332 would come up twice, once as the headword and once as the row.
APP_OWN = (" OR (e.scope IN ('B','C','D','E','F')"
           " AND e.id NOT IN (SELECT entry_id FROM appendix_head))")

RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$")
RE_TERM = re.compile(r'"([^"]*)"?|(\S+)')

# How many hits each list shows on the overview, and per page once a list is
# opened on its own with ?in=index, ?in=text, ?in=notes, ?in=study, or a
# translation's key, ?in=ud (build/translation.py SCOPES).
OVERVIEW = {"index": 25, "text": 40, "notes": 10, "study": 10, "tr": 40}
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


def mark_terms(texts: list[str], q: str, at: list | None = None) -> list[Markup]:
    """Each text with what the search matched in <mark>, as snippet() marks a paragraph.

    An index hit is shown by its chip -- `path_plain`, or a Chronology event's
    dated label -- which is not a column FTS5 indexes, so snippet() cannot reach
    it.  Rather than copy the tokenizer's rules (Unicode 6.1's idea of a letter,
    diacritics folded, a prefix, a phrase), the texts go into a throwaway table
    with the same tokenizer and FTS5's own highlight() marks them.  The terms are
    OR'd: a hit can match one of them only in a citation, and its chip should
    still show the others.  The marks go in as control characters and become
    tags only after the text is escaped, so "6. & 7." stays text.  `at`, one
    list to a text, says where its superscripts stand (sups()), so that a chip
    shows "1st" as it stands beside the text.
    """
    at = at or [()] * len(texts)
    terms = _terms(q)
    if not terms or not texts:
        return [_snip(t, t, a) for t, a in zip(texts, at)]
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE VIRTUAL TABLE t USING fts5(x, tokenize='{TOKENIZE}')")
    con.executemany("INSERT INTO t(rowid, x) VALUES (?, ?)", enumerate(texts))
    anyq = " OR ".join(_phrase(t, star) for t, star in terms)
    marked = dict(con.execute(
        "SELECT rowid, highlight(t, 0, char(2), char(3)) FROM t WHERE t MATCH ?", (anyq,)))
    con.close()
    return [_snip(marked.get(i, t), t, at[i]) for i, t in enumerate(texts)]


RE_SUP = re.compile(r"(</?sup>)")
RE_TAG = re.compile(r"<[^>]+>")


def sups(h: str | None) -> list[tuple[int, int]]:
    """Where the superscripts of an HTML fragment stand in its text, as
    (start, end): in the fragment's tags stripped and its entities read, which
    the round-trip gates hold to the stored text (render.strip_tags)."""
    out: list[tuple[int, int]] = []
    if not h or "<sup>" not in h:
        return out
    n = start = 0
    for piece in RE_SUP.split(h):
        if piece == "<sup>":
            start = n
        elif piece == "</sup>":
            out.append((start, n))
        else:
            n += len(html.unescape(RE_TAG.sub("", piece)))
    return out


def _html(s: str, base: int = 0, at=()) -> Markup:
    """`s`, a stretch of a text from `base` on, as HTML: escaped, FTS5's marks
    \\x02 and \\x03 as <mark> tags and a snippet's cut \\x04 as an ellipsis, and
    the text's superscripts (`at`, as sups() gives them) set as the page sets
    them, 611,121<sup>st</sup>.  FTS5 marks whole tokens and a superscript stands
    inside one, so each <sup> falls within a <mark> or outside them all."""
    n = sum(c not in "\x02\x03\x04" for c in s)
    opens = {max(a - base, 0) for a, b in at if a < base + n and b > base}
    closes = {min(b - base, n) for a, b in at if a < base + n and b > base}
    if not opens:
        return Markup(str(escape(s)).replace("\x02", "<mark>").replace("\x03", "</mark>")
                      .replace("\x04", "…"))
    out, i = [], 0
    for c in s:
        if c == "\x02":
            out.append("<mark>")
        elif c == "\x03":
            out.append("</mark>")
        elif c == "\x04":
            out.append("…")
        else:
            if i in opens:
                out.append("<sup>")
            out.append(str(escape(c)))
            i += 1
            if i in closes:
                out.append("</sup>")
    return Markup("".join(out))


def _snip(s: str, text: str = "", at=()) -> Markup:
    """What FTS5's highlight() or snippet() made of `text`, as HTML (_html).  A
    snippet is the text verbatim between its cuts, so where it stands, which
    places the superscripts, is found by looking."""
    base = 0
    if at:
        core = s.replace("\x02", "").replace("\x03", "").strip("\x04")
        base = text.find(core)
        if base < 0:
            raise ValueError(f"a search hit is not in its text: {core[:60]!r}")
    return _html(s, base, at)


def fold(s: str) -> str:
    """ё read as е, as the translations' search reads their text
    (build/schema/004_fts.sql): one letter for one."""
    return s.replace("ё", "е").replace("Ё", "Е")


def _unfold(s: str, text: str) -> str:
    """What snippet() made of a translation's text read through its view, ё as
    е, in the translation's own letters: the view folds one letter for one, so
    the snippet's stretch stands at the same place in `text`, and FTS5's marks
    \\x02 \\x03 \\x04 stay where they are."""
    if "ё" not in text and "Ё" not in text:
        return s
    core = s.replace("\x02", "").replace("\x03", "").strip("\x04")
    i = fold(text).find(core)
    if i < 0:
        raise ValueError(f"a search hit is not in its text: {core[:60]!r}")
    out = []
    for c in s:
        if c in "\x02\x03\x04":
            out.append(c)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _reasons_at(a_text, a_html, b_text, b_html) -> list[tuple[int, int]]:
    """Where the superscripts of a 1955 note's reasons stand in footnote_fts's
    `reasons`: the committee's two joined as derive.fts joins them,
    TRIM(a || ' ' || b)."""
    joined = f"{a_text or ''} {b_text or ''}"
    lead = len(joined) - len(joined.lstrip(" "))
    return [(x - lead, y - lead) for x, y in sups(f"{a_html or ''} {b_html or ''}")]


RE_WORD = re.compile(r"\S+")
RE_GLUE = re.compile(r"(.*?)(\S*)\Z", re.S)


def _around(text: str, at: int, before: int = 8, after: int = 6,
            sup=()) -> tuple[Markup, Markup, Markup, Markup]:
    """Today's words on either side of a 1955 note's ring, `at` in `text`.

    The ring stands after the words that changed, so what shows is what
    replaced the 1955 reading, and enough on each side to read it by: so many
    words, cut where a word ends, with an ellipsis only where something was cut.
    As (lead, word, glue, rest): `word` and `glue` touch the ring on either
    side -- "forgo" and "", "mussels" and "," -- and the page keeps them on
    one line with it, which the browser would otherwise break around it.
    Each as HTML, with the text's superscripts where `sup` (sups()) puts them.
    """
    head, tail = text[:at], text[at:]
    hw, tw = list(RE_WORD.finditer(head)), list(RE_WORD.finditer(tail))
    a = hw[-before].start() if len(hw) > before else 0
    b = at + tw[after - 1].end() if len(tw) > after else len(text)
    w = at - len(RE_GLUE.match(text[a:at]).group(2))
    g = at + len(re.match(r"\S*", text[at:b]).group(0))
    piece = lambda i, j: _html(text[i:j], i, sup)
    return (Markup("…" if a else "") + piece(a, w), piece(w, at), piece(at, g),
            piece(g, b) + Markup("…" if b < len(text) else ""))


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


def missing(request, msg):
    """A 404 that is still a page of the site, with its header and search box:
    `msg` a key of ru.toml, or its words made (l10n.tr())."""
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
        # deploy of this code over an older ub.db.  /healthz then omits the
        # commits; turning into a 500 would be the worse failure.
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


def _runs(ns: list[int]) -> str:
    """[0, 1, 2, 3, 5] -> "0–3, 5"."""
    out, a = [], None
    for i, n in enumerate(ns):
        if a is None:
            a = n
        if i + 1 == len(ns) or ns[i + 1] != n + 1:
            out.append(f"{a}–{n}" if n > a else f"{a}")
            a = None
    return ", ".join(out)


def _cover(whole: list[int], part: list[int]) -> l10n.L:
    """What a translation covers, from its papers: "the whole book", or
    "Papers 0–40, and 41, 43, 195 and 196 in part"."""
    if not part and len(whole) == 197:
        return l10n.tr("the whole book")
    some = l10n.tr("{a} and {b}", a=", ".join(map(str, part[:-1])), b=part[-1]) if len(part) > 1 \
        else l10n.L.same(part[0]) if part else None
    if whole and some:
        return l10n.tr("Papers {r}, and {p} in part", r=_runs(whole), p=some)
    return l10n.tr("Papers {r}", r=_runs(whole)) if whole else l10n.tr("Papers {p} in part", p=some)


@functools.lru_cache(maxsize=4)
def _translations(mtime_ns: int, bilingual: bool) -> list[dict]:
    try:
        con = db()
        rows = con.execute("SELECT * FROM translation ORDER BY ord").fetchall()
        n = dict(con.execute("SELECT paper_n, COUNT(*) FROM paragraph GROUP BY paper_n").fetchall())
        out = []
        for r in rows:
            have = dict(con.execute(
                "SELECT p.paper_n, COUNT(*) FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                " WHERE t.translation = ? GROUP BY p.paper_n", (r["key"],)).fetchall())
            whole = [k for k in sorted(have) if have[k] == n[k]]
            part = [k for k in sorted(have) if have[k] < n[k]]
            out.append({"key": r["key"], "lang": r["lang"], "title": r["title"],
                        "by": l10n.L({"en": escape(r["by_en"]), "ru": escape(r["by_ru"])}),
                        "label": escape(r["label"]),
                        # Its language, as Settings names it: "Russian".
                        "language": l10n.tr(LANGUAGES[r["lang"]]),
                        # What its owner asks a reader be told, "Copyright © …", or None.
                        "credit": r["credit_en"] and l10n.L({"en": escape(r["credit_en"]),
                                                              "ru": escape(r["credit_ru"])}),
                        "cover": _cover(whole, part)})
        return out
    except sqlite3.Error:
        return []                                  # a database from before 010_translation.sql


def translations() -> list[dict]:
    """The translations this database carries, in the order Settings lists them
    (data/translations.toml): each with its words in both languages, an l10n.L,
    and what it covers, counted from what it has."""
    return _translations(db_version(), l10n.BILINGUAL)


T.env.globals["translations"] = translations
# A translation's language, as Settings names it.
LANGUAGES = {"ru": "Russian"}
T.env.globals["LANGUAGES"] = LANGUAGES


def translations_json() -> Markup:
    """What a fold needs of each translation (ub.js): its key, title and
    language, its short name, and who made it and its language's name in each
    language, as {en, ru}, which l10n.js's T() takes as words made (the player
    names its voices so, listen.js); and the version of its contents,
    which the left rail asks for under it (/rail/<key>).  HTML, escaped.  In
    the dialog, so in the shell."""
    out = [{"key": x["key"], "lang": x["lang"], "title": str(escape(x["title"])),
            "label": str(x["label"]), "by": dict(x["by"].by), "language": dict(x["language"].by),
            "toc": (toc_of(x["key"]) or {}).get("v")}
           for x in translations()]
    return Markup(json.dumps(out, ensure_ascii=False).replace("</", "<\\/"))


T.env.globals["translations_json"] = translations_json


@functools.lru_cache(maxsize=256)
def _translated(mtime_ns: int, bilingual: bool, paper: int, sec: int) -> dict:
    try:
        got = queries.translated(db(), paper, sec)
    except sqlite3.Error:
        return {"has": {}, "html": "", "v": ""}       # a database from before 010_translation.sql
    html = T.env.get_template("tr_section.html").render(heads=got["heads"], rows=got["rows"])
    # Its version is a hash of what it sends, the words of its cards in each
    # language with it: a build that changes nothing moves nothing (trap 29).
    return {"has": got["has"], "html": html,
            "v": hashlib.sha256(html.encode()).hexdigest()[:12] if got["rows"] else ""}


def translated(paper: int, sec: int) -> dict:
    """A section's translations, kept per database: the section page reads
    its version and its folds' data-has, /tr/ its fragment, drawn from
    queries.translated() by templates/tr_section.html."""
    return _translated(db_version(), l10n.BILINGUAL, paper, sec)


# The fragment's frame: tr_section.html with nothing in it.  Between its ends
# stand every translation's headings, then every translation's paragraphs, each
# in Settings' order, as queries.translated() orders them.
TR_FRAME = ('<div class="trs">\n', "</div>")


def tr_pieces(paper: int, sec: int) -> dict[str, tuple[str, str]]:
    """Each translation's share of /tr/<paper>:<section>, {key: (its headings,
    its paragraphs and their notes)}, in Settings' order, for the offline copy,
    which keeps each translation apart (offline/pages.py): the frame around
    them all, joined in order, is the fragment."""
    got = queries.translated(db(), paper, sec)
    tpl = T.env.get_template("tr_section.html")
    if tpl.render(heads=[], rows=[]) != "".join(TR_FRAME):
        raise ValueError("tr_section.html's frame is not TR_FRAME")

    def inner(**what) -> str:
        return tpl.render(**what)[len(TR_FRAME[0]):-len(TR_FRAME[1])]
    return {k: (inner(heads=[h for h in got["heads"] if h["k"] == k], rows=[]),
                inner(heads=[], rows=[r for r in got["rows"] if r["k"] == k]))
            for k in dict.fromkeys(r["k"] for r in got["rows"])}


@app.get("/tr/{ref}", include_in_schema=False)
def translations_of(ref: str, v: str = ""):
    """A section's translations, for the folds under its paragraphs (ub.js),
    which fetch it the first time one is opened: every translation the section
    has, not only those a reader ticked, so that no setting reaches the server.
    Asked for under its version (the article's data-trv), the answer is kept
    for good, as /rail/N's is."""
    m = re.fullmatch(r"(\d+):(\d+)", ref)
    got = translated(int(m[1]), int(m[2])) if m else None
    if not got or not got["v"]:
        return Response("No translation has this section.\n", status_code=404, media_type="text/plain")
    cache = "public, max-age=31536000, immutable" if v == got["v"] else "no-cache"
    return HTMLResponse(got["html"], headers={"Cache-Control": cache})


def db_version() -> int:
    """Which database this is: its mtime, which every cache here keys on."""
    try:
        return DB.stat().st_mtime_ns
    except OSError:
        return 0


ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
# What the left rail says itself (templates/_rail.html), which its version holds:
# the interface's words.  Not its contents' own words, "0. Introduction",
# "Part I.", "9 and 10.", which are in the contents' language, English for the
# book's and the translation's own in a translation's (/rail/<key>), whatever
# the interface's (Tigran, 2026-10-27): until then they followed the
# interface, and a reader of it in Russian read «0. Введение» and «Часть I.»
# among the book's English titles.
RAIL_WORDS = ("Contents", "The book", "Show the contents in a translation")
# The contents' own words, keyed as l10n's catalog keys them.
TOC_WORDS = {"intro": "0. Introduction", "part": "Part {r}.", "and": "{a} and {b}"}


@functools.lru_cache(maxsize=4)
def _book(mtime_ns: int, bilingual: bool) -> dict:
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
    # every paper's chunk with each deploy, the book unchanged.  With the words
    # the rail says itself, in each language (ubsite/l10n.py), so that a fragment
    # kept from before they changed is not drawn again.
    said = [l10n.BILINGUAL] + [l10n.tr(k).by for k in RAIL_WORDS]
    v = hashlib.sha256(json.dumps([papers, sections, said], sort_keys=True).encode()).hexdigest()[:12]
    return {"foreword": [p for p in papers if p["part_n"] is None],
            "parts": parts, "sections": sections, "v": v}


def book() -> dict:
    """The whole book as the left rail draws it: the Foreword, the four parts
    with their papers, and every paper's sections.  Cached on the database's
    mtime, as sources() is."""
    return _book(db_version(), l10n.BILINGUAL)


T.env.globals["book"] = book
T.env.globals["settings_groups"] = settings.groups
T.env.globals["settings_defaults"] = settings.defaults()
T.env.globals["site_defaults"] = settings.site_defaults()
T.env.globals["settings_spared"] = settings.SPARED
T.env.globals["bilingual"] = lambda: l10n.BILINGUAL


# The same build is live at two addresses, and an app installed from each looked
# the same, as did a tab of each (Tigran, 2026-10-15).  So each says which it is:
# its manifest's full name names the site, and ubsite.ddns.net's icons have a
# burgundy book (tools/make_icons.py VARIANTS): ubsite.sigmaai.au is the main
# site, and has the blue (Tigran, 2026-10-24; the other way round until then).
# Only Chrome's install dialog and chrome://webapks show that name: Android
# labels the app with short_name, under its icon and in Settings > Apps alike
# (Chromium's WebAPK template), and it stays "Urantia Book" on both, since it
# has no room for more.  Any other host, this machine's included, looks like the
# main site, without its name.  The server answers the manifest and the touch
# icon by host, and the offline copy, made once for both, holds neither
# (offline-core.js HOSTED).  The tab's icon is chosen in the page, from its
# address, by base.html's head script, which is handed this table; the header's
# mark and the home page's logo are the same on both.
SITES = {"ubsite.ddns.net": "-burgundy", "ubsite.sigmaai.au": ""}
T.env.globals["sites"] = SITES


def _site(request: Request) -> tuple[str, str]:
    """(the site's name, its icons' suffix) for the host the request was sent to."""
    host = request.url.hostname or ""
    return (host, SITES[host]) if host in SITES else ("", "")


# Asked for by fixed name at the root, with or without a <link>: browsers try
# /favicon.ico, iOS /apple-touch-icon.png.  Both are drawn from favicon.svg by
# tools/make_icons.py.  Without these they fell through to the {ref} route and
# got the not-found page, as HTML.
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(ROOT / "ubsite" / "static" / "favicon.ico", media_type="image/x-icon")


@app.get("/apple-touch-icon.png", include_in_schema=False)
def touch_icon(request: Request):
    return FileResponse(ROOT / "ubsite" / "static" / f"apple-touch-icon{_site(request)[1]}.png")


# Asked for by a crawler before it crawls; every other crawler may read it all.
# Reflectionbot gathers pages to train Reflection AI's models (reflection.ai/bot)
# and sends no readers: from 2026-10-09 it took a thousand pages a day from pi5,
# asking here 32 times and getting a 404, which says take everything.  Refused
# here alone on 2026-10-15 (Tigran); should it crawl on, nginx refuses it next.
ROBOTS = "User-agent: Reflectionbot\nDisallow: /\n"


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return Response(ROBOTS, media_type="text/plain")


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


@app.get("/speech/{key}/{ref}", include_in_schema=False)
def speech_tr(key: str, ref: str):
    """A section of translation `key` as the browser's voice reads it
    (build/speech.py derive_tr), in the shape /speech/ sends the English's:
    its heading first, where it titles the section, then each paragraph it
    has.  404 for a section it has none of."""
    m = re.fullmatch(r"(\d+):(\d+)", ref)
    try:
        rows = db().execute(
            "SELECT p.ref, x.text FROM tr_speech x JOIN section s ON s.id=x.section_id"
            " LEFT JOIN paragraph p ON p.id=x.paragraph_id"
            " WHERE x.translation=? AND s.paper_n=? AND s.n=? ORDER BY p.para_n IS NOT NULL, p.para_n",
            (key, int(m[1]), int(m[2]))).fetchall() if m else []
    except sqlite3.Error:
        rows = []                                    # a database from before tr_speech
    if not any(r["ref"] for r in rows):
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
    v = {"core": asset("offline-core.js"), "l10n": l10n_url(),
         **{k.split(".")[1]: f"/offline/{k}?v={engine(k)[1]}" for k in ENGINE}}
    src = (STATIC / "sw.js").read_text()
    if src.count("var V = __VERSIONS__;") != 1:
        raise RuntimeError("static/sw.js has lost its `var V = __VERSIONS__;`")
    body = src.replace("var V = __VERSIONS__;", f"var V = {json.dumps(v)};")
    return _etagged(request, body.encode(), "text/javascript")


@app.get("/l10n.js", include_in_schema=False)
def l10n_script(request: Request, v: str = ""):
    """The scripts' words (l10n_js()), kept for good under its hash.  Gzipped
    here: nginx compresses only under /static/."""
    data, gz, h = l10n_js()
    headers = {"Cache-Control": "public, max-age=31536000, immutable" if v == h else "no-cache",
               "Vary": "Accept-Encoding"}
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(gz, media_type="text/javascript", headers={**headers, "Content-Encoding": "gzip"})
    return Response(data, media_type="text/javascript", headers=headers)


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
def web_manifest(request: Request):
    """What lets a reader install the site as an app: a Home Screen icon, and on
    an iPhone the only way an offline copy is kept for good (Safari deletes a
    site's stored data after seven days of use without a visit).  Each host's
    names it and its icons (SITES).  A variant's icons are its PNGs alone: the
    SVG is the blue book, and a browser may take it over a PNG."""
    host, v = _site(request)
    icons = [{"src": f"/static/icon-192{v}.png", "sizes": "192x192", "type": "image/png"},
             {"src": f"/static/icon-512{v}.png", "sizes": "512x512", "type": "image/png"}]
    if not v:
        icons.append({"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"})
    return JSONResponse({
        "name": f"The Urantia Book · {host}" if host else "The Urantia Book", "short_name": "Urantia Book",
        "description": "The Uversa Press text read together with its index.",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#f8f5f0", "theme_color": "#f8f5f0",  # --paper
        "icons": icons,
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
    """Index hits, text hits, the study notes, each translation and the 1955
    readings, kept apart.

    With no `in`, an overview: the first few of each list.  `in=index`,
    `in=text`, `in=study`, `in=notes` or a translation's key, `in=ud`, opens
    that one list whole, a hundred to a page.  Either way the number beside a
    heading counts exactly what its list holds, so "Show all" always delivers
    the number it promised.  Every list is sent, and CSS shows those Settings
    asks for, since no setting reaches the server.
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
    trs = translations()
    scope = scope if scope in ("index", "text", "notes", "study", *(x["key"] for x in trs)) else ""
    number = int(page_no) if page_no.isdigit() and int(page_no) > 0 else 1
    fq = fts_query(q)
    heads, idx, txt, old, stu, found_tr = [], None, None, None, None, []
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
            "SELECT e.id, e.slug, e.headword, e.headword_html, e.scope, e.anchor, a.title AS appendix,"
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
            "SELECT e.path_plain AS path, e.path_html, e.level, e.anchor, e.scope,"
            "  (SELECT slug FROM index_entry WHERE id=e.root_id) AS rslug,"
            "  (SELECT title FROM appendix WHERE letter=e.scope) AS appendix,"
            "  (SELECT label FROM chronology_event WHERE entry_id=e.id) AS event,"
            "  (SELECT label_html FROM chronology_event WHERE entry_id=e.id) AS event_html"
            + where + " ORDER BY rank LIMIT ? OFFSET ?",
            (fq, *shown, size, off)).fetchall()
        # What each hit shows, with the reader's words marked as in the text hits,
        # and its superscripts as beside the text.
        marked = mark_terms([r["event"] or r["path"] for r in rows], q,
                            [sups(r["event_html"] or r["path_html"]) for r in rows])
        idx = _hits(n, off, [dict(r, marked=m) for r, m in zip(rows, marked)])
    if fq and scope in ("", "text"):
        n = con.execute("SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?",
                        (fq,)).fetchone()[0]
        size, off = _window(scope == "text", "text", number, n)
        # Each with its superscripts, as the page sets them: "611,121st".
        txt = _hits(n, off, [{"ref": r["ref"], "s": _snip(r["s"], r["text"], sups(r["html"]))}
                             for r in con.execute(
            "SELECT p.ref, p.text, p.html,"
            "  snippet(paragraph_fts, 0, char(2), char(3), char(4), 24) AS s"
            " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid"
            " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT ? OFFSET ?",
            (fq, size, off)).fetchall()])
    if fq and scope in ("", "study"):
        # The study notes' words (Tigran, 2026-10-26), each line as the List of
        # study notes has it.  Always looked up, and shown only while Settings
        # shows the notes (ub.css .bystudy), for settings never reach the server.
        where = (" FROM footnote_fts x JOIN footnote f ON f.id=x.rowid"
                 " JOIN paragraph p ON p.id=f.paragraph_id"
                 " WHERE footnote_fts MATCH ? AND f.kind='study'")
        n = con.execute("SELECT COUNT(*)" + where, (fq,)).fetchone()[0]
        size, off = _window(scope == "study", "study", number, n)
        hits = con.execute(
            "SELECT f.id, snippet(footnote_fts, 0, char(2), char(3), char(4), 24) AS s,"
            "  x.reading AS text, f.html" + where
            + " ORDER BY p.ord, f.anchor, f.ord LIMIT ? OFFSET ?", (fq, size, off)).fetchall()
        found = {n["id"]: n for n in queries.study(
            con, f"f.id IN ({','.join('?' * len(hits))})", tuple(h["id"] for h in hits))}
        stu = _hits(n, off, [_study_hit(found[h["id"]], _snip(h["s"], h["text"], sups(h["html"])))
                             for h in hits])
    # Each translation beside the text (Tigran, 2026-10-26), its paragraphs and
    # its translator's notes, ё as е.  Always looked up, every one of them, and
    # each list shown only for a translation Settings shows (base.html ubTr);
    # on the overview, only where it found something.
    tq = fts_query(fold(q))
    for x in trs:
        if scope in ("", x["key"]):
            got = _tr_hits(con, x["key"], tq, scope == x["key"], number) if tq else _hits(0, 0, [])
            if got["n"] or scope:
                found_tr.append({**x, "hits": got})
    if fq and scope in ("", "notes"):
        # What the 1955 cards say: the reading, and the committee's reasons beneath
        # it.  Always looked up, and shown only when Settings asks (ub.css
        # .by1955, off by default), for settings never reach the server.
        where = (" FROM footnote_fts x JOIN footnote f ON f.id=x.rowid"
                 " JOIN paragraph p ON p.id=f.paragraph_id"
                 " LEFT JOIN srt_item s ON s.id=f.srt_item_id"
                 " LEFT JOIN srt_item t ON t.id=s.see_id"
                 " WHERE footnote_fts MATCH ? AND f.kind='variant-1955'")
        n = con.execute("SELECT COUNT(*)" + where, (fq,)).fetchone()[0]
        size, off = _window(scope == "notes", "notes", number, n)
        hits = con.execute(
            "SELECT f.id, highlight(footnote_fts, 0, char(2), char(3)) AS reading,"
            "  snippet(footnote_fts, 1, char(2), char(3), char(4), 20) AS reasons,"
            "  x.reading AS reading_text, f.html AS reading_html, x.reasons AS reasons_text,"
            "  s.why_text AS a_text, s.why_html AS a_html, t.why_text AS b_text, t.why_html AS b_html"
            + where + " ORDER BY p.ord, f.ord LIMIT ? OFFSET ?", (fq, size, off)).fetchall()
        found = {n["id"]: n for n in queries.notes(
            con, f"f.id IN ({','.join('?' * len(hits))})", tuple(h["id"] for h in hits))}
        old = _hits(n, off, [
            _old_hit(found[h["id"]], _snip(h["reading"], h["reading_text"], sups(h["reading_html"])),
                     # Only where the search found something in them.
                     reasons=_snip(h["reasons"], h["reasons_text"],
                                   _reasons_at(h["a_text"], h["a_html"], h["b_text"], h["b_html"]))
                     if "\x02" in h["reasons"] else None)
            for h in hits])
    if q:
        # For the visit counter: a search that finds nothing is one the index might
        # answer.  So the 1955 readings, the study notes and the translations,
        # which most readers never see, count only where a reader asked for one
        # of them alone.
        request.state.hits = (len(heads) + (idx["n"] if idx else 0) + (txt["n"] if txt else 0)
                              + (old["n"] if old and scope == "notes" else 0)
                              + (stu["n"] if stu and scope == "study" else 0)
                              + sum(x["hits"]["n"] for x in found_tr if scope == x["key"]))
    return page(request, "search.html", q=q, scope=scope, idx=idx, txt=txt, old=old, stu=stu,
                trs=found_tr, heads=heads, diagnose=cite.diagnose(q) if q else None)


def _study_hit(n: dict, s: Markup) -> dict:
    """One study note among the search results (templates/_hits.html
    study_hit): its note (queries.study), the words it stands after, as the
    List of study notes shows them, and `s`, what the search found in it."""
    lead, word, _, _ = _around(n["para_text"], n["anchor"], before=10)
    return {**n, "before": lead + word, "s": s}


# A paragraph a translation's list holds: one whose words matched, or one of
# whose translator's notes did, for one translation (004_fts.sql).
TR_HIT = ("SELECT t.paragraph_id AS pid FROM tr_paragraph_fts f JOIN tr_paragraph t ON t.id=f.rowid"
          " WHERE tr_paragraph_fts MATCH ? AND t.translation=?"
          " UNION SELECT n.paragraph_id FROM tr_note_fts f JOIN tr_note n ON n.id=f.rowid"
          " WHERE tr_note_fts MATCH ? AND n.translation=?")


def _tr_hits(con: sqlite3.Connection, key: str, tq: str, whole: bool, number: int) -> dict:
    """One translation's list: a line to each paragraph it holds (TR_HIT), in
    the order of the book, by our reference.  Each with what the search found
    in the paragraph's words, `s`, or None where it found nothing there, and in
    its translator's notes, `notes`, each its key, number and snippet.  `tq` is
    the reader's words as fts_query() makes them, ё read as е (fold())."""
    args = (tq, key, tq, key)
    n = con.execute(f"SELECT COUNT(*) FROM ({TR_HIT})", args).fetchone()[0]
    size, off = _window(whole, "tr", number, n)
    rows = con.execute(f"SELECT h.pid, p.ref FROM ({TR_HIT}) h JOIN paragraph p ON p.id=h.pid"
                       " ORDER BY p.ord LIMIT ? OFFSET ?", (*args, size, off)).fetchall()
    ids = tuple(r["pid"] for r in rows)
    within = ",".join("?" * len(ids))
    said = {r["paragraph_id"]: _snip(_unfold(r["s"], r["text"]), r["text"],
                                     sups(r["html_hy"].replace("­", "")))
            for r in con.execute(
        "SELECT t.paragraph_id, t.text, t.html_hy,"
        "  snippet(tr_paragraph_fts, 0, char(2), char(3), char(4), 24) AS s"
        " FROM tr_paragraph_fts f JOIN tr_paragraph t ON t.id=f.rowid"
        f" WHERE tr_paragraph_fts MATCH ? AND t.translation=? AND t.paragraph_id IN ({within})",
        (tq, key, *ids))}
    notes: dict[int, list] = {}
    for r in con.execute(
            "SELECT n.paragraph_id, n.key, n.num, n.text, n.html_hy,"
            "  snippet(tr_note_fts, 0, char(2), char(3), char(4), 24) AS s"
            " FROM tr_note_fts f JOIN tr_note n ON n.id=f.rowid"
            f" WHERE tr_note_fts MATCH ? AND n.translation=? AND n.paragraph_id IN ({within})"
            " ORDER BY n.num", (tq, key, *ids)):
        notes.setdefault(r["paragraph_id"], []).append(
            {"key": r["key"], "num": r["num"],
             "s": _snip(_unfold(r["s"], r["text"]), r["text"], sups(r["html_hy"].replace("­", "")))})
    return _hits(n, off, [{"ref": r["ref"], "s": said.get(r["pid"]), "notes": notes.get(r["pid"], [])}
                          for r in rows])


def _old_hit(n: dict, reading: Markup, **more) -> dict:
    """One 1955 reading for a list (templates/_old.html), on the List of 1955
    readings and among the search results: its note (queries.notes), the
    reading as that list shows it, and today's words around its ring.  `more`
    is what that list alone shows -- `dec`, the verdict on the line, and
    `reasons`, a search's snippet -- under keys of their own: the note's
    columns are what its card is made from."""
    return {**n, "reading": reading,
            "now": _around(n["para_text"], n["anchor"], sup=sups(n["para_html"])), **more}


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
        "SELECT e.slug, e.headword_html, s.n_descendants"
        " FROM index_entry e JOIN entry_stats s ON s.entry_id=e.id"
        " WHERE e.scope='az' AND e.level=1 AND e.letter=? ORDER BY e.ord",
        (letter.upper(),)).fetchall()
    if not rows:
        return missing(request, l10n.tr("The index has no section headed “{l}”.", l=letter))
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
# (Tigran, 2026-10-12), the study notes as their papers are reviewed (Tigran,
# 2026-10-18), the works those notes cite (2026-10-19), and the illustrations
# with Phase 6.
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


@app.get("/lists/notes", response_class=HTMLResponse)
def list_notes(request: Request):
    """Every study note on the site in one list, by paper, in the order of the
    book (Tigran, 2026-10-18): the words it stands after, and the note itself,
    as its card shows it.  The reference opens its paragraph, with the card.
    Only the papers whose notes are reviewed (build/study.py)."""
    groups: list[dict] = []
    for n in queries.study(db()):
        if not groups or groups[-1]["n"] != n["paper_n"]:
            groups.append({"n": n["paper_n"], "title": n["paper_title"], "rows": []})
        lead, word, _, _ = _around(n["para_text"], n["anchor"], before=10)
        groups[-1]["rows"].append({**n, "before": lead + word})
    return page(request, "list_notes.html", groups=groups,
                n=sum(len(g["rows"]) for g in groups))


@app.get("/lists/bibliography", response_class=HTMLResponse)
def list_bibliography(request: Request):
    """Every work the study notes on the site cite, once, by its author's
    surname, with the notes that cite it (Tigran, 2026-10-19): so that, as the
    papers' notes are reviewed, the human sources the book draws on can be
    seen in one list.  A note's reference opens its paragraph, with the card."""
    return page(request, "list_bibliography.html", works=queries.bibliography(db()))


# The changelog, ChangeLog.md as build/changelog.py put it in the database
# (Tigran, 2026-10-18): the file as written, every block in its order, each
# entry in a version with the day it was written, and what is for developers
# folded where it stands.  What's new lists the same entries for readers, those
# after a reader's copy.  The footer links it from every page.
def us_date(iso: str) -> str:
    """"October 18, 2026": the site writes a date in words in the American
    order (Tigran, 2026-10-18), as offline.js and sw.js do."""
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def _blocks(rows) -> list[dict]:
    """[{kind: h1 h2 h3 p ul dev, ...}] in the file's order: a run of entries is
    one list, and what stands under For developers one folded block."""
    out: list[dict] = []
    into = out
    for r in rows:
        k, h = r["kind"], Markup(r["html"])
        if k in ("h1", "h2", "h3"):
            into = out
            if k == "h3" and r["part"] == "developers":
                out.append({"kind": "dev", "summary": h, "blocks": []})
                into = out[-1]["blocks"]
                continue
            out.append({"kind": k, "html": h})
        elif k == "para":
            into.append({"kind": "p", "html": h})
        else:
            if not into or into[-1]["kind"] != "ul":
                into.append({"kind": "ul", "items": []})
            into[-1]["items"].append({"html": h, "day": r["version"] and us_date(r["written"])})
    return out


@app.get("/changelog", response_class=HTMLResponse)
def changelog(request: Request):
    rows = db().execute("SELECT * FROM changelog ORDER BY line").fetchall()
    return page(request, "changelog.html", blocks=_blocks(rows))


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


@functools.lru_cache(maxsize=16)
def _toc(mtime_ns: int, bilingual: bool, key: str) -> dict | None:
    try:
        con = db()
        row = con.execute("SELECT lang FROM translation WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        rows = con.execute("SELECT kind, n, section_n, html, caps FROM tr_toc WHERE translation = ?"
                           " ORDER BY kind, n, section_n", (key,)).fetchall()
    except sqlite3.Error:
        return None                                # a database from before tr_toc
    lang = row["lang"]
    words = {}
    for w, k in TOC_WORDS.items():
        by = l10n.tr(k, r="{r}", a="{a}", b="{b}").by
        words[w] = str(by.get(lang, by["en"]))
    out = {"lang": lang, "words": words, "parts": {}, "papers": {}, "sections": {},
           "caps": {"parts": [], "papers": [], "sections": []}}
    for r in rows:
        k = str(r["n"]) if r["section_n"] is None else f"{r['n']}:{r['section_n']}"
        out[r["kind"] + "s"][k] = r["html"]
        if r["caps"]:
            out["caps"][r["kind"] + "s"].append(k)
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    return {"body": body, "v": hashlib.sha256(body.encode()).hexdigest()[:12]}


def toc_of(key: str) -> dict | None:
    """A translation's own contents as the left rail shows them when a reader
    chooses it (ub.js tocApply), JSON: its parts', papers' and sections' titles
    by our numbers, those written in capitals (`caps`, set in small capitals),
    and the rail's own words in its language, 0. Введение, Часть I., 9 и 10.;
    with its version, a hash of it.  None for a key no translation has."""
    return _toc(db_version(), l10n.BILINGUAL, key)


@app.get("/rail/{key}", include_in_schema=False)
def rail_toc(key: str, v: str = ""):
    """A translation's contents, for the left rail when a reader chooses it on
    the rail's line (Tigran, 2026-10-27): asked for under its version
    (translations_json's `toc`), the answer is kept for good, as /rail/N's is."""
    got = toc_of(key)
    if got is None:
        return Response("No such translation.\n", status_code=404, media_type="text/plain")
    cache = "public, max-age=31536000, immutable" if v == got["v"] else "no-cache"
    return Response(got["body"], media_type="application/json", headers={"Cache-Control": cache})


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
    nxt = {"href": f"/{fp}:{first}", "label": l10n.tr("Next section: {s}", s=f"{fp}:{first}")}
    return page(request, "part.html", part=part, roman=ROMAN[n], nxt=nxt)


NO_PAPER = "There is no Paper {n}. The Foreword is Paper 0, and the papers run to 196."


@app.get("/{paper:int}")
def paper_page(request: Request, paper: int):
    """A paper number opens the paper, not a table of its sections.

    Every paper begins with an unnumbered introduction, so /101 lands on
    101:0 -- the first words of the text.  The section list is always in the
    left rail, so a separate page for it was a click that bought nothing.
    """
    return _first_section(request, paper, "")


def _first_section(request: Request, paper: int, then: str):
    con = db()
    first = con.execute(
        "SELECT MIN(n) FROM section WHERE paper_n=?", (paper,)).fetchone()[0]
    if first is None:
        return missing(request, l10n.tr(NO_PAPER, n=paper))
    return RedirectResponse(f"/{paper}:{first}{then}", status_code=307)


# Compare, the text and the translations a reader has ticked side by side
# (ROADMAP item 15, step 2), has an address of its own, /1:1/compare, so that
# Back leaves it and a reload or a link keeps it.  It is the same page as
# /1:1, byte for byte: ub.js draws the columns from /tr/, as a fold draws its
# translations, so no setting reaches the server and the offline copy holds
# no page more (offline-core.js resolve).  The rail's papers link /N, which
# goes to the paper's first section, and in Compare /N/compare.
@app.get("/{paper:int}/compare")
def paper_compare(request: Request, paper: int):
    return _first_section(request, paper, "/compare")


@app.get("/{ref}/compare", response_class=HTMLResponse)
def read_compare(request: Request, ref: str):
    if ref == "api":
        raise HTTPException(404)               # a program's, answered in JSON (http_error)
    return read(request, ref)


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
        return missing(request, l10n.tr(NO_PAPER, n=paper))
    if s is None:
        return missing(request, l10n.tr("Paper {n} has no section {s}.", n=paper, s=sec))
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
                return missing(request, l10n.tr("There is no paragraph {p}: {s} runs from {a} to {b}.",
                                                p=f"{here}.{k}", s=here, a=go(f"{here}.1"), b=go(f"{here}.{n}")))
        if last < focus:
            return missing(request, l10n.tr("A range runs forwards, in the order of the book: {a}, not {b}.",
                                            a=go(f"{here}.{last}-{focus}"), b=f"{here}.{focus}-{last}"))
    rows = queries.section(con, paper, sec)
    go = transport(con, paper, sec)
    # Where listening goes on to: the next section, or from a paper's last
    # section the next paper's first, as the transport bar's ⏭ does.
    onward = None
    if go["next"]:
        n = go["next"]
        onward = {"href": n["href"], "label": f"{n['n']}. {n['title']}"}
        if n["paper_n"] != paper:
            # Text, as listen.js sets it: in Russian too, where both are drawn.
            w = l10n.tr("Paper {n}. {title}", n=n["paper_n"], title=n["ptitle"])
            onward["label"] = w.en.unescape()
            if l10n.BILINGUAL:
                onward["label_ru"] = w["ru"].unescape()
    tr = translated(paper, sec)
    return page(request, "section.html", paper=p, section=s, **rows,
                focus=focus, last=last, go=go, onward=onward,
                audio=section_audio(con, s["id"]), tr_has=tr["has"], trv=tr["v"])


def transport(con, paper: int, sec: int) -> dict:
    """The transport bar at a section's end: a paper back (fb), a section back
    (prev), a section on (next), a paper on (ff), in the order of the book.

    A section steps across a paper's edge, 101:0 back to 100's last section;
    a paper goes to its first section, never the /N redirect.  Part pages are
    not stops.  None at the book's ends.  The label is the tooltip and the
    accessible name alike (Tigran, 2026-10-14).
    """

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
    def paper(row, foreword, numbered):
        return row and (l10n.tr(foreword) if row["paper_n"] == 0 else l10n.tr(numbered, p=row["paper_n"]))
    return {"fb": at(fb, paper(fb, "Previous paper: the Foreword", "Previous paper: {p}")),
            "prev": at(prev, prev and l10n.tr("Previous section: {s}", s=f"{prev['paper_n']}:{prev['n']}")),
            "next": at(nxt, nxt and l10n.tr("Next section: {s}", s=f"{nxt['paper_n']}:{nxt['n']}")),
            "ff": at(ff, paper(ff, "Next paper: the Foreword", "Next paper: {p}"))}
