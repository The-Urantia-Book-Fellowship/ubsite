"""data/cosmology/chart.json: Alexander Alyuev's chart of the personalities,
as tools/cosmo/snapshot.py took it from his repository
(config.cosmology()).

A snapshot inside this project, not a master: the build reads it and never
his repository.  `problems()` is everything about it that can be held to
without the book: that its ids are what it says they are, that everything
stands where his page drew it, and that every line runs from the one to the
other.  build/cosmo.py holds it to the text and the index.

A place is a card: a personality where it has its origin, `father`, or again
where it serves, `~michael`, a shadow in his words.  A line's end is a place,
or a unit that says it may be one (`linkable`: the Trinity, the Corps of the
Finality).
"""

from __future__ import annotations

import json
import pathlib
import re

RE_REF = re.compile(r"(\d+)(?::(\d+))?")
RE_ID = re.compile(r"[a-z][a-z0-9]*")
RE_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
LINK_TYPES = ("origin", "service", "ascent")
# The site's own languages (ubsite/l10n.py): a name in each, or the page would
# have a card with no words on it for one of its readers.
LANGS = ("en", "ru")
FIELDS = ("name", "aka", "desc", "serves", "there", "terms")
TOP = ("made", "source", "languages", "canvas", "classes", "groups", "functions",
       "units", "persons", "places", "links")


