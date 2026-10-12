"""The rows, drawn: every document of the EPUB, as (name, XHTML).

What stands beside a paragraph and what a concept page lists come from
`ubsite/queries.py`, the site's own selection; this module only draws them,
with links mapped by `hrefs.Hrefs` into the package.

The order of the book is the printed volume's: the Foreword, the four parts
with their papers, the Index A-Z, Appendices A-F.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import sqlite3

import jinja2

from ubsite import queries

from . import hrefs as H

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

# An index letter's file is split, at a headword, once it passes this many
# characters of stored entry HTML -- about half what the file comes to, once
# its links are mapped and its lines wrapped.  Readers paginate a file as a
# whole, and older ones (Adobe's RMSDK) slow badly, or refuse, past 300 KB.
INDEX_SPLIT = 110_000

RE_FNREF = re.compile(r'<a class="fn" href="#(fn[0-9_]+)" id="(fnref[0-9_]+)"[^>]*></a>')
# A link out of the book, in the SRT Committee's reasons: the book is read
# offline, and every link in it lands inside it (check.py), so it is its words.
RE_OUT = re.compile(r'<a href="https?://[^"]*">(.*?)</a>', re.S)


@dataclasses.dataclass
class Doc:
    name: str                   # its file in OEBPS/
    title: str                  # for the nav and the NCX
    xhtml: str
    properties: str = ""        # manifest properties, e.g. "svg"
    linear: bool = True


def connect(path: pathlib.Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def env(links: H.Hrefs) -> jinja2.Environment:
    e = jinja2.Environment(
        loader=jinja2.FileSystemLoader(HERE / "templates"),
        autoescape=True, undefined=jinja2.StrictUndefined,
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    e.globals.update(entry_href=links.entry, appendix_href=links.appendix,
                     paper_href=links.paper, section_href=links.section)
    return e


def sources(con) -> dict:
    """The commits the database was built from, as the site's footer has them."""
    return {r["repo"]: {"commit": r["commit_id"], "short": r["commit_id"][:7],
                        "date": r["committed_at"], "dirty": bool(r["dirty"])}
            for r in con.execute("SELECT * FROM build_source")}


def mark_svg() -> str:
    """The site's mark, inline, in its light colours: e-ink draws it in grey.

    Its <style> becomes attributes on the paths it styles: readers honour a
    fill attribute everywhere and a style sheet inside an SVG only sometimes.
    """
    svg = (ROOT / "ubsite" / "static" / "favicon.svg").read_text()
    svg = re.sub(r"\s*<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"\s*@media.*?\}\s*\}", "", svg, flags=re.S)
    style = re.search(r"\s*<style>(.*?)</style>", svg, flags=re.S)
    rules = {cls: " ".join(f'{k.strip()}="{v.strip()}"' for k, v in
                           (d.split(":") for d in body.split(";") if d.strip()))
             for cls, body in re.findall(r"\.([\w-]+)\s*\{([^}]*)\}", style.group(1))}
    svg = svg.replace(style.group(0), "")
    svg = re.sub(r'class="([\w-]+)"', lambda m: rules[m.group(1)], svg)
    return svg.replace("<svg ", '<svg class="mark" aria-hidden="true" ', 1)


# -- the text ------------------------------------------------------------------

def _chip(links: H.Hrefs, c) -> dict:
    if c["rslug"]:
        return {"href": links.entry(c["rslug"], c["anchor"]), "label": None,
                "text": c["path"]}
    return {"href": links.appendix(c["scope"], c["anchor"]), "label": c["appendix"],
            "text": c["event"] or c["path"]}


def _offline(links: H.Hrefs, html: str) -> str:
    return links.rewrite(RE_OUT.sub(r"\1", html))


