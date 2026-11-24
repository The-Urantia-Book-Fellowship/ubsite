"""Does Search by meaning find what it should?  The retrieval test.

    .venv/bin/python -m tools.embed.bench              -> var/embed/bench.md
    .venv/bin/python -m tools.embed.bench --ask "why do the good suffer" [--ask ...]

The questions are the quiz's, each with the passage of the text that answers
it, reviewed by hand a paper at a time (data/quiz/; the tables quiz_question
and quiz_ref): a judgment made by a reader of the book, not by searching it
for the question's words, which is what makes a test of a search unfair to
every way of searching but by words.  They are put, as a reader would put
them, without their answers, to each route of ubsite/meaning.py alone and to
fusions of them, and a route is right where one of the paragraphs judged is
among its first ten.

Three sets, reported apart, because they are not alike:

  the edition's   the questions the British Study Edition asked: of memory,
                  worded close to the text they were drawn from, which
                  flatters a search by words;
  Paper 1's 28    written for the site on 2026-11-22 to test comprehension:
                  a question in other words than its paragraph's.  The
                  honest test, and a small one;
  in Russian      tests/fixtures/meaning-ru.tsv: Paper 1's and a sample of
                  the edition's, put in Russian, the answer still a paragraph
                  of the English text.

The vectors of the questions are kept in var/embed/bench.npz, by the hash of
each, so that a change to the fusion is tried in a second.

With --ask, no test: the passages the fusion returns for each question,
with the route that brought each, to be read.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ubsite import meaning                        # noqa: E402

UB = ROOT / "var" / "ub.db"
WORK = ROOT / "var" / "embed"
KEPT = WORK / "bench.npz"
OUT = WORK / "bench.md"
RU = ROOT / "tests" / "fixtures" / "meaning-ru.tsv"
PAPER1 = range(823, 851)          # Paper 1's 28, written for the site (data/quiz/001.toml)
AT = (1, 3, 10, 20)               # among the first so many
DEEP = 50                         # as far as a list is read, for the mean reciprocal rank

# What is tried: a name, and each route's weight in the fusion.  The first of
# the fusions is the site's own (ubsite/meaning.py WEIGHTS).
TRIALS = [
    ("by meaning alone", {"para": 1}),
    ("through the index alone", {"index": 1}),
    ("by words alone", {"words": 1}),
    ("by words alone, without stems", {"words0": 1}),
    ("the study notes' paragraphs alone", {"note": 1}),
    ("**meaning + index x0.5 + words** (the site's)", dict(meaning.WEIGHTS)),
    ("meaning + index + words", {"para": 1, "index": 1, "words": 1}),
    ("meaning + words", {"para": 1, "words": 1}),
    ("meaning + index", {"para": 1, "index": 1}),
    ("meaning x2 + index + words", {"para": 2, "index": 1, "words": 1}),
    ("meaning + index + words x0.5", {"para": 1, "index": 1, "words": 0.5}),
    ("meaning + index x0.5 + words + notes", {"para": 1, "index": 0.5, "words": 1, "note": 1}),
]


def questions(ub: sqlite3.Connection) -> list[dict]:
    """Every question the quiz answers by the text: its words, and the
    paragraphs judged to answer it."""
    judged: dict[int, set[int]] = {}
    for qid, a, z in ub.execute("SELECT question_id, paragraph_id, paragraph_last_id FROM quiz_ref"):
        judged.setdefault(qid, set()).update(range(a, (z or a) + 1))
    out = []
    for qid, paper, text in ub.execute(
            "SELECT id, paper_n, text FROM quiz_question WHERE state = 'text' ORDER BY id"):
        out.append({"id": qid, "paper": paper, "q": text, "judged": judged[qid],
                    "set": "Paper 1's 28" if qid in PAPER1 else "the edition's"})
    return out


def russian(qs: list[dict]) -> list[dict]:
    """The same questions in Russian, where the file has them."""
    if not RU.is_file():
        return []
    by = {x["id"]: x for x in qs}
    out = []
    for line in RU.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        qid, text = line.split("\t")
        x = by[int(qid)]
        out.append({**x, "q": text, "set": "in Russian: " + x["set"]})
    return out


def vectors(texts: list[str], em_of) -> dict[str, object]:
    """Each text's vector, from what is kept or made now."""
    import numpy as np
    key = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
    kept = dict(np.load(KEPT)) if KEPT.is_file() else {}
    new = [t for t in dict.fromkeys(texts) if key(t) not in kept]
    if new:
        em = em_of()
        t0 = time.time()
        for t in new:
            kept[key(t)] = em.one(t)
        print(f"{len(new):,} questions embedded in {time.time() - t0:.0f} s", flush=True)
        np.savez(KEPT, **kept)
    return {t: kept[key(t)] for t in texts}


