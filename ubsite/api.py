"""The text API, /api/v1: the English text for other sites to sync with their own.

A site keeps the number of the version it last received.  It asks
/api/v1/text?since=<that number>, and gets every record new or changed after
it, the keys of any removed, and the new number to keep.  From 0 -- a site with
no text yet -- the reply is the whole text.  Versions are made by the build
(build/versions.py), which stores every record as the JSON sent here, so this
module only selects, concatenates and compresses.  /api, in app.py, documents it.

A site may also ask for a passage or a paper by reference,
/api/v1/paragraphs/101:4.2-7,5:1 or /api/v1/papers/101-103, in this site's
numbering or, with ?numbering=uf, the Foundation's.  The reply holds the same
records, and the section, paper and part each paragraph stands in.

Every reply is cached gzipped per worker, keyed on the database and on what was
asked: the whole text is compressed once per worker per deploy, and a site
already up to date costs a 304.
"""

from __future__ import annotations

import dataclasses
import functools
import gzip
import hashlib
import json
import pathlib
import re
import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "var" / "ub.db"
KINDS = ("part", "paper", "section", "paragraph")
PLURAL = {k: k + "s" for k in KINDS}
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Expose-Headers": "ETag"}

router = APIRouter(prefix="/api/v1", include_in_schema=False)


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _db_version() -> int:
    try:
        return DB.stat().st_mtime_ns
    except OSError:
        return 0


def licence(base: str) -> dict:
    """The English text is in the public domain; credit is asked for, not required."""
    return {"text": "public domain", "credit": "requested, not required",
            "credit_line": f"Text: the Uversa Press edition of The Urantia Book, {base}"}


class Unbuilt(Exception):
    """A database from before the text API (build/schema/006_api.sql)."""


@functools.lru_cache(maxsize=2)
def _meta(mtime_ns: int) -> dict:
    con = _con()
    try:
        versions = [{"version": n, "made": made, "press_commit": commit, "changed": c,
                     "removed": r} for n, made, commit, c, r in con.execute(
                        "SELECT n, made_on, press_commit, changed, removed FROM text_version"
                        " ORDER BY n")]
    except sqlite3.Error:
        versions = []
    if not versions:
        raise Unbuilt
    counts = dict(con.execute("SELECT kind, COUNT(*) FROM text_unit GROUP BY kind"))
    press = con.execute("SELECT commit_id, committed_at, dirty FROM build_source"
                        " WHERE repo = 'press'").fetchone()
    return {"versions": versions, "counts": {PLURAL[k]: counts.get(k, 0) for k in KINDS},
            "press": press and {"commit": press[0], "date": press[1], "dirty": bool(press[2])}}


def head(cur: dict, since: int, base: str) -> dict:
    """What a reply to /text says before its records: /api shows it as it is."""
    return {"api": 1, "version": cur["version"], "since": since, "full": since == 0,
            "made": cur["made"], "source": {"press": cur["press_commit"]},
            "licence": licence(base)}


def selection_head(cur: dict, base: str) -> dict:
    """What a reply to /paragraphs or /papers says before its records.  No since,
    full or removed: it is not a step in keeping a copy, and a sync client handed
    one by mistake fails on the missing keys rather than keeping its version."""
    return {"api": 1, "version": cur["version"], "made": cur["made"],
            "source": {"press": cur["press_commit"]}, "licence": licence(base)}


def _counted(top: dict, n: dict, removed: bool) -> str:
    """A reply as /api shows it: its head as it is, its records counted, not listed."""
    out = json.dumps(top, ensure_ascii=False, indent=1)[:-2]
    for k in KINDS:
        out += f',\n "{PLURAL[k]}": ' + (
            f"[ {n[k]:,} record{'' if n[k] == 1 else 's'} ]" if n.get(k) else "[]")
    if removed:
        empty = ", ".join(f'"{PLURAL[k]}": []' for k in KINDS)
        out += f',\n "removed": {{{empty}}}'
    return out + "\n}"