def paper(con, links: H.Hrefs, e: jinja2.Environment, p) -> Doc:
    secs = []
    for s in con.execute("SELECT * FROM section WHERE paper_n=? ORDER BY n", (p["n"],)):
        rows = queries.section(con, p["n"], s["n"])
        paras = []
        for q in rows["paras"]:
            # As on the site: the 1955 reading as the press gives it, and the SRT
            # Committee's decision and reasons, and the note it refers to.
            notes = [{"id": f"fn{q['paper_n']}_{q['section_n']}_{q['para_n']}_{f['ord']}",
                      "back": f"fnref{q['paper_n']}_{q['section_n']}_{q['para_n']}_{f['ord']}",
                      "then": f["html"],
                      "verdict": f["verdict"], "why": _offline(links, f["srt_why"] or ""),
                      "see_ref": f["see_ref"], "see_href": f["see_ref"] and links.site(f"/{f['see_ref']}"),
                      "see_verdict": f["see_verdict"],
                      "see_why": f["see_why"] and _offline(links, f["see_why"])}
                     for f in rows["notes"].get(q["id"], [])]
            html, n = RE_FNREF.subn(
                r'<a class="fn" epub:type="noteref" href="#\1" id="\2">*</a>', q["html"])
            if n != len(notes) or q["html"].count('class="fn"') != n:
                raise ValueError(f"{q['ref']}: {n} note markers for {len(notes)} notes")
            paras.append({"id": H.para_id(q["paper_n"], q["section_n"], q["para_n"]),
                          "ref": q["ref"], "pc": bool(q["gap_before"]), "head": bool(q["heading"]),
                          "stars": q["sep_before"],
                          "html": html,
                          "chips": [_chip(links, c) for c in rows["citers"].get(q["id"], [])],
                          "notes": notes})
        secs.append({"id": H.section_id(p["n"], s["n"]), "n": s["n"],
                     "combined_with": s["combined_with"], "title_html": s["title_html"],
                     "blanket": [_chip(links, c) for c in rows["blanket"]],
                     "paras": paras})
    title = p["title"] if p["n"] == 0 else f"{p['n']}. {p['title']}"
    return Doc(H.paper_file(p["n"]), title,
               e.get_template("paper.xhtml").render(paper=p, sections=secs))


def part(e: jinja2.Environment, r) -> Doc:
    return Doc(f"part{r['n']}.xhtml", f"Part {ROMAN[r['n']]}. {r['title']}",
               e.get_template("part.xhtml").render(part=r, lines=r["title_lines"].split("\n")))


# -- the index -------------------------------------------------------------------

def index_layout(con, links: H.Hrefs) -> list[dict]:
    """Which file each headword goes in: one per letter, split when long.

    Decided before anything is drawn, because the text's chips link into it.
    Each file is {name, letter, part, heads: [root rows]}.
    """
    files: list[dict] = []
    size = 0
    for r in con.execute(
            "SELECT r.*, (SELECT SUM(LENGTH(text_html)) FROM index_entry e"
            "             WHERE e.root_id=r.id) AS weight"
            " FROM index_entry r WHERE r.scope='az' AND r.level=1"
            " ORDER BY r.letter='NUMBERS' DESC, r.letter, r.ord"):
        if not files or files[-1]["letter"] != r["letter"]:
            files.append({"letter": r["letter"], "part": 1, "heads": []})
            size = 0
        elif size > INDEX_SPLIT:
            files.append({"letter": r["letter"], "part": files[-1]["part"] + 1, "heads": []})
            size = 0
        files[-1]["heads"].append(r)
        size += r["weight"]
    for f in files:
        stem = "numbers" if f["letter"] == "NUMBERS" else f["letter"]
        f["name"] = f"index-{stem}.xhtml" if f["part"] == 1 else f"index-{stem}-{f['part']}.xhtml"
        for r in f["heads"]:
            links.index_file[r["slug"]] = f["name"]
    return files


def index_file(con, links: H.Hrefs, e: jinja2.Environment, f: dict) -> Doc:
    heads = []
    for r in f["heads"]:
        c = queries.concept(con, r["id"])
        tree = [{"id": t["anchor"], "level": t["level"], "html": links.rewrite(t["text_html"])}
                for t in c["tree"]]
        if not tree or tree[0]["id"] != r["anchor"]:
            raise ValueError(f"{r['headword']}: its tree does not begin with itself")
        heads.append({
            "head": tree[0], "tree": tree[1:],
            "listed": [{"href": links.appendix(x["scope"], x["anchor"]),
                        "text": f"Appendix {x['scope']}, {x['title']}"} for x in c["listed"]],
            "xrefs": [{"kind": "See also" if x["kind"] == "seealso" else "See",
                       "target": x["target"],
                       "href": links.entry(x["slug"]) if x["slug"] else None}
                      for x in c["xrefs"]],
            "near": [{"href": links.entry(n["slug"]), "text": n["headword"]} for n in c["near"]],
        })
    label = "Numbers" if f["letter"] == "NUMBERS" else f["letter"]
    title = f"Index: {label}" + (f" ({f['part']})" if f["part"] > 1 else "")
    return Doc(f["name"], title, e.get_template("index.xhtml").render(
        label=label, first=f["part"] == 1, title=title, heads=heads))


