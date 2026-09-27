"""Every section title, line for line, against the press project's own HTML.

`misc/html/` is the independently verified second copy of the text.  Its
headings carry the printed line breaks as <br />, so this proves more than the
words: it proves where each title breaks.  Reading \\\\ as a space ran fifteen
titles' lines together, and left the [1ex] of a \\\\[1ex] behind as text, and
nothing checked a title at all.

The heading id names the section (U57_7_0).  p139's one heading over sections 9
and 10 is keyed by the second, and says "9. and 10." -- both numbers are taken.

Where the HTML breaks a line the TeX does not, the difference is declared in
tests/known-title-deltas.tsv, and must be exactly that set.
"""

from __future__ import annotations

import html
import pathlib
import re

from ..readers._io import read_text
from ..render import title as render_title

RE_H2 = re.compile(r'<h2 id="U(\d+)_(\d+)_0">(.*?)</h2>', re.S)
RE_NUM = re.compile(r"^((?:\d+|[IVXL]+)\.)(?: and (\d+)\.)?\s*")
RE_BR = re.compile(r"<br\s*/?>")
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def _number(label: str) -> int:
    """'7.' -> 7, and the Foreword's 'XII.' -> 12."""
    s = label.rstrip(".")
    if s.isdigit():
        return int(s)
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return n


def load_press_titles(htmldir: pathlib.Path) -> dict:
    """{(paper, section): (line, line, ...)} from every paper's HTML."""
    out = {}
    for f in sorted(htmldir.glob("*-Paper[0-9][0-9][0-9].html")):
        for m in RE_H2.finditer(read_text(f)):
            paper = int(m.group(1))
            lines = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
                     for x in RE_BR.split(m.group(3))]
            num = RE_NUM.match(lines[0])
            lines[0] = lines[0][num.end():] if num else lines[0]
            lines = tuple(x for x in lines if x)
            numbers = {int(m.group(2))}
            if num:
                numbers.add(_number(num.group(1)))
                if num.group(2):
                    numbers.add(int(num.group(2)))
            for n in numbers:
                out[(paper, n)] = lines
    return out


def _plain(lines):
    return render_title("\n".join(lines))[0] if lines else None


def run(papers, press: dict, deltas: dict[str, str] | None = None,
        limit: int = 10) -> int:
    ours = {(p.n, n): tuple(t.split("\n"))
            for p in papers for n, t in p.sections.items() if n > 0}
    declared = {tuple(int(x) for x in ref.split(":")) for ref in (deltas or {})}
    ok, diff, excused, stale = 0, [], 0, []
    for key in sorted(set(ours) | set(press)):
        same = ours.get(key) == press.get(key)
        if key in declared:
            # Excused only if the one difference is a break the TeX leaves out:
            # the same words, joined the same way.
            if same or _plain(ours.get(key)) != _plain(press.get(key)):
                stale.append(key)
            else:
                excused += 1
        elif same:
            ok += 1
        else:
            diff.append(key)
    for key in stale:
        print(f"  declared delta {key[0]}:{key[1]} no longer differs only by a break"
              f"\n    ours  {ours.get(key)}\n    press {press.get(key)}")
    for key in diff[:limit]:
        print(f"\n  {key[0]}:{key[1]}")
        print(f"    ours  {ours.get(key)}")
        print(f"    press {press.get(key)}")
    broken = sum(1 for v in ours.values() if len(v) > 1)
    print(f"titles: {ok} agree, {excused} declared deltas, {len(diff)} differ   "
          f"(ours {len(ours)}, press {len(press)}; {broken} set on more than one line)")
    return 1 if diff or stale else 0