def example(base: str) -> tuple[int, str]:
    """(since, reply): the reply to a site one version behind, its records counted
    rather than listed, for /api.  From 0 while there is only one version."""
    meta = _meta(_db_version())
    cur = meta["versions"][-1]
    since = cur["version"] - 1
    n = dict(_con().execute("SELECT kind, COUNT(*) FROM text_unit WHERE version > ?"
                            " GROUP BY kind", (since,)))
    return since, _counted(head(cur, since, base), n, removed=True)


def example_selection(base: str, sel: str) -> str:
    """The reply to /paragraphs/<sel>, its records counted, for /api: the reply
    itself, so that the page cannot describe another."""
    mtime = _db_version()
    reply = json.loads(gzip.decompress(_select(
        mtime, _merge(_paragraph_runs(_book(mtime), sel, False)), base)))
    return _counted({k: v for k, v in reply.items() if k not in PLURAL.values()},
                    {k: len(reply[PLURAL[k]]) for k in KINDS}, removed=False)


def _pack(top: dict, bodies: dict, removed: dict | None = None) -> bytes:
    """A reply, gzipped: its head, then each kind's stored records as they are."""
    out = [json.dumps(top, ensure_ascii=False, separators=(",", ":"))[:-1]]
    for k in KINDS:
        out.append(f',"{PLURAL[k]}":[' + ",".join(bodies[k]) + "]")
    if removed is not None:
        out.append(',"removed":' + json.dumps(removed, separators=(",", ":")))
    out.append("}")
    return gzip.compress("".join(out).encode("utf-8"), 6)


@functools.lru_cache(maxsize=8)
def _text(mtime_ns: int, since: int, base: str) -> bytes:
    """The reply to /text?since=..., gzipped.  `since` is 0 for the whole text."""
    meta = _meta(mtime_ns)
    cur = meta["versions"][-1]
    con = _con()
    bodies = {k: [] for k in KINDS}
    for kind, body in con.execute("SELECT kind, body FROM text_unit WHERE version > ?"
                                  " ORDER BY id", (since,)):
        bodies[kind].append(body)
    # A full reply replaces everything, so it has nothing to remove.
    removed = {PLURAL[k]: [] for k in KINDS}
    for kind, key in con.execute("SELECT kind, key FROM text_removed WHERE version > ?"
                                 " AND ? > 0 ORDER BY version, kind, key", (since, since)):
        removed[PLURAL[kind]].append(key)
    return _pack(head(cur, since, base), bodies, removed)


@dataclasses.dataclass(frozen=True)
class Book:
    """Where every record stands, for /paragraphs and /papers: paragraphs by their
    place in reading order, and sections and papers as runs of those places."""
    ids: list[int]                              # each paragraph's text_unit id
    sec_of: list[str]                           # each paragraph's section, '101:4'
    paper_of: list[int]
    at: dict[str, int]                          # '101:4.2' -> its place
    uf_at: dict[str, int]                       # the same, by the Foundation's numbering
    sec: dict[str, tuple[int, int]]             # '101:4' -> (first place, last place)
    uf_sec: dict[str, tuple[int, int]]          # '139:10' -> our 139:9's
    paper: dict[int, tuple[int, int]]
    part_of: dict[int, int | None]              # the Foreword is in no part
    unit: dict[tuple[str, str], int]            # (kind, key) -> text_unit id, but paragraphs


@functools.lru_cache(maxsize=2)
def _book(mtime_ns: int) -> Book:
    _meta(mtime_ns)                             # Unbuilt, for a database from before the API
    con = _con()
    ids, sec_of, paper_of, at, uf_at = [], [], [], {}, {}
    sec: dict[str, tuple[int, int]] = {}
    paper: dict[int, tuple[int, int]] = {}
    for i, (ref, uid, o, uf) in enumerate(con.execute(
            "SELECT t.key, t.id, t.ord, u.ref FROM text_unit t JOIN paragraph p ON p.ref = t.key"
            " JOIN uf_paragraph u ON u.paragraph_id = p.id WHERE t.kind = 'paragraph'"
            " ORDER BY t.ord")):
        if o != i:
            raise RuntimeError(f"text_unit: paragraph {ref} is at {o}, not {i}")
        s = ref.partition(".")[0]
        n = int(s.partition(":")[0])
        ids.append(uid)
        sec_of.append(s)
        paper_of.append(n)
        at[ref] = uf_at[uf] = i
        sec[s] = (sec.get(s, (i, i))[0], i)
        paper[n] = (paper.get(n, (i, i))[0], i)
    uf_sec = {uf: sec[f"{p}:{n}"] for p, n, uf in con.execute(
        "SELECT s.paper_n, s.n, u.ref FROM section s JOIN uf_section u ON u.section_id = s.id")}
    return Book(ids, sec_of, paper_of, at, uf_at, sec, uf_sec, paper,
                dict(con.execute("SELECT n, part_n FROM paper")),
                {(k, key): uid for k, key, uid in con.execute(
                    "SELECT kind, key, id FROM text_unit WHERE kind <> 'paragraph'")})


