"""Snapshot Alexander Alyuev's chart of the personalities: data/cosmology/chart.json.

    .venv/bin/python -m tools.cosmo.snapshot          (make cosmo-snapshot)
    .venv/bin/python -m tools.cosmo.snapshot --check  write nothing; fail if the snapshot is not this

His repository (config.cosmology()) holds the chart as three YAML files,
data/cosmology.yaml, the structure, and data/lang/<code>.yaml, the words in
each language, and an engine, src/engine.html, which draws it in the reader's
browser.  The data says what stands in which unit and in which row; it does
not say where a line runs.  The engine finds that as the page opens, by a
search over a 10 px grid that takes two and a half seconds, and keeps it in
the browser.

So this reads, at the commit `rev` names:

  the three YAML files, held to the keys it knows: a key it does not know
  fails, since his format is days old and a field read past is a thing of his
  the site would silently not show;

  and his own built page, dist/cosmology.html, opened unmodified in Chrome,
  once in each language, with the network closed to it: where every card and
  every unit stands, and every line as the corners it turns at.  The page's
  own data, window.COSMO, must be what the YAML makes by his tools/cosmo.py's
  rule, or the page was not built from that commit's data, and this stops.

A unit's title is an obstacle to the lines, as wide as the page's font drew
it, so the routes differ by language, and each language's are kept; the boxes
must not differ, and this stops if they do.

What it writes is the build's input (build/cosmo.py), a record to a line, so
that a refresh shows as a diff of what he changed.  It holds no date of its
own: the same commit makes the same file, on this machine, whose fonts the
titles were measured in.  Run it on purpose, review the diff, and commit it.
`make data` reads the snapshot, and never his repository, the network or a
browser.
"""

from __future__ import annotations

import copy
import json
import math
import sys

import yaml

from build import config
from build.readers import _io
from build.readers import cosmo as reader

CHROME = "/usr/bin/google-chrome"
# Where the page is served from, to the browser alone: a name no site can
# have, so that the page has an origin, and its storage, and nothing else.
PAGE = "https://cosmology.invalid/cosmology.html"

KNOWN = {
    "top": {"meta", "classes", "groups", "functions", "units", "persons", "links"},
    "meta": {"version", "base_language"},
    "key": {"color"},
    "unit": {"id", "color", "content", "width", "beside", "linkable", "refs"},
    "person": {"class", "origin", "groups", "refs", "func", "pair", "fuse"},
    "lang": {"language", "classes", "groups", "functions", "units", "persons"},
    "language": {"code", "name"},
    "lang unit": {"name", "desc"},
    "lang person": {"name", "aka", "desc", "terms", "serves", "there"},
}
LINK_TYPES = ("origin", "service", "ascent")

# What the page is asked for, once everything is drawn: the engine's own
# names, top-level in its script.  One renamed fails here, by name.
GEOMETRY = """() => ({
  data: window.COSMO,
  canvas: {w: W, h: H, card: [NW, NH], long: LONG},
  persons: persons.map(p => [p.id, p.x, p.y, p.unit]),
  ghosts: Object.values(GHOSTS).map(g => [g.id, g.x, g.y, g.unit]),
  units: UNITS.map(u => [u.id, u.x, u.y, u.w, u.h, u.lw, u.parent ? u.parent.id : null]),
  links: edges.map(e => [e.from, e.to, e.type, e.pts]),
})"""
ROUTED = "typeof edges !== 'undefined' && edges.length > 0 && edges.every(e => e.pts && e.pts.length > 1)"


class Unknown(Exception):
    """Something in his data this does not know how to read."""


def known(d: dict, kind: str, where: str) -> None:
    extra = sorted(set(d) - KNOWN[kind])
    if extra:
        raise Unknown(f"{where}: {', '.join(extra)}: a key this does not know."
                      f"  Read what it means in his repository, then teach tools/cosmo/snapshot.py"
                      f" and build/readers/cosmo.py to carry it")


