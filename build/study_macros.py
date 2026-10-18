"""The macro table for a study note, and for a source it cites.

The study edition's own, never the press's: the same name can mean another
thing in the two repositories (trap 1, `\\tunemarkup`), and a note is set for
a reader, not compared with an oracle, so `\\ldots` is "…" here where the press
emits "..." to match the SRT text.  Closed: what is not here fails the build.
These are the commands found inside the 404 `\\fnst` and the 60 `\\bibitem` of
the edition (study 2474116), less those a reviewed note has no use for.

Four are callbacks, made per note by build/study.py, which knows the paper's
sources and the book's paragraphs: `\\cite`, `\\bibref`, `\\myurl`, `\\bibfrac`.
Math, `$...$`, never reaches this table: study.py takes it out first and
build/texmath.py converts it.
"""

from __future__ import annotations

from .spec import ACCENT, CALL, EMIT_ARG, EMIT_TEXT, SPAN, Spec

TABLE: dict[str, Spec] = {
    "bibemph": Spec(SPAN, args=1, kind="em"),
    "emph": Spec(SPAN, args=1, kind="em"),
    "textit": Spec(SPAN, args=1, kind="em"),
    "textsc": Spec(SPAN, args=1, kind="sc"),
    "bibtextul": Spec(SPAN, args=1, kind="ul"),
    "ts": Spec(SPAN, args=1, kind="sup", note="\\textsuperscript: 19\\ts{th}, kg/m\\ts{3}"),
    "hyp": Spec(EMIT_TEXT, args=1, text="-", note="hyphenat's hyphen; its argument is {}"),
    ",": Spec(EMIT_TEXT, text=" ", note="a thin space that does not break: 12.6\\,ly"),
    " ": Spec(EMIT_TEXT, text=" "),
    "#": Spec(EMIT_TEXT, text="#"),
    "%": Spec(EMIT_TEXT, text="%"),
    "$": Spec(EMIT_TEXT, text="$"),
    "&": Spec(EMIT_TEXT, text="&"),
    "ldots": Spec(EMIT_TEXT, text="…"),
    "ae": Spec(EMIT_TEXT, text="æ"),
    "'": Spec(ACCENT, text="́", note="acute: oor\\'anteeya"),
    '"': Spec(ACCENT, text="̈", note="diaeresis"),
    "mbox": Spec(EMIT_ARG, args=1),
    "texttt": Spec(EMIT_ARG, args=1, note="a site's name in a note; set as the text"),
    "bibexpl": Spec(EMIT_ARG, args=1, note="the edition marks a note informational; the site does not"),
    "textgreek": Spec(SPAN, args=1, kind="lang", attr=(("lang", "grc"),)),
    # Logical order here: the edition writes Hebrew word by word reversed, for
    # XeTeX without bidi (tools/mktext.php), and tools/study/draft.py turns it.
    "textheb": Spec(SPAN, args=1, kind="lang", attr=(("lang", "he"), ("dir", "rtl"))),
    "textarm": Spec(SPAN, args=1, kind="lang", attr=(("lang", "hy"),)),
    "textchinese": Spec(SPAN, args=1, kind="lang", attr=(("lang", "zh"),)),
    "cite": Spec(CALL, args=1, note="a source in the paper's list: [n], listed in the card"),
    "bibref": Spec(CALL, opt=1, args=1, note="\\bibref[1:2.9]{p001 2:9}: a link to the paragraph"),
    "myurl": Spec(CALL, args=1, note="an address, linked"),
    "bibfrac": Spec(CALL, args=2, note="\\bibfrac{3}{4}: 3/4"),
}

# {\em ...} in a bibliography entry: italic to the end of its group.
ITALIC_OPENERS = frozenset({"em", "itshape"})

# TeX's ligatures: ``a'' is “a”, `a' is ‘a’, Nave's is Nave’s, and a tie is a
# space that does not break.
SUBS = [("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"), ("`", "‘"), ("'", "’"),
        ("~", " ")]
