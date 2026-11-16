"""A study note's inline TeX math -> MathML Core, for the closed set it uses.

The notes hold 118 `$...$` in 39 notes (study 2474116), all inline, no
environment, in about thirty commands; ud's, its translator's, 41 more
(tests/fixtures/tr-math.tsv), in a few more: an integral, a set's braces; and the
quiz's five (build/quiz.py), in three: \\alpha, \\tau and \\infty.  Each is converted here, at
build, so a
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
             "rightarrow": "→", "geqslant": "⩾", "leqslant": "⩽", "cdot": "⋅",
             # ud's notes (build/translation.py), with the braces of a set
             "in": "∈", "Rightarrow": "⇒", "ldots": "…", "{": "{", "}": "}"}
CHARS = {"-": "−", "*": "∗"}
# A function's name is set upright, and TeX's thin space follows it before a
# letter or a number (\cos\theta), none before a bracket (\cos(x)): the pull
# of a flattened body at 11:8.9, $P_2(\cos\theta)$ (2026-11-06).
FUNCTIONS = {"cos", "sin"}
OPCHARS = set("+-=<>()[]/,;:!|*.×")
SPACES = {",": "0.1667em", " ": "0.25em"}
# A bracket written plainly is the size of the text, as TeX sets it: only
# \left and \right stretch one, and they are not in the set.  MathML's own
# rule is the opposite, every bracket of a row stretched to the row's height
# and centred on the axis, so 11:8.9's g(r, θ) stood in brackets as tall as the
# fraction after it; and a bracket that carries a script, the ) of (-1)^k, is
# not one of the row's, so Chrome left it where it was and moved its partner:
# 14:1.9's "crooked" brackets, one lower than the other (Tigran, 2026-11-11).
FENCES = set("()[]{}|")
# TeX's rule for a sign (The TeXbook, Appendix G, rule 5): it is no binary
# operator where nothing stands before it to operate on, at the start of its
# list or after another operator, a relation, an opening bracket or a comma;
# it is then set close to its number, (−1), = −2.  MathML takes a sign in the
# middle of a row for binary, and set ( − 1 ).
SIGNS = set("+−±")
BINARY = set("+−±×⋅∗")
RELATIONS = set("=<>:≈≠⊂→⩾⩽∈⇒")
_NOTHING_BEFORE = BINARY | RELATIONS | set("([{" ",;")
# Where a line may break in a formula (Tigran, 2026-11-15: "let it break a
# formula after a relation or a binary operator").  To a browser a <math> is a
# box, which never breaks, and a card has no sideways scroll: on a phone the
# sum at 15:7.12 ran 332 px past its card, its result out of reach.  The rule
# is TeX's for a formula in a line of text (The TeXbook, chapter 18, given
# here in my words, the book not being at hand): a formula is broken only
# after a relation, = or < or →, or after a binary operation, + or − or ×,
# standing at its outer level, that is, in no braced group, script, root or
# fraction; a bracket written plainly is no level of its own, so a line may
# break inside one.  And Appendix G's, for which of them count: a
# binary operation with nothing before it to operate on, or with a relation, a
# closing bracket or a comma after it, is none, and of two relations together
# the break is after the second.
#
# TeX weighs such a break against the line's spacing (\relpenalty 500,
# \binoppenalty 700) and a browser cannot: it takes every break it is given
# as it takes a space.  So two are not given: after an operator that begins
# the formula, "≈ 10" being better moved whole; and at the × of a number
# written 1.77 × 10¹⁴, which is one number as 10,000 is (_tokens).
_CLOSES = set(")]},;!")
# The forms each operator of the set has an entry for in MathML Core's
# operator dictionary.  A browser takes an operator's form from its place,
# prefix where it is first of several in its row, postfix where last, infix
# otherwise, and falls back to another form, in the order infix, postfix,
# prefix, where the dictionary has none for that one; the form gives the
# spaces round it.  A formula cut in pieces puts operators first and last
# that stood in the middle, so each is told the form it had (_pieces).
_FORMS = {**{c: ("infix", "prefix") for c in "+−±"},
          **{c: ("infix",) for c in "×⋅∗" "=<>:≈≠⊂→⩾⩽∈⇒" "/,;.…"},
          **{c: ("prefix",) for c in "([{∑∫"},
          **{c: ("postfix",) for c in ")]}!"},
          "|": ("prefix", "infix", "postfix")}


def _mo(ch: str, unary: bool = False) -> str:
    attrs = ' stretchy="false"' if ch in FENCES else ' form="prefix"' if unary else ""
    return f"<mo{attrs}>{html.escape(ch, quote=False)}</mo>"

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
        self.fn = False                 # the atom just taken was a function's name

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        t = self.peek()
        if t is None:
            raise MathError("ends too soon")
        self.i += 1
        return t

    def unary(self) -> bool:
        """Whether the sign just taken has nothing before it to operate on
        (SIGNS, above): by the token before it, a space apart."""
        j = self.i - 2
        while j >= 0 and self.toks[j][0] == "cmd" and self.toks[j][1] in SPACES:
            j -= 1
        if j < 0:
            return True
        kind, v = self.toks[j]
        if kind in ("{", "^", "_"):
            return True
        if kind == "op":
            return v in _NOTHING_BEFORE
        if kind == "cmd":
            return (OPERATORS.get(v) in _NOTHING_BEFORE or v in FUNCTIONS
                    or v in ("sum", "int", "limits", "over"))
        return False

    def seq(self, closing: bool) -> str:
        """Nodes up to the group's end; a \\over splits them into a fraction."""
        return "".join(self.row(closing)[0])

    def row(self, closing: bool) -> tuple[list[str], list[str | None]]:
        """The same nodes one by one, and beside each the relation or binary
        operation it is, where it is one and nothing more: no sign of a
        number, which is set as a prefix, and nothing with a script."""
        nodes: list[str] = []
        ops: list[str | None] = []
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
                over, nodes, ops = nodes, [], []
                continue
            node = self.scripted()
            ch = t[1] if t[0] == "op" else OPERATORS.get(t[1]) if t[0] == "cmd" else None
            nodes.append(node)
            ops.append(ch if ch in BINARY | RELATIONS and node == _mo(ch) else None)
        if over is not None:
            return [f"<mfrac>{_row(over)}{_row(nodes)}</mfrac>"], [None]
        return nodes, ops

    def scripted(self) -> str:
        base, limits = self.atom()
        fn, self.fn = self.fn, False
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
        if sub is not None or sup is not None:
            if limits:
                tag = "munderover" if sub and sup else "munder" if sub else "mover"
            else:
                tag = "msubsup" if sub and sup else "msub" if sub else "msup"
            base = f"<{tag}>{base}{sub or ''}{sup or ''}</{tag}>"
        nxt = self.peek()
        if fn and nxt is not None and nxt[0] != "}" and nxt not in (("op", "("), ("op", "[")):
            base += f'<mspace width="{SPACES[","]}"/>'
        return base

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
            return _mo(v, v in SIGNS and self.unary()), False
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
        if v in FUNCTIONS:
            self.fn = True
            return f"<mi>{v}</mi>", False
        if v == "infty":                       # the quiz's answer "$\infty$" (build/quiz.py)
            return "<mi>∞</mi>", False
        if v in OPERATORS:
            return _mo(OPERATORS[v], OPERATORS[v] in SIGNS and self.unary()), False
        if v in SPACES:
            return f'<mspace width="{SPACES[v]}"/>', False
        if v in ("sum", "int"):
            op = "∑" if v == "sum" else "∫"
            limits = self.peek() == ("cmd", "limits")
            if limits:
                self.i += 1
                return f'<mo movablelimits="false">{op}</mo>', True
            return f"<mo>{op}</mo>", False
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
            # Its letters and digits in the style; an operator among them, as
            # \\mathbf{A(r)}'s brackets, stays as it is.
            out = []
            while True:
                t = self.take()
                if t[0] == "}":
                    break
                if t[0] == "op":
                    out.append(_mo(t[1]))
                    continue
                if t[0] not in ("id", "num"):
                    raise MathError(f"\\{v} holds {t[1]!r}, not letters")
                out.extend(f"<mi>{alnum(style, ch)}</mi>" for ch in t[1])
            return "".join(out), False
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
    # A root's radical sign is no token: the browser draws it for <msqrt> and
    # <mroot> from the font's own glyph (U+221A, stretched by the MATH table),
    # so the subset must keep it.  Without this, 11:2.2's eccentricity lost its
    # radical and was set as 1 − (6/7)² (2026-11-05).
    if "<msqrt" in mathml or "<mroot" in mathml:
        out.add("√")
    return out


