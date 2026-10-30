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

The whole paper's page, /15 (templates/paper.html, Settings' Whole paper), is
its sections' text once more, under one head: each section's piece of it, the
inner of its <section id="15:3"> (templates/_text.html textof), is byte for
byte the piece in the section's own page, so the whole page is kept as its
own text with a hole where each section's text goes, and the worker fills
the holes from the section pages it holds (holes(), offline-core.js whole()).
Stored whole, the 197 pages would have added a tenth to the copy.

A headword's reading path (/i/<slug>/read, and /read/theme) is a page like any
other, and the largest part of the copy: 132 MB of the 191 unpacked, though
it is made of paragraphs the copy has already, because each paragraph comes
with its captions and the folds around it.

The translations beside the text are each a download of their own (ROADMAP
item 15), which a reader chooses in Settings' Offline tab: a section's
fragment, /tr/<paper>:<section>, holds every translation it has, so each
translation's share of it is kept apart, its headings and its paragraphs
(app.py tr_pieces), twenty papers to a chunk, and the worker joins the shares
of those the reader keeps inside the fragment's frame, which the shell holds.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3

from markupsafe import Markup
from starlette.requests import Request

from ubsite import l10n

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

# The page about the text API names the address it is read at (app.py
# api_docs: request.base_url), and the copy is one for every host.  So it is
# kept as asked at API_HOST, a name no site can have, and the worker puts its
# own address where API_BASE stands (offline-core.js knows it too).
API_HOST = "ubsite.offline.invalid"
API_BASE = f"https://{API_HOST}/"

# The not-found page's words, to cut it at: its message, as the page draws it
# in both languages (ubsite/l10n.py), and the path it names.
PROBE = "/offline-missing-probe"
NOPAGE = "There is no page at this address."


class Shape(Exception):
    """A page that does not cut as base.html says every page does."""


def cut(html: str) -> tuple[tuple[str, ...], dict]:
    """(the shell's six pieces, the page's own) for one rendered page."""
    # The title piece begins inside its tag, so that it carries the title's
    # Russian, data-ru, where it has one (base.html): ` data-ru="…">Lists`.
    try:
        i0 = html.index("<title") + len("<title")
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


def lift_rail_whole(body: str, paper: int, rail: str) -> str:
    """The whole paper's body (paper.html) with a NUL where its rail was: the
    rail is its sections' with no section marked, which the paper's chunk
    keeps."""
    found = list(RE_RAIL.finditer(body))
    if len(found) != 1:
        raise Shape(f"/{paper} has {len(found)} rails")
    m = found[0]
    if m.group(0) != rail:
        raise Shape(f"/{paper}'s rail is not its sections' with no section marked")
    return body[:m.start()] + RAIL + body[m.end():]


def inner(body: str, paper: int, sec: int) -> tuple[int, int]:
    """Where section paper:sec's text stands in a body (templates/_text.html
    textof): the inner of its <section id>, from the end of the open tag to
    the first </section> after it (the grid holds no section; the notes'
    come later), as offsets."""
    tag = f'<section id="{paper}:{sec}"'
    if body.count(tag) != 1:
        raise Shape(f"{paper}:{sec}'s text stands {body.count(tag)} times in its page")
    i = body.index(">", body.index(tag)) + 1
    return i, body.index("</section>", i)


def holes(whole: str, sections: dict[str, dict], paper: int, secs: list[int]) -> list:
    """The whole paper's body as its own text and holes: each section's text,
    which the copy holds in the section's own page, replaced by [s], and each
    section's record given `sec`, where that text stands in its body, so that
    the worker can fill the hole (offline-core.js whole()).  The sections in
    the order of the book, each found once."""
    parts: list = []
    rest = whole
    for s in secs:
        rec = sections[str(s)]
        i, j = inner(rec["b"], paper, s)
        rec["sec"] = [i, j]
        piece = rec["b"][i:j]
        if rest.count(piece) != 1:
            raise Shape(f"{paper}:{s}'s text stands {rest.count(piece)} times in /{paper}")
        at = rest.index(piece)
        parts += [rest[:at], [s]]
        rest = rest[at + len(piece):]
    parts.append(rest)
    return parts


