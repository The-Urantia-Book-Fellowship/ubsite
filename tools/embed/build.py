"""var/embed.db: every unit Search by meaning searches, with its vector.

    make embed          what has changed since the last time, on this machine's CPU
    make embed GPU=1    the same on the 3090, for when the whole book is new

    .venv/bin/python -m tools.embed.build [--limit N] [--threads N]
    ~/Software/ml/venv-embed/bin/python -m tools.embed.build --gpu

The units are build/embed.py's, composed from var/ub.db and var/bible.db as
they stand; the model is the one build/config.py embed() names, in var/embed/bge-m3/
(tools/embed/fetch.py), run by ubsite/meaning.py's Embedder, the same code
that embeds a reader's question on a host.

A vector is made once.  var/embed/cache.db keeps every vector by the SHA-256
of its text, with how it was made; a unit whose text has not changed takes
its vector from there, and so does one whose text was changed and changed
back.  So after an edit of the index a few hundred entries are embedded, on
the CPU, in a minute; and var/embed.db, put together from the units in their
order and the vectors the cache has, is byte for byte the same for the same
units: it has no date and no path in it, and where nothing has changed it is
not written at all.

Before the file is swapped in, units from all through it are embedded again
on the CPU, one at a time, as a host embeds a question, and each must come
out as it is stored (cosine 0.9999): the 3090 makes most of them, and the
hosts answer on CPUs.

The whole book is hours on a CPU and minutes on the 3090, so more than
--limit new units are refused here without --gpu.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import config, embed                   # noqa: E402
from tools.embed import fetch                     # noqa: E402
from ubsite import meaning                        # noqa: E402

UB = ROOT / "var" / "ub.db"
BIBLE = ROOT / "var" / "bible.db"
OUT = ROOT / "var" / "embed.db"
WORK = ROOT / "var" / "embed"
CACHE = WORK / "cache.db"
LOG = WORK / "build.log"
SCHEMA = ROOT / "build" / "schema_embed" / "embed.sql"

LIMIT = 2000          # new units a CPU is asked for; more is the 3090's work
SAMPLE = 64           # units embedded again on the CPU before the swap
ALIKE = 0.9999        # the least cosine of one of them with what is stored
# A batch: its texts padded to its longest, so many tokens at the most, and so
# many texts.  The 3090 has room for far more; a CPU gains nothing from more.
BATCH = {True: (20000, 96), False: (1500, 8)}


def say(*words: object) -> None:
    line = " ".join(str(w) for w in words)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")


def ro(path: pathlib.Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"{path.relative_to(ROOT)}: not built (make data)")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def model_meta(cfg: dict) -> dict[str, str]:
    """What embed_meta and the cache say of the model."""
    out = {"model": cfg["repo"], "rev": cfg["rev"], "dim": str(cfg["dim"])}
    out.update({f"sha256 {name}": sha for name, sha in sorted(cfg["sha256"].items())})
    return out


def current(dig: str, cfg: dict) -> bool:
    """Whether var/embed.db is already today's units, of this model."""
    if not OUT.is_file():
        return False
    try:
        con = sqlite3.connect(f"file:{OUT}?mode=ro", uri=True)
        meta = dict(con.execute("SELECT key, value FROM embed_meta"))
        con.close()
    except sqlite3.Error:
        return False
    return meta.get("units") == dig and all(meta.get(k) == v for k, v in model_meta(cfg).items())


def cache(cfg: dict) -> sqlite3.Connection:
    """The vectors made so far, of this model alone."""
    new = not CACHE.is_file()
    con = sqlite3.connect(CACHE)
    if new:
        con.executescript(
            "CREATE TABLE cache_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;"
            # how: the runtime's provider and version, 'CUDAExecutionProvider 1.32.0'
            "CREATE TABLE vec (hash BLOB PRIMARY KEY, v BLOB NOT NULL CHECK (length(v) = 4096),"
            "                  how TEXT NOT NULL) WITHOUT ROWID;")
        con.executemany("INSERT INTO cache_meta VALUES (?, ?)", model_meta(cfg).items())
        con.commit()
    elif dict(con.execute("SELECT key, value FROM cache_meta")) != model_meta(cfg):
        raise SystemExit(f"{CACHE.relative_to(ROOT)} holds another model's vectors: move it aside, "
                         f"and the whole book is embedded anew")
    return con