class Bad(Exception):
    """A selection that cannot be read: a 400."""


class Missing(Exception):
    """References well formed that name nothing in the text: a 404, naming them all."""

    def __init__(self, refs: list[str], message: str):
        super().__init__(message)
        self.refs = refs


NUM = "[0-9]{1,4}"
RE_PAPER = re.compile(NUM)
RE_SEC = re.compile(rf"({NUM}):({NUM})")
RE_PARA = re.compile(rf"({NUM}):({NUM})\.({NUM})")
RE_TAIL = re.compile(rf"({NUM})\.({NUM})")
MAX_ITEMS = 100
PAPERS = "The Foreword is Paper 0, and the papers run to 196."


def _items(sel: str) -> list[str]:
    # An en dash too: a range copied from print, or from /api itself, has one.
    items = [x.strip() for x in sel.replace("–", "-").split(",")]
    if len(items) > MAX_ITEMS:
        raise Bad(f"At most {MAX_ITEMS} references at a time.")
    if "" in items:
        raise Bad("An empty reference: write them with one comma between each two.")
    return items


def _whole(m: re.Match) -> str:
    """A reference as this site writes it: 101:04.2 is 101:4.2."""
    return ":".join(".".join(str(int(x)) for x in part.split("."))
                    for part in m[0].split(":"))


def _end(start: re.Match, end: str) -> str | None:
    """The end of a range, written whole: it has the shape of the start's tail,
    so after 101:4.7 it is 9, 5.2 or 102:1.3, and after 101:4 it is 6 or 102:1."""
    p, s = start[1], start[2]
    if start.re is RE_PARA:
        if RE_PAPER.fullmatch(end):
            return _whole(RE_PARA.fullmatch(f"{p}:{s}.{end}"))
        if RE_TAIL.fullmatch(end):
            return _whole(RE_PARA.fullmatch(f"{p}:{end}"))
        m = RE_PARA.fullmatch(end)
    else:
        if RE_PAPER.fullmatch(end):
            return _whole(RE_SEC.fullmatch(f"{p}:{end}"))
        m = RE_SEC.fullmatch(end)
    return m and _whole(m)


def _paragraph_runs(book: Book, sel: str, uf: bool) -> list[tuple[int, int]]:
    """The places a /paragraphs selection names, as (first, last) runs."""
    at, sec = (book.uf_at, book.uf_sec) if uf else (book.at, book.sec)
    runs, missing = [], []
    for item in _items(sel):
        first, dash, last = (x.strip() for x in item.partition("-"))
        m = RE_PARA.fullmatch(first) or RE_SEC.fullmatch(first)
        if not m:
            if RE_PAPER.fullmatch(first):
                raise Bad(f"{item}: write each reference whole, 61:4.3,61:4.4 or 61:4.3-4;"
                          f" a whole paper is /api/v1/papers/{item.replace(' ', '')}")
            raise Bad(f"{item}: not a reference.  Write a paragraph 101:4.2, a section"
                      " 101:4, or a range of either, 101:4.2-7 or 101:4-6.")
        a = _whole(m)
        b = _end(m, last) if dash else a
        if b is None:
            raise Bad(f"{item}: a range ends as it begins, with as much as changes:"
                      " 101:4.2-7, 101:4.7-5.2, 101:4.7-102:1.3, or 101:4-6, 101:4-102:1.")
        found = []
        for r in dict.fromkeys((a, b)):
            span = ((at[r], at[r]) if r in at else None) if "." in r else sec.get(r)
            if span is None:
                missing.append(r)
            found.append(span)
        if None in found:
            continue
        lo, hi = found[0][0], found[-1][1]
        if hi < lo:
            raise Bad(f"{item}: a range runs forwards, in the order of the book.")
        runs.append((lo, hi))
    if missing:
        how = " as the Foundation numbers it" if uf else ""
        raise Missing(list(dict.fromkeys(missing)),
                      f"Not in the text{how}: {', '.join(dict.fromkeys(missing))}.")
    return runs


