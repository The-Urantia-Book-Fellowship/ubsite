"""Subset UB Goudy to the corpus and emit WOFF2.

UBGoudy.otf's name table records it as an OFL 1.1 derivative of Sorts Mill
Goudy, correctly renamed off the Reserved Font Name -- so the web may serve the
book's own face rather than an approximation.  `OFL.txt` ships beside it.

Goudy Handtooled BT, used for the four part-title pages, is Bitstream
proprietary and must never leave this machine; `check_rights` fails if it
appears under static/.

The subset is gated: every codepoint that occurs in the rendered corpus must be
present in the output, or the build stops.  A silently substituted glyph is
exactly the class of defect the index project spent months hunting.
"""

from __future__ import annotations

import pathlib

from fontTools import subset
from fontTools.ttLib import TTFont

FACES = [("UBGoudy.otf", "UBGoudy.woff2"),
         ("UBGoudy-Italic.otf", "UBGoudy-Italic.woff2")]
FORBIDDEN = "Goudy-Handtooled-BT.ttf"


def corpus_codepoints(con) -> set[str]:
    cps: set[str] = set()
    for (t,) in con.execute("SELECT text FROM paragraph"):
        cps.update(t)
    for (t,) in con.execute("SELECT title FROM paper"):
        cps.update(t or "")
    for (t,) in con.execute("SELECT title FROM section WHERE title IS NOT NULL"):
        cps.update(t)
    for (t,) in con.execute("SELECT text FROM index_entry"):
        cps.update(t)
    cps.update("0123456789:.,()[]-–—…'’“” /*&%#?!; ")
    return cps


def build(con, srcdir: pathlib.Path, outdir: pathlib.Path, report) -> dict:
    if (outdir / FORBIDDEN).exists():
        report.hard("font-rights", str(outdir / FORBIDDEN),
                    "Goudy Handtooled BT is proprietary and must never be served")
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = corpus_codepoints(con)
    stats = {}
    for src, dst in FACES:
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]        # keep the ligatures and smcp
        opts.name_IDs = ["*"]               # keep the OFL notice in the file
        opts.notdef_outline = True
        font = subset.load_font(str(srcdir / src), opts)
        s = subset.Subsetter(options=opts)
        s.populate(text="".join(sorted(wanted)))
        s.subset(font)
        out = outdir / dst
        subset.save_font(font, str(out), opts)
        font.close()

        have = set()
        f = TTFont(out)
        for table in f["cmap"].tables:
            have.update(chr(c) for c in table.cmap)
        f.close()
        missing = {c for c in wanted if c not in have and c.strip()}
        if missing:
            report.hard("font-missing-glyph", dst,
                        "".join(sorted(missing))[:60])
        stats[dst] = (out.stat().st_size, len(have), len(missing))
    return stats