def read(path: pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def rects(doc: dict) -> dict[str, tuple[int, int, int, int]]:
    """Where everything stands, (x, y, w, h) by id: each unit's box, and each
    place's card."""
    cw, ch = doc["canvas"]["card"]
    out = {u["id"]: tuple(u["box"]) for u in doc["units"]}
    out.update({p["id"]: (p["at"][0], p["at"][1], cw, ch) for p in doc["places"]})
    return out


def _inside(a, b, slack: int = 0) -> bool:
    return (a[0] >= b[0] - slack and a[1] >= b[1] - slack
            and a[0] + a[2] <= b[0] + b[2] + slack and a[1] + a[3] <= b[1] + b[3] + slack)


def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _on_edge(pt, r, slack: int = 1) -> bool:
    """On the rectangle's border, to a pixel."""
    x, y = pt
    if not (r[0] - slack <= x <= r[0] + r[2] + slack and r[1] - slack <= y <= r[1] + r[3] + slack):
        return False
    return (abs(x - r[0]) <= slack or abs(x - r[0] - r[2]) <= slack
            or abs(y - r[1]) <= slack or abs(y - r[1] - r[3]) <= slack)


def _crosses(a, b, r) -> bool:
    """Whether the segment a-b, level or upright, passes through the inside
    of rectangle r."""
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    return x0 < r[0] + r[2] and x1 > r[0] and y0 < r[1] + r[3] and y1 > r[1]


def problems(doc: dict) -> list[str]:
    """What is wrong with a snapshot's shape, each as a line; none if nothing."""
    out: list[str] = []
    missing = [k for k in TOP if k not in doc]
    extra = [k for k in doc if k not in TOP]
    if missing or extra:
        return [f"the snapshot lacks {missing} and has {extra}, which this does not know: made by another"
                f" version of tools/cosmo/snapshot.py"]
    if not re.fullmatch(r"[0-9a-f]{40}", doc["source"].get("commit") or ""):
        out.append("source: no commit")
    codes = [l["code"] for l in doc["languages"]]
    for lg in LANGS:
        if lg not in codes:
            out.append(f"languages: no {lg}, which the site speaks")
    canvas = doc["canvas"]
    if not all(isinstance(canvas.get(k), int) and canvas[k] > 0 for k in ("w", "h", "long")) \
            or not (isinstance(canvas.get("card"), list) and len(canvas["card"]) == 2):
        return out + [f"canvas: {canvas!r}"]

    def texts(kind, rec, need=("name",)):
        for f in need:
            for lg in LANGS:
                if not str((rec.get(f) or {}).get(lg) or "").strip():
                    out.append(f"{kind} {rec['id']}: no {f} in {lg}")
        for f in FIELDS:
            for lg, v in (rec.get(f) or {}).items():
                for w in (v if isinstance(v, list) else [v]):
                    if not isinstance(w, str) or w != w.strip() or "\n" in w or not w:
                        out.append(f"{kind} {rec['id']}: {f} in {lg} is {w!r}")

    keys = {}
    for sect in ("classes", "groups", "functions"):
        keys[sect] = [k["id"] for k in doc[sect]]
        if len(set(keys[sect])) != len(keys[sect]):
            out.append(f"{sect}: an id twice")
        for k in doc[sect]:
            if not RE_COLOR.fullmatch(k.get("color") or ""):
                out.append(f"{sect} {k['id']}: colour {k.get('color')!r}")
            texts(sect, k)

    units = {u["id"]: u for u in doc["units"]}
    persons = {p["id"]: p for p in doc["persons"]}
    ids = [u["id"] for u in doc["units"]] + [p["id"] for p in doc["persons"]]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        out.append(f"id {i} twice, among the units and the personalities")
    for i in ids:
        if not RE_ID.fullmatch(i):
            out.append(f"id {i!r}: not a word of small letters and digits, which an address can end in")
    seen: set[str] = set()
    for u in doc["units"]:
        if u["parent"] is not None and u["parent"] not in seen:
            out.append(f"unit {u['id']}: its parent {u['parent']!r} does not stand before it")
        seen.add(u["id"])
        if not RE_COLOR.fullmatch(u.get("color") or ""):
            out.append(f"unit {u['id']}: colour {u.get('color')!r}")
        if not (isinstance(u.get("box"), list) and len(u["box"]) == 4 and all(isinstance(v, int) for v in u["box"])):
            out.append(f"unit {u['id']}: box {u.get('box')!r}")
        for lg in LANGS:
            if not isinstance((u.get("title") or {}).get(lg), int):
                out.append(f"unit {u['id']}: no width of its title in {lg}")
        texts("unit", u)
    for p in doc["persons"]:
        if p["class"] not in keys["classes"]:
            out.append(f"{p['id']}: class {p['class']!r} is none of the classes")
        for g in p["groups"]:
            if g not in keys["groups"]:
                out.append(f"{p['id']}: group {g!r} is none of the groups")
        if not p["groups"]:
            out.append(f"{p['id']}: in no group, and its sign is drawn by its first")
        for g in p["func"]:
            if g not in keys["functions"]:
                out.append(f"{p['id']}: function {g!r} is none of the functions")
        if not re.fullmatch(r"[ATFSDE]*", p["origin"]):
            out.append(f"{p['id']}: origin {p['origin']!r}")
        if p.get("pair") and (persons.get(p["pair"]) or {}).get("pair") != p["id"]:
            out.append(f"{p['id']}: its pair {p['pair']!r} does not name it back")
        for f in p.get("fuse", []):
            if f not in persons:
                out.append(f"{p['id']}: fuses {f!r}, which is no personality")
        texts("personality", p)
    for kind, recs in (("unit", doc["units"]), ("personality", doc["persons"])):
        for r in recs:
            for ref in r["refs"]:
                if not RE_REF.fullmatch(ref):
                    out.append(f"{kind} {r['id']}: reference {ref!r} is not a paper or paper:section")

    if out:
        return out          # what follows reads boxes and ids as sound

    where = rects(doc)
    placed: dict[str, dict] = {}
    for pl in doc["places"]:
        pid = pl["id"]
        if pid in placed:
            out.append(f"{pid} stands twice")
        placed[pid] = pl
        if pid.lstrip("~") not in persons:
            out.append(f"{pid} stands in {pl['unit']}, and is no personality")
        if pl["unit"] not in units:
            out.append(f"{pid} stands in {pl['unit']!r}, which is no unit")
    for pid in persons:
        if pid not in placed:
            out.append(f"{pid} stands nowhere")
    for pid, p in persons.items():
        if p.get("serves") and "~" + pid not in placed:
            out.append(f"{pid}: said to serve somewhere, and drawn nowhere but at its origin")
    if out:
        return out

    whole = (0, 0, canvas["w"], canvas["h"])
    for u in doc["units"]:
        if not _inside(where[u["id"]], where[u["parent"]] if u["parent"] else whole):
            out.append(f"unit {u['id']} is not inside {u['parent'] or 'the canvas'}")
    for a in doc["units"]:
        for b in doc["units"]:
            if a["id"] < b["id"] and a["parent"] == b["parent"] and _overlap(where[a["id"]], where[b["id"]]):
                out.append(f"units {a['id']} and {b['id']} overlap")
    cards = list(placed)
    for pid in cards:
        if not _inside(where[pid], where[placed[pid]["unit"]]):
            out.append(f"{pid} is not inside its unit, {placed[pid]['unit']}")
        # Nor in a unit within it: a card stands in its own unit's rows.
        for u in doc["units"]:
            if u["parent"] == placed[pid]["unit"] and _overlap(where[pid], where[u["id"]]):
                out.append(f"{pid} stands over unit {u['id']}")
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            if _overlap(where[a], where[b]):
                out.append(f"{a} and {b} overlap")

    for n, l in enumerate(doc["links"]):
        name = f"line {n}, {l['from']} > {l['to']}"
        if l["type"] not in LINK_TYPES:
            out.append(f"{name}: type {l['type']!r}")
        bad = False
        for end in (l["from"], l["to"]):
            if not (end in placed or (end in units and units[end].get("linkable"))):
                out.append(f"{name}: {end!r} is no card, and no unit a line may end at")
                bad = True
        if bad:
            continue
        for lg in LANGS:
            pts = (l.get("route") or {}).get(lg)
            if not pts or len(pts) < 2:
                out.append(f"{name}: no route in {lg}")
                continue
            if any(a[0] != b[0] and a[1] != b[1] for a, b in zip(pts, pts[1:])):
                out.append(f"{name} ({lg}): his router found it no way, and drew it straight across")
                continue
            if not _on_edge(pts[0], where[l["from"]]):
                out.append(f"{name} ({lg}): begins at {pts[0]}, off the edge of {l['from']}")
            if not _on_edge(pts[-1], where[l["to"]]):
                out.append(f"{name} ({lg}): ends at {pts[-1]}, off the edge of {l['to']}")
            for pid in cards:
                if pid in (l["from"], l["to"]):
                    continue
                if any(_crosses(a, b, where[pid]) for a, b in zip(pts, pts[1:])):
                    out.append(f"{name} ({lg}): runs through {pid}")
    return out