def _paper_runs(book: Book, sel: str) -> list[tuple[int, int]]:
    """The places a /papers selection names, as (first, last) runs."""
    runs, missing = [], []
    for item in _items(sel):
        if ":" in item:
            raise Bad(f"{item}: a paragraph or a section is /api/v1/paragraphs/{item}")
        first, dash, last = (x.strip() for x in item.partition("-"))
        if not RE_PAPER.fullmatch(first) or (dash and not RE_PAPER.fullmatch(last)):
            raise Bad(f"{item}: not a paper.  Write 101, or a range, 101-103.")
        a, b = int(first), int(last) if dash else int(first)
        if b < a:
            raise Bad(f"{item}: a range runs forwards, in the order of the book.")
        gone = [n for n in dict.fromkeys((a, b)) if n not in book.paper]
        missing += gone
        if not gone:
            runs.append((book.paper[a][0], book.paper[b][1]))
    if missing:
        raise Missing([str(n) for n in dict.fromkeys(missing)],
                      f"Not in the text: {', '.join(map(str, dict.fromkeys(missing)))}. {PAPERS}")
    return runs


def _merge(runs: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """The runs sorted and joined where they touch: one selection, however written."""
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(runs):
        if out and lo <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return tuple(out)


@functools.lru_cache(maxsize=32)
def _select(mtime_ns: int, runs: tuple[tuple[int, int], ...], base: str) -> bytes:
    """The reply to a selection, gzipped: its paragraphs, each once in reading
    order, and the section, paper and part each stands in."""
    cur = _meta(mtime_ns)["versions"][-1]
    book = _book(mtime_ns)
    ids, around = [], {}
    for lo, hi in runs:
        for i in range(lo, hi + 1):
            ids.append(book.ids[i])
            around[("section", book.sec_of[i])] = None
            around[("paper", str(book.paper_of[i]))] = None
            part = book.part_of[book.paper_of[i]]
            if part is not None:
                around[("part", str(part))] = None
    ids += [book.unit[k] for k in around]
    bodies = {k: [] for k in KINDS}
    for kind, body in _con().execute("SELECT kind, body FROM text_unit WHERE id IN"
                                     " (SELECT value FROM json_each(?)) ORDER BY ord",
                                     (json.dumps(ids),)):
        bodies[kind].append(body)
    return _pack(selection_head(cur, base), bodies)


def about_meta() -> dict:
    """The versions, the current one and the counts, for the /api page."""
    meta = _meta(_db_version())
    return {**meta, "current": meta["versions"][-1]}


def _gzip_ok(request: Request) -> bool:
    for token in request.headers.get("accept-encoding", "").split(","):
        name, _, q = token.strip().partition(";")
        if name.strip().lower() in ("gzip", "*"):
            return q.replace(" ", "") not in ("q=0", "q=0.0", "q=0.00", "q=0.000")
    return False


def _matches(request: Request, etag: str) -> bool:
    have = request.headers.get("if-none-match", "")
    tags = [t.strip() for t in have.split(",")]
    bare = etag.removeprefix("W/")
    return "*" in tags or any(t.removeprefix("W/") == bare for t in tags)


def _reply(request: Request, packed: bytes, etag: str) -> Response:
    """200, or 304 if the client has it; gzipped if it says it can take that."""
    headers = {**CORS, "ETag": etag, "Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
    if _matches(request, etag):
        return Response(status_code=304, headers=headers)
    if _gzip_ok(request):
        return Response(packed, media_type="application/json",
                        headers={**headers, "Content-Encoding": "gzip"})
    return Response(gzip.decompress(packed), media_type="application/json", headers=headers)


def error(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra, "docs": "/api"}, status_code=status,
                        headers=CORS)


def _base(request: Request) -> str:
    return str(request.base_url)


RE_SINCE = re.compile(r"[0-9]{1,9}")


@router.get("/text")
def text(request: Request, since: str = "0"):
    """Everything new or changed after version `since`; from 0, or from a version
    this site has not made, the whole text."""
    if not RE_SINCE.fullmatch(since):
        return error(400, "since must be a version number: 0, or the version you hold")
    asked = int(since)
    mtime = _db_version()
    cur = _meta(mtime)["versions"][-1]["version"]
    eff = asked if 0 < asked <= cur else 0
    request.state.api = (asked, cur, eff == 0)
    return _reply(request, _text(mtime, eff, _base(request)), f'W/"v{cur}-s{eff}"')


NUMBERING = 'numbering must be "uf", for the Foundation\'s, or left out, for this site\'s'


def _selected(request: Request, numbering: str, runs_of) -> Response:
    """The reply to a selection, `runs_of(book)` reading it: or a 400, or a 404
    naming every reference not in the text."""
    if numbering not in ("", "uf"):
        return error(400, NUMBERING)
    mtime = _db_version()
    try:
        runs = _merge(runs_of(_book(mtime)))
    except Bad as e:
        return error(400, str(e))
    except Missing as e:
        return error(404, str(e), missing=e.refs)
    cur = _meta(mtime)["versions"][-1]["version"]
    request.state.api = (None, cur, False)
    tag = hashlib.sha256(repr(runs).encode()).hexdigest()[:16]
    return _reply(request, _select(mtime, runs, _base(request)), f'W/"v{cur}-r{tag}"')


@router.get("/paragraphs/{sel}")
def paragraphs(request: Request, sel: str, numbering: str = ""):
    """Paragraphs, ranges of them and whole sections, from anywhere in the book."""
    return _selected(request, numbering, lambda book: _paragraph_runs(book, sel, numbering == "uf"))


@router.get("/papers/{sel}")
def papers(request: Request, sel: str, numbering: str = ""):
    """Whole papers.  Both numberings number papers alike, so `numbering` is taken
    and changes nothing: a client that always sends it is not refused."""
    return _selected(request, numbering, lambda book: _paper_runs(book, sel))


def _small(request: Request, obj: dict, etag: str) -> Response:
    packed = gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                           .encode("utf-8"), 6)
    return _reply(request, packed, etag)


