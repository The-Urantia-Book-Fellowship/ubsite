"""Subset UB Goudy to what the site draws, and emit WOFF2.

UBGoudy.otf's name table records it as an OFL 1.1 derivative of Sorts Mill
Goudy, correctly renamed off the Reserved Font Name -- so the web may serve the
book's own face rather than an approximation.  `OFL.txt` ships beside it.

Goudy Handtooled BT, used for the four part-title pages, is Bitstream
proprietary and must never leave this machine; the build fails if it appears
under static/.

The subset is gated: every codepoint the site can draw must be in the output,
or the build stops and nothing is written.  A silently substituted glyph is
exactly the class of defect the index project spent months hunting.  "What the
site draws" is more than the corpus: the margin chips join their levels with
`›`, a chronology date can end in `±`, and the templates and the stylesheet
carry characters of their own.  When the subset was taken from the corpus alone,
those three were drawn in whatever face the browser found instead.

Run by `make data`, into ubsite/static/fonts/, the one place it writes.
"""

from __future__ import annotations

import html
import io
import pathlib
import re
import unicodedata

from fontTools import subset
from fontTools.ttLib import TTFont

from .readers._io import read_bytes

FACES = [("UBGoudy.otf", "UBGoudy.woff2"),
         ("UBGoudy-Italic.otf", "UBGoudy-Italic.woff2")]
FORBIDDEN = "Goudy-Handtooled-BT.ttf"

# Characters the site draws on purpose in another face, and where.  The gate
# excuses these and nothing else.
ELSEWHERE = {
    "◐": "the theme button, set in the system UI face (ub.css .theme)",
    "↗": "a 1955 card's link to the committee's table, set in the system UI face"
         " (ub.css :is(.note, .pop) .src)",
    "γ": "42:5.1's SRT note names the Greek letter that became the 1955 'Y';"
         " UB Goudy has no Greek, and the serif behind it in the stack draws it",
    "\u2060": "the word joiner that holds a 1955 ring to its word (ub.css"
              " a.fn::before); it draws nothing",
}

RE_JINJA = re.compile(r"\{[%#{].*?[%#}]\}", re.S)
RE_CODE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
RE_TAG = re.compile(r"<[^>]+>")
RE_CSS_CONTENT = re.compile(r'content:\s*"([^"]*)"')
RE_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})\s?")


def corpus_codepoints(con) -> set[str]:
    cps: set[str] = set()
    for q in ("SELECT text FROM paragraph",
              "SELECT title FROM paper",
              "SELECT author FROM paper WHERE author IS NOT NULL",
              "SELECT title FROM part",
              "SELECT label || title_lines || sponsor FROM part",   # its own page
              "SELECT title FROM section WHERE title IS NOT NULL",
              "SELECT text FROM index_entry",
              "SELECT path_plain FROM index_entry",     # the chips, with their ›
              "SELECT title FROM appendix",             # an appendix chip's label
              "SELECT label FROM chronology_event",     # its year and month too
              # A study note is read from its HTML, below: its Greek, Hebrew and
              # math are drawn in other faces.
              "SELECT text FROM footnote WHERE kind <> 'study'",
              "SELECT text FROM study_source",
              "SELECT text FROM changelog",             # /changelog
              # The SRT Committee's reasons a 1955 note shows, and those of the
              # note it refers to.
              "SELECT verdict || why_text FROM srt_item WHERE id IN"
              " (SELECT srt_item_id FROM footnote UNION SELECT s.see_id FROM srt_item s"
              "  JOIN footnote f ON f.srt_item_id = s.id)"):
        for (t,) in con.execute(q):
            cps.update(t or "")
    cps.update(study_codepoints(con)[0])
    cps.update("0123456789:.,()[]-–—…'’“” /*&%#?!; ")
    # The soft hyphens of paragraph.html_hy, and the hyphen a browser may draw
    # for one at a line's end when the page does not name its own: in the
    # book's face, never a fallback's.  The press's fonts have both.
    cps.update("­‐")
    return cps


# A study note's words in another language (study_macros.py \textgreek ...):
# drawn by the device's own font, as UB Goudy has none of these scripts, and
# held to the script its `lang` names, so that nothing else slips past the gate.
SCRIPTS = {
    "grc": ((0x0370, 0x03FF), (0x1F00, 0x1FFF), (0x0300, 0x036F)),
    "he": ((0x0590, 0x05FF), (0xFB1D, 0xFB4F)),
    "hy": ((0x0530, 0x058F), (0xFB13, 0xFB17)),
    "zh": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x3000, 0x303F)),
}
RE_LANG = re.compile(r'<span class="lang" lang="([a-z]+)"[^>]*>(.*?)</span>', re.S)
RE_MATH = re.compile(r"<math\b.*?</math>", re.S)


