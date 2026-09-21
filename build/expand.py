"""Expand a token list into (plain text, spans, notes).

The contract, and the reason this file is worth reading carefully:

  * The plain text must come out byte-identical to what the press project's own
    verified extractor produces, because that text has been compared paragraph
    by paragraph against an independent HTML copy of the book.  Markup must not
    move a single character.
  * Spans are half-open code-point ranges into that text.  They are the source
    of truth for markup; the HTML is a cache derived from them.
  * An unrecognised control sequence is a hard failure.  A best-effort sweep
    would swallow the text inside an unknown macro and the loss would be
    invisible -- the exact failure mode build_srt.py warns about.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import sys

from .spec import (EMIT_ARG, EMIT_SUP, EMIT_TEXT, FLAG, MARK, NOTE, SPAN,
                   STRIP, STRUCTURAL)

# \kern-1pt and friends take a length with no braces around it; the length is
# not text and must be eaten or it lands in the middle of a sentence.
RE_LENGTH = re.compile(r"\s*[-+]?(?:\d*\.?\d+\s*(?:pt|em|ex|mm|cm|in|bp|sp|dd|pc)|\d*\.?\d*)\s*")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "vendor" / "press"))
from latex_tokenizer import TokenStream, tokenize  # noqa: E402

# LaTeX text-level substitutions, longest first.
_SUBS = [("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"),
         ("~", " "), ("\\&", "&"), ("\\%", "%"), ("\\$", "$"), ("\\#", "#")]

_ORDINALS = ("th", "st", "nd", "rd")


@dataclasses.dataclass(slots=True)
class Span:
    start: int
    end: int
    kind: str
    attr: dict | None = None


@dataclasses.dataclass(slots=True)
class Note:
    offset: int
    kind: str
    raw: str


@dataclasses.dataclass(slots=True)
class Expanded:
    text: str
    spans: list[Span]
    notes: list[Note]
    flags: dict[str, float]
    macros_seen: set[str]


class Expander:
    def __init__(self, table, environments, report, where: str,
                 unbraced_lengths=frozenset(), italic_openers=frozenset()):
        self.table = table
        self.environments = environments
        self.unbraced_lengths = unbraced_lengths
        self.italic_openers = italic_openers
        self.report = report
        self.where = where

    def run(self, src: str) -> Expanded:
        self.out: list[str] = []
        self.n = 0                       # running length of "".join(self.out)
        self.spans: list[Span] = []
        self.notes: list[Note] = []
        self.flags: dict[str, float] = {}
        self.seen: set[str] = set()
        self._expand(TokenStream(tokenize(src)))
        return Expanded("".join(self.out), self.spans, self.notes,
                        self.flags, self.seen)

    # -- emission -------------------------------------------------------
    def _emit(self, s: str) -> None:
        if s:
            self.out.append(s)
            self.n += len(s)

    def _text(self, raw: str) -> None:
        for a, b in _SUBS:
            raw = raw.replace(a, b)
        self._emit(raw)

    # -- the walk -------------------------------------------------------
    def _expand(self, ts: TokenStream) -> None:
        while True:
            tok = ts.next()
            if tok is None:
                return
            k = tok.kind
            if k == "TEXT":
                self._text(tok.value)
            elif k == "NEWLINE":
                self._emit(" ")
            elif k == "COMMENT":
                pass
            elif k == "OPEN_BRACE":
                # a bare group: {\itshape ...}. Expand its contents inline.
                depth, inner = 1, []
                while True:
                    t = ts.next()
                    if t is None:
                        break
                    if t.kind == "OPEN_BRACE":
                        depth += 1
                    elif t.kind == "CLOSE_BRACE":
                        depth -= 1
                        if depth == 0:
                            break
                    inner.append(t)
                # \itshape switches to italic for the REMAINDER of its
                # enclosing group, wherever in the group it appears -- in the
                # one live case it sits after an \hspace*, so testing only the
                # leading token misses it.  Split the group at the switch.
                at = next((i for i, t in enumerate(inner)
                           if t.kind == "MACRO" and t.value in self.italic_openers),
                          None)
                if at is None:
                    self._expand(TokenStream(inner))
                else:
                    self._expand(TokenStream(inner[:at]))
                    start = self.n
                    self._expand(TokenStream(inner[at + 1:]))
                    if self.n > start:
                        self.spans.append(Span(start, self.n, "em"))
            elif k == "CLOSE_BRACE":
                pass
            elif k in ("OPEN_BRACKET", "CLOSE_BRACKET"):
                self._text(tok.value or ("[" if k == "OPEN_BRACKET" else "]"))
            elif k == "MACRO":
                self._macro(tok, ts)

    def _macro(self, tok, ts: TokenStream) -> None:
        name = tok.value
        self.seen.add(name)

        if name == "begin" or name == "end":
            env = ts.read_brace_arg_raw()
            if env is not None and env not in self.environments:
                self.report.hard("unknown-environment",
                                 f"{self.where}:{tok.line}",
                                 f"\\{name}{{{env}}} not in the table")
            if name == "begin":
                ts.read_optional_arg()
            return

        spec = self.table.get(name)
        if spec is None:
            self.report.hard("unknown-macro", f"{self.where}:{tok.line}",
                             f"\\{name} is not in the macro table")
            return

        if name in self.unbraced_lengths:
            nxt = ts.peek()
            if nxt is not None and nxt.kind == "TEXT":
                m = RE_LENGTH.match(nxt.value)
                if m and m.group(0).strip():
                    nxt.value = nxt.value[m.end():]

        nxt = ts.peek()
        if nxt is not None and nxt.kind == "TEXT" and nxt.value.startswith("*"):
            if nxt.value == "*":
                ts.next()
            else:
                nxt.value = nxt.value[1:]

        for _ in range(spec.opt):
            ts.read_optional_arg()

        args: list[list] = []
        for _ in range(spec.args):
            g = ts.read_brace_group_tokens()
            args.append(g if g is not None else [])

        a = spec.action
        if a in (STRIP, STRUCTURAL):
            return
        if a == FLAG:
            self.flags[spec.kind] = 1.0
            return
        if a == EMIT_TEXT:
            self._emit(spec.text)
            return
        if a == MARK:
            self.spans.append(Span(self.n, self.n, spec.kind))
            self._emit(spec.text)
            return
        if a == NOTE:
            raw = _raw(args[spec.which - 1]) if args else ""
            self.notes.append(Note(self.n, spec.kind, raw))
            self.spans.append(Span(self.n, self.n, "fnref",
                                   {"kind": spec.kind, "i": len(self.notes) - 1}))
            return

        sel = args[spec.which - 1] if len(args) >= spec.which else []
        if a == EMIT_ARG:
            self._expand(TokenStream(sel))
            return
        if a == SPAN:
            start = self.n
            self._expand(TokenStream(sel))
            if self.n > start:
                self.spans.append(Span(start, self.n, spec.kind))
            return
        if a == EMIT_SUP:
            start = self.n
            self._expand(TokenStream(sel))
            if self.n > start:
                self.spans.append(Span(start, self.n, "sup"))
            return
        raise AssertionError(f"unhandled action {a!r}")


def _raw(tokens) -> str:
    from latex_tokenizer import _tokens_to_raw
    return _tokens_to_raw(tokens)