@router.get("")
@router.get("/")
def about(request: Request):
    """The current version, where it came from, how much there is, and where to go next."""
    meta = _meta(_db_version())
    cur = meta["versions"][-1]
    base = _base(request)
    request.state.api = (None, cur["version"], False)
    return _small(request, {
        "api": 1, "version": cur["version"], "made": cur["made"], "counts": meta["counts"],
        "source": {"press": meta["press"]}, "licence": licence(base),
        "links": {"text": f"{base}api/v1/text?since=0", "versions": f"{base}api/v1/versions",
                  "paragraphs": f"{base}api/v1/paragraphs/{{refs}}",
                  "papers": f"{base}api/v1/papers/{{numbers}}", "docs": f"{base}api"}},
        f'W/"v{cur["version"]}-about-{_db_version()}"')


@router.get("/versions")
def versions(request: Request):
    """Every version: when it was made, from which press commit, and how much it changed."""
    meta = _meta(_db_version())
    cur = meta["versions"][-1]["version"]
    request.state.api = (None, cur, False)
    return _small(request, {"api": 1, "version": cur, "versions": meta["versions"]},
                  f'W/"v{cur}-versions"')


def preflight():
    """A browser asks before sending If-None-Match from another site's page."""
    return Response(status_code=204, headers={**CORS, "Access-Control-Allow-Methods": "GET",
                                              "Access-Control-Allow-Headers": "If-None-Match",
                                              "Access-Control-Max-Age": "86400"})


# Endpoint by endpoint: one OPTIONS route over every path would make a GET of a
# path that is not an endpoint a 405, "wrong method", rather than a 404.
for _path in ("", "/", "/text", "/versions", "/paragraphs/{sel}", "/papers/{sel}"):
    router.add_api_route(_path, preflight, methods=["OPTIONS"])
