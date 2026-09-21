"""Phase 2 gate: our italic spans must match an independent extraction, by offset.

The plain-text oracle carries no markup, so it cannot check a single span.  The
press project's own text-verify artifacts can: they record italics as
``[[start, end]]`` code-point pairs into the same normalized text, which is
exactly the form this project stores.

A matching *total* would prove nothing -- two extractions can agree on how many
italic runs exist and disagree about which words they cover.  This compares the
offsets.
"""

from __future__ import annotations

import json
import pathlib
import sys


def load_press_italics(artdir: pathlib.Path) -> dict:
    """{(paper, section, verse): [(start, end), ...]} from press's own extract."""
    out = {}
    for f in sorted(artdir.glob("p[0-9][0-9][0-9].jsonl")):
        for line in f.open(encoding="utf-8"):
            r = json.loads(line)
            if r.get("_kind") == "paper":
                continue
            out[(r["paper"], r["section"], r["verse"])] = \
                [tuple(x) for x in r.get("italics", [])]
    return out


def run(papers, press: dict, limit: int = 10) -> int:
    ours = {(q.paper, q.section, q.n): q for p in papers for q in p.paragraphs}
    ok = diff = missing = 0
    examples = []
    for key, want in press.items():
        q = ours.get(key)
        if q is None:
            missing += 1
            continue
        got = sorted((s.start, s.end) for s in q.ex.spans if s.kind == "em")
        want = sorted(want)
        if got == want:
            ok += 1
        else:
            diff += 1
            if len(examples) < limit:
                examples.append((key, got, want, q.ex.text))
    for key, got, want, text in examples:
        print(f"\n  {key[0]}:{key[1]}.{key[2]}")
        print(f"    ours  {got}  -> {[text[a:b] for a, b in got]}")
        print(f"    press {want}  -> {[text[a:b] for a, b in want]}")
    n_ours = sum(1 for p in papers for q in p.paragraphs
                 for s in q.ex.spans if s.kind == "em")
    n_press = sum(len(v) for v in press.values())
    print(f"\nitalics: {ok} paragraphs agree, {diff} differ, {missing} not in ours"
          f"   (spans: ours {n_ours}, press {n_press})")
    return 0 if (diff == 0 and missing == 0) else 1