# -- the appendices ----------------------------------------------------------------

def appendix(con, links: H.Hrefs, e: jinja2.Environment, a) -> Doc:
    name, title = H.appendix_file(a["letter"]), f"Appendix {a['letter']}. {a['title']}"
    if a["letter"] == "A":
        years, bands = queries.chronology(con)
        first_of = {b["id"]: b["name"] for b in bands}

        def ev(r):
            return {"id": r["anchor"], "html": links.rewrite(r["text_html"])}
        ys = [{"id": y["id"], "label": y["label"], "band": first_of.get(y["id"]),
               "rows": [{"event": ev(i["event"])} if "event" in i else
                         {"month": i["month"], "events": [ev(r) for r in i["events"]]}
                         for i in y["items"]]} for y in years]
        return Doc(name, title, e.get_template("chronology.xhtml").render(app=a, years=ys))
    rows = [{"id": r["anchor"], "html": links.rewrite(r["text_html"])}
            for r in queries.appendix_rows(con, a["letter"])]
    return Doc(name, title, e.get_template("appendix.xhtml").render(app=a, rows=rows))


# -- the whole -------------------------------------------------------------------

def documents(con) -> tuple[list[Doc], dict]:
    """Every content document in reading order, and what the package needs."""
    links = H.Hrefs(con)
    e = env(links)
    layout = index_layout(con, links)
    papers = con.execute("SELECT * FROM paper ORDER BY n").fetchall()
    parts = con.execute("SELECT * FROM part ORDER BY n").fetchall()
    apps = queries.appendices(con)
    src = sources(con)
    letters = [f for f in layout if f["part"] == 1]

    front = [
        Doc("cover.xhtml", "Cover", e.get_template("cover.xhtml").render()),
        Doc("title.xhtml", "Title page", e.get_template("title.xhtml").render(
            mark=mark_svg(), src=src), properties="svg"),
    ]
    # No contents page: the reader's own outline (nav.xhtml) reaches every
    # section in two taps, and a page listing 197 papers is pages of paper
    # (Tigran, 2026-10-10).
    text = []
    for p in papers:
        # A part's divider stands before its first paper, as in print.
        for r in parts:
            if r["first_paper"] == p["n"]:
                text.append(part(e, r))
        text.append(paper(con, links, e, p))
    index = [index_file(con, links, e, f) for f in layout]
    appendices = [appendix(con, links, e, a) for a in apps]
    ofl = (ROOT / "ubsite" / "static" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    back = [Doc("ofl.xhtml", "SIL Open Font License", e.get_template("ofl.xhtml").render(
        text=ofl), linear=False)]

    # The navigation: Foreword, parts > papers > sections, the index, appendices.
    sections = {}
    for s in con.execute("SELECT paper_n, n, title, combined_with FROM section WHERE n > 0"
                         " ORDER BY paper_n, n"):
        n = f"{s['n']} and {s['combined_with']}" if s["combined_with"] else f"{s['n']}"
        sections.setdefault(s["paper_n"], []).append(
            {"href": links.section(s["paper_n"], s["n"]), "label": f"{n}. {s['title']}"})
    toc = []
    for d in text:
        if d.name.startswith("part"):
            toc.append({"href": d.name, "label": d.title, "kids": []})
        else:
            n = int(d.name[1:4])
            node = {"href": d.name, "label": d.title, "kids": [
                {"href": s["href"], "label": s["label"], "kids": []} for s in sections.get(n, [])]}
            (toc[-1]["kids"] if n and toc[-1]["href"].startswith("part") else toc).append(node)
    toc.append({"href": index[0].name, "label": "Index", "kids": [
        {"href": f["name"], "label": "Numbers" if f["letter"] == "NUMBERS" else f["letter"],
         "kids": []} for f in letters]})
    toc.append({"href": appendices[0].name, "label": "Appendices", "kids": [
        {"href": d.name, "label": d.title, "kids": []} for d in appendices]})

    meta = {"toc": toc, "sources": src,
            "landmarks": [("cover", "cover.xhtml", "Cover"),
                          ("bodymatter", H.paper_file(0), "Foreword"),
                          ("index", index[0].name, "Index")]}
    return front + text + index + appendices + back, meta