def merged(d: dict, langs: dict[str, dict]) -> dict:
    """His tools/cosmo.py load(), without its `orphans`: the structure with
    each text put in as {language: words}.  What his build writes into the
    page as window.COSMO, and so what the page must hold."""
    d = copy.deepcopy(d)
    d.setdefault("meta", {})["languages"] = list(langs)

    def put(obj, sect, key, fields):
        for lg, t in langs.items():
            v = (t.get(sect) or {}).get(key)
            if isinstance(v, str):
                v = {"name": v}
            for f in fields:
                if v and v.get(f):
                    obj.setdefault(f, {})[lg] = v[f]

    for k, c in d.get("classes", {}).items():
        put(c, "classes", k, ["name"])
    for k, c in d.get("groups", {}).items():
        put(c, "groups", k, ["name"])
    for k, c in d.get("functions", {}).items():
        put(c, "functions", k, ["name"])

    def walk(us):
        for u in us:
            put(u, "units", u["id"], ["name", "desc"])
            walk([x for x in u.get("content", []) if isinstance(x, dict)])

    walk(d.get("units", []))
    for pid, p in d.get("persons", {}).items():
        put(p, "persons", pid, ["name", "aka", "desc", "terms", "serves", "there"])
    return d


def read(src: dict) -> tuple[dict, dict[str, dict], str]:
    """(the structure, each language's words by its code, the built page), at
    the commit, each held to the keys this knows."""
    repo, at = src["path"], src["commit"]
    d = yaml.safe_load(_io.read_at_rev(repo, "data/cosmology.yaml", at)) or {}
    known(d, "top", "cosmology.yaml")
    known(d.get("meta", {}), "meta", "cosmology.yaml meta")
    for sect in ("classes", "groups", "functions"):
        for k, v in d.get(sect, {}).items():
            known(v, "key", f"cosmology.yaml {sect}.{k}")

    def walk(us):
        for u in us:
            known(u, "unit", f"cosmology.yaml unit {u.get('id')}")
            walk([x for x in u.get("content", []) if isinstance(x, dict)])

    walk(d.get("units", []))
    for pid, p in d.get("persons", {}).items():
        known(p, "person", f"cosmology.yaml persons.{pid}")
    for l in d.get("links", []):
        if not 2 <= len(l) <= 3 or (len(l) == 3 and l[2] not in LINK_TYPES):
            raise Unknown(f"cosmology.yaml links: {l!r} is not [from, to] or [from, to, {'|'.join(LINK_TYPES)}]")

    langs: dict[str, dict] = {}
    for name in _io.list_at_rev(repo, "data/lang", at):
        if not name.endswith(".yaml"):
            raise Unknown(f"data/lang/{name}: not a language's .yaml")
        t = yaml.safe_load(_io.read_at_rev(repo, f"data/lang/{name}", at)) or {}
        known(t, "lang", f"lang/{name}")
        known(t.get("language", {}), "language", f"lang/{name} language")
        for k, v in (t.get("units") or {}).items():
            if not isinstance(v, str):
                known(v, "lang unit", f"lang/{name} units.{k}")
        for k, v in (t.get("persons") or {}).items():
            if not isinstance(v, str):
                known(v, "lang person", f"lang/{name} persons.{k}")
        langs[t["language"]["code"]] = t
    return d, langs, _io.read_at_rev(repo, "dist/cosmology.html", at)


def geometry(page: str, langs: list[str]) -> dict[str, dict]:
    """What his page makes of its data, in each language: {language: what
    GEOMETRY asks}.  The page is given to the browser from memory, at a name
    no site has, and every other request it makes is refused and counted."""
    from playwright.sync_api import sync_playwright

    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        try:
            for lg in langs:
                ctx = b.new_context(viewport={"width": 1500, "height": 900})
                asked, errors = [], []

                def serve(route, asked=asked):
                    if route.request.url.split("?")[0] == PAGE:
                        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=page)
                    else:
                        asked.append(route.request.url)
                        route.abort()

                ctx.route("**/*", serve)
                pg = ctx.new_page()
                pg.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                pg.goto(f"{PAGE}?lang={lg}", wait_until="load")
                pg.wait_for_function(ROUTED, timeout=120_000)
                out[lg] = pg.evaluate(GEOMETRY)
                ctx.close()
                if asked:
                    raise Unknown(f"his page asked the network for {asked[:3]}: it was one file with no"
                                  f" dependency when this was written")
                if errors:
                    raise Unknown(f"his page failed in Chrome ({lg}): {errors[:3]}")
        finally:
            b.close()
    return out


