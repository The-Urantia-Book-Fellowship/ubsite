"""The chart of the personalities: data/cosmology/chart.json into the database.

Alexander Alyuev's "Cosmology of Personalities in the Urantia Book" (Tigran,
2026-11-13; config.cosmology()): the orders of personalities, each a
card where it has its origin, in the units of the universe from Paradise to
Urantia, and the lines of origin, service and ascent between them.  His
repository draws it in the reader's browser; here it is data like the rest,
drawn by the site (ubsite/templates/cosmology.html), so that a card's sources
are links into the text, its name a link into the index, and the page speaks
the reader's language and is in the offline copy.

The build reads the snapshot tools/cosmo/snapshot.py made of his repository,
never the repository, and holds it to four things, each a hard failure:

  its shape (readers/cosmo.py problems()): ids, places, boxes, and every line
  from the edge of one card to the edge of another through no third;

  the book: every reference of his is a paper or a section there is;

  the words: every name, and every other name, is in the text, the English in
  the press's and the Russian in the translation it says it follows (TERMS),
  by his own validator's rule, any ending allowed; the names that are his own
  wording and not the book's are listed in tests/known-cosmo-terms.tsv, and
  the build wants exactly that list;

  the index: a name or another name that is a headword as written is linked
  to it, and data/cosmology/headwords.tsv, ours and reviewed, names the
  headword of one that is not; every slug there must be a headword's.

What is derived here and not his: the sign each card carries (GLYPHS, his
engine's rule, with the sign for Trinity origin the site's own, DECISIONS.md),
each line as a path with rounded corners, and which lines are far.
"""

from __future__ import annotations

import csv
import pathlib
import re

from . import config
from .readers import cosmo as reader

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEADS = ROOT / "data" / "cosmology" / "headwords.tsv"
KNOWN_TERMS = ROOT / "tests" / "known-cosmo-terms.tsv"

# The text each language's names are held to: the press's, and for the Russian
# the Foundation's translation, whose terms his lang/ru.yaml says it uses
# ("Термины — по переводу Фонда Урантии").
TERMS = {"en": None, "ru": "uf-ru"}

# The sign on a card, by his engine's rule (src/engine.html originGlyph, at
# dffe509): the first of a personality's groups in this order decides it, and
# lends the sign its colour.
GLYPH_ORDER = ("deity", "desc", "trin", "supreme", "supspirit", "coord", "angel", "powercenters",
               "spirit", "local", "asc", "unclass", "stationary", "transcg", "finality")
GLYPHS = {"deity": "deity", "desc": "descending", "angel": "angel", "local": "local", "asc": "ascender"}
# How round a line's corners are, as his pathD draws them.
CORNER = 9

RE_WORD = re.compile(r"[\w'’-]+")
RE_PART = re.compile(r"\s+—\s+|[()]")


def glyph(origin: str, groups: list[str]) -> tuple[str, str]:
    """(the sign, the group whose colour draws it)."""
    first = next((g for g in GLYPH_ORDER if g in groups), groups[0])
    if origin == "A":
        return "absolute", first
    if first != "deity" and origin == "T":
        return "trinity", first
    if first != "deity" and "asc" in groups:
        return "ascender", first
    return GLYPHS.get(first, "spirit"), first


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}"


def path_d(pts: list[list[int]], r: int = CORNER) -> str:
    """The corners a line turns at as an SVG path, each rounded: his pathD."""
    d = f"M{pts[0][0]},{pts[0][1]}"
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        l1 = abs(b[0] - a[0]) + abs(b[1] - a[1])
        l2 = abs(c[0] - b[0]) + abs(c[1] - b[1])
        rr = min(r, l1 / 2, l2 / 2)
        p1 = (b[0] + (a[0] - b[0]) * rr / l1, b[1] + (a[1] - b[1]) * rr / l1)
        p2 = (b[0] + (c[0] - b[0]) * rr / l2, b[1] + (c[1] - b[1]) * rr / l2)
        d += f" L{_n(p1[0])},{_n(p1[1])} Q{b[0]},{b[1]} {_n(p2[0])},{_n(p2[1])}"
    return d + f" L{pts[-1][0]},{pts[-1][1]}"


def parts(name: str) -> list[str]:
    """«А — Б (В)» as А, Б, В: each is looked for by itself."""
    return [x.strip() for x in RE_PART.split(name) if x.strip()]


