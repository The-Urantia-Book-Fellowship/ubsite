"""The KJV's marginal notes, a gloss at a time, and where each stands.

A note of data/kjv/ is the margin of one verse: one gloss or several, each
`lemma: gloss.`, the lemma the verse's words it glosses, or their first words
and an ellipsis (`the light from...: Heb. between the light and between the
darkness.`).  The 1769 printing set a mark, a dagger for the Hebrew's words and
a double bar for another reading, before the first word of each lemma in the
verse, and the margin's gloss beside it; the site does the same, a mark and a
card to each gloss (Tigran, 2026-11-22, "Before, as 1769").

This module is pure: it splits a note into its glosses and finds a lemma's
words in a verse.  Where a lemma stands once in its verse and its psalm's
title, that is its place; where it stands more than once, or not at all, the
place is read and written in data/kjv/marks.tsv (build/bible.py reads it), and
a gloss with neither fails the build.  tools/kjv/compare.py and facsimile.py
read the notes through it too, so there is one parser.
"""

from __future__ import annotations

import dataclasses
import re

# A lemma: at the note's start or after a gloss's last stop, question or
# exclamation, the words before the first ": ", with no stop of their own; or
# their first words and an ellipsis, written "..." in the copy and "…" once
# expanded.  "Shupham…Hupham" is one lemma: two names of the verse, glossed
# together.
RE_LEMMA = re.compile(r"(?:^|(?<=[.?!] ))([^:.?!]+?(?:\.\.\.)?): ")
# Not a lemma: the second sentence of a gloss, `or, X: Y`; nor the words
# after an abbreviation's stop, `Eve: Heb. Chavah: that is Living.`, where
# "Chavah" is the gloss's, not the verse's.
RE_NOT = re.compile(r"(?:(?:Heb|Gr|Chaldee|Syr|i\.e)\b|or,)")
RE_ABBR = re.compile(r"\b(?:Heb|Gr|Chald|Syr|i\.e)\. $")
RE_WORD = re.compile(r"[\w’']+")


@dataclasses.dataclass
class Gloss:
    lemma: str | None          # None: a note that names no words of its verse
    start: int                 # its place in the note's text
    end: int
    text: str
    spans: list                # the note's spans inside it, rebased


def glosses(text: str, spans=()) -> list[Gloss]:
    """A note's text and spans -> its glosses, in the note's order.  A span
    across two glosses raises ValueError: nothing of the copy does that."""
    found = [m for m in RE_LEMMA.finditer(text)
             if not RE_NOT.match(m[1]) and not RE_ABBR.search(text[:m.start()])]
    cuts = [m.start() for m in found]
    lemmas = [m[1] for m in found]
    # Words before the first lemma are the first gloss's (Psa 148:1, "Praise
    # ye the Lord. Praise: Heb. Hallelujah, etc."); a note with none is one
    # gloss that names no words.
    if not cuts:
        cuts, lemmas = [0], [None]
    cuts[0] = 0
    out = []
    for i, (a, lemma) in enumerate(zip(cuts, lemmas)):
        b = cuts[i + 1] if i + 1 < len(cuts) else len(text)
        t = text[a:b].rstrip()
        b = a + len(t)
        mine = []
        for s in spans:
            if s.start >= a and s.end <= b and not (s.start == s.end == b and i + 1 < len(cuts)):
                mine.append((s, s.start - a, s.end - a))
            elif s.start < b and s.end > a:
                raise ValueError(f"a span {s.start}..{s.end} across the glosses at {a}..{b}: {text!r}")
        out.append(Gloss(lemma, a, b, t, mine))
    return out


def words(s: str) -> list[str]:
    return [w.lower().replace("’", "'") for w in RE_WORD.findall(s)]


def lemma_words(lemma: str) -> list[str]:
    """The words a lemma names in its verse: all of them, or those before its
    first ellipsis, which stands for the rest."""
    return words(re.split(r"…|\.\.\.", lemma)[0])


def same(word: str, want: str) -> bool:
    """A verse's word is the lemma's, or it with the possessive's ending: the
    note to 2Sa 6:6 glosses "Nachon" in "Nachon’s threshingfloor"."""
    return word == want or word in (want + "'s", want + "'")


def find(seq: list[str], parts: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """Each place where the words `seq` stand one after another, as (part,
    offset of the first word's first letter), the parts in order."""
    out = []
    if not seq:
        return out
    for part, text in parts:
        ws = [(m[0].lower().replace("’", "'"), m.start()) for m in RE_WORD.finditer(text)]
        for i in range(len(ws) - len(seq) + 1):
            if all(same(ws[i + k][0], seq[k]) for k in range(len(seq))):
                out.append((part, ws[i][1]))
    return out


def occurrences(lemma: str, parts: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """Where a lemma stands in its verse: `parts` is [("title", a psalm's
    title), ("text", the verse)], the title only where the verse has one."""
    return find(lemma_words(lemma), parts)


def lemma_key(lemma: str | None) -> str:
    """A lemma as data/kjv/marks.tsv names it: as the copy writes it, "..."
    and ', or "-" for a gloss that has none."""
    return "-" if lemma is None else lemma.replace("…", "...").replace("’", "'")


RE_PLACE = re.compile(r"(?P<n>[1-9]\d*)|at (?P<at>[^#,]+?)(?: #(?P<k>[1-9]\d*))?|(?P<end>end)")


def places_ok(spec: str) -> bool:
    """A place column of data/kjv/marks.tsv: one place, or one to each gloss
    where a verse's note glosses one lemma twice (Dan 12:5's two "bank"), in
    the note's order, `1, 2`."""
    return all(RE_PLACE.fullmatch(x) for x in spec.split(", "))


def place(spec: str, lemma: str | None, parts: list[tuple[str, str]]) -> tuple[str, int] | None:
    """A place data/kjv/marks.tsv writes -> (part, offset), or None where the
    verse has no such place.  `2` the lemma's second place in the title and the
    verse; `at Eve` before the first place of other words of the verse, `at
    from #3` before their third; `end` after the verse's last word."""
    m = RE_PLACE.fullmatch(spec)
    if not m:
        return None
    if m["end"]:
        return (parts[-1][0], len(parts[-1][1]))
    if m["n"]:
        occ = occurrences(lemma, parts) if lemma else []
        n = int(m["n"])
    else:
        occ = find(words(m["at"]), parts)
        n = int(m["k"] or 1)
    return occ[n - 1] if n <= len(occ) else None
