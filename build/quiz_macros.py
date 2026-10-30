"""The macro table for a question of the quiz, and its answers.

The study edition's own, a named part of the table its notes are set with
(build/study_macros.py), never the press's: the same name can mean another
thing in the two repositories (trap 1).  Closed, and held to exactly the
commands tex/quiz.tex uses (study 2474116): a command it starts to use fails
the build until it is added here, and one it stops using fails too, so the
table never carries what nothing reads.  Math, `$...$`, never reaches it:
build/study.py's expand() takes it out first and build/texmath.py converts it.
"""

from __future__ import annotations

from .spec import EMIT_TEXT, Spec
from .study_macros import SUBS, TABLE as STUDY

NAMES = ("bibemph", "ts", "hyp", ",", " ", "#", "%", "&", "ldots")

TABLE: dict[str, Spec] = {
    **{k: STUDY[k] for k in NAMES},
    "-": Spec(EMIT_TEXT, text="", note="a discretionary hyphen: per\\-so\\-na\\-li\\-ty, quiz.tex:5859"),
    "textasciitilde": Spec(EMIT_TEXT, text="~", note="\"~135 million\": about; a slip until ruled"),
}

# What the questions use besides: \qstart, \qstop, \qpaper, \quizheader are the
# file's structure, read by build/readers/quiz.py, and $\alpha$, $\tau$ and
# $\infty$ are math.
STRUCTURE = frozenset({"qstart", "qstop", "qpaper", "quizheader"})
MATH = frozenset({"alpha", "tau", "infty"})

__all__ = ["TABLE", "SUBS", "STRUCTURE", "MATH"]