def by_language(obj: dict, field: str) -> dict:
    """{language: words} for one field of a merged object; aka a list in each."""
    v = obj.get(field) or {}
    if field == "aka":
        return {lg: ([x] if isinstance(x, str) else list(x)) for lg, x in v.items()}
    return dict(v)


def assemble(src: dict, d: dict, langs: dict[str, dict], geo: dict[str, dict]) -> dict:
    """The snapshot: his data whole, in his order, and what his page drew."""
    m = merged(d, langs)
    codes = list(langs)
    first = geo[codes[0]]
    for lg in codes:
        if json.loads(json.dumps(m)) != geo[lg]["data"]:
            theirs = geo[lg]["data"]
            diff = sorted(k for k in set(m) | set(theirs) if m.get(k) != theirs.get(k))
            raise Unknown(f"dist/cosmology.html at {src['commit'][:7]} does not hold that commit's data:"
                          f" it differs in {', '.join(diff)}.  He has not built it since his last edit"
                          f" (python tools/build.py there): wait for that commit, or name an earlier `rev`")
        for part in ("canvas", "persons", "ghosts"):
            if geo[lg][part] != first[part]:
                raise Unknown(f"the page places its {part} otherwise in {lg} than in {codes[0]}:"
                              f" the site draws one set of boxes for every language")
        if [u[:5] + u[6:] for u in geo[lg]["units"]] != [u[:5] + u[6:] for u in first["units"]]:
            raise Unknown(f"the page places its units otherwise in {lg} than in {codes[0]}")
        if [l[:3] for l in geo[lg]["links"]] != [[l[0], l[1], l[2] if len(l) > 2 else "origin"] for l in m["links"]]:
            raise Unknown(f"the page's lines ({lg}) are not the data's links, in their order")

    def key(sect):
        return [{"id": k, "color": v["color"], "name": by_language(v, "name")} for k, v in m.get(sect, {}).items()]

    box = {u[0]: u[1:5] for u in first["units"]}
    parent = {u[0]: u[6] for u in first["units"]}
    label = {lg: {u[0]: u[5] for u in geo[lg]["units"]} for lg in codes}
    at = {p[0]: p[1:3] for p in first["persons"] + first["ghosts"]}
    stands = {p[0]: p[3] for p in first["persons"] + first["ghosts"]}
    units, places = [], []

    def walk(us, up):
        for u in us:
            if parent.get(u["id"], "?") != up:
                raise Unknown(f"the page puts unit {u['id']} in {parent.get(u['id'])}, the data in {up}")
            rec = {"id": u["id"], "parent": up, "color": u["color"]}
            for k in ("width", "beside", "linkable"):
                if k in u:
                    rec[k] = u[k]
            rec["refs"] = [str(r) for r in u.get("refs", [])]
            rec["name"] = by_language(u, "name")
            if u.get("desc"):
                rec["desc"] = by_language(u, "desc")
            rec["box"] = box[u["id"]]
            # As wide as the page's font drew the title, in each language: what
            # the lines were kept clear of, to the nearest pixel above.
            rec["title"] = {lg: math.ceil(label[lg][u["id"]]) for lg in codes}
            units.append(rec)
            row = 0
            for item in u.get("content", []):
                if isinstance(item, dict):
                    walk([item], u["id"])
                    continue
                for col, pid in enumerate(item):
                    if stands.get(pid) != u["id"]:
                        raise Unknown(f"the page puts {pid} in {stands.get(pid)}, the data in {u['id']}")
                    places.append({"id": pid, "unit": u["id"], "row": row, "col": col, "at": at[pid]})
                row += 1

    walk(m["units"], None)
    persons = []
    for pid, p in m["persons"].items():
        rec = {"id": pid, "class": p["class"], "origin": p.get("origin", ""), "groups": p.get("groups", []),
               "func": p.get("func", []), "refs": [str(r) for r in p.get("refs", [])]}
        for k in ("pair", "fuse"):
            if p.get(k):
                rec[k] = p[k]
        for f in ("name", "aka", "desc", "serves", "there", "terms"):
            if p.get(f):
                rec[f] = by_language(p, f)
        persons.append(rec)
    links = [{"from": a, "to": b_, "type": t, "route": {lg: geo[lg]["links"][i][3] for lg in codes}}
             for i, (a, b_, t, _) in enumerate(first["links"])]
    for l in links:
        for lg, pts in l["route"].items():
            if not all(isinstance(v, int) for pt in pts for v in pt):
                raise Unknown(f"the line {l['from']} > {l['to']} ({lg}) turns off the grid: {pts}")
    return {
        "made": "tools/cosmo/snapshot.py (make cosmo-snapshot), from the repository below at this commit;"
                " never edit it by hand",
        "source": {"url": src["url"], "commit": src["commit"], "date": src["date"],
                   "version": str(m["meta"].get("version", "")),
                   "base_language": m["meta"].get("base_language", "en")},
        "languages": [{"code": lg, "name": langs[lg]["language"]["name"]} for lg in codes],
        "canvas": first["canvas"],
        "classes": key("classes"), "groups": key("groups"), "functions": key("functions"),
        "units": units, "persons": persons, "places": places, "links": links,
    }


