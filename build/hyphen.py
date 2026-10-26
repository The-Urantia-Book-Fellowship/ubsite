"""Where a word may break at the end of a line: where the book lets it.

The press sets the text with XeLaTeX and polyglossia's `english`, which is
Knuth's original hyphen.tex -- not hyph-en-us, not usenglishmax -- with
hyphenmins 2/3 (gloss-english.ldf), plus the \\hyphenation list
tex/urantia-hyphen-en.tex, plus the source's own \\- in the odd word.  This
module runs that model.  It is the TeX class of the press's
tools/hyphen_audit.py, which at fc7323b predicted every one of the 23,719
breaks the book printed in source words; tools/hyphen_print.py holds this copy
to the same printed book.

The rules, all TeX's:

  * Liang's algorithm on the patterns, after Knuth's own 14 exceptions in
    hyphen.tex (`present' and `project' never break by pattern);
  * the press's list over both, matched case-insensitively, a word listed
    twice taking the LATER entry;
  * no break with fewer than 2 letters before it or 3 after, listed or not
    (`nev-er' can never break);
  * a word is a run of ASCII letters, so an entry governs its possessive too
    (Mi-chael's prints from Mi-cha-el) and `twenty-five' is two words;
  * a \\- in the source overrides all of that for its one occurrence: the
    word breaks there and nowhere else, minimums or not.  That is how the press
    divides `to pre-sent' from `the pres-ent age' (tools/verb_breaks.py).

pyphen and the browsers' dictionaries do something else: pyphen's en_US,
which is LibreOffice's and Firefox's, disagrees with 387 of the list's 523
words (su-per-crea-t-u-ral, mo-ron-ti-aize).

A translation is set by its own TeX, and so hyphenated as that TeX would
(Tigran, 2026-10-26): both Russian ones load polyglossia's `russian`, which is
hyph-ru with hyphenmins 2/2 (gloss-russian.ldf), plus each translation's own
\\hyphenation list (build/translation.py reads it).  `RUSSIAN` is that model.
A word written with a stress mark, U+0301, is left whole: TeX's lccode for the
mark is 0, and how it would cut the word around it is not worth the copy.
"""

from __future__ import annotations

import dataclasses
import functools
import pathlib
import re

LEFT, RIGHT = 2, 3                 # \lefthyphenmin, \righthyphenmin for english
PATTERNS = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "tex" / "hyphen.tex"
RU_PATTERNS = PATTERNS.with_name("hyph-ru.tex")

_WORD = re.compile(r"[^\W\d_]+")   # a run of letters, any script
_ASCII = re.compile(r"[A-Za-z]+")
# A Russian word, with any stress mark written in it (U+0301 is no letter to \w).
_RU_WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|\u0301)*")
STRESS = "\u0301"


@dataclasses.dataclass(frozen=True, slots=True)
class Language:
    """A pattern file, its minimums, and which letter runs it breaks."""
    patterns: pathlib.Path
    encoding: str
    left: int
    right: int
    ascii_only: bool         # English: a run with an accented letter is left whole


ENGLISH = Language(PATTERNS, "latin-1", LEFT, RIGHT, True)
RUSSIAN = Language(RU_PATTERNS, "utf-8", 2, 2, False)


def points_of(entry: str) -> frozenset[int]:
    """`hap-pi-ness' -> {3, 5}: the break positions an entry writes."""
    parts = entry.split("-")
    return frozenset(len("".join(parts[:k])) for k in range(1, len(parts)))


@functools.lru_cache(maxsize=None)
def _load_knuth(path: pathlib.Path = PATTERNS, encoding: str = "latin-1"):
    src = path.read_text(encoding=encoding)
    body = re.sub(r"%.*", "", src.split("\\patterns{")[1].split("}")[0])
    pats = {}
    for p in body.split():
        letters = re.sub(r"\d", "", p)
        nums = [0] * (len(letters) + 1)
        i = 0
        for ch in p:
            if ch.isdigit():
                nums[i] = int(ch)
            else:
                i += 1
        pats[letters] = nums
    exc = {e.replace("-", "").lower(): points_of(e)
           for e in re.sub(r"%.*", "", src.split("\\hyphenation{")[1].split("}")[0]).split()}
    return pats, exc


class Hyphenator:
    """The book's hyphenation.  `entries` is the press's list, in file order;
    for a translation, its own, with `language` the one its TeX loads."""

    def __init__(self, entries, language: Language = ENGLISH):
        self.lang = language
        self.pats, self.knuth_exc = _load_knuth(language.patterns, language.encoding)
        self.entries: dict[str, frozenset[int]] = {}
        for raw in entries:                      # a later entry wins, as in TeX
            self.entries[raw.replace("-", "").lower()] = points_of(raw)
        self._cache: dict[str, frozenset[int]] = {}

    def patterns(self, w: str) -> frozenset[int]:
        """Knuth's points for lower-case w, his exceptions included, no minimums."""
        if w in self.knuth_exc:
            return self.knuth_exc[w]
        word = "." + w + "."
        v = [0] * (len(word) + 1)
        for i in range(len(word)):
            for j in range(i + 1, min(len(word), i + 10) + 1):
                n = self.pats.get(word[i:j])
                if n:
                    for k, x in enumerate(n):
                        v[i + k] = max(v[i + k], x)
        return frozenset(i for i in range(1, len(w)) if v[i + 1] % 2)

    def word(self, w: str) -> frozenset[int]:
        """Where TeX may break the word w, absent a \\- in it."""
        lw = w.lower()
        got = self._cache.get(lw)
        if got is None:
            written = self.entries[lw] if lw in self.entries else self.patterns(lw)
            got = frozenset(p for p in written
                            if self.lang.left <= p <= len(lw) - self.lang.right)
            self._cache[lw] = got
        return got

    def points(self, text: str, spans) -> list[int]:
        """Every offset in text before which the line may break with a hyphen.

        `spans` are the paragraph's; its `shy` spans are the source's \\-.
        A letter run that is not all ASCII is left whole: TeX would read the
        accented letter into the word, and these patterns know no such word
        (two in the book, `attachés' and `365¼').
        """
        shy = sorted(s.start for s in spans if s.kind == "shy")
        out = []
        for m in (_WORD if self.lang.ascii_only else _RU_WORD).finditer(text):
            if self.lang.ascii_only and not _ASCII.fullmatch(m.group()):
                continue
            if STRESS in m.group():
                continue
            a, b = m.span()
            own = [p for p in shy if a < p < b]
            if own:
                out.extend(own)
            else:
                out.extend(a + p for p in sorted(self.word(m.group())))
        return out