def fold(text: str) -> str:
    """Text as it is searched: small letters, ё as е, one apostrophe, and no
    stress mark, which the Foundation's Russian writes on a word here and
    there (build/tr_html.py)."""
    return text.lower().replace("ё", "е").replace("’", "'").replace("\u0301", "")


def found(term: str, text: str, lang: str) -> bool:
    """Whether `term` is in `text` (folded), by his validator's rule: its words
    in their order, a Russian word by its stem with any ending, an English one
    with a plural's or a possessive's."""
    words = RE_WORD.findall(fold(term))
    if not words:
        return True
    if lang == "ru":
        pat = r"[\s,]+".join(re.escape(w[:max(3, len(w) - 2)] if len(w) > 4 else w) + r"[\w-]*" for w in words)
    else:
        pat = r"\s+".join(re.escape(w[:-1] if w.endswith("s") and len(w) > 4 else w) + r"[\w']*" for w in words)
    return re.search(r"(?<![\w-])" + pat, text) is not None


def book_text(con, lang: str) -> str | None:
    """Everything the book says in a language, folded: its paragraphs and its
    titles.  None where the translation TERMS names is not in the database."""
    key = TERMS[lang]
    if key is None:
        qs = ("SELECT text FROM paragraph", "SELECT title FROM section WHERE title IS NOT NULL",
              "SELECT title FROM paper")
        rows = [t for q in qs for (t,) in con.execute(q)]
    else:
        if not con.execute("SELECT 1 FROM translation WHERE key=?", (key,)).fetchone():
            return None
        rows = [t for (t,) in con.execute("SELECT text FROM tr_paragraph WHERE translation=?", (key,))]
        rows += [t for (t,) in con.execute("SELECT text FROM tr_heading WHERE translation=?", (key,))]
    return fold(" \n ".join(rows))


def names(p: dict, lang: str) -> list[str]:
    """What a personality is called in a language: its name, and its others."""
    out = [p["name"][lang]] if p.get("name", {}).get(lang) else []
    out += (p.get("aka") or {}).get(lang, [])
    return out


def terms_missing(con, doc: dict) -> set[tuple[str, str, str]]:
    """{(id, language, term)}: each part of a personality's names that the book
    does not have, in that language's text.  His `terms`, where a personality
    has them, stand for its names, as in his validator."""
    out = set()
    for lang in TERMS:
        text = book_text(con, lang)
        if text is None:
            out.add(("*", lang, f"no translation {TERMS[lang]} in this build"))
            continue
        for p in doc["persons"]:
            given = (p.get("terms") or {}).get(lang)
            cand = given if given else [x for n in names(p, lang) for x in parts(n)]
            out.update((p["id"], lang, t) for t in cand if not found(t, text, lang))
    return out


