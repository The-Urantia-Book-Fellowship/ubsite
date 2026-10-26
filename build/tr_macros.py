"""The macro tables of the translations, one to each (build/translation.py).

Closed, as the press's and the study notes' are: what is not here fails the
build.  Each translation has its own table, never the press's, and the two
share an entry only where their styles define the macro alike (trap 1: the
same name can mean another thing in two repositories).  Each entry was read
against the style it serves -- ud's ud.sty and ubook.sty, urantia-ru's
urantia-ru.sty, tex/urantia-core.tex and ubook.sty -- at the commits the
build read on 2026-10-26 (ud 51f3039, urantia-ru a6525fe).

What a reader of the site needs from a paragraph is its words, their italics,
a list's label and a table row's leader.  The rest is the printed page's:
spacing, line breaks for one device (\\tunemarkup{pgnexus10}{...}), the figures
(\\tunemarkup{pictures}{...}), which the site does not show from a translation,
and the 1955 groups (\\pc), which the English carries.  A translator's note,
\\fnst, is kept as written, where it stands, for build/translation.py to store;
it is not expanded here.
"""

from __future__ import annotations

from .spec import ACCENT, CALL, EMIT_TEXT, FLAG, MARK, SPAN, STRIP, Spec

# Both styles alike.
SHARED: dict[str, Spec] = {
    "bibemph": Spec(SPAN, args=1, kind="em"),
    "hyp": Spec(EMIT_TEXT, args=1, text="-", note="hyphenat's hyphen, which lets each part break; its argument is {}"),
    ",": Spec(EMIT_TEXT, text=" ", note="a thin space that does not break: 10\\,000, н.\\,э."),
    " ": Spec(EMIT_TEXT, text=" "),
    "%": Spec(EMIT_TEXT, text="%"),
    "&": Spec(EMIT_TEXT, text="&"),
    "ldots": Spec(EMIT_TEXT, text="…"),
    # No optional argument, as both styles define it (\def\pc{...}): the press's
    # takes one, and read so, `\pc [Под объединенным покровительством ...]`
    # lost the whole of 31:10.21 as its argument (trap 2).
    "pc": Spec(FLAG, kind="gap_before", note="the 1955 group mark (§§ or ¶ in print); the English carries it"),
    "bibdf": Spec(MARK, kind="dotleader", text=" ",
                  note="a table row's leader, as the press's: the space TeX swallows, and the point"),
    "bibnobreakspace": Spec(EMIT_TEXT, text=" ", note="\\kern5pt after a list's label: the space TeX swallows"),
    "vsetoff": Spec(STRIP, note="\\vspace{1ex}"),
    "hsetoff": Spec(STRIP, note="\\hspace*{1em}: a line of verse set in"),
    "-": Spec(MARK, kind="shy", text="", note="a discretionary hyphen: where this word may break, and nowhere else"),
}

# «Урантийские документы» (../ud): the study edition's lineage.
UD: dict[str, Spec] = SHARED | {
    "li": Spec(CALL, args=1, note="ud.sty: \\kern1em\\makebox[0.2em][r]{#1}\\kern0.3em -- a list's label, then its space"),
    "bibfrac": Spec(CALL, args=2, note="a fraction, 3\\bibfrac{1}{8}: drawn as one (VULGAR)"),
    "fnst": Spec(CALL, args=1, note="the translator's note, kept as written (build/translation.py)"),
    "'": Spec(ACCENT, text="́", note="the stress mark: призна\\'ют"),
    "tunemarkup": Spec(STRIP, args=2, note="ud.sty: #2 only where tune@markup@#1 is defined -- one device's "
                                           "line breaks (pgnexus10), the figures (pictures)"),
    "kern": Spec(STRIP, note="its length is unbraced: \\kern0.3em"),
    "hfill": Spec(MARK, kind="dotleader", text=" ",
                  note="15:2's rows, which ud sets with a fill where the press sets a leader"),
    "ts": Spec(SPAN, args=1, kind="sup", note="\\textsuperscript"),
    "linebreak": Spec(EMIT_TEXT, opt=1, text=" "),
    "subtitlefont": Spec(STRIP, note="a skeleton paper's English title, never stored"),
    "\\": Spec(EMIT_TEXT, opt=1, text=" ", note="a printed line break, in a title"),
}
UD_UNBRACED = frozenset({"kern"})
UD_ITALIC = frozenset({"em"})

# «Книга Урантии» (../urantia-ru): the press's own lineage, and only its macros
# but \uforeword, which is a line of its own (build/readers/translation.py).
URANTIA_RU: dict[str, Spec] = SHARED | {
    "ublistelem": Spec(SPAN, args=1, kind="listmark", note="a list's label; \\bibnobreakspace follows"),
}

TABLES = {"ud": (UD, UD_UNBRACED, UD_ITALIC),
          "urantia-ru": (URANTIA_RU, frozenset(), frozenset())}

# TeX's ligatures, as XeTeX's tex-text mapping sets them, longest first: the
# Russian quotes «», „ and “, and the dashes.  A tie is a space that does not
# break, before a dash above all: Бог~--- Отец.
SUBS = [("---", "—"), ("--", "–"), ("<<", "«"), (">>", "»"), (",,", "„"),
        ("``", "“"), ("''", "”"), ("`", "‘"), ("'", "’"), ("~", " ")]

# \bibfrac's fractions where UB Goudy has a character for them: 2\bibfrac{1}{2}
# is 2½.  Any other is n⁄d, with the fraction slash, in a span that turns on
# Goudy's `frac`, which draws it as one: 3\bibfrac{1}{8} is 3⅛, though Goudy
# has no ⅛.  After a digit a word joiner comes first, as Unicode asks of a mixed
# number, so that it neither breaks nor reads as 31/8 (build/translation.py).
VULGAR = {("1", "2"): "½", ("1", "4"): "¼", ("3", "4"): "¾"}
