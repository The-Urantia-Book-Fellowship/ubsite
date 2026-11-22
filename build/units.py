"""Unit conversions: data/units.toml into the tables unit_* (015_units.sql).

The page /units converts the units of time, distance, speed, weight and
temperature the Urantia Papers define or use into each other and into the
familiar ones, every row of a table editable and the rest following (Tigran,
2026-11-22).  The units are data, read here and held to the text; the page's
script (ubsite/static/units.js) does the arithmetic and nothing else.

Each unit's size is an expression over others, `1000 year - 7 minute - 3.125
second`, worked out here in fractions, so that what the book states exactly
is stored exactly (`scale_exact`), and as a float for the page.  Held, each a
hard failure:

  the tables, bands and units are named once and join up; each table has one
  base, and nothing refers to a unit that is not there, or round in a circle;
  a term is of its own table, or a distance over a time in the speeds';

  a unit the book defines names a paragraph there is, and its words are in it,
  once and whole, and the same words of the Foundation's Russian in uf-ru's
  paragraph, where uf-ru is built (the Russian names are the Foundation's:
  Tigran, 2026-11-22); a familiar unit gives its standard in both languages;

  the parsec, the one size that is no fraction, is 648,000/π astronomical
  units to the last digit a float holds;

  an example's words are its paragraph's, as a unit's are, and where the book
  gives its figure in another unit too (`says`), the table agrees within the
  fraction `within`: 54:6.6's twenty-five thousand years of system time are
  twenty thousand of Urantia time, and the table makes them 20,228.

A unit is `about` where the book says about or almost, and so is every unit
made from one.
"""

from __future__ import annotations

import math
import pathlib
import re
import sqlite3
import tomllib
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "units.toml"
EXPECT = ROOT / "verify" / "expectations.toml"
# The Foundation's Russian translation, whose words the Russian page quotes.
UF = "uf-ru"
# A table whose units are made of two others' (`mile/second`), and of which.
DIMS = {"speed": ("distance", "time")}

RE_TERM = re.compile(r"\s*([+-])?\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?(?:/\d+)?)?\s*([a-z][a-z0-9]*)(?:/([a-z][a-z0-9]*))?\s*")


def read(path: pathlib.Path = DATA) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def terms(expr: str) -> list[tuple[Fraction, str, str | None]] | None:
    """`3 day - 1 hour` as [(3, 'day', None), (-1, 'hour', None)];
    `1 mile/second` as [(1, 'mile', 'second')]; None where it does not parse."""
    out, i = [], 0
    while i < len(expr):
        m = RE_TERM.match(expr, i)
        if not m or m.end() == i or (out and not m[1]) or (not out and m[1] == "+"):
            return None
        sign = -1 if m[1] == "-" else 1
        num = Fraction(1) if m[2] is None else _number(m[2])
        out.append((sign * num, m[3], m[4]))
        i = m.end()
    return out or None


def _number(s: str) -> Fraction:
    if "/" in s:
        a, b = s.split("/")
        return Fraction(a) / Fraction(b)
    return Fraction(s) if "e" not in s else Fraction(*float(s).as_integer_ratio())


def find(text: str, words: str) -> tuple[int | None, str]:
    """Where `words` begin in `text`, or None and why not: there once, and
    whole words."""
    if not words or words != words.strip():
        return None, "no words, or a space before or after them"
    i = text.find(words)
    if i < 0:
        return None, "the words are not in the paragraph"
    if text.find(words, i + 1) >= 0:
        return None, "the words occur more than once: say more"
    e = i + len(words)
    if (i > 0 and text[i - 1].isalnum() and words[0].isalnum()) or \
            (e < len(text) and text[e - 1].isalnum() and text[e].isalnum()):
        return None, "the words begin or end inside a word"
    return i, ""