def join_whole(parts: list, sections: dict[str, dict]) -> str:
    """The whole paper's body again, as offline-core.js whole() makes it."""
    return "".join(x if isinstance(x, str) else sections[str(x[0])]["b"][slice(*sections[str(x[0])]["sec"])]
                   for x in parts)


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
            + ["/lists", "/lists/1955", "/lists/notes", "/lists/bibliography", "/changelog", "/api"]
            + [f"/part/{r[0]}" for r in con.execute("SELECT n FROM part ORDER BY n")])
    # The papers the quiz has questions on (build/quiz.py), each a page /quiz/N.
    quiz = [n for (n,) in con.execute("SELECT paper_n FROM quiz_paper ORDER BY paper_n")]
    return {"papers": papers, "letters": letters, "slugs": slugs, "paths": paths,
            "lasts": lasts, "misc": misc, "quiz": quiz}


def _request(path: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": [],
                    "query_string": b"", "server": (site.HOST, 443), "scheme": "https",
                    "root_path": "", "app": site.app})


def build(con: sqlite3.Connection) -> tuple[dict, dict, dict, dict]:
    """(chunks by name, the sha256 of every page the copy answers by its path,
    counts, each translation's chunks by name, in Settings' order).  Each chunk
    is JSON-able; pack.py writes them."""
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
        # The whole paper's page, its own text with a hole for each section's,
        # and held to the page the server sends once joined again.
        wpage = site.get(f"/{p}")
        wrec = own(f"/{p}", wpage)
        wrec["b"] = holes(lift_rail_whole(wrec["b"], p, rail), out, p, secs)
        if compose(shell, {**wrec, "b": join_whole(wrec["b"], out).replace(RAIL, rail, 1)}) != wpage.text:
            raise Shape(f"/{p} is not its own text with its sections' pieces in their holes")
        chunks[f"paper-{p}"] = {"rail": rail, "railsecs": sections.text, "sections": out, "whole": wrec}

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

    # The translations, each apart: a section's fragment as the server sends it
    # is the frame around every translation's headings, then every one's
    # paragraphs, in Settings' order, and each translation keeps its two
    # pieces of it, twenty papers to a chunk, as the spoken text is kept.
    from ubsite import app as A
    named = {x["key"]: x for x in A.translations()}
    order = list(named)
    trs: dict[str, dict] = {k: {} for k in order}
    tr_secs: dict[str, dict] = {k: {} for k in order}
    fragments = 0
    for p, secs in u["papers"].items():
        frags = site.get_many([(f"/tr/{p}:{s}", "") for s in secs])
        for s, got in zip(secs, frags):
            parts = A.tr_pieces(p, s)
            if not parts:
                if got.status != 404:
                    raise Shape(f"/tr/{p}:{s} answered {got.status}, with no translation of it")
                continue
            if list(parts) != [k for k in order if k in parts]:
                raise Shape(f"/tr/{p}:{s}'s translations are not in Settings' order")
            joined = (A.TR_FRAME[0] + "".join(h for h, _ in parts.values())
                      + "".join(r for _, r in parts.values()) + A.TR_FRAME[1])
            if got.status != 200 or joined != got.text:
                raise Shape(f"/tr/{p}:{s} is not its translations' pieces joined in their frame")
            expect[f"/tr/{p}:{s}"] = sha(got.text)
            fragments += 1
            for k, piece in parts.items():
                trs[k].setdefault(f"tr-{k}-{p // SPOKEN}", {})[f"{p}:{s}"] = list(piece)
                tr_secs[k].setdefault(str(p), []).append(s)

    # What the browser's voice reads of each (app.py speech_tr), as the server
    # sends it, in its own download, twenty papers to a chunk as its pieces of
    # /tr/ are, so that a translation kept can be heard offline (Tigran,
    # 2026-10-27), as the English is.
    tr_spoken = 0
    for k in order:
        addrs = [f"/speech/{k}/{p}:{s}" for p, secs in tr_secs[k].items() for s in secs]
        for path, got in zip(addrs, site.get_many([(a, "") for a in addrs])):
            if got.status != 200 or not got.headers.get("content-type", "").startswith("application/json"):
                raise Shape(f"{path} answered {got.status}")
            at = path.rsplit("/", 1)[1]
            expect[path] = sha(got.text)
            trs[k].setdefault(f"tr-{k}-speech-{int(at.split(':')[0]) // SPOKEN}", {})[at] = got.text
            tr_spoken += 1

    # Each one's own contents, which the left rail shows when a reader chooses
    # it (app.py toc_of): /rail/<key> as the server sends it, a chunk of its
    # own in its download, so that a translation not kept leaves the rail in
    # English offline.
    tocs = 0
    for k in order:
        if not trs[k]:
            continue
        got = site.get(f"/rail/{k}")
        if got.status != 200:
            raise Shape(f"/rail/{k} answered {got.status}")
        trs[k][f"tr-{k}-toc"] = {"toc": got.text}
        expect[f"/rail/{k}"] = sha(got.text)
        tocs += 1

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
    # The quiz (app.py quiz_page, quiz_paper_page): /quiz, with all its
    # questions, and each paper's, a chunk of their own, which moves only when
    # the quiz does, a reviewed paper's references with it; not misc, which
    # /changelog moves with every release.
    # Every quiz page names the board's site, the same on every host and in this
    # one copy: never a test's (UB_BOARD).
    from ubsite import board
    if board.BOARD != board.DEFAULT:
        raise Shape(f"UB_BOARD is {board.BOARD}: the copy's quiz pages would send to it")
    qpaths = ["/quiz"] + [f"/quiz/{n}" for n in u["quiz"]]
    chunks["quiz"] = {"pages": {path: own(path, pg)
                                for path, pg in zip(qpaths, site.get_many([(m, "") for m in qpaths]))}}
    # /api, asked again at API_HOST: the page at HOST but for its address, or the
    # address is not all of it that depends on the host.  The gate holds what
    # the worker makes of it to the page at HOST.
    api = site.get("/api", host=API_HOST)
    api_sh, api_rec = cut(api.text)
    if (api.status != 200 or api_sh != shell or api_rec.pop("q") != ""
            or api.text.replace(API_BASE, f"https://{site.HOST}/") != site.get("/api").text):
        raise Shape("/api depends on the host it is asked at other than by its address")
    chunks["misc"]["pages"]["/api"] = api_rec

    # The not-found page, as the server draws it for any message and path, cut
    # around both; and the page that says an address is read online.
    nf = site.get(PROBE)
    nf_sh, nf_rec = cut(nf.text)
    if nf.status != 404 or nf_sh != shell:
        raise Shape(f"{PROBE} answered {nf.status}, or with another shell")
    body, probe_msg = nf_rec["b"], str(l10n.t(NOPAGE))
    if body.count(probe_msg) != 1 or body.count(PROBE) != 1 or body.index(probe_msg) > body.index(PROBE):
        raise Shape("the not-found page does not name its message, then its path, once each")
    pre, rest = body.split(probe_msg)
    mid, post = rest.split(PROBE)
    missing = {"t": nf_rec["t"], "h": nf_rec["h"], "s": nf_rec["s"], "b": [pre, mid, post]}

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
        "misc": u["misc"], "quiz": u["quiz"],
        # What /tr/ is made of offline: the fragment's two ends, and each
        # translation in Settings' order with the sections it has, by paper,
        # and its names and language, which its list among a search's results
        # is headed by (search.html), its short name as HTML.
        "tr": {"frame": list(A.TR_FRAME),
               "order": [{"key": k, "secs": tr_secs[k], "title": named[k]["title"],
                          "label": str(named[k]["label"]), "lang": named[k]["lang"], "speech": True}
                         for k in order if trs[k]]},
    }
    counts = {"sections": sum(len(s) for s in u["papers"].values()), "papers": len(u["papers"]),
              "whole": len(u["papers"]),
              "headwords": len(u["slugs"]), "letters": len(u["letters"]), "misc": len(u["misc"]),
              "paths": sum(1 for p in expect if p.startswith("/i/") and "/read" in p),
              "pages": len(expect) - spoken - fragments - tocs - tr_spoken, "spoken": spoken,
              "fragments": fragments, "tr_spoken": tr_spoken}
    return chunks, expect, counts, {k: c for k, c in trs.items() if c}