def load_known_terms() -> set[tuple[str, str, str]]:
    if not KNOWN_TERMS.is_file():
        return set()
    rows = csv.DictReader((ln for ln in KNOWN_TERMS.read_text(encoding="utf-8").splitlines()
                           if ln.strip() and not ln.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE)
    return {(r["id"], r["lang"], r["term"]) for r in rows}


def load_heads_table(report) -> list[tuple[str, str]]:
    """data/cosmology/headwords.tsv: (id, slug) in its order, a unit's or a
    personality's, for a name that is no headword as written."""
    if not HEADS.is_file():
        return []
    out = []
    lines = [ln for ln in HEADS.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    for r in csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE):
        if set(r) != {"id", "slug", "why"} or not r["id"] or not r["slug"]:
            report.hard("cosmo-headwords", HEADS.name, f"not id, slug, why: {r!r}")
            continue
        out.append((r["id"], r["slug"]))
    return out


def heads(con, doc: dict, table: list[tuple[str, str]], report) -> list[tuple[str, str, int, str, str]]:
    """(kind, key, ord, slug, via) for cosmo_head: a name that is a headword
    as written, then another name that is, then the table's."""
    by_word: dict[str, str] = {}
    for h, slug in con.execute("SELECT headword, slug FROM index_entry WHERE scope='az' AND level=1"
                               " AND slug IS NOT NULL ORDER BY ord"):
        by_word.setdefault(h.rstrip(". ").casefold(), slug)
    slugs = set(by_word.values())
    kinds = {u["id"]: "unit" for u in doc["units"]} | {p["id"]: "person" for p in doc["persons"]}
    got: dict[str, list[tuple[str, str]]] = {}

    def add(key, slug, via):
        if slug not in [s for s, _ in got.setdefault(key, [])]:
            got[key].append((slug, via))

    for u in doc["units"]:
        s = by_word.get(u["name"]["en"].casefold())
        if s:
            add(u["id"], s, "name")
    for p in doc["persons"]:
        s = by_word.get(p["name"]["en"].casefold())
        if s:
            add(p["id"], s, "name")
        for a in (p.get("aka") or {}).get("en", []):
            s = by_word.get(a.casefold())
            if s:
                add(p["id"], s, "aka")
    for key, slug in table:
        if key not in kinds:
            report.hard("cosmo-headwords", key, f"{HEADS.name} names it, and the chart has none such")
        elif slug not in slugs:
            report.hard("cosmo-headwords", key, f"{HEADS.name} gives it /i/{slug}, which is no headword's address")
        elif slug in [s for s, _ in got.get(key, [])]:
            report.hard("cosmo-headwords", key, f"{HEADS.name} gives it /i/{slug}, which its name finds already:"
                                                f" take the line out")
        else:
            add(key, slug, "table")
    return [(kinds[key], key, i, slug, via) for key, found_ in got.items() for i, (slug, via) in enumerate(found_)]


def load(con, src: dict, report) -> dict:
    """Read the snapshot, hold it to the book, and store it.  The stats for
    `stat`; all zero where there is no snapshot, and the page is then absent."""
    stats = {"cosmo_persons": 0, "cosmo_units": 0, "cosmo_links": 0, "cosmo_headwords": 0}
    path = src["snapshot"]
    if not path.is_file():
        return stats
    doc = reader.read(path)
    bad = reader.problems(doc)
    for b in bad[:30]:
        report.hard("cosmo-shape", path.name, b)
    if bad:
        return stats
    # His repository has moved on, where it is on this machine: said, and not
    # a failure, since the snapshot is refreshed on purpose and reviewed.
    if src["commit"] and src["commit"] != doc["source"]["commit"]:
        report.warn("cosmo-snapshot-behind", path.name,
                    f"made at {doc['source']['commit'][:7]}; his repository is at {src['commit'][:7]}"
                    f" of {src['date']}: make cosmo-snapshot, and review the diff")

    papers = {n for (n,) in con.execute("SELECT n FROM paper")}
    sections = {(p, s) for p, s in con.execute("SELECT paper_n, n FROM section")}
    refs = []
    for kind, recs in (("unit", doc["units"]), ("person", doc["persons"])):
        for r in recs:
            for i, ref in enumerate(r["refs"]):
                m = reader.RE_REF.fullmatch(ref)
                p, s = int(m[1]), (int(m[2]) if m[2] is not None else None)
                if p not in papers or (s is not None and (p, s) not in sections):
                    report.hard("cosmo-ref", r["id"], f"{ref}: the book has no such "
                                                      f"{'paper' if s is None else 'section'}")
                refs.append((kind, r["id"], i, p, s))

    missing, known = terms_missing(con, doc), load_known_terms()
    for pid, lang, term in sorted(missing - known):
        report.hard("cosmo-term", f"{pid} [{lang}]",
                    f"{term!r} is not in the {'press text' if TERMS[lang] is None else TERMS[lang]}:"
                    f" a slip of his, or his own wording, which {KNOWN_TERMS.name} then lists")
    for pid, lang, term in sorted(known - missing):
        report.hard("cosmo-term", f"{pid} [{lang}]",
                    f"{KNOWN_TERMS.name} lists {term!r} as not in the text, and it is, or the chart no longer"
                    f" says it: take the line out")

    head_rows = heads(con, doc, load_heads_table(report), report)

    con.executemany("INSERT INTO cosmo_meta VALUES (?,?)",
                    [("url", doc["source"]["url"]), ("commit", doc["source"]["commit"]),
                     ("date", doc["source"]["date"]), ("version", doc["source"]["version"]),
                     ("w", str(doc["canvas"]["w"])), ("h", str(doc["canvas"]["h"])),
                     ("card_w", str(doc["canvas"]["card"][0])), ("card_h", str(doc["canvas"]["card"][1]))])
    texts = []

    def words(kind, rec):
        for f in ("name", "aka", "desc", "serves", "there"):
            for lang, v in (rec.get(f) or {}).items():
                if lang in reader.LANGS:
                    texts.extend((kind, rec["id"], f, lang, i, w) for i, w in enumerate(v if isinstance(v, list) else [v]))

    for kind, sect in (("class", "classes"), ("group", "groups"), ("func", "functions")):
        for i, k in enumerate(doc[sect]):
            con.execute("INSERT INTO cosmo_key VALUES (?,?,?,?)", (kind, k["id"], i, k["color"].lower()))
            words(kind, k)
    depth: dict[str | None, int] = {None: -1}
    for i, u in enumerate(doc["units"]):
        depth[u["id"]] = depth[u["parent"]] + 1
        con.execute("INSERT INTO cosmo_unit VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (u["id"], u["parent"], i, depth[u["id"]], u["color"].lower(), int(bool(u.get("linkable"))),
                     *u["box"]))
        con.executemany("INSERT INTO cosmo_title VALUES (?,?,?)",
                        [(u["id"], lang, u["title"][lang]) for lang in reader.LANGS])
        words("unit", u)
    for i, p in enumerate(doc["persons"]):
        con.execute("INSERT INTO cosmo_person VALUES (?,?,?,?,?,?,?)",
                    (p["id"], i, p["class"], p["origin"], None, *glyph(p["origin"], p["groups"])))
        for kind, f in (("group", "groups"), ("func", "func"), ("fuse", "fuse")):
            con.executemany("INSERT INTO cosmo_tag VALUES (?,?,?,?)",
                            [(p["id"], kind, k, n) for n, k in enumerate(p.get(f, []))])
        words("person", p)
    con.executemany("UPDATE cosmo_person SET pair=? WHERE id=?",
                    [(p["pair"], p["id"]) for p in doc["persons"] if p.get("pair")])
    con.executemany("INSERT INTO cosmo_place VALUES (?,?,?,?,?,?,?,?)",
                    [(pl["id"], pl["id"].lstrip("~"), int(pl["id"].startswith("~")), pl["unit"],
                      pl["row"], pl["col"], *pl["at"]) for pl in doc["places"]])
    where = reader.rects(doc)
    for i, l in enumerate(doc["links"], 1):
        a, b = where[l["from"]], where[l["to"]]
        far = abs(a[0] - b[0]) + abs(a[1] - b[1]) > doc["canvas"]["long"]
        con.execute("INSERT INTO cosmo_link VALUES (?,?,?,?,?)", (i, l["from"], l["to"], l["type"], int(far)))
        con.executemany("INSERT INTO cosmo_route VALUES (?,?,?,?)",
                        [(i, lang, " ".join(f"{x},{y}" for x, y in l["route"][lang]), path_d(l["route"][lang]))
                         for lang in reader.LANGS])
    con.executemany("INSERT INTO cosmo_text VALUES (?,?,?,?,?,?)", texts)
    con.executemany("INSERT INTO cosmo_ref VALUES (?,?,?,?,?)", refs)
    con.executemany("INSERT INTO cosmo_head VALUES (?,?,?,?,?)", head_rows)
    return {"cosmo_persons": len(doc["persons"]), "cosmo_units": len(doc["units"]),
            "cosmo_links": len(doc["links"]),
            "cosmo_headwords": len({k for kind, k, *_ in head_rows if kind == "person"})}


def source_row(src: dict) -> tuple | None:
    """build_source's row for the snapshot: the commit of his repository it was
    made at, which is in it, and that commit's page."""
    path = src["snapshot"]
    if not path.is_file():
        return None
    s = reader.read(path)["source"]
    return ("cosmology", s["commit"], 0, "snapshot", s["date"], f"{s['url'].rstrip('/')}/commit/{s['commit']}")


if __name__ == "__main__":
    # What the gates would say of the snapshot against the database as built.
    import sqlite3
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    doc = reader.read(config.cosmology()["snapshot"])
    print("shape:", reader.problems(doc) or "sound")
    for row in sorted(terms_missing(con, doc)):
        print("not in the text:", *row, sep="\t")