class Units:
    """The file, its sizes worked out: `size[key]` in its table's base, a
    Fraction (a float for the parsec), `about[key]`."""

    def __init__(self, doc: dict, report, where: str = "data/units.toml"):
        self.doc, self.report, self.where = doc, report, where
        self.groups = {g["key"]: g for g in doc.get("group", [])}
        self.bands = {(b["group"], b["key"]): b for b in doc.get("band", [])}
        self.units = {u["key"]: u for u in doc.get("unit", [])}
        self.size: dict[str, Fraction | float] = {}
        self.about: dict[str, bool] = {}
        self._names()
        for k in self.units:
            self._size(k, ())

    def hard(self, code: str, msg: str) -> None:
        self.report.hard(code, self.where, msg)

    def _names(self) -> None:
        for kind, rows in (("group", self.doc.get("group", [])), ("unit", self.doc.get("unit", []))):
            keys = [r.get("key") for r in rows]
            for k in sorted({k for k in keys if keys.count(k) > 1}):
                self.hard("units-twice", f"the {kind} {k!r} is named twice")
        bands = [(b.get("group"), b.get("key")) for b in self.doc.get("band", [])]
        for g, k in sorted({b for b in bands if bands.count(b) > 1}):
            self.hard("units-twice", f"the band {k!r} of {g!r} is named twice")
        for (g, k) in self.bands:
            if g not in self.groups:
                self.hard("units-band", f"the band {k!r} is of {g!r}, which is no table")
        for g in self.groups.values():
            for f in ("en", "ru"):
                if not g.get(f):
                    self.hard("units-name", f"the table {g['key']!r} has no {f} name")
            st = g.get("start", {})
            if self.units.get(st.get("unit"), {}).get("group") != g["key"] or not isinstance(st.get("value"), (int, float)):
                self.hard("units-start", f"the table {g['key']!r} opens at {st!r}, which is not a unit of it with a value")
            bases = [u["key"] for u in self.units.values() if u.get("group") == g["key"] and u.get("size") == "base"]
            if len(bases) != 1:
                self.hard("units-base", f"the table {g['key']!r} has {len(bases)} bases, and needs one")
        for u in self.units.values():
            k = u["key"]
            if u.get("group") not in self.groups:
                self.hard("units-group", f"{k}: {u.get('group')!r} is no table")
                continue
            if "band" in u and (u["group"], u["band"]) not in self.bands:
                self.hard("units-band", f"{k}: {u['band']!r} is no band of {u['group']!r}")
            if any(b[0] == u["group"] for b in self.bands) != ("band" in u):
                self.hard("units-band", f"{k}: a unit has a band where its table has bands, and only there")
            for f in ("en", "ru"):
                if not u.get(f):
                    self.hard("units-name", f"{k}: no {f} name")
            book, fam = "ref" in u, "def" in u
            if book == fam:
                self.hard("units-what", f"{k}: a unit is the book's (ref, words, words_ru) or familiar (def), and one of them")
            if book and not (u.get("words") and u.get("words_ru")):
                self.hard("units-what", f"{k}: a unit of the book's gives its words in English and Russian")
            if fam and not (u["def"].get("en") and u["def"].get("ru")):
                self.hard("units-what", f"{k}: a familiar unit gives its standard in English and Russian")

    def _size(self, k: str, path: tuple[str, ...]):
        if k in self.size:
            return self.size[k]
        if k in path:
            self.hard("units-circle", " -> ".join(path + (k,)) + ": round in a circle")
            return None
        u = self.units.get(k)
        if u is None or u.get("group") not in self.groups:
            return None
        if u.get("size") == "base":
            self.size[k], self.about[k] = Fraction(1), bool(u.get("about"))
            return self.size[k]
        ts = terms(u.get("size", ""))
        if ts is None:
            self.hard("units-size", f"{k}: {u.get('size')!r} does not parse")
            return None
        total, about = Fraction(0), bool(u.get("about"))
        for num, a, b in ts:
            if a not in self.units or (b is not None and b not in self.units):
                self.hard("units-size", f"{k}: {u['size']!r} names a unit there is not")
                return None
            ga, gb = self.units[a]["group"], (self.units[b]["group"] if b else None)
            if (b is None and ga != u["group"]) or (b is not None and DIMS.get(u["group"]) != (ga, gb)):
                self.hard("units-size", f"{k}: {u['size']!r} mixes tables ({ga}{'/' + gb if gb else ''} in {u['group']})")
                return None
            for x in (a, b):
                if x and self.units[x].get("offset"):
                    self.hard("units-size", f"{k}: {x} has an offset, and is no measure to count in")
                    return None
            sa = self._size(a, path + (k,))
            sb = self._size(b, path + (k,)) if b else 1
            if sa is None or sb is None:
                return None
            total += num * sa / sb
            about |= self.about[a] or bool(b and self.about[b])
        if total <= 0:
            self.hard("units-size", f"{k}: {u['size']!r} is not more than nothing")
            return None
        self.size[k], self.about[k] = total, about
        return total

    def scale(self, k: str) -> float:
        return float(self.size[k])

    def offset(self, k: str) -> float:
        return float(Fraction(self.units[k].get("offset", "0")))

    def convert(self, value: float, a: str, b: str) -> float:
        base = (value + self.offset(a)) * self.scale(a)
        return base / self.scale(b) - self.offset(b)


