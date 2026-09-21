"""Phase 1 gate: our text must equal an independently produced copy, exactly.

``../index/data/srt.jsonl`` was produced by a different parser, in a different
project, for a different purpose (validating 50,758 index citations).  If our
extractor agrees with it on all 14,586 paragraphs, character for character,
then two independent readings of the same LaTeX agree -- which is a far stronger
statement than any self-consistency check we could write.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata


def load_oracle(p: pathlib.Path) -> dict:
    return {(r["p"], r["s"], r["n"]): r["text"]
            for r in (json.loads(l) for l in p.open(encoding="utf-8"))}


def norm(s: str) -> str:
    """The final pass both sides agree to apply before comparison."""
    s = unicodedata.normalize("NFC", s)
    for ch in (" ", " ", " "):
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    s = s.replace(" — ", "—").replace(" —", "—").replace("— ", "—")
    return s.strip()


def load_deltas(p: pathlib.Path) -> dict[str, str]:
    """The recorded, arbitrated disagreements with the oracle."""
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        ref, code, *rest = line.split("\t")
        out[ref] = code
    return out


def run(papers, oracle: dict, deltas: dict[str, str] | None = None,
        limit: int = 12) -> int:
    deltas = deltas or {}
    ours = {(q.paper, q.section, q.n): q for p in papers for q in p.paragraphs}
    ok = miss = extra = diff = 0
    examples = []
    seen_deltas: set[str] = set()
    for k, want in oracle.items():
        got = ours.get(k)
        if got is None:
            miss += 1
            continue
        a, b = norm(got.ex.text), norm(want)
        if a == b:
            ok += 1
        else:
            ref = f"{k[0]}:{k[1]}.{k[2]}"
            if ref in deltas:
                seen_deltas.add(ref)
                continue
            diff += 1
            if len(examples) < limit:
                i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                         min(len(a), len(b)))
                examples.append((k, i, a[max(0, i-45):i+45], b[max(0, i-45):i+45]))
    extra = len(set(ours) - set(oracle))
    for k, i, a, b in examples:
        print(f"\n  {k[0]}:{k[1]}.{k[2]}  first difference at char {i}")
        print(f"    ours   ...{a}...")
        print(f"    oracle ...{b}...")
    stale = sorted(set(deltas) - seen_deltas)
    for ref in stale:
        print(f"  STALE DELTA {ref} ({deltas[ref]}) no longer differs -- "
              f"remove it from known-oracle-deltas.tsv", file=sys.stderr)
    for ref in sorted(seen_deltas):
        print(f"  declared delta  {ref:<12} {deltas[ref]}")
    print(f"\ntext: {ok} identical, {len(seen_deltas)} declared deltas, "
          f"{diff} undeclared, {miss} missing, {extra} extra "
          f"(oracle {len(oracle)}, ours {len(ours)})")
    return 0 if (diff == miss == extra == 0 and not stale) else 1