def study_codepoints(con) -> tuple[set[str], dict[str, set[str]], list[str]]:
    """What the study notes draw: in UB Goudy, in the device's font by
    language, and in math (each <math> whole)."""
    goudy: set[str] = set()
    other: dict[str, set[str]] = {}
    maths: list[str] = []
    for (h,) in con.execute("SELECT html FROM footnote WHERE kind = 'study'"):
        maths += RE_MATH.findall(h)
        h = RE_MATH.sub(" ", h)
        for lang, inner in RE_LANG.findall(h):
            for c in html.unescape(RE_TAG.sub("", inner)):
                if c.isspace() or (c.isascii() and not c.isalnum()):
                    goudy.add(c)
                else:
                    other.setdefault(lang, set()).add(c)
        goudy.update(html.unescape(RE_TAG.sub("", RE_LANG.sub(" ", h))))
    return goudy, other, maths


def chrome_codepoints(site: pathlib.Path) -> set[str]:
    """What the templates and the stylesheet draw themselves.

    The text of each template with its Jinja, its scripts and its tags taken
    out, entities decoded -- so `&nbsp;` counts and `{% if %}` does not -- and
    every string a stylesheet `content:` puts on the page.  The EPUB's
    templates (epub/) count too: it embeds this same subset, and its own gate
    fails on a character the subset lacks.
    """
    cps: set[str] = set()
    epub = site.parent / "epub"
    for f in sorted([*(site / "templates").glob("*.html"),
                     *(epub / "templates").glob("*.xhtml")]):
        src = RE_CODE.sub(" ", RE_JINJA.sub(" ", f.read_text(encoding="utf-8")))
        cps.update(html.unescape(RE_TAG.sub(" ", src)))
    for f in sorted([*(site / "static").glob("*.css"), *epub.glob("*.css")]):
        for s in RE_CSS_CONTENT.findall(f.read_text(encoding="utf-8")):
            # "\2060" is the one character it stands for, not five.
            cps.update(RE_CSS_ESCAPE.sub(lambda m: chr(int(m[1], 16)), s))
    return cps


def build(con, srcdir: pathlib.Path, site: pathlib.Path, report) -> dict:
    outdir = site / "static" / "fonts"
    if (outdir / FORBIDDEN).exists():
        report.hard("font-rights", str(outdir / FORBIDDEN),
                    "Goudy Handtooled BT is proprietary and must never be served")
    # Spaces count -- the footer's "UB&nbsp;Goudy" needs U+00A0 -- but a line
    # break is not drawn.
    wanted = {c for c in corpus_codepoints(con) | chrome_codepoints(site)
              if unicodedata.category(c) != "Cc" and c not in ELSEWHERE}
    _, other, maths = study_codepoints(con)
    for lang, chars in sorted(other.items()):
        spans = SCRIPTS.get(lang, ())
        stray = sorted(c for c in chars if not any(a <= ord(c) <= b for a, b in spans))
        if stray:
            report.hard("study-lang-script", f"lang={lang}",
                        " ".join(f"{c} U+{ord(c):04X}" for c in stray)[:200])
    if maths:
        report.hard("study-math-font", f"{len(maths)} <math>",
                    "a study note holds math, and the site has no math font yet")
    stats = {}
    subsets = []
    for src, dst in FACES:
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]        # keep the ligatures and smcp
        opts.name_IDs = ["*"]               # keep the OFL notice in the file
        opts.notdef_outline = True
        # recalcTimestamp off: otherwise saving stamps the time into `head`, and
        # every build would change two committed files that did not change.
        font = TTFont(io.BytesIO(read_bytes(srcdir / src)), recalcTimestamp=False)
        s = subset.Subsetter(options=opts)
        s.populate(text="".join(sorted(wanted)))
        s.subset(font)
        # Gate before writing: a subset missing a glyph never reaches static/.
        have = {chr(c) for table in font["cmap"].tables for c in table.cmap}
        missing = wanted - have
        if missing:
            report.hard("font-missing-glyph", dst,
                        " ".join(f"{c} U+{ord(c):04X}" for c in sorted(missing))[:200])
        subsets.append((font, opts, dst, len(have)))
    if report.blocking:
        return stats
    outdir.mkdir(parents=True, exist_ok=True)
    for font, opts, dst, n in subsets:
        out = outdir / dst
        subset.save_font(font, str(out), opts)
        font.close()
        stats[dst] = (out.stat().st_size, n)
    return stats
