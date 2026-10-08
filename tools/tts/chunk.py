"""Text in the pieces a voice model reads well: a sentence or two at a time.

The large models lose the thread over a long paragraph.  Bark simply stopped
after about 14 seconds; Higgs TTS 3 read 1:7.9's 145 words in 22 seconds where
Merritt Horn takes 57, leaving out two thirds.  Given a sentence or two at a
time -- and a long sentence halved at its clauses -- they read every word.

    chunks(text) -> ["In the minds of ... and deity.", "Human beings are ...", ...]
"""

from __future__ import annotations

import re

LIMIT = 200          # characters: about 35 words
SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[\"“‘A-Z])")
CLAUSE = re.compile(r"[,;:—] ?| (?=(?:which|that|who|whom|whose|where|when|as|and|but|or"
                    r"|because|while|though)\b)")


# A piece may not end on one of these.  Given "...up to the fullness of",
# Higgs TTS 3 never once ended cleanly -- eight seeds, eight readings that ran
# on past the text -- and a clause cut that strands half of "so that", "just
# as" or "those who" reads as badly.
WEAK = set("""a an the of to in on at by for with from into onto upon about over under
    through toward towards and or but nor so just even such those these this that which
    who whom whose as than is are was were be been being has have had do does did will
    would shall should can could may might must not no his her its their our your my
    all any each every some many much more most very""".split())


def weak_end(s: str) -> bool:
    words = re.findall(r"[\w’']+", s)
    return bool(words) and words[-1].lower() in WEAK


def halve(s: str, limit: int = LIMIT) -> list[str]:
    """A sentence over `limit` cut near its middle -- at punctuation if it has
    any there, else before a clause word, else at a space -- and each half
    again if need be, never leaving a half that ends on a WEAK word.  Cutting
    at the limit itself read "such terms as God, / divinity, and deity." and
    "the English language of / Urantia."."""
    if len(s) <= limit:
        return [s]
    mid, lo, hi = len(s) / 2, len(s) // 4, 3 * len(s) // 4
    cuts = [(m.end() if m.group(0).strip() else m.start(), bool(m.group(0).strip()))
            for m in CLAUSE.finditer(s) if lo <= m.start() <= hi]
    cuts = [(at, punct) for at, punct in cuts if punct or not weak_end(s[:at])]
    if cuts:
        at = min(cuts, key=lambda c: (not c[1], abs(c[0] - mid)))[0]   # punctuation first
    else:
        spaces = [m.start() for m in re.finditer(" ", s)]
        at = min([i for i in spaces if not weak_end(s[:i])] or spaces, key=lambda i: abs(i - mid))
    return halve(s[:at].strip(), limit) + halve(s[at:].strip(), limit)


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    """Sentences, joined while they fit in `limit`, the long ones halved."""
    out: list[str] = []
    for s in SENTENCE.split(text):
        for piece in halve(s, limit):
            if out and len(out[-1]) + len(piece) + 1 <= limit and out[-1][-1] in ".!?;:”’\"":
                out[-1] += " " + piece
            else:
                out.append(piece)
    return out
