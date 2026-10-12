"""The macro table for the Uversa Press edition.

Derived mechanically from the press project's own exhaustive inventory, then
overridden only where this project needs a distinction that theirs discards.

The derivation is the point: ``assert_covers_upstream()`` compares key sets, so
the day a new macro appears in the book, *this* build fails too instead of
quietly emitting whatever the tokenizer happened to do with it.
"""

from __future__ import annotations

import sys

from .spec import (EMIT_ARG, EMIT_SUP, EMIT_TEXT, FLAG, MARK, NOTE, SPAN,
                   STRIP, STRUCTURAL, Spec)

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "vendor" / "press"))
import macros as _upstream  # noqa: E402

# How the upstream action vocabulary maps onto ours.
_TRANSLATE = {
    "STRIP": lambda s: Spec(STRIP, s.opt, s.args, note=s.note),
    "EMIT_TEXT": lambda s: Spec(EMIT_TEXT, s.opt, s.args, text=s.text, note=s.note),
    "EMIT_ARG": lambda s: Spec(EMIT_ARG, s.opt, s.args, s.which, note=s.note),
    "EMIT_SUP": lambda s: Spec(EMIT_SUP, s.opt, s.args, s.which, note=s.note),
    "EMIT_ARG_ITALIC": lambda s: Spec(SPAN, s.opt, s.args, s.which, kind="em", note=s.note),
    "STRUCTURAL": lambda s: Spec(STRUCTURAL, s.opt, s.args, s.which, note=s.note),
}

# The overrides.  Each one recovers information the text-equality extractor
# deliberately throws away.  Plain-text output is unchanged by every one of
# them -- that is asserted separately (Phase 2 gate: text byte-identical).
OVERRIDES: dict[str, Spec] = {
    "textcolor": Spec(SPAN, args=2, which=2, kind="redletter",
                      note="THE WORDS OF JESUS. ubdarkred is defined {gray}{0.0} -- "
                           "black in print, so the web is the first place these are red."),
    "fnc": Spec(NOTE, args=1, kind="variant-1955",
                note="the 1955 First Edition reading at this point; unique to this "
                     "edition, absent from the SRT. Emits no text."),
    "pc": Spec(FLAG, opt=1, kind="gap_before",
               note="start of a blank-line-delimited group in the 1955 printing. "
                    "Typographic in print; the British edition prints it as a "
                    "visible section mark."),
    "ublistelem": Spec(SPAN, args=1, kind="listmark",
                       note="list label ('1.', 'a.', 'IV.'). NOT an <ol>: the marker "
                            "is real text the index quotes, so converting it would "
                            "change the text."),
    "bibdf": Spec(MARK, kind="dotleader", text=" ",
                  note="dot leader in a pseudo-table row. Emits the single space "
                       "that LaTeX's control-word scan swallows, and marks the "
                       "point so the row can be set as label/leader/value."),
    "-": Spec(MARK, kind="shy", text="",
              note="discretionary hyphen: where the press lets this one occurrence "
                   "break, and nowhere else in the word (to pre\\-sent against the "
                   "pres-ent age). Emits no text; build/hyphen.py reads the point."),
}


def build_table() -> dict[str, Spec]:
    table: dict[str, Spec] = {}
    for name, up in _upstream.TABLE.items():
        if name in OVERRIDES:
            table[name] = OVERRIDES[name]
            continue
        fn = _TRANSLATE.get(up.action)
        if fn is None:
            raise SystemExit(f"press_macros: upstream action {up.action!r} "
                             f"({name}) has no translation")
        table[name] = fn(up)
    return table


TABLE = build_table()
KNOWN_ENVIRONMENTS = set(_upstream.KNOWN_ENVIRONMENTS)
STARRED_FORMS = set(getattr(_upstream, "STARRED_FORMS", ()))
UNBRACED_LENGTH_MACROS = set(getattr(_upstream, "UNBRACED_LENGTH_MACROS", ()))
ITALIC_OPENING_MACROS = set(getattr(_upstream, "ITALIC_OPENING_MACROS", ()))


def assert_covers_upstream() -> list[str]:
    """Key-set equality with upstream.  A new macro upstream fails us too."""
    ours, theirs = set(TABLE), set(_upstream.TABLE)
    problems = []
    for missing in sorted(theirs - ours):
        problems.append(f"upstream has {missing!r}, we do not")
    for extra in sorted(ours - theirs):
        problems.append(f"we have {extra!r}, upstream does not")
    return problems


if __name__ == "__main__":
    bad = assert_covers_upstream()
    print(f"press table: {len(TABLE)} macros, {len(KNOWN_ENVIRONMENTS)} environments")
    print(f"overrides:   {', '.join(sorted(OVERRIDES))}")
    print("coverage:    " + ("OK" if not bad else "\n  " + "\n  ".join(bad)))
