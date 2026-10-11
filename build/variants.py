"""A 1955 note must differ from the text it stands beside.

A note gives the 1955 reading of the words just before its anchor.  Most give
other words; six give the same words with other italics -- 102:3.5's note reads
"*true reality*; while" against the text's "*true reality;* while".  Until
2026-10-11 the build told those six in its own words ("the semicolon is upright
in 1955, italic here").  Each now carries the SRT Committee's own explanation
instead (build/srt.py), so the build only checks that a note says something: a
note with the text's words AND its italics is a defect in the press TeX.
"""

from __future__ import annotations


def _italic(spans, start: int, end: int) -> list[bool]:
    on = [False] * (end - start)
    for s in spans:
        if s.kind == "em":
            for i in range(max(s.start, start), min(s.end, end)):
                on[i - start] = True
    return on


def says_nothing(ptext: str, pspans, anchor: int, ntext: str, nspans) -> bool:
    """Has the note the very words before its anchor, italics and all?

    Spaces do not count: a space set in italics looks like one that is not.
    """
    start = anchor - len(ntext)
    if start < 0 or ptext[start:anchor] != ntext:
        return False
    now, then = _italic(pspans, start, anchor), _italic(nspans, 0, len(ntext))
    return all(a == b or ntext[i].isspace() for i, (a, b) in enumerate(zip(now, then)))
