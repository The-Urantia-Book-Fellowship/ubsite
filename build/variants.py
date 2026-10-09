"""A 1955 note that differs from the text only in its italics.

Most `\\fnc` notes give other words, and the change is seen at once.  Six give
the same words with other italics.  102:3.5's note reads "*true reality*; while"
against the text's "*true reality;* while", and a reader can look at the pair for
half an hour without seeing that one semicolon is upright and the other slants
(Tigran, 2026-10-09).  For these the build works out which characters changed,
says so in words (`footnote.gloss`), and marks them in the note.

A note gives the 1955 reading of the words just before its anchor, so a note
whose text equals those words differs from them in nothing but its spans.
"""

from __future__ import annotations

import dataclasses

# A run that is one of these is named, not quoted: "the semicolon" reads, and
# a quoted ";" is as hard to see as the thing it explains.
NAMES = {";": "semicolon", ":": "colon", ",": "comma", ".": "period",
         "?": "question mark", "!": "exclamation mark", "’": "apostrophe"}


@dataclasses.dataclass(frozen=True, slots=True)
class Mark:
    """A run of the note to mark; the renderer wraps it in <mark class="chg">."""
    start: int
    end: int
    kind: str = "chg"


def _italic(spans, start: int, end: int) -> list[bool]:
    on = [False] * (end - start)
    for s in spans:
        if s.kind == "em":
            for i in range(max(s.start, start), min(s.end, end)):
                on[i - start] = True
    return on


def italics_only(ptext: str, pspans, anchor: int, ntext: str, nspans):
    """(gloss, marks) for a note whose words are the text's, else None.

    Returns ("", []) when the words are the same and so are the italics: a note
    that says nothing a reader can see, which the caller reports as a problem.
    """
    start = anchor - len(ntext)
    if start < 0 or ptext[start:anchor] != ntext:
        return None
    now, then = _italic(pspans, start, anchor), _italic(nspans, 0, len(ntext))
    runs: list[list[int]] = []                    # [start, end, italic in 1955]
    for i, (a, b) in enumerate(zip(now, then)):
        if a == b:
            continue
        if runs and runs[-1][1] == i and runs[-1][2] == b:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, b])
    # A space set in italics looks like one that is not: mark only what shows.
    for r in runs:
        while r[0] < r[1] and ntext[r[0]].isspace():
            r[0] += 1
        while r[1] > r[0] and ntext[r[1] - 1].isspace():
            r[1] -= 1
    runs = [r for r in runs if r[0] < r[1]]
    if not runs:
        return "", []
    whole = len(runs) == 1 and ntext[runs[0][0]:runs[0][1]] == ntext.strip()
    clauses = []
    for r in runs:
        then_, now_ = ("italic", "upright") if r[2] else ("upright", "italic")
        if whole:
            clauses.append(f"{then_} in 1955, {now_} here")
            continue
        piece = ntext[r[0]:r[1]]
        what = f"the {NAMES[piece]}" if piece in NAMES else f"“{piece}”"
        clauses.append(f"{what} is {then_} in 1955, {now_} here")
    return "; ".join(clauses), [Mark(r[0], r[1]) for r in runs]
