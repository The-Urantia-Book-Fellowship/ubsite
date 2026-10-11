"""The text API, /api/v1: the English text for other sites to sync with their own.

A site keeps the number of the version it last received.  It asks
/api/v1/text?since=<that number>, and gets every record new or changed after
it, the keys of any removed, and the new number to keep.  From 0 -- a site with
no text yet -- the reply is the whole text.  Versions are made by the build
(build/versions.py), which stores every record as the JSON sent here, so this
module only selects, concatenates and compresses.  /api, in app.py, documents it.

Every reply is cached gzipped per worker, keyed on the database and on what was
asked: the whole text is compressed once per worker per deploy, and a site
already up to date costs a 304.
"""

from __future__ import annotations

import functools
import gzip
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


def example(base: str) -> tuple[int, str]:
    """(since, reply): the reply to a site one version behind, its records counted
    rather than listed, for /api.  From 0 while there is only one version."""
    meta = _meta(_db_version())
    cur = meta["versions"][-1]
    since = cur["version"] - 1
    n = dict(_con().execute("SELECT kind, COUNT(*) FROM text_unit WHERE version > ?"
                            " GROUP BY kind", (since,)))
    out = json.dumps(head(cur, since, base), ensure_ascii=False, indent=1)[:-2]
    for k in KINDS:
        out += f',\n "{PLURAL[k]}": ' + (f"[ {n[k]:,} records ]" if n.get(k) else "[]")
    empty = ", ".join(f'"{PLURAL[k]}": []' for k in KINDS)
    return since, out + f',\n "removed": {{{empty}}}\n}}'


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
    out = [json.dumps(head(cur, since, base), ensure_ascii=False, separators=(",", ":"))[:-1]]
    for k in KINDS:
        out.append(f',"{PLURAL[k]}":[' + ",".join(bodies[k]) + "]")
    out.append(',"removed":' + json.dumps(removed, separators=(",", ":")) + "}")
    return gzip.compress("".join(out).encode("utf-8"), 6)


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


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "docs": "/api"}, status_code=status, headers=CORS)


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
                  "docs": f"{base}api"}}, f'W/"v{cur["version"]}-about-{_db_version()}"')


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
for _path in ("", "/", "/text", "/versions"):
    router.add_api_route(_path, preflight, methods=["OPTIONS"])