RE_MO = re.compile(r"<mo( [^>]*)?>([^<]*)</mo>")
RE_POWER_OF_TEN = re.compile(r"<msup><mn>10</mn>")


def _elements(s: str) -> list[str]:
    """The elements standing side by side in s, one by one."""
    out, depth, i, start = [], 0, 0, 0
    while i < len(s):
        if s.startswith("</", i):
            depth -= 1
            i = s.index(">", i) + 1
            if depth == 0:
                out.append(s[start:i])
                start = i
        elif s.startswith("<", i):
            j = s.index(">", i)
            if s[j - 1] != "/":
                depth += 1
            elif depth == 0:
                out.append(s[start:j + 1])
                start = j + 1
            i = j + 1
        else:
            i += 1
    if depth or start != len(s):
        raise MathError(f"{s!r} is not elements side by side")
    return out


def _is_space(node: str) -> bool:
    return node.startswith("<mspace") and node.endswith("/>") and node.count("<") == 1


def _char(node: str) -> str | None:
    """The character of a node that is one operator and nothing more."""
    m = RE_MO.fullmatch(node)
    return html.unescape(m[2]) if m else None


def _cuts(nodes: list[str], ops: list[str | None]) -> list[int]:
    """After how many of the nodes a line may break (BINARY, above)."""
    out = []
    for i, op in enumerate(ops):
        if op is None or i == 0:
            continue
        # A space typed after it stays with it, as TeX's glue does, which is
        # dropped at a break.
        j = i + 1
        while j < len(nodes) and _is_space(nodes[j]):
            j += 1
        if j == len(nodes):
            continue                            # nothing after it
        k = i - 1
        while k > 0 and _is_space(nodes[k]):
            k -= 1
        if op in RELATIONS:
            if ops[j] in RELATIONS:
                continue                        # := and the like: after the second
        else:
            if _char(nodes[k]) in _NOTHING_BEFORE:
                continue                        # nothing before it to operate on
            if ops[j] in RELATIONS or _char(nodes[j]) in _CLOSES:
                continue
            if (op in "×⋅" and nodes[k].startswith("<mn>")
                    and RE_POWER_OF_TEN.match(nodes[j])):
                continue                        # 1.77 × 10¹⁴ is one number
        out.append(j)
    return out


