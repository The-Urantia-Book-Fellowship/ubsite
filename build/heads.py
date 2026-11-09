"""The A-Z headwords by name, for whatever names one: a See or See also, a q.v.,
an Appendix B-F row.

xref.fold() forgives case and punctuation, as a reader does, and so it
collides (CLAUDE.md, trap 8): 4,736 headwords make 4,734 keys, "Ammonites" the
tribe and "ammonites" the fossils one of them, "Absolutes" and "absolutes" the
other.  Keyed by the fold alone, the first headword won, and until 2026-11-09
"animals › types named. See … ammonites" and "marine life › types named. See
ammonites" went to the tribe.  So a name is looked up as it is written first,
and by its fold only where no headword is written so.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "vendor" / "index"))
import xref  # noqa: E402


class Heads:
    """Headword ids by name: `rows` are (id, headword) in id order, and the
    first of two headwords written alike, or folding alike, keeps the name."""

    def __init__(self, rows):
        self.exact: dict[str, int] = {}
        self.folded: dict[str, int] = {}
        for i, h in rows:
            self.exact.setdefault(h.strip(), i)
            self.folded.setdefault(xref.fold(h), i)

    def get(self, name: str) -> int | None:
        h = self.exact.get(name.strip())
        return h if h is not None else self.folded.get(xref.fold(name))

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def __getitem__(self, name: str) -> int:
        h = self.get(name)
        if h is None:
            raise KeyError(name)
        return h
