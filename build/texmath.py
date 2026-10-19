"""A study note's inline TeX math -> MathML Core, for the closed set it uses.

The notes hold 118 `$...$` in 39 notes (study 2474116), all inline, no
environment, in about thirty commands.  Each is converted here, at build, so a
page carries MathML the browser lays out itself: no script, the same in the
offline copy.  A command outside the set fails, as an unknown macro does in the
text: a converter that guessed would print something else than the editor
wrote, and nobody would see it.

MathML Core honours `mathvariant` only as "normal", so a bold, script or
double-struck letter is its own character (Unicode's mathematical
alphanumerics), and a single letter is left for the browser to set italic, as
TeX does.  Capital Greek is upright, as TeX sets it.
"""

from __future__ import annotations

import html
import re

NS = "http://www.w3.org/1998/Math/MathML"

GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ",
         "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "lambda": "λ",
         "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ",
         "tau": "τ", "phi": "ϕ", "chi": "χ", "psi": "ψ", "omega": "ω"}
GREEK_UPPER = {"Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Pi": "Π",
               "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω"}
OPERATORS = {"times": "×", "approx": "≈", "pm": "±", "neq": "≠", "subset": "⊂",
             "rightarrow": "→", "geqslant": "⩾", "leqslant": "⩽", "cdot": "⋅"}
CHARS = {"-": "−", "*": "∗"}
OPCHARS = set("+-=<>()[]/,;:!|*.")
SPACES = {",": "0.1667em", " ": "0.25em"}

