"""(text, spans) -> HTML.  The only renderer in the project.

The contract, and the reason `check_roundtrip` is the most important gate here:
**stripping the tags from the output must give back the stored text, byte for
byte.**  The dot-leader rows are where a renderer goes wrong -- the printed row
is `Superuniverses . . . . . 7`, but the *text* is `Superuniverses 7`, and a
leader drawn with `content: "....."` copy-pastes as garbage.  So the dots are
drawn in CSS and the markup carries nothing that is not already in the text.

Spans nest (a red-letter quotation containing an emphasis) but never partially
overlap within a kind, so the open set changes only at boundaries and the output
is well-formed without any tag-splitting heuristics.
"""

from __future__ import annotations

import html

# kind -> (tag, class).  Zero-width kinds are point insertions, not wrappers.
WRAP = {
    "em":        ("em", None),
    "redletter": ("span", "jesus"),
    "supplied":  ("span", "supplied"),
    "sup":       ("sup", None),
    "sc":        ("span", "sc"),
    "ul":        ("span", "ul"),
    "listmark":  ("span", "mark"),
    "lang":      ("span", "lang"),
    "link":      ("a", None),
    "url":       ("a", "url"),
    "nobreak":   ("span", "nobreak"),
    "chg":       ("mark", "chg"),     # the SRT Committee's 1955 text: the changed words
}
POINT = {
    "dotleader": '<span class="leader"></span>',
    "fnref":     None,      # rendered by the caller; carries a note id
    # The text API's mark for a 1955 reading (build/versions.py), where the
    # site's is the fnref link: empty, and the reading in readings_1955.
    "v1955":     '<span class="v1955"></span>',
}


def render(text: str, spans, note_key: str = "", shy=()) -> str:
    """spans: iterable of objects with .start .end .kind (and optional .attr).

    note_key names the paragraph, as `101_4_2`, so that a footnote marker's id
    is unique in the whole book and not only within its paragraph: a section
    page carries every paragraph's notes, and the EPUB a whole paper's.

    shy: offsets before which to put a soft hyphen, U+00AD -- where the book
    lets a word break (build/hyphen.py).  The one character render() may add
    to the text, and only into paragraph.html_hy, the copy the site sets
    justified; every other consumer, and the round-trip gate, takes `html`,
    rendered without.  A raw character, never `&shy;`, which is no XML entity.
    """
    shy = set(shy)
    opens: dict[int, list] = {}
    closes: dict[int, list] = {}
    points: dict[int, list] = {}
    for s in spans:
        if s.kind in POINT or s.start == s.end:
            points.setdefault(s.start, []).append(s)
            continue
        opens.setdefault(s.start, []).append(s)
        closes.setdefault(s.end, []).append(s)

    out = []
    stack = []
    for i in range(len(text) + 1):
        # close innermost-first
        for _s in sorted(closes.get(i, []), key=lambda x: -x.start):
            while stack:
                top = stack.pop()
                out.append(f"</{WRAP[top.kind][0]}>")
                if top.end == i:
                    break
        for s in points.get(i, []):
            frag = _point(s, note_key)
            if frag:
                out.append(frag)
        # open outermost-first: widest span first, so nesting is well-formed
        for s in sorted(opens.get(i, []), key=lambda x: (-(x.end - x.start), x.kind)):
            tag, cls = WRAP[s.kind]
            attrs = f' class="{cls}"' if cls else ""
            # A link that knows where it goes (build/srt.py); a paragraph's own
            # \bibref spans carry a citation instead, and no href.
            if s.kind == "link" and isinstance(s.attr, dict) and s.attr.get("href"):
                attrs += f' href="{html.escape(s.attr["href"])}"'
            # A study note's Greek or Hebrew says which, and which way it runs.
            if s.kind == "lang" and isinstance(s.attr, dict):
                attrs += "".join(f' {k}="{html.escape(s.attr[k])}"'
                                 for k in ("lang", "dir") if s.attr.get(k))
            out.append(f"<{tag}{attrs}>")
            stack.append(s)
        if i < len(text):
            if i in shy:
                out.append("\u00ad")
            out.append(html.escape(text[i], quote=False))
    while stack:
        out.append(f"</{WRAP[stack.pop().kind][0]}>")
    return "".join(out)


def _point(s, note_key: str) -> str:
    if s.kind in ("dotleader", "v1955"):
        return POINT[s.kind]
    if s.kind == "fnref":
        n = (s.attr or {}).get("i", 0) if isinstance(s.attr, dict) else 0
        # Empty: the marker is drawn by CSS, for the same reason the dot
        # leaders are.  Anything emitted here would be text the reader copies
        # and the round-trip gate would rightly reject.
        k = f"{note_key}_{n}" if note_key else f"{n}"
        kind = (s.attr or {}).get("kind") if isinstance(s.attr, dict) else None
        # A study note's marker shows its number, 1.. in the paper, drawn from
        # data-n by CSS like the ring; it is `fn` like the ring, so that every
        # gate looking for a marker where none belongs finds this one too.
        # data-hs: it names a human source, for a switch of its own one day.
        if kind == "study":
            key, num = s.attr["key"], s.attr["n"]
            hs = ' data-hs="1"' if s.attr.get("hs") else ""
            return (f'<a class="fn" href="#fn{key}" id="fnref{key}" data-k="st"'
                    f' data-n="{num}"{hs} aria-label="Note {num}"></a>')
        if kind == "variant-1955":
            return (f'<a class="fn" href="#fn{k}" id="fnref{k}" data-k="1955"'
                    f' aria-label="1955 reading"></a>')
        return f'<a class="fn" href="#fn{k}" id="fnref{k}"></a>'
    return ""


_TAG_RE = None


def strip_tags(s: str) -> str:
    """Inverse of render(), for the round-trip gate."""
    global _TAG_RE
    if _TAG_RE is None:
        import re
        _TAG_RE = re.compile(r"<[^>]+>")
    return html.unescape(_TAG_RE.sub("", s))


def title(lines: str) -> tuple[str, str]:
    """A section title's plain text and its HTML, from its printed lines.

    Some titles are set on two or three lines, and the reader keeps the breaks
    as "\\n".  The plain title joins the lines with a space -- or with nothing
    after a dash, since "Racial Amalgamation—" breaks after its em dash.  The
    HTML is that same text with a <br/> at each break, placed after the joining
    space, so stripping its tags returns the plain title byte for byte.  The
    break is self-closed because the EPUB is XML, and HTML reads it the same.
    """
    parts = lines.split("\n")
    plain, out = parts[0], [html.escape(parts[0], quote=False)]
    for prev, line in zip(parts, parts[1:]):
        sep = "" if prev.endswith(("—", "–", "-")) else " "
        plain += sep + line
        out.append(sep + "<br/>" + html.escape(line, quote=False))
    return plain, "".join(out)
