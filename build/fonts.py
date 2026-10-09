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
}

RE_JINJA = re.compile(r"\{[%#{].*?[%#}]\}", re.S)
RE_CODE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
RE_TAG = re.compile(r"<[^>]+>")
RE_CSS_CONTENT = re.compile(r'content:\s*"([^"]*)"')


def corpus_codepoints(con) -> set[str]:
    cps: set[str] = set()
    for q in ("SELECT text FROM paragraph",
              "SELECT title FROM paper",
              "SELECT author FROM paper WHERE author IS NOT NULL",
              "SELECT title FROM part",
              "SELECT title FROM section WHERE title IS NOT NULL",
              "SELECT text FROM index_entry",
              "SELECT path_plain FROM index_entry",     # the chips, with their ›
              "SELECT title FROM appendix",             # an appendix chip's label
              "SELECT label FROM chronology_event",     # its year and month too
              "SELECT text FROM footnote",
              "SELECT gloss FROM footnote"):
        for (t,) in con.execute(q):
            cps.update(t or "")
    cps.update("0123456789:.,()[]-–—…'’“” /*&%#?!; ")
    return cps


def chrome_codepoints(site: pathlib.Path) -> set[str]:
    """What the templates and the stylesheet draw themselves.

    The text of each template with its Jinja, its scripts and its tags taken
    out, entities decoded -- so `&nbsp;` counts and `{% if %}` does not -- and
    every string a stylesheet `content:` puts on the page.
    """
    cps: set[str] = set()
    for f in sorted((site / "templates").glob("*.html")):
        src = RE_CODE.sub(" ", RE_JINJA.sub(" ", f.read_text(encoding="utf-8")))
        cps.update(html.unescape(RE_TAG.sub(" ", src)))
    for f in sorted((site / "static").glob("*.css")):
        for s in RE_CSS_CONTENT.findall(f.read_text(encoding="utf-8")):
            cps.update(s)
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