def _placed(i: int, n: int) -> str:
    """The form a browser gives the i-th of a row's n elements by its place."""
    return "infix" if n == 1 or 0 < i < n - 1 else "prefix" if i == 0 else "postfix"


def _form(ch: str, placed: str) -> str | None:
    """The form the dictionary answers for, asked for an operator so placed."""
    if ch not in _FORMS:
        raise MathError(f"{ch!r} at a break: its forms are not on record (_FORMS)")
    has = _FORMS[ch]
    return placed if placed in has else next((f for f in ("infix", "postfix", "prefix") if f in has), None)


def _pieces(nodes: list[str], cuts: list[int]) -> list[str]:
    """The formula's row cut after cuts[0], cuts[1]... of its nodes, each piece
    a row of its own, in which every operator keeps the form it had."""
    counts = [len(_elements(node)) for node in nodes]
    row = [el for node in nodes for el in _elements(node)]
    ends = [sum(counts[:c]) for c in cuts] + [len(row)]
    out, a = [], 0
    for b in ends:
        piece = row[a:b]
        for at in {0, len(piece) - 1}:
            el = piece[at]
            m = RE_MO.fullmatch(el)
            was, now = _placed(a + at, len(row)), _placed(at, len(piece))
            if not m or was == now or "form=" in (m[1] or ""):
                continue
            had = _form(html.unescape(m[2]), was)
            if had and had != now:
                piece[at] = f'<mo{m[1] or ""} form="{had}">{m[2]}</mo>'
        out.append("".join(piece))
        a = b
    return out


def convert(tex: str, breaks: bool = False) -> str:
    """`2^3 - 1 = 7` -> its <math>, inline.  MathError if outside the set.

    With `breaks`, a formula a line may break in (BINARY, above) is as many
    <math> as the places make of it, a <wbr/> between them: with nothing
    between, the pieces stand exactly as the one formula did, each operator's
    spaces inside its piece, and a line may end after any piece.  The <wbr/>
    is for a formula kept with the punctuation typed against it, in a span
    that does not wrap (study.glued): a browser breaks there all the same.
    A formula with no such place is the one <math> it was, to the byte.
    """
    nodes, ops = _Parser(tex).row(False)
    if not nodes:
        raise MathError("empty")
    cuts = _cuts(nodes, ops) if breaks else []
    return "<wbr/>".join(f'<math xmlns="{NS}">{piece}</math>'
                        for piece in (_pieces(nodes, cuts) if cuts else ["".join(nodes)]))