def embed_new(con: sqlite3.Connection, todo: dict[bytes, str], em: meaning.Embedder, gpu: bool) -> None:
    """Every text of `todo` into the cache, the longest first, so that what
    the largest batch needs is known at once; kept as it goes, so that a run
    stopped is taken up where it stopped."""
    np = em.np
    hashes = list(todo)
    lens = []
    for i in range(0, len(hashes), 4096):
        lens += em.lengths([todo[h] for h in hashes[i:i + 4096]])
    order = sorted(range(len(hashes)), key=lambda i: -lens[i])
    tokens, most = BATCH[gpu]
    how = f"{em.provider} {em.runtime}"
    total = sum(lens)
    say(f"{len(hashes):,} texts, {total:,} tokens, the longest {lens[order[0]]:,}, on {how}")
    done = done_tokens = 0
    t0 = last = time.time()
    i = 0
    while i < len(order):
        n = max(1, min(most, tokens // lens[order[i]], len(order) - i))
        part = order[i:i + n]
        v = em.encode([todo[hashes[j]] for j in part])
        if v.shape != (n, meaning.DIM) or not np.isfinite(v).all():
            raise SystemExit(f"the model gave {v.shape}, or a number that is none")
        con.executemany("INSERT OR REPLACE INTO vec VALUES (?, ?, ?)",
                        [(hashes[j], v[k].astype("<f4").tobytes(), how) for k, j in enumerate(part)])
        con.commit()
        i += n
        done += n
        done_tokens += sum(lens[j] for j in part)
        if time.time() - last > 5 or i == len(order):
            last = time.time()
            rate = done_tokens / max(last - t0, 1e-9)
            say(f"  {done:,} of {len(hashes):,} texts, {rate:,.0f} tokens a second, "
                f"{(total - done_tokens) / max(rate, 1e-9):,.0f} s to go")


def again(us: list[embed.Unit], vecs: dict[bytes, bytes], em: meaning.Embedder) -> float:
    """SAMPLE units from all through the list, embedded one at a time on the
    CPU: the least cosine of one with what is stored for it."""
    np = em.np
    step = max(1, len(us) // SAMPLE)
    least = 1.0
    for u in us[::step][:SAMPLE]:
        c = float(em.one(u.text) @ np.frombuffer(vecs[u.hash], dtype="<f4"))
        if c < ALIKE:
            raise SystemExit(f"{u.kind} {u.label}: the CPU's vector and the one stored are {c:.6f} alike, "
                             f"under {ALIKE}; nothing is written")
        least = min(least, c)
    return least


def write(us: list[embed.Unit], vecs: dict[bytes, bytes], dig: str, cfg: dict, probe: bytes) -> None:
    tmp = OUT.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.executemany("INSERT INTO unit VALUES (?, ?, ?, ?, ?, ?)",
                    ((i, u.kind, u.label, u.target, u.hash, vecs[u.hash]) for i, u in enumerate(us, 1)))
    meta: dict[str, object] = dict(model_meta(cfg))
    meta.update(recipe=str(embed.RECIPE), units=dig, n=str(len(us)), probe=meaning.PROBE, probe_v=probe)
    for k in embed.KINDS:
        meta[f"n {k}"] = str(sum(u.kind == k for u in us))
    con.executemany("INSERT INTO embed_meta VALUES (?, ?)", sorted(meta.items()))
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, OUT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gpu", action="store_true", help="on the GPU the environment shows (the 3090: the Makefile's)")
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"new units a CPU is asked for ({LIMIT:,})")
    ap.add_argument("--threads", type=int, default=min(6, os.cpu_count() or 1), help="the CPU's threads for one run")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)

    cfg = config.embed()
    ub, bible = ro(UB), ro(BIBLE)
    us = embed.units(ub, bible)
    dig = embed.digest(us)
    counts = ", ".join(f"{sum(u.kind == k for u in us):,} {k}" for k in embed.KINDS)
    if current(dig, cfg):
        print(f"var/embed.db is today's: {len(us):,} units ({counts})")
        return 0

    con = cache(cfg)
    texts = {u.hash: u.text for u in us}
    texts[embed.Unit("", "", "", meaning.PROBE).hash] = meaning.PROBE
    have = {h for (h,) in con.execute("SELECT hash FROM vec")}
    todo = {h: t for h, t in texts.items() if h not in have}
    say(f"{len(us):,} units ({counts}); {len(todo):,} texts to embed, {len(texts) - len(todo):,} had")
    if len(todo) > a.limit and not a.gpu:
        raise SystemExit(f"{len(todo):,} texts are new, more than {a.limit:,}: the 3090's work (make embed GPU=1)")

    wrong = fetch.check(cfg)
    if wrong:
        raise SystemExit("\n".join(wrong))
    main_em = meaning.Embedder(threads=a.threads, gpu=a.gpu) if (todo or not a.gpu) else None
    if todo:
        embed_new(con, todo, main_em, a.gpu)
    cpu = main_em if (main_em is not None and not a.gpu) else meaning.Embedder(threads=a.threads)

    vecs = {h: v for h, v in con.execute("SELECT hash, v FROM vec") if h in texts}
    missing = [h for h in texts if h not in vecs]
    if missing:
        raise SystemExit(f"{len(missing):,} texts have no vector in the cache")
    least = again(us, vecs, cpu)
    probe = vecs[embed.Unit("", "", "", meaning.PROBE).hash]
    alike = float(cpu.one(meaning.PROBE) @ cpu.np.frombuffer(probe, dtype="<f4"))
    if alike < ALIKE:
        raise SystemExit(f"the probe: the CPU's vector and the one stored are {alike:.6f} alike, under {ALIKE}")
    write(us, vecs, dig, cfg, probe)
    say(f"var/embed.db: {len(us):,} units, {OUT.stat().st_size / 1e6:,.1f} MB; "
        f"{SAMPLE} of them embedded again on the CPU, the least {least:.6f} alike; the probe {alike:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