# Unicode's mathematical alphanumerics: the letters of \mathbf, \mathcal and
# \mathbb.  Where a letter was encoded before that block (ℝ, ℳ), the block
# leaves a hole and the older character stands.
_HOLES = {
    "cal": {"B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ",
            "e": "ℯ", "g": "ℊ", "o": "ℴ"},
    "bb": {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"},
    "bf": {},
}
_BASE = {"bf": 0x1D400, "cal": 0x1D49C, "bb": 0x1D538}


def alnum(style: str, ch: str) -> str:
    if ch in _HOLES[style]:
        return _HOLES[style][ch]
    if "A" <= ch <= "Z":
        return chr(_BASE[style] + ord(ch) - 65)
    if "a" <= ch <= "z":
        return chr(_BASE[style] + 26 + ord(ch) - 97)
    if style == "bf" and "0" <= ch <= "9":
        return chr(0x1D7CE + ord(ch) - 48)
    raise MathError(f"no {style} form of {ch!r}")


class MathError(ValueError):
    pass


def _tokens(src: str):
    i = 0
    while i < len(src):
        c = src[i]
        if c == "\\":
            j = i + 1
            while j < len(src) and src[j].isalpha():
                j += 1
            if j == i + 1:                  # a control symbol: \, \  \{
                if j >= len(src):
                    raise MathError("a backslash at the end")
                yield ("cmd", src[j])
                i = j + 1
            else:
                yield ("cmd", src[i + 1:j])
                i = j
        elif c.isspace():
            i += 1
        elif c.isdigit():
            j = i
            while j < len(src) and src[j].isdigit():
                j += 1
            # A decimal part, and thousands set off by commas (10,000), are one
            # number; any other comma separates (2,8,8,18 is a list).
            while True:
                if j + 1 < len(src) and src[j] == "." and src[j + 1].isdigit():
                    j += 1
                    while j < len(src) and src[j].isdigit():
                        j += 1
                elif (src[j:j + 1] == "," and len(src[j + 1:j + 4]) == 3
                      and src[j + 1:j + 4].isdigit() and not src[j + 4:j + 5].isdigit()):
                    j += 4
                else:
                    break
            yield ("num", src[i:j])
            i = j
        elif c.isalpha():
            yield ("id", c)
            i += 1
        elif c in "{}^_":
            yield (c, c)
            i += 1
        elif c in OPCHARS:
            yield ("op", CHARS.get(c, c))
            i += 1
        else:
            raise MathError(f"{c!r} is not in the set")


class _Parser:
    def __init__(self, src: str):
        self.toks = list(_tokens(src))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        t = self.peek()
        if t is None:
            raise MathError("ends too soon")
        self.i += 1
        return t

    def seq(self, closing: bool) -> str:
        """Nodes up to the group's end; a \\over splits them into a fraction."""
        nodes: list[str] = []
        over: list[str] | None = None
        while True:
            t = self.peek()
            if t is None:
                if closing:
                    raise MathError("a { never closed")
                break
            if t[0] == "}":
                if not closing:
                    raise MathError("a } with no {")
                self.i += 1
                break
            if t == ("cmd", "over"):
                if over is not None:
                    raise MathError("two \\over in one group")
                self.i += 1
                over, nodes = nodes, []
                continue
            nodes.append(self.scripted())
        if over is not None:
            return f"<mfrac>{_row(over)}{_row(nodes)}</mfrac>"
        return "".join(nodes)

    def scripted(self) -> str:
        base, limits = self.atom()
        sub = sup = None
        while self.peek() and self.peek()[0] in "^_":
            k = self.take()[0]
            arg = _row_of(self.atom()[0])
            if k == "^":
                if sup is not None:
                    raise MathError("two superscripts")
                sup = arg
            else:
                if sub is not None:
                    raise MathError("two subscripts")
                sub = arg
        if sub is None and sup is None:
            return base
        if limits:
            tag = "munderover" if sub and sup else "munder" if sub else "mover"
        else:
            tag = "msubsup" if sub and sup else "msub" if sub else "msup"
        return f"<{tag}>{base}{sub or ''}{sup or ''}</{tag}>"

    def atom(self) -> tuple[str, bool]:
        """One node, and whether its scripts go under and over it (\\limits)."""
        kind, v = self.take()
        if kind == "{":
            return _row_of(self.seq(True)), False
        if kind == "num":
            return f"<mn>{v}</mn>", False
        if kind == "id":
            return f"<mi>{v}</mi>", False
        if kind == "op":
            return f"<mo>{html.escape(v, quote=False)}</mo>", False
        if kind in "^_":
            raise MathError(f"a {v} with nothing to stand on")
        if kind == "}":
            raise MathError("a } with no {")
        # a command
        if v in GREEK:
            return f"<mi>{GREEK[v]}</mi>", False
        if v in GREEK_UPPER:
            return f'<mi mathvariant="normal">{GREEK_UPPER[v]}</mi>', False
        if v == "hbar":
            return "<mi>ℏ</mi>", False
        if v in OPERATORS:
            return f"<mo>{OPERATORS[v]}</mo>", False
        if v in SPACES:
            return f'<mspace width="{SPACES[v]}"/>', False
        if v == "sum":
            limits = self.peek() == ("cmd", "limits")
            if limits:
                self.i += 1
                return '<mo movablelimits="false">∑</mo>', True
            return "<mo>∑</mo>", False
        if v == "sqrt":
            return f"<msqrt>{self.argument()}</msqrt>", False
        if v in ("vec", "overline"):
            # \overline's bar is the macron, which MathML stretches as an
            # accent, and which the math font has (it has no U+203E).
            mark = "→" if v == "vec" else "¯"
            return f'<mover accent="true">{_row_of(self.argument())}<mo>{mark}</mo></mover>', False
        if v in ("mathbf", "mathcal", "mathbb"):
            style = {"mathbf": "bf", "mathcal": "cal", "mathbb": "bb"}[v]
            kind2, _ = self.take()
            if kind2 != "{":
                raise MathError(f"\\{v} wants its letters in braces")
            out = []
            while True:
                t = self.take()
                if t[0] == "}":
                    break
                if t[0] not in ("id", "num"):
                    raise MathError(f"\\{v} holds {t[1]!r}, not letters")
                out.extend(alnum(style, ch) for ch in t[1])
            return "".join(f"<mi>{ch}</mi>" for ch in out), False
        raise MathError(f"\\{v} is not in the set")

    def argument(self) -> str:
        return self.atom()[0]


def _row(nodes: list[str]) -> str:
    return nodes[0] if len(nodes) == 1 else f"<mrow>{''.join(nodes)}</mrow>"


def _row_of(s: str) -> str:
    """One node: s itself if it is one element, else an <mrow> around it."""
    if s.startswith("<") and _single(s):
        return s
    return f"<mrow>{s}</mrow>"


def _single(s: str) -> bool:
    depth, i = 0, 0
    while i < len(s):
        if s.startswith("</", i):
            depth -= 1
            i = s.index(">", i) + 1
            if depth == 0 and i < len(s):
                return False
        elif s.startswith("<", i):
            j = s.index(">", i)
            if s[j - 1] != "/":
                depth += 1
            elif depth == 0 and j + 1 < len(s):
                return False
            i = j + 1
        else:
            i += 1
    return True


# What a browser draws for a single letter in an <mi>: its mathematical italic
# (MathML Core's text-transform: math-auto).  The math font is subset to these,
# not to the letters stored (build/fonts.py).
_ITALIC = {"h": "ℎ", "ϵ": "𝜖", "ϑ": "𝜗", "ϰ": "𝜘", "ϕ": "𝜙", "ϱ": "𝜚", "ϖ": "𝜛", "∂": "𝜕",
           "∇": "𝛻", "ı": "𝚤", "ȷ": "𝚥"}
RE_TOKEN = re.compile(r"<(mi|mo|mn)( [^>]*)?>([^<]*)</\1>")


def italic(ch: str) -> str:
    if ch in _ITALIC:
        return _ITALIC[ch]
    if "A" <= ch <= "Z":
        return chr(0x1D434 + ord(ch) - 65)
    if "a" <= ch <= "z":
        return chr(0x1D44E + ord(ch) - 97)
    if "Α" <= ch <= "Ω" and ch != "΢":
        return chr(0x1D6E2 + ord(ch) - 0x391)
    if "α" <= ch <= "ω":
        return chr(0x1D6FC + ord(ch) - 0x3B1)
    return ch


def drawn(mathml: str) -> set[str]:
    """The characters a browser draws for a <math> this module made."""
    out: set[str] = set()
    for tag, attrs, text in RE_TOKEN.findall(mathml):
        text = html.unescape(text)
        if tag == "mi" and len(text) == 1 and "mathvariant" not in (attrs or ""):
            text = italic(text)
        out.update(text)
    return out


def convert(tex: str) -> str:
    """`2^3 - 1 = 7` -> its <math>, inline.  MathError if outside the set."""
    body = _Parser(tex).seq(False)
    if not body:
        raise MathError("empty")
    return f'<math xmlns="{NS}">{body}</math>'