def dump(doc: dict) -> str:
    """The snapshot as JSON, a record to a line."""
    def j(x):
        return json.dumps(x, ensure_ascii=False, separators=(", ", ": "))

    lines = ["{"]
    for i, (k, v) in enumerate(doc.items()):
        end = "" if i == len(doc) - 1 else ","
        if isinstance(v, list) and v and isinstance(v[0], dict):
            lines.append(f" {json.dumps(k)}: [")
            lines += [f"  {j(x)}{'' if n == len(v) - 1 else ','}" for n, x in enumerate(v)]
            lines.append(" ]" + end)
        else:
            lines.append(f" {json.dumps(k)}: {j(v)}{end}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    src = config.cosmology()
    if src["path"] is None or src["commit"] is None:
        print("cosmo-snapshot: his repository is not on this machine, or `rev` names no commit of it"
              " (config.cosmology()) -- nothing written", file=sys.stderr)
        return 1
    try:
        d, langs, page = read(src)
        doc = assemble(src, d, langs, geometry(page, list(langs)))
    except Unknown as exc:
        print(f"cosmo-snapshot: {exc} -- nothing written", file=sys.stderr)
        return 1
    text = dump(doc)
    # What the build will make of it, before it is written: its shape alone,
    # the gates that need the text being the build's.
    problems = reader.problems(json.loads(text))
    for p in problems[:20]:
        print(f"cosmo-snapshot: {p}", file=sys.stderr)
    if problems:
        print(f"cosmo-snapshot: {len(problems)} problems in his data as read -- nothing written", file=sys.stderr)
        return 1
    out = src["snapshot"]
    was = out.read_text(encoding="utf-8") if out.exists() else None
    n = {k: len(doc[k]) for k in ("units", "persons", "places", "links")}
    say = (f"{n['persons']} personalities in {n['units']} units, {n['places'] - n['persons']} of them drawn"
           f" again where they serve, {n['links']} lines; his {doc['source']['version']},"
           f" {src['commit'][:7]} of {src['date']}")
    rel = out.relative_to(config.ROOT)
    if "--check" in argv:
        print(f"{rel}: {'is' if was == text else 'is NOT'} what his repository makes now: {say}")
        return 0 if was == text else 1
    if was == text:
        print(f"{rel}: unchanged: {say}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{rel}: {len(text.encode('utf-8')):,} bytes: {say}\nReview the diff, then commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
