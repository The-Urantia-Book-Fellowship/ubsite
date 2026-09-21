"""Align the British Study Edition's paragraph numbering to the Uversa Press text.

The two editions diverge for one mechanical reason.  Press writes a section
divider as a bare macro::

    \\separatorline

while the study edition gives it a paragraph number of its own::

    \\vs p031 10:22 \\separatorline

which consumes a number and shifts every later paragraph in that section by one.
There are ten such lines, in p031, p056, p120, p134 and (six times) p144.
Because the Index is built from the press text, the study edition's numbers for
those sections -- including all of Paper 144's prayers, which are heavily
indexed -- do not currently match the citations that point at them.

This script strips the number from each divider and renumbers the remainder of
its section down to close the gap, in ``\\vs``, ``\\vsmark`` and
``\\printvssuper`` alike.  It writes nothing unless --apply is given.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

RE_VS      = re.compile(r"^(\\vs p(\d+) (\d+):(\d+) ?)(.*)$")
RE_SEP     = re.compile(r"^\\separator(line|short)\b")
RE_MARK    = re.compile(r"\\vsmark\{(\d+)\}\{(\d+)\}")
RE_SUPER   = re.compile(r"\\printvssuper\{(\d+)\}")
RE_BIBREF  = re.compile(r"(\\bibref\[)([^\]]*)(\]\{p)(\d+) (\d+):(\d+)(\})")


def plan(path: pathlib.Path):
    """Return (drop_linenos, shift[(section)] -> sorted list of removed numbers)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    drop, removed = [], {}
    for i, raw in enumerate(lines):
        m = RE_VS.match(raw.strip())
        if m and RE_SEP.match(m.group(5).strip()):
            sec, num = int(m.group(3)), int(m.group(4))
            drop.append(i)
            removed.setdefault(sec, []).append(num)
    return lines, drop, removed


def remap(removed: dict[int, list[int]], sec: int, num: int) -> int:
    """New paragraph number after the removals in this section."""
    return num - sum(1 for r in removed.get(sec, ()) if r < num)


def process(path: pathlib.Path, apply: bool) -> list[str]:
    lines, drop, removed = plan(path)
    if not drop:
        return []
    dropset = set(drop)
    changes, out = [], []
    for i, raw in enumerate(lines):
        if i in dropset:
            m = RE_VS.match(raw.strip())
            body = m.group(5)
            indent = raw[:len(raw) - len(raw.lstrip())]
            changes.append(f"  {path.name}:{i+1}  -{raw.strip()}")
            changes.append(f"  {path.name}:{i+1}  +{body}")
            out.append(indent + body)
            continue

        new = raw
        m = RE_VS.match(raw.strip())
        if m:
            sec, num = int(m.group(3)), int(m.group(4))
            nn = remap(removed, sec, num)
            if nn != num:
                new = raw.replace(f"\\vs p{m.group(2)} {sec}:{num} ",
                                  f"\\vs p{m.group(2)} {sec}:{nn} ", 1)
        def _mark(mo):
            s, n = int(mo.group(1)), int(mo.group(2))
            return "\\vsmark{%d}{%d}" % (s, remap(removed, s, n))
        new2 = RE_MARK.sub(_mark, new)
        if new2 != new:
            new = new2
        if new != raw:
            changes.append(f"  {path.name}:{i+1}  -{raw.strip()[:88]}")
            changes.append(f"  {path.name}:{i+1}  +{new.strip()[:88]}")
        out.append(new)

    if apply:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changes


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("texdir")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    d = pathlib.Path(a.texdir)
    total = 0
    for f in sorted(d.glob("p[0-9]*.tex")):
        ch = process(f, a.apply)
        if ch:
            print(f"\n=== {f.name} ===")
            print("\n".join(ch))
            total += len(ch) // 2
    print(f"\n{'APPLIED' if a.apply else 'DRY RUN'}: {total} line(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
