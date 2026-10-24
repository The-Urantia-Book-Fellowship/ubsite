"""The site, asked in-process: what the server sends for a URL.

The offline copy is the site's own pages, so it is made by asking the app for
them, as a browser would through nginx, but without a socket: the ASGI app is
called directly, with routing, the exception handlers and the middleware all
in the path.  The visit counter is off (UB_VISITS=off, set before the app is
imported), since these are not visits.
"""

from __future__ import annotations

import asyncio
import os

os.environ["UB_VISITS"] = "off"

from ubsite.app import app  # noqa: E402

HOST = "ubsite.ddns.net"


class Page:
    __slots__ = ("status", "headers", "body")

    def __init__(self, status: int, headers: dict, body: bytes):
        self.status, self.headers, self.body = status, headers, body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def get(path: str, query: str = "", host: str = HOST) -> Page:
    """GET `path`?`query` from the app, as the server would answer it, asked
    at `host`."""
    return asyncio.run(_get(path, query, host))


async def _get(path: str, query: str, host: str = HOST) -> Page:
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "https", "path": path, "raw_path": path.encode(),
             "root_path": "", "query_string": query.encode(),
             "headers": [(b"host", host.encode()), (b"accept", b"text/html")],
             "server": (host, 443), "client": ("127.0.0.1", 0)}
    out = {"status": 0, "headers": {}, "body": []}
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            await asyncio.sleep(3600)
        sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        if m["type"] == "http.response.start":
            out["status"] = m["status"]
            out["headers"] = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            out["body"].append(m.get("body", b""))

    await app(scope, receive, send)
    return Page(out["status"], out["headers"], b"".join(out["body"]))


def get_many(paths: list[tuple[str, str]]) -> list[Page]:
    """Many pages on one event loop: about twice as fast as get() each."""
    async def run():
        return [await _get(p, q) for p, q in paths]
    return asyncio.run(run())