def place(ranked: list[int], judged: set[int]) -> int | None:
    """Where the first paragraph judged right stands, from 1; None beyond DEEP."""
    for i, pid in enumerate(ranked[:DEEP], 1):
        if pid in judged:
            return i
    return None


def score(places: list[int | None]) -> dict:
    n = len(places)
    out = {f"@{k}": sum(p is not None and p <= k for p in places) / n for k in AT}
    out["mrr"] = sum(1 / p for p in places if p) / n
    return out


def run(a) -> int:
    ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
    units = meaning.Units()
    qs = questions(ub)
    qs += russian(qs)
    vs = vectors([x["q"] for x in qs], meaning.Embedder)
    t0 = time.time()
    for x in qs:
        r = meaning.routes(units, ub, vs[x["q"]], x["q"])
        x["found"] = r["found"]
        x["found"]["words0"] = meaning.by_words(ub, x["q"], meaning.language(x["q"]), stems=False)
    per = (time.time() - t0) / len(qs) * 1000
    sets = list(dict.fromkeys(x["set"] for x in qs))
    lines = ["# Search by meaning: the retrieval test", "",
             f"{time.strftime('%Y-%m-%d')}; {units.meta['n']} units, recipe {units.meta['recipe']}, "
             f"{units.meta['model']} at {units.meta['rev'][:8]}; the routes of one question {per:.0f} ms "
             f"(the question's own embedding apart).", "",
             "A question is right where a paragraph judged to answer it is among the first so many; "
             f"MRR is the mean of one over the place of the first such, read to {DEEP}.", ""]
    for name in sets:
        mine = [x for x in qs if x["set"] == name]
        lines += [f"## {name} ({len(mine)} questions)", "",
                  "| | " + " | ".join(f"first {k}" for k in AT) + " | MRR |", "|---|" + "---:|" * (len(AT) + 1)]
        for trial, weights in TRIALS:
            s = score([place([p for p, _ in meaning.fuse(x["found"], weights)], x["judged"]) for x in mine])
            lines.append(f"| {trial} | " + " | ".join(f"{100 * s[f'@{k}']:.1f}%" for k in AT) + f" | {s['mrr']:.3f} |")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


def ask(a) -> int:
    """What a reader would be shown, as text."""
    ub = sqlite3.connect(f"file:{UB}?mode=ro", uri=True)
    units, em = meaning.Units(), meaning.Embedder()
    for q in a.ask:
        t0 = time.time()
        r = meaning.routes(units, ub, em.one(q), q)
        ms = (time.time() - t0) * 1000
        print(f"\n=== {q}   ({ms:.0f} ms)")
        print("  index:", "; ".join(units.label[e] for e in r["entries"][:6]))
        for pid, worth in meaning.fuse(r["found"])[:a.n]:
            ref = units.para[pid][0]
            why = [k for k in ("para", "note", "index", "words") if pid in r["found"][k][:DEEP]]
            text = ub.execute("SELECT text FROM paragraph WHERE id = ?", (pid,)).fetchone()[0]
            print(f"  {ref:10} {worth:.4f} {'+'.join(why):22} {text[:150]}")
        print("  kjv:", "; ".join(units.label[k] for k in r["kjv"][:5]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ask", action="append", help="a question to answer, in place of the test")
    ap.add_argument("-n", type=int, default=12, help="passages shown for a question asked (12)")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    return ask(a) if a.ask else run(a)


if __name__ == "__main__":
    raise SystemExit(main())
