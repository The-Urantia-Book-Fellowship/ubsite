"""What the copy holds: the site's pages, asked of the app and cut into pieces.

A page is cut at six fixed places in base.html.  What lies between them is
the same on every page of a build -- the head with its links and the settings
script, the header, the Settings dialog, the footer -- and is kept once, as
the shell.  What is left is the page's own:

    t  its title               h  its head block, after the settings script
    q  the search box's value  b  its body block, the <main>
    s  its scripts block

and a page is shell[0] + t + shell[1] + h + shell[2] + q + shell[3] + b +
shell[4] + s + shell[5].  static/offline-core.js joins them so; a stored page
has q empty, and only a search fills it in.

A section page's left rail (templates/_rail.html) is the whole book, with its
paper open and its section marked `here`.  It is two thirds of the page, and
the same for every section of a paper but for that mark, so it is lifted out
of the body, where a NUL stands in for it, and kept once for the paper with
no section marked.  The worker marks the section again.

A headword's reading path (/i/<slug>/read, and /read/theme) is a page like any
other, and the largest part of the copy: 132 MB of the 191 unpacked, though
it is made of paragraphs the copy has already, because each paragraph comes
with its captions and the folds around it.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3

from markupsafe import Markup
from starlette.requests import Request

from . import site

# Where each piece of the shell ends, in base.html's order.  Each is searched
# for after the one before; the footer's and the body's end from the end, since
# a page's own body could hold anything.
RE_RAIL = re.compile(r'<nav class="rail".*?</nav>', re.S)
RAIL = "\x00"
# Papers to a chunk of spoken text (offline-core.js knows it too).
SPOKEN = 20
# About how much of the reading paths a chunk holds, as JSON: what the worker
# unpacks and parses to show one of them.  A headword whose paths are longer
# has a chunk of its own (Jesus: 2.7 MB in each order).
PATHS = 1_000_000

# The not-found page's words, to cut it at: its message and the path it names.
PROBE = "/offline-missing-probe"
PROBE_MSG = "There is no page at this address."


class Shape(Exception):
    """A page that does not cut as base.html says every page does."""


def cut(html: str) -> tuple[tuple[str, ...], dict]:
    """(the shell's six pieces, the page's own) for one rendered page."""
    try:
        i0 = html.index("<title>") + len("<title>")
        i1 = html.index("</title>", i0)
        i2 = html.index("</script>\n", i1) + len("</script>\n")      # the settings script
        i3 = html.index("</head>", i2)
        i4 = html.index('<input name="q" value="', i3) + len('<input name="q" value="')
        i5 = html.index('"', i4)
        i6 = html.index("</dialog>\n", i5) + len("</dialog>\n")
        i7 = html.rindex("\n<footer>")
        i8 = html.index("></script>\n", html.index('<script src="/static/ub.js', i7)) + len("></script>\n")
        i9 = html.rindex("\n</body>")
    except ValueError as exc:
        raise Shape(str(exc)) from None
    if not i0 <= i1 < i2 <= i3 < i4 <= i5 < i6 <= i7 < i8 <= i9:
        raise Shape("the pieces are out of order")
    shell = (html[:i0], html[i1:i2], html[i3:i4], html[i5:i6], html[i7:i8], html[i9:])
    return shell, {"t": html[i0:i1], "h": html[i2:i3], "q": html[i4:i5], "b": html[i6:i7],
                   "s": html[i8:i9]}


def compose(shell, rec: dict, q: str = "") -> str:
    """The page again, as offline-core.js compose() makes it."""
    return (shell[0] + rec["t"] + shell[1] + rec["h"] + shell[2] + q + shell[3] + rec["b"]
            + shell[4] + rec["s"] + shell[5])


def lift_rail(body: str, paper: int, sec: int) -> tuple[str, str]:
    """(the body with a NUL where its rail was, the rail with no section marked)."""
    found = list(RE_RAIL.finditer(body))
    if len(found) != 1:
        raise Shape(f"{paper}:{sec} has {len(found)} rails")
    m = found[0]
    here = f'<li class="here"><a href="/{paper}:{sec}">'
    if m.group(0).count(here) != 1:
        raise Shape(f"{paper}:{sec}'s rail marks it {m.group(0).count(here)} times")
    return (body[:m.start()] + RAIL + body[m.end():],
            m.group(0).replace(here, f'<li><a href="/{paper}:{sec}">'))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def universe(con: sqlite3.Connection) -> dict:
    """Every address the copy answers from what it stores, by kind."""
    papers: dict[int, list[int]] = {}
    for p, s in con.execute("SELECT paper_n, n FROM section ORDER BY paper_n, n"):
        papers.setdefault(p, []).append(s)
    letters = [r[0] for r in con.execute(
        "SELECT letter FROM index_entry WHERE scope='az' AND level=1"
        " GROUP BY letter ORDER BY letter='NUMBERS' DESC, letter")]
    slugs = {slug: letter for slug, letter in con.execute(
        "SELECT slug, letter FROM index_entry WHERE scope='az' AND level=1 AND slug IS NOT NULL"
        " ORDER BY ord")}
    # The headwords with a reading path, in the index's order, and in how many
    # chapters: with two or more it is read by theme too (app.py _reading_path).
    paths = {slug: n for slug, n in con.execute(
        "SELECT e.slug, r.n_chapters FROM reading_path r JOIN index_entry e ON e.id=r.root_id"
        " ORDER BY e.ord")}
    lasts = {f"{p}:{s}": n for p, s, n in con.execute(
        "SELECT paper_n, section_n, MAX(para_n) FROM paragraph GROUP BY paper_n, section_n")}
    misc = (["/", "/read", "/index", "/appendix"]
            + [f"/appendix/{r[0]}" for r in con.execute("SELECT letter FROM appendix ORDER BY letter")]
            + ["/lists", "/lists/1955"]
            + [f"/part/{r[0]}" for r in con.execute("SELECT n FROM part ORDER BY n")])
    return {"papers": papers, "letters": letters, "slugs": slugs, "paths": paths,
            "lasts": lasts, "misc": misc}


def _request(path: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": [],
                    "query_string": b"", "server": (site.HOST, 443), "scheme": "https",
                    "root_path": "", "app": site.app})


def build(con: sqlite3.Connection) -> tuple[dict, dict, dict]:
    """(chunks by name, the sha256 of every page the copy answers by its path,
    counts).  Each chunk is JSON-able; pack.py writes them."""
    u = universe(con)
    shell = None
    expect: dict[str, str] = {}

    def own(path: str, page: site.Page, status: int = 200) -> dict:
        nonlocal shell
        if page.status != status:
            raise Shape(f"{path} answered {page.status}")
        text = page.text
        sh, rec = cut(text)
        if shell is None:
            shell = sh
        elif sh != shell:
            diff = next(i for i in range(6) if sh[i] != shell[i])
            raise Shape(f"{path}'s shell differs from the first page's, in piece {diff}")
        if rec.pop("q") != "":
            raise Shape(f"{path} has a search in its search box")
        expect[path] = sha(text)
        return rec

    chunks: dict[str, dict] = {}

    # The book: a chunk to a paper, its sections and its rail.
    for p, secs in u["papers"].items():
        pages = site.get_many([(f"/{p}:{s}", "") for s in secs])
        out, rail = {}, None
        for s, page in zip(secs, pages):
            rec = own(f"/{p}:{s}", page)
            rec["b"], canon = lift_rail(rec["b"], p, s)
            if rail is None:
                rail = canon
            elif canon != rail:
                raise Shape(f"{p}:{s}'s rail differs from {p}:{secs[0]}'s but for its mark")
            out[str(s)] = rec
        sections = site.get(f"/rail/{p}")
        if sections.status != 200:
            raise Shape(f"/rail/{p} answered {sections.status}")
        chunks[f"paper-{p}"] = {"rail": rail, "railsecs": sections.text, "sections": out}

    # What the browser's voice reads (app.py speech(), build/speech.py), as the
    # server sends it, so that it reads offline too.  Apart from the pages,
    # twenty papers to a chunk: it moves only when the text does, and the pages
    # with every edit of the index.
    spoken = 0
    for p, secs in u["papers"].items():
        texts = site.get_many([(f"/speech/{p}:{s}", "") for s in secs])
        for s, got in zip(secs, texts):
            if got.status != 200 or not got.headers.get("content-type", "").startswith("application/json"):
                raise Shape(f"/speech/{p}:{s} answered {got.status}")
            expect[f"/speech/{p}:{s}"] = sha(got.text)
            chunks.setdefault(f"speech-{p // SPOKEN}", {})[f"{p}:{s}"] = got.text
            spoken += 1

    # The index: a chunk to a letter, its page and its headwords' pages.
    by_letter: dict[str, list[str]] = {}
    for slug, letter in u["slugs"].items():
        by_letter.setdefault(letter, []).append(slug)
    for letter in u["letters"]:
        slugs = by_letter.get(letter, [])
        pages = site.get_many([(f"/index/{letter}", "")] + [(f"/i/{s}", "") for s in slugs])
        chunks[f"index-{letter}"] = {
            "page": own(f"/index/{letter}", pages[0]),
            "heads": {s: own(f"/i/{s}", pg) for s, pg in zip(slugs, pages[1:])}}

    # The reading paths, each headword's in both its orders, a letter's in
    # chunks of about PATHS in the index's order.  The shell names each one's
    # chunk, so a path that grows moves only its own letter's chunks.
    where: dict[str, list] = {}
    for letter in u["letters"]:
        mine = [s for s in by_letter.get(letter, []) if s in u["paths"]]
        addrs = [(s, f"/i/{s}/read") for s in mine]
        addrs += [(s, f"/i/{s}/read/theme") for s in mine if u["paths"][s] >= 2]
        got: dict[str, dict] = {}
        for (s, path), pg in zip(addrs, site.get_many([(p, "") for _, p in addrs])):
            got.setdefault(s, {})[path] = own(path, pg)
        k, size, name = 0, 0, None
        for s in mine:
            n = sum(len(r["t"]) + len(r["h"]) + len(r["b"]) + len(r["s"]) for r in got[s].values())
            if n > PATHS:
                chunks[f"read-{s}"] = got[s]
                where[s] = [u["paths"][s], f"read-{s}"]
                continue
            if name is None or size + n > PATHS:
                name, size = f"read-{letter}-{k}", 0
                k += 1
                chunks[name] = {}
            chunks[name].update(got[s])
            size += n
            where[s] = [u["paths"][s], name]
    if where.keys() != u["paths"].keys():
        raise Shape("a headword's reading path is in no letter of the index")

    # Everything else that is a page of its own.
    chunks["misc"] = {"pages": {path: own(path, pg)
                                for path, pg in zip(u["misc"], site.get_many([(m, "") for m in u["misc"]]))}}

    # The not-found page, as the server draws it for any message and path, cut
    # around both; and the page that says an address is read online.
    nf = site.get(PROBE)
    nf_sh, nf_rec = cut(nf.text)
    if nf.status != 404 or nf_sh != shell:
        raise Shape(f"{PROBE} answered {nf.status}, or with another shell")
    body = nf_rec["b"]
    if body.count(PROBE_MSG) != 1 or body.count(PROBE) != 1 or body.index(PROBE_MSG) > body.index(PROBE):
        raise Shape("the not-found page does not name its message, then its path, once each")
    pre, rest = body.split(PROBE_MSG)
    mid, post = rest.split(PROBE)
    missing = {"t": nf_rec["t"], "h": nf_rec["h"], "s": nf_rec["s"], "b": [pre, mid, post]}

    from ubsite import app as A
    away_text = A.page(_request("/"), "offline.html", msg=Markup(RAIL)).body.decode("utf-8")
    away_sh, away_rec = cut(away_text)
    if away_sh != shell or away_rec["b"].count(RAIL) != 1:
        raise Shape("templates/offline.html does not cut as every page does")
    away = {"t": away_rec["t"], "h": away_rec["h"], "s": away_rec["s"],
            "b": away_rec["b"].split(RAIL)}

    # A search's page has its own title and body, and the search page's head
    # and scripts blocks, which search.html leaves as base.html has them.
    srch_sh, srch = cut(site.get("/search").text)
    if srch_sh != shell:
        raise Shape("the search page does not cut as every page does")

    chunks["shell"] = {
        "shell": list(shell), "missing": missing, "away": away,
        "search": {"h": srch["h"], "s": srch["s"]},
        "papers": {str(p): secs for p, secs in u["papers"].items()},
        "lasts": u["lasts"], "letters": u["letters"], "slugs": u["slugs"], "paths": where,
        "misc": u["misc"],
    }
    counts = {"sections": sum(len(s) for s in u["papers"].values()), "papers": len(u["papers"]),
              "headwords": len(u["slugs"]), "letters": len(u["letters"]), "misc": len(u["misc"]),
              "paths": sum(1 for p in expect if p.startswith("/i/") and "/read" in p),
              "pages": len(expect) - spoken, "spoken": spoken}
    return chunks, expect, counts
