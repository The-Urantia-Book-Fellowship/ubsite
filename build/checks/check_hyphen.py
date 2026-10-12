"""Gate the soft hyphens: the book's breaks, and nothing else.

paragraph.html_hy is paragraph.html with a U+00AD wherever the book lets a word
break (build/hyphen.py).  This holds it to that, from the outside:

  * removing every U+00AD gives `html` byte for byte, so it carries the same
    text and markup, and the round-trip gate on `html` covers it too;
  * a soft hyphen stands only inside a run of ASCII letters;
  * every \\- in the source is one, and a word carrying a \\- breaks nowhere
    else;
  * every other break leaves at least 2 letters before it and 3 after;
  * every word the press's list names breaks exactly where the entry says,
    less the minimums -- read here from the list itself, not the model.

That the model's breaks are the ones the book printed is tools/hyphen_print.py,
against a PDF of the book: not a gate, because that PDF is built, not kept.
"""

from __future__ import annotations

import html
import re

from ..hyphen import LEFT, RIGHT, points_of

SHY = "­"
_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[^\W\d_]+")


def _offsets(h: str) -> list[int]:
    """Where the soft hyphens of h fall, as offsets into its text."""
    out, n = [], 0
    for ch in html.unescape(_TAG.sub("", h)):
        if ch == SHY:
            out.append(n)
        else:
            n += 1
    return out


def run(con, entries) -> int:
    listed = {}
    for raw in entries:                          # a later entry wins, as in TeX
        listed[raw.replace("-", "").lower()] = points_of(raw)
    shy_at: dict[int, list[int]] = {}
    for pid, start in con.execute("SELECT paragraph_id, start FROM span WHERE kind='shy'"):
        shy_at.setdefault(pid, []).append(start)

    fails: dict[str, list[str]] = {k: [] for k in (
        "differs from html but for its soft hyphens",
        "a soft hyphen outside a word",
        "a \\- with no soft hyphen",
        "a word with a \\- breaks elsewhere too",
        "a break under the minimums",
        "a listed word not broken as listed")}
    n = total = words_listed = 0
    for pid, ref, text, h, hy in con.execute(
            "SELECT id, ref, text, html, html_hy FROM paragraph ORDER BY ord"):
        n += 1
        if hy.replace(SHY, "") != h:
            fails["differs from html but for its soft hyphens"].append(ref)
            continue
        at = _offsets(hy)
        total += len(at)
        got = set(at)
        own = set(shy_at.get(pid, ()))
        for p in sorted(own - got):
            fails["a \\- with no soft hyphen"].append(f"{ref} @{p}")
        inside = set()
        for m in _WORD.finditer(text):
            a, b = m.span()
            here = {p - a for p in got if a < p < b}
            inside |= {a + p for p in here}
            mine = {p - a for p in own if a < p < b}
            w = m.group().lower()
            if mine:
                if here != mine:
                    fails["a word with a \\- breaks elsewhere too"].append(f"{ref} {m.group()}")
                continue
            if any(p < LEFT or p > len(w) - RIGHT for p in here):
                fails["a break under the minimums"].append(f"{ref} {m.group()}")
            if w in listed and w.isascii():
                words_listed += 1
                want = {p for p in listed[w] if LEFT <= p <= len(w) - RIGHT}
                if here != want:
                    fails["a listed word not broken as listed"].append(f"{ref} {m.group()}")
            if here and not m.group().isascii():
                fails["a soft hyphen outside a word"].append(f"{ref} {m.group()}")
        for p in sorted(got - inside):
            fails["a soft hyphen outside a word"].append(f"{ref} @{p}")

    print(f"soft hyphens: {total:,} in {n:,} paragraphs; {sum(map(len, shy_at.values())):,}"
          f" of them the source's \\-; {words_listed:,} listed words as listed")
    bad = 0
    for name, where in fails.items():
        print(f"  {name:52} {len(where)}{'' if not where else '   FAIL  ' + ', '.join(where[:5])}")
        bad += bool(where)
    return 1 if bad else 0