def load(con: sqlite3.Connection, report, path: pathlib.Path = DATA) -> dict:
    """Store the file; return its counts for the stat table."""
    where = f"data/{path.name}"
    U = Units(read(path), report, where)
    para = {r: (i, t) for i, r, t in con.execute("SELECT id, ref, text FROM paragraph")}
    has_uf = con.execute("SELECT 1 FROM translation WHERE key = ?", (UF,)).fetchone() is not None
    uf = dict(con.execute("SELECT p.ref, t.text FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                          " WHERE t.translation = ?", (UF,))) if has_uf else {}
    heads = {r[0] for r in con.execute("SELECT slug FROM index_entry WHERE level = 1 AND slug IS NOT NULL")}
    if not has_uf:
        report.warn("units-uf", where, f"{UF} is not built: the Russian page quotes the English")

    def held(what: str, ref: str, words: str, words_ru: str | None) -> tuple[int | None, str | None]:
        if ref not in para:
            report.hard("units-ref", where, f"{what}: {ref} is no paragraph")
            return None, None
        pid, text = para[ref]
        at, why = find(text, words)
        if at is None:
            report.hard("units-words", where, f"{what}, {ref} {words[:50]!r}...: {why}")
            return None, None
        if not has_uf:
            return pid, None
        if not words_ru:
            report.hard("units-words", where, f"{what}, {ref}: no words of {UF}")
            return None, None
        at, why = find(uf.get(ref, ""), words_ru)
        if at is None:
            report.hard("units-words", where, f"{what}, {ref} in {UF} {words_ru[:50]!r}...: {why}")
            return None, None
        return pid, words_ru

    if "parsec" in U.size and "au" in U.size:
        want = 648000 / math.pi * float(U.size["au"])
        if abs(float(U.size["parsec"]) / want - 1) > 2e-16:
            report.hard("units-parsec", where, f"the parsec is {float(U.size['parsec'])!r} m, and 648,000/π au is {want!r}")

    groups, bands, units, examples = [], [], [], []
    for n, g in enumerate(U.groups.values(), 1):
        if g.get("index") and g["index"] not in heads:
            report.hard("units-index", where, f"the table {g['key']!r}: {g['index']!r} is no headword of the index")
        groups.append((g["key"], n, g["en"], g["ru"], g.get("index"), g["start"]["unit"], g["start"]["value"]))
    order: dict[str, int] = {}
    for (gk, bk), b in U.bands.items():
        order[gk] = order.get(gk, 0) + 1
        bands.append((gk, bk, order[gk], b["en"], b["ru"]))
    rows: dict[str, int] = {}
    for k, u in U.units.items():
        if k not in U.size:
            continue
        rows[u["group"]] = rows.get(u["group"], 0) + 1
        pid = words_ru = None
        if "ref" in u:
            pid, words_ru = held(k, u["ref"], u.get("words", ""), u.get("words_ru"))
        s = U.size[k]
        exact = f"{s.numerator}/{s.denominator}" if isinstance(s, Fraction) else ""
        if k == "parsec":
            exact = ""      # written as a whole number of metres, and is 648,000/π au
        units.append((k, u["group"], u.get("band"), rows[u["group"]], u["en"], u["ru"], float(s), exact,
                      U.offset(k), int(U.about[k]), u.get("ref"), pid, u.get("words"), words_ru,
                      u.get("def", {}).get("en"), u.get("def", {}).get("ru")))
    for n, x in enumerate(U.doc.get("example", []), 1):
        what = f"example {n}"
        g, k = x.get("group"), x.get("unit")
        if g not in U.groups or U.units.get(k, {}).get("group") != g or k not in U.size:
            report.hard("units-example", where, f"{what}: {k!r} is no unit of the table {g!r}")
            continue
        if not isinstance(x.get("value"), (int, float)):
            report.hard("units-example", where, f"{what}: no value")
            continue
        pid, words_ru = held(what, x.get("ref", ""), x.get("words", ""), x.get("words_ru"))
        if pid is None:
            continue
        says = x.get("says")
        if says:
            su = says.get("unit")
            if U.units.get(su, {}).get("group") != g or su not in U.size:
                report.hard("units-example", where, f"{what}: says in {su!r}, no unit of the table {g!r}")
                continue
            got = U.convert(x["value"], k, su)
            off = abs(got - says["value"]) / abs(says["value"])
            if off > says["within"]:
                report.hard("units-says", where,
                            f"{what}, {x['ref']}: {x['value']:g} {k} are {got:,.6g} {su}, and the book says"
                            f" {says['value']:g}: {off:.4%} off, more than {says['within']:.4%}")
                continue
        examples.append((n, g, x["ref"], pid, x["words"], words_ru, k, x["value"],
                         says and says["unit"], says and says["value"], says and says["within"]))
    con.executemany("INSERT INTO unit_group VALUES (?,?,?,?,?,?,?)", groups)
    con.executemany("INSERT INTO unit_band VALUES (?,?,?,?,?)", bands)
    con.executemany("INSERT INTO unit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", units)
    con.executemany("INSERT INTO unit_example VALUES (?,?,?,?,?,?,?,?,?,?,?)", examples)
    return {"units": len(units), "units_book": sum(1 for u in units if u[10]),
            "unit_examples": len(examples)}


def expected(path: pathlib.Path = EXPECT) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh).get("units", {})


def check(db) -> int:
    """What was stored: its counts against verify/expectations.toml [units],
    and each count of what is wrong 0."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    got = {"groups": one("SELECT COUNT(*) FROM unit_group"),
           "units": one("SELECT COUNT(*) FROM unit"),
           "book_units": one("SELECT COUNT(*) FROM unit WHERE ref IS NOT NULL"),
           "about": one("SELECT COUNT(*) FROM unit WHERE about"),
           "examples": one("SELECT COUNT(*) FROM unit_example"),
           "gated": one("SELECT COUNT(*) FROM unit_example WHERE says_unit IS NOT NULL")}
    want = expected()
    rc = 0
    for k, v in got.items():
        ok = want.get(k) == v
        print(f"  {k:12} {v:>4}" + ("" if ok else f"   EXPECTED {want.get(k)} (verify/expectations.toml [units])"))
        rc |= not ok
    U = Units(read(), _Silent())
    has_uf = one("SELECT COUNT(*) FROM translation WHERE key = ?", UF)
    checks = [
        ("the database holds every unit and example of data/units.toml",
         abs(got["units"] - len(U.units)) + abs(got["examples"] - len(U.doc.get("example", [])))),
        ("every unit's and example's words are its paragraph's, once",
         sum(find(t, w)[0] is None for t, w in con.execute(
             "SELECT p.text, x.words FROM (SELECT paragraph_id, words FROM unit WHERE ref IS NOT NULL"
             " UNION ALL SELECT paragraph_id, words FROM unit_example) x JOIN paragraph p ON p.id = x.paragraph_id"))),
        (f"and their Russian {UF}'s" if has_uf else f"({UF} is not built: no Russian words)",
         sum(find(t or "", w)[0] is None for t, w in con.execute(
             "SELECT t.text, x.words_ru FROM (SELECT paragraph_id, words_ru FROM unit WHERE ref IS NOT NULL"
             " UNION ALL SELECT paragraph_id, words_ru FROM unit_example) x LEFT JOIN tr_paragraph t"
             " ON t.paragraph_id = x.paragraph_id AND t.translation = ?", (UF,))) if has_uf else 0),
        ("every unit is the size data/units.toml makes it",
         sum(abs(s - U.scale(k)) > 1e-12 * U.scale(k) for k, s in con.execute("SELECT key, scale FROM unit")
             if k in U.size)),
        ("every example the book gives in another unit agrees within its fraction",
         sum(abs(_conv(con, v, a, b) - s) / abs(s) > w for v, a, b, s, w in con.execute(
             "SELECT value, unit_key, says_unit, says_value, within FROM unit_example WHERE says_unit IS NOT NULL"))),
        ("every table has one base, a unit of size 1 from 0",
         one("SELECT COUNT(*) FROM unit_group g WHERE (SELECT COUNT(*) FROM unit u WHERE u.group_key = g.key"
             " AND u.scale = 1 AND u.offset = 0) != 1")),
    ]
    for what, bad in checks:
        print(f"  {what:<70} {bad}")
        rc |= bool(bad)
    return int(rc)


def _conv(con, value: float, a: str, b: str) -> float:
    (sa, oa), (sb, ob) = (con.execute("SELECT scale, offset FROM unit WHERE key = ?", (k,)).fetchone() for k in (a, b))
    return (value + oa) * sa / sb - ob


class _Silent:
    def hard(self, *a): pass
    def warn(self, *a): pass
