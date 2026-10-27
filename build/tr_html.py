"""The Foundation's HTML, a paragraph's or a title's, as text and spans.

What build/tr_macros.py and the Expander are to a translation's TeX, this is to
the bodies build/readers/uf_html.py reads from the Foundation's zip of it
(build/translation.py).  Closed, as they are: a tag that is not here fails.

  <em>                        em
  <span class="scaps">        sc: small capitals, Uversa's names in 42:2
  <sup>                       sup
  <span class="pra">          a table row's words, then
    <span class="dot"></span>   its leader: a dotleader mark and a space, as the
    <span class="ran">          press's and urantia-ru's \\bibdf: "Сверхвселенные 7"
  <br />                      a line break in a section's title: a space

And one mark that is no tag: a bare `*` in the text is where an editor's note
attaches, a footnote's marker in print.  The note itself stands at its paper's
end, after `{{` (build/translation.py), and the `*` is taken out of the text,
its place returned for the note's marker.

A translation's own characters are kept, but where its key declares a
normalisation (translation.STYLE): the Russian writes about 650 of its stress
marks as a Latin vowel with an acute inside a Cyrillic word, чтó, бóльшую,
which search would not find as что and hyphenation would break at, and is
read with the Cyrillic vowel and U+0301, as it writes the rest (LATIN_STRESS).
After that, a word with letters of both alphabets fails.
"""

from __future__ import annotations

import html
import re

from .expand import Span

RE_TOKEN = re.compile(r"<(/?)([a-z0-9]+)((?:\s+[a-z]+=\"[^\"]*\")*)\s*(/?)>|([^<]+)")
RE_CLASS = re.compile(r'\s+class="([a-z]+)"')
# Each opening tag, by its name and class, and the span it makes (None: none).
OPEN = {("em", None): "em", ("sup", None): "sup", ("span", "scaps"): "sc",
        ("span", "pra"): None, ("span", "ran"): None}
# The Latin vowels with an acute that stand for a Cyrillic one with the stress
# mark, in a word with Cyrillic letters.
LATIN_STRESS = {"á": "а́", "é": "е́", "ó": "о́", "ý": "у́"}
RE_WORD = re.compile(r"\w+")
RE_LETTERS = re.compile(r"(?:[^\W\d_]|́)+")
RE_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
RE_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")


def normalise(body: str, table: dict[str, str]) -> tuple[str, int]:
    """The body with each of `table`'s characters replaced where it stands in a
    word that has Cyrillic, and how many were.  On the HTML as written: a tag's
    name and class have no Cyrillic, and no word here is cut by a tag."""
    if not table:
        return body, 0
    n = 0

    def fix(m):
        nonlocal n
        w = m.group()
        if not RE_CYRILLIC.search(w) or not any(c in w for c in table):
            return w
        n += sum(w.count(c) for c in table)
        return "".join(table.get(c, c) for c in w)
    return RE_WORD.sub(fix, body), n


def marks(body: str) -> list[str]:
    """Its `*` marks, in its words and never in a tag."""
    return [c for m in RE_TOKEN.finditer(body) if m.group(5) for c in html.unescape(m.group(5)) if c == "*"]


def expand(body: str, report, where: str) -> tuple[str, list[Span], list[int]]:
    """(text, spans, the places of its `*` marks)."""
    out: list[str] = []
    at = 0
    spans: list[Span] = []
    marks: list[int] = []
    stack: list[tuple[str, str | None, str | None, int]] = []     # (tag, class, span kind, start)
    for m in RE_TOKEN.finditer(body):
        close, tag, attrs, empty, words = m.groups()
        if words is not None:
            for piece in re.split(r"(\*)", html.unescape(words)):
                if piece == "*":
                    marks.append(at)
                elif piece:
                    out.append(piece)
                    at += len(piece)
            continue
        cls = RE_CLASS.fullmatch(attrs) if attrs else None
        if attrs and cls is None:
            report.hard("tr-html-unread", where, f"<{tag}{attrs}>: an attribute that is not one class")
            continue
        cls = cls and cls.group(1)
        if close:
            if not stack or stack[-1][0] != tag:
                report.hard("tr-html-unread", where, f"</{tag}> closes nothing open")
                continue
            _, _, kind, start = stack.pop()
            if kind:
                spans.append(Span(start, at, kind))
        elif tag == "br" and empty and not cls:
            out.append(" ")
            at += 1
        elif (tag, cls) == ("span", "dot") and not empty:
            # Empty, and in a row: the leader, then its space.
            if not body.startswith("</span>", m.end()) or not any(c == "pra" for _, c, _, _ in stack):
                report.hard("tr-html-unread", where, "a leader outside a row, or with something in it")
            stack.append((tag, cls, None, at))
            spans.append(Span(at, at, "dotleader"))
            out.append(" ")
            at += 1
        elif (tag, cls) in OPEN and not empty:
            if cls == "ran" and not any(c == "pra" for _, c, _, _ in stack):
                report.hard("tr-html-unread", where, "a leader's number outside its row")
            stack.append((tag, cls, OPEN[(tag, cls)], at))
        else:
            report.hard("tr-html-unread", where, m.group()[:60])
    for tag, *_ in stack:
        report.hard("tr-html-unread", where, f"<{tag}> never closes")
    if RE_TOKEN.sub("", body).strip():
        report.hard("tr-html-unread", where, f"a stray '<': {RE_TOKEN.sub('', body).strip()[:40]!r}")
    text = "".join(out)
    for w in RE_LETTERS.findall(text):
        if RE_CYRILLIC.search(w) and RE_LATIN.search(w):
            report.hard("tr-mixed-script", where, f"{w!r}: Latin and Cyrillic letters in one word")
    return text, spans, marks
