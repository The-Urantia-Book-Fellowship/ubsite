"""Search by meaning's vectors, as var/embed.db holds them (tools/embed/build.py).

Each count of the first table must be 0:

  that the file is of the model config.embed() names, by its revision
  and the digest of each of its files, and of today's recipe;

  that its units are exactly the units build/embed.py composes from var/ub.db
  and var/bible.db as they are now, in their order, each with its name, its
  target and the hash of its text.  So every paragraph of the book has one
  vector and no more, every index entry that cites has one, and no vector is
  of a text that has since changed: after `make data` has moved a text, this
  fails until `make embed`;

  that every vector, the probe's among them, is 1,024 numbers of unit length.

Then the numbers verify/expectations.toml holds, [embed]: the paragraphs and
the KJV's passages, which move only with the book and the recipe, exactly; the index's entries and the study notes, which move as the index is
edited and as papers' notes are reviewed, within a band.

It does not ask whether a vector is the right one for its text: the tool
embeds 64 units again on the CPU before it writes the file, and a host embeds
the probe as it loads the model.  Nor whether the search finds what it
should, which is tools/embed/bench.py's.
"""

from __future__ import annotations

import pathlib
import sqlite3
import tomllib

from .. import config, embed

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "var" / "embed.db"
UB = ROOT / "var" / "ub.db"
BIBLE = ROOT / "var" / "bible.db"
EXACT = ("para", "kjv")
BAND = ("entry", "note")


def expected() -> dict:
    with open(ROOT / "verify" / "expectations.toml", "rb") as fh:
        return tomllib.load(fh)["embed"]


def run(db: pathlib.Path = OUT) -> int:
    for p, how in ((db, "make embed"), (UB, "make data"), (BIBLE, "make bible")):
        if not p.exists():
            print(f"  {p.relative_to(ROOT)} is missing ({how})")
            return 1
    import numpy as np

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    meta = dict(con.execute("SELECT key, value FROM embed_meta"))
    cfg = config.embed()
    model = {"model": cfg["repo"], "rev": cfg["rev"], "dim": str(cfg["dim"])}
    model.update({f"sha256 {name}": sha for name, sha in cfg["sha256"].items()})
    today = embed.units(sqlite3.connect(f"file:{UB}?mode=ro", uri=True),
                        sqlite3.connect(f"file:{BIBLE}?mode=ro", uri=True))
    want = [(u.kind, u.label, u.target, u.hash) for u in today]
    got = con.execute("SELECT kind, label, target, hash FROM unit ORDER BY id").fetchall()
    ids = [i for (i,) in con.execute("SELECT id FROM unit ORDER BY id")]
    stale = len(set(want) ^ set(got)) if want != got else 0
    blob = b"".join(v for (v,) in con.execute("SELECT v FROM unit ORDER BY id"))
    m = np.frombuffer(blob, dtype="<f4").reshape(-1, cfg["dim"]) if len(blob) % (4 * cfg["dim"]) == 0 else None
    norms = np.linalg.norm(m, axis=1) if m is not None else None
    probe = meta.get("probe_v", b"")
    pv = np.frombuffer(probe, dtype="<f4") if len(probe) == 4 * cfg["dim"] else None
    paras = sqlite3.connect(f"file:{UB}?mode=ro", uri=True).execute("SELECT COUNT(*) FROM paragraph").fetchone()[0]
    gates = [
        ("the model is not the one config.embed() names", sum(meta.get(k) != v for k, v in model.items())),
        ("the recipe is not build/embed.py's", int(meta.get("recipe") != str(embed.RECIPE))),
        ("units that are not today's, or today's that are missing (make embed)", stale or int(want != got)),
        ("the units' digest is not the file's own word of it", int(meta.get("units") != embed.digest(today))),
        ("units not numbered 1..N in their order", int(ids != list(range(1, len(ids) + 1)))),
        ("paragraphs without exactly one vector", abs(sum(k == "para" for k, *_ in got) - paras)
         + len({lab for k, lab, *_ in got if k == "para"} ^ {u.label for u in today if u.kind == "para"})),
        ("vectors that are not 1,024 numbers", int(m is None) + int(m is not None and len(m) != len(got))),
        ("vectors not of unit length", int(norms is None) or int(((norms < 0.999) | (norms > 1.001) | ~np.isfinite(norms)).sum())),
        ("the probe has no vector of unit length", int(pv is None or abs(float(np.linalg.norm(pv)) - 1) > 1e-3
                                                      or not meta.get("probe"))),
    ]
    rc = 0
    for label, n in gates:
        print(f"  {label:68} {n}")
        rc |= bool(n)
    exp = expected()
    for k in EXACT:
        n = int(meta.get(f"n {k}", -1))
        ok = n == exp[k]
        print(f"  {k:8} {n:>7,}" + ("" if ok else f"   EXPECTED {exp[k]:,} (verify/expectations.toml [embed])"))
        rc |= not ok
    for k in BAND:
        n = int(meta.get(f"n {k}", -1))
        lo, hi = exp[k]
        ok = lo <= n <= hi
        print(f"  {k:8} {n:>7,}" + ("" if ok else f"   EXPECTED {lo:,} to {hi:,} (verify/expectations.toml [embed])"))
        rc |= not ok
    print(f"  {'in all':8} {len(got):>7,}   {db.stat().st_size / 1e6:,.1f} MB")
    con.close()
    return rc
