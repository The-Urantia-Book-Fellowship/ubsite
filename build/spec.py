"""The action vocabulary for a *rendering* extractor.

The press project's own table (vendor/press/macros.py) is tuned for proving
text equality against an independent HTML copy, so it deliberately flattens
everything that carries only presentation: ``\\textcolor`` keeps its argument
and loses the colour, ``\\fnc`` is dropped whole, ``\\pc`` vanishes.

For a website those three are exactly the interesting ones -- they are the words
of Jesus, the 1955 first-edition reading, and the paragraph grouping of the
original printing.  So this module adds actions that *keep* the distinction,
while emitting byte-identical plain text.
"""

from __future__ import annotations

import dataclasses

# Actions that emit into the plain text stream
STRIP = "STRIP"                  # emit nothing
EMIT_TEXT = "EMIT_TEXT"          # emit a fixed literal
EMIT_ARG = "EMIT_ARG"            # emit argument `which`, expanded
EMIT_SUP = "EMIT_SUP"            # superscript (ordinals inline, exponents with ^)
SPAN = "SPAN"                    # emit argument `which`, and record a span over it
MARK = "MARK"                    # emit argument `which`, record a ZERO-WIDTH span at its start
NOTE = "NOTE"                    # emit NOTHING; record a note anchored at the cursor
FLAG = "FLAG"                    # emit nothing; set a paragraph-level flag
STRUCTURAL = "STRUCTURAL"        # handled by the paper state machine, not here

ALL_ACTIONS = {STRIP, EMIT_TEXT, EMIT_ARG, EMIT_SUP, SPAN, MARK, NOTE, FLAG, STRUCTURAL}

# The closed span vocabulary.  A CHECK constraint in the schema mirrors this.
SPAN_KINDS = {
    "em",          # \bibemph, \textit      -- semantic emphasis
    "redletter",   # \textcolor{ubdarkred}  -- the words of Jesus
    "supplied",    # KJV italics            -- words supplied by the translators
    "sup",         # \ts
    "sc",          # \textsc
    "ul",          # \bibtextul
    "listmark",    # \ublistelem            -- the label is real text the index quotes
    "dotleader",   # \bibdf                 -- zero width; splits a pseudo-table row
    "lang",        # \textgreek/heb/arm/chinese
    "link",        # \bibref                -- carries a citation in attr
    "fnref",       # zero width; a footnote anchor
    "url",         # \myurl
    "nobreak",
    "shy",         # \-                     -- zero width; where the press lets this word break
}


@dataclasses.dataclass(frozen=True, slots=True)
class Spec:
    action: str
    opt: int = 0            # number of [..] optional args to consume
    args: int = 0           # number of {..} mandatory args to consume
    which: int = 1          # 1-based index of the arg to emit
    text: str = ""          # for EMIT_TEXT
    kind: str = ""          # for SPAN / MARK / NOTE / FLAG
    note: str = ""          # human-readable rationale

    def __post_init__(self) -> None:
        if self.action not in ALL_ACTIONS:
            raise ValueError(f"unknown action {self.action!r}")
        if self.action in (SPAN, MARK) and self.kind not in SPAN_KINDS:
            raise ValueError(f"{self.action} needs a span kind, got {self.kind!r}")
